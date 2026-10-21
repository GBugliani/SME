import type {User} from './api';

const topics = [
  ['comecar', 'Primeiros passos'],
  ['fluxo', 'Como os dados chegam'],
  ['fontes', 'Fontes de dados'],
  ['monitoramento', 'Monitoramento'],
  ['interpretacao', 'Como interpretar'],
  ['comparacao', 'Comparação territorial'],
  ['alertas', 'Alertas e exportação'],
  ['acesso', 'Acesso e administração'],
] as const;

export function HelpPage({user}: {user: User}) {
  return <section className="help-page" aria-labelledby="help-title">
    <header className="help-intro"><span className="eyebrow">AJUDA</span><h1 id="help-title">Como usar o SME</h1><p>O sistema reúne séries epidemiológicas públicas por semana, município, agravo e origem. Use esta página para entender de onde vêm os dados, como consultá-los e o que cada sinalização significa.</p></header>

    <nav className="help-index" aria-label="Assuntos da ajuda">{topics.map(([id,label])=><a key={id} href={`#${id}`}>{label}<span aria-hidden="true">↗</span></a>)}</nav>

    <section id="comecar" className="card help-section"><span className="eyebrow">01 · COMEÇAR</span><h2>Primeiros passos</h2>
      <ol className="help-steps"><li><strong>Entre com sua conta.</strong><span>Um administrador cria os usuários e define as permissões. Seu perfil atual é <strong>{user.perfil}</strong>.</span></li><li><strong>Abra Monitoramento e use Filtrar.</strong><span>Escolha município ou região imediata, agravo, origem/indicador e, se quiser, datas de início das semanas epidemiológicas.</span></li><li><strong>Leia a série e a origem.</strong><span>O gráfico mostra os casos por semana; os painéis mostram atualidade, qualidade, período e fonte dos registros.</span></li><li><strong>Explore outras consultas.</strong><span>Compare territórios, consulte alertas pelo sino e exporte dados quando seu perfil permitir.</span></li></ol>
    </section>

    <section id="fluxo" className="card help-section"><span className="eyebrow">02 · DADOS</span><h2>Como os dados chegam ao painel</h2>
      <ol className="help-steps"><li><strong>Fonte configurada</strong><span>O cadastro associa provedor, agravo e território a um acompanhamento.</span></li><li><strong>Coleta</strong><span>Uma pessoa autorizada pode usar “Coletar agora”. Com o Airflow em execução, as fontes habilitadas são consultadas diariamente às 06h, no horário de São Paulo.</span></li><li><strong>Validação e armazenamento</strong><span>O sistema preserva a origem da coleta, interpreta os registros e monta a série semanal no banco.</span></li><li><strong>Consulta e detecção</strong><span>O monitoramento usa as séries processadas. O detector configurado avalia semanas com dados suficientes e pode gerar sinalizações.</span></li></ol>
      <p className="help-note">A data em que uma fonte foi consultada é diferente da semana a que os casos se referem. Uma coleta recente pode conter dados de anos anteriores.</p>
    </section>

    <section id="fontes" className="card help-section"><span className="eyebrow">03 · CONFIGURAÇÃO</span><h2>Fontes de dados</h2>
      <p>Em <strong>Fontes de dados</strong>, todos os usuários podem pesquisar cadastros, conferir sua situação e abrir o histórico de coleta. Quem tem permissão de gestão pode cadastrar, editar e arquivar fontes. A coleta manual exige uma permissão própria.</p>
      <ul><li><strong>InfoDengue:</strong> dengue, chikungunya e zika em municípios de SP disponíveis no catálogo. O período pode ser fixo ou de acompanhamento contínuo.</li><li><strong>InfoGripe / Fiocruz:</strong> série de SRAG para São Paulo capital.</li><li><strong>SIVEP-Gripe / Ministério da Saúde:</strong> SRAG total nos municípios de SP presentes nos arquivos publicados.</li><li><strong>e-SUS Notifica / Ministério da Saúde:</strong> síndrome gripal por COVID-19, com coleta semanal por município de SP.</li><li><strong>Outra URL:</strong> pode ser registrada como referência. Ela só será coletada automaticamente depois de existir uma integração compatível; o cadastro sozinho não ativa um novo provedor.</li></ul>
      <p>A disponibilidade muda conforme a fonte, o agravo, o município e o período. Uma coleta sem registros não comprova que houve zero casos. Arquivar desliga a coleta e oculta o cadastro das listas comuns, mas preserva seu histórico. Ao restaurar, a fonte continua desabilitada até ser reativada.</p>
    </section>

    <section id="monitoramento" className="card help-section"><span className="eyebrow">04 · CONSULTA</span><h2>Monitoramento</h2>
      <p>O filtro combina <strong>recorte territorial, agravo, origem/indicador e período</strong>. “Região imediata” é um agrupamento geográfico de municípios do IBGE. A lista de opções mostra os territórios que possuem séries armazenadas para a origem escolhida.</p>
      <p>O mapa localiza o território selecionado; ele não pinta municípios por risco. Arraste para mover, use os botões de zoom, <kbd>Ctrl</kbd> + rolagem do mouse ou dois dedos em telas sensíveis ao toque. O botão de restauração volta ao enquadramento do estado.</p>
      <p>Em <strong>Evolução temporal</strong>, a linha principal representa casos observados por semana e a linha tracejada, a média das últimas quatro semanas. A faixa azul destaca as quatro semanas finais do período consultado. Passe o mouse ou toque em um ponto para ver seus valores; “Ver registros semanais” abre a tabela.</p>
      <p>Os painéis <strong>Atualidade dos dados</strong>, <strong>Qualidade da série</strong> e <strong>Origem dos dados</strong> ajudam a conferir a última semana armazenada, lacunas, cobertura, publicador, período e horário da coleta.</p>
    </section>

    <section id="interpretacao" className="card help-section"><span className="eyebrow">05 · LEITURA</span><h2>Como interpretar os números</h2>
      <ul><li><strong>Sem dados é diferente de zero:</strong> zero é uma contagem informada; uma lacuna significa que não há contagem completa disponível.</li><li><strong>Região com cobertura parcial:</strong> a soma inclui somente municípios com dados naquela origem e semana. Confira o número de municípios cobertos antes de interpretar o total regional.</li><li><strong>Casos absolutos:</strong> o gráfico e a comparação exibem contagens, não taxas ajustadas pela população. Uma contagem maior não significa necessariamente maior risco individual.</li><li><strong>Semana acima do padrão:</strong> o detector compara uma semana com seu histórico anterior. A marcação pede análise epidemiológica; não confirma surto nem diagnóstico.</li><li><strong>Atualidade:</strong> verifique a semana da série e a data da consulta à fonte separadamente. Revisões posteriores da fonte podem alterar semanas antigas.</li></ul>
    </section>

    <section id="comparacao" className="card help-section"><span className="eyebrow">06 · TERRITÓRIOS</span><h2>Comparação territorial</h2>
      <p>No fim da tela de Monitoramento, abra <strong>Escolher territórios</strong> e selecione de dois a quatro municípios ou regiões do mesmo tipo. A comparação mantém o agravo, a origem e o período do filtro principal. Sem datas definidas, usa todo o histórico disponível de cada território.</p>
      <p>As linhas compartilham a escala de casos. Lacunas não são transformadas em zero. Observe os anos e a cobertura: séries de períodos diferentes podem aparecer no mesmo gráfico sem ter semanas em comum.</p>
    </section>

    <section id="alertas" className="card help-section"><span className="eyebrow">07 · RESULTADOS</span><h2>Alertas e exportação</h2>
      <p>O <strong>sino</strong> no cabeçalho abre as sinalizações geradas pelo detector. Você pode filtrar, examinar a semana, os valores e a origem, além de marcar um alerta ou todas as sinalizações vigentes como lidas para sua própria conta. “Vigente” descreve a sinalização nos dados armazenados, não um surto em andamento hoje.</p>
      <p>Quando permitido para o perfil, <strong>Exportar</strong> baixa a consulta em CSV ou JSON agregado, ou registros brutos interpretados em JSON. O arquivo usa os filtros e os dados já armazenados; exportar não executa uma nova coleta.</p>
      <p>O envio de alertas por e-mail é opcional e precisa ser habilitado pela administração. Ela configura destinatários individuais ou grupos; ativar o envio não dispara mensagens de todo o histórico.</p>
    </section>

    <section id="acesso" className="card help-section"><span className="eyebrow">08 · CONTA</span><h2>Acesso e administração</h2>
      <p>O menu do <strong>perfil</strong>, no canto superior direito, mostra sua identificação e permite sair. Se você for administrador, também abre <strong>Administração</strong>, onde é possível gerenciar usuários, perfis de acesso, auditoria, método de detecção e e-mail. A criação de contas e a redefinição de senhas são feitas pela administração.</p>
      <p>Todo usuário autenticado pode consultar o monitoramento e as fontes. As permissões de exportar, gerenciar fontes e iniciar coletas podem variar por perfil. Se um botão de ação não aparece, confira seu perfil com o administrador.</p>
      <div className="help-permissions"><strong>Nesta sessão: {user.nome || user.email} · {user.perfil}</strong><span>{user.administrador?'Você tem acesso à administração.':'A administração de contas não está disponível para este perfil.'} {user.permissoes.includes('gerenciar_fontes')?'Pode gerenciar fontes.':'Pode consultar fontes.'} {user.permissoes.includes('coletar_dados')?'Pode iniciar coletas manuais.':''} {user.permissoes.includes('exportar_dados')?'Pode exportar dados.':''}</span></div>
    </section>

    <section className="card help-section"><span className="eyebrow">QUANDO NÃO APARECEM DADOS</span><h2>O que conferir</h2><p>Verifique se a origem e o agravo escolhidos têm uma fonte integrada, se houve coleta e processamento bem-sucedidos, se o município e as datas têm registros e se a fonte não foi arquivada. Em <strong>Fontes de dados</strong>, consulte a última coleta e o histórico; em <strong>Monitoramento</strong>, confira a cobertura e as semanas sem dados. Se a fonte externa não publicou registros para o recorte, o painel não deve inventar zeros.</p></section>
  </section>;
}
