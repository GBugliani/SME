# Detecção configurável, alertas e comparação

## Funcionalidades

| Entrega | Comportamento |
| --- | --- |
| Alertas | Sinalização persistente por município, indicador, semana e configuração; origem/lote preservados; leitura por usuário e revisão. |
| Configuração | Administração → Detecção: escolha de método, parâmetros, versão padrão ou específica por origem, histórico e reanálise em fila. |
| Comparação | De dois a quatro municípios ou regiões imediatas no mesmo gráfico, com agravo, indicador e período comuns. |

### Configuração da detecção

Somente administradores podem configurar métodos e solicitar reanálises. A API valida os parâmetros e usa controle de versão de base para rejeitar uma edição que ficou desatualizada. Cada gravação cria uma nova configuração; as versões anteriores permanecem para rastreabilidade. A versão do algoritmo também é persistida.

A configuração padrão atende todas as origens que não possuem configuração própria. Uma origem pode ter parâmetros específicos. **Usar configuração padrão** remove essa exceção de ativação, preservando a versão no histórico. As consultas usam a configuração ativa e a identificam na resposta e nas exportações.

São implementadas duas estratégias, ambas sem usar a semana analisada ou dados futuros na referência:

| Método | Referência das semanas anteriores | Limiar |
| --- | --- | --- |
| Média móvel e desvio padrão | Média e desvio padrão populacional da janela anterior | Maior entre média + multiplicador × desvio, razão mínima × média e piso |
| Mediana e MAD | Mediana e mediana dos desvios absolutos em relação à mediana da janela | Maior entre mediana + fator × 1,4826 × MAD, razão mínima × mediana e piso |

O sinal ocorre somente quando a contagem observada é **estritamente maior** que o limiar. É necessário ter todas as semanas da janela anterior com contagens observadas. Zero é válido; ausência de contagem ou semana interrompe a referência. Não há imputação de lacunas.

Limites administrativos: janela inteira de 4–52 semanas; multiplicador de 0,1–10; razão de 1–10; piso de 0–1.000.000 casos. Valores não finitos, booleanos, campos desconhecidos ou incompatíveis com o método são rejeitados. Os padrões anteriores foram preservados: média móvel, janela 8, multiplicador 3, razão 2 e piso 5. Escolher um método instalado e configurar seus parâmetros dispensa alteração de código; instalar uma estratégia inteiramente nova exige implementação e validação.

### Fila de reanálise

O serviço Docker `detector` executa `python manage.py process_detection_jobs --loop`, usando a mesma imagem do backend. As alterações são gravadas no PostgreSQL como `ReanaliseDeteccao`; a API retorna 202 e o painel acompanha o progresso. Reanálises não dependem de manter o navegador aberto.

- Há no máximo uma execução pendente/em andamento por configuração.
- Dois workers não podem reivindicar a mesma tarefa pendente. A análise é idempotente e atualiza o progresso por município/indicador.
- Uma execução que fica dez minutos sem atualizar progresso é considerada interrompida e volta à fila. Reinício do container pode, portanto, aguardar esse prazo antes da recuperação.
- Uma configuração substituída encerra sua tarefa como substituída. Exceções ficam registradas como falha e podem ser tentadas novamente na administração.
- A coleta do Airflow continua normalizando e analisando cada série nova; o worker atende a reanálise histórica solicitada pela administração.
- Análise e ativação de configuração compartilham um lock transacional, evitando que uma análise publique resultados de uma ativação atravessada por outra gravação. Novas coletas continuam preservadas em caso de falha da análise, conforme o fluxo de lotes existente.

Operação pelo terminal:

```powershell
docker compose up --build -d
docker compose logs --tail=100 detector
docker compose exec backend python manage.py process_detection_jobs
```

### Alertas

O sino no cabeçalho abre os alertas. Toda conta autenticada pode consultar e marcar sua própria leitura. O botão **Marcar todas como lidas** atualiza, para a conta atual, as revisões de todas as sinalizações vigentes, inclusive as de outras páginas; alertas encerrados permanecem no histórico. O painel distingue sinalizações vigentes nos dados e encerradas por revisão ou configuração. “Vigente” descreve o resultado estatístico para a semana armazenada, não a existência de um surto em andamento hoje.

O alerta guarda município, agravo/indicador, semana, observado, referência, limiar, configuração, lote, título, mensagem e canal `painel`. A interface mostra a semana de referência, a origem e os detalhes do cálculo. Ex.: Dados de 2024 continuam identificados como 2024 mesmo se coletados em 2026.

Reprocessar o mesmo lote não duplica alertas. Cadastros sobrepostos do mesmo indicador usam a mesma revisão canônica do painel: a mais recente por município/semana, sem misturar provedores. Uma alteração relevante do alerta incrementa sua revisão e exige nova leitura. A leitura é individual, não compartilhada entre os usuários.

Quando uma revisão retira a sinalização, o alerta anterior é encerrado e mantém os valores e o lote que fundamentaram aquele sinal. Uma nova configuração preserva alertas antigos no histórico e produz os novos resultados pela fila. Nenhuma anomalia implica nenhum novo alerta.

### Envio opcional por e-mail

Em **Administração → E-mail**, o administrador cadastra grupos com seus endereços, seleciona quais grupos receberão alertas e pode incluir e-mails avulsos. Um endereço que aparece em mais de um grupo ou como avulso recebe uma única mensagem por revisão. Há limite de 100 endereços por grupo e 200 destinatários únicos. A tela mostra os últimos 30 envios, falhas e a ação de tentar novamente. Essas listas e os registros de entrega só são visíveis a administradores.

As credenciais SMTP são variáveis de ambiente no servidor; a API nunca devolve a senha. O canal começa **desativado** e só pode ser habilitado quando houver SMTP e ao menos um destinatário. Acrescentar destinatários afeta alertas futuros; remover um endereço cancela suas mensagens ainda pendentes. Habilitar o canal não envia todo o histórico já armazenado. A coleta enfileira apenas sinalizações novas ou revistas de uma semana epidemiológica encerrada há no máximo 14 dias. Reanálises administrativas não enfileiram mensagens. O texto informa município, agravo, semana, contagem, referência, limiar e origem, e deixa explícito que a sinalização não confirma um surto.

O serviço Docker `mailer` processa a fila PostgreSQL fora da transação de coleta. Cada mensagem tem destinatário individual e chave única por alerta, revisão e endereço. Falhas recebem até cinco tentativas com intervalo crescente; erros terminais podem ser recolocados na fila pelo administrador. Mensagens de alerta encerrado ou substituído são canceladas antes da entrega. Desativar o canal pausa a fila. Se o processo terminar entre a aceitação pelo servidor SMTP e a gravação do sucesso, o reenvio pode produzir uma duplicata: SMTP não oferece confirmação transacional com o banco.

### Comparação de territórios

Em Monitoramento, use **Comparar municípios ou regiões → Escolher territórios**. A lista usa apenas territórios que possuem dados da origem selecionada. É possível pesquisar por nome/código e escolher até quatro territórios do mesmo tipo. A comparação utiliza o agravo, a origem e o período da consulta principal.

O período utiliza as datas efetivamente escolhidas nos filtros. Sem datas, considera todo o histórico disponível de cada território; não limita a comparação às datas do município exibido no painel principal. Datas inicial/final isoladas também são preservadas. O painel e o diálogo mostram o período utilizado.

As séries compartilham escala de casos e eixo de datas. Ausências interrompem as linhas e permanecem sem dados; não são convertidas em zero ou interpoladas. A legenda informa semanas completas e cobertura municipal. O cálculo regional exige contagem de todos os municípios cobertos naquela semana e identifica regiões com cobertura parcial.

Pontos isolados são desenhados como marcadores. O eixo mantém as semanas intermediárias mesmo entre históricos de anos diferentes e mostra os anos quando necessário. Se nenhum território tem contagens no intervalo, aparece uma mensagem em vez de eixos vazios. A legenda informa o histórico armazenado e quais territórios estão sem contagem completa no recorte. Quando os períodos não coincidem, um aviso deixa explícito que não há semanas comuns; comparar períodos distintos não equivale a comparar a mesma semana.