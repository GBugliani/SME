from django.db import migrations


def populate(apps, schema_editor):
    Profile = apps.get_model('sme', 'PerfilAcesso')
    User = apps.get_model('sme', 'Usuario')
    admin, _ = Profile.objects.get_or_create(codigo='administrador', defaults={
        'nome': 'Administrador', 'permissoes': ['gerenciar_fontes', 'coletar_dados', 'exportar_dados']})
    reader, _ = Profile.objects.get_or_create(codigo='usuario', defaults={
        'nome': 'Usuário', 'permissoes': ['exportar_dados']})
    User.objects.filter(is_staff=True, perfil__isnull=True).update(perfil=admin)
    User.objects.filter(is_staff=False, perfil__isnull=True).update(perfil=reader)


class Migration(migrations.Migration):
    dependencies = [('sme', '0006_registroauditoria_detalhes_perfilacesso_and_more')]
    operations = [migrations.RunPython(populate, migrations.RunPython.noop)]
