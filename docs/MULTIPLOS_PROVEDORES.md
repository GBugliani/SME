# Múltiplos provedores e agravos

## Integrações disponíveis

| Provedor | Agravo | Recorte implementado | Medida |
| --- | --- | --- | --- |
| InfoDengue | Dengue | Municípios do catálogo de SP | Casos notificados por semana |
| InfoDengue | Chikungunya | Municípios do catálogo de SP | Casos notificados por semana |
| InfoDengue | Zika | Municípios do catálogo de SP | Casos notificados por semana |
| InfoGripe / Fiocruz | SRAG | São Paulo capital | Casos reportados, sem exigência de febre, escala casos e grupo jurídico 0 |
| SIVEP-Gripe / Ministério da Saúde | SRAG total | Municípios de SP presentes na planilha | Casos por residência e semana de início dos sintomas |

O catálogo de municípios não garante disponibilidade para todos os agravos e períodos. Uma resposta vazia não significa zero. Estimativas da fonte são armazenadas separadamente; o gráfico e o detector usam casos observados.

O CSV InfoGripe utilizado contém capitais. Esta implementação filtra São Paulo capital; não atribui seus números ao estado inteiro. SRAG é uma síndrome: não corresponde a todos os casos de gripe ou Covid. Outros arquivos, filtros de sintomas ou vírus exigem contratos próprios.

CVE-SP, TBWEB e Seade **não estão habilitados para coleta** nesta entrega. O sistema permite registrar uma URL pública como referência, mas informa quando não existe integração automática. Esses provedores exigem validação dos arquivos e um adaptador próprio.

## Uso

1. Como administrador, abra **Fontes de dados → Cadastrar fonte**.
2. Escolha provedor, agravo e município. A URL e o formato são preenchidos automaticamente.
3. No InfoDengue, escolha período fixo (até dois anos e semanas) ou **Acompanhamento contínuo**, que consulta ano atual e anterior automaticamente. Cadastros existentes continuam fixos até serem editados.
4. No InfoGripe, o coletor lê o histórico disponível no arquivo. A seleção temporal é feita no Monitoramento.
5. No SIVEP-Gripe, escolha um ano fixo desde 2019 ou **Acompanhamento contínuo** para o ano atual. A pasta publicada mais recente do ano é descoberta automaticamente. Um ano ainda não publicado gera falha explícita e mantém o histórico. A disponibilidade é conferida na coleta.
6. Salve e use **Coletar agora**, ou aguarde o ciclo diário do Airflow, às 06h de São Paulo.
7. Em **Monitoramento → Filtrar**, escolha agravo e **Origem / indicador**. Os municípios/regiões oferecidos correspondem às séries armazenadas dessa integração.

O painel **Origem dos dados** identifica o publicador, a base original, a definição e o período. Não basta selecionar outro agravo para obter dados: ele precisa ter sido coletado e processado.

Consulte [Atualidade, acompanhamento contínuo e qualidade](ACOMPANHAMENTO_CONTINUO.md) para os períodos móveis, preservação da URL por lote e métricas de disponibilidade.

O perfil padrão Usuário consulta e exporta dados. Administradores podem delegar cadastro/edição de fontes e coleta manual a perfis personalizados. A gestão de contas e perfis permanece administrativa.

## Revisão da arquitetura

| Parte revisada | Alteração |
| --- | --- |
| Cadastro e API | Campo estável `indicador`; validação da combinação provedor/agravo/território/formato/endereço |
| Catálogo | `datasets.py` descreve publicador, base original, agravo, unidade, frequência, definição, cobertura e versão |
| Coleta | Seleção de adaptador por integração; destinos oficiais permitidos; sem execução de URLs arbitrárias |
| Normalização | Adaptadores validam seus formatos e produzem o mesmo contrato semanal de registros |
| Banco | Indicador no cadastro, lote e série; bytes originais, hash e metadados de proveniência nos novos lotes |
| Indicadores | Isolamento por indicador; fontes de provedores/definições diferentes não são somadas nem usadas para preencher lacunas |
| Interface | Cadastro de provedor/agravo, filtro de origem, rótulos dinâmicos e cobertura compatível |
| Airflow e terminal | A mesma lista de integrações habilitadas alimenta coleta manual e agendada |
| Segurança | DNS público, conexão fixada no IP, HTTPS, rejeição de redirects, tamanho limitado e permissões existentes preservadas |
| Detecção | Executada dentro de cada série; método estatístico existente mantido, sem declarar validação epidemiológica para cada novo agravo |

### Origem e revisões

- A chave do indicador representa provedor, agravo e definição. Mudança de significado exige nova chave, não alteração silenciosa de um contrato existente.
- Cada lote novo guarda o conteúdo recebido, SHA-256 original, dados interpretados, hash de deduplicação e uma cópia da definição/metadados. O hash de deduplicação considera indicador, território, conteúdo interpretado e hash original.
- A identificação de URL, território e agravo usada no reprocessamento vem do lote, não do cadastro atual. Os bytes e hashes dos lotes antigos não são fabricados: a migração marca esses lotes como legados, preservando o JSON e hash que já existiam.
- Renomear ou desabilitar uma fonte não apaga o histórico. Trocar provedor, agravo ou território depois de armazenar um lote exige cadastrar outra fonte.
- Cada ponto da API informa os IDs de fonte/lote que o compõem. A resposta também contém os metadados e hashes dos lotes usados, sem enviar os arquivos completos ao navegador.
- Entre cadastros sobrepostos do **mesmo indicador**, a revisão coletada mais recentemente prevalece por município/semana. Um reprocessamento de lote antigo não substitui um mais recente. Não há comparação automática entre indicadores diferentes.
- A data da coleta não é a data de atualização epidemiológica. Os cabeçalhos HTTP são preservados quando presentes; ETag não é uma data. Os provedores podem não informar uma data de atualização. O período efetivamente observado vem dos registros.
- Ausências no interior da série permanecem lacunas; não são preenchidas com zero. Agregações regionais informam cobertura parcial e exigem a mesma integração.
- Versões novas do arquivo podem revisar o passado. No SIVEP-Gripe, o lote é um retrato anual: a retirada de uma semana torna sua contagem nula (sem dados), preservando o original anterior. Nos demais adaptadores, retirada de semanas exige política específica.

### Operação

```powershell
docker compose up --build -d
docker compose exec backend python manage.py collect_sources
docker compose exec backend python manage.py collect_sources --source 1
docker compose exec backend python manage.py process_lotes
```

`collect_infodengue` permanece como alias histórico para `collect_sources`. O ID do DAG `sme_infodengue_piloto` foi conservado para preservar histórico e impedir dois agendamentos concorrentes; apesar do nome, ele atende todas as integrações habilitadas. Há no máximo duas tarefas de coleta simultâneas. Falhas de processamento aparecem como falha da execução, com os dados brutos mantidos para investigação.

Os arquivos originais ficam no PostgreSQL nesta etapa. Planejar retenção, capacidade e armazenamento externo antes de ampliar o volume em produção. O limite é 5 MiB por resposta InfoDengue , 8 MiB por CSV InfoGripe e 32 MiB por XLSX SIVEP-Gripe (até 256 MiB expandido). Arquivos maiores geram falha explícita, sem importação parcial.

## Adicionar uma integração

1. Verificar um arquivo real, sua licença/atribuição, definição, cobertura territorial e temporal. Não confundir base de origem e publicador.
2. Criar uma chave em `datasets.py` com definição imutável e versão do normalizador.
3. Implementar e registrar o adaptador em `get_adapter`: `validate`, `fetch` e `normalize`. O normalizador deve produzir ano, semana, início da semana, casos e estimativas separadas, sem misturar unidades ou estratos.
4. Definir o cadastro assistido em `source_setup.py`; manter destinos e recursos explicitamente permitidos.
5. Testar respostas reais, esquema alterado, duplicações, revisões, ausência de dados, DNS/redirects, permissões, agendamento e separação dos indicadores.

A estrutura atual atende séries **semanais de contagens não negativas**. Dados anuais, incidência, acumulados e ajustes negativos não devem ser forçados nesses campos: exigem uma extensão do contrato/modelo e visualização apropriada. O mapa e o catálogo territorial continuam restritos a SP.

## Armazenamento e leitura SIVEP-Gripe

O XLSX nacional é armazenado uma vez por SHA-256 em `ArquivoColeta`; lotes municipais apontam para esse original e guardam somente suas linhas interpretadas. `RecursoColeta` reutiliza downloads por até uma hora, inclusive entre processos; o horário de verificação do arquivo fica na proveniência. Após expirar, falha de rede é reportada como erro, sem apresentar cache antigo como coleta nova. Versões antigas continuam preservadas; ainda não há expurgo automático.

O adaptador lê somente a aba Município e Semana e confere a soma SP com UF e Semana. Não soma outras abas ou categorias de vírus. Códigos IBGE de seis dígitos são associados ao catálogo local de sete dígitos. Ausências são nulas, inclusive em revisões, e não contam como municípios cobertos. A semana 53/2025 é aceita pelo calendário já existente. A versão A reaparecendo após B gera revisão nova, reutilizando o original A.

A integração continua separada do InfoGripe no filtro Origem / indicador. Nenhuma fonte municipal é cadastrada automaticamente: o administrador escolhe quais acompanhar.
