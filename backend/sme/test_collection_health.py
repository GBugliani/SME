from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .collection_health import routine_data
from .models import ExecucaoColeta, FonteEpidemiologica, LoteColeta, ProcessamentoLote, RecorteGeografico, RotinaColeta


@override_settings(COLLECTION_TOKEN='health-test-token')
class CollectionHealthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('health@example.org', 'Health-test-2026!')
        self.client.force_login(self.user)
        territory = RecorteGeografico.objects.create(tipo='municipio', nome='São Paulo', codigo='3550308', uf='SP')
        self.source = FonteEpidemiologica.objects.create(recorte=territory, nome='Dengue', tipo='json',
            url='https://example.org/dados', indicador='infodengue_dengue')

    def get_health(self, **params):
        with patch('sme.collection_health.eligible_source_ids', return_value=[self.source.pk]):
            return self.client.get('/api/fontes/saude/', params)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.get_health().status_code, 401)

    def test_failed_attempt_does_not_replace_last_success_and_can_be_stale(self):
        previous = timezone.now() - timedelta(hours=27)
        ExecucaoColeta.objects.create(fonte=self.source, status='sucesso', finalizada_em=previous)
        ExecucaoColeta.objects.create(fonte=self.source, status='erro', finalizada_em=timezone.now(), mensagem='Fonte indisponível')
        data = self.get_health(situacao='atrasadas').json()
        self.assertEqual(data['resumo']['falhas'], 1)
        self.assertEqual(data['resumo']['atrasadas'], 1)
        self.assertEqual(data['fontes'][0]['ultima_sucesso'], previous.isoformat(timespec='milliseconds').replace('+00:00', 'Z'))
        self.assertFalse(data['agendamento']['monitoramento_disponivel'])
        self.assertFalse(data['agendamento']['sem_confirmacao'])

    def test_legacy_scheduler_does_not_imply_missing_confirmation(self):
        ExecucaoColeta.objects.create(fonte=self.source, origem='airflow', status='sucesso', finalizada_em=timezone.now())
        data = self.get_health().json()
        self.assertEqual(data['resumo']['ok'], 1)
        self.assertFalse(data['agendamento']['monitoramento_disponivel'])
        self.assertFalse(data['agendamento']['sem_confirmacao'])
        self.assertIsNone(data['agendamento']['ultima'])

    def test_missing_confirmation_is_reported_after_a_registered_schedule(self):
        routine = RotinaColeta.objects.create(run_id='scheduled__previous', tipo='scheduled', fontes_previstas=[self.source.pk])
        RotinaColeta.objects.filter(pk=routine.pk).update(iniciada_em=timezone.now()-timedelta(days=2))
        data = self.get_health().json()
        self.assertTrue(data['agendamento']['monitoramento_disponivel'])
        self.assertTrue(data['agendamento']['sem_confirmacao'])

    def test_empty_is_separate_from_failure_and_new_source_is_not_stale(self):
        ExecucaoColeta.objects.create(fonte=self.source, status='vazia', finalizada_em=timezone.now())
        data = self.get_health(situacao='vazias').json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['resumo']['falhas'], 0)
        self.assertFalse(data['fontes'][0]['atrasada'])
        self.assertEqual(self.get_health(situacao='invalid').status_code, 400)

    def test_routine_finish_reports_missing_sources_and_is_idempotent(self):
        routine = RotinaColeta.objects.create(run_id='scheduled__health', tipo='scheduled', fontes_previstas=[self.source.pk, 99999])
        ExecucaoColeta.objects.create(fonte=self.source, rotina=routine, status='sucesso', finalizada_em=timezone.now())
        kwargs = {'content_type': 'application/json', 'HTTP_X_COLETA_TOKEN': 'health-test-token'}
        response = self.client.post('/api/internal/coleta/', {'action': 'finish', 'run_id': routine.run_id}, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rotina']['status'], 'com_falhas')
        self.assertEqual(response.json()['rotina']['contagens']['sem_confirmacao'], 1)
        end = response.json()['rotina']['finalizada_em']
        self.assertEqual(self.client.post('/api/internal/coleta/', {'action': 'finish', 'run_id': routine.run_id}, **kwargs).json()['rotina']['finalizada_em'], end)
        self.assertEqual(self.client.post('/api/internal/coleta/', {'action': 'finish', 'run_id': routine.run_id}, content_type='application/json').status_code, 403)

    def test_registration_keeps_same_source_snapshot_on_retry(self):
        with patch('sme.views.eligible_source_ids', return_value=[self.source.pk]):
            for _ in range(2):
                self.assertEqual(self.client.post('/api/internal/coleta/', {'action': 'list', 'run_id': 'manual__health'},
                    content_type='application/json', HTTP_X_COLETA_TOKEN='health-test-token').status_code, 200)
        self.assertEqual(RotinaColeta.objects.count(), 1)
        routine = RotinaColeta.objects.get()
        self.assertEqual(routine.tipo, 'manual')
        self.assertEqual(routine_data(routine)['contagens']['sem_confirmacao'], 1)

    def test_processing_failure_is_identified_separately(self):
        lot = LoteColeta.objects.create(fonte=self.source, adaptador='infodengue', agravo='dengue',
            url_origem=self.source.url, territorio_codigo='3550308', sha256='a'*64,
            dados_brutos=[], quantidade_registros=0)
        ProcessamentoLote.objects.create(lote=lot, status='erro', mensagem='Falha na conversão')
        ExecucaoColeta.objects.create(fonte=self.source, lote=lot, status='erro', finalizada_em=timezone.now())
        row = self.get_health(situacao='falhas').json()['fontes'][0]
        self.assertTrue(row['processamento_falhou'])

    def test_interrupted_source_is_not_shown_as_running_forever(self):
        run = ExecucaoColeta.objects.create(fonte=self.source, status='executando')
        ExecucaoColeta.objects.filter(pk=run.pk).update(iniciada_em=timezone.now()-timedelta(minutes=11))
        self.assertEqual(self.get_health(situacao='executando').json()['count'], 0)
        self.assertEqual(self.get_health(situacao='falhas').json()['count'], 1)
