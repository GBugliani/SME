# Decisões de arquitetura

## Componentes

React + TypeScript apresenta o sistema; Django 5.2 fornece a API JSON e regras de negócio; PostgreSQL 17 persiste dados. Nginx serve os arquivos React e encaminha `/api/` à API. O navegador usa uma origem única, simplificando cookies e CSRF. Python/pandas e Airflow terão containers separados quando o pipeline for implementado.

O documento especifica Python mas não escolhe framework de API. Django foi adotado para reaproveitar autenticação, hash de senha, sessões, permissões, ORM e migrações. Não há necessidade de construir um sistema próprio de senhas ou armazenar tokens no localStorage. Referência: [Django 5.2](https://docs.djangoproject.com/en/5.2/).

## Correspondência com os diagramas

| Elemento do diagrama | Implementação / momento |
|---|---|
| Usuario | `Usuario`, e-mail como identificador, estado ativo e hash de senha |
| PerfilAcesso / Permissao | Infraestrutura Group/Permission do Django; gestão completa na Sprint 3 |
| RecorteGeografico / Município / Região | Uma tabela com discriminador de tipo, código e UF; evita duplicação para este escopo |
| FonteEpidemiologica | Fonte vinculada ao recorte, URL, tipo, habilitação e última coleta nula até coleta real |
| RegistroAuditoria | Registro de criação/alteração de fonte, ator e horário |
| Agravo / SerieEpidemiologica / RegistroEpidemiologico | Sprint 2 |
| MetodoDeteccao / ConfiguracaoDeteccao | Método inicial na Sprint 2; Strategy e configuração versionada na Sprint 4 |
| Anomalia / AlertaSurto | Sprints 2 e 4, respectivamente |

A tabela única de recorte é uma decisão de mapeamento relacional das especializações do UML. O código valida código IBGE de sete dígitos e UF; a conferência do nome/código com catálogo oficial ainda será adicionada. A coleta deve confirmar correspondência do território retornado pela fonte.

O serviço `save_source` concentra transação, consistência do território e auditoria. Os repositórios de séries, configurações e alertas serão introduzidos junto aos respectivos serviços, como previsto no diagrama de sequência.

## Segurança atual e limites

- Somente contas preexistentes entram. Bootstrap administrativo via `createsuperuser`.
- `is_staff` identifica o administrador nesta etapa. O IAM configurável continua na Sprint 3.
- Sessão armazenada no banco, expiração de oito horas e cookie HttpOnly. Logout invalida a sessão. HTTPS/cookies seguros habilitados fora do modo debug.
- CSRF inclusive no login; dados de autenticação não vão para localStorage. Cinco erros de login por conta suspendem tentativas por 15 minutos, em estado compartilhado no banco.
- Limitação por conta deve ser complementada por limite de requisições no proxy, controle de tentativas distribuídas e limpeza periódica de registros expirados antes de publicação.
- URLs cadastradas devem ser HTTPS e não podem conter credenciais nem apontar literalmente para IP privado. O cadastro não acessa a URL. O futuro coletor precisa de allowlist, verificação de DNS/IP e bloqueio de redirects para rede privada; a validação cadastral sozinha não é uma barreira suficiente contra SSRF.
- Não são importados dados individuais de pacientes nesta etapa. Segredos ficam fora do versionamento.

## Evolução e publicação

As três caixas de servidores no diagrama são responsabilidades separadas. No desenvolvimento podem executar na mesma máquina em containers. A publicação deve separar aplicação, processamento e banco logicamente e permitir separação física conforme uso, sem exigir três servidores pagos logo no início.

O Compose é exclusivamente local. HTTPS, backups diários com restauração testada, observabilidade, política de retenção e execução real do pipeline são requisitos do release; não estão implementados por existir um Dockerfile.
