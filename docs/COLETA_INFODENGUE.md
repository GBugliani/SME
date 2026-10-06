# Coleta InfoDengue — piloto da Sprint 1

O piloto coleta **dados brutos de dengue dos municípios de SP cadastrados e habilitados**. Não calcula indicadores, não classifica risco e não produz séries padronizadas; essas entregas pertencem à Sprint 2.

## Como usar

1. Execute `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1`. O script adiciona a credencial interna de coleta aos ambientes existentes sem trocar os demais segredos.
2. Execute `docker compose up --build -d`. O Airflow entra junto com os outros serviços; não exige instalação de Python no Windows.
3. Cadastre ou use a fonte JSON/API InfoDengue habilitada, com nome oficial do município, código IBGE de sete dígitos e UF SP.
4. Em **Fontes de dados**, clique em **Coletar agora**. O botão aparece apenas nas fontes compatíveis com o piloto. **Histórico** mostra as dez últimas execuções.
5. A coluna **Última coleta** mostra a última execução concluída (inclusive resposta vazia), enquanto uma falha fica identificada separadamente e não apaga o sucesso anterior.

Exemplo histórico validado, 52 semanas de 2024:

```text
https://info.dengue.mat.br/api/alertcity?geocode=3550308&disease=dengue&format=json&ew_start=1&ew_end=52&ey_start=2024&ey_end=2024
```

O coletor respeita o período salvo na URL. **Esse exemplo continua consultando 2024**, mesmo quando executado diariamente. Para acompanhar outro período, edite os parâmetros de ano e semana; o piloto aceita até dois anos consecutivos, sem anos futuros. Ele não altera silenciosamente a configuração cadastrada.

Alternativa pelo terminal:

```powershell
docker compose exec backend python manage.py collect_infodengue --source 1
```

Substitua 1 pelo ID da fonte. Sem `--source`, o comando processa o todas as fontes compatíveis e habilitadas, em sequência.

## Agendamento

DAG `sme_infodengue_piloto`, diariamente às **06h no fuso America/Sao_Paulo**. As execuções acontecem enquanto o Docker e o container Airflow estão ligados. `catchup=False` evita acumular todos os dias em que o computador esteve desligado; o Airflow pode executar o último intervalo elegível ao iniciar.

O Airflow chama a API interna com `COLETA_TOKEN`, separado da sessão de usuário. A rota interna não é exposta pelo Nginx. A UI do Airflow não publica porta no host.

```powershell
docker compose exec airflow airflow dags list
docker compose exec airflow airflow dags list-runs sme_infodengue_piloto
docker compose exec airflow airflow dags trigger sme_infodengue_piloto
```

Para este ambiente local usamos o modo **standalone** oficial, com metadados no volume `airflow_data`. Para produção, separar os componentes e usar PostgreSQL para os metadados, conforme `PUBLICACAO.md`.

## Dados e falhas

- `LoteColeta`: JSON bruto, fonte, URL, município, agravo, horário, quantidade e hash SHA-256. Conteúdo idêntico reutiliza o lote existente.
- `ExecucaoColeta`: início/fim, origem manual ou Airflow, resultado, mensagem e vínculo com o lote. Execuções repetidas continuam registradas.
- Resposta vazia tem status próprio: não significa zero casos.
- Erros de rede/JSON/contrato ficam registrados; próxima tentativa ocorre no próximo ciclo diário. Não há repetição imediata indiscriminada.
- Execuções concorrentes da mesma fonte são bloqueadas; execuções interrompidas há mais de dez minutos são encerradas como erro antes de tentar novamente.
- Configuração modificada ou fonte desabilitada durante a coleta faz descartar o resultado.
- Somente host/caminho oficiais; HTTPS com validação de certificado; DNS deve resolver para IP público, e a conexão é fixada no IP verificado. Redirecionamentos são rejeitados.
- Timeout de socket de 20 segundos e resposta de até 5 MB. Conferência de estrutura, município e semanas antes da persistência; a padronização completa será feita na Sprint 2.

A arquitetura mantém adaptadores separados da persistência. Adicionar agravos/fontes exige definir e testar o contrato específico. **CSV genérico, municípios fora de SP e outras doenças ainda não são coletados** pelo piloto.

## Fontes técnicas

- [InfoDengue — API e dicionário](https://info.dengue.mat.br/services/api)
- [Airflow 3.3.1 — standalone local](https://airflow.apache.org/docs/apache-airflow/3.3.1/start.html)
- [Airflow — DAGs e agendamento](https://airflow.apache.org/docs/apache-airflow/3.3.1/core-concepts/dags.html)

## Exemplo: Caraguatatuba

Nome: InfoDengue — Caraguatatuba — Dengue. Tipo: JSON/API. Território: Município. Nome do território: Caraguatatuba. Código IBGE: 3510500. UF: SP.

```text
https://info.dengue.mat.br/api/alertcity?geocode=3510500&disease=dengue&format=json&ew_start=1&ew_end=52&ey_start=2024&ey_end=2024
```

O catálogo de 645 municípios é derivado da mesma malha oficial do IBGE usada no mapa. Código e nome devem corresponder; cadastrar uma fonte não implica cobertura comprovada da API. Resposta vazia permanece distinta de zero casos.

O Airflow lista as fontes elegíveis e cria uma tarefa por fonte, com no máximo duas coletas simultâneas. Uma falha fica registrada separadamente e não impede as demais tarefas. Não há limite silencioso de cinco fontes nem consulta automática a municípios não cadastrados.
