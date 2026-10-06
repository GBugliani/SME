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

## Limites do primeiro incremento (04/10/2026; superados parcialmente abaixo)

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


## Segundo incremento — coleta (05/10/2026)

- Docker Desktop/WSL2 funcionando; API e PostgreSQL saudáveis. Migração 0002 aplicada sem modificar contas/fontes existentes.
- 30 testes backend passaram contra PostgreSQL real em banco de testes separado; os 15 testes anteriores continuam passando. Três testes frontend e build TypeScript/Vite aprovados.
- Coleta real da fonte existente InfoDengue/São Paulo: 52 registros semanais de 2024. Execuções manual e Airflow bem-sucedidas. Repetições registradas com reutilização de um único lote bruto.
- DAG diário às 06h, America/Sao_Paulo, ativo; nenhuma falha de importação. Verificados um ciclo agendado e um disparo manual via Airflow.
- Testes cobrem falhas/timeout, resposta vazia, payload inválido, tamanho excedido, município/período incorretos, DNS privado, redirecionamentos, duplicação, configuração alterada durante coleta e impedimento de execuções simultâneas.
- API de coleta manual e histórico exigem administrador; agendamento exige token próprio. A rota interna recebe 404 pelo proxy público.
- Navegador com banco SQLite exclusivo de QA: login, botão Coletar agora, 52 registros persistidos e histórico exibido. Desktop e celular verificados; nenhum erro JavaScript. Conta QA não foi criada no PostgreSQL do usuário.
- O Nginx foi corrigido para iniciar mesmo com o backend parado e resolver o destino nas requisições.

### Ainda fora desta entrega

- Consolidação de séries, pandas, indicadores, detector e cores de risco: Sprint 2 em diante.
- Expansão para 645 municípios e outros agravos; o mapa já possui limites municipais, mas o coletor atual atende somente São Paulo/dengue.
- Airflow de produção, retenção de lotes, backups/restore e desempenho do release.
- Homologação final e aceite da equipe: não inferidos dos testes técnicos.

## Persistência após reinício — 06/10/2026

Reiniciados os quatro containers com Docker Compose. Comparados antes/depois todos os lotes (incluindo conteúdo bruto e hash), IDs/status/horários das execuções e datas de última coleta: resultado idêntico. PostgreSQL e backend voltaram saudáveis; a API respondeu status ok pelo frontend. Esse teste verifica reinício dos containers, não substitui um teste de restauração de backup.


## Ampliação municipal — 06/10/2026

33 testes backend aprovados no PostgreSQL. Novas verificações: outro município paulista, código inexistente, nome divergente, UF incorreta, coleta de mais de cinco fontes, exclusão de fontes desabilitadas e API interna por fonte. Consulta real de Caraguatatuba (3510500): 52 registros de 2024, sem criar fonte ou lote de teste no banco do usuário. Build frontend aprovado. DAG sem erros de importação.
