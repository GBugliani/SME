"""Normalização de lotes InfoDengue e detecção reprodutível; não emite alertas de surto."""
import logging
import math
from datetime import date, timedelta
import pandas as pd
from django.db import transaction
from .collection import CollectionError, InfoDengueAdapter, normalized
from .models import (LoteColeta, Agravo, SerieEpidemiologica, RegistroEpidemiologico,
                     ProcessamentoLote, ConfiguracaoDeteccao, Anomalia)

logger = logging.getLogger(__name__)
PARAMETERS = {'janela': 8, 'desvios': 3.0, 'razao_minima': 2.0, 'piso': 5.0}


def week_start(year, week):
    def first(y):
        january = date(y, 1, 4)
        return january - timedelta(days=(january.weekday() + 1) % 7)
    result = first(year) + timedelta(weeks=week - 1)
    if week < 1 or week > 53 or result >= first(year + 1):
        raise CollectionError('Semana epidemiológica inexistente para o ano informado.')
    return result


class MovingBaseline:
    name = 'media_movel'
    version = 1

    def analyze(self, points):
        if not points:
            return []
        frame = pd.DataFrame(points).set_index('data')
        frame.index = pd.to_datetime(frame.index)
        frame = frame.reindex(pd.date_range(frame.index.min(), frame.index.max(), freq='7D'))
        values = pd.to_numeric(frame['casos'], errors='coerce')
        past = values.shift(1).rolling(PARAMETERS['janela'], min_periods=PARAMETERS['janela'])
        mean, deviation = past.mean(), past.std(ddof=0)
        threshold = pd.concat([mean + PARAMETERS['desvios'] * deviation,
                               mean * PARAMETERS['razao_minima'],
                               pd.Series(PARAMETERS['piso'], index=frame.index)], axis=1).max(axis=1)
        output = []
        for day in frame.index:
            if pd.notna(mean.loc[day]) and pd.notna(values.loc[day]) and values.loc[day] > threshold.loc[day]:
                output.append({'data': day.date(), 'observado': int(values.loc[day]),
                               'referencia': float(mean.loc[day]), 'limiar': float(threshold.loc[day])})
        return output


class SeriesRepository:
    def persist(self, lote, rows):
        # Fonte serializa revisões do mesmo território. Dados do lote permanecem imutáveis.
        source = lote.fonte
        from .models import FonteEpidemiologica, RecorteGeografico
        FonteEpidemiologica.objects.select_for_update().get(pk=source.pk)
        territory = RecorteGeografico.objects.get(tipo='municipio', codigo=lote.territorio_codigo)
        disease, _ = Agravo.objects.get_or_create(codigo=lote.agravo, defaults={'nome':'Dengue'})
        series, _ = SerieEpidemiologica.objects.get_or_create(fonte=source, recorte=territory, agravo=disease)
        for row in rows:
            old = series.registros.filter(ano=row['ano'], semana=row['semana']).select_related('lote').first()
            # Reprocessamento de lote antigo não sobrescreve uma revisão mais recente.
            if old and (old.lote.criada_em, old.lote_id) > (lote.criada_em, lote.pk):
                continue
            RegistroEpidemiologico.objects.update_or_create(serie=series, ano=row['ano'], semana=row['semana'],
                defaults={'data_referencia':row['data'], 'casos':row['casos'], 'casos_estimados':row['estimados'], 'lote':lote})
        series.save(update_fields=['atualizada_em'])
        return series


def normalize_lote(lote):
    from types import SimpleNamespace
    from .collection import MUNICIPIOS_SP
    from urllib.parse import parse_qs, urlsplit
    code = lote.territorio_codigo
    if lote.adaptador != 'infodengue' or lote.agravo != 'dengue' or code not in MUNICIPIOS_SP:
        raise CollectionError('Não existe normalizador compatível com este lote.')
    source = SimpleNamespace(url=lote.url_origem, tipo='json', recorte=SimpleNamespace(
        tipo='municipio', codigo=code, uf='SP', nome=MUNICIPIOS_SP[code]))
    adapter = InfoDengueAdapter()
    q = adapter.validate(source)
    adapter.validate_payload(lote.dados_brutos, source, q)
    rows = []
    frame = pd.DataFrame(lote.dados_brutos)
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
    configuration, _ = ConfiguracaoDeteccao.objects.get_or_create(metodo=MovingBaseline.name, versao=1,
                                                               defaults={'parametros':PARAMETERS})
    # Uma versão nunca muda silenciosamente seus parâmetros.
    if configuration.parametros != PARAMETERS:
        raise CollectionError('Parâmetros do detector diferem da versão registrada.')
    records = list(series.registros.all())
    by_date = {r.data_referencia:r for r in records}
    points = [{'data':r.data_referencia, 'casos':r.casos} for r in records]
    Anomalia.objects.filter(registro__serie=series, configuracao=configuration).update(ativa=False)
    for item in MovingBaseline().analyze(points):
        Anomalia.objects.update_or_create(registro=by_date[item['data']], configuracao=configuration,
            defaults={k:v for k,v in item.items() if k!='data'} | {'ativa':True})


def process_lote(lote_id):
    lote = LoteColeta.objects.select_related('fonte').get(pk=lote_id)
    try:
        rows = normalize_lote(lote)
        with transaction.atomic():
            LoteColeta.objects.select_for_update().get(pk=lote.pk)
            if rows:
                series = SeriesRepository().persist(lote, rows)
                detect_series(series)
            result, _ = ProcessamentoLote.objects.update_or_create(lote=lote, defaults={
                'status':'sucesso','mensagem':'Dados validados e padronizados.' if rows else 'Lote vazio; nenhuma semana preenchida com zero.',
                'quantidade_registros':len(rows), 'versao':'infodengue_v1'})
    except Exception as exc:
        message = str(exc)[:300] if isinstance(exc, CollectionError) else 'Falha interna no processamento do lote.'
        logger.warning('Processamento do lote %s falhou: %s', lote.pk, message)
        result, _ = ProcessamentoLote.objects.update_or_create(lote=lote, defaults={
            'status':'erro','mensagem':message,'quantidade_registros':0, 'versao':'infodengue_v1'})
    return result
