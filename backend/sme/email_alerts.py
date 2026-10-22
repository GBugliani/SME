"""Fila durável de avisos por e-mail, sem segredos no banco de dados."""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .datasets import DATASETS
from .alert_presentation import decimal_pt
from .models import ConfiguracaoEmail, DestinoEmail, EnvioAlertaEmail

logger = logging.getLogger(__name__)
MAX_DESTINATARIOS = 200
MAX_TENTATIVAS = 5


def smtp_configured():
    return bool(settings.EMAIL_HOST and settings.EMAIL_HOST_USER and
                settings.EMAIL_HOST_PASSWORD and settings.DEFAULT_FROM_EMAIL and
                (settings.EMAIL_USE_SSL != settings.EMAIL_USE_TLS))


def recipient_addresses():
    addresses = set()
    for destination in DestinoEmail.objects.select_related('grupo'):
        if destination.grupo_id:
            addresses.update(destination.grupo.enderecos)
        else:
            addresses.add(destination.email)
    return sorted(addresses)


def eligible_week(day, today=None):
    """Apenas semana já encerrada, até 14 dias depois de seu encerramento."""
    today = today or timezone.localdate()
    return day + timedelta(days=7) <= today <= day + timedelta(days=21)


def alert_email_content(alert, *, example=False):
    """Compartilha o conteúdo do aviso automático com a demonstração ao admin."""
    spec = DATASETS[alert.indicador]
    disease = spec['agravo_nome']
    place = f'{alert.recorte.nome}/{alert.recorte.uf}' if alert.recorte.uf else alert.recorte.nome
    week = alert.data_referencia.strftime('%d/%m/%Y')
    subject = f'[SME] {disease} · {place} · semana de {week}'
    body = (f'Sinalização epidemiológica: {disease}\n'
            f'Território: {place}\nSemana iniciada em: {week}\n'
            f'{spec["indicador_nome"]}: {alert.observado}\n'
            f'Referência: {decimal_pt(alert.referencia)}\nLimiar: {decimal_pt(alert.limiar)}\n'
            f'Origem: {alert.lote.fonte.nome}\n\n'
            'O resultado estatístico requer investigação e não confirma um surto.\n')
    if settings.APP_PUBLIC_URL:
        body += f'Abra o SME: {settings.APP_PUBLIC_URL.rstrip("/")}/\n'
    if example:
        subject = f'[SME] Exemplo de alerta · {disease} · {place} · semana de {week}'
        body = ('DEMONSTRAÇÃO — este alerta já estava registrado no SME. '
                'Este e-mail não indica uma nova ocorrência.\n\n' + body)
    return subject[:255], body


def enqueue_alert_email(alert):
    """Chamado na mesma transação da coleta, nunca por reanálise histórica."""
    if not eligible_week(alert.data_referencia):
        return 0
    if not ConfiguracaoEmail.objects.filter(pk=1, habilitado=True).exists():
        return 0
    if not smtp_configured():
        return 0
    addresses = recipient_addresses()
    if not addresses:
        return 0
    if len(addresses) > MAX_DESTINATARIOS:
        logger.error('Número de destinatários de alerta acima do limite configurado.')
        return 0
    subject, body = alert_email_content(alert)
    created = 0
    for address in addresses:
        _, was_created = EnvioAlertaEmail.objects.get_or_create(
            alerta=alert, revisao=alert.revisao, destinatario=address,
            defaults={'assunto':subject, 'corpo':body})
        created += was_created
    return created


def run_next_email():
    """Reivindica uma entrega; tentativas SMTP acontecem fora da transação."""
    if not ConfiguracaoEmail.objects.filter(pk=1, habilitado=True).exists() or not smtp_configured():
        return None
    now = timezone.now()
    with transaction.atomic():
        EnvioAlertaEmail.objects.filter(status='enviando', atualizado_em__lt=now-timedelta(minutes=10)).update(
            status='pendente', proxima_tentativa_em=now, atualizado_em=now)
        delivery = (EnvioAlertaEmail.objects.select_for_update(skip_locked=True)
            .select_related('alerta').filter(status='pendente')
            .filter(Q(proxima_tentativa_em__isnull=True) | Q(proxima_tentativa_em__lte=now))
            .order_by('pk').first())
        if delivery is None:
            return None
        if not delivery.alerta.ativa or delivery.alerta.revisao != delivery.revisao:
            delivery.status = 'cancelado'
            delivery.erro = 'Alerta substituído ou encerrado.'
            delivery.save(update_fields=['status', 'erro', 'atualizado_em'])
            return delivery
        delivery.status = 'enviando'
        delivery.tentativas += 1
        delivery.save(update_fields=['status', 'tentativas', 'atualizado_em'])
    try:
        sent = EmailMessage(delivery.assunto, delivery.corpo, settings.DEFAULT_FROM_EMAIL,
                            [delivery.destinatario]).send(fail_silently=False)
        if sent != 1:
            raise RuntimeError('SMTP não confirmou a entrega')
    except Exception as exc:
        logger.warning('Falha no envio do aviso %s: %s', delivery.pk, type(exc).__name__)
        delivery.status = 'erro' if delivery.tentativas >= MAX_TENTATIVAS else 'pendente'
        delivery.erro = type(exc).__name__[:100]
        delivery.proxima_tentativa_em = (timezone.now() + timedelta(minutes=min(60, 2**delivery.tentativas))
                                       if delivery.status == 'pendente' else None)
        delivery.save(update_fields=['status', 'erro', 'proxima_tentativa_em', 'atualizado_em'])
    else:
        delivery.status = 'enviado'
        delivery.erro = ''
        delivery.enviado_em = timezone.now()
        delivery.proxima_tentativa_em = None
        delivery.save(update_fields=['status', 'erro', 'enviado_em', 'proxima_tentativa_em', 'atualizado_em'])
    return delivery
