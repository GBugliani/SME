import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from .models import FonteEpidemiologica, RegistroAuditoria, TentativaLogin

User = get_user_model()


class SprintOneTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('admin@example.org', 'Strong-test-pass-2026')
        cls.user = User.objects.create_user('user@example.org', 'Strong-test-pass-2026')
        cls.inactive = User.objects.create_user('inactive@example.org', 'Strong-test-pass-2026', is_active=False)

    def post_json(self, url, data, client=None, **extra):
        return (client or self.client).post(url, data=json.dumps(data), content_type='application/json', **extra)

    def source_payload(self, **extra):
        return {'nome': 'Fonte de teste', 'tipo': 'csv', 'url': 'https://example.org/data.csv',
                'ativa': True, 'recorte_tipo': 'municipio', 'recorte_nome': 'São Paulo',
                'recorte_codigo': '3550308', 'recorte_uf': 'SP', **extra}

    def test_anonymous_cannot_read_sources_or_identity(self):
        for path in ['/api/fontes/', '/api/auth/me/']:
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_login_restore_and_logout(self):
        response = self.post_json('/api/auth/login/', {'email': ' ADMIN@EXAMPLE.ORG ', 'password': 'Strong-test-pass-2026'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['user']['administrador'])
        self.assertEqual(self.client.get('/api/auth/me/').json()['user']['email'], self.admin.email)
        self.assertTrue(response.cookies['sessionid']['httponly'])
        self.assertEqual(self.post_json('/api/auth/logout/', {}).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_invalid_and_inactive_users_receive_same_error(self):
        for email in ['unknown@example.org', self.inactive.email, self.admin.email]:
            response = self.post_json('/api/auth/login/', {'email': email, 'password': 'incorrect'})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()['error'], 'E-mail ou senha inválidos.')
        self.assertEqual(self.post_json('/api/auth/login/', {'email': self.inactive.email, 'password': 'Strong-test-pass-2026'}).status_code, 401)

    def test_login_throttles_and_recovers_after_window(self):
        for _ in range(5):
            self.assertEqual(self.post_json('/api/auth/login/', {'email': self.user.email, 'password': 'bad'}).status_code, 401)
        self.assertEqual(self.post_json('/api/auth/login/', {'email': self.user.email, 'password': 'Strong-test-pass-2026'}).status_code, 429)
        TentativaLogin.objects.update(inicio=timezone.now() - timedelta(minutes=16))
        self.assertEqual(self.post_json('/api/auth/login/', {'email': self.user.email, 'password': 'Strong-test-pass-2026'}).status_code, 200)

    def test_password_hash_and_case_insensitive_email_unique(self):
        self.assertNotEqual(self.admin.password, 'Strong-test-pass-2026')
        self.assertTrue(self.admin.check_password('Strong-test-pass-2026'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email='ADMIN@example.org')

    def test_regular_user_cannot_manage_sources(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/api/fontes/').status_code, 403)
        self.assertEqual(self.post_json('/api/fontes/', self.source_payload()).status_code, 403)
        self.assertEqual(self.client.put('/api/fontes/1/', '{}', content_type='application/json').status_code, 403)

    def test_create_list_update_disable_and_audit(self):
        self.client.force_login(self.admin)
        response = self.post_json('/api/fontes/', self.source_payload())
        self.assertEqual(response.status_code, 201, response.content)
        source = response.json()['source']
        self.assertIsNone(source['ultima_coleta_em'])
        self.assertEqual(self.client.get('/api/fontes/').json()['count'], 1)
        changed = self.source_payload(ativa=False, nome='Fonte atualizada')
        response = self.client.put(f"/api/fontes/{source['id']}/", json.dumps(changed), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FonteEpidemiologica.objects.get(pk=source['id']).ativa)
        self.assertEqual(RegistroAuditoria.objects.count(), 2)
        self.assertEqual(self.client.put('/api/fontes/9999/', json.dumps(changed), content_type='application/json').status_code, 404)

    def test_duplicate_source_and_conflicting_territory_rejected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.post_json('/api/fontes/', self.source_payload()).status_code, 201)
        self.assertEqual(self.post_json('/api/fontes/', self.source_payload()).status_code, 400)
        response = self.post_json('/api/fontes/', self.source_payload(recorte_nome='Outro município', url='https://example.org/another.csv'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('recorte_codigo', response.json()['fields'])
        self.assertEqual(FonteEpidemiologica.objects.count(), 1)
        self.assertEqual(RegistroAuditoria.objects.count(), 1)

    def test_regions_allowed_without_uf(self):
        self.client.force_login(self.admin)
        response = self.post_json('/api/fontes/', self.source_payload(recorte_tipo='regiao', recorte_codigo='REG-01', recorte_nome='Região de teste', recorte_uf=''))
        self.assertEqual(response.status_code, 201, response.content)

    def test_invalid_sources_rejected(self):
        self.client.force_login(self.admin)
        changes = [{'url': 'http://example.org/data.csv'}, {'url': 'https://127.0.0.1/data.csv'},
                   {'url': 'https://localhost/data'}, {'url': 'https://user:pass@example.org/file'},
                   {'url': 'https://example.org:8000/data'}, {'recorte_codigo': '123'},
                   {'url': 'https://example.org:99999/data'},
                   {'recorte_uf': 'ZZ'}, {'tipo': 'exe'}, {'ativa': 'false'}, {'nome': []}]
        for change in changes:
            with self.subTest(change=change):
                response = self.post_json('/api/fontes/', self.source_payload(**change))
                self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(FonteEpidemiologica.objects.count(), 0)

    def test_malformed_json_and_credential_types(self):
        for data in [[], {'email': ['bad'], 'password': {}}, {'email': 'a@b.c', 'password': 'x' * 1025}]:
            self.assertEqual(self.post_json('/api/auth/login/', data).status_code, 400)
        self.assertEqual(self.client.post('/api/auth/login/', '{', content_type='application/json').status_code, 400)

    def test_csrf_required_for_login_and_source_mutations(self):
        browser = Client(enforce_csrf_checks=True)
        credentials = {'email': self.admin.email, 'password': 'Strong-test-pass-2026'}
        self.assertEqual(self.post_json('/api/auth/login/', credentials, browser).status_code, 403)
        token = browser.get('/api/auth/csrf/').json()['csrfToken']
        response = self.post_json('/api/auth/login/', credentials, browser, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        new_token = response.json()['csrfToken']
        self.assertEqual(self.post_json('/api/fontes/', self.source_payload(), browser).status_code, 403)
        self.assertEqual(self.post_json('/api/fontes/', self.source_payload(), browser, HTTP_X_CSRFTOKEN=new_token).status_code, 201)

    def test_list_is_paginated(self):
        self.client.force_login(self.admin)
        self.post_json('/api/fontes/', self.source_payload())
        first = FonteEpidemiologica.objects.first()
        FonteEpidemiologica.objects.bulk_create([FonteEpidemiologica(nome=f'Fonte {i}', tipo='csv', url=f'https://example.org/{i}', recorte=first.recorte) for i in range(21)])
        data = self.client.get('/api/fontes/').json()
        self.assertEqual(len(data['sources']), 20)
        self.assertEqual(data['count'], 22)
        self.assertEqual(len(self.client.get('/api/fontes/?page=2').json()['sources']), 2)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_production_redirects_to_https(self):
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 301)

    @override_settings(CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:5173'])
    def test_dev_proxy_origin_allowed_but_foreign_origin_rejected(self):
        browser = Client(enforce_csrf_checks=True)
        token = browser.get('/api/auth/csrf/').json()['csrfToken']
        credentials = {'email': self.admin.email, 'password': 'Strong-test-pass-2026'}
        self.assertEqual(self.post_json('/api/auth/login/', credentials, browser, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='https://untrusted.example.org').status_code, 403)
        self.assertEqual(self.post_json('/api/auth/login/', credentials, browser, HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='http://127.0.0.1:5173').status_code, 200)
