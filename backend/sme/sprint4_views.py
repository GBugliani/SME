"""Configurações administrativas, leitura de alertas e comparação territorial."""
from datetime import date
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max, OuterRef, Subquery, Q, F
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .administration import lock_administration
from .alert_presentation import alert_message
from .datasets import DATASETS
from .detection import configuration_for, configuration_data, job_data
from .detectors import METHODS, validate_parameters
from .indicators import query_indicators, REGIONS
from .models import ConfiguracaoDeteccao, ReanaliseDeteccao, RegistroAuditoria, AlertaSurto, LeituraAlerta
from .views import authorized, payload, error


@require_http_methods(['GET', 'POST'])
@authorized(admin=True)
def configurations(request):
    if request.method == 'GET':
        return JsonResponse({'metodos':METHODS, 'integracoes':list(DATASETS.values()),
            'ativas':[configuration_data(c) for c in ConfiguracaoDeteccao.objects.filter(ativa=True)],
            'configuracoes':[configuration_data(c) for c in ConfiguracaoDeteccao.objects.order_by('-pk')[:100]],
            'reanalises':[job_data(j) for j in ReanaliseDeteccao.objects.order_by('-pk')[:20]]})
    try:
        data = payload(request)
        if set(data) != {'metodo', 'parametros', 'indicador', 'base_id'}:
            raise ValueError('Informe método, parâmetros, origem e versão de base.')
        method, indicator = data['metodo'], data['indicador']
        if not isinstance(method, str) or not isinstance(indicator, str) or (indicator and indicator not in DATASETS):
            raise ValueError('Método ou origem inválida.')
        parameters = validate_parameters(method, data['parametros'])
        if data['base_id'] is not None and type(data['base_id']) is not int:
            raise ValueError('A versão de base é inválida.')
        with transaction.atomic():
            lock_administration(request)
            current = configuration_for(indicator)
            if data['base_id'] != current.pk:
                return error('A configuração mudou. Atualize a tela antes de salvar.', 409)
            if current.metodo == method and current.parametros == parameters and current.indicador == indicator:
                raise ValueError('A configuração já está ativa com esses parâmetros.')
            ConfiguracaoDeteccao.objects.filter(indicador=indicator, ativa=True).update(ativa=False)
            version = (ConfiguracaoDeteccao.objects.filter(metodo=method).aggregate(value=Max('versao'))['value'] or 0) + 1
            config = ConfiguracaoDeteccao.objects.create(metodo=method, versao=version, parametros=parameters,
                indicador=indicator, ativa=True, criada_por=request.user)
            alerts = AlertaSurto.objects.filter(ativa=True)
            if indicator:
                alerts = alerts.filter(indicador=indicator)
            else:
                overrides = ConfiguracaoDeteccao.objects.filter(ativa=True).exclude(indicador='').values_list('indicador', flat=True)
                alerts = alerts.exclude(indicador__in=overrides)
            alerts.update(ativa=False, motivo_encerramento='Configuração substituída', atualizada_em=timezone.now())
            job = ReanaliseDeteccao.objects.create(configuracao=config)
            RegistroAuditoria.objects.create(usuario=request.user, acao='detector_configurado', entidade='ConfiguracaoDeteccao',
                entidade_id=config.pk, detalhes={'antes':configuration_data(current), 'depois':configuration_data(config)})
        return JsonResponse({'configuracao':configuration_data(config), 'reanalise':job_data(job)}, status=202)
    except ValueError as exc:
        return error(str(exc))
    except PermissionError as exc:
        return error(str(exc), 403)


@require_POST
@authorized(admin=True)
def reanalyze(request, config_id):
    with transaction.atomic():
        lock_administration(request)
        try:
            config = ConfiguracaoDeteccao.objects.get(pk=config_id, ativa=True)
        except ConfiguracaoDeteccao.DoesNotExist:
            return error('Selecione uma configuração ativa.', 404)
        job, created = ReanaliseDeteccao.objects.get_or_create(configuracao=config,
            status__in=['pendente', 'executando'], defaults={'status':'pendente'})
        if created:
            RegistroAuditoria.objects.create(usuario=request.user, acao='reanalise_solicitada', entidade='ReanaliseDeteccao', entidade_id=job.pk)
    return JsonResponse({'reanalise':job_data(job)}, status=202)


@require_POST
@authorized(admin=True)
def inherit_configuration(request, indicator):
    if indicator not in DATASETS:
        return error('Origem inválida.')
    with transaction.atomic():
        lock_administration(request)
        override = ConfiguracaoDeteccao.objects.filter(indicador=indicator, ativa=True).first()
        if override is None:
            return error('Esta origem já utiliza a configuração padrão.')
        config = ConfiguracaoDeteccao.objects.filter(ativa=True, indicador='').first()
        if config is None:
            return error('A configuração padrão não está disponível.', 409)
        override.ativa=False; override.save(update_fields=['ativa'])
        AlertaSurto.objects.filter(indicador=indicator, ativa=True).update(ativa=False,
            motivo_encerramento='Origem retornou à configuração padrão', atualizada_em=timezone.now())
        job, _ = ReanaliseDeteccao.objects.get_or_create(configuracao=config,
            status__in=['pendente', 'executando'], defaults={'status':'pendente'})
        RegistroAuditoria.objects.create(usuario=request.user, acao='detector_padrao_restaurado',
            entidade='ConfiguracaoDeteccao', entidade_id=override.pk, detalhes={'indicador':indicator,'padrao_id':config.pk})
    return JsonResponse({'configuracao':configuration_data(config),'reanalise':job_data(job)}, status=202)


@require_GET
@authorized()
def compare(request):
    codes = request.GET.get('codigos', '').split(',')
    if not 2 <= len(codes) <= 4 or len(set(codes)) != len(codes):
        return error('Selecione de dois a quatro territórios diferentes.')
    indicator = request.GET.get('indicador', '')
    if indicator not in DATASETS:
        return error('Selecione uma única origem para a comparação.')
    try:
        config = configuration_for(indicator)
        data = [query_indicators({**{k:request.GET.get(k, '') for k in ('inicio','fim')},
            'tipo':request.GET.get('tipo', 'municipio'), 'codigo':code,
            'agravo':request.GET.get('agravo', ''), 'indicador':indicator}, configuration=config) for code in codes]
        return JsonResponse({'series':data, 'unidade':DATASETS[indicator]['unidade'],
            'aviso':'Contagens absolutas. Diferenças de população e cobertura devem ser consideradas; não comparam risco individual.'})
    except ValueError as exc:
        return error(str(exc))


def alerts_queryset(user):
    read = LeituraAlerta.objects.filter(usuario=user, alerta_id=OuterRef('pk')).values('revisao')[:1]
    return AlertaSurto.objects.select_related('recorte', 'configuracao', 'lote').defer(
        'lote__conteudo_original', 'lote__dados_brutos').annotate(revisao_lida=Subquery(read))


def alert_data(alert):
    spec = DATASETS[alert.indicador]
    return {'id':alert.pk, 'titulo':alert.titulo,
        'mensagem':alert_message(spec['agravo_nome'], alert.observado, alert.data_referencia, alert.limiar),
        'ativa':alert.ativa, 'canal':alert.canal,
        'motivo_encerramento':alert.motivo_encerramento, 'revisao':alert.revisao,
        'lida':alert.revisao_lida == alert.revisao, 'territorio':{'codigo':alert.recorte.codigo, 'nome':alert.recorte.nome},
        'data_referencia':alert.data_referencia, 'observado':alert.observado, 'referencia':alert.referencia,
        'limiar':alert.limiar, 'criada_em':alert.criada_em, 'atualizada_em':alert.atualizada_em,
        'configuracao':configuration_data(alert.configuracao), 'indicador':alert.indicador,
        'agravo':spec['agravo_nome'], 'publicador':spec['publicador'], 'lote_id':alert.lote_id,
        'fonte_id':alert.lote.fonte_id, 'url_origem':alert.lote.url_origem,
        'sha256_original':alert.lote.sha256_original, 'coletado_em':alert.lote.criada_em}


@require_GET
@authorized()
def alert_options(request):
    rows = AlertaSurto.objects.order_by().values_list('recorte__codigo', 'indicador').distinct()
    codes, indicators = set(), set()
    for code, indicator in rows:
        codes.add(code); indicators.add(indicator)
    specs = [DATASETS[k] for k in DATASETS if k in indicators]
    return JsonResponse({'municipios':sorted([{'codigo':c, 'nome':REGIONS[c]['nome']} for c in codes if c in REGIONS], key=lambda r:r['nome']),
        'integracoes':specs, 'agravos':list({s['agravo']:{'codigo':s['agravo'], 'nome':s['agravo_nome']} for s in specs}.values())})


@require_GET
@authorized()
def alerts(request):
    qs = alerts_queryset(request.user)
    unread_condition = Q(revisao_lida__isnull=True) | ~Q(revisao_lida=F('revisao'))
    total_unread = qs.filter(ativa=True).filter(unread_condition).count()
    active = request.GET.get('situacao', 'ativas')
    if active not in ('ativas', 'todas', 'encerradas'):
        return error('Situação de alerta inválida.')
    if active != 'todas':
        qs = qs.filter(ativa=active=='ativas')
    if request.GET.get('indicador'):
        if request.GET['indicador'] not in DATASETS:
            return error('Origem inválida.')
        qs = qs.filter(indicador=request.GET['indicador'])
    disease = request.GET.get('agravo', '')
    if disease:
        indicators = [k for k,s in DATASETS.items() if s['agravo'] == disease]
        if not indicators or (request.GET.get('indicador') and request.GET['indicador'] not in indicators):
            return error('Agravo e origem devem corresponder à mesma integração.')
        qs = qs.filter(indicador__in=indicators)
    try:
        start = date.fromisoformat(request.GET['inicio']) if request.GET.get('inicio') else None
        end = date.fromisoformat(request.GET['fim']) if request.GET.get('fim') else None
    except ValueError:
        return error('Use datas válidas no formato AAAA-MM-DD.')
    if start and end and start > end:
        return error('A data inicial deve ser anterior ou igual à final.')
    if start:
        qs = qs.filter(data_referencia__gte=start)
    if end:
        qs = qs.filter(data_referencia__lte=end)
    if request.GET.get('codigo'):
        if request.GET.get('tipo', 'municipio') not in ('municipio', 'regiao'):
            return error('Tipo de território inválido.')
        code = request.GET['codigo']
        if request.GET.get('tipo', 'municipio') == 'regiao':
            codes = [c for c,v in REGIONS.items() if v['regiao_codigo']==code]
        else:
            codes = [code] if code in REGIONS else []
        if not codes:
            return error('Território inválido.')
        qs = qs.filter(recorte__codigo__in=codes)
    unread = qs.filter(unread_condition).count()
    if request.GET.get('nao_lidas') == '1':
        qs = qs.filter(Q(revisao_lida__isnull=True) | ~Q(revisao_lida=F('revisao')))
    page = Paginator(qs, 10).get_page(request.GET.get('page', 1))
    return JsonResponse({'alertas':[alert_data(a) for a in page], 'page':page.number,
        'pages':page.paginator.num_pages, 'count':page.paginator.count, 'nao_lidas':unread, 'nao_lidas_total':total_unread})


@require_POST
@authorized()
def mark_all_read(request):
    """Marca as revisões vigentes como lidas para esta conta, em todas as páginas."""
    with transaction.atomic():
        active = list(AlertaSurto.objects.filter(ativa=True).order_by('pk').select_for_update().values_list('pk', 'revisao'))
        read = dict(LeituraAlerta.objects.filter(usuario=request.user, alerta_id__in=[pk for pk, _ in active])
            .values_list('alerta_id', 'revisao'))
        now = timezone.now()
        pending = [LeituraAlerta(usuario=request.user, alerta_id=pk, revisao=revision, lida_em=now)
            for pk, revision in active if read.get(pk) != revision]
        if pending:
            LeituraAlerta.objects.bulk_create(pending, batch_size=500, update_conflicts=True,
                update_fields=['revisao', 'lida_em'], unique_fields=['usuario', 'alerta'])
    return JsonResponse({'ok': True, 'marcadas': len(pending)})


@require_POST
@authorized()
def mark_read(request, alert_id):
    try:
        data = payload(request)
        if type(data.get('revisao')) is not int:
            raise ValueError('Informe a revisão do alerta exibido.')
        with transaction.atomic():
            alert = AlertaSurto.objects.select_for_update().get(pk=alert_id)
            if data['revisao'] != alert.revisao:
                return error('O alerta foi atualizado. Carregue os novos dados antes de marcar como lido.', 409)
            LeituraAlerta.objects.update_or_create(usuario=request.user, alerta=alert, defaults={'revisao':alert.revisao})
        return JsonResponse({'ok':True})
    except ValueError as exc:
        return error(str(exc))
    except AlertaSurto.DoesNotExist:
        return error('Alerta não encontrado.', 404)
