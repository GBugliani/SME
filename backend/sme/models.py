from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Informe o e-mail.")
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("O administrador deve ter is_staff e is_superuser habilitados.")
        return self.create_user(email, password, **extra)


class Usuario(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UsuarioManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="usuario_email_ci_unique")]


class RecorteGeografico(models.Model):
    class Tipo(models.TextChoices):
        MUNICIPIO = "municipio", "Município"
        REGIAO = "regiao", "Região"

    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    nome = models.CharField(max_length=150)
    codigo = models.CharField(max_length=50)
    uf = models.CharField(max_length=2, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tipo", "codigo"], name="recorte_tipo_codigo_unique")]


class FonteEpidemiologica(models.Model):
    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=10, choices=[("csv", "CSV"), ("json", "JSON/API")])
    url = models.URLField(max_length=2000)
    recorte = models.ForeignKey(RecorteGeografico, on_delete=models.PROTECT)
    ativa = models.BooleanField(default=True)
    ultima_coleta_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em", "-pk"]
        constraints = [models.UniqueConstraint(fields=["url", "recorte"], name="fonte_url_recorte_unique")]


class RegistroAuditoria(models.Model):
    usuario = models.ForeignKey(Usuario, null=True, on_delete=models.SET_NULL)
    acao = models.CharField(max_length=50)
    entidade = models.CharField(max_length=50)
    entidade_id = models.BigIntegerField()
    criada_em = models.DateTimeField(auto_now_add=True)


class TentativaLogin(models.Model):
    # Hash of normalized email; no password or credential is recorded.
    chave = models.CharField(max_length=64, unique=True)
    falhas = models.PositiveIntegerField(default=0)
    inicio = models.DateTimeField()


class LoteColeta(models.Model):
    fonte = models.ForeignKey(FonteEpidemiologica, on_delete=models.PROTECT, related_name="lotes")
    adaptador = models.CharField(max_length=30)
    agravo = models.CharField(max_length=30)
    url_origem = models.URLField(max_length=2000)
    territorio_codigo = models.CharField(max_length=7)
    sha256 = models.CharField(max_length=64)
    dados_brutos = models.JSONField()
    quantidade_registros = models.PositiveIntegerField()
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["fonte", "sha256"], name="lote_fonte_hash_unique")]


class ExecucaoColeta(models.Model):
    fonte = models.ForeignKey(FonteEpidemiologica, on_delete=models.PROTECT, related_name="coletas")
    status = models.CharField(max_length=15, choices=[("executando", "Executando"), ("sucesso", "Sucesso"), ("vazia", "Sem registros"), ("erro", "Falha")])
    iniciada_em = models.DateTimeField(auto_now_add=True)
    finalizada_em = models.DateTimeField(null=True)
    mensagem = models.CharField(max_length=300, blank=True)
    quantidade_registros = models.PositiveIntegerField(default=0)
    lote = models.ForeignKey(LoteColeta, null=True, on_delete=models.PROTECT)
    repetida = models.BooleanField(default=False)
    origem = models.CharField(max_length=15, default="manual")

    class Meta:
        ordering = ["-iniciada_em", "-pk"]
        constraints = [models.UniqueConstraint(fields=["fonte"], condition=models.Q(status="executando"), name="uma_coleta_ativa_por_fonte")]


class Agravo(models.Model):
    codigo = models.SlugField(unique=True)
    nome = models.CharField(max_length=100)


class SerieEpidemiologica(models.Model):
    fonte = models.ForeignKey(FonteEpidemiologica, on_delete=models.PROTECT)
    recorte = models.ForeignKey(RecorteGeografico, on_delete=models.PROTECT)
    agravo = models.ForeignKey(Agravo, on_delete=models.PROTECT)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['fonte', 'recorte', 'agravo'], name='serie_fonte_recorte_agravo')]


class RegistroEpidemiologico(models.Model):
    serie = models.ForeignKey(SerieEpidemiologica, on_delete=models.PROTECT, related_name='registros')
    ano = models.PositiveSmallIntegerField()
    semana = models.PositiveSmallIntegerField()
    data_referencia = models.DateField(db_index=True)
    casos = models.PositiveBigIntegerField(null=True)
    casos_estimados = models.FloatField(null=True)
    lote = models.ForeignKey(LoteColeta, on_delete=models.PROTECT)

    class Meta:
        ordering = ['data_referencia']
        constraints = [models.UniqueConstraint(fields=['serie', 'ano', 'semana'], name='registro_serie_semana_unique')]


class ProcessamentoLote(models.Model):
    lote = models.OneToOneField(LoteColeta, on_delete=models.PROTECT, related_name='processamento')
    status = models.CharField(max_length=15, choices=[('sucesso','Concluído'),('erro','Falha')])
    mensagem = models.CharField(max_length=300)
    quantidade_registros = models.PositiveIntegerField(default=0)
    versao = models.CharField(max_length=30, default='infodengue_v1')
    atualizado_em = models.DateTimeField(auto_now=True)


class ConfiguracaoDeteccao(models.Model):
    metodo = models.CharField(max_length=50, default='media_movel')
    versao = models.PositiveIntegerField(default=1)
    parametros = models.JSONField(default=dict)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['metodo','versao'], name='config_metodo_versao_unique')]


class Anomalia(models.Model):
    registro = models.ForeignKey(RegistroEpidemiologico, on_delete=models.PROTECT, related_name='anomalias')
    configuracao = models.ForeignKey(ConfiguracaoDeteccao, on_delete=models.PROTECT)
    observado = models.PositiveBigIntegerField()
    referencia = models.FloatField()
    limiar = models.FloatField()
    ativa = models.BooleanField(default=True)
    detectada_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['registro','configuracao'], name='anomalia_registro_config_unique')]
