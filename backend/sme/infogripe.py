"""Série semanal de SRAG das capitais, escala casos, sem filtro de febre."""
import csv
import io
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from .collection import CollectionError, fetch_public, normalized
from .datasets import INFOGRIPE_URL

CASES = 'Casos semanais reportados até a última atualização'
YEAR, WEEK = 'Ano epidemiológico', 'Semana epidemiológica'
GROUP = 'Grupo Jurídico'
REQUIRED = {CASES, YEAR, WEEK, GROUP, 'CO_MUN_RES', 'CO_MUN_RES_nome', 'DS_UF_SIGLA', 'escala', 'casos estimados'}


class InfoGripeAdapter:
    name = 'infogripe'
    disease = 'srag'
    dataset = 'infogripe_srag'

    def __init__(self, disease='srag'):
        if disease != 'srag':
            raise CollectionError('Agravo não suportado pelo adaptador InfoGripe.')

    def validate(self, source):
        if source.url != INFOGRIPE_URL or source.tipo != 'csv':
            raise CollectionError('Use o CSV oficial de estimativas de SRAG das capitais, sem filtro de febre.')
        r = source.recorte
        if r.tipo != 'municipio' or r.codigo != '3550308' or r.uf != 'SP' or normalized(r.nome) != 'sao paulo':
            raise CollectionError('Esta integração InfoGripe cobre São Paulo capital; não cobre os demais municípios de SP.')

    def fetch(self, source):
        self.validate(source)
        url = urlsplit(INFOGRIPE_URL)
        self.raw_body, self.http_metadata = fetch_public(url.hostname, url.path, limit=8 * 1024 * 1024)
        return self.parse(self.raw_body)

    def parse(self, body):
        try:
            reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig')), delimiter=';')
            if not REQUIRED.issubset(reader.fieldnames or []):
                raise CollectionError('O esquema do CSV InfoGripe mudou; nenhum dado foi importado.')
            selected = []
            for index, row in enumerate(reader):
                if index > 200_000:
                    raise CollectionError('CSV InfoGripe excedeu o limite de registros.')
                if None in row or any(row.get(k) is None for k in REQUIRED):
                    raise CollectionError('Linha incompleta ou colunas extras no CSV InfoGripe.')
                if row['CO_MUN_RES'] == '355030' and row['escala'] == 'casos' and row[GROUP] == '0':
                    selected.append(row)
        except (UnicodeError, csv.Error) as exc:
            raise CollectionError('CSV InfoGripe inválido.') from exc
        self.normalize(selected)
        return selected

    def normalize(self, rows, source=None):
        if source is not None:
            self.validate(source)
        from .processing import week_start
        from django.utils import timezone
        if not isinstance(rows, list) or len(rows) > 6000:
            raise CollectionError('Resposta semanal InfoGripe inválida.')
        result, seen = [], set()
        for row in rows:
            if not isinstance(row, dict) or not REQUIRED.issubset(row):
                raise CollectionError('Registro InfoGripe incompleto.')
            if (row['CO_MUN_RES'] != '355030' or row['DS_UF_SIGLA'] != 'SP'
                    or normalized(row['CO_MUN_RES_nome']) != 'sao paulo'
                    or row['escala'] != 'casos' or row[GROUP] != '0'):
                raise CollectionError('Território, escala ou grupo incompatível com a série InfoGripe.')
            try:
                year, week = int(row[YEAR]), int(row[WEEK])
                if not 2000 <= year <= timezone.localdate().year:
                    raise ValueError()
                day = week_start(year, week)
                cases = self.number(row[CASES], integer=True)
                estimated = self.number(row['casos estimados'])
            except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
                raise CollectionError('Semana ou contagem inválida no InfoGripe.') from exc
            if day in seen:
                raise CollectionError('Semana duplicada no InfoGripe; verifique as dimensões da série.')
            seen.add(day)
            result.append({'ano':year, 'semana':week, 'data':day, 'casos':cases, 'estimados':estimated})
        return sorted(result, key=lambda r:r['data'])

    @staticmethod
    def number(value, integer=False):
        if value == '':
            return None
        value = Decimal(value.replace(',', '.'))
        if not value.is_finite() or value < 0 or value > 9_000_000_000_000_000 or (integer and value != value.to_integral_value()):
            raise ValueError()
        return int(value) if integer else float(value)
