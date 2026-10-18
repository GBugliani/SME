from django.core.exceptions import ValidationError
from django.db import transaction
from .models import FonteEpidemiologica, RecorteGeografico, RegistroAuditoria


@transaction.atomic
def save_source(*, data, user, instance=None):
    from types import SimpleNamespace
    from .datasets import infer_dataset, source_dataset
    from .collection import get_adapter, CollectionError
    indicator = data.get('indicador') or infer_dataset(data['url'])
    if instance:
        instance = FonteEpidemiologica.objects.select_for_update().get(pk=instance.pk)
        if instance.lotes.exists() and (source_dataset(instance) != indicator or instance.recorte.codigo != data['recorte_codigo'] or instance.recorte.tipo != data['recorte_tipo']):
            raise ValidationError({'indicador':'Uma fonte com histórico não pode mudar de provedor, agravo ou território. Cadastre outra fonte.'})
    if indicator:
        candidate = SimpleNamespace(indicador=indicator, url=data['url'], tipo=data['tipo'], periodo_movel=data.get('periodo_movel', False), recorte=SimpleNamespace(
            tipo=data['recorte_tipo'], codigo=data['recorte_codigo'], nome=data['recorte_nome'], uf=data['recorte_uf']))
        try:
            from .collection_period import collection_source
            get_adapter(candidate).validate(collection_source(candidate))
        except CollectionError as exc:
            raise ValidationError({'url':str(exc)}) from exc
    recorte, created = RecorteGeografico.objects.get_or_create(
        tipo=data["recorte_tipo"], codigo=data["recorte_codigo"],
        defaults={"nome": data["recorte_nome"], "uf": data["recorte_uf"]},
    )
    if not created and (recorte.nome.casefold() != data["recorte_nome"].casefold() or recorte.uf != data["recorte_uf"]):
        raise ValidationError({"recorte_codigo": "Este código já está associado a outro nome ou UF."})
    source = instance or FonteEpidemiologica()
    action = "fonte_atualizada" if source.pk else "fonte_criada"
    if data.get('periodo_movel') and not indicator:
        raise ValidationError({'periodo_movel':'Selecione uma integração compatível com período móvel.'})
    for key in ("nome", "tipo", "url", "ativa", "periodo_movel"):
        setattr(source, key, data[key])
    source.indicador = indicator
    source.recorte = recorte
    source.full_clean()
    source.save()
    RegistroAuditoria.objects.create(usuario=user, acao=action, entidade="FonteEpidemiologica", entidade_id=source.pk)
    return source
