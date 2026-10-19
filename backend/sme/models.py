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


class PerfilAcesso(models.Model):
    nome = models.CharField(max_length=80, unique=True)
    codigo = models.SlugField(max_length=40, unique=True, null=True, blank=True)
    permissoes = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['nome', 'pk']
        constraints = [models.UniqueConstraint(Lower('nome'), name='perfil_nome_ci_unique')]


class Usuario(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    perfil = models.ForeignKey(PerfilAcesso, null=True, blank=True, on_delete=models.PROTECT)
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
    indicador = models.CharField(max_length=80, blank=True, default='')
    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=10, choices=[("csv", "CSV"), ("json", "JSON/API"), ("xlsx", "Excel")])
    url = models.URLField(max_length=2000)
    recorte = models.ForeignKey(RecorteGeografico, on_delete=models.PROTECT)
    ativa = models.BooleanField(default=True)
    arquivada_em = models.DateTimeField(null=True, blank=True)
    periodo_movel = models.BooleanField(default=False)
    ultima_coleta_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criada_em", "-pk"]
        constraints = [models.UniqueConstraint(fields=["url", "recorte"], name="fonte_url_recorte_unique"),
            models.UniqueConstraint(fields=['recorte', 'indicador'], condition=models.Q(periodo_movel=True), name='fonte_movel_recorte_indicador_unique')]


class RegistroAuditoria(models.Model):
    usuario = models.ForeignKey(Usuario, null=True, on_delete=models.SET_NULL)
    acao = models.CharField(max_length=50)
    entidade = models.CharField(max_length=50)
    entidade_id = models.BigIntegerField()
    detalhes = models.JSONField(default=dict)
    criada_em = models.DateTimeField(auto_now_add=True)


class TentativaLogin(models.Model):
    # Hash of normalized email; no password or credential is recorded.
    chave = models.CharField(max_length=64, unique=True)
    falhas = models.PositiveIntegerField(default=0)
    inicio = models.DateTimeField()


class ArquivoColeta(models.Model):
    """Original imutável, compartilhado entre lotes municipais da mesma versão."""
    sha256 = models.CharField(max_length=64, unique=True)
    conteudo = models.BinaryField(editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)


class RecursoColeta(models.Model):
    """Cache de leitura por URL; o arquivo anterior continua preservado nos lotes."""
    url = models.URLField(max_length=2000, unique=True)
    arquivo = models.ForeignKey(ArquivoColeta, null=True, on_delete=models.PROTECT)
    verificado_em = models.DateTimeField(null=True)
    metadados = models.JSONField(default=dict)


class LoteColeta(models.Model):
    arquivo_original = models.ForeignKey(ArquivoColeta, null=True, on_delete=models.PROTECT)
    indicador = models.CharField(max_length=80, blank=True, default='')
    proveniencia = models.JSONField(default=dict)
    conteudo_original = models.BinaryField(null=True, editable=False)
    sha256_original = models.CharField(max_length=64, blank=True, default='')
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


class ColetaInicial(models.Model):
    """Pedido durável para a primeira coleta de uma fonte habilitada."""
    fonte = models.OneToOneField(FonteEpidemiologica, on_delete=models.CASCADE, related_name="coleta_inicial")
    status = models.CharField(max_length=15, default="pendente", choices=[
        ("pendente", "Pendente"), ("executando", "Executando"),
        ("concluida", "Concluída"), ("ignorada", "Ignorada"), ("erro", "Falha")])
    tentativas = models.PositiveIntegerField(default=0)
    mensagem = models.CharField(max_length=300, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["criada_em", "pk"]
        indexes = [models.Index(fields=["status", "criada_em"], name="coleta_inicial_fila_idx")]


class Agravo(models.Model):
    codigo = models.SlugField(unique=True)
    nome = models.CharField(max_length=100)


class SerieEpidemiologica(models.Model):
    indicador = models.CharField(max_length=80, blank=True, default='', db_index=True)
    fonte = models.ForeignKey(FonteEpidemiologica, on_delete=models.PROTECT)
    recorte = models.ForeignKey(RecorteGeografico, on_delete=models.PROTECT)
    agravo = models.ForeignKey(Agravo, on_delete=models.PROTECT)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['fonte', 'recorte', 'agravo', 'indicador'], name='serie_fonte_recorte_agravo_indicador')]


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
    indicador = models.CharField(max_length=80, blank=True, default='')
    ativa = models.BooleanField(default=False)
    versao_algoritmo = models.PositiveSmallIntegerField(default=1)
    criada_por = models.ForeignKey(Usuario, null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['metodo','versao'], name='config_metodo_versao_unique'),
                       models.UniqueConstraint(fields=['indicador'], condition=models.Q(ativa=True), name='config_ativa_por_indicador')]


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


class AlertaSurto(models.Model):
    recorte = models.ForeignKey(RecorteGeografico, on_delete=models.PROTECT)
    indicador = models.CharField(max_length=80)
    data_referencia = models.DateField()
    configuracao = models.ForeignKey(ConfiguracaoDeteccao, on_delete=models.PROTECT)
    anomalia = models.ForeignKey(Anomalia, on_delete=models.PROTECT)
    lote = models.ForeignKey(LoteColeta, on_delete=models.PROTECT)
    titulo = models.CharField(max_length=200)
    mensagem = models.TextField()
    canal = models.CharField(max_length=10, default='painel', choices=[('painel', 'Painel')])
    observado = models.PositiveBigIntegerField()
    referencia = models.FloatField()
    limiar = models.FloatField()
    ativa = models.BooleanField(default=True)
    motivo_encerramento = models.CharField(max_length=100, blank=True)
    revisao = models.PositiveIntegerField(default=1)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_referencia', '-pk']
        constraints = [models.UniqueConstraint(fields=['recorte', 'indicador', 'data_referencia', 'configuracao'], name='alerta_semana_config_unico')]
        indexes = [models.Index(fields=['ativa', '-data_referencia'], name='alerta_ativo_semana')]


class LeituraAlerta(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    alerta = models.ForeignKey(AlertaSurto, on_delete=models.CASCADE)
    revisao = models.PositiveIntegerField()
    lida_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['usuario', 'alerta'], name='leitura_usuario_alerta_unica')]


class ReanaliseDeteccao(models.Model):
    configuracao = models.ForeignKey(ConfiguracaoDeteccao, on_delete=models.PROTECT)
    status = models.CharField(max_length=15, default='pendente', choices=[
        ('pendente', 'Na fila'), ('executando', 'Em execução'), ('sucesso', 'Concluída'),
        ('erro', 'Falha'), ('substituida', 'Configuração substituída')])
    total = models.PositiveIntegerField(default=0)
    processados = models.PositiveIntegerField(default=0)
    mensagem = models.CharField(max_length=300, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    finalizada_em = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['configuracao'], condition=models.Q(status__in=['pendente', 'executando']), name='uma_reanalise_ativa_config')]


class ConfiguracaoEmail(models.Model):
    """Ativação explícita do canal, separada das credenciais SMTP do ambiente."""
    habilitado = models.BooleanField(default=False)
    atualizado_em = models.DateTimeField(auto_now=True)


class GrupoEmail(models.Model):
    nome = models.CharField(max_length=100)
    enderecos = models.JSONField(default=list)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome', 'pk']
        constraints = [models.UniqueConstraint(Lower('nome'), name='grupo_email_nome_ci_unique')]


class DestinoEmail(models.Model):
    """Um endereço individual ou um grupo selecionado para receber alertas."""
    email = models.EmailField(blank=True)
    grupo = models.ForeignKey(GrupoEmail, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(email='', grupo__isnull=False) |
                (~models.Q(email='') & models.Q(grupo__isnull=True))), name='destino_email_ou_grupo'),
            models.UniqueConstraint(Lower('email'), condition=~models.Q(email=''), name='destino_email_unico_ci'),
            models.UniqueConstraint(fields=['grupo'], condition=models.Q(grupo__isnull=False), name='destino_grupo_unico'),
        ]


class EnvioAlertaEmail(models.Model):
    """Mensagem individual e imutável de uma revisão; evita duplicar o enfileiramento."""
    alerta = models.ForeignKey(AlertaSurto, on_delete=models.PROTECT)
    revisao = models.PositiveIntegerField()
    destinatario = models.EmailField()
    assunto = models.CharField(max_length=255)
    corpo = models.TextField()
    status = models.CharField(max_length=12, default='pendente', choices=[
        ('pendente', 'Pendente'), ('enviando', 'Enviando'), ('enviado', 'Enviado'),
        ('erro', 'Falha'), ('cancelado', 'Cancelado')])
    tentativas = models.PositiveSmallIntegerField(default=0)
    proxima_tentativa_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    erro = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['alerta', 'revisao', 'destinatario'], name='envio_alerta_revisao_email_unico')]
        indexes = [models.Index(fields=['status', 'proxima_tentativa_em'], name='envio_email_pendente')]
