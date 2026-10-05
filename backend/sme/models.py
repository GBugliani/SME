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
