"""Normalização por contrato de integração, detecção versionada e alertas no painel."""
import logging
import math
from datetime import date, timedelta
import pandas as pd
from django.db import transaction
from .collection import CollectionError, get_adapter
from .datasets import DATASETS, DISEASES, infer_dataset
from .models import (LoteColeta, Agravo, SerieEpidemiologica, RegistroEpidemiologico,
                     ProcessamentoLote, ConfiguracaoDeteccao, Anomalia)

logger = logging.getLogger(__name__)
from .detectors import PARAMETERS, MovingBaseline


def week_start(year, week):
    def first(y):
        january = date(y, 1, 4)
        return january - timedelta(days=(january.weekday() + 1) % 7)
    result = first(year) + timedelta(weeks=week - 1)
    if week < 1 or week > 53 or result >= first(year + 1):
        raise CollectionError('Semana epidemiológica inexistente para o ano informado.')
    return result


class SeriesRepository:
    def persist(self, lote, rows):
        source = lote.fonte
        from .models import FonteEpidemiologica, RecorteGeografico
        FonteEpidemiologica.objects.select_for_update().get(pk=source.pk)
        territory = RecorteGeografico.objects.get(tipo='municipio', codigo=lote.territorio_codigo)
        disease, _ = Agravo.objects.get_or_create(codigo=lote.agravo, defaults={'nome':DISEASES[lote.agravo]})
        series, _ = SerieEpidemiologica.objects.get_or_create(fonte=source, recorte=territory, agravo=disease, indicador=lote.indicador or infer_dataset(lote.url_origem))
        existing = {(r.ano,r.semana):r for r in series.registros.select_related('lote').only('ano','semana','lote_id','lote__criada_em')}
        if lote.adaptador in ('sivep', 'esus') and rows:
            published = {(r['ano'], r['semana']) for r in rows}
            year = rows[0]['ano']
            for key, old in existing.items():
                if key[0] == year and key not in published and (old.lote.criada_em, old.lote_id) <= (lote.criada_em, lote.pk):
                    RegistroEpidemiologico.objects.filter(pk=old.pk).update(casos=None, casos_estimados=None, lote=lote)
        for row in rows:
            old = existing.get((row['ano'],row['semana']))
            if old and (old.lote.criada_em, old.lote_id) > (lote.criada_em, lote.pk):
                continue
            RegistroEpidemiologico.objects.update_or_create(serie=series, ano=row['ano'], semana=row['semana'],
                defaults={'data_referencia':row['data'], 'casos':row['casos'], 'casos_estimados':row['estimados'], 'lote':lote})
        series.save(update_fields=['atualizada_em'])
        return series


def normalize_lote(lote):
    from types import SimpleNamespace
    from .collection import MUNICIPIOS_SP
    code = lote.territorio_codigo
    key = lote.indicador or infer_dataset(lote.url_origem)
    spec = DATASETS.get(key)
    if not spec or spec['provedor'] != lote.adaptador or spec['agravo'] != lote.agravo or code not in MUNICIPIOS_SP:
        raise CollectionError('Não existe normalizador compatível com este lote.')
    source = SimpleNamespace(url=lote.url_origem, indicador=key, tipo=spec['formato'], recorte=SimpleNamespace(
        tipo='municipio', codigo=code, uf='SP', nome=MUNICIPIOS_SP[code]))
    adapter = get_adapter(source)
    return adapter.normalize(lote.dados_brutos, source)


def normalize_infodengue(data):
    rows = []
    frame = pd.DataFrame(data)
    if frame.empty:
        return rows
    if 'data_iniSE' not in frame:
        raise CollectionError('O lote não informa a data de início da semana epidemiológica.')
    for row in frame.to_dict('records'):
        year, week = divmod(row['SE'], 100)
        expected = week_start(year, week)
        raw_date = row['data_iniSE']
        try:
            if isinstance(raw_date, (int,float)) and not isinstance(raw_date,bool):
                day = pd.to_datetime(raw_date, unit='ms', utc=True).date()
            elif isinstance(raw_date, str):
                day = pd.to_datetime(raw_date, utc=True).date()
            else:
                raise ValueError()
        except (ValueError, TypeError, OverflowError):
            raise CollectionError('Data de referência inválida no lote.')
        if day != expected:
            raise CollectionError('Data de início não corresponde à semana epidemiológica informada.')
        cases = row['casos']
        if pd.isna(cases):
            cases = None
        elif not float(cases).is_integer():
            raise CollectionError('Casos notificados devem ser números inteiros.')
        else:
            cases = int(cases)
        estimated = row.get('casos_est')
        if estimated is None or pd.isna(estimated):
            estimated = None
        elif isinstance(estimated,bool) or not isinstance(estimated,(int,float)) or not math.isfinite(estimated) or estimated < 0:
            raise CollectionError('Estimativa de casos inválida.')
        rows.append({'ano':year, 'semana':week, 'data':day, 'casos':cases, 'estimados':estimated})
    return sorted(rows, key=lambda r:r['data'])


def detect_series(series):
    from .detection import analyze_territory
    analyze_territory(series.recorte_id, series.indicador, notify_email=True)


def process_lote(lote_id):
    lote = LoteColeta.objects.select_related('fonte').defer('conteudo_original').get(pk=lote_id)
    version = DATASETS.get(lote.indicador or infer_dataset(lote.url_origem), {}).get('versao', 'desconhecido')
    try:
        rows = normalize_lote(lote)
        with transaction.atomic():
            LoteColeta.objects.select_for_update().get(pk=lote.pk)
            if rows:
                series = SeriesRepository().persist(lote, rows)
                detect_series(series)
            result, _ = ProcessamentoLote.objects.update_or_create(lote=lote, defaults={
                'status':'sucesso','mensagem':'Dados validados e padronizados.' if rows else 'Lote vazio; nenhuma semana preenchida com zero.',
                'quantidade_registros':len(rows), 'versao':version})
    except Exception as exc:
        message = str(exc)[:300] if isinstance(exc, CollectionError) else 'Falha interna no processamento do lote.'
        logger.warning('Processamento do lote %s falhou: %s', lote.pk, message)
        result, _ = ProcessamentoLote.objects.update_or_create(lote=lote, defaults={
            'status':'erro','mensagem':message,'quantidade_registros':0, 'versao':version})
    return result
