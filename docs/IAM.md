# Usuários, perfis e exportação

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

## Proteções

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