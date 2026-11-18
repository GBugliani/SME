import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('sme', '0015_coletainicial')]
    operations = [
        migrations.CreateModel(name='RotinaColeta', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('run_id', models.CharField(max_length=250, unique=True)),
            ('tipo', models.CharField(max_length=15)),
            ('fontes_previstas', models.JSONField(default=list)),
            ('iniciada_em', models.DateTimeField(auto_now_add=True)),
            ('finalizada_em', models.DateTimeField(null=True)),
        ]),
        migrations.AddField(model_name='execucaocoleta', name='rotina',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='coletas', to='sme.rotinacoleta')),
    ]
