from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .collection import eligible_source_ids
from .models import ExecucaoColeta, FonteEpidemiologica, RegistroEpidemiologico, RotinaColeta
from .views import authorized, error


def routine_data(routine):
    if routine is None:
        return None
    latest = {}
    for row in routine.coletas.order_by('pk').values('fonte_id', 'status', 'finalizada_em'):
        latest[row['fonte_id']] = row
    counts = {key: 0 for key in ('sucesso', 'vazia', 'erro', 'executando', 'sem_confirmacao')}
    for source_id in routine.fontes_previstas:
        row = latest.get(source_id)
        counts[row['status'] if row else 'sem_confirmacao'] += 1
    complete = routine.finalizada_em is not None
    status = ('com_falhas' if counts['erro'] or counts['executando'] or counts['sem_confirmacao'] else 'concluida') if complete else 'executando'
    if not complete and routine.iniciada_em < timezone.now() - timedelta(hours=26):
        status = 'sem_confirmacao'
    return {'id': routine.pk, 'run_id': routine.run_id, 'tipo': routine.tipo,
            'iniciada_em': routine.iniciada_em, 'finalizada_em': routine.finalizada_em,
            'status': status, 'previstas': len(routine.fontes_previstas), 'contagens': counts}


@require_GET
@authorized()
def health(request):
    situation = request.GET.get('situacao', '')
    if situation not in ('', 'falhas', 'atrasadas', 'vazias', 'executando', 'sem_coleta'):
        return error('Filtro de situação inválido.')
    now = timezone.now()
    limit = settings.COLLECTION_STALE_HOURS
    latest = ExecucaoColeta.objects.filter(fonte_id=OuterRef('pk')).order_by('-iniciada_em', '-pk')
    success = ExecucaoColeta.objects.filter(fonte_id=OuterRef('pk'), status='sucesso').order_by('-finalizada_em')
    week = RegistroEpidemiologico.objects.filter(serie__fonte_id=OuterRef('pk'), casos__isnull=False).order_by('-data_referencia')
    rows = FonteEpidemiologica.objects.filter(pk__in=eligible_source_ids()).select_related('recorte').annotate(
        tentativa=Subquery(latest.values('iniciada_em')[:1]),
        estado=Subquery(latest.values('status')[:1]),
        mensagem=Subquery(latest.values('mensagem')[:1]),
        processamento=Subquery(latest.values('lote__processamento__status')[:1]),
        ultima_sucesso=Subquery(success.values('finalizada_em')[:1]),
        semana=Subquery(week.values('data_referencia')[:1]),
    ).order_by('recorte__nome', 'nome', 'pk')
    counts = {key: 0 for key in ('total', 'falhas', 'atrasadas', 'vazias', 'executando', 'sem_coleta', 'ok')}
    selected = []
    query = request.GET.get('q', '').strip().casefold()[:200]
    for source in rows:
        state = 'sem_coleta'
        if source.estado == 'executando':
            state = 'falhas' if source.tentativa < now - timedelta(minutes=10) else 'executando'
        elif source.processamento == 'erro' or source.estado == 'erro':
            state = 'falhas'
        elif source.estado == 'vazia':
            state = 'vazias'
        elif source.estado == 'sucesso':
            state = 'ok'
        stale = (source.ultima_sucesso or source.criada_em) < now - timedelta(hours=limit)
        counts['total'] += 1
        counts[state] += 1
        counts['atrasadas'] += int(stale)
        if situation and not (stale if situation == 'atrasadas' else state == situation):
            continue
        if query and not all(term in f'{source.nome} {source.recorte.nome} {source.recorte.codigo} {source.indicador}'.casefold() for term in query.split()):
            continue
        selected.append({'id': source.pk, 'nome': source.nome, 'municipio': source.recorte.nome,
                         'codigo': source.recorte.codigo, 'situacao': state, 'atrasada': stale,
                         'ultima_tentativa': source.tentativa, 'ultima_sucesso': source.ultima_sucesso,
                         'ultima_semana': source.semana, 'processamento_falhou': source.processamento == 'erro',
                         'mensagem': 'Execução sem conclusão há mais de 10 minutos.' if source.estado == 'executando' and state == 'falhas' else source.mensagem or ''})
    page = Paginator(selected, 20).get_page(request.GET.get('page', 1))
    local_now = now.astimezone(ZoneInfo('America/Sao_Paulo'))
    today = datetime.combine(local_now.date(), time(6), tzinfo=local_now.tzinfo)
    next_run = today if local_now < today else today + timedelta(days=1)
    scheduled = RotinaColeta.objects.filter(tipo='scheduled').order_by('-iniciada_em').first()
    expected = today if local_now >= today else today - timedelta(days=1)
    return JsonResponse({'resumo': counts, 'limite_atraso_horas': limit, 'atualizado_em': now,
                         'agendamento': {'ultima': routine_data(scheduled), 'proxima_prevista': next_run,
                             'monitoramento_disponivel': scheduled is not None,
                             'sem_confirmacao': scheduled is not None and scheduled.iniciada_em < expected,
                             'ultima_rotina': routine_data(RotinaColeta.objects.order_by('-iniciada_em').first())},
                         'fontes': list(page), 'page': page.number, 'pages': page.paginator.num_pages,
                         'count': page.paginator.count})
