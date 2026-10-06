# Sprints e rastreabilidade

A fonte principal é `Documentacao_Software_Sistema_Monitoramento_Epidemiológico_ver4.docx`, seções 2, 3.2 e 5. O TXT é a proposta inicial. Seus números de RF diferem dos números da versão 4; este projeto usa os IDs da versão 4.

| Sprint | Período da especificação | Histórias | Entrega |
|---|---|---|---|
| 1 | 03–10/10/2026 | HU01, HU02 e QA | 10/10/2026 |
| 2 | 11–17/10/2026 | HU03, HU04, HU05, HU06, HU10, HU11 e QA | 17/10/2026 |
| 3 | 18–24/10/2026 | HU07, HU08, HU09 e QA | 24/10/2026 |
| 4 | 25/10–01/11/2026 | HU12, HU13, HU14 e QA | 02/11/2026 |

## Sprint 1 — estado atual (05/10/2026)

| Item | Estado | Evidência / pendência |
|---|---|---|
| HU01 / RF07 / UC07 | Implementado | Login, sessão, logout, autorização e testes SQLite/PostgreSQL |
| HU02 / RF02 / UC02 | Implementado | Cadastro/edição/desabilitação de fontes por município ou região |
| Banco de dados | Executado em PostgreSQL/Docker | Migrações e persistência verificadas; volume preservado |
| HU02 / RF01 / UC01 | Implementado no piloto dengue/São Paulo | API InfoDengue, dados brutos, histórico e DAG Airflow diário às 06h |
| QA | Verificações técnicas realizadas; aceite da equipe pendente | 30 testes backend em PostgreSQL, 3 frontend, build e fluxo real no navegador |

A fonte previamente cadastrada foi coletada: 52 semanas de 2024. Agendamento Airflow e repetição sem duplicação foram verificados. O período é o da URL cadastrada; não equivale a acompanhamento do ano atual. Demais fontes/municípios/agravos ainda não possuem adaptador.

## Para encerrar a Sprint 1

1. A equipe confirmar o aceite do login, cadastro e coleta no seu ambiente.
2. Confirmar o período de interesse para o piloto. A fonte atual consulta 2024.
3. Seguir o roteiro e registrar o aceite em `QA_SPRINT_1.md`.

A coleta de RF01 não foi transferida para outra sprint. Normalização/pandas, séries consolidadas e indicadores permanecem em HU03/HU04 da Sprint 2. Referência operacional: `COLETA_INFODENGUE.md`.

## Planejamento das próximas sprints

- Sprint 2: pandas, validação/padronização por semana epidemiológica, persistência de séries, filtros, consulta/histórico, tendência, reforço de autenticação e primeiro detector de anomalias (HU11).
- Sprint 3: gerenciamento de usuários, perfis/permissões e exportação estruturada.
- Sprint 4: alertas no painel/e-mail opcional, configuração versionada do detector, comparação de territórios, avaliação retrospectiva, desempenho e preparação do release.

O detector básico está na Sprint 2 (HU11), apesar do objetivo da Sprint 4 mencionar detecção. Na Sprint 4 entram configuração e alertas, seguindo a distribuição das histórias. Controles mínimos de senha, CSRF e autorização são necessários desde o login; isso não representa conclusão antecipada de HU06/HU07.

## Divergências e decisões

- Desempenho: TXT diz 3 segundos; Word v4 diz 5. Vale o Word. O RNF06 “independente do volume” precisa de um volume e carga de teste definidos para ser verificável; ainda não foi alegado como atendido.
- Cadastro de usuários: HU08 menciona usuário, mas UC09 restringe a administrador. Será usado cadastro administrativo, coerente com acesso previamente autorizado.
- Airflow: adotado pelo Word, apesar de o TXT sugerir Airflow ou cron.
- O release está indicado em 02/11, um dia após o fim do período da Sprint 4. Datas foram preservadas.
- Fonte de dados: InfoGripe/DATASUS são exemplos. InfoDengue foi adotado para o piloto autorizado de dengue em São Paulo; outras fontes exigem adaptadores próprios.

## Ampliação da coleta — 06/10/2026

O coletor de dengue do InfoDengue agora aceita os municípios de SP, validando nome e código IBGE no catálogo de 645 municípios. Apenas fontes cadastradas, compatíveis e habilitadas são consultadas. O Airflow executa uma tarefa por fonte, com até duas coletas simultâneas; a restrição anterior à capital e a cinco fontes foi removida. Outros agravos e provedores continuam exigindo integração própria. Consulte [o guia de coleta](COLETA_INFODENGUE.md).
