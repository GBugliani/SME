# Instalação e execução no Windows

## Caminho recomendado: Docker Desktop

O Docker executa Python, PostgreSQL, Node (durante a compilação) e Nginx em containers. Para rodar esta etapa você não precisa instalar essas ferramentas individualmente.

1. Baixe o [Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/), seguindo os requisitos atuais da sua versão do Windows.
2. Ative virtualização e WSL 2 se o instalador solicitar. Isso pode exigir acesso de administrador e reinicialização. Se o WSL ainda não estiver instalado, use `wsl --install` em PowerShell de administrador, reinicie quando solicitado e depois `wsl --update`.
3. Abra o Docker Desktop e use o mecanismo WSL 2 / containers Linux.
4. Em um PowerShell novo, rode `docker --version`, `docker compose version` e `docker info`. O último comando precisa conseguir falar com o servidor Docker.
5. Execute os comandos abaixo.

```powershell
cd C:\Projetos\sme
powershell -ExecutionPolicy Bypass -File .\scripts\check-environment.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
docker compose up --build -d
docker compose ps
docker compose exec backend python manage.py createsuperuser
```

O script gera `.env` com segredos aleatórios e preserva um arquivo já existente. Não compartilhe esse arquivo. O bypass da política vale apenas para o processo que executa o script; não muda a política da máquina.

O primeiro build baixa imagens e dependências, por isso precisa de internet. As migrações são aplicadas automaticamente ao iniciar a API. No cadastro do administrador, use uma senha com pelo menos 12 caracteres. A digitação da senha não aparece no terminal.

Abra [SME local](http://localhost:8080). Use sempre o mesmo endereço para preservar cookies e sessão. O banco não publica uma porta na rede. Por padrão, a interface escuta somente em `127.0.0.1`, inclusive no servidor.

### Acessar pelo celular na mesma rede

Conecte o celular ao Wi-Fi do mesmo roteador do computador. Confira o IPv4 do computador com `ipconfig`, copie `compose.lan.example.yaml` para `compose.lan.yaml` e substitua `192.168.10.67` pelo IPv4 encontrado nas duas linhas do arquivo. Inicie com `docker compose -f compose.yaml -f compose.lan.yaml up -d --build` e abra `http://SEU-IP:8080` no celular. O computador e o Docker precisam estar ligados. `localhost` no celular aponta para o próprio celular. A sessão do celular é independente da sessão no PC.

O arquivo `compose.lan.yaml` é ignorado pelo Git e só é aplicado quando incluído com `-f`; atualizações do repositório não publicarão o IP local no servidor. Se o IPv4 mudar, atualize esse arquivo e execute novamente o comando acima. Para voltar ao modo somente local, execute `docker compose up -d --force-recreate backend frontend`. Não use `*` em hosts permitidos nem encaminhe essa porta no roteador para a internet.

Se o Firewall do Windows bloquear o acesso, permita TCP 8080 para a sub-rede local no perfil da sua rede doméstica. Não é necessário publicar portas do PostgreSQL, backend ou Airflow.

## Criar usuário comum

O administrador pode criar contas em **ícone de perfil → Administração → Usuários → Cadastrar usuário**. O cadastro público pela tela de login foi removido.

Como alternativa pelo terminal, com o Docker ligado, execute um único comando:

```powershell
docker compose exec backend python manage.py createuser
```

O comando pergunta e-mail, senha e confirmação. A senha fica oculta e precisa atender às validações do sistema, incluindo pelo menos 12 caracteres. E-mail inválido/duplicado ou senha inválida podem ser corrigidos no próprio terminal. A conta nasce ativa, sem permissões administrativas. Ctrl+C cancela sem criar a conta.

## Comandos do dia a dia

```powershell
# Iniciar
docker compose up -d
# Recompilar após alterações no código
docker compose up --build -d
# Consultar logs
docker compose logs --tail=100 backend frontend
# Desligar sem apagar os dados
docker compose down
# Alterar a senha de uma conta pelo terminal
docker compose exec backend python manage.py changepassword seu-email@exemplo.com
```

Se a porta 8080 estiver ocupada, altere no compose o lado esquerdo de `127.0.0.1:8080:80`, por exemplo para `127.0.0.1:8081:80`, e use a nova porta no navegador. Se houver falha de conexão com o Docker, abra o aplicativo antes de repetir o comando. Não apague o volume para resolver falhas de inicialização.

Na interface, o ícone de perfil no canto superior abre um menu com nome/e-mail, tipo de usuário e **Sair**, além de **Administração** para administradores. Quando nome e e-mail forem iguais, o e-mail aparece uma única vez. A redefinição de senha é realizada pelo administrador na lista de usuários. Para visualizar alterações após recompilar o frontend, recarregue com **Ctrl + F5**.

Para navegar no mapa, use os botões +/− ou **Ctrl + scroll**. O scroll sem Ctrl rola a página. No celular, um dedo rola a página e dois dedos ajustam o zoom do mapa. Em telas menores ou com zoom no navegador, ambos os grupos de painéis passam para baixo do mapa; a tabela de fontes vira cartões no celular.

## Ambiente para editar o código

Para desenvolvimento com recarga automática, instale [Python 3.12](https://www.python.org/downloads/), [Node.js 24](https://nodejs.org/en/download) e [Git](https://git-scm.com/downloads/win). O projeto utiliza `pnpm` 11.25.0, instalável com `npm install -g pnpm@11.25.0`. A interface usa Vite; consulte seus [requisitos de Node](https://vite.dev/guide/).

O PostgreSQL pode continuar no Docker. Para editar só a interface, inicie o compose e use no `frontend/vite.config.ts` o destino de proxy `http://127.0.0.1:8080`; então rode `pnpm dev`. Para API local, o proxy original é `http://127.0.0.1:8000`.

Uma API local exige um PostgreSQL acessível e as variáveis `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=true`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` e `POSTGRES_PASSWORD` configuradas no terminal. O Django não lê `.env` automaticamente; no caminho recomendado, o Compose injeta as variáveis.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
# Configure as variáveis acima antes dos comandos seguintes.
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py runserver
```

Em outro terminal:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

O arquivo `config.test_settings` permite testes isolados com SQLite quando não há PostgreSQL. Ele usa hash simplificado para acelerar testes e nunca deve ser usado para publicar ou operar o sistema.

## Permissões atuais

Usuários autenticados podem consultar a quantidade, a lista, os endereços públicos, os territórios, a situação e o histórico de coleta das fontes visíveis. O perfil padrão Usuário também pode exportar. Administradores podem cadastrar perfis personalizados com permissões independentes de cadastro/edição/arquivamento de fontes, coleta manual e exportação. Somente administradores gerenciam contas e perfis. A API verifica as permissões em cada solicitação, além de a interface ocultar ações indisponíveis.

## Administração de usuários e exportação

Entre como administrador e abra o ícone de perfil → **Administração**. Em **Usuários**, cadastre ou edite nome, e-mail, perfil e situação. Desativar uma conta preserva seu histórico e encerra suas sessões. **Perfis de acesso** permite criar e editar perfis personalizados; **Auditoria** mostra responsável, horário e alterações.

A senha inicial é definida no cadastro. Para redefinir, use **Administração → Usuários → Redefinir senha**, confirme sua senha de administrador e informe a nova senha duas vezes. Todas as sessões da conta alterada são encerradas. Se alterar a própria conta administrativa, entre novamente. Senhas existentes não podem ser consultadas. `createsuperuser`, `createuser` e `changepassword` continuam disponíveis. Cadastro público e troca de senha pelo menu do usuário foram removidos, inclusive os respectivos endpoints.

No **Monitoramento**, o botão **Exportar** usa o recorte, agravo, origem e período do painel: agregados em CSV/JSON ou registros brutos por município em JSON. Arquivos incluem a origem e os lotes utilizados.

Antes de atualizar, faça backup. Rode `docker compose up --build -d`; as migrações 0006–0008 adicionam perfis e detalhes de auditoria sem redefinir senhas. Recarregue o navegador com Ctrl + F5.

## Provedores e agravos

Após atualizar o código, execute `docker compose up --build -d`; a API aplica a migração de identificação das fontes existentes. Faça backup do banco antes de atualizar. O cadastro assistido oferece InfoDengue (dengue, chikungunya, zika), InfoGripe (SRAG, São Paulo capital) e SIVEP-Gripe / Ministério da Saúde (SRAG total, municípios de SP, um ano por acompanhamento desde 2019). A atualização instala também o leitor XLSX e aplica a migração 0005 para compartilhar arquivos originais. Consulte [Múltiplos provedores](MULTIPLOS_PROVEDORES.md) para coleta, filtros e limites.

Em **Fontes de dados**, quem tem permissão **Gerenciar fontes** pode clicar **Arquivar** após confirmar a ação. A fonte deixa de aparecer na lista principal e no resumo, para de ser coletada e permanece com lotes, indicadores e histórico consultáveis. Use **Arquivadas → Histórico** para consultar as coletas e **Restaurar** para recolocá-la na lista. A restauração mantém a coleta desabilitada; use **Editar → Habilitada para coleta** se desejar retomá-la. A migração 0014 adiciona esse estado sem apagar registros existentes. Fontes arquivadas só aparecem na lista Arquivadas para perfis com permissão de gestão.

Uma fonte habilitada com integração compatível e sem coletas anteriores entra automaticamente na fila de primeira coleta. O serviço Docker `collector` processa essa fila no PostgreSQL; o cadastro não espera pela consulta externa. Ao iniciar, ele também inclui fontes antigas habilitadas que nunca tiveram uma tentativa. A lista de fontes atualiza o estado durante a execução. Falhas ficam no histórico para análise e não são repetidas continuamente; o administrador pode usar **Coletar agora**. O Airflow continua fazendo as coletas diárias. Após atualizar o código, rode `docker compose up --build -d` para aplicar a migração 0015 e iniciar `collector`. Confira `docker compose logs --tail=100 collector` se a primeira coleta não começar.

## Detector, alertas e comparação

Os ajustes posteriores estão em [Atualidade, acompanhamento contínuo e qualidade](ACOMPANHAMENTO_CONTINUO.md). A migração 0012 mantém as fontes existentes no modo fixo. Ao editar/cadastrar, é possível escolher o acompanhamento contínuo. O Monitoramento informa última semana, defasagem e qualidade; o sino oferece filtros por município, agravo, origem e semana.

Atualize com `docker compose up --build -d`. O serviço `detector` usa a imagem do backend e executa a fila de reanálise. A API aplica as migrações 0009–0011 antes de o worker iniciar. Sem esse serviço, novas coletas continuam analisadas, mas reanálises administrativas ficam pendentes.

Em **Administração → Detecção**, escolha método, parâmetros e se a regra será padrão ou específica para uma origem. Salvar cria uma versão e agenda a reanálise; acompanhe o resultado nessa tela. `docker compose logs --tail=100 detector` mostra o processamento. O sino no cabeçalho abre alertas e permite marcar a leitura individual. Em Monitoramento, o painel **Comparar municípios ou regiões** permite escolher de dois a quatro territórios.

## Alertas por e-mail (opcional)

Na conta de e-mail da Hostinger, em **Conecte apps e dispositivos → Outros → Configurações avançadas**, confira servidor de saída, porta e SSL/TLS. Para a caixa configurada neste ambiente: `smtp.hostinger.com`, porta `465`, segurança `ssl`, usuário e remetente `system@synaptik.cloud`. Confira esses dados no painel antes de habilitar. [Instruções da Hostinger](https://support.hostinger.com/pt/articles/1575756-como-encontrar-os-detalhes-de-configuracao-de-e-mail-no-hpanel).

No arquivo `.env` local, defina `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY` (`ssl` para 465 ou `starttls` para 587), `SMTP_USER`, `SMTP_PASSWORD` e `SMTP_FROM_EMAIL`. Coloque a senha **somente no `.env` do servidor**, nunca no Git ou no chat. Se ela contiver caracteres como `$` ou `#`, use aspas simples no valor do `.env` do Compose. `APP_PUBLIC_URL` é opcional e adiciona ao texto do e-mail o endereço público HTTPS do sistema.

Depois de salvar o `.env`, execute `docker compose up --build -d` para aplicar a migração 0013 e iniciar `mailer`. Entre como administrador, abra **Administração → E-mail** e clique **Enviar teste para meu e-mail**; o teste vai apenas para a conta administrativa e tem limite de três solicitações por 15 minutos. Depois cadastre os grupos, escolha os grupos e/ou informe e-mails individuais em **Destinatários**, salve e clique **Ativar envio**. O envio começa desativado; registros antigos e reanálises não disparam mensagens. Use **Últimos envios** e `docker compose logs --tail=100 mailer` para acompanhar o resultado. Se alterar o `.env` depois, execute `docker compose up -d --force-recreate backend mailer`.

Alertas podem se referir a anos anteriores; confira a semana informada. Para analisar o início de um crescimento, colete também histórico anterior, de preferência incluindo o ano anterior.
