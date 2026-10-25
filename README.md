# Sistema de Monitoramento Epidemiológico

## Começar no Windows

Instale o **Docker Desktop**, abra-o e aguarde o mecanismo de containers iniciar. Use containers Linux com WSL 2. O passo a passo está em [Instalação](docs/INSTALACAO.md).

No PowerShell, dentro desta pasta:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
docker compose up --build -d
docker compose exec backend python manage.py createsuperuser
```

Escolha o e-mail e a senha do administrador no terminal. Não existe senha padrão. Acesse **http://localhost:8080** e faça login.

O canal opcional de alertas por e-mail usa SMTP e destinatários individuais ou grupos gerenciados em **Administração → E-mail**. Ele inicia desativado; consulte [Instalação](docs/INSTALACAO.md#alertas-por-e-mail-opcional) para preencher o `.env` e habilitá-lo.

Ao cadastrar uma fonte habilitada e compatível, o serviço `collector` inicia sua primeira coleta em segundo plano. As atualizações posteriores seguem a rotina diária do Airflow.

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
| `infra/` | Proxy Nginx e DAG de coleta no Airflow |
| `scripts/` | Preparação e diagnóstico do ambiente |
| `docs/` | Instalação, decisões, QA e publicação |

## Documentação

- [Instalação e execução](docs/INSTALACAO.md)
- [Arquitetura e decisões](docs/ARQUITETURA.md)
- [Fontes de dados para São Paulo](docs/FONTES_SP.md)
- [Múltiplos provedores e agravos: uso, limites e validação](docs/MULTIPLOS_PROVEDORES.md)
- [Detecção e alertas](docs/DETECCAO.md)
- [Usuários, perfis e exportação](docs/IAM.md)

O [documento acadêmico](docs/Documentacao_Software_Sistema_Monitoramento_Epidemiológico.docx) reúne especificações e diagramas, que não devem ser lidos como uma transcrição literal do código. O [painel de indicadores](docs/Painel%20de%20indicadores%20epidemiológic.txt) é uma proposta inicial preservada para consulta histórica.

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
