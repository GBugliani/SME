from django.utils import timezone
from .models import EventoSinalizacao


def record_event(alert, kind):
    config = alert.configuracao
    return EventoSinalizacao.objects.create(alerta=alert, tipo=kind, estado={
        'revisao': alert.revisao, 'ativa': alert.ativa, 'motivo': alert.motivo_encerramento,
        'observado': alert.observado, 'referencia': alert.referencia, 'limiar': alert.limiar,
        'lote_id': alert.lote_id, 'semana': alert.data_referencia.isoformat(),
        'configuracao': {'id': config.pk, 'metodo': config.metodo, 'versao': config.versao,
                         'parametros': config.parametros, 'versao_algoritmo': config.versao_algoritmo}})


def close_alerts(queryset, reason):
    for alert in queryset.select_related('configuracao').select_for_update():
        if not alert.eventos.exists():
            record_event(alert, 'estado_inicial')
        alert.ativa = False
        alert.motivo_encerramento = reason
        alert.atualizada_em = timezone.now()
        alert.save(update_fields=['ativa', 'motivo_encerramento', 'atualizada_em'])
        record_event(alert, 'encerrada')
