"""Ausência de contagem não é zero nem ausência de anomalia."""
from datetime import timedelta
from django.utils import timezone


def summarize(history, selected, current, configuration, all_codes):
    window = configuration.parametros['janela']
    eligible, consecutive = set(), 0
    for point in history:
        if point['casos'] is None:
            consecutive = 0
        else:
            if consecutive >= window:
                eligible.add(point['data'])
            consecutive += 1
    points = [p for p in selected if p['casos'] is not None]
    latest_base = max((r.data_referencia for r in current.values() if r.casos is not None), default=None)
    latest_period = max((p['data'] for p in points), default=None)
    today = timezone.localdate()
    closed = today-timedelta(days=(today.weekday()+1)%7+7)
    evaluated = sum(p['data'] in eligible for p in selected)
    selected_dates = {p['data'] for p in selected}
    covered = {r.serie.recorte.codigo for r in current.values()
        if r.casos is not None and r.data_referencia in selected_dates}
    checked = max((r.serie.fonte.ultima_coleta_em for r in current.values()
        if r.serie.fonte.ultima_coleta_em), default=None)
    return {
        'atualidade':{'ultima_semana_base':latest_base, 'ultima_semana_periodo':latest_period,
            'ultima_semana_fechada':closed,
            'defasagem_semanas':max(0, (closed-latest_base).days//7) if latest_base else None,
            'periodo_historico':bool(latest_period and latest_base and latest_period < latest_base),
            'ultima_consulta_em':checked},
        'qualidade':{'semanas_esperadas':len(selected), 'semanas_completas':len(points),
            'semanas_sem_contagem_completa':len(selected)-len(points),
            'completude_percentual':round(len(points)/len(selected)*100, 1) if selected else None,
            'municipios_com_dados':len(covered), 'municipios_previstos':len(all_codes),
            'cobertura_percentual':round(len(covered)/len(all_codes)*100, 1),
            'janela_deteccao':window, 'semanas_avaliaveis':evaluated,
            'semanas_com_dados_sem_base':len(points)-evaluated,
            'inicio_historico':history[0]['data'] if history else None,
            'fim_historico':history[-1]['data'] if history else None}}
