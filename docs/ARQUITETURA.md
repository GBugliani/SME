# Decisões de arquitetura

## Componentes

React + TypeScript apresenta o sistema; Django 5.2 fornece a API JSON e regras de negócio; PostgreSQL 17 persiste dados. Nginx serve os arquivos React e encaminha `/api/` à API. O navegador usa uma origem única, simplificando cookies e CSRF. Airflow executa em container separado e chama a API interna; a API coleta, normaliza com pandas, persiste séries e executa o detector configurado. Um worker dedicado na mesma imagem processa reanálises persistidas no PostgreSQL.

Django foi adotado para reaproveitar autenticação, hash de senha, sessões, permissões, ORM e migrações. Não há necessidade de construir um sistema próprio de senhas ou armazenar tokens no localStorage. Referência: [Django 5.2](https://docs.djangoproject.com/en/5.2/).

## Consulta e interface

- O catálogo `datasets.py` define contratos de integração. Coleta, normalização, série e consulta identificam o mesmo provedor/agravo/definição. InfoDengue (dengue, chikungunya e zika), InfoGripe (SRAG da capital) e SIVEP-Gripe/MS (SRAG total municipal) têm adaptadores próprios. O SIVEP compartilha o original nacional entre lotes municipais via ArquivoColeta, com cache de download por uma hora em RecursoColeta. [Detalhes, migração e limites](MULTIPLOS_PROVEDORES.md).
- Novos lotes preservam bytes originais, hash, URL e metadados; lotes legados conservam o JSON/hash existente e são identificados como tal. A consulta exige selecionar a origem quando há indicadores distintos, impedindo a mistura de provedores.

- `GET /api/fontes/?q=TERMO&page=N` exige autenticação e filtra antes da paginação de 20 fontes. Os termos são combinados: cada termo deve estar no nome da fonte, nome/código/UF do recorte ou URL. A pesquisa não acessa URLs externas nem altera cadastros. Não há normalização de acentos nesta consulta.
- O arquivamento é reversível: `arquivada_em` oculta a fonte das listas comuns, desabilita a coleta e preserva lotes, séries e auditoria. `GET /api/fontes/?arquivadas=1` e `PUT /api/fontes/<id>/arquivamento/` exigem a permissão `gerenciar_fontes`. Restaurar não reativa a coleta automaticamente.
- A interface espera 250 ms após mudanças na busca e descarta respostas de consultas anteriores. O filtro da tela de fontes não restringe o resumo do Monitoramento. Todos os perfis têm acesso de leitura. Ações de escrita e exportação dependem das permissões do perfil, verificadas na API.
- O gráfico mostra casos e média de quatro semanas por mouse, toque ou teclado. Sem dados não equivale a zero; o tooltip do mouse permanece à esquerda do cursor. As linhas e o detector usam a mesma série da API.
- Abaixo de 1281 px de largura útil, os dois grupos de painéis passam para baixo do mapa; até 900 px, formam uma coluna. Até 760 px, a tabela de fontes assume apresentação em cartões. O zoom do navegador pode acionar essas mesmas quebras.
- Scroll normal navega na página; Ctrl + scroll e dois dedos ajustam o mapa. As transições de navegação, mapa e notificações respeitam a preferência de movimento reduzido.

## Segurança atual e limites

- Bootstrap administrativo via `createsuperuser`. Cadastro de contas e redefinição de senhas são exclusivos da administração.
- `is_staff` identifica o administrador. `PerfilAcesso` atribui permissões de gestão de fontes, coleta manual e exportação; somente administradores gerenciam contas e perfis. As migrações 0006–0008 preservam credenciais e atribuem perfis padrão às contas existentes.
- Sessão armazenada no banco, expiração de oito horas e cookie HttpOnly. Logout invalida a sessão. HTTPS/cookies seguros habilitados fora do modo debug.
- CSRF inclusive no login; dados de autenticação não vão para localStorage. Cinco erros de login por conta suspendem tentativas por 15 minutos, em estado compartilhado no banco.
- Redefinição de senha exige acesso administrativo, confirmação da senha do administrador e validação da nova senha. Cinco erros de confirmação suspendem tentativas por 15 minutos. O evento é auditado sem segredos e as sessões da conta alterada são encerradas; administradores comuns não podem redefinir contas de superusuário.
- Limitação por conta deve ser complementada por limite de requisições no proxy, controle de tentativas distribuídas e limpeza periódica de registros expirados antes de publicação.
- URLs cadastradas devem ser HTTPS e não podem conter credenciais nem apontar literalmente para IP privado. O cadastro não acessa a URL. O coletor InfoDengue usa destino fixo permitido, verifica DNS/IP público, fixa a conexão no IP e rejeita redirects. Novos adaptadores devem preservar essas barreiras; a validação cadastral sozinha não é suficiente contra SSRF.
- Não são importados dados individuais de pacientes nesta etapa. Segredos ficam fora do versionamento.

## Gestão de acesso e exportação

- Administração no menu de perfil: cadastro, edição e desativação de usuários; perfis personalizados; auditoria paginada. Perfis padrão são fixos e mantêm uma referência de administração e leitura.
- Permissões são verificadas por requisição. Desativação remove as sessões existentes; reativação exige novo login. Não é permitido desativar ou remover o próprio acesso administrativo. Operações administrativas são serializadas e revalidam o ator antes de persistir.
- Alterações de contas e perfis guardam responsável, horário e valores anteriores/novos, sem senha ou hash. Exportações também são auditadas.
- Exportação reutiliza a consulta do painel: CSV/JSON agregados ou JSON dos registros brutos interpretados por município, com proveniência. Não exporta o arquivo nacional inteiro. Limites de 50 mil linhas e 20 MiB exigem reduzir filtros em consultas grandes. Lacunas permanecem nulas e o CSV protege células contra interpretação de fórmulas.

## Detecção e alertas

`detectors.py` contém as estratégias causais (média/desvio e mediana/MAD). Configurações são versionadas, possuem uma versão do algoritmo e escopo padrão ou por indicador. `series_data.py` centraliza a escolha da revisão mais recente por município/semana, compartilhada com consultas e comparação.

`detection.py` analisa o município canônico do indicador e persiste `Anomalia` e `AlertaSurto` sem duplicar cadastros sobrepostos. Alertas guardam valores e lote, mantêm revisões e são encerrados quando deixam de valer. `LeituraAlerta` identifica usuário e revisão lida.

`ReanaliseDeteccao` é a fila durável. O serviço Compose `detector` executa `process_detection_jobs --loop`, reivindicando tarefas com lock e recuperando execuções sem progresso após dez minutos. Alterações administrativas e análise compartilham um lock transacional. Configurações substituídas não continuam publicando novas análises.

A comparação exige uma mesma origem/agravo e dois a quatro territórios, com a mesma configuração fixada na resposta. Ausências são preservadas e a cobertura regional parcial é explícita. O desempenho das consultas continua separado do processamento em segundo plano.

## Evolução e publicação

As três caixas de servidores no diagrama são responsabilidades separadas. No desenvolvimento podem executar na mesma máquina em containers. A publicação deve separar aplicação, processamento e banco logicamente e permitir separação física conforme uso, sem exigir três servidores pagos logo no início.

O Compose é exclusivamente local. HTTPS, backups diários com restauração testada, observabilidade, política de retenção e execução confiável do pipeline em produção são requisitos do release.
