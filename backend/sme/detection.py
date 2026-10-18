"""Detecção municipal canônica e alertas idempotentes com leitura individual."""
import logging
from datetime import timedelta
from types import SimpleNamespace
from django.db import transaction
from django.utils import timezone
from .collection import CollectionError
from .datasets import DATASETS
from .detectors import METHODS, PARAMETERS, strategy
from .models import (PerfilAcesso, ConfiguracaoDeteccao, RecorteGeografico, Anomalia,
                     AlertaSurto, ReanaliseDeteccao, RegistroEpidemiologico)
from .series_data import current_records

logger = logging.getLogger(__name__)


def lock_detection():
    # Mesmo lock das alterações administrativas: uma ativação não cruza uma análise.
    return PerfilAcesso.objects.select_for_update().get(codigo='administrador')


def configuration_for(indicator):
    qs = ConfiguracaoDeteccao.objects.filter(ativa=True)
    return (qs.filter(indicador=indicator).first() or qs.filter(indicador='').first() or
            SimpleNamespace(pk=None, metodo='media_movel', versao=1, parametros=dict(PARAMETERS),
                            indicador='', ativa=True, criada_em=None, versao_algoritmo=1))


def ensure_configuration(indicator):
    config = configuration_for(indicator)
    if config.pk is None:
        config, _ = ConfiguracaoDeteccao.objects.get_or_create(metodo='media_movel', versao=1,
            defaults={'parametros':dict(PARAMETERS)})
        config.ativa = True
        config.save(update_fields=['ativa'])
    return config


def configuration_data(config):
    return {'id': config.pk, 'metodo':config.metodo, 'nome':METHODS.get(config.metodo, {}).get('nome', config.metodo),
            'versao':config.versao, 'versao_algoritmo':config.versao_algoritmo,
            'parametros':config.parametros, 'indicador':config.indicador, 'ativa':config.ativa,
            'criada_em':config.criada_em.isoformat() if config.criada_em else None}


@transaction.atomic
def analyze_territory(territory_id, indicator, expected_config=None):
    lock_detection()
    config = ensure_configuration(indicator)
    if expected_config is not None and config.pk != expected_config:
        return False
    territory = RecorteGeografico.objects.get(pk=territory_id)
    current = current_records([territory.codigo], indicator)
    records = {day:r for (_, day),r in current.items()}
    try:
        flags = strategy(config.metodo, config.parametros, config.versao_algoritmo).analyze(
            [{'data':day, 'casos':r.casos} for day,r in sorted(records.items())])
    except ValueError as exc:
        raise CollectionError(str(exc)) from exc
    Anomalia.objects.filter(registro__serie__recorte_id=territory_id, registro__serie__indicador=indicator).update(ativa=False)
    alerts = AlertaSurto.objects.filter(recorte_id=territory_id, indicador=indicator)
    alerts.filter(ativa=True).exclude(configuracao=config).update(ativa=False, motivo_encerramento='Configuração substituída', atualizada_em=timezone.now())
    days = []
    for item in flags:
        day = item['data']; record = records[day]; days.append(day)
        anomaly, _ = Anomalia.objects.update_or_create(registro=record, configuracao=config,
            defaults={k:v for k,v in item.items() if k!='data'} | {'ativa':True})
        values = {'anomalia_id':anomaly.pk, 'lote_id':record.lote_id,
            'titulo':f'Crescimento acima do padrão · {territory.nome}',
            'mensagem': f'{DATASETS[indicator]["agravo_nome"]}: {item["observado"]} casos na semana de {day:%d/%m/%Y}, acima do limiar {item["limiar"]:.1f}. Sinal de possível surto para investigação; não confirma ocorrência.',
            'observado':item['observado'], 'referencia':item['referencia'], 'limiar':item['limiar'],
            'ativa':True, 'motivo_encerramento':''}
        alert, created = AlertaSurto.objects.get_or_create(recorte_id=territory_id, indicador=indicator,
            data_referencia=day, configuracao=config, defaults=values)
        if not created and any(getattr(alert, key)!=value for key,value in values.items()):
            for key,value in values.items(): setattr(alert, key, value)
            alert.revisao += 1
            alert.save()
    alerts.filter(configuracao=config, ativa=True).exclude(data_referencia__in=days).update(
        ativa=False, motivo_encerramento='Dados revisados: semana fora do critério', atualizada_em=timezone.now())
    return True


def job_data(job):
    return {'id':job.pk, 'configuracao_id':job.configuracao_id, 'status':job.status, 'total':job.total,
            'processados':job.processados, 'mensagem':job.mensagem, 'criada_em':job.criada_em,
            'atualizada_em':job.atualizada_em, 'finalizada_em':job.finalizada_em}


def run_next_job():
    # Trabalho ao menos uma vez. Uma execução interrompida volta à fila; análises são idempotentes.
    with transaction.atomic():
        ReanaliseDeteccao.objects.filter(status='executando', atualizada_em__lt=timezone.now()-timedelta(minutes=10)).update(status='pendente')
        job = ReanaliseDeteccao.objects.select_for_update(skip_locked=True).filter(status='pendente').order_by('pk').first()
        if job is None:
            return None
        job.status = 'executando'; job.mensagem = ''; job.processados = 0; job.save()
    try:
        config = job.configuracao
        targets = RegistroEpidemiologico.objects.all()
        if config.indicador:
            targets = targets.filter(serie__indicador=config.indicador)
        pairs = list(targets.order_by().values_list('serie__recorte_id', 'serie__indicador').distinct())
        job.total = len(pairs); job.save(update_fields=['total', 'atualizada_em'])
        for territory_id, indicator in pairs:
            if not ConfiguracaoDeteccao.objects.filter(pk=config.pk, ativa=True).exists():
                job.status = 'substituida'; break
            analyze_territory(territory_id, indicator, expected_config=config.pk)
            job.processados += 1; job.save(update_fields=['processados', 'atualizada_em'])
        else:
            job.status = 'sucesso' if ConfiguracaoDeteccao.objects.filter(pk=config.pk, ativa=True).exists() else 'substituida'
        job.mensagem = 'Reanálise concluída.' if job.status=='sucesso' else 'Uma configuração mais recente substituiu esta execução.'
    except Exception:
        logger.exception('Falha na reanálise %s', job.pk)
        job.status = 'erro'; job.mensagem = 'Falha na reanálise. Consulte os logs e tente novamente pela administração.'
    job.finalizada_em = timezone.now(); job.save()
    return job
