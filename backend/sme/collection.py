"""Coleta de dados brutos. Não produz séries ou indicadores (Sprint 2)."""
import hashlib
import http.client
import ipaddress
import json
import math
import socket
import ssl
import unicodedata
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlencode
from django.db import transaction
from django.utils import timezone
from .models import FonteEpidemiologica, ExecucaoColeta, LoteColeta, RegistroAuditoria

MAX_BYTES = 5 * 1024 * 1024
HOST = "info.dengue.mat.br"
MUNICIPIOS_SP = json.loads(Path(__file__).with_name("municipios_sp.json").read_text(encoding="utf-8"))


class CollectionError(Exception):
    pass


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)).strip()


class InfoDengueAdapter:
    name = "infodengue"
    disease = "dengue"

    def validate(self, source):
        u = urlsplit(source.url)
        if u.scheme != "https" or u.netloc not in (HOST, HOST + ":443") or u.path != "/api/alertcity" or u.fragment:
            raise CollectionError("A coleta aceita somente a API HTTPS oficial do InfoDengue.")
        if source.tipo != "json" or source.recorte.tipo != "municipio" or source.recorte.codigo not in MUNICIPIOS_SP or source.recorte.uf != "SP" or normalized(source.recorte.nome) != normalized(MUNICIPIOS_SP.get(source.recorte.codigo, "")):
            raise CollectionError("Use JSON de dengue e um município válido de SP, com nome e código IBGE correspondentes.")
        params = parse_qs(u.query, keep_blank_values=True)
        required = {"geocode", "disease", "format", "ew_start", "ew_end", "ey_start", "ey_end"}
        if set(params) != required or any(len(v) != 1 for v in params.values()):
            raise CollectionError("Informe os sete parâmetros da API InfoDengue, sem parâmetros repetidos.")
        q = {k: v[0] for k, v in params.items()}
        if q["geocode"] != source.recorte.codigo or q["disease"] != "dengue" or q["format"] != "json":
            raise CollectionError("URL, município, formato e agravo devem corresponder à fonte cadastrada.")
        try:
            a, b, c, d = (int(q[k]) for k in ("ey_start", "ew_start", "ey_end", "ew_end"))
        except ValueError:
            raise CollectionError("Ano e semana epidemiológica devem ser números inteiros.")
        if not (2010 <= a <= c <= timezone.localdate().year and c - a <= 1 and 1 <= b <= 53 and 1 <= d <= 53 and (a, b) <= (c, d)):
            raise CollectionError("Período inválido: use até dois anos, semanas 1 a 53, sem anos futuros.")
        return q

    def fetch(self, source):
        q = self.validate(source)
        # Endereço de destino fixo, IP validado e conexão fixada nesse IP. Sem redirects.
        try:
            addresses = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise CollectionError("A fonte não resolveu para um endereço público permitido.")
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(HOST, timeout=20, context=context)
            sock = socket.create_connection((addresses[0][4][0], 443), timeout=20)
            try:
                conn.sock = context.wrap_socket(sock, server_hostname=HOST)
            except Exception:
                sock.close()
                raise
            try:
                conn.request("GET", "/api/alertcity?" + urlencode(q), headers={"Accept": "application/json", "User-Agent": "SME/1.0 public-health-pilot"})
                response = conn.getresponse()
                if response.status != 200:
                    raise CollectionError(f"InfoDengue respondeu HTTP {response.status}; nova tentativa no próximo ciclo.")
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise CollectionError("Resposta da fonte excedeu o limite de 5 MB.")
                data = json.loads(body)
            finally:
                conn.close()
        except CollectionError:
            raise
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise CollectionError("Não foi possível obter JSON válido do InfoDengue; nova tentativa no próximo ciclo.") from exc
        self.validate_payload(data, source, q)
        return data

    def validate_payload(self, data, source, q):
        if not isinstance(data, list) or len(data) > 106:
            raise CollectionError("Resposta inesperada: lista de até 106 semanas esperada.")
        seen = set()
        lower, upper = int(q["ey_start"]) * 100 + int(q["ew_start"]), int(q["ey_end"]) * 100 + int(q["ew_end"])
        for row in data:
            if not isinstance(row, dict) or not {"SE", "casos", "municipio_nome", "id"} <= row.keys():
                raise CollectionError("Resposta não corresponde ao contrato semanal do InfoDengue.")
            week = row["SE"]
            if not isinstance(week, int) or isinstance(week, bool) or not lower <= week <= upper or not 1 <= week % 100 <= 53 or week in seen:
                raise CollectionError("Semana repetida, inválida ou fora do período solicitado.")
            seen.add(week)
            if normalized(str(row["municipio_nome"])) != normalized(source.recorte.nome) or not str(row["id"]).startswith(source.recorte.codigo):
                raise CollectionError("A fonte retornou dados de outro município.")
            if row["casos"] is not None and (isinstance(row["casos"], bool) or not isinstance(row["casos"], (int, float)) or not math.isfinite(row["casos"]) or row["casos"] < 0):
                raise CollectionError("Contagem de casos inválida no conteúdo bruto.")


ADAPTERS = {"infodengue": InfoDengueAdapter()}


def collect_source(source_id, *, origin="manual", user=None):
    adapter = ADAPTERS["infodengue"]
    with transaction.atomic():
        source = FonteEpidemiologica.objects.select_for_update().select_related("recorte").get(pk=source_id)
        if not source.ativa:
            raise CollectionError("A fonte está desabilitada.")
        # Libera execuções interrompidas pelo desligamento do container.
        source.coletas.filter(status="executando", iniciada_em__lt=timezone.now() - timedelta(minutes=10)).update(status="erro", finalizada_em=timezone.now(), mensagem="Execução interrompida; liberada para nova tentativa.")
        if source.coletas.filter(status="executando").exists():
            raise CollectionError("Já existe uma coleta em execução para esta fonte.")
        run = ExecucaoColeta.objects.create(fonte=source, status="executando", origem=origin)
    try:
        data = adapter.fetch(source)
        digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()).hexdigest()
        with transaction.atomic():
            # Não persiste resultado de uma configuração modificada durante a coleta.
            current = FonteEpidemiologica.objects.select_for_update().get(pk=source.pk)
            if not current.ativa or current.atualizada_em != source.atualizada_em:
                raise CollectionError("A configuração da fonte mudou durante a coleta; resultado descartado.")
            lote, created = LoteColeta.objects.get_or_create(fonte=source, sha256=digest, defaults={"adaptador": adapter.name, "agravo": adapter.disease, "url_origem": source.url, "territorio_codigo": source.recorte.codigo, "dados_brutos": data, "quantidade_registros": len(data)})
            run.lote, run.repetida, run.quantidade_registros = lote, not created, len(data)
            run.status = "sucesso" if data else "vazia"
            run.mensagem = "Dados brutos coletados." if data else "A fonte não retornou registros; isso não significa zero casos."
            run.finalizada_em = timezone.now()
            run.save()
            current.ultima_coleta_em = run.finalizada_em
            current.save(update_fields=["ultima_coleta_em"])
            RegistroAuditoria.objects.create(usuario=user, acao="coleta_concluida", entidade="ExecucaoColeta", entidade_id=run.pk)
    except Exception as exc:
        run.status = "erro"
        run.mensagem = str(exc)[:300] if isinstance(exc, CollectionError) else "Falha interna durante a coleta."
        run.finalizada_em = timezone.now()
        run.save(update_fields=["status", "mensagem", "finalizada_em"])
    return run


def eligible_source_ids():
    adapter = ADAPTERS["infodengue"]
    ids = []
    for source in FonteEpidemiologica.objects.filter(ativa=True, recorte__uf="SP", recorte__tipo="municipio").select_related("recorte").order_by("pk"):
        try:
            adapter.validate(source)
        except CollectionError:
            continue
        ids.append(source.pk)
    return ids


def collect_pilot(*, origin="airflow"):
    runs = []
    for source_id in eligible_source_ids():
        try:
            runs.append(collect_source(source_id, origin=origin))
        except CollectionError:
            continue  # Fonte já em execução/desabilitada.
    return runs
