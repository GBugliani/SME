# Usuários, perfis e exportação

Implementado conforme HU07/RF08, HU08/RF09 e HU09/RF10 do DOCX oficial. Os fluxos UC08 e UC09 colocam a gestão de perfis e cadastros sob responsabilidade do administrador. 

## Entregas

| História | Implementação |
| --- | --- |
| HU07 — IAM | Perfis personalizados, atribuição a contas e permissões independentes para gerenciar fontes, executar coleta manual e exportar. Verificação na API em cada requisição. |
| HU08 — Cadastros | Interface administrativa para criar, pesquisar, editar e desativar usuários. Auditoria com responsável, horário e valores anteriores/novos. |
| HU09 — Exportação | CSV e JSON de séries agregadas, JSON de registros brutos interpretados por município. Recorte, período, agravo e indicador do painel são respeitados; origem e lotes acompanham a exportação. |

## Como usar

1. Entre como administrador e abra **ícone de perfil → Administração**.
2. **Usuários**: cadastre nome, e-mail, senha inicial, perfil e situação. Para editar, selecione a conta. Senhas existentes não são exibidas. A ação **Redefinir senha** exige confirmação da senha do administrador e da nova senha, aplica os validadores e encerra as sessões da conta alterada. `changepassword` permanece disponível para recuperação pelo operador do servidor.
3. **Perfis de acesso**: crie um perfil, como “Operador de coleta”, e marque as ações permitidas. Atribua esse perfil aos usuários na edição da conta.
4. **Auditoria**: consulte as ações e expanda “Ver alterações”. Não há edição ou exclusão dos registros pela interface.
5. Em **Monitoramento → Exportar**, escolha conteúdo e formato. A opção aparece somente para quem pode exportar e fica disponível quando a consulta possui série.

## Matriz de permissões

| Ação | Administrador | Usuário padrão | Perfil personalizado |
| --- | --- | --- | --- |
| Consultar monitoramento, fontes e histórico de coleta | Sim | Sim | Sim |
| Exportar | Sim | Sim | Conforme configuração |
| Cadastrar/editar/desabilitar fontes | Sim | Não | Conforme configuração |
| Executar coleta manual | Sim | Não | Conforme configuração |
| Gerenciar contas, perfis e consultar auditoria | Sim | Não | Não |

Os dois perfis padrão são fixos. O administrador cria perfis personalizados em vez de alterar o significado dos padrões. Gestão de fontes não concede automaticamente coleta manual, nem gestão de contas. A leitura é a permissão básica de qualquer conta ativa. Contas criadas por `createuser` sem atribuição explícita de perfil recebem o comportamento de Usuário; `createsuperuser` conserva o acesso administrativo.

## Proteções e migração

- Migrações 0006–0008 acrescentam `PerfilAcesso`, associação opcional à conta e detalhes de auditoria. Contas anteriores recebem o perfil padrão compatível, preservando senha, situação e privilégios existentes.
- Somente administradores podem atribuir o perfil Administrador. A interface não cria superusuários. Administradores comuns não podem editar contas de superusuário.
- Não é permitido remover o próprio acesso administrativo ou desativar a própria conta. A validação também impede remover o último administrador ativo. Um lock compartilhado serializa alterações administrativas e revalida o ator antes da gravação.
- Ao desativar uma conta, suas sessões são removidas. Reativá-la não reativa cookies antigos. Mudanças de permissões passam a valer na próxima requisição; a interface atualiza a identidade ao recuperar foco ou recarregar.
- E-mails são normalizados e únicos sem distinção de maiúsculas. Senha inicial passa pelos validadores existentes; a auditoria não contém senha nem hash. Escritas exigem CSRF.
- Perfis/contas são preservados; não foi implementada exclusão física. Dados epidemiológicos e trilhas históricas permanecem associados aos registros existentes.

## Contrato da exportação

Endpoint autenticado: `GET /api/indicadores/exportar/`, usando os mesmos parâmetros de `/api/indicadores/`, acrescidos de `modo=agregados|brutos` e `formato=csv|json`.

- **Agregados:** a mesma série semanal apresentada no painel. CSV usa UTF-8 com BOM e separador `;`, para abertura em planilhas. Colunas incluem território, agravo, indicador, unidade, contagens, anomalias, cobertura, origens, fontes/lotes e data de exportação. JSON reúne esses dados e metadados de consulta.
- **Brutos:** JSON com os registros dos lotes que sustentam cada ponto da consulta, sem somar municípios. InfoDengue conserva campos da resposta; InfoGripe conserva colunas do CSV; SIVEP conserva os registros municipais interpretados do XLSX, incluindo lacunas explícitas. Não corresponde aos bytes do arquivo original nem exporta a planilha nacional inteira. Hash e identificação do lote original ficam nos metadados.
- Revisões vigentes são as mesmas do painel. O exportador não mistura indicadores ou provedores e não recupera automaticamente outras versões históricas.
- Campos nulos permanecem `null` em JSON e vazios em CSV; zero continua zero. Quando a cobertura regional é parcial, o arquivo informa quantos municípios compõem o resultado.
- Limites por solicitação: 50 mil linhas e 20 MiB. Acima disso, o usuário deve reduzir período/recorte.
- Valores textuais potencialmente interpretados como fórmulas em planilhas são protegidos. Respostas não podem ser armazenadas em cache; exportações bem-sucedidas geram auditoria.
- Não é feita nova coleta para exportar: são usados os dados armazenados. Uma coleta concorrente pode atualizar os valores entre a visualização e o download.

## Validação técnica — 16/10/2026

- **122 testes backend passaram no PostgreSQL**, em banco de testes separado; a mesma suíte passou em SQLite. Incluem 23 testes novos de IAM, cadastro/edição, bloqueios de elevação de privilégios, revogação de sessão, CSRF, auditoria, exportação e migração de contas.
- Exportação validada para InfoDengue, InfoGripe e SIVEP, inclusive semana 53, lacunas, região com múltiplos municípios, período e separação por agravo/indicador.
- TypeScript e build Docker passaram. Os três testes existentes do cliente API passaram. Permanece o aviso anterior de tamanho do arquivo da malha municipal.
- Navegador em 1440×1000 e 390×844: cadastro/edição de usuário, criação de perfil, login com perfil personalizado, restrição dos controles, auditoria e downloads CSV/JSON. Sem erros JavaScript nem rolagem horizontal nas telas verificadas.
- Migrações aplicadas no Docker local após backup. Hashes dos registros comparados antes/depois: **3 contas, 14 fontes e 850 registros epidemiológicos preservados**, incluindo hashes das senhas e situações de acesso.
- `makemigrations --check --dry-run`: nenhuma alteração pendente; migrações até 0008 aplicadas.

## Aceite e limites de escopo

O aceite da equipe deve confirmar os fluxos acima com seus perfis reais. A atualização do servidor remoto e sua configuração de segurança não são comprovadas pelos testes locais.

Alertas no painel, configuração do detector e comparação simultânea de territórios foram implementados Backup diário automático, restauração, validação retrospectiva do detector e revisão do ambiente de produção permanecem no fechamento do projeto; o backup manual desta atualização não substitui o RNF09.

## Ajuste de escopo — 17/10/2026

Cadastro público (`/api/auth/register/`) e alteração da própria senha (`/api/auth/password/`) foram removidos do frontend e da API. A variável antiga não reativa esses endpoints. A opção de mostrar/ocultar a senha digitada no login continua disponível.

A administração oferece `POST /api/administracao/usuarios/<id>/senha/`: permissão administrativa, CSRF, confirmação da senha do administrador, limitação por conta administradora (cinco erros por 15 minutos), validação de senha e auditoria sem valores secretos. O reset não revela a senha anterior. Todas as sessões do usuário são encerradas; redefinir a própria conta exige novo login. A restrição de edição de superusuários permanece.

Testes foram ajustados ao novo escopo: cadastro/troca direta indisponíveis, redefinição por administrador, confirmação inválida, CSRF, acesso indevido, limitação de tentativas, auditoria e encerramento de sessões.

Validação deste ajuste: **120 testes backend passaram no PostgreSQL**, três testes do cliente API e build/TypeScript passaram. No navegador, cadastro público e troca no menu ausentes; redefinição administrativa e login com a nova senha passaram em base QA isolada, com verificação de desktop e celular. Docker local atualizado, sem novas migrações.
