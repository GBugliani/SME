from django.test import TestCase, override_settings
from .models import Usuario


class AdministrativeAccountPolicyTests(TestCase):
    @override_settings(ALLOW_SELF_REGISTRATION=True)
    def test_public_registration_cannot_be_reenabled_by_legacy_setting(self):
        response = self.client.post('/api/auth/register/', {
            'nome': 'Teste', 'email': 'new@example.org', 'password': 'Test-password-2026!'},
            content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Usuario.objects.exists())
        self.assertNotIn('registrationEnabled', self.client.get('/api/auth/csrf/').json())

    def test_self_service_password_endpoint_is_removed(self):
        user = Usuario.objects.create_user('user@example.org', 'Original-password-2026!')
        self.client.force_login(user)
        self.assertEqual(self.client.post('/api/auth/password/', {}, content_type='application/json').status_code, 404)
        user.refresh_from_db()
        self.assertTrue(user.check_password('Original-password-2026!'))
