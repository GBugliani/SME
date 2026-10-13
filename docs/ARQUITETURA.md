# Decisões de arquitetura

## Componentes

React + TypeScript apresenta o sistema; Django 5.2 fornece a API JSON e regras de negócio; PostgreSQL 17 persiste dados. Nginx serve os arquivos React e encaminha `/api/` à API. O navegador usa uma origem única, simplificando cookies e CSRF. Airflow executa em container separado e chama a API interna; a API coleta, normaliza com pandas, persiste séries e executa o detector inicial.

Django foi adotado para reaproveitar autenticação, hash de senha, sessões, permissões, ORM e migrações. Não há necessidade de construir um sistema próprio de senhas ou armazenar tokens no localStorage. Referência: [Django 5.2](https://docs.djangoproject.com/en/5.2/).

## Consulta e interface

- `GET /api/fontes/?q=TERMO&page=N` exige autenticação e filtra antes da paginação de 20 fontes. Os termos são combinados: cada termo deve estar no nome da fonte, nome/código/UF do recorte ou URL. A pesquisa não acessa URLs externas nem altera cadastros. Não há normalização de acentos nesta consulta.
- A interface espera 250 ms após mudanças na busca e descarta respostas de consultas anteriores. O filtro da tela de fontes não restringe o resumo do Monitoramento. Usuários comuns têm a mesma leitura, com ações de escrita reservadas a administradores.
- O gráfico mostra casos e média de quatro semanas por mouse, toque ou teclado. Sem dados não equivale a zero; o tooltip do mouse permanece à esquerda do cursor. As linhas e o detector usam a mesma série da API.
- Abaixo de 1281 px de largura útil, os dois grupos de painéis passam para baixo do mapa; até 900 px, formam uma coluna. Até 760 px, a tabela de fontes assume apresentação em cartões. O zoom do navegador pode acionar essas mesmas quebras.
- Scroll normal navega na página; Ctrl + scroll e dois dedos ajustam o mapa. As transições de navegação, mapa e notificações respeitam a preferência de movimento reduzido.

## Segurança atual e limites

- Somente contas preexistentes entram. Bootstrap administrativo via `createsuperuser`.
- `is_staff` identifica o administrador nesta etapa.
- Sessão armazenada no banco, expiração de oito horas e cookie HttpOnly. Logout invalida a sessão. HTTPS/cookies seguros habilitados fora do modo debug.
- CSRF inclusive no login; dados de autenticação não vão para localStorage. Cinco erros de login por conta suspendem tentativas por 15 minutos, em estado compartilhado no banco.
- Alteração da própria senha exige senha atual, confirmação e validação; aplica limite de tentativas, audita o evento sem segredos, rotaciona a sessão atual e invalida as demais na próxima requisição.
- Limitação por conta deve ser complementada por limite de requisições no proxy, controle de tentativas distribuídas e limpeza periódica de registros expirados antes de publicação.
- URLs cadastradas devem ser HTTPS e não podem conter credenciais nem apontar literalmente para IP privado. O cadastro não acessa a URL. O coletor InfoDengue usa destino fixo permitido, verifica DNS/IP público, fixa a conexão no IP e rejeita redirects. Novos adaptadores devem preservar essas barreiras; a validação cadastral sozinha não é suficiente contra SSRF.
- Não são importados dados individuais de pacientes nesta etapa. Segredos ficam fora do versionamento.

## Evolução e publicação

As três caixas de servidores no diagrama são responsabilidades separadas. No desenvolvimento podem executar na mesma máquina em containers. A publicação deve separar aplicação, processamento e banco logicamente e permitir separação física conforme uso, sem exigir três servidores pagos logo no início.

O Compose é exclusivamente local. HTTPS, backups diários com restauração testada, observabilidade, política de retenção e execução confiável do pipeline em produção são requisitos do release.
