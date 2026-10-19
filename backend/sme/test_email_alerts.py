"""Envio opcional: configuração, destinatários, fila e entrega sem SMTP externo."""
import smtplib
from datetime import datetime, time, timedelta, timezone as utc_timezone
from unittest.mock import patch

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .email_alerts import enqueue_alert_email, run_next_email
from .detection import run_next_job
from .detectors import PARAMETERS
from .models import (ConfiguracaoDeteccao, DestinoEmail, EnvioAlertaEmail, FonteEpidemiologica,
                     GrupoEmail, LoteColeta, RecorteGeografico, RegistroAuditoria, ReanaliseDeteccao, Usuario)
from .processing import process_lote, week_start


SMTP = {'EMAIL_HOST':'smtp.hostinger.com', 'EMAIL_PORT':465, 'EMAIL_HOST_USER':'system@example.org',
        'EMAIL_HOST_PASSWORD':'test-only-password', 'DEFAULT_FROM_EMAIL':'system@example.org',
        'EMAIL_USE_SSL':True, 'EMAIL_USE_TLS':False,
        'EMAIL_BACKEND':'django.core.mail.backends.locmem.EmailBackend'}


@override_settings(**SMTP)
class EmailAlertTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser('mail-admin@example.org', 'Mail-password-2026!')
        self.reader = Usuario.objects.create_user('mail-reader@example.org', 'Mail-password-2026!')
        self.client.force_login(self.admin)

    def put(self, path, data):
        return self.client.put(path, data, content_type='application/json')

    def post(self, path, data):
        return self.client.post(path, data, content_type='application/json')

    def configure(self):
        group = self.post('/api/administracao/email/grupos/',
                          {'nome':'Vigilância', 'enderecos':['A@example.org','b@example.org']})
        self.assertEqual(group.status_code, 201, group.content)
        group_id = group.json()['grupo']['id']
        targets = self.put('/api/administracao/email/destinatarios/',
                           {'individuais':['a@example.org','c@example.org'], 'grupos':[group_id]})
        self.assertEqual(targets.status_code, 200, targets.content)
        self.assertEqual(targets.json()['destinatarios_resolvidos'], 3)
        enabled = self.put('/api/administracao/email/', {'habilitado':True})
        self.assertEqual(enabled.status_code, 200, enabled.content)
        return group_id

    def recent_lot(self):
        code = '3550308'
        territory = RecorteGeografico.objects.create(tipo='municipio', codigo=code, nome='São Paulo', uf='SP')
        today = timezone.localdate()
        last = today - timedelta(days=(today.weekday()+1)%7+7)
        starts = [last-timedelta(weeks=9-i) for i in range(10)]
        def epi_code(day):
            for year in (day.year-1, day.year, day.year+1):
                first = week_start(year, 1)
                if first <= day < week_start(year+1, 1):
                    return year*100 + (day-first).days//7+1
            raise AssertionError('Semana de teste não encontrada')
        codes = [epi_code(day) for day in starts]
        first_year, last_year = min(codes)//100, max(codes)//100
        source = FonteEpidemiologica.objects.create(nome='InfoDengue',tipo='json', indicador='infodengue_dengue',recorte=territory,
            url=f'https://info.dengue.mat.br/api/alertcity?geocode={code}&disease=dengue&format=json&ew_start=1&ew_end=53&ey_start={first_year}&ey_end={last_year}')
        rows = [{'SE':codes[i],
                 'data_iniSE':int(datetime.combine(day,time(),tzinfo=utc_timezone.utc).timestamp()*1000),
                 'casos':value,'casos_est':value,'municipio_nome':territory.nome,'id':int(f'{code}{i:05d}')}
                for i,(day,value) in enumerate(zip(starts,[10]*9+[100]))]
        lot = LoteColeta.objects.create(fonte=source,indicador='infodengue_dengue',adaptador='infodengue',agravo='dengue',
            url_origem=source.url,territorio_codigo=code,sha256='a'*64,dados_brutos=rows,quantidade_registros=10)
        return lot

    def test_admin_manages_groups_and_selection_without_duplicate_delivery(self):
        group_id = self.configure()
        settings = self.client.get('/api/administracao/email/').json()
        self.assertTrue(settings['habilitado'])
        self.assertEqual(settings['individuais'], ['a@example.org','c@example.org'])
        self.assertEqual(settings['grupos_selecionados'], [group_id])
        self.assertEqual(GrupoEmail.objects.get(pk=group_id).enderecos, ['a@example.org','b@example.org'])
        self.assertEqual(DestinoEmail.objects.count(), 3)
        self.assertTrue(RegistroAuditoria.objects.filter(acao='destinatarios_email_editados').exists())
        self.assertEqual(self.client.delete(f'/api/administracao/email/grupos/{group_id}/').status_code,409)
        self.assertEqual(self.put('/api/administracao/email/destinatarios/',
            {'individuais':['c@example.org'],'grupos':[]}).status_code,200)
        self.assertEqual(self.client.delete(f'/api/administracao/email/grupos/{group_id}/').status_code,200)

    def test_reject_invalid_addresses_groups_and_enable_without_recipients(self):
        self.assertEqual(self.put('/api/administracao/email/',{'habilitado':True}).status_code,409)
        self.assertEqual(self.post('/api/administracao/email/grupos/',
            {'nome':'Teste','enderecos':['not-an-email']}).status_code,400)
        self.assertEqual(self.put('/api/administracao/email/destinatarios/',
            {'individuais':['a@example.org','A@example.org'],'grupos':[]}).status_code,400)
        self.assertEqual(self.put('/api/administracao/email/destinatarios/',
            {'individuais':[],'grupos':[999]}).status_code,400)
        self.assertEqual(DestinoEmail.objects.count(),0)
        with override_settings(EMAIL_HOST_PASSWORD=''):
            self.assertEqual(self.put('/api/administracao/email/destinatarios/',
                {'individuais':['a@example.org'],'grupos':[]}).status_code,200)
            self.assertEqual(self.put('/api/administracao/email/',{'habilitado':True}).status_code,409)

    def test_reader_cannot_view_or_edit_and_csrf_is_required(self):
        reader = Client();reader.force_login(self.reader)
        for path in ['/api/administracao/email/','/api/administracao/email/envios/']:
            self.assertEqual(reader.get(path).status_code,403)
        self.assertEqual(reader.put('/api/administracao/email/destinatarios/',{},content_type='application/json').status_code,403)
        self.assertEqual(reader.post('/api/administracao/email/teste/',{},content_type='application/json').status_code,403)
        csrf = Client(enforce_csrf_checks=True);csrf.force_login(self.admin)
        self.assertEqual(csrf.post('/api/administracao/email/grupos/',{},content_type='application/json').status_code,403)
        self.assertEqual(csrf.post('/api/administracao/email/teste/',{},content_type='application/json').status_code,403)

    def test_admin_can_test_own_mailbox_with_rate_limit_and_safe_errors(self):
        with override_settings(EMAIL_HOST_PASSWORD=''):
            self.assertEqual(self.post('/api/administracao/email/teste/',{}).status_code,409)
        self.assertEqual(self.post('/api/administracao/email/teste/',{'destinatario':'other@example.org'}).status_code,400)
        for _ in range(2):
            response = self.post('/api/administracao/email/teste/',{})
            self.assertEqual(response.status_code,200,response.content)
            self.assertEqual(response.json()['destinatario'],self.admin.email)
        with patch('sme.email_views.EmailMessage.send',side_effect=smtplib.SMTPAuthenticationError(535,b'secret')):
            response = self.post('/api/administracao/email/teste/',{})
            self.assertEqual(response.status_code,502)
            self.assertNotIn(b'secret',response.content)
        self.assertEqual(self.post('/api/administracao/email/teste/',{}).status_code,429)
        self.assertEqual(len(mail.outbox),2)

    def test_recent_collection_queues_one_per_address_and_worker_sends(self):
        self.configure()
        lot = self.recent_lot()
        self.assertEqual(process_lote(lot.pk).status,'sucesso')
        self.assertEqual(EnvioAlertaEmail.objects.count(),3)
        self.assertEqual(process_lote(lot.pk).status,'sucesso')
        self.assertEqual(EnvioAlertaEmail.objects.count(),3)
        for _ in range(3):
            self.assertEqual(run_next_email().status,'enviado')
        self.assertEqual(len(mail.outbox),3)
        self.assertEqual({m.to[0] for m in mail.outbox}, {'a@example.org','b@example.org','c@example.org'})
        self.assertTrue(all('não confirma um surto' in m.body for m in mail.outbox))
        self.assertTrue(all(len(m.to)==1 for m in mail.outbox))

    def test_historical_or_reanalysis_does_not_queue_and_disabled_pauses(self):
        self.configure()
        lot = self.recent_lot()
        self.assertEqual(process_lote(lot.pk).status,'sucesso')
        alert = EnvioAlertaEmail.objects.first().alerta
        EnvioAlertaEmail.objects.all().delete()
        alert.data_referencia = timezone.localdate()-timedelta(days=60)
        alert.save(update_fields=['data_referencia'])
        self.assertEqual(enqueue_alert_email(alert),0)
        alert.data_referencia = timezone.localdate()-timedelta(days=7)
        alert.save(update_fields=['data_referencia'])
        self.assertEqual(self.put('/api/administracao/email/',{'habilitado':False}).status_code,200)
        self.assertEqual(enqueue_alert_email(alert),0)
        EnvioAlertaEmail.objects.create(alerta=alert,revisao=alert.revisao,destinatario='a@example.org',assunto='test',corpo='test')
        self.assertIsNone(run_next_email())
        self.assertEqual(len(mail.outbox),0)

    def test_reanalysis_of_recent_series_does_not_email(self):
        self.configure()
        lot = self.recent_lot()
        self.assertEqual(process_lote(lot.pk).status,'sucesso')
        EnvioAlertaEmail.objects.all().delete()
        old = ConfiguracaoDeteccao.objects.get(ativa=True)
        old.ativa = False;old.save(update_fields=['ativa'])
        fresh = ConfiguracaoDeteccao.objects.create(metodo='media_movel',versao=old.versao+1,
            parametros=PARAMETERS,ativa=True)
        ReanaliseDeteccao.objects.all().delete()
        ReanaliseDeteccao.objects.create(configuracao=fresh)
        self.assertEqual(run_next_job().status,'sucesso')
        self.assertEqual(EnvioAlertaEmail.objects.count(),0)

    def test_removing_recipient_cancels_only_their_pending_messages(self):
        self.configure()
        lot = self.recent_lot()
        self.assertEqual(process_lote(lot.pk).status,'sucesso')
        response = self.put('/api/administracao/email/destinatarios/',
                            {'individuais':['c@example.org'],'grupos':[]})
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(EnvioAlertaEmail.objects.filter(status='cancelado').count(),2)
        self.assertEqual(EnvioAlertaEmail.objects.filter(status='pendente',destinatario='c@example.org').count(),1)

    def test_smtp_failure_retries_then_admin_can_retry_terminal_failure(self):
        self.configure()
        lot = self.recent_lot()
        self.assertEqual(process_lote(lot.pk).status,'sucesso')
        row = EnvioAlertaEmail.objects.first()
        with patch('sme.email_alerts.EmailMessage.send',side_effect=ConnectionError('private-detail')):
            self.assertEqual(run_next_email().status,'pendente')
        row.refresh_from_db()
        self.assertEqual(row.tentativas,1)
        self.assertNotIn('private-detail',row.erro)
        self.assertIsNotNone(row.proxima_tentativa_em)
        row.tentativas=4;row.proxima_tentativa_em=timezone.now()-timedelta(seconds=1)
        row.save(update_fields=['tentativas','proxima_tentativa_em'])
        with patch('sme.email_alerts.EmailMessage.send',side_effect=ConnectionError('private-detail')):
            self.assertEqual(run_next_email().status,'erro')
        self.assertEqual(self.post(f'/api/administracao/email/envios/{row.pk}/tentar/',{}).status_code,200)
        row.refresh_from_db();self.assertEqual((row.status,row.tentativas),('pendente',0))
        self.assertEqual(run_next_email().status,'enviado')
