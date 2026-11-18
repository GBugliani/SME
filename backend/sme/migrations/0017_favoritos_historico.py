import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def preserve_current_state(apps, schema_editor):
    Alert = apps.get_model('sme', 'AlertaSurto')
    Event = apps.get_model('sme', 'EventoSinalizacao')
    for alert in Alert.objects.using(schema_editor.connection.alias).select_related('configuracao').iterator(chunk_size=500):
        config = alert.configuracao
        Event.objects.using(schema_editor.connection.alias).create(alerta_id=alert.pk, tipo='estado_inicial', estado={
            'revisao': alert.revisao, 'ativa': alert.ativa, 'motivo': alert.motivo_encerramento,
            'observado': alert.observado, 'referencia': alert.referencia, 'limiar': alert.limiar,
            'lote_id': alert.lote_id, 'semana': alert.data_referencia.isoformat(),
            'configuracao': {'id': config.pk, 'metodo': config.metodo, 'versao': config.versao,
                             'parametros': config.parametros, 'versao_algoritmo': config.versao_algoritmo}})


class Migration(migrations.Migration):

    dependencies = [
        ('sme', '0016_rotinacoleta'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventoSinalizacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(max_length=25)),
                ('estado', models.JSONField()),
                ('registrado_em', models.DateTimeField(auto_now_add=True)),
                ('alerta', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='eventos', to='sme.alertasurto')),
            ],
            options={
                'ordering': ['-pk'],
            },
        ),
        migrations.CreateModel(
            name='MunicipioFavorito',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=7)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('usuario', 'codigo'), name='favorito_usuario_municipio')],
            },
        ),
        migrations.RunPython(preserve_current_state, migrations.RunPython.noop),
    ]
