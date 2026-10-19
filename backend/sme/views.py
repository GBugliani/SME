import hashlib
import secrets
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .collection import eligible_source_ids, collect_source, collect_pilot, CollectionError
from .collection_period import collection_source
from .models import ExecucaoColeta
import json
from datetime import timedelta
from functools import wraps
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import OuterRef, Subquery, Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .forms import FonteForm
from .models import FonteEpidemiologica, TentativaLogin, Usuario, RegistroAuditoria
from .services import save_source
from .access import can, permissions_for, profile_name


def error(message, status=400, **extra):
    return JsonResponse({"error": message, **extra}, status=status)


def csrf_failure(request, reason=""):
    return error("Sua sessão de segurança expirou. Atualize a página e tente novamente.", 403)


def authorized(admin=False, permission=None):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated or not request.user.is_active:
                return error("Entre na sua conta para continuar.", 401)
            if admin and not request.user.is_staff:
                return error("Esta ação é restrita a administradores.", 403)
            if permission and not can(request.user, permission):
                return error("Seu perfil não permite esta ação.", 403)
            return view(request, *args, **kwargs)
        return never_cache(wrapped)
    return decorator


def payload(request):
    if request.content_type != "application/json":
        raise ValueError("Envie os dados no formato JSON.")
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("O conteúdo JSON é inválido.")
    if not isinstance(data, dict):
        raise ValueError("Envie um objeto JSON.")
    return data


def user_data(user):
    return {"id": user.pk, "email": user.email, "nome": user.get_full_name() or user.email,
            "administrador": user.is_staff, "perfil": profile_name(user),
            "perfil_id": user.perfil_id, "ativo": user.is_active, "permissoes": permissions_for(user)}


def source_data(source):
    effective_url = source.url
    try:
        from .collection import get_adapter
        effective = collection_source(source)
        get_adapter(effective).validate(effective)
        effective_url = effective.url
        available = source.ativa and source.arquivada_em is None
    except CollectionError:
        available = False
    from .datasets import DATASETS, source_dataset
    spec = DATASETS.get(source_dataset(source))
    latest = source.coletas.first()
    from .models import ProcessamentoLote
    processing = ProcessamentoLote.objects.filter(lote__fonte=source).order_by("-lote__criada_em", "-pk").first()
    return {"indicador": source_dataset(source), "integracao":spec, "id": source.pk, "nome": source.nome, "tipo": source.tipo, "url": source.url,
            "ativa": source.ativa, "arquivada_em": source.arquivada_em, "periodo_movel":source.periodo_movel, "url_coleta":effective_url, "ultima_coleta_em": source.ultima_coleta_em,
            "processamento": {"status":processing.status,"mensagem":processing.mensagem,"registros":processing.quantidade_registros} if processing else None,
            "coleta_disponivel": available, "ultima_execucao": run_data(latest),
            "recorte_tipo": source.recorte.tipo, "recorte_nome": source.recorte.nome,
            "recorte_codigo": source.recorte.codigo, "recorte_uf": source.recorte.uf}


@require_GET
@never_cache
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return error("Banco indisponível.", 503)
    return JsonResponse({"status": "ok"})


@require_GET
@never_cache
def csrf(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
@never_cache
def sign_in(request):
    try:
        data = payload(request)
    except ValueError as exc:
        return error(str(exc))
    email, password = data.get("email"), data.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password or len(email) > 254 or len(password) > 1024:
        return error("Informe e-mail e senha válidos.")
    email = email.strip().lower()
    key = hashlib.sha256(email.encode()).hexdigest()
    with transaction.atomic():
        attempt, _ = TentativaLogin.objects.get_or_create(chave=key, defaults={"inicio": timezone.now()})
        attempt = TentativaLogin.objects.select_for_update().get(pk=attempt.pk)
        if timezone.now() - attempt.inicio >= timedelta(minutes=15):
            attempt.falhas, attempt.inicio = 0, timezone.now()
        if attempt.falhas >= 5:
            response = error("Muitas tentativas. Tente novamente em 15 minutos.", 429)
            response["Retry-After"] = "900"
            return response
        user = authenticate(request, email=email, password=password)
        if user is None:
            attempt.falhas += 1
            attempt.save()
            return error("E-mail ou senha inválidos.", 401)
        attempt.falhas = 0
        attempt.inicio = timezone.now()
        attempt.save()
    login(request, user)
    return JsonResponse({"user": user_data(user), "csrfToken": get_token(request)})


@require_POST
@authorized()
def sign_out(request):
    logout(request)
    return JsonResponse({"ok": True})


@require_GET
@authorized()
def me(request):
    return JsonResponse({"user": user_data(request.user)})


def persist_source(request, instance=None):
    try:
        data = payload(request)
        from .source_setup import prepare_source
        data = prepare_source(data)
    except ValueError as exc:
        return error(str(exc))
    if not isinstance(data.get("ativa"), bool):
        return error("Informe se a fonte está ativa usando true ou false.")
    if type(data.get('periodo_movel', False)) is not bool:
        return error('Informe o período móvel usando true ou false.')
    if any(not isinstance(data.get(key, ""), str) for key in FonteForm.base_fields if key not in ("ativa", "periodo_movel")):
        return error("Os campos da fonte devem ser textos.")
    form = FonteForm(data)
    if not form.is_valid():
        return error("Revise os campos indicados.", fields={k: list(v) for k, v in form.errors.items()})
    try:
        source = save_source(data=form.cleaned_data, user=request.user, instance=instance)
    except ValidationError as exc:
        return error("Não foi possível salvar a fonte.", fields=exc.message_dict)
    except IntegrityError:
        return error("Já existe uma fonte com essa URL e esse recorte.", 409)
    return JsonResponse({"source": source_data(source)}, status=200 if instance else 201)


@require_http_methods(["GET", "POST"])
@authorized()
def sources(request):
    if request.method == "POST":
        if not can(request.user, "gerenciar_fontes"):
            return error("Esta ação é restrita a administradores.", 403)
        return persist_source(request)
    from .models import ProcessamentoLote
    latest_processing = ProcessamentoLote.objects.filter(lote__fonte=OuterRef("pk")).order_by("-lote__criada_em", "-pk").values("status")[:1]
    archived_param = request.GET.get("arquivadas", "0")
    if archived_param not in ("0", "1"):
        return error("Filtro de fontes arquivadas inválido.")
    archived = archived_param == "1"
    if archived and not can(request.user, "gerenciar_fontes"):
        return error("Esta ação requer permissão para gerenciar fontes.", 403)
    visible = FonteEpidemiologica.objects.filter(arquivada_em__isnull=True)
    processing_failures = visible.annotate(process_status=Subquery(latest_processing)).filter(process_status="erro").count()
    queryset = FonteEpidemiologica.objects.select_related("recorte").filter(arquivada_em__isnull=not archived)
    for term in request.GET.get("q", "").strip()[:200].split():
        queryset = queryset.filter(Q(nome__icontains=term) | Q(recorte__nome__icontains=term)
                                   | Q(recorte__codigo__icontains=term) | Q(recorte__uf__icontains=term)
                                   | Q(url__icontains=term) | Q(indicador__icontains=term))
    page = Paginator(queryset, 20).get_page(request.GET.get("page", 1))
    return JsonResponse({"sources": [source_data(s) for s in page], "arquivadas": archived,
                         "count": page.paginator.count,
                         "page": page.number, "pages": page.paginator.num_pages,
                         "coleta_realizada": visible.filter(ultima_coleta_em__isnull=False).exists(),
                         "falhas_processamento": processing_failures})


@require_http_methods(["PUT"])
@authorized(permission="gerenciar_fontes")
def source_detail(request, source_id):
    try:
        source = FonteEpidemiologica.objects.get(pk=source_id)
    except FonteEpidemiologica.DoesNotExist:
        return error("Fonte não encontrada.", 404)
    if source.arquivada_em is not None:
        return error("Restaure a fonte antes de editá-la.", 409)
    return persist_source(request, source)


@require_http_methods(["PUT"])
@authorized(permission="gerenciar_fontes")
def source_archive(request, source_id):
    try:
        data = payload(request)
    except ValueError as exc:
        return error(str(exc))
    if set(data) != {"arquivar"} or type(data["arquivar"]) is not bool:
        return error("Informe arquivar como true ou false.")
    try:
        with transaction.atomic():
            source = FonteEpidemiologica.objects.select_for_update().get(pk=source_id)
            if (source.arquivada_em is not None) != data["arquivar"]:
                if data["arquivar"]:
                    source.arquivada_em = timezone.now()
                    source.ativa = False
                    action = "fonte_arquivada"
                else:
                    source.arquivada_em = None
                    action = "fonte_restaurada"
                source.save(update_fields=["arquivada_em", "ativa", "atualizada_em"])
                RegistroAuditoria.objects.create(usuario=request.user, acao=action,
                    entidade="FonteEpidemiologica", entidade_id=source.pk)
    except FonteEpidemiologica.DoesNotExist:
        return error("Fonte não encontrada.", 404)
    return JsonResponse({"source": source_data(source)})


def run_data(run):
    if run is None:
        return None
    return {"id": run.pk, "status": run.status, "iniciada_em": run.iniciada_em,
            "finalizada_em": run.finalizada_em, "mensagem": run.mensagem,
            "quantidade_registros": run.quantidade_registros, "repetida": run.repetida,
            "origem": run.origem}


@require_http_methods(["GET", "POST"])
@authorized()
def source_collection(request, source_id):
    if request.method == "POST" and not can(request.user, "coletar_dados"):
        return error("Esta ação é restrita a administradores.", 403)
    try:
        source = FonteEpidemiologica.objects.get(pk=source_id)
    except FonteEpidemiologica.DoesNotExist:
        return error("Fonte não encontrada.", 404)
    if request.method == "GET":
        return JsonResponse({"execucoes": [run_data(r) for r in source.coletas.all()[:10]]})
    try:
        run = collect_source(source.pk, user=request.user)
    except CollectionError as exc:
        return error(str(exc), 409)
    if run.status == "erro":
        return error(run.mensagem, 502, execucao=run_data(run))
    return JsonResponse({"execucao": run_data(run)})


@csrf_exempt
@require_POST
def scheduled_collection(request):
    # Credencial separada para chamada interna do Airflow; nenhuma sessão de usuário.
    token = settings.COLLECTION_TOKEN
    supplied = request.headers.get("X-Coleta-Token", "")
    if not token or not secrets.compare_digest(token, supplied):
        return error("Credencial de coleta inválida.", 403)
    try:
        body = json.loads(request.body or b"{}")
        if not isinstance(body, dict):
            return error("Requisição inválida.", 400)
    except ValueError:
        return error("JSON inválido.", 400)
    if body.get("action") == "list":
        return JsonResponse({"fontes": eligible_source_ids()})
    if "fonte_id" in body:
        source_id = body["fonte_id"]
        if type(source_id) is not int or source_id not in eligible_source_ids():
            return error("Fonte não habilitada para coleta.", 400)
        try:
            runs = [collect_source(source_id, origin="airflow")]
        except CollectionError as exc:
            return error(str(exc), 409)
    else:
        runs = collect_pilot()
    return JsonResponse({"execucoes": [run_data(r) for r in runs]}, status=502 if any(r.status == "erro" for r in runs) else 200)


@require_GET
@authorized()
def indicator_options(request):
    from .indicators import options
    return JsonResponse(options())


@require_GET
@authorized(permission="gerenciar_fontes")
def source_catalog(request):
    from .collection import MUNICIPIOS_SP
    from .datasets import DATASETS
    return JsonResponse({'municipios':[{'codigo':c,'nome':n} for c,n in sorted(MUNICIPIOS_SP.items(),key=lambda x:x[1])], 'ano_atual':timezone.localdate().year, 'integracoes':list(DATASETS.values())})


@require_GET
@authorized()
def indicators(request):
    from .indicators import query_indicators
    try:
        return JsonResponse(query_indicators(request.GET))
    except ValueError as exc:
        return error(str(exc), 400)
