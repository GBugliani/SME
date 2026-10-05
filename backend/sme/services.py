from django.core.exceptions import ValidationError
from django.db import transaction
from .models import FonteEpidemiologica, RecorteGeografico, RegistroAuditoria


@transaction.atomic
def save_source(*, data, user, instance=None):
    recorte, created = RecorteGeografico.objects.get_or_create(
        tipo=data["recorte_tipo"], codigo=data["recorte_codigo"],
        defaults={"nome": data["recorte_nome"], "uf": data["recorte_uf"]},
    )
    if not created and (recorte.nome.casefold() != data["recorte_nome"].casefold() or recorte.uf != data["recorte_uf"]):
        raise ValidationError({"recorte_codigo": "Este código já está associado a outro nome ou UF."})
    source = instance or FonteEpidemiologica()
    action = "fonte_atualizada" if source.pk else "fonte_criada"
    for key in ("nome", "tipo", "url", "ativa"):
        setattr(source, key, data[key])
    source.recorte = recorte
    source.full_clean()
    source.save()
    RegistroAuditoria.objects.create(usuario=user, acao=action, entidade="FonteEpidemiologica", entidade_id=source.pk)
    return source
