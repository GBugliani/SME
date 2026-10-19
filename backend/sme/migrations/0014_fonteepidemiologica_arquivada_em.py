from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sme', '0013_configuracaoemail_grupoemail_envioalertaemail_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='fonteepidemiologica',
            name='arquivada_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
