# Saúde das coletas

Em **Fontes de dados → Saúde das coletas**, a tela acompanha as fontes ativas,
não arquivadas e compatíveis com o coletor. As situações distinguem falha,
processamento com erro, ausência de registros, tentativa em execução e fontes
sem tentativa. Atraso é um indicador independente: usa o último sucesso ou,
enquanto não há sucesso, o cadastro. O limite padrão é de 26 horas e pode ser
alterado por `COLETA_ATRASO_HORAS` no ambiente do backend.

A DAG atual `sme_infodengue_piloto` e o arquivo `infodengue_pilot.py` são
preservados. Ela continua coletando pelo contrato existente, sem precisar ser
pausada, renomeada ou reativada nesta publicação.

Enquanto o agendamento não envia um identificador de rotina, o acompanhamento
usa as tentativas individuais das fontes. A tela informa essa limitação e não
emite aviso de falta de confirmação do agendamento. Os avisos administrativos
sobre três ou mais fontes com falha continuam ativos.

O backend também aceita registro explícito de início, fontes previstas e
encerramento por `run_id`. As confirmações de rotina só ficam disponíveis
após o recebimento de uma rotina agendada nesse contrato; execuções antigas
não são reconstruídas por aproximação dos horários.

O calendário é diário às 6h de Brasília. A tela não lê o banco do Airflow: depois de iniciado o monitoramento por rotina, a falta de um novo registro
na data prevista indica falta de confirmação. Uma rotina sem encerramento por mais de
26 horas deixa de ser apresentada como em execução. Uma tentativa de fonte sem
conclusão por mais de dez minutos é sinalizada como possível interrupção; a tela
não encerra tarefas.

## Publicação

Reconstrua backend e frontend e recrie os serviços que utilizam a imagem do
backend (`backend`, `detector`, `collector` e `mailer`). O backend aplica as
migrações automaticamente antes de iniciar; aguarde seu healthcheck antes dos
workers. Preserve o banco, os volumes e as configurações de produção. Não há
passo manual de troca da DAG.
