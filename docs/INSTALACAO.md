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

Abra [SME local](http://localhost:8080). Use sempre o mesmo endereço para preservar cookies e sessão. O banco não publica uma porta na rede e a interface escuta apenas em `127.0.0.1`.

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
# Alterar a senha do administrador
docker compose exec backend python manage.py changepassword seu-email@exemplo.com
```

Se a porta 8080 estiver ocupada, altere no compose o lado esquerdo de `127.0.0.1:8080:80`, por exemplo para `127.0.0.1:8081:80`, e use a nova porta no navegador. Se houver falha de conexão com o Docker, abra o aplicativo antes de repetir o comando. Não apague o volume para resolver falhas de inicialização.

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

## Diagnóstico nesta entrega

Em 04/10/2026, Git foi encontrado. Docker, Python e npm próprios do usuário não estavam disponíveis no PATH verificado. Foram usados Python 3.12 e Node 24 internos do Codex para preparar dependências e testar; esses runtimes não substituem uma instalação de desenvolvimento independente. Nenhum instalador de sistema foi executado.

Airflow já faz parte do Docker Compose e agenda a coleta do piloto diariamente às 06h, com o Docker em execução. Não é necessário instalar Airflow no Windows. Veja o [guia de coleta](COLETA_INFODENGUE.md). O processamento com pandas fica para a Sprint 2.
