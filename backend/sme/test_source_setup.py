from urllib.parse import parse_qs, urlsplit
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import FonteEpidemiologica


class AssistedSourceTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser('setup@example.org','Source-test-2026!')
        self.client.force_login(self.admin)
        self.data={'provedor':'infodengue','municipio':'3510500','ano_inicio':2024,'ano_fim':2024,'ativa':True}

    def save(self,**changes):
        return self.client.post('/api/fontes/',self.data|changes,content_type='application/json')

    def test_catalog_is_complete_and_admin_only(self):
        self.assertEqual(len(self.client.get('/api/fontes/catalogo/').json()['municipios']),645)
        viewer=get_user_model().objects.create_user('catalog@example.org','Source-test-2026!')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get('/api/fontes/catalogo/').status_code,403)
        self.assertEqual(self.save().status_code,403)
        self.client.logout()
        self.assertEqual(self.client.get('/api/fontes/catalogo/').status_code,401)

    def test_assisted_creation_builds_url_and_prevents_duplicate(self):
        self.assertEqual(self.save().status_code,201)
        source=FonteEpidemiologica.objects.get()
        self.assertEqual(source.recorte.nome,'Caraguatatuba')
        self.assertEqual(source.tipo,'json')
        self.assertEqual(source.nome,'InfoDengue 2024')
        q=parse_qs(urlsplit(source.url).query)
        self.assertEqual(q['geocode'],['3510500'])
        self.assertEqual(q['ew_end'],['52'])
        self.assertEqual(q['disease'],['dengue'])
        self.assertEqual(self.save().status_code,400)
        self.assertEqual(FonteEpidemiologica.objects.count(),1)

    def test_invalid_input_does_not_create_source(self):
        for changes in [{'municipio':'9999999'},{'ano_inicio':True},{'ano_fim':2023},{'ano_inicio':2020},{'ano_fim':2099},{'semana_fim':53},{'semana_inicio':-1},{'provedor':'unknown'}]:
            self.assertEqual(self.save(**changes).status_code,400,changes)
        self.assertEqual(FonteEpidemiologica.objects.count(),0)

    def test_edit_preserves_explicit_week_range(self):
        self.assertEqual(self.save(semana_inicio=10,semana_fim=30).status_code,201)
        source=FonteEpidemiologica.objects.get()
        response=self.client.put(f'/api/fontes/{source.pk}/',self.data|{'semana_inicio':10,'semana_fim':30,'ativa':False},content_type='application/json')
        self.assertEqual(response.status_code,200)
        source.refresh_from_db()
        self.assertFalse(source.ativa)
        self.assertEqual(parse_qs(urlsplit(source.url).query)['ew_start'],['10'])
