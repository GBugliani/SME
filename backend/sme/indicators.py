import json
from datetime import date, timedelta
from pathlib import Path
from django.db.models import Q
from .models import RegistroEpidemiologico, Agravo
from .processing import MovingBaseline, PARAMETERS, week_start

REGIONS = json.loads(Path(__file__).with_name('regioes_sp.json').read_text(encoding='utf-8'))


def options():
    codes = set(RegistroEpidemiologico.objects.values_list('serie__recorte__codigo', flat=True))
    municipalities = [{'codigo':c, 'nome':REGIONS[c]['nome'], 'regiao_codigo':REGIONS[c]['regiao_codigo']} for c in codes if c in REGIONS]
    municipalities.sort(key=lambda r:r['nome'])
    region_codes = {REGIONS[c]['regiao_codigo'] for c in codes if c in REGIONS}
    regions = {v['regiao_codigo']:v['regiao_nome'] for v in REGIONS.values() if v['regiao_codigo'] in region_codes}
    return {'municipios':municipalities, 'regioes':[{'codigo':c,'nome':n} for c,n in sorted(regions.items(),key=lambda x:x[1])],
            'agravos':list(Agravo.objects.filter(serieepidemiologica__registros__isnull=False).distinct().values('codigo','nome'))}


def query_indicators(params):
    kind, code = params.get('tipo','municipio'), params.get('codigo','')
    disease = params.get('agravo','dengue')
    if kind not in ('municipio','regiao'):
        raise ValueError('Tipo de território inválido.')
    if kind=='municipio':
        if code not in REGIONS:
            raise ValueError('Selecione um município válido de SP.')
        all_codes = [code]
        name = REGIONS[code]['nome']
    else:
        all_codes = [c for c,v in REGIONS.items() if v['regiao_codigo']==code]
        if not all_codes:
            raise ValueError('Selecione uma região imediata válida de SP.')
        name = REGIONS[all_codes[0]]['regiao_nome']
    if not Agravo.objects.filter(codigo=disease).exists():
        raise ValueError('Agravo não disponível.')
    try:
        start = date.fromisoformat(params['inicio']) if params.get('inicio') else None
        end = date.fromisoformat(params['fim']) if params.get('fim') else None
    except ValueError:
        raise ValueError('Use datas válidas no formato AAAA-MM-DD.')
    if start and end and (start>end or (end-start).days>3660):
        raise ValueError('Selecione um intervalo ordenado de até dez anos.')
    records = RegistroEpidemiologico.objects.filter(serie__recorte__codigo__in=all_codes, serie__agravo__codigo=disease).select_related('serie__recorte','serie__fonte','lote').order_by('lote__criada_em','pk')
    # Revisões e fontes sobrepostas não duplicam o município/semana.
    current = {}
    for r in records:
        current[(r.serie.recorte.codigo,r.data_referencia)] = r
    covered = {c for c,d in current}
    weeks = {}
    for (c,day),r in current.items():
        weeks.setdefault(day,[]).append(r)
    history = []
    if weeks:
        day, last = min(weeks), max(weeks)
        while day<=last:
            rows = weeks.get(day,[])
            complete = len(rows)==len(covered) and all(r.casos is not None for r in rows)
            sample = rows[0] if rows else None
            history.append({'data':day, 'ano':sample.ano if sample else None, 'semana':sample.semana if sample else None,
                'casos':sum(r.casos for r in rows) if complete else None,
                'municipios_com_dados':sum(r.casos is not None for r in rows), 'anomalia':False, 'referencia':None, 'limiar':None})
            day+=timedelta(weeks=1)
    flags = {r['data']:r for r in MovingBaseline().analyze(history)}
    for p in history:
        if p['data'] in flags:
            p.update({k:v for k,v in flags[p['data']].items() if k not in ('data','observado')})
            p['anomalia']=True
    selected = [p for p in history if (not start or p['data']>=start) and (not end or p['data']<=end)]
    recent = selected[-4:]
    previous = selected[-8:-4]
    def average(rows):
        return sum(p['casos'] for p in rows)/4 if len(rows)==4 and all(p['casos'] is not None for p in rows) else None
    a,b = average(recent),average(previous)
    change = (a/b-1)*100 if a is not None and b not in (None,0) else None
    relevant = [r for r in current.values() if (not start or r.data_referencia>=start) and (not end or r.data_referencia<=end)]
    source_ids = {r.serie.fonte_id for r in relevant}
    sources = {r.serie.fonte_id:{'id':r.serie.fonte_id,'nome':r.serie.fonte.nome,'url':r.lote.url_origem} for r in relevant}
    return {'territorio':{'tipo':kind,'codigo':code,'nome':name}, 'agravo':disease,
        'serie':[{**p,'data':p['data'].isoformat()} for p in selected],
        'casos_total':sum(p['casos'] for p in selected if p['casos'] is not None),
        'semanas_com_dados':sum(p['casos'] is not None for p in selected), 'semanas_sem_dados':sum(p['casos'] is None for p in selected),
        'tendencia_percentual':change, 'anomalias':sum(p['anomalia'] for p in selected),
        'municipios_cobertos':len(covered), 'municipios_regiao':len(all_codes), 'codigos_cobertos':sorted(covered),
        'fontes':list(sources.values()), 'coletado_em':max((r.serie.fonte.ultima_coleta_em for r in relevant if r.serie.fonte.ultima_coleta_em),default=None), 'atualizado_em':max((r.serie.atualizada_em for r in relevant),default=None),
        'detector':{'metodo':MovingBaseline.name,'versao':1,'parametros':PARAMETERS}}
