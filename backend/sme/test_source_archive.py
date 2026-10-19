from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .collection import CollectionError, collect_source, eligible_source_ids
from .models import (Agravo, ExecucaoColeta, FonteEpidemiologica, LoteColeta,
    RegistroAuditoria, RegistroEpidemiologico, SerieEpidemiologica)


class SourceArchiveTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('archive-admin@example.org', 'Archive-test-2026!')
        self.viewer = get_user_model().objects.create_user('archive-viewer@example.org', 'Archive-test-2026!')
        self.client.force_login(self.admin)
        self.source_input = {'provedor':'infodengue', 'agravo':'dengue', 'municipio':'3550308',
            'ano_inicio':2024, 'ano_fim':2024, 'ativa':True}
        response = self.client.post('/api/fontes/', self.source_input, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.source = FonteEpidemiologica.objects.get(pk=response.json()['source']['id'])
        self.url = f'/api/fontes/{self.source.pk}/arquivamento/'

    def archive(self, value=True):
        return self.client.put(self.url, {'arquivar':value}, content_type='application/json')

    def test_archive_preserves_history_and_restore_requires_explicit_reactivation(self):
        lot = LoteColeta.objects.create(fonte=self.source, adaptador='infodengue', agravo='dengue',
            url_origem=self.source.url, territorio_codigo='3550308', sha256='a'*64,
            dados_brutos=[{'casos': 3}], quantidade_registros=1)
        run = ExecucaoColeta.objects.create(fonte=self.source, lote=lot, status='sucesso', quantidade_registros=1)
        disease = Agravo.objects.create(codigo='dengue', nome='Dengue')
        series = SerieEpidemiologica.objects.create(fonte=self.source, recorte=self.source.recorte,
            agravo=disease, indicador='infodengue_dengue')
        RegistroEpidemiologico.objects.create(serie=series, ano=2024, semana=1,
            data_referencia=date(2023, 12, 31), casos=3, lote=lot)
        indicator_url = '/api/indicadores/?tipo=municipio&codigo=3550308&agravo=dengue'
        self.assertEqual(self.client.get(indicator_url).json()['casos_total'], 3)
        self.assertIn(self.source.pk, eligible_source_ids())
        response = self.archive()
        self.assertEqual(response.status_code, 200, response.content)
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.arquivada_em)
        self.assertFalse(self.source.ativa)
        self.assertFalse(response.json()['source']['coleta_disponivel'])
        visible = self.client.get('/api/fontes/').json()
        self.assertEqual(visible['count'], 0)
        self.assertFalse(visible['arquivadas'])
        archived = self.client.get('/api/fontes/', {'arquivadas':'1'}).json()
        self.assertTrue(archived['arquivadas'])
        self.assertEqual([s['id'] for s in archived['sources']], [self.source.pk])
        self.assertEqual(archived['sources'][0]['arquivada_em'], response.json()['source']['arquivada_em'])
        self.assertEqual(self.client.get(f'/api/fontes/{self.source.pk}/coletas/').json()['execucoes'][0]['id'], run.pk)
        self.assertEqual(LoteColeta.objects.get(pk=lot.pk).fonte_id, self.source.pk)
        historical = self.client.get(indicator_url).json()
        self.assertEqual(historical['casos_total'], 3)
        self.assertEqual(historical['fontes'][0]['id'], self.source.pk)
        self.assertNotIn(self.source.pk, eligible_source_ids())
        self.assertEqual(self.client.post(f'/api/fontes/{self.source.pk}/coletas/', {}, content_type='application/json').status_code, 409)
        with self.assertRaisesMessage(CollectionError, 'arquivada'):
            collect_source(self.source.pk)
        self.assertEqual(self.client.put(f'/api/fontes/{self.source.pk}/', self.source_input,
            content_type='application/json').status_code, 409)

        self.assertEqual(self.archive(False).status_code, 200)
        self.source.refresh_from_db()
        self.assertIsNone(self.source.arquivada_em)
        self.assertFalse(self.source.ativa)
        self.assertEqual(self.client.get('/api/fontes/').json()['count'], 1)
        self.assertNotIn(self.source.pk, eligible_source_ids())
        self.assertEqual(self.client.put(f'/api/fontes/{self.source.pk}/', self.source_input,
            content_type='application/json').status_code, 200)
        self.assertIn(self.source.pk, eligible_source_ids())
        actions = list(RegistroAuditoria.objects.filter(entidade='FonteEpidemiologica', entidade_id=self.source.pk)
            .values_list('acao', flat=True))
        self.assertIn('fonte_arquivada', actions)
        self.assertIn('fonte_restaurada', actions)

    def test_archive_is_idempotent_and_filtered_before_search_and_pagination(self):
        self.assertEqual(self.archive().status_code, 200)
        self.assertEqual(self.archive().status_code, 200)
        self.assertEqual(RegistroAuditoria.objects.filter(acao='fonte_arquivada').count(), 1)
        self.assertEqual(self.client.get('/api/fontes/', {'q':'3550308'}).json()['count'], 0)
        self.assertEqual(self.client.get('/api/fontes/', {'q':'3550308', 'arquivadas':'1'}).json()['count'], 1)
        self.assertEqual(self.client.get('/api/fontes/', {'arquivadas':'invalid'}).status_code, 400)
        self.assertEqual(self.archive(False).status_code, 200)
        self.assertEqual(self.archive(False).status_code, 200)
        self.assertEqual(RegistroAuditoria.objects.filter(acao='fonte_restaurada').count(), 1)

    def test_only_source_managers_can_view_archive_and_change_state(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get('/api/fontes/', {'arquivadas':'1'}).status_code, 403)
        self.assertEqual(self.archive().status_code, 403)
        self.assertEqual(self.client.get('/api/fontes/').json()['count'], 1)
        self.client.logout()
        self.assertEqual(self.archive().status_code, 401)

    def test_archive_requires_valid_json_and_csrf(self):
        for body in [{}, {'arquivar':'true'}, {'arquivar':1}, {'arquivar':True, 'extra':1}]:
            self.assertEqual(self.client.put(self.url, body, content_type='application/json').status_code, 400)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        self.assertEqual(browser.put(self.url, {'arquivar':True}, content_type='application/json').status_code, 403)
        token = browser.get('/api/auth/csrf/').json()['csrfToken']
        self.assertEqual(browser.put(self.url, {'arquivar':True}, content_type='application/json',
            HTTP_X_CSRFTOKEN=token).status_code, 200)
