from django.db import migrations


def populate(apps, schema_editor):
    Config = apps.get_model('sme','ConfiguracaoDeteccao')
    Job = apps.get_model('sme','ReanaliseDeteccao')
    config, _ = Config.objects.get_or_create(metodo='media_movel', versao=1,
        defaults={'parametros':{'janela':8,'desvios':3.0,'razao_minima':2.0,'piso':5.0}})
    config.ativa = True; config.save(update_fields=['ativa'])
    Job.objects.get_or_create(configuracao=config, status='pendente')


class Migration(migrations.Migration):
    dependencies = [('sme','0009_alertasurto_leituraalerta_reanalisedeteccao_and_more')]
    operations = [migrations.RunPython(populate, migrations.RunPython.noop)]
