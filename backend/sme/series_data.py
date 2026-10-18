"""Revisões vigentes compartilhadas pelo painel, comparações e detecção."""
from .models import RegistroEpidemiologico


def current_records(codes, indicator, disease=None):
    records = RegistroEpidemiologico.objects.filter(serie__recorte__codigo__in=codes, serie__indicador=indicator)
    if disease:
        records = records.filter(serie__agravo__codigo=disease)
    records = records.select_related('serie__recorte', 'serie__fonte', 'lote').defer('lote__conteudo_original', 'lote__dados_brutos')
    current = {}
    for row in records.order_by('lote__criada_em', 'lote_id', 'pk'):
        current[(row.serie.recorte.codigo, row.data_referencia)] = row
    return current
