# Plano de publicação

## Direção proposta

Publicar os containers da aplicação em ambiente Linux, com domínio e HTTPS. Manter React e `/api/` na mesma origem. PostgreSQL deve ser privado; Airflow e seus componentes administrativos não devem ser acessíveis ao público. A separação segue os diagramas de aplicação, processamento e dados.

Para uma demonstração acadêmica, um servidor Linux com containers pode concentrar os serviços. Para uso contínuo, banco gerenciado e processamento separado simplificam backups e isolamento. O provedor será escolhido perto da publicação, a partir de orçamento, memória real consumida pelo Airflow, retenção e público esperado. Não há estimativa de preço nem contratação nesta entrega.

## O que está preparado

- Imagens separadas da API e do frontend.
- Banco PostgreSQL e migrações versionadas.
- Segredos por variáveis de ambiente.
- API com processo Gunicorn e endpoint de saúde que consulta o banco.
- Defaults de HTTPS e cookies seguros quando `DJANGO_DEBUG` não está habilitado.

`compose.yaml` foi criado para uso local: debug habilitado, HTTP em localhost e migração ao iniciar. **Não reutilizar esse arquivo diretamente como configuração de produção.**

## Antes do primeiro ambiente online

1. Concluir e homologar o incremento de coleta da Sprint 1 e as funcionalidades necessárias ao público que terá acesso.
2. Criar configuração de produção com `DJANGO_DEBUG=false`, hosts explícitos e segredos exclusivos.
3. Configurar TLS no proxy. Se TLS terminar em proxy confiável, ele deve sobrescrever `X-Forwarded-Proto`; só então habilitar `TRUST_PROXY=true`. O Nginx local sobrescreve o header com seu próprio esquema HTTP e precisa de configuração específica para uma cadeia de proxies em produção.
4. Executar `python manage.py check --deploy` e resolver avisos aplicáveis. Aplicar migrações como etapa única de release, antes de escalar réplicas.
5. Configurar backup diário automático (RNF09), retenção e cópia fora do servidor. Testar restauração e registrar resultado; um volume persistente não é backup.
6. Manter banco e Airflow em rede privada, adicionar limite de login por origem e limpar tentativas expiradas/sessões antigas.
7. Registrar logs sem senhas ou tokens; monitorar saúde da API, falhas de coleta, atraso de atualização e uso de disco.
8. Validar cargas e tempo de resposta com séries reais, quantidade de municípios e concorrência definidos. O limite de 5 segundos será medido nesse cenário.
9. Criar ambiente de homologação separado, publicar versão identificável e documentar rollback de aplicação compatível com migrações.
10. Definir responsáveis por usuários, operação e verificação dos alertas antes do release do MVP.

Referência técnica: [checklist de publicação do Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/). A publicação e os backups automáticos ainda não foram executados.


## Airflow do piloto local

O compose agora inclui Airflow 3.3.1 em modo standalone, sem porta publicada, com metadados no volume `airflow_data`. Antes de hospedar, separar scheduler/API/dag-processor e migrar metadados para PostgreSQL, dimensionar workers, monitorar falhas, definir retenção dos lotes brutos e guardar `COLETA_TOKEN` no gerenciador de segredos. A execução local validada não representa uma implantação de produção.
