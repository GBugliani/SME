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

Abra [SME local](http://localhost:8080). Use sempre o mesmo endereço para preservar cookies e sessão. O banco não publica uma porta na rede. A interface escuta em `127.0.0.1` e no IPv4 local `192.168.10.67`.

### Acessar pelo celular na mesma rede

Conecte o celular ao Wi-Fi do mesmo roteador do computador e abra http://192.168.10.67:8080 . O computador e o Docker precisam estar ligados. `localhost` no celular aponta para o próprio celular. A sessão do celular é independente da sessão no PC.

A configuração publica a interface somente no endereço local indicado, preservando também o acesso por `localhost`. Se o IPv4 do computador mudar, confira com `ipconfig`, atualize a segunda entrada de `frontend.ports` e o `DJANGO_ALLOWED_HOSTS` do backend no `compose.yaml`, e execute `docker compose up -d backend frontend`. Não use `*` em hosts permitidos nem encaminhe essa porta no roteador para a internet.

Se o Firewall do Windows bloquear o acesso, permita TCP 8080 para a sub-rede local no perfil da sua rede doméstica. Não é necessário publicar portas do PostgreSQL, backend ou Airflow.

## Criar usuário comum

O ambiente Docker também permite criar uma conta pela tela de login em **Criar uma conta**. Informe nome, e-mail, senha (mínimo de 12 caracteres) e confirmação. A conta recebe somente o perfil de usuário comum e entra no sistema após o cadastro. Não há confirmação de e-mail nesta versão.

Este cadastro público foi habilitado temporariamente a pedido da equipe, além do fluxo administrativo da documentação. Para removê-lo, altere `ALLOW_SELF_REGISTRATION` para `"false"` no backend do `compose.yaml` e execute `docker compose up -d backend`. O botão desaparece e a API bloqueia novos cadastros; as contas existentes continuam funcionando. O padrão do Django fora desse compose é desabilitado. Há proteção CSRF, validação de senha, unicidade de e-mail e limite de 10 tentativas de cadastro com dados válidos por 15 minutos por origem de conexão (compartilhado pelos usuários quando estão atrás do mesmo proxy).

Com o Docker ligado, execute um único comando:

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

Na interface, o ícone de perfil no canto superior abre um menu com nome/e-mail, tipo de usuário, **Alterar senha** e **Sair**. Quando nome e e-mail forem iguais, o e-mail aparece uma única vez. A alteração pela interface exige a senha atual. Para visualizar alterações após recompilar o frontend, recarregue com **Ctrl + F5**.

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

Usuários autenticados podem consultar a quantidade, a lista, os endereços públicos, os territórios, a situação e o histórico de coleta das fontes. Cadastro, edição/desabilitação e coleta manual são exclusivos do administrador. A API verifica as permissões, além de a interface ocultar os controles administrativos.
