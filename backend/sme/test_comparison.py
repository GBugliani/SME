from django.test import TestCase
from .models import Usuario
from .indicators import query_indicators,REGIONS
from .collection import MUNICIPIOS_SP
from .processing import process_lote,week_start
from .models import FonteEpidemiologica,RecorteGeografico,LoteColeta


class ComparisonRegressionTests(TestCase):
    def setUp(self):
        self.user=Usuario.objects.create_user('compare-reader@example.org','Comparison-tests-2026!')
        self.client.force_login(self.user)
        self.make_source('3550308',2024,[0,10,None,20])
        self.make_source('3501905',2026,[2,0,None,3])

    def make_source(self,code,year,counts):
        territory=RecorteGeografico.objects.create(tipo='municipio',codigo=code,nome=MUNICIPIOS_SP[code],uf='SP')
        source=FonteEpidemiologica.objects.create(nome='Comparação QA',tipo='json',indicador='infodengue_dengue',
            recorte=territory,url=f'https://info.dengue.mat.br/api/alertcity?geocode={code}&disease=dengue&format=json&ew_start=1&ew_end=52&ey_start={year}&ey_end={year}')
        rows=[{'SE':year*100+i,'data_iniSE':week_start(year,i).isoformat(),'casos':n,'municipio_nome':territory.nome,
            'id':int(code+str(year*100+i)+'00001')} for i,n in enumerate(counts,1)]
        lot=LoteColeta.objects.create(fonte=source,indicador=source.indicador,adaptador='infodengue',agravo='dengue',
            url_origem=source.url,territorio_codigo=code,sha256=code+'a'*57,dados_brutos=rows,quantidade_registros=len(rows))
        self.assertEqual(process_lote(lot.pk).status,'sucesso')

    def compare(self,**overrides):
        response=self.client.get('/api/indicadores/comparar/',{'tipo':'municipio','codigos':'3550308,3501905',
            'agravo':'dengue','indicador':'infodengue_dengue',**overrides})
        self.assertEqual(response.status_code,200,response.content)
        return response.json()['series']

    def test_default_context_does_not_invent_a_fixed_period(self):
        context=query_indicators({'codigo':'3550308','agravo':'dengue','indicador':'infodengue_dengue'})
        self.assertEqual(context['filtros'],{'inicio':None,'fim':None})
        data=self.compare()
        self.assertEqual([s['semanas_com_dados'] for s in data],[3,3])
        self.assertEqual(data[0]['serie'][0]['data'],'2023-12-31')
        self.assertEqual(data[1]['serie'][0]['data'],'2026-01-04')

    def test_explicit_period_excludes_other_year_and_reports_history(self):
        data=self.compare(inicio='2023-12-31',fim='2024-01-21')
        self.assertEqual(data[0]['filtros'],{'inicio':'2023-12-31','fim':'2024-01-21'})
        self.assertEqual([p['casos'] for p in data[0]['serie']],[0,10,None,20])
        self.assertEqual(data[1]['semanas_com_dados'],0)
        self.assertTrue(all(p['casos'] is None for p in data[1]['serie']))
        self.assertEqual(data[1]['qualidade']['inicio_historico'],'2026-01-04')

    def test_one_sided_dates_remain_one_sided(self):
        data=self.compare(inicio='2024-01-07')
        self.assertEqual(data[0]['filtros'],{'inicio':'2024-01-07','fim':None})
        self.assertEqual(data[1]['semanas_com_dados'],3)

    def test_empty_period_and_regions_are_not_filled_with_zero(self):
        data=self.compare(inicio='2025-01-01',fim='2025-12-31')
        self.assertEqual([s['semanas_com_dados'] for s in data],[0,0])
        self.assertTrue(all(p['casos'] is None for s in data for p in s['serie']))
        codes=','.join(REGIONS[c]['regiao_codigo'] for c in ['3550308','3501905'])
        regional=self.compare(tipo='regiao',codigos=codes)
        self.assertTrue(all(s['municipios_cobertos']==1 for s in regional))
        self.assertTrue(all(s['municipios_cobertos']<s['municipios_regiao'] for s in regional))
