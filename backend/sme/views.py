import hashlib
import json
from datetime import timedelta
from functools import wraps
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .forms import FonteForm
from .models import FonteEpidemiologica, TentativaLogin
from .services import save_source


def error(message, status=400, **extra):
    return JsonResponse({"error": message, **extra}, status=status)


def csrf_failure(request, reason=""):
    return error("Sua sessão de segurança expirou. Atualize a página e tente novamente.", 403)


def authorized(admin=False):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated or not request.user.is_active:
                return error("Entre na sua conta para continuar.", 401)
            if admin and not request.user.is_staff:
                return error("Esta ação é restrita a administradores.", 403)
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
            "administrador": user.is_staff}


def source_data(source):
    return {"id": source.pk, "nome": source.nome, "tipo": source.tipo, "url": source.url,
            "ativa": source.ativa, "ultima_coleta_em": source.ultima_coleta_em,
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
    except ValueError as exc:
        return error(str(exc))
    if not isinstance(data.get("ativa"), bool):
        return error("Informe se a fonte está ativa usando true ou false.")
    if any(not isinstance(data.get(key, ""), str) for key in FonteForm.base_fields if key != "ativa"):
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
@authorized(admin=True)
def sources(request):
    if request.method == "POST":
        return persist_source(request)
    page = Paginator(FonteEpidemiologica.objects.select_related("recorte"), 20).get_page(request.GET.get("page", 1))
    return JsonResponse({"sources": [source_data(s) for s in page], "count": page.paginator.count,
                         "page": page.number, "pages": page.paginator.num_pages})


@require_http_methods(["PUT"])
@authorized(admin=True)
def source_detail(request, source_id):
    try:
        source = FonteEpidemiologica.objects.get(pk=source_id)
    except FonteEpidemiologica.DoesNotExist:
        return error("Fonte não encontrada.", 404)
    return persist_source(request, source)
