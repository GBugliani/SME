import type {Indicators, Point} from './monitoring';
import {number, trend} from './monitoring';

const date=(value:string|null|undefined)=>value?value.split('-').reverse().join('/'):'—';
const percent=(value:number|null|undefined)=>value==null?'—':`${value.toLocaleString('pt-BR',{maximumFractionDigits:1})}%`;
const timestamp=(value:string|null|undefined)=>value?new Date(value).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'}):'—';

export function CompactOverview({data}:{data:Indicators|null}) {
  const hasData=Boolean(data?.semanas_com_dados);
  return <section className="card compact-dashboard-card" aria-label="Resumo do monitoramento">
    <span className="eyebrow">RESUMO</span>
    <h2>{data?.territorio.nome||'Monitoramento'}{data?.agravo_nome?` · ${data.agravo_nome}`:''}</h2>
    <div className="compact-dashboard-primary"><strong>{hasData?number(data!.casos_total):'—'}</strong><span>casos no período</span></div>
    <dl className="compact-dashboard-facts">
      <div><dt>Tendência</dt><dd>{hasData?trend(data?.tendencia_percentual):'—'}</dd></div>
      <div><dt>Semanas com dados</dt><dd>{data?number(data.semanas_com_dados):'—'}</dd></div>
      <div><dt>Semanas sinalizadas</dt><dd>{hasData?number(data!.anomalias):'—'}</dd></div>
    </dl>
    <small className="compact-dashboard-note">Sinalizações estatísticas pedem investigação; não confirmam surto.</small>
  </section>;
}

export function CompactRecent({data,latestWeek}:{data:Indicators|null;latestWeek:Point|undefined}) {
  return <section className="card compact-dashboard-card" aria-label="Semana mais recente no período">
    <span className="eyebrow">SEMANA</span>
    <h2>Última contagem no período</h2>
    {latestWeek?<>
      <p className="compact-dashboard-date">{date(latestWeek.data)}</p>
      <div className="compact-dashboard-primary"><strong>{number(latestWeek.casos!)}</strong><span>casos notificados</span></div>
    </>:<p className="compact-dashboard-source">Nenhuma semana com contagem no período selecionado.</p>}
    <dl className="compact-dashboard-facts">
      <div><dt>Última semana na base</dt><dd>{date(data?.atualidade.ultima_semana_base)}</dd></div>
      <div><dt>Defasagem da base</dt><dd>{data?.atualidade.defasagem_semanas==null?'—':data.atualidade.defasagem_semanas===0?'Semana recente':`${number(data.atualidade.defasagem_semanas)} ${data.atualidade.defasagem_semanas===1?'semana':'semanas'}`}</dd></div>
    </dl>
    {data?.atualidade.periodo_historico&&<small className="compact-dashboard-note">O filtro mostra um período histórico; há dados mais recentes armazenados.</small>}
  </section>;
}

export function CompactQuality({data}:{data:Indicators|null}) {
  const quality=data?.qualidade;
  return <section className="card compact-dashboard-card" aria-label="Qualidade da série">
    <span className="eyebrow">QUALIDADE</span>
    <h2>Completude dos dados</h2>
    <div className="compact-dashboard-progress-heading"><strong>{percent(quality?.completude_percentual)}</strong><span>semanas completas</span></div>
    <div className="compact-dashboard-progress" role="meter" aria-label="Completude das semanas" aria-valuemin={0} aria-valuemax={100} aria-valuenow={quality?.completude_percentual??undefined} aria-valuetext={quality?.completude_percentual==null?'Sem dados':percent(quality.completude_percentual)}><span style={{width:`${Math.max(0,Math.min(100,quality?.completude_percentual??0))}%`}}/></div>
    <dl className="compact-dashboard-facts">
      <div><dt>Semanas completas</dt><dd>{quality?`${number(quality.semanas_completas)} / ${number(quality.semanas_esperadas)}`:'—'}</dd></div>
      <div><dt>Sem contagem completa</dt><dd>{quality?number(quality.semanas_sem_contagem_completa):'—'}</dd></div>
      <div><dt>Cobertura territorial</dt><dd>{percent(quality?.cobertura_percentual)}</dd></div>
    </dl>
    <small className="compact-dashboard-note">Ausência de dados não significa zero casos.</small>
    {data?.atualidade.ultima_semana_fechada&&<small className="compact-dashboard-note">Comparação com a semana encerrada de {date(data.atualidade.ultima_semana_fechada)}. O prazo de publicação varia por provedor.</small>}
  </section>;
}

export function CompactOrigin({data}:{data:Indicators|null}) {
  return <section className="card compact-dashboard-card" aria-label="Resumo da origem dos dados">
    <span className="eyebrow">DADOS</span>
    <h2>Origem e atualidade</h2>
    <p className="compact-dashboard-source">{data?.integracao?`${data.integracao.publicador} · ${data.integracao.indicador_nome}`:'Nenhuma série selecionada'}</p>
    <dl className="compact-dashboard-facts">
      <div><dt>Última semana na base</dt><dd>{date(data?.atualidade.ultima_semana_base)}</dd></div>
      <div><dt>Última consulta à fonte</dt><dd>{data?.atualidade.ultima_consulta_em?new Date(data.atualidade.ultima_consulta_em).toLocaleDateString('pt-BR'):'—'}</dd></div>
      <div><dt>Fontes usadas</dt><dd>{data?number(data.fontes.length):'—'}</dd></div>
    </dl>
    {data?.integracao&&<small className="compact-dashboard-note">{data.integracao.base_original} · {data.integracao.base_temporal}</small>}
  </section>;
}

export function CompactSeries({data}:{data:Indicators|null}) {
  const points=data?.serie.slice(-12)||[];
  const max=Math.max(1,...points.map(point=>point.casos??0));
  const width=300/Math.max(1,points.length);
  const barWidth=Math.min(20,width*.68);
  return <section className="card compact-dashboard-card" aria-label="Evolução das semanas recentes">
    <span className="eyebrow">EVOLUÇÃO</span>
    <h2>Últimas semanas do período</h2>
    {points.some(point=>point.casos!==null)?<>
      <svg className="compact-dashboard-chart" viewBox="0 0 300 110" role="img" aria-label="Casos semanais nas últimas 12 semanas do período; lacunas indicam semanas sem dados">
        <line x1="0" x2="300" y1="100" y2="100" stroke="#52617a"/>
        {points.map((point,index)=>point.casos===null?null:<rect key={point.data} x={index*width+(width-barWidth)/2} y={100-Math.max(1,point.casos/max*90)} width={barWidth} height={Math.max(1,point.casos/max*90)} rx="2" fill={point.anomalia?'#efb768':'#8cabee'}><title>{date(point.data)} · {number(point.casos)} casos{point.anomalia?' · acima do padrão':''}</title></rect>)}
      </svg>
      <p className="compact-dashboard-chart-range">{date(points[0]?.data)} — {date(points.at(-1)?.data)}</p>
      <small className="compact-dashboard-note">Barras mostram contagens; semanas sem dados ficam sem barra.</small>
    </>:<p className="compact-dashboard-source">Nenhuma semana com contagem no período selecionado.</p>}
  </section>;
}

export function CompactSources({data}:{data:Indicators|null}) {
  return <section className="card compact-dashboard-card compact-dashboard-sources" aria-label="Fontes da série selecionada">
    <span className="eyebrow">FONTES</span>
    <h2>Fontes da série selecionada</h2>
    {data?.fontes.length?<ul className="compact-dashboard-links">{data.fontes.map(source=><li key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.nome} ↗</a></li>)}</ul>:<p className="compact-dashboard-source">Nenhuma fonte associada à série selecionada.</p>}
    <dl className="compact-dashboard-facts">
      <div><dt>Coleta dos lotes exibidos</dt><dd>{timestamp(data?.coletado_em)}</dd></div>
      <div><dt>Processamento</dt><dd>{timestamp(data?.atualizado_em)}</dd></div>
      <div><dt>Período</dt><dd>{data?.serie.length?`${date(data.serie[0].data)} a ${date(data.serie.at(-1)!.data)}`:'Sem dados no período'}</dd></div>
      <div><dt>Última consulta à fonte</dt><dd>{timestamp(data?.atualidade.ultima_consulta_em)}</dd></div>
    </dl>
    {data?.integracao?.documentacao&&<a className="compact-dashboard-method" href={data.integracao.documentacao} target="_blank" rel="noreferrer">Metodologia da origem ↗</a>}
  </section>;
}
