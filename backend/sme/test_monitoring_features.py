import copy
import json
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
from django.test import TestCase
from django.http import JsonResponse
from .models import Usuario, MunicipioFavorito, AlertaSurto, LoteColeta, PerfilAcesso
from .processing import process_lote
from .detection import analyze_territory
from .alert_history import close_alerts


class MonitoringFeaturesTests(TestCase):
    def setUp(self):
        from .test_sprint3 import ExportTests
        self.admin = Usuario.objects.create_superuser('features-admin@example.org','Features-2026-password!')
        self.user = Usuario.objects.create_user('features-user@example.org','Features-2026-password!')
        self.client.force_login(self.user)
        self.lot = ExportTests().make_lot('3550308',[10]*8+[100,10])

    def test_favorites_are_private_idempotent_and_validate_municipality(self):
        for _ in range(2):
            self.assertEqual(self.client.post('/api/favoritos/',{'codigo':'3550308'},content_type='application/json').status_code,200)
        self.assertEqual(MunicipioFavorito.objects.count(),1)
        self.assertEqual(self.client.post('/api/favoritos/',{'codigo':'invalid'},content_type='application/json').status_code,400)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/api/favoritos/').json()['favoritos'],[])
        self.client.delete('/api/favoritos/3550308/')
        self.assertEqual(MunicipioFavorito.objects.count(),1)
        self.client.force_login(self.user)
        self.client.delete('/api/favoritos/3550308/')
        self.assertEqual(MunicipioFavorito.objects.count(),0)

    def test_history_preserves_values_revision_closure_and_idempotence(self):
        alert=AlertaSurto.objects.get()
        self.assertEqual(alert.eventos.get().tipo,'criada')
        rows=copy.deepcopy(self.lot.dados_brutos)
        rows[8]['casos']=200
        lot=LoteColeta.objects.create(fonte=self.lot.fonte,indicador='infodengue_dengue',adaptador='infodengue',agravo='dengue',url_origem=self.lot.url_origem,territorio_codigo='3550308',sha256='history-revision',dados_brutos=rows,quantidade_registros=len(rows))
        self.assertEqual(process_lote(lot.pk).status,'sucesso')
        alert.refresh_from_db()
        self.assertEqual(alert.eventos.count(),2)
        analyze_territory(alert.recorte_id,alert.indicador)
        self.assertEqual(alert.eventos.count(),2)
        from django.db import transaction
        with transaction.atomic():close_alerts(AlertaSurto.objects.filter(pk=alert.pk),'Teste de encerramento')
        events=self.client.get(f'/api/alertas/{alert.pk}/historico/').json()['eventos']
        self.assertEqual(events[0]['tipo'],'encerrada')
        self.assertFalse(events[0]['estado']['ativa'])
        self.assertEqual(events[-1]['estado']['observado'],100)
        self.assertEqual(events[1]['estado']['observado'],200)

    def test_operational_notices_are_admin_only_and_do_not_send_email(self):
        self.assertEqual(self.client.get('/api/administracao/coletas/avisos/').status_code,403)
        self.client.force_login(self.admin)
        data={'agendamento':{'monitoramento_disponivel':True,'sem_confirmacao':True,'ultima':None},'resumo':{'falhas':3}}
        with patch('sme.monitoring_features.health',return_value=JsonResponse(data)),patch('sme.monitoring_features.timezone.localtime',return_value=datetime(2026,11,7,10,tzinfo=ZoneInfo('America/Sao_Paulo'))):
            response=self.client.get('/api/administracao/coletas/avisos/')
        self.assertEqual(len(response.json()['avisos']),2)

    def test_legacy_schedule_keeps_failure_notices_without_schedule_warning(self):
        self.client.force_login(self.admin)
        data={'agendamento':{'monitoramento_disponivel':False,'sem_confirmacao':True,'ultima':None},'resumo':{'falhas':3}}
        with patch('sme.monitoring_features.health',return_value=JsonResponse(data)),patch('sme.monitoring_features.timezone.localtime',return_value=datetime(2026,11,18,10,tzinfo=ZoneInfo('America/Sao_Paulo'))):
            notices=self.client.get('/api/administracao/coletas/avisos/').json()['avisos']
        self.assertEqual(len(notices),1)
        self.assertEqual(notices[0]['titulo'],'Falhas acumuladas nas fontes')

    def test_pdf_export_uses_permission_and_is_a_valid_document(self):
        params={'tipo':'municipio','codigo':'3550308','agravo':'dengue','indicador':'infodengue_dengue','formato':'pdf'}
        response=self.client.get('/api/indicadores/exportar/',params)
        self.assertEqual(response.status_code,200,response.content[:200])
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertTrue(response.content.rstrip().endswith(b'%%EOF'))
        self.user.perfil=PerfilAcesso.objects.create(nome='Somente consulta',permissoes=[]);self.user.save()
        self.assertEqual(self.client.get('/api/indicadores/exportar/',params).status_code,403)

    def test_endpoints_require_session(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/favoritos/').status_code,401)
        self.assertEqual(self.client.get(f'/api/alertas/{AlertaSurto.objects.get().pk}/historico/').status_code,401)
