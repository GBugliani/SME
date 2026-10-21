import io
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import openpyxl
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .collection import CollectionError, MUNICIPIOS_SP, collect_source
from .datasets import ESUS_URL, source_dataset
from .esus import EsusCovidAdapter
from .models import ArquivoColeta, FonteEpidemiologica, RecorteGeografico, RegistroEpidemiologico
from .source_setup import prepare_source


def covid_workbook(state_cases=7):
    workbook = openpyxl.Workbook()
    cities = workbook.active
    cities.title = 'Município e Semana'
    cities.append(('estadoIBGE', 'municipio', 'semEpi', 'casos'))
    cities.append(('SP', 'SAO PAULO', 1, 5))
    cities.append(('SP', 'OSASCO', 1, 2))
    cities.append(('SP', 'OSASCO', 3, 1))
    states = workbook.create_sheet('UF e Semana')
    states.append(('estadoIBGE', 'semEpi', 'casos'))
    states.append(('SP', 1, state_cases))
    states.append(('SP', 3, 1))
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


class EsusCovidParserTests(SimpleTestCase):
    def source(self):
        code = '3550308'
        return SimpleNamespace(url=f'{ESUS_URL}?ano=2026', tipo='xlsx',
                               recorte=SimpleNamespace(tipo='municipio', codigo=code,
                                                       nome=MUNICIPIOS_SP[code], uf='SP'))

    def test_validates_state_totals_and_keeps_missing_weeks_null(self):
        adapter = EsusCovidAdapter()
        rows = adapter.parse(covid_workbook(), self.source(), 2026)
        self.assertEqual(rows, [
            {'ano': 2026, 'semana': 1, 'codigo': '3550308', 'casos': 5},
            {'ano': 2026, 'semana': 2, 'codigo': '3550308', 'casos': None},
            {'ano': 2026, 'semana': 3, 'codigo': '3550308', 'casos': None},
        ])
        with self.assertRaisesRegex(CollectionError, 'divergem'):
            adapter.parse(covid_workbook(state_cases=6), self.source(), 2026)
        self.assertEqual([row['casos'] for row in adapter.normalize(rows, self.source())], [5, None, None])

    def test_assisted_source_uses_its_own_indicator(self):
        prepared = prepare_source({'provedor': 'esus', 'agravo': 'covid', 'municipio': '3550308',
                                   'ano_inicio': 2026, 'periodo_movel': True, 'ativa': True})
        self.assertEqual(prepared['indicador'], 'esus_covid')
        self.assertEqual(source_dataset(SimpleNamespace(**prepared)), 'esus_covid')
        self.assertEqual(EsusCovidAdapter().validate(SimpleNamespace(
            url=prepared['url'], tipo=prepared['tipo'], recorte=self.source().recorte)), 2026)


class EsusCovidCollectionTests(TestCase):
    def test_collects_weekly_cases_and_reuses_unchanged_publication(self):
        year = timezone.localdate().year
        recorte = RecorteGeografico.objects.create(tipo='municipio', codigo='3550308', nome='São Paulo', uf='SP')
        source = FonteEpidemiologica.objects.create(
            nome='COVID-19 São Paulo', tipo='xlsx', url=f'{ESUS_URL}?ano={year}',
            indicador='esus_covid', recorte=recorte, ativa=True, periodo_movel=True)
        body = covid_workbook()
        catalog = json.dumps([{'name': f'{year}_40', 'type': 'tree'}]).encode()
        catalog_file = ArquivoColeta.objects.create(sha256=hashlib.sha256(catalog).hexdigest(), conteudo=catalog)
        workbook_file = ArquivoColeta.objects.create(sha256=hashlib.sha256(body).hexdigest(), conteudo=body)

        def official_resource(path, limit):
            return (catalog_file if 'tree?' in path else workbook_file), {}, timezone.now()

        with patch('sme.esus.shared_resource', side_effect=official_resource):
            first = collect_source(source.pk)
            again = collect_source(source.pk)

        self.assertEqual(first.status, 'sucesso')
        self.assertEqual(again.status, 'sucesso')
        self.assertTrue(again.repetida)
        self.assertEqual(again.lote_id, first.lote_id)
        self.assertEqual(list(RegistroEpidemiologico.objects.values_list('semana', 'casos').order_by('semana')),
                         [(1, 5), (2, None), (3, None)])
        self.assertEqual(first.lote.indicador, 'esus_covid')
        self.assertEqual(first.lote.arquivo_original_id, workbook_file.pk)
