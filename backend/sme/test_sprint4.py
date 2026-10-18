import copy
import json
from pathlib import Path
from types import SimpleNamespace
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, Client
from django.utils import timezone
from .models import (Usuario, ConfiguracaoDeteccao, AlertaSurto, LeituraAlerta, RegistroAuditoria,
                     FonteEpidemiologica, LoteColeta, ReanaliseDeteccao, Anomalia, RegistroEpidemiologico)
from .detectors import PARAMETERS, MovingBaseline, MedianMAD, validate_parameters
from .detection import run_next_job, analyze_territory
from .processing import process_lote
from .indicators import REGIONS
from django.db import connection, connections, close_old_connections
from django.test import TransactionTestCase
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor


class SprintFourTests(TestCase):
    def setUp(self):
        from .test_sprint3 import ExportTests
        self.admin = Usuario.objects.create_superuser('s4-admin@example.org','Sprint4-password-2026!')
        self.user = Usuario.objects.create_user('s4-user@example.org','Sprint4-password-2026!')
        self.client.force_login(self.admin)
        self.fixture = ExportTests()
        self.lot = self.fixture.make_lot('3550308', [10]*8+[100,10])
        ReanaliseDeteccao.objects.all().delete()

    def config(self, indicator='', method='media_movel', parameters=None, base=None):
        from .detection import configuration_for
        return self.client.post('/api/deteccao/configuracoes/', {'indicador':indicator,'metodo':method,
            'parametros':parameters if parameters is not None else {**PARAMETERS,'piso':500},
            'base_id':base if base is not None else configuration_for(indicator).pk}, content_type='application/json')

    def revise(self, counts, source=None):
        source = source or self.lot.fonte
        rows = copy.deepcopy(self.lot.dados_brutos)
        for row,value in zip(rows, counts):row['casos']=value
        lot = LoteColeta.objects.create(fonte=source, indicador='infodengue_dengue', adaptador='infodengue',
            agravo='dengue',url_origem=source.url,territorio_codigo=source.recorte.codigo,
            sha256=str(LoteColeta.objects.count()),dados_brutos=rows,quantidade_registros=len(rows))
        self.assertEqual(process_lote(lot.pk).status,'sucesso')
        return lot

    def test_default_alert_preserves_week_original_and_configuration(self):
        alert = AlertaSurto.objects.get()
        self.assertEqual(alert.observado,100)
        self.assertEqual(alert.data_referencia.isoformat(),'2024-02-25')
        self.assertEqual(alert.lote_id,self.lot.pk)
        self.assertEqual(alert.configuracao.parametros,PARAMETERS)
        self.assertIn('não confirma',alert.mensagem)
        self.assertEqual(alert.configuracao.metodo,'media_movel')

    def test_reprocessing_and_overlapping_sources_do_not_duplicate_alert(self):
        for _ in range(2):process_lote(self.lot.pk)
        source = FonteEpidemiologica.objects.create(nome='Outro cadastro',tipo='json',indicador='infodengue_dengue',
            url=self.lot.fonte.url.replace('ey_end=2024','ey_end=2025'),recorte=self.lot.fonte.recorte)
        new = self.revise([10]*8+[200,10],source)
        process_lote(self.lot.pk)
        self.assertEqual(AlertaSurto.objects.count(),1)
        alert = AlertaSurto.objects.get()
        self.assertEqual((alert.observado,alert.lote_id),(200,new.pk))
        self.assertEqual(Anomalia.objects.filter(ativa=True).count(),1)
        panel=self.client.get('/api/indicadores/',{'codigo':'3550308','agravo':'dengue'}).json()
        self.assertEqual(panel['serie'][8]['casos'],alert.observado)

    def test_data_revision_withdraws_alert_and_keeps_history(self):
        old = AlertaSurto.objects.get()
        self.revise([10]*10)
        old.refresh_from_db();self.assertFalse(old.ativa)
        self.assertEqual(old.observado,100)
        self.assertEqual(old.lote_id,self.lot.pk)
        self.assertEqual(self.client.get('/api/alertas/').json()['count'],0)
        self.assertEqual(self.client.get('/api/alertas/',{'situacao':'encerradas'}).json()['count'],1)

    def test_read_status_is_individual_and_new_revision_becomes_unread(self):
        alert = AlertaSurto.objects.get()
        self.assertEqual(self.client.get('/api/alertas/').json()['nao_lidas'],1)
        self.assertEqual(self.client.post(f'/api/alertas/{alert.pk}/ler/',{'revisao':alert.revisao},content_type='application/json').status_code,200)
        self.assertEqual(self.client.get('/api/alertas/').json()['nao_lidas'],0)
        other=Client();other.force_login(self.user)
        self.assertEqual(other.get('/api/alertas/').json()['nao_lidas'],1)
        self.revise([10]*8+[150,10])
        self.assertEqual(self.client.get('/api/alertas/').json()['nao_lidas'],1)
        self.assertEqual(self.client.post(f'/api/alertas/{alert.pk}/ler/',{'revisao':1},content_type='application/json').status_code,409)

    def test_alert_permissions_pagination_scope_and_csrf(self):
        alert=AlertaSurto.objects.get()
        self.assertEqual(self.client.get('/api/alertas/',{'codigo':'3510500'}).json()['count'],0)
        self.assertEqual(self.client.get('/api/alertas/',{'indicador':'infodengue_zika'}).json()['count'],0)
        for params in [{'codigo':'bad'},{'situacao':'bad'},{'indicador':'bad'}]:
            self.assertEqual(self.client.get('/api/alertas/',params).status_code,400)
        c=Client(enforce_csrf_checks=True);c.force_login(self.user)
        self.assertEqual(c.post(f'/api/alertas/{alert.pk}/ler/',{'revisao':1},content_type='application/json').status_code,403)
        self.client.logout();self.assertEqual(self.client.get('/api/alertas/').status_code,401)

    def test_configuration_creates_immutable_version_and_reanalysis(self):
        old=ConfiguracaoDeteccao.objects.get(ativa=True)
        response=self.config()
        self.assertEqual(response.status_code,202,response.content)
        config=ConfiguracaoDeteccao.objects.get(pk=response.json()['configuracao']['id'])
        old.refresh_from_db();self.assertFalse(old.ativa)
        self.assertEqual(old.parametros,PARAMETERS)
        self.assertEqual(config.versao,2)
        self.assertEqual(config.criada_por,self.admin)
        self.assertFalse(AlertaSurto.objects.get(configuracao=old).ativa)
        self.assertEqual(run_next_job().status,'sucesso')
        self.assertFalse(AlertaSurto.objects.filter(ativa=True).exists())
        self.assertEqual(RegistroAuditoria.objects.get(acao='detector_configurado').entidade_id,config.pk)
        panel=self.client.get('/api/indicadores/',{'codigo':'3550308','agravo':'dengue'}).json()
        self.assertEqual(panel['detector']['id'],config.pk)
        self.assertEqual(panel['anomalias'],0)

    def test_stale_configuration_conflict_and_invalid_parameters_are_atomic(self):
        old=ConfiguracaoDeteccao.objects.get(ativa=True)
        for changes in [{'janela':True},{'janela':3},{'janela':53},{'piso':-1},{'desvios':float('inf')},{'razao_minima':'2'}]:
            response=self.config(parameters={**PARAMETERS,**changes})
            self.assertEqual(response.status_code,400)
        self.assertEqual(ConfiguracaoDeteccao.objects.count(),1)
        self.assertEqual(self.config().status_code,202)
        self.assertEqual(self.config(base=old.pk).status_code,409)
        self.assertEqual(ConfiguracaoDeteccao.objects.count(),2)

    def test_indicator_override_is_isolated_from_global_change(self):
        from .detection import configuration_for
        response=self.config(indicator='infodengue_dengue')
        override=response.json()['configuracao']['id'];run_next_job()
        self.assertEqual(self.config(parameters={**PARAMETERS,'piso':200}).status_code,202)
        run_next_job()
        self.assertEqual(configuration_for('infodengue_dengue').pk,override)
        self.assertNotEqual(configuration_for('infodengue_zika').pk,override)

    def test_origin_can_return_to_global_configuration(self):
        from .detection import configuration_for
        override=self.config(indicator='infodengue_dengue').json()['configuracao']['id']
        run_next_job()
        response=self.client.post('/api/deteccao/origens/infodengue_dengue/padrao/',{},content_type='application/json')
        self.assertEqual(response.status_code,202,response.content)
        self.assertNotEqual(configuration_for('infodengue_dengue').pk,override)
        self.assertEqual(run_next_job().status,'sucesso')
        self.assertTrue(AlertaSurto.objects.filter(ativa=True).exists())

    def test_older_job_is_superseded_and_retry_is_idempotent(self):
        first=self.config().json()['configuracao']['id']
        second=self.config(parameters={**PARAMETERS,'piso':5}).json()['configuracao']['id']
        self.assertEqual(run_next_job().status,'substituida')
        self.assertEqual(run_next_job().status,'sucesso')
        self.assertEqual(AlertaSurto.objects.filter(ativa=True).count(),1)
        for _ in range(2):
            self.assertEqual(self.client.post(f'/api/deteccao/configuracoes/{second}/reanalisar/',{},content_type='application/json').status_code,202)
        self.assertEqual(ReanaliseDeteccao.objects.filter(configuracao_id=second,status='pendente').count(),1)
        run_next_job()
        self.assertEqual(AlertaSurto.objects.filter(ativa=True).count(),1)
        self.assertEqual(self.client.post(f'/api/deteccao/configuracoes/{first}/reanalisar/',{},content_type='application/json').status_code,404)

    def test_job_failure_keeps_records_and_can_be_retried(self):
        config=self.config().json()['configuracao']['id']
        before=list(RegistroEpidemiologico.objects.values_list('pk','casos'))
        with patch('sme.detection.analyze_territory',side_effect=RuntimeError('QA failure')):
            self.assertEqual(run_next_job().status,'erro')
        self.assertEqual(list(RegistroEpidemiologico.objects.values_list('pk','casos')),before)
        self.client.post(f'/api/deteccao/configuracoes/{config}/reanalisar/',{},content_type='application/json')
        self.assertEqual(run_next_job().status,'sucesso')

    def test_stale_running_job_is_recovered(self):
        self.config()
        job=ReanaliseDeteccao.objects.get()
        ReanaliseDeteccao.objects.filter(pk=job.pk).update(status='executando',atualizada_em=timezone.now()-timedelta(minutes=11))
        self.assertEqual(run_next_job().status,'sucesso')

    def test_mad_strategy_can_be_selected_without_code_changes(self):
        response=self.config(method='mediana_mad',parameters={'janela':8,'fator_mad':3,'razao_minima':2,'piso':5})
        self.assertEqual(response.status_code,202,response.content)
        self.assertEqual(run_next_job().status,'sucesso')
        self.assertEqual(AlertaSurto.objects.get(ativa=True).configuracao.metodo,'mediana_mad')

    def test_configuration_is_admin_only_and_csrf_protected(self):
        guarded=Client(enforce_csrf_checks=True);guarded.force_login(self.admin)
        self.assertEqual(guarded.post('/api/deteccao/configuracoes/',{},content_type='application/json').status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/api/deteccao/configuracoes/').status_code,403)
        self.assertEqual(self.config().status_code,403)
        self.client.logout();self.assertEqual(self.client.get('/api/deteccao/configuracoes/').status_code,401)

    def test_causal_detectors_do_not_use_future_or_current_for_baseline(self):
        points=[{'data':(timezone.now().date()+timedelta(weeks=i)), 'casos':10 if i<8 else 100} for i in range(10)]
        for detector in [MovingBaseline(),MedianMAD()]:
            result=detector.analyze(points)
            self.assertEqual(result[0]['referencia'],10)
            changed=copy.deepcopy(points);changed[-1]['casos']=100000
            self.assertEqual(result[0],detector.analyze(changed)[0])
            changed=copy.deepcopy(points);changed[5]['casos']=None
            self.assertFalse(detector.analyze(changed))

    def test_comparison_uses_one_indicator_period_and_preserves_gaps(self):
        self.fixture.make_lot('3510500',[5,None,7])
        response=self.client.get('/api/indicadores/comparar/',{'tipo':'municipio','codigos':'3550308,3510500',
            'agravo':'dengue','indicador':'infodengue_dengue','inicio':'2023-12-31','fim':'2024-01-14'})
        self.assertEqual(response.status_code,200,response.content)
        data=response.json()['series']
        self.assertEqual([r['casos'] for r in data[0]['serie']],[10,10,10])
        self.assertEqual([r['casos'] for r in data[1]['serie']],[5,None,7])
        self.assertEqual(data[0]['detector'],data[1]['detector'])

    def test_comparison_regions_and_read_only_access(self):
        self.fixture.make_lot('3510500',[10]*8+[150])
        codes=','.join([REGIONS[c]['regiao_codigo'] for c in ['3550308','3510500']])
        self.client.force_login(self.user)
        result=self.client.get('/api/indicadores/comparar/',{'tipo':'regiao','codigos':codes,
            'agravo':'dengue','indicador':'infodengue_dengue'})
        self.assertEqual(result.status_code,200,result.content)
        self.assertTrue(all(r['municipios_cobertos']<r['municipios_regiao'] for r in result.json()['series']))
        for params in [{'codigos':'3550308'},{'codigos':'3550308,3550308'}, {'codigos':'3550308,bad'},
                       {'codigos':'3550308,3510500','indicador':'bad'}, {'codigos':'3550308,3510500','agravo':'zika'}]:
            query={'tipo':'municipio','agravo':'dengue','indicador':'infodengue_dengue',**params}
            self.assertEqual(self.client.get('/api/indicadores/comparar/',query).status_code,400)

    def test_preserved_real_peak_with_and_without_previous_year(self):
        from .collection import InfoDengueAdapter
        url='https://info.dengue.mat.br/api/alertcity?geocode=3550308&disease=dengue&format=json&ew_start=1&ew_end=52&ey_start=2023&ey_end=2024'
        source=SimpleNamespace(url=url,tipo='json',recorte=SimpleNamespace(tipo='municipio',codigo='3550308',nome='São Paulo',uf='SP'))
        raw=json.loads(Path(__file__).with_name('fixtures').joinpath('validation/infodengue_sp_2023_2024.json').read_bytes())
        points=InfoDengueAdapter().normalize(raw,source)
        selected=[p for p in points if p['ano']==2024]
        peak=max(selected,key=lambda p:p['casos'])
        self.assertEqual((peak['semana'],peak['casos']),(19,85389))
        self.assertFalse(MovingBaseline().analyze(selected))
        flags=[f for f in MovingBaseline().analyze(points) if f['data']>=selected[0]['data']]
        self.assertEqual(len(flags),6)
        self.assertLess(flags[0]['data'],peak['data'])


@skipUnless(connection.vendor == 'postgresql', 'Concorrência exige PostgreSQL.')
class SprintFourConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from .models import PerfilAcesso
        from .test_sprint3 import ExportTests
        PerfilAcesso.objects.get_or_create(codigo='administrador',defaults={'nome':'Administrador','permissoes':[]})
        self.config,_=ConfiguracaoDeteccao.objects.get_or_create(metodo='media_movel',versao=1,
            defaults={'ativa':True,'parametros':PARAMETERS})
        self.admin=Usuario.objects.create_superuser('race@example.org','Race-password-2026!')
        self.lot=ExportTests().make_lot('3550308',[10]*8+[100])
        ReanaliseDeteccao.objects.all().delete()

    def parallel(self, operation):
        def isolated(index):
            close_old_connections()
            try:return operation(index)
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(isolated,i) for i in range(2)]
            return [f.result(timeout=20) for f in futures]

    def test_simultaneous_activation_keeps_one_active_version(self):
        def save(index):
            client=Client();client.force_login(Usuario.objects.get(pk=self.admin.pk))
            return client.post('/api/deteccao/configuracoes/',{'metodo':'media_movel','indicador':'',
                'parametros':{**PARAMETERS,'piso':500+index},'base_id':self.config.pk},content_type='application/json').status_code
        self.assertEqual(sorted(self.parallel(save)),[202,409])
        self.assertEqual(ConfiguracaoDeteccao.objects.filter(ativa=True,indicador='').count(),1)

    def test_simultaneous_reprocessing_does_not_duplicate_alert(self):
        self.parallel(lambda _:process_lote(self.lot.pk).status)
        self.assertEqual(AlertaSurto.objects.filter(ativa=True).count(),1)


    def test_two_workers_claim_a_job_once(self):
        ReanaliseDeteccao.objects.create(configuracao=self.config)
        results=self.parallel(lambda _:getattr(run_next_job(),'status',None))
        self.assertEqual(sorted(str(v) for v in results),['None','sucesso'])
        self.assertEqual(AlertaSurto.objects.filter(ativa=True).count(),1)

class SprintFourMigrationTests(TransactionTestCase):
    def test_legacy_observations_and_configuration_are_preserved(self):
        from django.db.migrations.executor import MigrationExecutor
        previous=[('sme','0008_alter_perfilacesso_permissoes')]
        executor=MigrationExecutor(connection);latest=executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        try:
            apps=executor.loader.project_state(previous).apps
            config,_=apps.get_model('sme','ConfiguracaoDeteccao').objects.get_or_create(metodo='media_movel',versao=1,defaults={'parametros':PARAMETERS})
            territory=apps.get_model('sme','RecorteGeografico').objects.create(tipo='municipio',codigo='3550308',nome='São Paulo',uf='SP')
            source=apps.get_model('sme','FonteEpidemiologica').objects.create(nome='Legado',tipo='json',indicador='infodengue_dengue',url='https://example.org',recorte=territory)
            disease=apps.get_model('sme','Agravo').objects.create(codigo='dengue',nome='Dengue')
            lot=apps.get_model('sme','LoteColeta').objects.create(fonte=source,indicador='infodengue_dengue',adaptador='infodengue',agravo='dengue',url_origem=source.url,territorio_codigo='3550308',sha256='a'*64,dados_brutos=[{'preservado':True}],quantidade_registros=1)
            series=apps.get_model('sme','SerieEpidemiologica').objects.create(fonte=source,recorte=territory,agravo=disease,indicador='infodengue_dengue')
            record=apps.get_model('sme','RegistroEpidemiologico').objects.create(serie=series,ano=2024,semana=1,data_referencia='2023-12-31',casos=100,lote=lot)
            anomaly=apps.get_model('sme','Anomalia').objects.create(registro=record,configuracao=config,observado=100,referencia=10,limiar=20)
        finally:
            MigrationExecutor(connection).migrate(latest)
        self.assertEqual(RegistroEpidemiologico.objects.get(pk=record.pk).casos,100)
        self.assertEqual(LoteColeta.objects.get(pk=lot.pk).dados_brutos,[{'preservado':True}])
        self.assertTrue(ConfiguracaoDeteccao.objects.get(pk=config.pk).ativa)
        self.assertEqual(Anomalia.objects.get(pk=anomaly.pk).observado,100)
        self.assertEqual(ReanaliseDeteccao.objects.get().configuracao_id,config.pk)
