import io
import json
from datetime import timedelta
from unittest.mock import patch

import openpyxl
from django.test import TestCase, override_settings
from django.utils import timezone

from .collection import CollectionError, collect_source, eligible_source_ids
from .datasets import SIVEP_URL
from .models import ArquivoColeta, FonteEpidemiologica, LoteColeta, RecorteGeografico, RecursoColeta, RegistroEpidemiologico, Usuario
from .processing import process_lote, week_start
from .sivep import HEADER, SivepAdapter


def workbook_bytes(rows=None, totals=None):
    rows = rows if rows is not None else [
        ['CARAGUATATUBA','01','SP','351050',3,0],
        ['CARAGUATATUBA','53','SP','351050',7,0],
        ['UBATUBA','53','SP','355540',2,0],
        ['RIO DE JANEIRO','01','RJ','330455',100,0],
    ]
    workbook = openpyxl.Workbook()
    sheet = workbook.active; sheet.title = 'Município e Semana'; sheet.append(HEADER)
    for row in rows: sheet.append(row)
    sheet = workbook.create_sheet('UF e Semana'); sheet.append(['Semana Epidemiológica',HEADER[2],'casos','obitos'])
    values = {}
    for row in rows:
        if row[2]=='SP': values[row[1]] = values.get(row[1],0)+row[4]
    for week, value in (totals if totals is not None else values).items(): sheet.append([week,'SP',value,0])
    stream=io.BytesIO();workbook.save(stream);workbook.close();return stream.getvalue()


class SivepTests(TestCase):
    def setUp(self):
        self.user=Usuario.objects.create_superuser('sivep@example.org','Password-test-2026!')
        self.client.force_login(self.user)
        self.city=RecorteGeografico.objects.create(tipo='municipio',codigo='3510500',nome='Caraguatatuba',uf='SP')
        self.source=FonteEpidemiologica.objects.create(nome='SRAG',tipo='xlsx',indicador='sivep_srag',url=SIVEP_URL+'?ano=2025',recorte=self.city)

    def fetch(self, body=None):
        body=workbook_bytes() if body is None else body
        catalog=json.dumps([{'name':'2025','type':'tree'}]).encode()
        def request(host,path,**kwargs):
            self.assertEqual(host,'gitlab.com')
            return (catalog if '/tree?' in path else body), {'ETag':'fixture'}
        return patch('sme.sivep.fetch_public',side_effect=request)

    def expire_cache(self):
        RecursoColeta.objects.update(verificado_em=timezone.now()-timedelta(hours=2))

    def test_real_calendar_boundary_and_missing_not_zero(self):
        body = workbook_bytes()
        with self.fetch(body): run=collect_source(self.source.pk)
        self.assertEqual(run.status,'sucesso',run.mensagem)
        rows=RegistroEpidemiologico.objects.order_by('semana')
        self.assertEqual(rows.count(),53)
        self.assertEqual(rows.last().casos,7)
        self.assertIsNone(rows.get(semana=2).casos)
        self.assertEqual(str(rows.last().data_referencia),'2025-12-28')
        self.assertEqual(str(week_start(2026,1)),'2026-01-04')
        self.assertIsNone(run.lote.conteudo_original)
        self.assertEqual(bytes(run.lote.arquivo_original.conteudo),body)
        self.assertIn('arquivo_url',run.lote.proveniencia)

    def test_original_shared_between_cities_and_repeat_does_not_download(self):
        city=RecorteGeografico.objects.create(tipo='municipio',codigo='3555406',nome='Ubatuba',uf='SP')
        second=FonteEpidemiologica.objects.create(nome='Ubatuba',tipo='xlsx',indicador='sivep_srag',url=self.source.url,recorte=city)
        with self.fetch() as request:
            first=collect_source(self.source.pk);other=collect_source(second.pk);repeat=collect_source(self.source.pk)
        self.assertEqual(request.call_count,2)
        self.assertEqual(first.lote.arquivo_original_id,other.lote.arquivo_original_id)
        self.assertEqual(first.lote_id,repeat.lote_id)
        self.assertTrue(repeat.repetida)
        self.assertEqual(ArquivoColeta.objects.count(),2)

    def test_revision_removes_old_count_preserving_original_and_old_reprocessing(self):
        with self.fetch(): first=collect_source(self.source.pk)
        self.expire_cache()
        revised=workbook_bytes([['UBATUBA','53','SP','355540',2,0]])
        with self.fetch(revised): latest=collect_source(self.source.pk)
        self.assertEqual(latest.status,'vazia',latest.mensagem)
        self.assertNotEqual(first.lote.arquivo_original_id,latest.lote.arquivo_original_id)
        self.assertIsNone(RegistroEpidemiologico.objects.get(semana=1).casos)
        process_lote(first.lote_id)
        self.assertIsNone(RegistroEpidemiologico.objects.get(semana=1).casos)

    def test_expired_cache_failure_not_reported_as_fresh_collection(self):
        with self.fetch(): collect_source(self.source.pk)
        self.expire_cache()
        with patch('sme.sivep.fetch_public',side_effect=CollectionError('Indisponível')): run=collect_source(self.source.pk)
        self.assertEqual(run.status,'erro')
        self.assertEqual(RegistroEpidemiologico.objects.get(semana=1).casos,3)
        self.assertEqual(LoteColeta.objects.count(),1)

    def test_reappearing_original_is_new_revision_and_reuses_file(self):
        body=workbook_bytes()
        with self.fetch(body): first=collect_source(self.source.pk)
        self.expire_cache()
        with self.fetch(workbook_bytes([['UBATUBA','01','SP','355540',2,0]])):
            collect_source(self.source.pk)
        self.assertIsNone(RegistroEpidemiologico.objects.get(semana=53).casos)
        self.expire_cache()
        with self.fetch(body): third=collect_source(self.source.pk)
        self.assertNotEqual(first.lote_id,third.lote_id)
        self.assertEqual(first.lote.arquivo_original_id,third.lote.arquivo_original_id)
        self.assertEqual(RegistroEpidemiologico.objects.get(semana=53).casos,7)
        with self.fetch(body) as request: repeat=collect_source(self.source.pk)
        request.assert_not_called()
        self.assertEqual(third.lote_id,repeat.lote_id)

    def test_parser_rejects_invalid_files_duplicate_weeks_and_mismatch(self):
        good=['CARAGUATATUBA','01','SP','351050',3,0]
        for body in [b'not excel',workbook_bytes([good,good]),workbook_bytes(totals={'01':999}),
                     workbook_bytes([good[:1]+['54']+good[2:]]),
                     workbook_bytes([good[:4]+[-1,0]])]:
            with self.subTest(size=len(body)),self.assertRaises(CollectionError):
                SivepAdapter().parse(body,self.source,2025)

    def test_api_setup_permissions_and_eligibility(self):
        response=self.client.post('/api/fontes/',{'provedor':'sivep','agravo':'srag','municipio':'3555406','ano_inicio':2025,'ativa':True},content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(response.json()['source']['tipo'],'xlsx')
        self.assertIn(self.source.pk,eligible_source_ids())
        for changes in [{'ano_inicio':2018},{'ano_inicio':True},{'agravo':'dengue'},{'municipio':'3304557'}]:
            response=self.client.post('/api/fontes/',{'provedor':'sivep','agravo':'srag','municipio':'3555406','ano_inicio':2025,'ativa':True,**changes},content_type='application/json')
            self.assertEqual(response.status_code,400)
        viewer=Usuario.objects.create_user('sivep-viewer@example.org','Password-test-2026!');self.client.force_login(viewer)
        self.assertEqual(self.client.post('/api/fontes/',{},content_type='application/json').status_code,403)

    def test_url_and_territory_restrictions(self):
        for url in ['https://127.0.0.1/file.xlsx',self.source.url+'&ano=2024',self.source.url+'#x',self.source.url.replace('https','http')]:
            self.source.url=url
            with self.assertRaises(CollectionError):SivepAdapter().validate(self.source)

    @override_settings(COLLECTION_TOKEN='sivep-test')
    def test_airflow_endpoint_and_indicator_filter(self):
        with self.fetch():
            response=self.client.post('/api/internal/coleta/',{'fonte_id':self.source.pk},content_type='application/json',HTTP_X_COLETA_TOKEN='sivep-test')
        self.assertEqual(response.status_code,200,response.content)
        result=self.client.get('/api/indicadores/',{'tipo':'municipio','codigo':'3510500','agravo':'srag','indicador':'sivep_srag'}).json()
        self.assertEqual(result['casos_total'],10)
        self.assertEqual(result['semanas_com_dados'],2)
        self.assertEqual(result['integracao']['provedor'],'sivep')

    def test_latest_week_folder_discovery(self):
        catalog=json.dumps([{'name':'2025_39','type':'tree'},{'name':'2025_40','type':'tree'},{'name':'2024','type':'tree'}]).encode()
        with patch('sme.sivep.fetch_public',side_effect=[(catalog,{}),(workbook_bytes(),{})]) as request:
            run=collect_source(self.source.pk)
        self.assertEqual(run.status,'sucesso',run.mensagem)
        self.assertIn('2025_40',request.call_args.args[1])

    def test_absent_municipality_is_not_counted_as_covered(self):
        with self.fetch(workbook_bytes([['UBATUBA','01','SP','355540',2,0]])):
            run=collect_source(self.source.pk)
        self.assertEqual(run.status,'vazia')
        result=self.client.get('/api/indicadores/',{'tipo':'municipio','codigo':'3510500','agravo':'srag','indicador':'sivep_srag'}).json()
        self.assertEqual(result['municipios_cobertos'],0)
        self.assertIsNone(result['serie'][0]['casos'])
