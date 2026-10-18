"""Resolve o período no início da execução; a configuração e os lotes antigos ficam intactos."""
from copy import copy
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from django.utils import timezone
from .datasets import DATASETS, source_dataset


def collection_source(source):
    if not getattr(source, 'periodo_movel', False):
        return source
    from .collection import CollectionError
    from .processing import week_start
    spec = DATASETS.get(source_dataset(source), {})
    provider = spec.get('provedor')
    if provider not in ('infodengue', 'sivep'):
        raise CollectionError('O período móvel está disponível para InfoDengue e SIVEP-Gripe.')
    # Nunca corrige ou disfarça URL/território inválidos: os adaptadores validam
    # também a configuração persistida antes de resolver os anos.
    from .collection import get_adapter
    get_adapter(source).validate(source)
    year = timezone.localdate().year
    parsed = urlsplit(source.url)
    params = dict(parse_qsl(parsed.query))
    if provider == 'infodengue':
        params.update(ey_start=str(year-1), ey_end=str(year), ew_start='1',
            ew_end=str((week_start(year+1, 1)-week_start(year, 1)).days//7))
    else:
        params['ano'] = str(year)
    effective = copy(source)
    effective.url = urlunsplit(parsed._replace(query=urlencode(params)))
    return effective
