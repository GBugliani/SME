import json
from datetime import date, timedelta
from pathlib import Path
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from .models import RegistroEpidemiologico, Agravo, AlertaSurto
from .datasets import DATASETS
from .detectors import strategy
from .detection import configuration_for, configuration_data
from .series_data import current_records

REGIONS = json.loads(Path(__file__).with_name('regioes_sp.json').read_text(encoding='utf-8'))


def map_signal_level(observed, threshold):
    """Intensidade do excesso sobre o limiar, não risco clínico ou incidência."""
    if threshold <= 0 or observed <= threshold:
        return 0
    ratio = observed / threshold
    return 3 if ratio >= 2.5 else 2 if ratio >= 1.5 else 1


def options():
    # A revisão vigente por semana deve ser a mesma exibida no painel.
    current = (RegistroEpidemiologico.objects.filter(serie__indicador__in=DATASETS)
               .annotate(revision=Window(
                   expression=RowNumber(),
                   partition_by=[F('serie__recorte__codigo'), F('serie__indicador'), F('data_referencia')],
                   order_by=[F('lote__criada_em').desc(), F('lote_id').desc(), F('pk').desc()],
               ))
               .filter(revision=1)
               .order_by('serie__recorte__codigo', 'serie__indicador', '-data_referencia')
               .values_list('serie__recorte__codigo', 'serie__indicador', 'data_referencia', 'casos'))
    coverage = {}
    latest = {}
    for code, indicator, day, cases in current.iterator(chunk_size=2000):
        if cases is None:
            continue
        coverage.setdefault(indicator, set()).add(code)
        latest.setdefault((code, indicator), (day, cases))
    codes = set().union(*coverage.values()) if coverage else set()
    municipalities = [{'codigo':c, 'nome':REGIONS[c]['nome'], 'regiao_codigo':REGIONS[c]['regiao_codigo']} for c in codes if c in REGIONS]
    municipalities.sort(key=lambda r:r['nome'])
    region_codes = {REGIONS[c]['regiao_codigo'] for c in codes if c in REGIONS}
    regions = {v['regiao_codigo']:v['regiao_nome'] for v in REGIONS.values() if v['regiao_codigo'] in region_codes}
    signals = []
    if latest:
        # A última semana isolada pode ter recuado após uma alta recente. Mantemos
        # a sinalização visível apenas nas quatro semanas disponíveis seguintes.
        newest_relevant = max(day for day, _ in latest.values())
        oldest_relevant = newest_relevant - timedelta(days=21)
        for code, indicator, day, observed, threshold in AlertaSurto.objects.filter(
                ativa=True, data_referencia__range=(oldest_relevant, newest_relevant)).order_by().values_list(
                'recorte__codigo', 'indicador', 'data_referencia', 'observado', 'limiar'):
            last_week = latest.get((code, indicator))
            if last_week is None or not last_week[0] - timedelta(days=21) <= day <= last_week[0]:
                continue
            level = map_signal_level(observed, threshold)
            if level:
                signals.append({'codigo':code, 'indicador':indicator, 'data_referencia':day.isoformat(),
                                'observado':observed, 'limiar':round(threshold, 1), 'nivel':level})
    return {'integracoes':[{**DATASETS[k], 'codigos_com_dados':sorted(coverage[k])} for k in DATASETS if k in coverage], 'municipios':municipalities, 'regioes':[{'codigo':c,'nome':n} for c,n in sorted(regions.items(),key=lambda x:x[1])],
            'agravos':list(Agravo.objects.filter(serieepidemiologica__registros__isnull=False).distinct().values('codigo','nome')),
            'sinalizacoes_mapa':signals,
            'ultimas_semanas_mapa':[{'codigo':code, 'indicador':indicator, 'data_referencia':day.isoformat(), 'casos':cases}
                                    for (code, indicator), (day, cases) in latest.items()]}


def query_indicators(params, configuration=None):
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
    indicator = params.get('indicador', '')
    candidates = list(records.order_by().values_list('serie__indicador', flat=True).distinct())
    if indicator:
        if indicator not in DATASETS or DATASETS[indicator]['agravo'] != disease:
            raise ValueError('O indicador e o agravo devem corresponder à mesma integração.')
    else:
        if len(candidates) > 1:
            raise ValueError('Há mais de um provedor/indicador. Selecione a origem nos filtros.')
        indicator = candidates[0] if candidates else next((k for k,v in DATASETS.items() if v['agravo']==disease), '')
    current = current_records(all_codes, indicator, disease)
    configuration = configuration or configuration_for(indicator)
    covered = {c for (c,d),r in current.items() if r.casos is not None}
    weeks = {}
    for (c,day),r in current.items():
        weeks.setdefault(day,[]).append(r)
    history = []
    if weeks:
        day, last = min(weeks), max(weeks)
        while day<=last:
            rows = [r for r in weeks.get(day,[]) if r.serie.recorte.codigo in covered]
            complete = bool(covered) and len(rows)==len(covered) and all(r.casos is not None for r in rows)
            sample = rows[0] if rows else None
            history.append({'data':day, 'ano':sample.ano if sample else None, 'semana':sample.semana if sample else None,
                'casos':sum(r.casos for r in rows) if complete else None,
                'origens':[{'fonte_id':r.serie.fonte_id,'lote_id':r.lote_id} for r in rows], 'municipios_com_dados':sum(r.casos is not None for r in rows), 'anomalia':False, 'referencia':None, 'limiar':None})
            day+=timedelta(weeks=1)
    flags = {r['data']:r for r in strategy(configuration.metodo, configuration.parametros, configuration.versao_algoritmo).analyze(history)}
    for p in history:
        if p['data'] in flags:
            p.update({k:v for k,v in flags[p['data']].items() if k not in ('data','observado')})
            p['anomalia']=True
    selected = [p for p in history if (not start or p['data']>=start) and (not end or p['data']<=end)]
    # Contabiliza também as lacunas nas bordas explicitamente solicitadas.
    first = start or (history[0]['data'] if history else None)
    last = end or (history[-1]['data'] if history else None)
    if first and last and first <= last:
        if (last-first).days > 3660 and (start or end):
            raise ValueError('Selecione um intervalo ordenado de até dez anos.')
        indexed = {p['data']:p for p in selected}
        selected = []
        offset = (6-first.weekday())%7
        if offset > (last-first).days:
            first = None
        else:
            first += timedelta(days=offset)
        while first is not None and first <= last:
            selected.append(indexed.get(first, {'data':first, 'ano':None, 'semana':None,
                'casos':None, 'origens':[], 'municipios_com_dados':0, 'anomalia':False,
                'referencia':None, 'limiar':None}))
            if (last-first).days < 7:
                break
            first += timedelta(weeks=1)
    from .data_quality import summarize
    summary = summarize(history, selected, current, configuration, all_codes)
    recent = selected[-4:]
    previous = selected[-8:-4]
    def average(rows):
        return sum(p['casos'] for p in rows)/4 if len(rows)==4 and all(p['casos'] is not None for p in rows) else None
    a,b = average(recent),average(previous)
    change = (a/b-1)*100 if a is not None and b not in (None,0) else None
    relevant = [r for r in current.values() if (not start or r.data_referencia>=start) and (not end or r.data_referencia<=end)]
    sources = {}
    for r in relevant:
        entry = sources.setdefault(r.serie.fonte_id, {'id':r.serie.fonte_id, 'nome':r.serie.fonte.nome,
            'url':r.lote.url_origem, 'lotes':{}})
        entry['lotes'][r.lote_id] = {'id':r.lote_id, 'url':r.lote.url_origem, 'coletado_em':r.lote.criada_em,
            'sha256':r.lote.sha256, 'sha256_original':r.lote.sha256_original,
            'proveniencia':r.lote.proveniencia}
    for entry in sources.values(): entry['lotes'] = list(entry['lotes'].values())
    return {**summary, 'filtros':{'inicio':start.isoformat() if start else None, 'fim':end.isoformat() if end else None},
        'territorio':{'tipo':kind,'codigo':code,'nome':name}, 'agravo':disease, 'agravo_nome':Agravo.objects.get(codigo=disease).nome, 'integracao':DATASETS.get(indicator),
        'serie':[{**p,'data':p['data'].isoformat()} for p in selected],
        'casos_total':sum(p['casos'] for p in selected if p['casos'] is not None),
        'semanas_com_dados':sum(p['casos'] is not None for p in selected), 'semanas_sem_dados':sum(p['casos'] is None for p in selected),
        'tendencia_percentual':change, 'anomalias':sum(p['anomalia'] for p in selected),
        'municipios_cobertos':len({r.serie.recorte.codigo for r in relevant if r.casos is not None}), 'municipios_regiao':len(all_codes), 'codigos_cobertos':sorted({r.serie.recorte.codigo for r in relevant if r.casos is not None}),
        'fontes':list(sources.values()), 'coletado_em':max((r.lote.criada_em for r in relevant),default=None), 'atualizado_em':max((r.serie.atualizada_em for r in relevant),default=None),
        'detector':configuration_data(configuration)}
