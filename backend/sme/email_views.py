"""Destinatários e acompanhamento SMTP exclusivos da administração."""
import logging
import smtplib
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .administration import lock_administration
from .email_alerts import MAX_DESTINATARIOS, alert_email_content, recipient_addresses, smtp_configured
from .models import AlertaSurto, ConfiguracaoEmail, DestinoEmail, EnvioAlertaEmail, GrupoEmail, RegistroAuditoria
from .views import authorized, error, payload

logger = logging.getLogger(__name__)


def normalize_email(value):
    if not isinstance(value, str) or len(value) > 254:
        raise ValueError('Informe endereços de e-mail válidos.')
    address = value.strip().lower()
    try:
        validate_email(address)
    except ValidationError as exc:
        raise ValueError('Informe endereços de e-mail válidos.') from exc
    return address


def normalize_list(values, limit=MAX_DESTINATARIOS):
    if not isinstance(values, list) or len(values) > limit:
        raise ValueError(f'Informe até {limit} endereços de e-mail.')
    addresses = [normalize_email(item) for item in values]
    if len(addresses) != len(set(addresses)):
        raise ValueError('Remova os endereços repetidos.')
    return addresses


def group_data(group):
    return {'id':group.pk, 'nome':group.nome, 'enderecos':group.enderecos}


def settings_data():
    config = ConfiguracaoEmail.objects.filter(pk=1).first()
    return {'habilitado':bool(config and config.habilitado), 'smtp_configurado':smtp_configured(),
            'grupos':[group_data(g) for g in GrupoEmail.objects.all()],
            'individuais':list(DestinoEmail.objects.filter(grupo__isnull=True).order_by('email').values_list('email', flat=True)),
            'grupos_selecionados':list(DestinoEmail.objects.filter(grupo__isnull=False).order_by('grupo_id').values_list('grupo_id', flat=True)),
            'destinatarios_resolvidos':len(recipient_addresses())}


def audit(actor, action, entity, pk, details):
    RegistroAuditoria.objects.create(usuario=actor, acao=action, entidade=entity, entidade_id=pk, detalhes=details)


@require_http_methods(['GET', 'PUT'])
@authorized(admin=True)
def email_settings(request):
    if request.method == 'GET':
        return JsonResponse(settings_data())
    try:
        data = payload(request)
        if set(data) != {'habilitado'} or type(data['habilitado']) is not bool:
            raise ValueError('Informe se o envio está habilitado.')
        with transaction.atomic():
            lock_administration(request)
            if data['habilitado'] and not smtp_configured():
                return error('Configure o SMTP no arquivo .env do servidor antes de habilitar o envio.', 409)
            if data['habilitado'] and not recipient_addresses():
                return error('Selecione ao menos um destinatário.', 409)
            config, _ = ConfiguracaoEmail.objects.select_for_update().get_or_create(pk=1)
            before = config.habilitado
            config.habilitado = data['habilitado']
            config.save(update_fields=['habilitado', 'atualizado_em'])
            if before != config.habilitado:
                audit(request.user, 'envio_email_configurado', 'ConfiguracaoEmail', config.pk,
                      {'habilitado':config.habilitado})
        return JsonResponse(settings_data())
    except ValueError as exc:
        return error(str(exc))
    except PermissionError as exc:
        return error(str(exc), 403)


@require_POST
@authorized(admin=True)
def test_email(request):
    try:
        if payload(request):
            raise ValueError('O teste é enviado somente para o e-mail da sua conta.')
    except ValueError as exc:
        return error(str(exc))
    if not smtp_configured():
        return error('Configure o SMTP no .env antes de testar.', 409)
    try:
        with transaction.atomic():
            lock_administration(request)
            recent = RegistroAuditoria.objects.filter(usuario=request.user,
                acao__in=['email_teste_solicitado', 'email_exemplo_solicitado'],
                criada_em__gte=timezone.now()-timedelta(minutes=15)).count()
            if recent >= 3:
                return error('Aguarde 15 minutos antes de solicitar outro teste.', 429)
            audit(request.user, 'email_teste_solicitado', 'Usuario', request.user.pk, {})
    except PermissionError as exc:
        return error(str(exc), 403)
    try:
        result = EmailMessage('[SME] Teste de envio',
            'Este e-mail confirma que o servidor SMTP está aceitando mensagens do SME.\n',
            settings.DEFAULT_FROM_EMAIL, [request.user.email]).send(fail_silently=False)
        if result != 1:
            raise RuntimeError('SMTP sem confirmação de entrega')
        return JsonResponse({'ok':True, 'destinatario':request.user.email})
    except Exception as exc:
        logger.warning('Teste de SMTP falhou: %s', type(exc).__name__)
        if isinstance(exc, smtplib.SMTPAuthenticationError):
            return error('Autenticação SMTP falhou. Confira o usuário e a senha no .env.', 502)
        return error('O SMTP não confirmou o envio. Confira as configurações e tente novamente.', 502)


@require_POST
@authorized(admin=True)
def example_alert_email(request):
    try:
        if payload(request):
            raise ValueError('O exemplo é enviado somente para o e-mail da sua conta.')
    except ValueError as exc:
        return error(str(exc))
    if not smtp_configured():
        return error('Configure o SMTP no .env antes de enviar um exemplo.', 409)
    alert = (AlertaSurto.objects.filter(ativa=True)
             .select_related('recorte', 'lote__fonte').first())
    if alert is None:
        return error('Ainda não há alertas registrados para usar como exemplo.', 409)
    try:
        with transaction.atomic():
            lock_administration(request)
            recent = RegistroAuditoria.objects.filter(usuario=request.user,
                acao__in=['email_teste_solicitado', 'email_exemplo_solicitado'],
                criada_em__gte=timezone.now()-timedelta(minutes=15)).count()
            if recent >= 3:
                return error('Aguarde 15 minutos antes de solicitar outro teste.', 429)
            audit(request.user, 'email_exemplo_solicitado', 'AlertaSurto', alert.pk, {})
    except PermissionError as exc:
        return error(str(exc), 403)
    subject, body = alert_email_content(alert, example=True)
    try:
        sent = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL,
                            [request.user.email]).send(fail_silently=False)
        if sent != 1:
            raise RuntimeError('SMTP sem confirmação de entrega')
        return JsonResponse({'ok': True, 'destinatario': request.user.email,
                             'alerta_id': alert.pk, 'assunto': subject})
    except Exception as exc:
        logger.warning('Exemplo de alerta por SMTP falhou: %s', type(exc).__name__)
        if isinstance(exc, smtplib.SMTPAuthenticationError):
            return error('Autenticação SMTP falhou. Confira o usuário e a senha no .env.', 502)
        return error('O SMTP não confirmou o envio. Confira as configurações e tente novamente.', 502)


@require_http_methods(['PUT'])
@authorized(admin=True)
def email_recipients(request):
    try:
        data = payload(request)
        if set(data) != {'individuais', 'grupos'}:
            raise ValueError('Informe endereços individuais e grupos selecionados.')
        individuals = normalize_list(data['individuais'])
        group_ids = data['grupos']
        if (not isinstance(group_ids, list) or len(group_ids) > 50 or
            any(type(pk) is not int or pk <= 0 for pk in group_ids) or len(group_ids) != len(set(group_ids))):
            raise ValueError('Selecione grupos válidos, sem repetição.')
        with transaction.atomic():
            lock_administration(request)
            groups = list(GrupoEmail.objects.filter(pk__in=group_ids))
            if len(groups) != len(group_ids):
                raise ValueError('Um dos grupos selecionados não existe.')
            resolved = set(individuals)
            for group in groups:
                resolved.update(group.enderecos)
            if len(resolved) > MAX_DESTINATARIOS:
                raise ValueError(f'Selecione até {MAX_DESTINATARIOS} endereços únicos.')
            if not resolved and ConfiguracaoEmail.objects.filter(pk=1, habilitado=True).exists():
                raise ValueError('Desative o envio antes de remover todos os destinatários.')
            before = recipient_addresses()
            DestinoEmail.objects.all().delete()
            DestinoEmail.objects.bulk_create(
                [DestinoEmail(email=address) for address in individuals] +
                [DestinoEmail(grupo=group) for group in groups])
            EnvioAlertaEmail.objects.filter(status='pendente').exclude(destinatario__in=resolved).update(
                status='cancelado', erro='Destinatário removido.', atualizado_em=timezone.now())
            audit(request.user, 'destinatarios_email_editados', 'DestinoEmail', 0,
                  {'antes':before, 'depois':sorted(resolved)})
        return JsonResponse(settings_data())
    except ValueError as exc:
        return error(str(exc))
    except PermissionError as exc:
        return error(str(exc), 403)


def save_group(request, group_id=None):
    try:
        data = payload(request)
        if set(data) != {'nome', 'enderecos'}:
            raise ValueError('Informe o nome e os endereços do grupo.')
        name = data['nome']
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            raise ValueError('Informe um nome de grupo com até 100 caracteres.')
        addresses = normalize_list(data['enderecos'], limit=100)
        if not addresses:
            raise ValueError('Inclua ao menos um endereço no grupo.')
        with transaction.atomic():
            lock_administration(request)
            group = GrupoEmail.objects.get(pk=group_id) if group_id else GrupoEmail()
            before = group_data(group) if group.pk else None
            group.nome, group.enderecos = name.strip(), addresses
            group.full_clean()
            group.save()
            if DestinoEmail.objects.filter(grupo=group).exists() and len(recipient_addresses()) > MAX_DESTINATARIOS:
                raise ValueError(f'O grupo selecionado excederia {MAX_DESTINATARIOS} destinatários únicos.')
            if DestinoEmail.objects.filter(grupo=group).exists():
                EnvioAlertaEmail.objects.filter(status='pendente').exclude(
                    destinatario__in=recipient_addresses()).update(
                    status='cancelado', erro='Destinatário removido.', atualizado_em=timezone.now())
            audit(request.user, 'grupo_email_editado' if group_id else 'grupo_email_criado',
                  'GrupoEmail', group.pk, {'antes':before, 'depois':group_data(group)})
        return JsonResponse({'grupo':group_data(group)}, status=200 if group_id else 201)
    except (ValueError, ValidationError) as exc:
        return error(' '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    except PermissionError as exc:
        return error(str(exc), 403)
    except GrupoEmail.DoesNotExist:
        return error('Grupo não encontrado.', 404)
    except IntegrityError:
        return error('Já existe um grupo com esse nome.', 409)


@require_POST
@authorized(admin=True)
def email_groups(request):
    return save_group(request)


@require_http_methods(['PUT', 'DELETE'])
@authorized(admin=True)
def email_group_detail(request, group_id):
    if request.method == 'PUT':
        return save_group(request, group_id)
    try:
        with transaction.atomic():
            lock_administration(request)
            group = GrupoEmail.objects.get(pk=group_id)
            if DestinoEmail.objects.filter(grupo=group).exists():
                return error('Remova este grupo dos destinatários antes de excluí-lo.', 409)
            before = group_data(group)
            group.delete()
            audit(request.user, 'grupo_email_excluido', 'GrupoEmail', group_id, {'antes':before})
        return JsonResponse({'ok':True})
    except PermissionError as exc:
        return error(str(exc), 403)
    except GrupoEmail.DoesNotExist:
        return error('Grupo não encontrado.', 404)


@require_GET
@authorized(admin=True)
def email_deliveries(request):
    rows = EnvioAlertaEmail.objects.order_by('-pk')[:30]
    return JsonResponse({'envios':[{'id':row.pk, 'destinatario':row.destinatario,
        'assunto':row.assunto, 'status':row.status, 'tentativas':row.tentativas,
        'erro':row.erro, 'criado_em':row.criado_em, 'enviado_em':row.enviado_em,
        'proxima_tentativa_em':row.proxima_tentativa_em} for row in rows]})


@require_POST
@authorized(admin=True)
def retry_email(request, delivery_id):
    try:
        with transaction.atomic():
            lock_administration(request)
            row = EnvioAlertaEmail.objects.select_for_update().select_related('alerta').get(pk=delivery_id)
            if row.status != 'erro':
                return error('Só é possível tentar novamente um envio que falhou.', 409)
            if not row.alerta.ativa or row.alerta.revisao != row.revisao:
                return error('Este alerta já foi encerrado ou substituído.', 409)
            if not smtp_configured():
                return error('SMTP não configurado.', 409)
            row.status, row.tentativas, row.erro, row.proxima_tentativa_em = 'pendente', 0, '', timezone.now()
            row.save(update_fields=['status', 'tentativas', 'erro', 'proxima_tentativa_em', 'atualizado_em'])
            audit(request.user, 'envio_email_retentado', 'EnvioAlertaEmail', row.pk, {})
        return JsonResponse({'ok':True})
    except PermissionError as exc:
        return error(str(exc), 403)
    except EnvioAlertaEmail.DoesNotExist:
        return error('Envio não encontrado.', 404)
