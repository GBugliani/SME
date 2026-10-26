import type {Indicators} from './monitoring';

const day=(value:string|null)=>value?value.split('-').reverse().join('/'):'Sem dados';
const percent=(value:number|null)=>value===null?'—':`${value.toLocaleString('pt-BR')}%`;

export function DataFreshness({data}:{data:Indicators}){
  const a=data.atualidade;
  return <section className="card data-freshness" aria-label="Atualidade dos dados"><div className="section-heading"><h3>Atualidade dos dados</h3></div>
    <p className="muted">Última semana na base</p><strong className="freshness-date">{day(a.ultima_semana_base)}</strong>
    <p><span className={`badge ${a.defasagem_semanas!==null&&a.defasagem_semanas>=4?'data-age-warning':'inactive'}`}>{a.defasagem_semanas===null?'Sem contagens disponíveis':a.defasagem_semanas===0?'Semana recente':`${a.defasagem_semanas} ${a.defasagem_semanas===1?'semana':'semanas'} de defasagem`}</span></p>
    {a.periodo_historico&&<p>O filtro mostra um período histórico. Há semanas mais recentes armazenadas nesta origem e território.</p>}
    {data.territorio.tipo==='regiao'&&<small>A última semana pode estar disponível apenas em parte dos municípios.</small>}
  </section>;
}

export function DataQuality({data}:{data:Indicators}){
  const q=data.qualidade;
  return <section className="card data-quality" aria-label="Qualidade da série"><div className="section-heading"><h3>Qualidade da série</h3></div>
    <dl className="quality-metrics"><div><dt>Semanas completas</dt><dd>{q.semanas_completas} / {q.semanas_esperadas} <small>({percent(q.completude_percentual)})</small></dd></div>
      <div><dt>Semanas sem contagem completa</dt><dd>{q.semanas_sem_contagem_completa}</dd></div>
      <div><dt>Municípios com dados</dt><dd>{q.municipios_com_dados} / {q.municipios_previstos} <small>({percent(q.cobertura_percentual)})</small></dd></div>
      <div><dt>Semanas avaliáveis pelo detector</dt><dd>{q.semanas_avaliaveis} / {q.semanas_completas}</dd></div>
      <div><dt>Com dados, sem base suficiente</dt><dd>{q.semanas_com_dados_sem_base}</dd></div>
      <div><dt>Histórico armazenado</dt><dd>{day(q.inicio_historico)} a {day(q.fim_historico)}</dd></div></dl>
    <p className="muted">Semana completa tem contagem em todos os municípios cobertos. Cobertura territorial é mostrada à parte; ausência de dados não é zero.</p>
    <details><summary>Histórico para detecção</summary><p>O método precisa de {q.janela_deteccao} semanas anteriores consecutivas com dados. A referência pode utilizar semanas anteriores ao filtro. Uma semana sem base suficiente não é classificada como normal.</p></details>
  </section>;
}
