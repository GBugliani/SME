import json
from datetime import timedelta
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from .views import authorized, payload, error
from .models import MunicipioFavorito, AlertaSurto, Usuario
from .indicators import REGIONS
from .collection_health import health


@require_http_methods(['GET', 'POST'])
@authorized()
def favorites(request):
    if request.method == 'POST':
        try:
            code = payload(request).get('codigo')
            if not isinstance(code, str) or code not in REGIONS:
                return error('Município inválido.')
            with transaction.atomic():
                Usuario.objects.select_for_update().get(pk=request.user.pk)
                if not MunicipioFavorito.objects.filter(usuario=request.user, codigo=code).exists():
                    if MunicipioFavorito.objects.filter(usuario=request.user).count() >= 100:
                        return error('Você pode salvar até 100 municípios favoritos.')
                    MunicipioFavorito.objects.create(usuario=request.user, codigo=code)
        except ValueError as exc:
            return error(str(exc))
    from .collection import MUNICIPIOS_SP
    rows = [{'codigo': row.codigo, 'nome': MUNICIPIOS_SP.get(row.codigo, row.codigo)}
            for row in MunicipioFavorito.objects.filter(usuario=request.user)]
    return JsonResponse({'favoritos': sorted(rows, key=lambda row: row['nome'])})


@require_http_methods(['DELETE'])
@authorized()
def remove_favorite(request, code):
    MunicipioFavorito.objects.filter(usuario=request.user, codigo=code).delete()
    return JsonResponse({'ok': True})


@require_GET
@authorized()
def alert_history(request, alert_id):
    alert = AlertaSurto.objects.filter(pk=alert_id).first()
    if alert is None:
        return error('Sinalização não encontrada.', 404)
    page = Paginator(alert.eventos.all(), 20).get_page(request.GET.get('page', 1))
    return JsonResponse({'eventos': [{'id': e.pk, 'tipo': e.tipo, 'estado': e.estado,
                                     'registrado_em': e.registrado_em} for e in page],
                         'page': page.number, 'pages': page.paginator.num_pages,
                         'count': page.paginator.count,
                         'observacao': 'O estado inicial preserva o registro disponível na implantação do histórico; revisões anteriores não podem ser reconstruídas.'})


@require_GET
@authorized(admin=True)
def operational_notices(request):
    response = health(request)
    if response.status_code != 200:
        return response
    data = json.loads(response.content)
    today = timezone.localdate()
    notices = []
    monitored = data['agendamento']['monitoramento_disponivel']
    if monitored and timezone.localtime().hour >= 8 and data['agendamento']['sem_confirmacao']:
        notices.append({'id': f'{today}:agendamento', 'titulo': 'Agendamento sem confirmação',
                        'mensagem': 'Ainda não foi registrado o início da rotina prevista para as 6h. Confira o Airflow em Saúde das coletas.'})
    routine = data['agendamento']['ultima']
    if monitored and routine and routine['status'] == 'sem_confirmacao':
        notices.append({'id': f'{today}:conclusao', 'titulo': 'Rotina sem confirmação de conclusão',
                        'mensagem': 'A última rotina agendada está sem encerramento há mais de 26 horas.'})
    count = data['resumo']['falhas']
    if count >= 3:
        notices.append({'id': f'{today}:falhas', 'titulo': 'Falhas acumuladas nas fontes',
                        'mensagem': f'{count} fontes monitoradas estão com falha na última tentativa. Consulte os motivos e o histórico em Saúde das coletas.'})
    return JsonResponse({'avisos': notices, 'atualizado_em': timezone.now()})
