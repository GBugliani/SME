from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .collection import CollectionError
from .initial_collection import enqueue_uncollected_sources, run_next_initial_collection
from .models import ColetaInicial, ExecucaoColeta, FonteEpidemiologica


class InitialCollectionTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser('initial@example.org', 'Initial-test-2026!')
        self.client.force_login(admin)
        self.input = {'provedor': 'infodengue', 'agravo': 'dengue', 'municipio': '3550308',
            'ano_inicio': 2024, 'ano_fim': 2024, 'ativa': True}

    def register(self, **changes):
        response = self.client.post('/api/fontes/', self.input | changes, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        return response

    def test_registration_is_queued_without_blocking_on_external_collection(self):
        response = self.register()
        source = FonteEpidemiologica.objects.get(pk=response.json()['source']['id'])
        self.assertEqual(response.json()['source']['coleta_inicial_status'], 'pendente')
        self.assertEqual(ColetaInicial.objects.get(fonte=source).status, 'pendente')
        self.assertFalse(source.coletas.exists())
        self.assertEqual(self.client.get('/api/fontes/').json()['sources'][0]['coleta_inicial_status'], 'pendente')

    def test_disabled_source_waits_until_enabled(self):
        source = FonteEpidemiologica.objects.get(pk=self.register(ativa=False).json()['source']['id'])
        self.assertFalse(ColetaInicial.objects.filter(fonte=source).exists())
        response = self.client.put(f'/api/fontes/{source.pk}/', self.input,
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(ColetaInicial.objects.get(fonte=source).status, 'pendente')

    def test_worker_collects_once_and_preserves_origin(self):
        source = FonteEpidemiologica.objects.get(pk=self.register().json()['source']['id'])

        def fake_collection(source_id, *, origin):
            self.assertEqual((source_id, origin), (source.pk, 'inicial'))
            return ExecucaoColeta.objects.create(fonte=source, status='vazia', origem=origin,
                mensagem='A fonte não retornou contagens.')

        with patch('sme.initial_collection.collect_source', side_effect=fake_collection) as collect:
            job = run_next_initial_collection()
            self.assertEqual(job.status, 'concluida')
            self.assertEqual(job.tentativas, 1)
            self.assertIsNone(run_next_initial_collection())
            collect.assert_called_once()
        self.assertEqual(source.coletas.get().origem, 'inicial')
        self.assertEqual(self.client.get('/api/fontes/').json()['sources'][0]['ultima_execucao']['origem'], 'inicial')

    def test_worker_skips_when_manual_collection_or_archive_wins(self):
        source = FonteEpidemiologica.objects.get(pk=self.register().json()['source']['id'])
        ExecucaoColeta.objects.create(fonte=source, status='sucesso', origem='manual')
        with patch('sme.initial_collection.collect_source') as collect:
            self.assertEqual(run_next_initial_collection().status, 'ignorada')
            collect.assert_not_called()

    def test_existing_uncollected_source_is_seeded_once_on_worker_start(self):
        source = FonteEpidemiologica.objects.get(pk=self.register().json()['source']['id'])
        ColetaInicial.objects.filter(fonte=source).delete()
        enqueue_uncollected_sources()
        enqueue_uncollected_sources()
        self.assertEqual(ColetaInicial.objects.filter(fonte=source).count(), 1)

    def test_collection_error_is_visible_and_not_retried_forever(self):
        source = FonteEpidemiologica.objects.get(pk=self.register().json()['source']['id'])
        with patch('sme.initial_collection.collect_source', side_effect=CollectionError('Fonte indisponível.')):
            job = run_next_initial_collection()
        self.assertEqual(job.status, 'erro')
        self.assertEqual(job.mensagem, 'Fonte indisponível.')
        self.assertEqual(self.client.get('/api/fontes/').json()['sources'][0]['coleta_inicial_status'], 'erro')
        self.assertIsNone(run_next_initial_collection())
