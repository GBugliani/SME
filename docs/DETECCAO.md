# Detecção configurável, alertas e comparação

Conforme HU12/RF13, HU13/RF14 e HU14/RF15 do DOCX oficial, fluxos UC12–UC15. O canal escolhido para o MVP é o painel; o RF13 admite painel, e-mail ou ambos.

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
# Executar as pendências até esvaziar a fila, sem modo contínuo:
docker compose exec backend python manage.py process_detection_jobs
```

### Alertas

O sino no cabeçalho abre os alertas. Toda conta autenticada pode consultar e marcar sua própria leitura. O botão **Marcar todas como lidas** atualiza, para a conta atual, as revisões de todas as sinalizações vigentes, inclusive as de outras páginas; alertas encerrados permanecem no histórico. O painel distingue sinalizações vigentes nos dados e encerradas por revisão ou configuração. “Vigente” descreve o resultado estatístico para a semana armazenada, não a existência de um surto em andamento hoje.

O alerta guarda município, agravo/indicador, semana, observado, referência, limiar, configuração, lote, título, mensagem e canal `painel`. A interface mostra a semana de referência, a origem e os detalhes do cálculo. Dados de 2024 continuam identificados como 2024 mesmo se coletados em 2026.

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

Trocar os filtros ou o município invalida o resultado anterior. Respostas atrasadas, inclusive após cancelar uma comparação em andamento, não restauram um gráfico de outro contexto.

Verificação da comparação em **18/10/2026**: foram reproduzidos o recorte automático pelo histórico de uma cidade e a invisibilidade de semanas isoladas. Após as correções, passaram 160 testes backend no PostgreSQL e oito testes frontend, além de sete comparações de navegador com perfil leitor em desktop 1440×1000 e celular 390×844. Os cenários incluem anos diferentes, datas explícitas/em aberto, período sem contagens, pontos isolados, zeros, lacunas, teclado, limite de seleção, regiões com cobertura parcial e resposta atrasada após cancelamento. Não houve erro JavaScript ou rolagem horizontal nos cenários verificados. As consultas QA ficaram abaixo de cinco segundos; isso não mede o servidor remoto.

O Docker local foi atualizado sem alteração de schema. A conferência de hashes confirmou 3 contas, 14 fontes e 852 registros preservados. Com as séries reais, a comparação sem datas retornou 52 semanas de São Paulo e 40 de Amparo; ao filtrar 2024, Amparo corretamente ficou sem contagens, pois seu histórico armazenado é de 2026. Scripts, capturas e evidências ficam em `.artifacts/comparison-check/`, fora do Git.

São contagens absolutas, sem normalização populacional. Uma cidade com mais casos não tem necessariamente maior risco individual. A consulta comparativa não mistura indicadores, unidades, provedores ou definições diferentes. Mouse, toque e teclado permitem consultar as semanas.

## Avaliação retrospectiva — RNF03/RNF05

Foi preservada uma resposta pública real do InfoDengue para São Paulo capital, dengue, anos de 2023 e 2024: 104 semanas, SHA-256 `a4ff778d562c196e55c01c167d690c0b392db26e95c4e6f845fa51e516192eb3`.

A referência epidemiológica independente é o [Boletim de Arboviroses da Prefeitura de São Paulo, SE 29/2024](https://drive.prefeitura.sp.gov.br/cidade/secretarias/upload/saude/BoletimArbo_SE29_24juL24.pdf), que documenta o elevado número de casos no primeiro semestre. As definições e revisões do boletim não são tratadas como equivalentes ponto a ponto à resposta do InfoDengue.

Na resposta preservada do InfoDengue, o máximo de 2024 é **85.389 casos na SE 19, iniciada em 05/05/2024**. Com os parâmetros padrão:

| Dados disponíveis ao detector | Média móvel | Mediana/MAD |
| --- | --- | --- |
| Somente 2024 | Nenhuma semana sinalizada | Nenhuma semana sinalizada |
| 2023 + 2024 | Seis semanas sinalizadas em 2024, de SE 01 a 06 | Oito semanas sinalizadas em 2024, de SE 01 a 08 |

Com o histórico anterior, o primeiro sinal de ambos é na semana de 31/12/2023, correspondente à SE 01/2024, dezoito semanas antes do pico **observado nesse arquivo**. O pico em si não foi sinalizado: o objetivo do detector é identificar crescimento relativo à referência anterior, que pode acompanhar uma alta gradual.

Este resultado não é uma estimativa de antecipação clínica de surto, sensibilidade, especificidade ou precisão. É uma avaliação retrospectiva de um episódio, com dados revisados, sem reproduzir atrasos de notificação ou revisões disponíveis em cada data histórica. O resultado negativo usando somente 2024 foi mantido; parâmetros de produção não foram ajustados para obter um resultado favorável.

Para o uso prático, é necessário coletar histórico anterior ao período de crescimento e avaliar cada agravo e origem. A janela curta pode deixar de sinalizar crescimento gradual, especialmente quando a série começa durante uma epidemia. O sistema permanece um apoio exploratório, sujeito à avaliação epidemiológica da equipe.

O comando abaixo reproduz o resultado estruturado com parâmetros, hash, pico e semanas sinalizadas. A [resposta original agregada](../backend/sme/fixtures/validation/infodengue_sp_2023_2024.json) tem atribuição à fonte e também é utilizada pelo teste automatizado, sem depender de rede.

Reprodução sem alterar o banco:

```powershell
.venv/Scripts/python.exe backend/manage.py evaluate_detector --arquivo backend/sme/fixtures/validation/infodengue_sp_2023_2024.json --url "https://info.dengue.mat.br/api/alertcity?geocode=3550308&disease=dengue&format=json&ew_start=1&ew_end=52&ey_start=2023&ey_end=2024" --municipio 3550308 --ano 2024 --saida .artifacts/avaliacao-reproduzida.json --settings=config.test_settings
```

## Atualização e aceite

Os ajustes posteriores de atualidade, período móvel, filtros de alertas e qualidade estão em [Acompanhamento contínuo](ACOMPANHAMENTO_CONTINUO.md), com a migração 0012.

Migrações 0009–0011 acrescentam alertas, leituras, fila, escopo/ativação e versão do algoritmo. A migração conserva a configuração anterior e adiciona uma reanálise inicial, executada pelo serviço `detector`. Contas, fontes, lotes e contagens não são substituídos por dados QA.

Antes de atualizar, faça backup. A equipe deve homologar a leitura de alertas, criação de versão, acompanhamento da fila e comparação com seus dados. A implementação local não confirma a configuração do servidor remoto.

## Verificação técnica

- **142 testes backend passaram no PostgreSQL**: incluem versões, permissões/CSRF, fila, recuperação, idempotência, revisões, leitura individual, comparação, migração e avaliação do arquivo real preservado. Os três testes de concorrência também passaram no PostgreSQL. Em SQLite, os demais testes passaram; concorrência foi explicitamente ignorada.
- Concorrência exercitada com duas solicitações de ativação, dois reprocessamentos e dois workers: uma ativação aceita e outra em conflito, ausência de duplicação e uma única reivindicação da tarefa.
- TypeScript, build de produção e três testes do cliente API passaram. Continua o aviso anterior de tamanho da malha municipal.
- Navegador QA em desktop 1440×1000 e celular 390×844: comparação de três municípios, leitura individual de alertas, histórico de encerrados, alteração para mediana/MAD e conclusão pela fila. Sem erro JavaScript ou rolagem horizontal nas telas verificadas. A comparação de teste ficou abaixo de cinco segundos; não representa um benchmark do servidor remoto.
- A série pública preservada foi também processada pelo comando de reprodução, com o mesmo pico e os mesmos sinais.

Após aplicar as migrações no Docker local, os snapshots confirmaram **3 contas, 14 fontes e 852 registros epidemiológicos preservados**, incluindo credenciais e contagens. A reanálise inicial concluiu 11 combinações município/indicador, com 11 alertas históricos persistidos. Reiniciar o serviço `detector` manteve integralmente configurações, tarefas e alertas, sem duplicações ou repetição da tarefa concluída. API e interface responderam no endereço local e na rede doméstica. Migrações até 0011 aplicadas, sem alterações de modelo pendentes.
