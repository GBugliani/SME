import json
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import Usuario, TentativaLogin, RegistroAuditoria
import hashlib


@override_settings(ALLOW_SELF_REGISTRATION=True)
class RegistrationTests(TestCase):
    def body(self, **changes):
        return dict(nome='Pessoa Teste',email=' NEW@EXAMPLE.ORG ',password='Strong-test-pass-2026',password_confirmation='Strong-test-pass-2026',**changes)

    def post(self, body=None, client=None, **headers):
        return (client or self.client).post('/api/auth/register/',json.dumps(body or self.body()),content_type='application/json',**headers)

    def test_account_session_hash_and_permissions(self):
        body=self.body();body.update(is_staff=True,is_superuser=True,administrador=True)
        response=self.post(body)
        self.assertEqual(response.status_code,201)
        user=Usuario.objects.get(email='new@example.org')
        self.assertTrue(user.check_password(body['password']))
        self.assertFalse(user.is_staff);self.assertFalse(user.is_superuser)
        self.assertEqual(user.first_name,'Pessoa Teste')
        self.assertEqual(self.client.get('/api/auth/me/').status_code,200)
        self.assertEqual(self.client.post('/api/fontes/', '{}',content_type='application/json').status_code,403)
        self.assertTrue(RegistroAuditoria.objects.filter(usuario=user,acao='usuario_cadastrado').exists())

    def test_validation_and_duplicate(self):
        for changes in [dict(password='short',password_confirmation='short'),dict(password_confirmation='different'),dict(email='invalid'),dict(nome=''),dict(nome=['bad'])]:
            body=self.body();body.update(changes)
            self.assertEqual(self.post(body).status_code,400)
        self.assertFalse(Usuario.objects.exists())
        Usuario.objects.create_user('new@example.org','Strong-test-pass-2026')
        self.assertEqual(self.post().status_code,400)
        self.assertEqual(Usuario.objects.count(),1)

    @override_settings(ALLOW_SELF_REGISTRATION=False)
    def test_disabled(self):
        self.assertEqual(self.post().status_code,403)
        self.assertFalse(self.client.get('/api/auth/csrf/').json()['registrationEnabled'])
        self.assertFalse(Usuario.objects.exists())

    def test_csrf_and_origin(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client=client).status_code,403)
        token=client.get('/api/auth/csrf/').json()['csrfToken']
        self.assertEqual(self.post(client=client,HTTP_X_CSRFTOKEN=token,HTTP_ORIGIN='https://untrusted.example.org').status_code,403)
        self.assertEqual(self.post(client=client,HTTP_X_CSRFTOKEN=token).status_code,201)

    def test_throttle(self):
        key=hashlib.sha256(b'register:127.0.0.1').hexdigest()
        TentativaLogin.objects.create(chave=key,inicio=timezone.now(),falhas=10)
        self.assertEqual(self.post().status_code,429)
        self.assertFalse(Usuario.objects.exists())
