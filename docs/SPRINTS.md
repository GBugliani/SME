# Sprints e rastreabilidade

A fonte principal é `Documentacao_Software_Sistema_Monitoramento_Epidemiológico_ver4.docx`, seções 2, 3.2 e 5. O TXT é a proposta inicial. Seus números de RF diferem dos números da versão 4; este projeto usa os IDs da versão 4.

| Sprint | Período da especificação | Histórias | Entrega |
|---|---|---|---|
| 1 | 03–10/10/2026 | HU01, HU02 e QA | 10/10/2026 |
| 2 | 11–17/10/2026 | HU03, HU04, HU05, HU06, HU10, HU11 e QA | 17/10/2026 |
| 3 | 18–24/10/2026 | HU07, HU08, HU09 e QA | 24/10/2026 |
| 4 | 25/10–01/11/2026 | HU12, HU13, HU14 e QA | 02/11/2026 |

## Sprint 1 — incremento atual

| Item | Estado | Evidência / pendência |
|---|---|---|
| HU01 / RF07 / UC07 | Implementado; homologação local pendente | Login React/API, sessão, logout, rejeição de inativos e usuários desconhecidos |
| HU02 / RF02 / UC02 | Implementado; homologação local pendente | Cadastro e edição de fontes vinculadas a município ou região |
| Banco de dados | Configurado; execução PostgreSQL pendente | Modelos, migração inicial e Compose PostgreSQL |
| HU02 / RF01 / UC01 | Pendente | Escolher primeiro município/agravo; implementar adaptador e agendamento Airflow |
| QA | Parcial | Testes automatizados locais; executar Compose/PostgreSQL e roteiro manual |

O objetivo é trabalhar por incrementos dentro da sprint. A coleta é explicitamente contabilizada como pendência da Sprint 1, porque HU02 também referencia RF01. Não foi silenciosamente transferida para outra sprint.

## Próximo incremento da Sprint 1

1. Instalar/iniciar Docker e validar migrações, login e persistência reais.
2. Confirmar o recorte inicial. Proposta: dengue, um município de SP, InfoDengue.
3. Implementar adaptador de coleta e DAG Airflow com rastreio de execução, timeout e nova tentativa no ciclo seguinte.
4. Coletar dados brutos com origem e horário; a padronização e as séries consolidadas pertencem à HU03/HU04 da Sprint 2.
5. Executar QA e registrar aceite antes de iniciar a Sprint 2.

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
- Fonte de dados: InfoGripe/DATASUS são exemplos. InfoDengue é uma alternativa coerente com dengue mencionada no escopo e com as referências, ainda sujeita à decisão da equipe.
