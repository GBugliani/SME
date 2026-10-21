from types import SimpleNamespace
from urllib.parse import urlencode
from .collection import MUNICIPIOS_SP, InfoDengueAdapter, CollectionError
from .processing import week_start
from .datasets import DATASETS, ESUS_URL, INFOGRIPE_URL, SIVEP_URL


def prepare_source(data):
    if 'provedor' not in data:
        return data
    provider = data['provedor']
    disease = data.get('agravo', 'dengue' if provider == 'infodengue' else 'covid' if provider == 'esus' else 'srag')
    if not isinstance(disease, str) or not isinstance(provider, str) or f'{provider}_{disease}' not in DATASETS:
        raise ValueError('Provedor inválido.')
    code = data.get('municipio')
    if not isinstance(code, str) or code not in MUNICIPIOS_SP:
        raise ValueError('Selecione um município válido de SP.')
    rolling = data.get('periodo_movel', False)
    if type(rolling) is not bool:
        raise ValueError('Informe o período móvel usando true ou false.')
    from django.utils import timezone
    if rolling:
        if provider == 'infogripe':
            raise ValueError('InfoGripe já consulta todo o histórico disponível.')
        data = {**data, 'ano_inicio':timezone.localdate().year-(provider == 'infodengue'),
            'ano_fim':timezone.localdate().year, 'semana_inicio':1}
        data.pop('semana_fim', None)
    if provider in ('sivep', 'esus'):
        from django.utils import timezone
        year = data.get('ano_inicio')
        first_year = 2023 if provider == 'esus' else 2019
        if type(year) is not int or not first_year <= year <= timezone.localdate().year:
            raise ValueError(f'Selecione um ano entre {first_year} e o ano atual.')
        dataset = 'esus_covid' if provider == 'esus' else 'sivep_srag'
        url = ESUS_URL if provider == 'esus' else SIVEP_URL
        return {'nome':data.get('nome') or f'{"e-SUS COVID-19" if provider == "esus" else "SIVEP-Gripe"} {year}', 'indicador':dataset,
                'tipo':'xlsx','url':f'{url}?ano={year}','ativa':data.get('ativa'), 'periodo_movel':rolling,
                'recorte_tipo':'municipio','recorte_codigo':code,'recorte_nome':MUNICIPIOS_SP[code],'recorte_uf':'SP'}
    if provider == 'infogripe':
        if code != '3550308':
            raise ValueError('InfoGripe/SRAG está disponível apenas para São Paulo capital neste recorte.')
        return {'nome':data.get('nome') or 'InfoGripe — SRAG', 'indicador':'infogripe_srag',
                'tipo':'csv','url':INFOGRIPE_URL,'ativa':data.get('ativa'), 'recorte_tipo':'municipio',
                'recorte_codigo':code,'recorte_nome':MUNICIPIOS_SP[code],'recorte_uf':'SP'}
    start, end = data.get('ano_inicio'), data.get('ano_fim')
    if type(start) is not int or type(end) is not int or not 2010 <= start <= end <= 2100:
        raise ValueError('Informe anos válidos e ordenados.')
    last_week = (week_start(end+1,1)-week_start(end,1)).days//7
    first, last = data.get('semana_inicio',1), data.get('semana_fim',last_week)
    if type(first) is not int or type(last) is not int:
        raise ValueError('As semanas devem ser números inteiros.')
    params={'geocode':code,'disease':disease,'format':'json','ew_start':first,'ew_end':last,'ey_start':start,'ey_end':end}
    url='https://info.dengue.mat.br/api/alertcity?'+urlencode(params)
    try:
        InfoDengueAdapter(disease).validate(SimpleNamespace(url=url,tipo='json',recorte=SimpleNamespace(tipo='municipio',codigo=code,nome=MUNICIPIOS_SP[code],uf='SP')))
        week_start(start,first);week_start(end,last)
    except CollectionError as exc:
        raise ValueError(str(exc)) from exc
    return {'nome':data.get('nome') or f'InfoDengue {start}' + (f'-{end}' if start!=end else ''),
            'indicador':f'infodengue_{disease}', 'tipo':'json','url':url,'ativa':data.get('ativa'), 'periodo_movel':rolling, 'recorte_tipo':'municipio','recorte_codigo':code,'recorte_nome':MUNICIPIOS_SP[code],'recorte_uf':'SP'}
