from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('sme', '0014_fonteepidemiologica_arquivada_em'),
    ]

    operations = [
        migrations.CreateModel(
            name='ColetaInicial',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('executando', 'Executando'), ('concluida', 'Concluída'), ('ignorada', 'Ignorada'), ('erro', 'Falha')], default='pendente', max_length=15)),
                ('tentativas', models.PositiveIntegerField(default=0)),
                ('mensagem', models.CharField(blank=True, max_length=300)),
                ('criada_em', models.DateTimeField(auto_now_add=True)),
                ('atualizada_em', models.DateTimeField(auto_now=True)),
                ('fonte', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='coleta_inicial', to='sme.fonteepidemiologica')),
            ],
            options={
                'ordering': ['criada_em', 'pk'],
            },
        ),
        migrations.AddIndex(
            model_name='coletainicial',
            index=models.Index(fields=['status', 'criada_em'], name='coleta_inicial_fila_idx'),
        ),
    ]
