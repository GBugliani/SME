# Fontes para São Paulo

## Escopo atual

O piloto começou com **dengue em São Paulo capital**, usando **InfoDengue**, e já foi ampliado para os municípios paulistas do catálogo de 645 municípios do IBGE. Apenas fontes cadastradas, compatíveis e habilitadas são coletadas.

O sistema também integra **chikungunya e zika pelo InfoDengue**, **SRAG de São Paulo capital pelo InfoGripe**, **SRAG total municipal pelo SIVEP-Gripe** e **síndrome gripal por COVID-19 pelo e-SUS Notifica**. Nas duas fontes do Ministério da Saúde, o administrador escolhe os municípios paulistas e um ano fixo ou acompanhamento contínuo; dados só aparecem quando a fonte tem registros publicados e foi coletada. Veja [Múltiplos provedores e agravos](MULTIPLOS_PROVEDORES.md) para definições e limites.

Como administrador, escolha provedor, agravo, município e, no InfoDengue, anos em **Fontes de dados → Cadastrar fonte**. A URL, o código IBGE e o nome são preenchidos pelo sistema. O campo **Pesquisar fontes** localiza cadastros por município, código IBGE, UF, nome ou termos da URL; o resultado é paginado. Usuários comuns também podem pesquisar e consultar, sem editar ou coletar manualmente.

## O que foi verificado

Veja o [Guia de integrações](MULTIPLOS_PROVEDORES.md) e [Consulta de amostra](https://info.dengue.mat.br/api/alertcity?geocode=3550308&disease=dengue&format=json&ew_start=1&ew_end=52&ey_start=2024&ey_end=2024).

O [serviço público](https://info.dengue.mat.br/services/api) permite filtrar município, agravo, período e formato. A [documentação da API](https://info.dengue.mat.br/services/api/doc) explica os parâmetros `geocode`, `disease`, `format`, `ew_start`, `ew_end`, `ey_start` e `ey_end`.

## Cuidados para a integração

- Usar `casos` (notificados) como série observada inicial; manter `casos_est` (estimados pela fonte) separado.
- O InfoDengue revisa valores retrospectivamente. Recoletar uma janela histórica e fazer upsert, preservando fonte, momento e metadados de versão.
- Tratar o início da semana epidemiológica conforme a fonte, sem assumir automaticamente a semana ISO.
- Não apresentar `nivel` da fonte como resultado do detector próprio do SME.
- Preservar uma cópia/versionamento do conjunto de avaliação para reprodutibilidade do artigo. Evitar avaliar com estimativas da fonte como se fossem observações independentes.
- Validar licença, atribuição, limites de uso e estabilidade do endpoint antes da integração regular.
- Conferir cobertura e qualidade de cada município adicional; uma resposta bem-sucedida para a capital não prova cobertura completa do estado.

O endpoint de amostra acima tem período fixo e serve para homologação. O coletor respeita o período cadastrado. Para acompanhar publicações novas, o administrador pode escolher **Acompanhamento contínuo**: no InfoDengue, ele consulta o ano atual e o anterior em cada execução. Isso não garante que a fonte já tenha publicado todas as semanas solicitadas.
