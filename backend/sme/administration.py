"""Gestão administrativa de contas e perfis; não exclui histórico nem registra senhas."""
import hashlib
from datetime import timedelta
from django.contrib.auth import logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .access import PERMISSIONS
from .models import PerfilAcesso, Usuario, RegistroAuditoria, TentativaLogin
from .views import authorized, error, payload, user_data


def profile_data(profile):
    return {'id': profile.pk, 'nome': profile.nome, 'permissoes': profile.permissoes,
            'sistema': bool(profile.codigo), 'administrador': profile.codigo == 'administrador'}


def text_field(data, key, limit):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f'Informe {key} válido, com até {limit} caracteres.')
    return value.strip()


def audit(actor, action, entity, pk, before, after):
    RegistroAuditoria.objects.create(usuario=actor, acao=action, entidade=entity,
                                    entidade_id=pk, detalhes={'antes': before, 'depois': after})


def lock_administration(request):
    # Uma mesma linha serializa edições de administradores, perfis e atribuições.
    # Revalida o ator depois do lock, inclusive caso outra sessão o tenha desativado.
    PerfilAcesso.objects.select_for_update().get(codigo='administrador')
    if not Usuario.objects.filter(pk=request.user.pk, is_active=True, is_staff=True).exists():
        raise PermissionError('Seu acesso administrativo foi removido. Entre novamente.')


@require_http_methods(['GET', 'POST'])
@authorized(admin=True)
def users(request):
    if request.method == 'POST':
        return save_user(request)
    queryset = Usuario.objects.select_related('perfil').order_by('email', 'pk')
    for term in request.GET.get('q', '')[:200].split():
        queryset = queryset.filter(Q(email__icontains=term) | Q(first_name__icontains=term) | Q(last_name__icontains=term))
    page = Paginator(queryset, 20).get_page(request.GET.get('page', 1))
    return JsonResponse({'usuarios': [user_data(u) for u in page], 'count': page.paginator.count,
                         'page': page.number, 'pages': page.paginator.num_pages})


@require_http_methods(['PUT'])
@authorized(admin=True)
def user_detail(request, user_id):
    return save_user(request, user_id)


def save_user(request, user_id=None):
    try:
        data = payload(request)
        if set(data) - {'nome', 'email', 'ativo', 'perfil_id', 'password', 'password_confirmation'}:
            raise ValueError('Campos de usuário não reconhecidos.')
        name = text_field(data, 'nome', 150)
        email = text_field(data, 'email', 254).lower()
        validate_email(email)
        if type(data.get('ativo')) is not bool or type(data.get('perfil_id')) is not int:
            raise ValueError('Informe um perfil e a situação da conta.')
        with transaction.atomic():
            lock_administration(request)
            profile = PerfilAcesso.objects.get(pk=data['perfil_id'])
            user = Usuario.objects.select_for_update().get(pk=user_id) if user_id else Usuario()
            before = user_data(user) if user.pk else None
            if user.is_superuser and not request.user.is_superuser:
                raise PermissionError('Somente um superusuário pode editar esta conta.')
            admin = profile.codigo == 'administrador'
            if user.pk == request.user.pk and (not admin or not data['ativo']):
                raise ValueError('Você não pode desativar sua própria conta ou remover seu acesso administrativo.')
            if user.is_staff and user.is_active and (not admin or not data['ativo']):
                if not Usuario.objects.filter(is_staff=True, is_active=True).exclude(pk=user.pk).exists():
                    raise ValueError('Mantenha pelo menos um administrador ativo.')
            if user.is_superuser and not admin:
                raise ValueError('Uma conta de superusuário deve manter o perfil Administrador.')
            user.first_name, user.last_name, user.email = name, '', email
            user.is_staff, user.is_active, user.perfil = admin, data['ativo'], profile
            if user_id:
                if 'password' in data or 'password_confirmation' in data:
                    raise ValueError('Use a ação Redefinir senha na administração.')
            else:
                password = data.get('password')
                if not isinstance(password, str) or not password or len(password) > 1024:
                    raise ValueError('Informe uma senha válida.')
                if password != data.get('password_confirmation'):
                    raise ValueError('As senhas não coincidem.')
                validate_password(password, user)
                user.set_password(password)
            user.full_clean()
            user.save()
            if before and before['ativo'] and not user.is_active:
                # Reativar a conta no futuro não deve reativar cookies antigos.
                for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
                    if session.get_decoded().get('_auth_user_id') == str(user.pk):
                        session.delete()
            audit(request.user, 'usuario_editado' if user_id else 'usuario_criado', 'Usuario', user.pk, before, user_data(user))
            return JsonResponse({'user': user_data(user)}, status=200 if user_id else 201)
    except (ValueError, ValidationError) as exc:
        return error(' '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    except PermissionError as exc:
        return error(str(exc), 403)
    except (Usuario.DoesNotExist, PerfilAcesso.DoesNotExist):
        return error('Usuário ou perfil não encontrado.', 404)
    except IntegrityError:
        return error('Já existe uma conta com este e-mail.', 409)


@require_POST
@authorized(admin=True)
def reset_password(request, user_id):
    try:
        data = payload(request)
        password, confirmation, admin_password = (data.get(k) for k in ('password', 'password_confirmation', 'admin_password'))
        if any(not isinstance(v, str) or not v or len(v) > 1024 for v in (password, confirmation, admin_password)):
            raise ValueError('Informe a nova senha, a confirmação e sua senha de administrador.')
        with transaction.atomic():
            lock_administration(request)
            actor = Usuario.objects.get(pk=request.user.pk)
            key = hashlib.sha256(f'admin-password-reset:{actor.pk}'.encode()).hexdigest()
            attempt, _ = TentativaLogin.objects.get_or_create(chave=key, defaults={'inicio': timezone.now()})
            if timezone.now() - attempt.inicio >= timedelta(minutes=15):
                attempt.falhas, attempt.inicio = 0, timezone.now()
            if attempt.falhas >= 5:
                return error('Muitas tentativas. Tente novamente em 15 minutos.', 429)
            if not actor.check_password(admin_password):
                attempt.falhas += 1
                attempt.save()
                return error('Sua senha de administrador é inválida.')
            user = Usuario.objects.select_for_update().get(pk=user_id)
            if user.is_superuser and not actor.is_superuser:
                raise PermissionError('Somente um superusuário pode editar esta conta.')
            if password != confirmation:
                raise ValueError('As senhas não coincidem.')
            validate_password(password, user)
            user.set_password(password)
            user.save(update_fields=['password'])
            for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
                if session.get_decoded().get('_auth_user_id') == str(user.pk):
                    session.delete()
            attempt.falhas = 0
            attempt.save()
            RegistroAuditoria.objects.create(usuario=actor, acao='senha_redefinida', entidade='Usuario', entidade_id=user.pk)
        own_account = user.pk == actor.pk
        if own_account:
            logout(request)
        return JsonResponse({'ok': True, 'login_required': own_account})
    except (ValueError, ValidationError) as exc:
        return error(' '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    except PermissionError as exc:
        return error(str(exc), 403)
    except Usuario.DoesNotExist:
        return error('Usuário não encontrado.', 404)


@require_http_methods(['GET', 'POST'])
@authorized(admin=True)
def profiles(request):
    if request.method == 'POST':
        return save_profile(request)
    return JsonResponse({'perfis': [profile_data(p) for p in PerfilAcesso.objects.all()],
                         'permissoes': PERMISSIONS})


@require_http_methods(['PUT'])
@authorized(admin=True)
def profile_detail(request, profile_id):
    return save_profile(request, profile_id)


def save_profile(request, profile_id=None):
    try:
        data = payload(request)
        if set(data) - {'nome', 'permissoes'}:
            raise ValueError('Campos de perfil não reconhecidos.')
        name = text_field(data, 'nome', 80)
        permissions = data.get('permissoes')
        if not isinstance(permissions, list) or any(not isinstance(p, str) or p not in PERMISSIONS for p in permissions):
            raise ValueError('Selecione somente permissões disponíveis.')
        with transaction.atomic():
            lock_administration(request)
            profile = PerfilAcesso.objects.get(pk=profile_id) if profile_id else PerfilAcesso()
            if profile.codigo:
                raise ValueError('Os perfis padrão são fixos. Crie um perfil personalizado.')
            before = profile_data(profile) if profile.pk else None
            profile.nome, profile.permissoes = name, sorted(set(permissions))
            profile.full_clean(exclude=['codigo'])
            profile.save()
            audit(request.user, 'perfil_editado' if profile_id else 'perfil_criado', 'PerfilAcesso', profile.pk, before, profile_data(profile))
            return JsonResponse({'perfil': profile_data(profile)}, status=200 if profile_id else 201)
    except (ValueError, ValidationError) as exc:
        return error(' '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    except PermissionError as exc:
        return error(str(exc), 403)
    except PerfilAcesso.DoesNotExist:
        return error('Perfil não encontrado.', 404)
    except IntegrityError:
        return error('Já existe um perfil com esse nome.', 409)


@require_GET
@authorized(admin=True)
def audit_log(request):
    page = Paginator(RegistroAuditoria.objects.select_related('usuario').order_by('-pk'), 20).get_page(request.GET.get('page', 1))
    return JsonResponse({'registros': [{'id': r.pk, 'usuario': r.usuario.email if r.usuario else 'Sistema',
        'acao': r.acao, 'entidade': r.entidade, 'entidade_id': r.entidade_id,
        'criada_em': r.criada_em, 'detalhes': r.detalhes} for r in page],
        'page': page.number, 'pages': page.paginator.num_pages, 'count': page.paginator.count})
