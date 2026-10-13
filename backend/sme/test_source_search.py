from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import FonteEpidemiologica, RecorteGeografico


class SourceSearchTests(TestCase):
    def setUp(self):
        self.viewer = get_user_model().objects.create_user('search@example.org', 'Search-test-2026!')
        self.client.force_login(self.viewer)
        capital = RecorteGeografico.objects.create(tipo='municipio', nome='São Paulo', codigo='3550308', uf='SP')
        coast = RecorteGeografico.objects.create(tipo='municipio', nome='Caraguatatuba', codigo='3510500', uf='SP')
        FonteEpidemiologica.objects.bulk_create([
            FonteEpidemiologica(nome='InfoDengue 2024', tipo='json', url=f'https://example.org/capital/{i}', recorte=capital)
            for i in range(21)
        ])
        self.coast = FonteEpidemiologica.objects.create(nome='InfoDengue 2025', tipo='json', url='https://example.org/coast', recorte=coast)

    def test_search_before_pagination_and_preserves_query(self):
        for query in ['São Paulo', '3550308', 'InfoDengue 2024']:
            first = self.client.get('/api/fontes/', {'q': query}).json()
            self.assertEqual((first['count'], first['pages'], len(first['sources'])), (21, 2, 20))
            second = self.client.get('/api/fontes/', {'q': query, 'page': 2}).json()
            self.assertEqual(len(second['sources']), 1)
            self.assertNotEqual(second['sources'][0]['id'], self.coast.id)

    def test_normal_user_can_search_combined_terms_and_empty_results(self):
        result = self.client.get('/api/fontes/', {'q': '  Caraguatatuba   2025 '}).json()
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['sources'][0]['id'], self.coast.id)
        self.assertEqual(self.client.get('/api/fontes/', {'q': 'inexistente'}).json()['count'], 0)
        self.assertEqual(self.client.get('/api/fontes/', {'q': '  '}).json()['count'], 22)

    def test_search_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/fontes/', {'q': 'Caraguatatuba'}).status_code, 401)
