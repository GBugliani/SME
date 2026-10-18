"""Coleta por contrato de integração, com origem imutável e processamento separado."""
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
from .datasets import DATASETS, source_dataset
from .models import FonteEpidemiologica, ExecucaoColeta, LoteColeta, RegistroAuditoria

MAX_BYTES = 5 * 1024 * 1024
HOST = "info.dengue.mat.br"
MUNICIPIOS_SP = json.loads(Path(__file__).with_name("municipios_sp.json").read_text(encoding="utf-8"))


class CollectionError(Exception):
    pass


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)).strip()


def fetch_public(host, path, *, limit=MAX_BYTES):
    """Destino permitido pelo adaptador; DNS público, IP fixado, TLS e sem redirects."""
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise CollectionError("A fonte não resolveu para um endereço público permitido.")
        context = ssl.create_default_context()
        conn = http.client.HTTPSConnection(host, timeout=25, context=context)
        sock = socket.create_connection((addresses[0][4][0], 443), timeout=25)
        try:
            conn.sock = context.wrap_socket(sock, server_hostname=host)
            conn.request("GET", path, headers={"Accept": "application/json,text/csv", "User-Agent": "SME/2.0 public-health"})
            response = conn.getresponse()
            if response.status != 200:
                raise CollectionError(f"A fonte respondeu HTTP {response.status}; nova tentativa no próximo ciclo.")
            body = response.read(limit + 1)
            if len(body) > limit:
                raise CollectionError("Resposta da fonte excedeu o limite permitido.")
            metadata = {}
            for key in ('ETag', 'Last-Modified', 'Content-Type'):
                value = response.getheader(key)
                if isinstance(value, str): metadata[key] = value
            return body, metadata
        finally:
            conn.close()
            sock.close()
    except CollectionError:
        raise
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise CollectionError("Não foi possível acessar a fonte; nova tentativa no próximo ciclo.") from exc


class InfoDengueAdapter:
    name = "infodengue"
    disease = "dengue"

    def __init__(self, disease="dengue"):
        self.disease = disease
        self.dataset = f'infodengue_{disease}'


    def validate(self, source):
        u = urlsplit(source.url)
        if u.scheme != "https" or u.netloc not in (HOST, HOST + ":443") or u.path != "/api/alertcity" or u.fragment:
            raise CollectionError("A coleta aceita somente a API HTTPS oficial do InfoDengue.")
        if source.tipo != "json" or source.recorte.tipo != "municipio" or source.recorte.codigo not in MUNICIPIOS_SP or source.recorte.uf != "SP" or normalized(source.recorte.nome) != normalized(MUNICIPIOS_SP.get(source.recorte.codigo, "")):
            raise CollectionError("Use JSON de um agravo suportado e um município válido de SP, com nome e código IBGE correspondentes.")
        params = parse_qs(u.query, keep_blank_values=True)
        required = {"geocode", "disease", "format", "ew_start", "ew_end", "ey_start", "ey_end"}
        if set(params) != required or any(len(v) != 1 for v in params.values()):
            raise CollectionError("Informe os sete parâmetros da API InfoDengue, sem parâmetros repetidos.")
        q = {k: v[0] for k, v in params.items()}
        if q["geocode"] != source.recorte.codigo or q["disease"] != self.disease or q["format"] != "json":
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
        self.raw_body, self.http_metadata = fetch_public(HOST, "/api/alertcity?" + urlencode(q))
        try:
            data = json.loads(self.raw_body)
        except (ValueError, UnicodeError) as exc:
            raise CollectionError("Não foi possível obter JSON válido do InfoDengue.") from exc
        self.validate_payload(data, source, q)
        return data

    def normalize(self, data, source):
        from .processing import normalize_infodengue
        q = self.validate(source)
        self.validate_payload(data, source, q)
        return normalize_infodengue(data)

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


def get_adapter(source):
    key = source_dataset(source)
    spec = DATASETS.get(key)
    if not spec:
        raise CollectionError("Esta fonte não possui integração habilitada. Selecione um provedor no cadastro assistido.")
    from .infogripe import InfoGripeAdapter
    from .sivep import SivepAdapter
    registry = {'infodengue':InfoDengueAdapter, 'infogripe':InfoGripeAdapter, 'sivep':SivepAdapter}
    factory = registry.get(spec['provedor'])
    if factory is None:
        raise CollectionError('Adaptador não instalado para este provedor.')
    return factory(spec['agravo'])


# Alias conservado para integrações internas antigas; novas chamadas usam get_adapter.
ADAPTERS = {"infodengue": InfoDengueAdapter()}


def collect_source(source_id, *, origin="manual", user=None):
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
        from .collection_period import collection_source
        effective = collection_source(source)
        adapter = get_adapter(effective)
        adapter.validate(effective)
        data = adapter.fetch(effective)
        digest = hashlib.sha256(json.dumps({"indicador":adapter.dataset,"territorio":source.recorte.codigo,
            **({'url':effective.url} if source.periodo_movel else {}),
            "arquivo":hashlib.sha256(adapter.raw_body).hexdigest() if getattr(adapter,"raw_body",None) is not None else None,"dados":data}, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()).hexdigest()
        with transaction.atomic():
            # Não persiste resultado de uma configuração modificada durante a coleta.
            current = FonteEpidemiologica.objects.select_for_update().get(pk=source.pk)
            if not current.ativa or current.atualizada_em != source.atualizada_em:
                raise CollectionError("A configuração da fonte mudou durante a coleta; resultado descartado.")
            if adapter.name == 'sivep':
                # Uma versão A pode reaparecer após B. Ela é uma revisão nova,
                # não um reprocessamento do lote antigo que seria ignorado.
                latest = source.lotes.defer('conteudo_original').order_by('-pk').first()
                raw_hash = hashlib.sha256(adapter.raw_body).hexdigest()
                if latest and latest.url_origem == effective.url and latest.sha256_original == raw_hash and latest.dados_brutos == data:
                    digest = latest.sha256
                elif source.lotes.filter(sha256=digest).exists():
                    digest = hashlib.sha256(f'{digest}:{run.pk}'.encode()).hexdigest()
            lote, created = LoteColeta.objects.get_or_create(fonte=source, sha256=digest, defaults={"adaptador": adapter.name, "agravo": adapter.disease, "url_origem": effective.url, "territorio_codigo": source.recorte.codigo, "dados_brutos": data, "quantidade_registros": len(data),
                "indicador": adapter.dataset, "proveniencia": {**DATASETS[adapter.dataset],
                    'http': getattr(adapter, 'http_metadata', {}), 'url':effective.url, 'periodo_movel':source.periodo_movel,
                    'territorio':source.recorte.codigo, 'nome_fonte':source.nome,
                    **getattr(adapter, 'provenance_extra', {})},
                "arquivo_original": getattr(adapter, 'arquivo_original', None),
                "conteudo_original": None if getattr(adapter, 'arquivo_original', None) else getattr(adapter, 'raw_body', None),
                "sha256_original": hashlib.sha256(adapter.raw_body).hexdigest() if getattr(adapter, 'raw_body', None) is not None else ''})
            run.lote, run.repetida, run.quantidade_registros = lote, not created, len(data)
            has_data = bool(data) and (adapter.name != 'sivep' or any(row['casos'] is not None for row in data))
            run.status = "sucesso" if has_data else "vazia"
            run.mensagem = "Dados brutos coletados." if has_data else "A fonte não retornou contagens para este município; isso não significa zero casos."
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
    if run.status in ("sucesso", "vazia"):
        from .processing import process_lote
        result = process_lote(run.lote_id)
        if result.status == 'erro':
            run.status = 'erro'
            run.mensagem = 'Dados brutos preservados; processamento falhou: ' + result.mensagem
            run.mensagem = run.mensagem[:300]
            run.save(update_fields=['status', 'mensagem'])
    return run


def eligible_source_ids():
    ids = []
    for source in FonteEpidemiologica.objects.filter(ativa=True).select_related("recorte").order_by("pk"):
        try:
            from .collection_period import collection_source
            effective = collection_source(source)
            get_adapter(effective).validate(effective)
        except CollectionError:
            continue
        ids.append(source.pk)
    return ids


def collect_all(*, origin="airflow"):
    runs = []
    for source_id in eligible_source_ids():
        try:
            runs.append(collect_source(source_id, origin=origin))
        except CollectionError:
            continue  # Fonte já em execução/desabilitada.
    return runs


# Compatibilidade com comandos e chamadas da primeira entrega.
collect_pilot = collect_all
