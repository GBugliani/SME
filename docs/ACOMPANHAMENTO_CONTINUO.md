# Atualidade, acompanhamento contínuo, alertas e qualidade

## Atualidade dos dados

O Monitoramento distingue:

- **Última semana na base:** semana mais recente com contagem para a origem e território, inclusive fora do filtro histórico. Em uma região, pode corresponder a apenas parte dos municípios.
- **Coleta dos lotes exibidos:** criação do lote mais recente que fundamenta os registros do período selecionado.
- **Última consulta bem-sucedida à fonte:** última consulta das fontes que fundamentam a série, mesmo se o conteúdo já estava armazenado. Não substitui a semana epidemiológica.

A defasagem é a distância em semanas entre a última semana na base e a última semana encerrada, no fuso do projeto. A semana em andamento não é exigida. Sem contagens, a defasagem fica indisponível; zero é uma contagem válida. A partir de quatro semanas o marcador recebe destaque visual apenas como referência de leitura: não é um prazo de publicação garantido ou uma avaliação do provedor.

Um aviso diferencia um filtro histórico de uma base com semanas mais recentes. Filtrar 2024 não altera a data mais recente armazenada da mesma série.

## Período de coleta

Em **Fontes de dados → Cadastrar fonte/Editar → Período de coleta**, escolha:

| Modo / provedor | Comportamento |
| --- | --- |
| Período fixo | Mantém os anos e semanas escolhidos. |
| Acompanhamento contínuo / InfoDengue | Ano atual e anterior, todas as semanas, resolvidos a cada execução. |
| Acompanhamento contínuo / SIVEP-Gripe | Ano atual, versão publicada mais recente. Não coleta automaticamente o ano anterior. |
| InfoGripe | Consulta todo o histórico do CSV; não precisa de um seletor móvel. |

Exemplo: no InfoDengue uma coleta contínua em 2026 consulta 2025–2026; em 2027 passa a consultar 2026–2027. Semanas 52/53 seguem o calendário epidemiológico do ano. Isso não garante que a fonte já tenha publicado todas as semanas solicitadas ou dados de todos os agravos/municípios.

O Airflow usa o mesmo resolvedor da coleta manual. Cadastrar uma fonte habilitada agenda a primeira coleta no worker `collector`; a lista mostra quando ela está agendada ou em execução. Fontes habilitadas já cadastradas e ainda sem tentativa também entram na fila quando o worker inicia. As coletas seguintes continuam na rotina diária do Airflow, às 06h de São Paulo, ou podem ser iniciadas com **Coletar agora**. No SIVEP, se o ano atual ainda não foi publicado, a tentativa falha explicitamente e mantém o histórico, sem preencher zeros nem apresentar o ano anterior como atual. Para coletar/revisar anos anteriores, use um acompanhamento fixo.

### Preservação e migração

A migração **0012** acrescenta `periodo_movel=False` às fontes existentes. Nenhuma muda automaticamente de período. Edite a fonte desejada para habilitar o acompanhamento contínuo.

Cada lote guarda a URL efetivamente consultada e o modo utilizado. A configuração não é reescrita a cada janeiro. Lotes antigos e semanas anteriores ao período móvel são mantidos; o reprocessamento utiliza os anos e a URL do próprio lote. As validações de destino HTTPS, território, agravo e conteúdo continuam aplicadas.

Só pode existir um acompanhamento contínuo por município/indicador. A restrição anterior de URL/território continua: prefira editar a fonte existente para evitar cadastros duplicados. Fontes com histórico não podem mudar de provedor, agravo ou território.

## Filtros de alertas

No sino do cabeçalho, combine município, agravo, origem/indicador e datas, e use **Aplicar filtros**. **Limpar filtros** mantém apenas a situação escolhida. As datas são os inícios das semanas epidemiológicas, com limites inclusivos; não são as datas de coleta/criação do alerta.

As opções incluem sinalizações encerradas. Toda conta autenticada pode consultar; a leitura continua individual. O contador do cabeçalho representa todos os alertas vigentes não lidos, independentemente do filtro da lista.

API: `GET /api/alertas/?codigo=3550308&agravo=dengue&indicador=infodengue_dengue&inicio=2024-01-01&fim=2024-12-31`. Opções: `GET /api/alertas/opcoes/`, com autenticação. `nao_lidas` representa o recorte; `nao_lidas_total` representa todos os vigentes não lidos.

## Qualidade da série

No período selecionado, o painel mostra semanas completas/esperadas, completude percentual, semanas sem contagem completa, cobertura municipal e semanas avaliáveis pelo detector. Inclui lacunas internas e nas bordas explicitamente solicitadas; as datas se alinham aos domingos de início das semanas. Uma consulta sem registros pode mostrar lacunas no painel, mas continua sem exportação de registros inexistentes.

Uma semana regional completa exige contagens de todos os municípios que possuem alguma contagem no histórico da série. Não implica cobertura de toda a região: cobertura territorial é informada separadamente. Não há imputação de zeros.

A avaliação exige a janela configurada de semanas anteriores consecutivas, além da contagem atual. Semanas anteriores ao filtro podem compor a referência. Uma lacuna interrompe a janela; semanas sem base suficiente não devem ser interpretadas como normais. O painel informa também o intervalo do histórico armazenado. Essas métricas não medem precisão clínica do detector.

## Atualização e verificação

Após backup, execute `docker compose up --build -d`. A API aplica a migração 0012 antes de os serviços dependentes iniciarem; backend e worker precisam usar a imagem atualizada.

`backend/sme/test_monitoring_improvements.py` cobre período fixo/móvel, virada de ano/semana 53, origem imutável, deduplicação, reprocessamento, falhas, SIVEP sem publicação, zeros, lacunas, janela histórica, atualidade e filtros com autorização.

```powershell
docker compose run --rm --no-deps -e TEST_POSTGRES=true backend python manage.py test sme --settings=config.test_settings --noinput
```

Os testes usam banco separado. Essa entrega não configura o servidor remoto nem habilita backups automáticos.
