# Sistema de Monitoramento Epidemiológico

Implementação incremental da especificação versão 4. A etapa atual é a **Sprint 1 (03 a 10/10/2026)**: acesso ao sistema, banco de dados e cadastro de fontes. O painel de séries e a detecção serão desenvolvidos nas próximas sprints.

## O que já está implementado

- Interface React em português, adaptada a celular e computador.
- Login por e-mail, logout e recuperação da sessão ao recarregar a página.
- Senhas com hash do Django, cookie de sessão HttpOnly, proteção CSRF e limite de tentativas por conta.
- Cadastro, listagem paginada, edição e habilitação/desabilitação de fontes públicas por administrador.
- Vínculo da fonte a município (código IBGE e UF) ou região.
- Validação de campos, prevenção de duplicidade e auditoria das alterações de fontes.
- Modelo e migrações PostgreSQL; containers para API, interface e banco.
- Testes automatizados de autenticação, autorização e cadastro.

A coleta automática de RF01, também relacionada à HU02, **ainda está pendente**. O cadastro não baixa nem valida o conteúdo remoto. A Sprint 1 não deve ser considerada homologada antes da integração da primeira fonte e da execução em PostgreSQL/Docker.

## Começar no Windows

Instale o **Docker Desktop**, abra-o e aguarde o mecanismo de containers iniciar. Use containers Linux com WSL 2. O passo a passo está em [Instalação](docs/INSTALACAO.md).

No PowerShell, dentro desta pasta:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
docker compose up --build -d
docker compose exec backend python manage.py createsuperuser
```

Escolha o e-mail e a senha do administrador no terminal. Não existe senha padrão. Acesse **http://localhost:8080** e faça login.

Para desligar preservando o banco:

```powershell
docker compose down
```

Não use `down -v` para desligar normalmente: essa opção apaga o volume do banco.

## Estrutura

| Pasta | Responsabilidade |
|---|---|
| `backend/` | API Django, entidades, serviços, migrações e testes |
| `frontend/` | React, TypeScript e Vite |
| `infra/` | Proxy Nginx para interface e API na mesma origem |
| `scripts/` | Preparação e diagnóstico do ambiente |
| `docs/` | Instalação, sprints, decisões, QA e publicação |
| `Diagramas/` | Diagramas originais fornecidos pela equipe |

## Documentação de trabalho

- [Instalação e execução](docs/INSTALACAO.md)
- [Sprints e rastreabilidade](docs/SPRINTS.md)
- [Arquitetura e decisões](docs/ARQUITETURA.md)
- [Fontes de dados para São Paulo](docs/FONTES_SP.md)
- [Plano de publicação](docs/PUBLICACAO.md)
- [Validação da primeira etapa](docs/QA_SPRINT_1.md)

## Testes

Com Docker já iniciado, rode os testes contra PostgreSQL:

```powershell
docker compose exec -e TEST_POSTGRES=true backend python manage.py test sme --settings=config.test_settings
docker compose exec backend python manage.py makemigrations --check --dry-run
```

Para os testes da interface com Node 24 e pnpm 11.25.0 instalados:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm test
pnpm run build
```

O compose desta etapa serve para desenvolvimento local. A estratégia de hospedagem e as pendências antes da exposição pública estão em `docs/PUBLICACAO.md`.
