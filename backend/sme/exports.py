"""Exportações da mesma consulta do painel, com proveniência e lacunas preservadas."""
import csv
import io
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from .views import authorized, error
from .indicators import query_indicators
from .models import LoteColeta, RegistroAuditoria
from .processing import week_start

MAX_ROWS = 50_000
MAX_BYTES = 20 * 1024 * 1024


def raw_rows(data):
    pairs = [(p, origin) for p in data['serie'] for origin in p['origens']]
    if len(pairs) > MAX_ROWS:
        raise ValueError('A exportação excede 50 mil registros. Reduza o período ou o recorte.')
    ids = {origin['lote_id'] for _, origin in pairs}
    lots = LoteColeta.objects.filter(pk__in=ids).only('id', 'adaptador', 'dados_brutos', 'territorio_codigo')
    indexed = {}
    for lot in lots:
        by_date = {}
        for row in lot.dados_brutos:
            if lot.adaptador == 'infodengue':
                year, week = divmod(int(row['SE']), 100)
            elif lot.adaptador == 'infogripe':
                year, week = int(row['Ano epidemiológico']), int(row['Semana epidemiológica'])
            elif lot.adaptador in ('sivep', 'esus'):
                year, week = int(row['ano']), int(row['semana'])
            else:
                raise ValueError('O lote usa um provedor sem exportação de registros brutos.')
            by_date[week_start(year, week).isoformat()] = row
        indexed[lot.pk] = (lot.territorio_codigo, by_date)
    result = []
    for point, origin in pairs:
        code, rows = indexed[origin['lote_id']]
        raw = rows.get(point['data'])
        result.append({'data': point['data'], 'municipio_ibge': code, **origin, 'registro_bruto': raw,
                       'ausente_no_lote': raw is None})
    return result


def csv_cell(value):
    if value is None:
        return ''
    if isinstance(value, str) and (value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n'))):
        return "'" + value
    return value


@require_GET
@authorized(permission='exportar_dados')
def export_data(request):
    mode, fmt = request.GET.get('modo', 'agregados'), request.GET.get('formato', 'csv')
    if mode not in ('brutos', 'agregados') or fmt not in ('csv', 'json') or (mode == 'brutos' and fmt != 'json'):
        return error('Use CSV ou JSON para agregados; JSON para registros brutos.')
    try:
        data = query_indicators(request.GET)
        if not data['fontes']:
            return error('Não há registros para exportar neste período.', 400)
        rows = raw_rows(data) if mode == 'brutos' else data['serie']
        if len(rows) > MAX_ROWS:
            raise ValueError('Reduza o período ou o recorte para exportar até 50 mil registros.')
    except ValueError as exc:
        return error(str(exc))
    exported_at = timezone.now().isoformat()
    metadata = {k: v for k, v in data.items() if k != 'serie'}
    metadata.update({'exportado_em': exported_at, 'modo': mode,
        'filtros': {k: request.GET.get(k, '') for k in ('tipo', 'codigo', 'agravo', 'indicador', 'inicio', 'fim')},
        'observacao': ('Registros do lote interpretados pelo coletor, sem agregação entre municípios. '
                      'No SIVEP e e-SUS, são as linhas municipais extraídas do XLSX, com lacunas explícitas. '
                      'Não são os bytes do arquivo original. Revisões vigentes são as mesmas do painel.') if mode == 'brutos' else
                     'Série semanal do recorte. Contagens ausentes permanecem nulas; cobertura parcial não representa toda a região.'})
    if fmt == 'json':
        content = json.dumps({'metadados': metadata, 'registros': rows}, ensure_ascii=False, cls=DjangoJSONEncoder).encode('utf-8')
        content_type = 'application/json; charset=utf-8'
    else:
        output = io.StringIO(newline='')
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['data', 'ano', 'semana', 'casos', 'anomalia', 'referencia', 'limiar', 'municipios_com_dados',
                         'municipios_no_recorte', 'territorio', 'codigo', 'agravo', 'indicador', 'publicador', 'unidade',
                         'origens', 'fontes_e_lotes', 'exportado_em'])
        provenance = json.dumps(data['fontes'], ensure_ascii=False, cls=DjangoJSONEncoder)
        spec = data['integracao'] or {}
        for row in rows:
            writer.writerow([csv_cell(v) for v in [row['data'], row['ano'], row['semana'], row['casos'],
                row['anomalia'], row['referencia'], row['limiar'], row['municipios_com_dados'],
                data['municipios_regiao'], data['territorio']['nome'], data['territorio']['codigo'],
                data['agravo'], spec.get('codigo', ''), spec.get('publicador', ''), spec.get('unidade', ''),
                json.dumps(row['origens']), provenance, exported_at]])
            if output.tell() > MAX_BYTES:
                return error('O arquivo excede 20 MiB. Reduza o período ou o recorte.', 413)
        content = output.getvalue().encode('utf-8-sig')
        content_type = 'text/csv; charset=utf-8'
    if len(content) > MAX_BYTES:
        return error('O arquivo excede 20 MiB. Reduza o período ou o recorte.', 413)
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="sme-{mode}-{data["territorio"]["codigo"]}.{fmt}"'
    response['X-Content-Type-Options'] = 'nosniff'
    RegistroAuditoria.objects.create(usuario=request.user, acao='dados_exportados', entidade='Exportacao', entidade_id=0,
        detalhes={'modo': mode, 'formato': fmt, 'filtros': metadata['filtros'], 'registros': len(rows)})
    return response
