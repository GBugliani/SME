import csv
import hashlib
import io
from unittest.mock import patch
from django.test import TestCase, override_settings
from .models import (Usuario, FonteEpidemiologica, RecorteGeografico, LoteColeta,
                     RegistroEpidemiologico, SerieEpidemiologica)
from .collection import collect_source, eligible_source_ids, CollectionError
from .datasets import DATASETS, INFOGRIPE_URL
from .infogripe import InfoGripeAdapter, CASES, YEAR, WEEK, GROUP
from .processing import process_lote
from .test_collection import URL, ROWS


def respiratory_row(**changes):
    return {CASES:'3,100000e+01', 'casos estimados':'1,720000e+02', YEAR:'2026', WEEK:'40',
            GROUP:'0', 'CO_MUN_RES':'355030', 'CO_MUN_RES_nome':'SAO PAULO',
            'DS_UF_SIGLA':'SP', 'escala':'casos', **changes}


def csv_bytes(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=respiratory_row().keys(), delimiter=';')
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue().encode('utf8')


class MultiProviderTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_superuser('multi@example.org', 'Test-secret-2026!')
        self.client.force_login(self.user)
        self.territory = RecorteGeografico.objects.create(tipo='municipio', codigo='3550308', nome='São Paulo', uf='SP')
        self.dengue = FonteEpidemiologica.objects.create(nome='InfoDengue', tipo='json', url=URL, recorte=self.territory, indicador='infodengue_dengue')
        self.srag = FonteEpidemiologica.objects.create(nome='InfoGripe', tipo='csv', url=INFOGRIPE_URL, recorte=self.territory, indicador='infogripe_srag')

    def collect_srag(self, rows=None):
        body = csv_bytes(rows if rows is not None else [respiratory_row()])
        with patch('sme.infogripe.fetch_public', return_value=(body, {'ETag':'"fixture-v1"'})):
            return collect_source(self.srag.pk)

    def query(self, **params):
        return self.client.get('/api/indicadores/', {'tipo':'municipio', 'codigo':'3550308', 'agravo':'srag', **params})

    def test_csv_selection_observed_and_estimated_provenance_and_hash(self):
        rows=[respiratory_row(), respiratory_row(escala='incidência'), respiratory_row(CO_MUN_RES='330455'), respiratory_row(**{GROUP:'1'})]
        run=self.collect_srag(rows)
        self.assertEqual(run.status, 'sucesso')
        point=RegistroEpidemiologico.objects.get()
        self.assertEqual((point.casos,point.casos_estimados),(31,172))
        self.assertEqual(str(point.data_referencia),'2026-10-04')
        self.assertEqual(point.serie.agravo.nome,'SRAG')
        self.assertEqual(point.serie.indicador,'infogripe_srag')
        lote=run.lote
        self.assertEqual(lote.sha256_original, hashlib.sha256(csv_bytes(rows)).hexdigest())
        self.assertEqual(bytes(lote.conteudo_original),csv_bytes(rows))
        self.assertEqual(lote.proveniencia['base_original'],'SIVEP-Gripe')
        self.assertEqual(lote.proveniencia['http']['ETag'],'"fixture-v1"')
        response=self.query().json()
        self.assertEqual(response['casos_total'],31)
        self.assertEqual(response['fontes'][0]['lotes'][0]['id'],lote.pk)
        self.assertEqual(response['serie'][0]['origens'],[{'fonte_id':self.srag.pk,'lote_id':lote.pk}])

    def test_all_infodengue_diseases_are_independent(self):
        with patch('sme.collection.InfoDengueAdapter.fetch',return_value=ROWS):
            for disease in ['dengue','chikungunya','zika']:
                source=self.dengue if disease=='dengue' else FonteEpidemiologica.objects.create(
                    nome=disease,tipo='json',url=URL.replace('disease=dengue',f'disease={disease}'),recorte=self.territory,indicador=f'infodengue_{disease}')
                self.assertEqual(collect_source(source.pk).status,'sucesso')
                response=self.query(agravo=disease,indicador=f'infodengue_{disease}').json()
                self.assertEqual(response['casos_total'],12)
                self.assertEqual(response['integracao']['agravo'],disease)
        self.assertEqual(SerieEpidemiologica.objects.count(),3)

    def test_selector_does_not_merge_providers_for_same_disease(self):
        self.collect_srag()
        original=RegistroEpidemiologico.objects.get()
        alternate=SerieEpidemiologica.objects.create(fonte=self.dengue,recorte=self.territory,agravo=original.serie.agravo,indicador='test_srag')
        RegistroEpidemiologico.objects.create(serie=alternate,ano=2026,semana=40,data_referencia=original.data_referencia,casos=99,lote=original.lote)
        with patch.dict(DATASETS,{'test_srag':{**DATASETS['infogripe_srag'],'codigo':'test_srag','publicador':'Provedor de teste'}}):
            self.assertEqual(self.query().status_code,400)
            self.assertEqual(self.query(indicador='infogripe_srag').json()['casos_total'],31)
            self.assertEqual(self.query(indicador='test_srag').json()['casos_total'],99)
            self.assertEqual(self.query(indicador='infodengue_dengue').status_code,400)

    def test_duplicate_payload_reuses_batch_and_revision_keeps_old_file(self):
        first=self.collect_srag()
        self.assertEqual(self.collect_srag().lote_id,first.lote_id)
        newer=self.collect_srag([respiratory_row(**{CASES:'40'})])
        self.assertNotEqual(newer.lote_id,first.lote_id)
        self.assertEqual(process_lote(first.lote_id).status,'sucesso')
        self.assertEqual(RegistroEpidemiologico.objects.get().casos,40)
        self.assertEqual(LoteColeta.objects.get(pk=first.lote_id).dados_brutos[0][CASES],'3,100000e+01')

    def test_source_edit_cannot_change_historical_identity(self):
        self.collect_srag()
        response=self.client.put(f'/api/fontes/{self.srag.pk}/',{'provedor':'infodengue','agravo':'zika',
            'municipio':'3550308','ano_inicio':2024,'ano_fim':2024,'ativa':True},content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.srag.refresh_from_db();self.assertEqual(self.srag.indicador,'infogripe_srag')

    def test_source_rename_preserves_original_batch_name(self):
        self.collect_srag()
        response=self.client.put(f'/api/fontes/{self.srag.pk}/',{'provedor':'infogripe','agravo':'srag',
            'municipio':'3550308','nome':'Nome novo','ativa':False},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(LoteColeta.objects.get().proveniencia['nome_fonte'],'InfoGripe')

    def test_srag_setup_rejects_wrong_city_disease_and_no_permission(self):
        for changes in [{'municipio':'3510500'},{'agravo':'dengue'},{'provedor':'unknown'}]:
            response=self.client.post('/api/fontes/',{'provedor':'infogripe','agravo':'srag','municipio':'3550308','ativa':True,**changes},content_type='application/json')
            self.assertEqual(response.status_code,400)
        viewer=Usuario.objects.create_user('viewer-multi@example.org','Test-secret-2026!');self.client.force_login(viewer)
        self.assertEqual(self.client.post(f'/api/fontes/{self.srag.pk}/coletas/').status_code,403)
        self.assertEqual(self.client.get('/api/fontes/catalogo/').status_code,403)
        self.assertEqual(self.client.get('/api/fontes/').status_code,200)

    def test_scheduler_selects_both_providers_and_skips_unsupported(self):
        unsupported=FonteEpidemiologica.objects.create(nome='TBWEB',tipo='csv',url='https://example.org/data.csv',recorte=self.territory)
        self.assertEqual(eligible_source_ids(),[self.dengue.pk,self.srag.pk])
        self.assertEqual(collect_source(unsupported.pk).status,'erro')
        self.assertFalse(LoteColeta.objects.exists())

    @override_settings(COLLECTION_TOKEN='fixture-token')
    def test_scheduled_srag_and_failure_propagation(self):
        headers={'HTTP_X_COLETA_TOKEN':'fixture-token'}
        with patch('sme.infogripe.fetch_public', return_value=(csv_bytes([respiratory_row()]),{})):
            response=self.client.post('/api/internal/coleta/',{'fonte_id':self.srag.pk},content_type='application/json',**headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['execucoes'][0]['origem'],'airflow')
        with patch('sme.infogripe.fetch_public',side_effect=CollectionError('Indisponível')):
            response=self.client.post('/api/internal/coleta/',{'fonte_id':self.srag.pk},content_type='application/json',**headers)
        self.assertEqual(response.status_code,502)
        self.assertEqual(RegistroEpidemiologico.objects.get().casos,31)

    def test_parser_rejects_schema_duplicates_negative_fractional_and_nan(self):
        adapter=InfoGripeAdapter()
        for body in [b'<html>indisponivel</html>',csv_bytes([respiratory_row()]*2)]+[
                csv_bytes([respiratory_row(**{CASES:v})]) for v in ('-1','1,5','NaN','Infinity')]:
            with self.subTest(body=body[:60]),self.assertRaises(CollectionError): adapter.parse(body)

    def test_missing_estimate_and_cases_stay_missing(self):
        run=self.collect_srag([respiratory_row(**{CASES:'','casos estimados':''})])
        self.assertEqual(run.status,'sucesso')
        row=RegistroEpidemiologico.objects.get();self.assertIsNone(row.casos);self.assertIsNone(row.casos_estimados)
        self.assertEqual(self.query().json()['semanas_com_dados'],0)

    def test_infogripe_url_restrictions_and_private_dns(self):
        adapter=InfoGripeAdapter()
        for url in [INFOGRIPE_URL+'?q=x',INFOGRIPE_URL.replace('/main/','/evil/'),INFOGRIPE_URL.replace('https://','http://')]:
            self.srag.url=url
            with self.assertRaises(CollectionError):adapter.validate(self.srag)
        self.srag.url=INFOGRIPE_URL
        with patch('sme.collection.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('sme.collection.socket.create_connection') as connect:
            with self.assertRaises(CollectionError):adapter.fetch(self.srag)
            connect.assert_not_called()

    def test_catalog_and_setup_use_validated_combination(self):
        catalog=self.client.get('/api/fontes/catalogo/').json()
        self.assertEqual({x['codigo'] for x in catalog['integracoes']},set(DATASETS))
        response=self.client.post('/api/fontes/',{'provedor':'infodengue','agravo':'chikungunya','municipio':'3510500','ano_inicio':2024,'ano_fim':2024,'ativa':True},content_type='application/json')
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()['source']['indicador'],'infodengue_chikungunya')

    def test_failed_normalization_is_collection_failure_with_raw_preserved(self):
        with patch('sme.infogripe.InfoGripeAdapter.fetch',return_value=[respiratory_row()]),patch('sme.processing.detect_series',side_effect=CollectionError('Falha no detector')):
            run=collect_source(self.srag.pk)
        self.assertEqual(run.status,'erro')
        self.assertTrue(LoteColeta.objects.exists())
        self.assertFalse(RegistroEpidemiologico.objects.exists())


from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MultiProviderMigrationTests(TransactionTestCase):
    def test_legacy_data_keeps_counts_hash_and_relations(self):
        old_target = [('sme','0003_agravo_configuracaodeteccao_processamentolote_and_more')]
        executor=MigrationExecutor(connection)
        latest=executor.loader.graph.leaf_nodes()
        executor.migrate(old_target)
        try:
            apps=executor.loader.project_state(old_target).apps
            territory=apps.get_model('sme','RecorteGeografico').objects.create(tipo='municipio',codigo='3550308',nome='São Paulo',uf='SP')
            source=apps.get_model('sme','FonteEpidemiologica').objects.create(nome='Legado',tipo='json',url=URL,recorte=territory)
            disease=apps.get_model('sme','Agravo').objects.create(codigo='dengue',nome='Dengue')
            batch=apps.get_model('sme','LoteColeta').objects.create(fonte=source,adaptador='infodengue',agravo='dengue',url_origem=URL,territorio_codigo='3550308',sha256='a'*64,dados_brutos=ROWS,quantidade_registros=1)
            series=apps.get_model('sme','SerieEpidemiologica').objects.create(fonte=source,recorte=territory,agravo=disease)
            record=apps.get_model('sme','RegistroEpidemiologico').objects.create(serie=series,ano=2024,semana=1,data_referencia='2023-12-31',casos=12,lote=batch)
        finally:
            executor=MigrationExecutor(connection);executor.migrate(latest)
        migrated=LoteColeta.objects.get(pk=batch.pk)
        self.assertEqual(migrated.indicador,'infodengue_dengue')
        self.assertEqual(migrated.sha256,'a'*64)
        self.assertEqual(migrated.dados_brutos,ROWS)
        self.assertIsNone(migrated.conteudo_original)
        self.assertTrue(migrated.proveniencia['legado'])
        migrated_record=RegistroEpidemiologico.objects.get(pk=record.pk)
        self.assertEqual((migrated_record.lote_id,migrated_record.casos),(batch.pk,12))
        self.assertEqual(migrated_record.serie.indicador,'infodengue_dengue')
