import hashlib
import json
from datetime import datetime, time, timezone as utc, timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from .models import (RecorteGeografico, FonteEpidemiologica, LoteColeta, RegistroEpidemiologico,
                     SerieEpidemiologica, ProcessamentoLote, Anomalia, ConfiguracaoDeteccao)
from .processing import process_lote, week_start, MovingBaseline
from .indicators import REGIONS
from .collection import collect_source


class SprintTwoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('viewer@example.org','Old-strong-password-2026!')
        self.client.force_login(self.user)
        self.source = self.make_source('3550308')

    def make_source(self, code, variant=''):
        territory,_=RecorteGeografico.objects.get_or_create(tipo='municipio',codigo=code,defaults={'nome':REGIONS[code]['nome'],'uf':'SP'})
        return FonteEpidemiologica.objects.create(nome='InfoDengue '+code+variant,tipo='json',recorte=territory,
            url=f'https://info.dengue.mat.br/api/alertcity?geocode={code}&disease=dengue&format=json&ew_start=0{variant}1&ew_end=52&ey_start=2024&ey_end=2024')

    def make_lote(self, cases, source=None):
        source=source or self.source
        rows=[]
        for i, value in enumerate(cases):
            day=week_start(2024,i+1)
            rows.append({'SE':202400+i+1,'casos':value,'casos_est':None if value is None else value*1.5,
                         'data_iniSE':int(datetime.combine(day,time(),tzinfo=utc.utc).timestamp()*1000),
                         'municipio_nome':source.recorte.nome,'id':int(source.recorte.codigo+str(202400+i+1)+'00001')})
        digest=hashlib.sha256(json.dumps(rows).encode()).hexdigest()
        return LoteColeta.objects.create(fonte=source,adaptador='infodengue',agravo='dengue',url_origem=source.url,
            territorio_codigo=source.recorte.codigo,sha256=digest,dados_brutos=rows,quantidade_registros=len(rows))

    def query(self, **params):
        return self.client.get('/api/indicadores/', {'tipo':'municipio','codigo':'3550308','agravo':'dengue',**params})

    def test_normalizes_dates_sorts_and_preserves_estimates_separately(self):
        lote=self.make_lote([2,4,6]);lote.dados_brutos.reverse();lote.save()
        self.assertEqual(process_lote(lote.pk).status,'sucesso')
        rows=list(RegistroEpidemiologico.objects.all())
        self.assertEqual([r.casos for r in rows],[2,4,6])
        self.assertEqual(rows[0].data_referencia.isoformat(),'2023-12-31')
        self.assertEqual(rows[0].casos_estimados,3)
        self.assertEqual(rows[0].lote_id,lote.pk)

    def test_reprocess_is_idempotent_and_old_lote_cannot_overwrite_revision(self):
        old=self.make_lote([2,4]);new=self.make_lote([20,40])
        process_lote(old.pk);process_lote(new.pk);process_lote(old.pk)
        self.assertEqual(list(RegistroEpidemiologico.objects.values_list('casos',flat=True)),[20,40])
        self.assertEqual(SerieEpidemiologica.objects.count(),1)

    def test_corrupt_lote_records_error_without_partial_data(self):
        lote=self.make_lote([2,4]);lote.dados_brutos[1]['data_iniSE']+=86400000;lote.save()
        result=process_lote(lote.pk)
        self.assertEqual(result.status,'erro')
        self.assertIn('semana',result.mensagem)
        self.assertFalse(RegistroEpidemiologico.objects.exists())
        lote.refresh_from_db();self.assertEqual(len(lote.dados_brutos),2)

    def test_fractional_cases_and_invalid_estimates_are_rejected(self):
        for field,value in [('casos',1.5),('casos_est',-1),('casos_est',True)]:
            lote=self.make_lote([5]);lote.dados_brutos[0][field]=value;lote.sha256=hashlib.sha256(json.dumps(lote.dados_brutos).encode()).hexdigest();lote.save()
            self.assertEqual(process_lote(lote.pk).status,'erro')
        self.assertFalse(RegistroEpidemiologico.objects.exists())

    def test_nulls_and_gaps_are_not_zero(self):
        lote=self.make_lote([0,None,2]);process_lote(lote.pk)
        data=self.query().json()
        self.assertEqual([p['casos'] for p in data['serie']],[0,None,2])
        self.assertEqual(data['semanas_sem_dados'],1)
        self.assertIsNone(data['tendencia_percentual'])
        self.assertFalse(any(p['anomalia'] for p in data['serie']))

    def test_missing_week_is_exposed_as_gap(self):
        lote=self.make_lote([1,2,3]);lote.dados_brutos.pop(1);lote.save();process_lote(lote.pk)
        self.assertEqual([p['casos'] for p in self.query().json()['serie']],[1,None,3])

    def test_empty_lote_does_not_create_zero_series(self):
        lote=self.make_lote([])
        self.assertEqual(process_lote(lote.pk).status,'sucesso')
        self.assertFalse(SerieEpidemiologica.objects.exists())

    def test_detection_uses_only_previous_complete_weeks_and_is_versioned(self):
        lote=self.make_lote([10]*8+[100]);process_lote(lote.pk)
        data=self.query().json()
        self.assertEqual(data['anomalias'],1)
        self.assertFalse(any(p['anomalia'] for p in data['serie'][:8]))
        anomaly=Anomalia.objects.get(ativa=True)
        self.assertEqual(anomaly.observado,100)
        self.assertEqual(anomaly.referencia,10)
        self.assertEqual(anomaly.limiar,20)
        self.assertEqual(anomaly.configuracao.versao,1)
        self.assertEqual(anomaly.configuracao.parametros['janela'],8)

    def test_detection_does_not_bridge_missing_weeks(self):
        lote=self.make_lote([10]*7+[None,100]);process_lote(lote.pk)
        self.assertFalse(Anomalia.objects.filter(ativa=True).exists())

    def test_corrected_peak_removes_current_signal(self):
        process_lote(self.make_lote([10]*8+[100]).pk)
        process_lote(self.make_lote([10]*9).pk)
        self.assertFalse(Anomalia.objects.filter(ativa=True).exists())
        self.assertEqual(self.query().json()['anomalias'],0)

    def test_filters_do_not_change_detection_baseline(self):
        process_lote(self.make_lote([10]*8+[100]).pk)
        start=week_start(2024,9).isoformat()
        data=self.query(inicio=start,fim=start).json()
        self.assertEqual(len(data['serie']),1)
        self.assertTrue(data['serie'][0]['anomalia'])

    def test_trend_compares_two_complete_blocks_of_four_weeks(self):
        process_lote(self.make_lote([10]*4+[20]*4).pk)
        self.assertEqual(self.query().json()['tendencia_percentual'],100)

    def test_region_aggregates_only_collected_municipalities_without_double_count(self):
        process_lote(self.make_lote([10]*9).pk)
        code=next(c for c,v in REGIONS.items() if c!='3550308' and v['regiao_codigo']==REGIONS['3550308']['regiao_codigo'])
        second=self.make_source(code)
        process_lote(self.make_lote([5]*9,second).pk)
        duplicate=self.make_source('3550308','0')
        self.assertEqual(process_lote(self.make_lote([10]*9,duplicate).pk).status,'sucesso')
        data=self.query(tipo='regiao',codigo=REGIONS['3550308']['regiao_codigo']).json()
        self.assertEqual(data['municipios_cobertos'],2)
        self.assertGreater(data['municipios_regiao'],2)
        self.assertEqual(data['serie'][0]['casos'],15)
        self.assertEqual(data['casos_total'],135)

    def test_options_and_invalid_queries(self):
        process_lote(self.make_lote([10]).pk)
        data=self.client.get('/api/indicadores/opcoes/').json()
        self.assertEqual(data['municipios'][0]['codigo'],'3550308')
        self.assertEqual(data['agravos'][0]['codigo'],'dengue')
        for params in [{'codigo':'garbage'},{'tipo':'outro'},{'inicio':'2024-99-99'},{'inicio':'2024-02-01','fim':'2024-01-01'},{'agravo':'zika'}]:
            self.assertEqual(self.query(**params).status_code,400)
        self.client.logout()
        self.assertEqual(self.query().status_code,401)
        self.assertEqual(self.client.get('/api/indicadores/opcoes/').status_code,401)

    def test_week_calendar_boundaries_and_invalid_week_53(self):
        self.assertEqual(week_start(2020,53).isoformat(),'2020-12-27')
        self.assertEqual(week_start(2021,1).isoformat(),'2021-01-03')
        with self.assertRaises(Exception):week_start(2021,53)

    @patch('sme.collection.InfoDengueAdapter.fetch')
    def test_collection_automatically_processes_new_lote(self,fetch):
        fixture=self.make_lote([5]);rows=fixture.dados_brutos;fixture.delete()
        fetch.return_value=rows
        run=collect_source(self.source.pk)
        self.assertEqual(run.status,'sucesso')
        self.assertEqual(run.lote.processamento.status,'sucesso')
        self.assertEqual(RegistroEpidemiologico.objects.get().casos,5)

    def test_password_change_preserves_current_session_and_invalidates_other(self):
        other=Client();other.force_login(self.user)
        old_session=self.client.session.session_key
        response=self.client.post('/api/auth/password/',{'old_password':'Old-strong-password-2026!',
            'new_password':'New-strong-password-2026!','confirmation':'New-strong-password-2026!'},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertNotEqual(self.client.session.session_key,old_session)
        self.assertEqual(self.client.get('/api/auth/me/').status_code,200)
        self.assertEqual(other.get('/api/auth/me/').status_code,401)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('New-strong-password-2026!'))

    def test_password_change_validation_throttle_and_csrf(self):
        data={'old_password':'wrong','new_password':'New-strong-password-2026!','confirmation':'New-strong-password-2026!'}
        for _ in range(5):self.assertEqual(self.client.post('/api/auth/password/',data,content_type='application/json').status_code,400)
        self.assertEqual(self.client.post('/api/auth/password/',data,content_type='application/json').status_code,429)
        guarded=Client(enforce_csrf_checks=True);guarded.force_login(self.user)
        self.assertEqual(guarded.post('/api/auth/password/',data,content_type='application/json').status_code,403)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('Old-strong-password-2026!'))


    def test_failed_reprocessing_rolls_back_existing_records(self):
        lote=self.make_lote([2,4]);process_lote(lote.pk)
        config=ConfiguracaoDeteccao.objects.get()
        config.parametros={'janela':99};config.save()
        newer=self.make_lote([20,40])
        self.assertEqual(process_lote(newer.pk).status,'erro')
        self.assertEqual(list(RegistroEpidemiologico.objects.values_list('casos',flat=True)),[2,4])

    def test_weak_password_mismatch_and_anonymous_changes_are_rejected(self):
        for password,confirmation in [('short','short'),('Secure-secret-2026!','different')]:
            response=self.client.post('/api/auth/password/',{'old_password':'Old-strong-password-2026!',
                'new_password':password,'confirmation':confirmation},content_type='application/json')
            self.assertEqual(response.status_code,400)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('Old-strong-password-2026!'))
        self.client.logout()
        self.assertEqual(self.client.post('/api/auth/password/',{},content_type='application/json').status_code,401)

    def test_data_origin_and_updated_timestamp_are_present(self):
        process_lote(self.make_lote([10]).pk)
        data=self.query().json()
        self.assertTrue(data['atualizado_em'])
        self.assertEqual(data['fontes'][0]['url'],self.source.url)
        self.assertEqual(data['fontes'][0]['nome'],self.source.nome)


    def test_admin_processing_failure_summary_follows_latest_lote(self):
        lote=self.make_lote([10]);lote.dados_brutos[0]['data_iniSE']=0;lote.save();process_lote(lote.pk)
        self.assertEqual(self.client.get('/api/fontes/').json()['falhas_processamento'],1)
        process_lote(self.make_lote([20]).pk)
        self.assertEqual(self.client.get('/api/fontes/').json()['falhas_processamento'],0)

    def test_eight_year_series_query(self):
        import time as clock
        for first in [2017,2019,2021,2023]:
            rows=[]
            for year in [first,first+1]:
                for week in range(1,54):
                    try:day=week_start(year,week)
                    except Exception:continue
                    rows.append({'SE':year*100+week,'casos':20+week%10,'data_iniSE':int(datetime.combine(day,time(),tzinfo=utc.utc).timestamp()*1000),
                        'municipio_nome':self.source.recorte.nome,'id':int('3550308'+str(year*100+week)+'00001')})
            url=self.source.url.replace('ey_start=2024',f'ey_start={first}').replace('ey_end=2024',f'ey_end={first+1}').replace('ew_end=52','ew_end=53')
            lote=LoteColeta.objects.create(fonte=self.source,adaptador='infodengue',agravo='dengue',url_origem=url,
                territorio_codigo='3550308',sha256=hashlib.sha256(json.dumps(rows).encode()).hexdigest(),dados_brutos=rows,quantidade_registros=len(rows))
            self.assertEqual(process_lote(lote.pk).status,'sucesso')
        started=clock.perf_counter();response=self.query();elapsed=clock.perf_counter()-started
        self.assertEqual(response.status_code,200)
        self.assertGreaterEqual(len(response.json()['serie']),416)
        self.assertEqual(response.json()['semanas_sem_dados'],0)
        print(f'Consulta de 8 anos: {len(response.json()["serie"])} semanas, {elapsed:.3f}s')
