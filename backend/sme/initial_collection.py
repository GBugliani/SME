"""Primeira coleta automática, com fila persistida no PostgreSQL."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .collection import CollectionError, collect_source, get_adapter
from .collection_period import collection_source
from .models import ColetaInicial, FonteEpidemiologica


def enqueue_uncollected_sources():
    """Inclui fontes antigas sem tentativa ao iniciar o worker, sem recadastrar falhas."""
    sources = (FonteEpidemiologica.objects.filter(
        ativa=True, arquivada_em__isnull=True, coletas__isnull=True,
        coleta_inicial__isnull=True).exclude(indicador='').select_related('recorte'))
    for source in sources.iterator():
        try:
            effective = collection_source(source)
            get_adapter(effective).validate(effective)
        except CollectionError:
            continue
        ColetaInicial.objects.get_or_create(fonte=source)


def run_next_initial_collection():
    """Processa um pedido; recupera pedidos interrompidos após 10 minutos."""
    now = timezone.now()
    with transaction.atomic():
        job = (ColetaInicial.objects.select_for_update(skip_locked=True)
            .filter(Q(status='pendente') | Q(status='executando', atualizada_em__lt=now-timedelta(minutes=10)))
            .order_by('criada_em', 'pk').first())
        if job is None:
            return None
        job.status = 'executando'
        job.tentativas += 1
        job.mensagem = ''
        job.save(update_fields=['status', 'tentativas', 'mensagem', 'atualizada_em'])

    source = FonteEpidemiologica.objects.get(pk=job.fonte_id)
    if source.arquivada_em or not source.ativa or source.coletas.exists():
        job.status = 'ignorada'
        job.mensagem = 'Fonte desabilitada, arquivada ou já coletada.'
    else:
        try:
            run = collect_source(source.pk, origin='inicial')
        except CollectionError as exc:
            job.status = 'ignorada' if source.coletas.exists() else 'erro'
            job.mensagem = str(exc)[:300]
        else:
            job.status = 'erro' if run.status == 'erro' else 'concluida'
            job.mensagem = run.mensagem
    job.save(update_fields=['status', 'mensagem', 'atualizada_em'])
    return job
