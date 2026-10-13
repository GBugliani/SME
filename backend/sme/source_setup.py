from types import SimpleNamespace
from urllib.parse import urlencode
from .collection import MUNICIPIOS_SP, InfoDengueAdapter, CollectionError
from .processing import week_start


def prepare_source(data):
    if 'provedor' not in data:
        return data
    if data['provedor'] != 'infodengue':
        raise ValueError('Provedor inválido.')
    code = data.get('municipio')
    if not isinstance(code, str) or code not in MUNICIPIOS_SP:
        raise ValueError('Selecione um município válido de SP.')
    start, end = data.get('ano_inicio'), data.get('ano_fim')
    if type(start) is not int or type(end) is not int or not 2010 <= start <= end <= 2100:
        raise ValueError('Informe anos válidos e ordenados.')
    last_week = (week_start(end+1,1)-week_start(end,1)).days//7
    first, last = data.get('semana_inicio',1), data.get('semana_fim',last_week)
    if type(first) is not int or type(last) is not int:
        raise ValueError('As semanas devem ser números inteiros.')
    params={'geocode':code,'disease':'dengue','format':'json','ew_start':first,'ew_end':last,'ey_start':start,'ey_end':end}
    url='https://info.dengue.mat.br/api/alertcity?'+urlencode(params)
    try:
        InfoDengueAdapter().validate(SimpleNamespace(url=url,tipo='json',recorte=SimpleNamespace(tipo='municipio',codigo=code,nome=MUNICIPIOS_SP[code],uf='SP')))
        week_start(start,first);week_start(end,last)
    except CollectionError as exc:
        raise ValueError(str(exc)) from exc
    return {'nome':data.get('nome') or f'InfoDengue {start}' + (f'-{end}' if start!=end else ''),
            'tipo':'json','url':url,'ativa':data.get('ativa'), 'recorte_tipo':'municipio','recorte_codigo':code,'recorte_nome':MUNICIPIOS_SP[code],'recorte_uf':'SP'}
