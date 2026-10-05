# Fonte inicial para São Paulo

## Proposta

Começar com **dengue em um município do estado de São Paulo**, usando **InfoDengue**. Depois de validar coleta e série histórica, ampliar para outros municípios paulistas. A escolha do município permanece aberta; São Paulo capital foi usado apenas para verificar a API.

Não é necessário restringir o desenho do banco a SP. O custo está sobretudo em baixar/processar arquivos brutos volumosos e em repetir consultas, e não em guardar algumas centenas de observações semanais por município. Exemplo ilustrativo: 10 municípios × 52 semanas × 5 anos × 1 agravo = aproximadamente 2.600 registros. Isso não é benchmark nem garantia de tempo de resposta.

## O que foi verificado

Em 04/10/2026 foi feita uma consulta pública de dengue de São Paulo capital (IBGE 3550308) para as semanas 1 a 52 de 2024. A API respondeu com **52 registros semanais** e identificou o município como São Paulo. Nenhum dado foi importado no banco do SME.

[Consulta de amostra](https://info.dengue.mat.br/api/alertcity?geocode=3550308&disease=dengue&format=json&ew_start=1&ew_end=52&ey_start=2024&ey_end=2024)

O [serviço público](https://info.dengue.mat.br/services/api) permite filtrar município, agravo, período e formato. A [documentação da API](https://info.dengue.mat.br/services/api/doc) explica os parâmetros `geocode`, `disease`, `format`, `ew_start`, `ew_end`, `ey_start` e `ey_end`. Alguns exemplos de documentação citam Rio de Janeiro, mas a consulta de SP acima foi verificada diretamente.

## Cuidados para a integração

- Usar `casos` (notificados) como série observada inicial; manter `casos_est` (estimados pela fonte) separado.
- O InfoDengue revisa valores retrospectivamente. Recoletar uma janela histórica e fazer upsert, preservando fonte, momento e metadados de versão.
- Tratar o início da semana epidemiológica conforme a fonte, sem assumir automaticamente a semana ISO.
- Não apresentar `nivel` da fonte como resultado do detector próprio do SME.
- Preservar uma cópia/versionamento do conjunto de avaliação para reprodutibilidade do artigo. Evitar avaliar com estimativas da fonte como se fossem observações independentes.
- Validar licença, atribuição, limites de uso e estabilidade do endpoint antes da integração regular.
- Conferir cobertura e qualidade de cada município adicional; uma resposta bem-sucedida para a capital não prova cobertura completa do estado.

O endpoint de amostra tem período fixo e serve para homologação. O coletor precisará montar janelas móveis, e não repetir para sempre essa URL de 2024.

InfoGripe/SIVEP-Gripe continuam candidatos se a equipe optar por agravos respiratórios; esse caminho exige avaliação específica de formato, cobertura municipal e volume dos arquivos.
