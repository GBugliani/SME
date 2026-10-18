import json
from datetime import date
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from .models import Usuario, FonteEpidemiologica, RegistroEpidemiologico, AlertaSurto, LoteColeta
from .collection import collect_source, eligible_source_ids, CollectionError
from .collection_period import collection_source
from .processing import process_lote, week_start
from .datasets import SIVEP_URL


class RollingCollectionTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser('rolling@example.org', 'Rolling-tests-2026!')
        self.client.force_login(self.admin)

    def create_source(self, **changes):
        response = self.client.post('/api/fontes/', {'provedor':'infodengue', 'agravo':'dengue',
            'municipio':'3550308', 'ativa':True, 'periodo_movel':True, **changes}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        return FonteEpidemiologica.objects.get(pk=response.json()['source']['id'])

    @staticmethod
    def response_for(source, year):
        return [{'SE':year*100+1, 'data_iniSE':week_start(year,1).isoformat(), 'casos':10,
            'id':int(source.recorte.codigo+str(year*100+1)+'00001'), 'municipio_nome':source.recorte.nome}]

    def test_resolves_each_execution_rolls_year_and_preserves_history_and_provenance(self):
        with patch('django.utils.timezone.localdate', return_value=date(2025,12,31)):
            source = self.create_source()
            self.assertEqual(parse_qs(urlsplit(source.url).query)['ew_end'], ['53'])
            with patch('sme.collection.fetch_public', return_value=(json.dumps(self.response_for(source,2025)).encode(), {})):
                first = collect_source(source.pk)
                repeated = collect_source(source.pk)
            self.assertEqual(first.status, 'sucesso', first.mensagem)
            self.assertEqual(first.lote_id, repeated.lote_id)
        with patch('django.utils.timezone.localdate', return_value=date(2026,1,5)):
            self.assertIn(source.pk, eligible_source_ids())
            with patch('sme.collection.fetch_public', return_value=(json.dumps(self.response_for(source,2026)).encode(), {})):
                second = collect_source(source.pk)
            self.assertEqual(second.status, 'sucesso', second.mensagem)
            self.assertEqual(parse_qs(urlsplit(second.lote.url_origem).query)['ey_start'], ['2025'])
            self.assertEqual(parse_qs(urlsplit(second.lote.url_origem).query)['ey_end'], ['2026'])
            self.assertTrue(second.lote.proveniencia['periodo_movel'])
            self.assertEqual(RegistroEpidemiologico.objects.count(), 2)
            source.refresh_from_db()
            self.assertEqual(source.url, first.lote.url_origem)
            self.assertEqual(process_lote(first.lote_id).status, 'sucesso')
            self.assertEqual(RegistroEpidemiologico.objects.count(), 2)

    def test_fixed_source_unchanged_and_invalid_rolling_rejected(self):
        source = self.create_source(periodo_movel=False, ano_inicio=2024, ano_fim=2024)
        self.assertIs(collection_source(source), source)
        for changes in [{'periodo_movel':'false'}, {'provedor':'infogripe', 'agravo':'srag'}]:
            response = self.client.post('/api/fontes/', {'provedor':'infodengue', 'municipio':'3550308',
                'ativa':True, 'periodo_movel':True, **changes}, content_type='application/json')
            self.assertEqual(response.status_code, 400)

    def test_assisted_edit_keeps_history_and_updates_collection_mode(self):
        source = self.create_source(periodo_movel=False, ano_inicio=2024, ano_fim=2024)
        with patch('sme.collection.fetch_public', return_value=(json.dumps(self.response_for(source,2024)).encode(), {})):
            run=collect_source(source.pk)
        response=self.client.put(f'/api/fontes/{source.pk}/', {'provedor':'infodengue', 'municipio':'3550308',
            'ativa':True, 'periodo_movel':True}, content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertTrue(response.json()['source']['periodo_movel'])
        self.assertEqual(LoteColeta.objects.get().url_origem, run.lote.url_origem)
        self.assertEqual(RegistroEpidemiologico.objects.count(),1)

    def test_failure_preserves_last_success_data_and_next_execution_recovers(self):
        source=self.create_source()
        year=timezone.localdate().year
        with patch('sme.collection.fetch_public', return_value=(json.dumps(self.response_for(source,year)).encode(), {})):
            first=collect_source(source.pk)
        source.refresh_from_db(); checked=source.ultima_coleta_em
        with patch('sme.collection.fetch_public', side_effect=CollectionError('Indisponível')):
            failed=collect_source(source.pk)
        self.assertEqual(failed.status,'erro')
        source.refresh_from_db();self.assertEqual(source.ultima_coleta_em,checked)
        self.assertEqual(RegistroEpidemiologico.objects.count(),1)
        with patch('sme.collection.fetch_public', return_value=(json.dumps(self.response_for(source,year)).encode(), {})):
            retry=collect_source(source.pk)
        self.assertEqual(retry.lote_id,first.lote_id)

    def test_sivep_rollover_unpublished_year_is_explicit_failure(self):
        with patch('django.utils.timezone.localdate',return_value=date(2025,12,31)):
            source=self.create_source(provedor='sivep',agravo='srag')
            self.assertEqual(source.url,SIVEP_URL+'?ano=2025')
        with patch('django.utils.timezone.localdate',return_value=date(2026,1,5)):
            self.assertEqual(collection_source(source).url,SIVEP_URL+'?ano=2026')
            with patch('sme.sivep.fetch_public',return_value=(b'[{"name":"2025","type":"tree"}]',{})):
                failed=collect_source(source.pk)
        self.assertEqual(failed.status,'erro')
        self.assertIn('ainda não publicou',failed.mensagem)
        self.assertFalse(source.lotes.exists())

    def test_duplicate_rolling_for_same_indicator_city_is_rejected(self):
        self.create_source()
        response=self.client.post('/api/fontes/', {'provedor':'infodengue','municipio':'3550308',
            'periodo_movel':True,'ativa':True},content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(FonteEpidemiologica.objects.count(),1)

    def test_rolling_does_not_sanitize_unsafe_configuration_into_allowed_request(self):
        source=self.create_source()
        source.url=source.url.replace('info.dengue.mat.br','127.0.0.1')
        source.save()
        with self.assertRaises(CollectionError):
            collection_source(source)
        self.assertNotIn(source.pk,eligible_source_ids())


class DataQualityAndAlertFiltersTests(TestCase):
    def setUp(self):
        from .test_sprint3 import ExportTests
        self.user=Usuario.objects.create_user('quality-reader@example.org','Quality-tests-2026!')
        self.client.force_login(self.user)
        self.fixture=ExportTests()
        self.lot=self.fixture.make_lot('3550308',[0]*8+[100,None,0,0])
        self.params={'codigo':'3550308','agravo':'dengue','indicador':'infodengue_dengue'}

    def panel(self,**params):
        response=self.client.get('/api/indicadores/',{**self.params,**params})
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def test_zero_gap_and_warmup_are_distinct(self):
        data=self.panel()
        q=data['qualidade']
        self.assertEqual(q['semanas_esperadas'],12)
        self.assertEqual(q['semanas_completas'],11)
        self.assertEqual(q['semanas_sem_contagem_completa'],1)
        self.assertEqual(q['semanas_avaliaveis'],1)
        self.assertEqual(q['semanas_com_dados_sem_base'],10)
        self.assertEqual(q['completude_percentual'],91.7)

    def test_filtered_period_uses_prior_history_and_counts_boundary_gaps(self):
        day=str(week_start(2024,9))
        data=self.panel(inicio=day,fim=day)
        self.assertEqual(data['qualidade']['semanas_avaliaveis'],1)
        self.assertTrue(data['atualidade']['periodo_historico'])
        data=self.panel(inicio='2023-12-24',fim=str(week_start(2024,13)))
        self.assertEqual(data['qualidade']['semanas_esperadas'],14)
        self.assertEqual(data['qualidade']['semanas_sem_contagem_completa'],3)
        empty=self.panel(inicio='2025-01-01',fim='2025-01-31')
        self.assertEqual(empty['qualidade']['semanas_completas'],0)
        self.assertIsNotNone(empty['atualidade']['ultima_semana_base'])

    def test_recent_collection_does_not_make_old_weeks_current(self):
        now=timezone.now()
        FonteEpidemiologica.objects.filter(pk=self.lot.fonte_id).update(ultima_coleta_em=now)
        with patch('django.utils.timezone.localdate',return_value=date(2026,10,17)):
            data=self.panel()
        self.assertGreater(data['atualidade']['defasagem_semanas'],100)
        self.assertEqual(data['atualidade']['ultima_semana_base'],str(week_start(2024,12)))
        self.assertNotEqual(data['coletado_em'],data['atualidade']['ultima_consulta_em'])

    def test_no_counts_has_no_freshness_and_regional_coverage_is_explicit(self):
        from .indicators import REGIONS
        region=REGIONS['3550308']['regiao_codigo']
        data=self.panel(tipo='regiao',codigo=region)
        self.assertEqual(data['qualidade']['municipios_com_dados'],1)
        self.assertLess(data['qualidade']['cobertura_percentual'],100)
        RegistroEpidemiologico.objects.update(casos=None)
        data=self.panel()
        self.assertIsNone(data['atualidade']['ultima_semana_base'])
        self.assertIsNone(data['atualidade']['defasagem_semanas'])
        self.assertEqual(data['qualidade']['semanas_avaliaveis'],0)

    def test_missing_record_is_a_gap_and_extreme_date_does_not_overflow(self):
        RegistroEpidemiologico.objects.filter(semana=4).delete()
        data=self.panel()
        self.assertEqual(data['qualidade']['semanas_esperadas'],12)
        self.assertEqual(data['qualidade']['semanas_sem_contagem_completa'],2)
        self.assertEqual(data['qualidade']['semanas_avaliaveis'],0)
        data=self.panel(inicio='9999-12-31',fim='9999-12-31')
        self.assertEqual(data['serie'],[])

    def test_combined_alert_filters_dates_inclusive_and_global_badge(self):
        self.fixture.make_lot('3510500',[10]*8+[100])
        self.fixture.make_lot('3550308',[10]*8+[100],indicator='infodengue_zika')
        params={**self.params,'inicio':str(week_start(2024,9)),'fim':str(week_start(2024,9))}
        data=self.client.get('/api/alertas/',params).json()
        self.assertEqual(data['count'],1)
        self.assertEqual(data['nao_lidas_total'],3)
        data=self.client.get('/api/alertas/',{**params,'fim':'2024-02-24','inicio':'2024-02-01'}).json()
        self.assertEqual(data['count'],0)
        self.assertEqual(data['nao_lidas_total'],3)
        self.assertEqual(self.client.get('/api/alertas/',{'agravo':'zika'}).json()['count'],1)

    def test_invalid_filters_and_authenticated_historical_catalog(self):
        for params in [{'inicio':'bad'},{'inicio':'2024-02-01','fim':'2024-01-01'},
                       {'agravo':'invalid'},{'agravo':'srag','indicador':'infodengue_dengue'}]:
            self.assertEqual(self.client.get('/api/alertas/',params).status_code,400)
        AlertaSurto.objects.update(ativa=False)
        data=self.client.get('/api/alertas/opcoes/').json()
        self.assertEqual(data['municipios'],[{'codigo':'3550308','nome':'São Paulo'}])
        self.assertEqual(data['agravos'],[{'codigo':'dengue','nome':'Dengue'}])
        self.client.logout()
        self.assertEqual(self.client.get('/api/alertas/opcoes/').status_code,401)
