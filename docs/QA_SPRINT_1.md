# QA do primeiro incremento da Sprint 1

Data: 04/10/2026. A implementação ainda não representa o encerramento completo da Sprint 1.

## Verificações realizadas

- Backend: 15 testes automatizados com banco SQLite isolado. Cobrem login/logout, sessão, inativos, credenciais inválidas, hash, unicidade de e-mail, limite de tentativas, CSRF e origens, autorização, validação, duplicidade, cadastro/edição/desabilitação, auditoria e paginação.
- Migrações: aplicação em banco SQLite novo; `makemigrations --check --dry-run` sem divergências.
- Frontend: 3 testes de API/sessão; verificação de tipos TypeScript e build Vite concluídos.
- Navegador real com API local e banco SQLite exclusivo de QA: login, listagem vazia, cadastro de fonte, edição/desabilitação, recuperação da sessão após reload e logout funcionaram.
- Inspeção visual: login e listagem em desktop; visão geral com viewport de celular (390 × 844).
- Corrigida rejeição CSRF no proxy Vite durante o teste integrado. Origens locais confiáveis são habilitadas somente em debug; teste cobre rejeição de origem externa.
- Consulta externa independente ao InfoDengue: 52 registros para dengue em São Paulo capital, semanas 1–52 de 2024. Isso valida a fonte candidata, não uma coleta automática implementada.

## Não validado nesta máquina

- Docker Compose, imagens Linux, inicialização e persistência em PostgreSQL: Docker não está instalado.
- Pipeline Airflow, pandas, reprocessamento e falhas da fonte: ainda não implementados.
- Indicadores, detector, alertas, exportação, IAM configurável e avaliação retrospectiva: próximas etapas.
- HTTPS de produção, backups automáticos, restauração e metas de desempenho: pendentes.

As evidências locais de navegador usam uma conta e um banco de QA; não criam administrador nem fonte no PostgreSQL que será usado pelo usuário. Os processos temporários de QA são encerrados ao finalizar esta entrega.

## Roteiro de aceite com Docker

1. Executar `scripts/setup.ps1`, construir/subir o compose e conferir serviços saudáveis.
2. Criar administrador com `createsuperuser`, entrar e sair.
3. Confirmar mensagem genérica com senha incorreta e bloqueio após cinco erros.
4. Cadastrar uma fonte com território; recarregar a página e conferir persistência.
5. Tentar repetir URL + território e confirmar erro sem duplicação.
6. Editar e desabilitar a fonte; confirmar estado e registro de auditoria.
7. Executar os testes com `TEST_POSTGRES=true`, conforme README.
8. Desligar com `docker compose down`, iniciar novamente e conferir persistência da conta e da fonte.
9. Validar no celular ou viewport pequeno os formulários e a tabela com rolagem horizontal.
10. Implementar e testar RF01 antes de considerar HU02 e a Sprint 1 totalmente concluídas.
