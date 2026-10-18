import {useEffect,useRef,useState,type FormEvent} from 'react';
import {api,ApiError,type Integration} from './api';
import {Notice,useTimedMessage} from './notifications';
import {number,type Indicators} from './monitoring';
import {comparisonData,comparisonPeriod} from './comparison-data';

type Options={municipios:{codigo:string;nome:string;regiao_codigo:string}[];regioes:{codigo:string;nome:string}[];integracoes:Integration[]};
type Result={series:Indicators[];unidade:string;aviso:string};
const colors=['#8cabee','#e9b66e','#ba9fe7','#7bc4d2'];

export function TerritoryComparison({context,onExpired}:{context:Indicators|null;onExpired:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);const container=useRef<HTMLElement>(null);
  const [options,setOptions]=useState<Options|null>(null);const [kind,setKind]=useState('municipio');
  const [codes,setCodes]=useState<string[]>([]);const [search,setSearch]=useState('');
  const [saved,setSaved]=useState<{key:string;data:Result}|null>(null);const [busy,setBusy]=useState(false);
  const [dialogOpen,setDialogOpen]=useState(false);const requestVersion=useRef(0);
  const [error,setError]=useTimedMessage();
  const indicator=context?.integracao?.codigo;
  const contextKey=JSON.stringify([indicator,context?.agravo,context?.territorio.tipo,context?.territorio.codigo,
    context?.filtros?.inicio,context?.filtros?.fim,context?.atualizado_em,context?.detector.id]);
  const activeContext=useRef(contextKey);activeContext.current=contextKey;
  const result=saved?.key===contextKey?saved.data:null;
  const period=comparisonPeriod(context?.filtros?.inicio,context?.filtros?.fim);
  useEffect(()=>{
    let active=true;requestVersion.current++;setSaved(null);setBusy(false);setOptions(null);
    dialog.current?.close();
    api<Options>('/indicadores/opcoes/').then(data=>{if(active)setOptions(data);}).catch(e=>{if(active){if(e instanceof ApiError&&e.status===401)onExpired();else setError(e.message);}});
    return()=>{active=false;requestVersion.current++;};
  },[contextKey]);
  const integration=options?.integracoes.find(i=>i.codigo===indicator);
  const cities=options?.municipios.filter(m=>integration?.codigos_com_dados?.includes(m.codigo))||[];
  const regions=options?.regioes.filter(r=>cities.some(m=>m.regiao_codigo===r.codigo))||[];
  const territories=kind==='municipio'?cities:regions;
  const normalized=(text:string)=>text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const visible=territories.filter(t=>normalized(`${t.nome} ${t.codigo}`).includes(normalized(search)));
  function open(){setKind(context?.territorio.tipo||'municipio');setCodes(context?[context.territorio.codigo]:[]);setSearch('');setError('');setDialogOpen(true);dialog.current?.showModal();}
  async function submit(event:FormEvent){
    event.preventDefault();if(!context||!indicator)return;setBusy(true);setError('');
    const version=++requestVersion.current,key=contextKey;
    const params=new URLSearchParams({tipo:kind,codigos:codes.join(','),agravo:context.agravo,indicador:indicator});
    if(context.filtros?.inicio)params.set('inicio',context.filtros.inicio);
    if(context.filtros?.fim)params.set('fim',context.filtros.fim);
    try{const response=await api<Result>(`/indicadores/comparar/?${params}`);
      if(version!==requestVersion.current||key!==activeContext.current)return;
      setSaved({key,data:response});setBusy(false);dialog.current?.close();
      setTimeout(()=>{if(key===activeContext.current)container.current?.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});},0);
    }catch(e){if(version===requestVersion.current&&key===activeContext.current){if(e instanceof ApiError&&e.status===401)onExpired();else setError(e instanceof Error?e.message:'Falha ao comparar.');}}
    finally{if(version===requestVersion.current)setBusy(false);}
  }
  return <section ref={container} className="card comparison-panel"><div className="section-heading"><div><span className="eyebrow">COMPARAÇÃO TERRITORIAL</span><h2>Comparar municípios ou regiões</h2></div><button className="secondary" disabled={!context||cities.length<2} onClick={open}>Escolher territórios</button></div>
    <p className="muted">Compare de dois a quatro territórios com o mesmo agravo, origem e período do monitoramento.</p>
    {context&&<p className="comparison-period"><strong>Período:</strong> {period}. {!context.filtros?.inicio&&!context.filtros?.fim&&'Cada território pode ter anos diferentes armazenados.'}</p>}
    <Notice message={dialogOpen?'':error}/>
    {result?<ComparisonChart data={result}/>:<p className="muted">{context&&options&&cities.length<2?'Esta origem precisa ter dados de pelo menos dois municípios para permitir comparação.':'Escolha os territórios para visualizar as séries no mesmo gráfico.'}</p>}
    <dialog ref={dialog} className="filter-dialog comparison-dialog" aria-labelledby="comparison-title" onClose={()=>{requestVersion.current++;setBusy(false);setDialogOpen(false);}}><div className="filter-dialog-heading"><h2 id="comparison-title">Comparar territórios</h2><button className="secondary" disabled={busy} onClick={()=>dialog.current?.close()}>Fechar</button></div>
      <form onSubmit={submit}><p className="filter-message">{context?.agravo_nome} · {context?.integracao?.publicador}<br/>Período: {period}. Para ajustar, use os filtros do Monitoramento.</p><label className="filter-territory">Tipo de território<select aria-label="Tipo de território para comparar" disabled={busy} value={kind} onChange={e=>{setKind(e.target.value);setCodes([]);setSearch('');}}><option value="municipio">Municípios</option><option value="regiao">Regiões imediatas</option></select></label>
        <label className="filter-territory">Pesquisar territórios<input type="search" maxLength={150} value={search} onChange={e=>setSearch(e.target.value)}/></label>
        <fieldset className="comparison-options filter-message"><legend>Selecionados: {codes.length} de 4</legend>{visible.map(t=><label className="checkbox" key={t.codigo}><input type="checkbox" checked={codes.includes(t.codigo)} disabled={busy||(!codes.includes(t.codigo)&&codes.length>=4)} onChange={e=>setCodes(v=>e.target.checked?[...v,t.codigo]:v.filter(c=>c!==t.codigo))}/>{t.nome}</label>)}{!visible.length&&<p>Nenhum território com dados para esta origem.</p>}</fieldset>
        <div className="filter-message"><Notice message={error}/></div><div className="filter-actions"><button type="submit" disabled={busy||codes.length<2}>{busy?'Comparando…':'Comparar séries'}</button></div>
      </form>
    </dialog>
  </section>;
}

function ComparisonChart({data}:{data:Result}){
  const ref=useRef<HTMLDivElement>(null);const [width,setWidth]=useState(600);const [selectedWeek,setActive]=useState<number|null>(null);
  useEffect(()=>{const element=ref.current;if(!element)return;const observer=new ResizeObserver(([entry])=>setWidth(Math.max(280,entry.contentRect.width)));observer.observe(element);return()=>observer.disconnect();},[]);
  useEffect(()=>setActive(null),[data]);
  const {dates,maps:points,segments,commonWeeks,seriesWithData}=comparisonData(data.series);
  const active=selectedWeek!==null&&selectedWeek<dates.length?selectedWeek:null;
  const multipleYears=dates.length>0&&dates[0].slice(0,4)!==dates.at(-1)!.slice(0,4);
  const ticks=(multipleYears&&width<500?[0,dates.length-1]:[0,Math.floor((dates.length-1)/2),dates.length-1]).filter((v,i,a)=>a.indexOf(v)===i);
  const max=Math.max(1,...data.series.map(s=>Math.max(0,...s.serie.map(p=>p.casos??0))));
  const left=74,right=width-14,top=20,bottom=200;
  const x=(i:number)=>left+(dates.length>1?i/(dates.length-1):.5)*(right-left),y=(n:number)=>bottom-n/max*(bottom-top);
  return <div ref={ref} className="comparison-chart"><p><strong>{data.series[0]?.agravo_nome}</strong> · {data.series[0]?.integracao?.publicador}</p>
    {seriesWithData>0&&<p className="comparison-availability" role="status">{commonWeeks?`${commonWeeks} ${commonWeeks===1?'semana':'semanas'} com dados em todos os territórios.`:seriesWithData<2?'Apenas um território tem contagens neste período. Confira os intervalos disponíveis abaixo.':'Os territórios não têm semanas com dados em comum. O gráfico mostra os períodos distintos de cada um.'}</p>}
    {!seriesWithData?<p className="comparison-empty" role="status">Nenhum dos territórios tem contagens no período selecionado. Ajuste as datas no filtro do Monitoramento ou colete dados desse período.</p>:<><svg width="100%" height="240" viewBox={`0 0 ${width} 240`} role="img" tabIndex={0} aria-label="Comparação de casos por território. Use as setas para consultar as semanas."
      onPointerMove={e=>{const bounds=e.currentTarget.getBoundingClientRect();const cursor=(e.clientX-bounds.left)*width/bounds.width;setActive(Math.max(0,Math.min(dates.length-1,Math.round((cursor-left)/(right-left)*(dates.length-1)))));}}
      onFocus={()=>setActive(0)} onKeyDown={e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();setActive(v=>e.key==='Home'?0:e.key==='End'?dates.length-1:Math.max(0,Math.min(dates.length-1,(v??0)+(e.key==='ArrowRight'?1:-1))));}}}>
      {[0,.5,1].map(f=><g key={f}><line x1={left} x2={right} y1={y(max*f)} y2={y(max*f)} stroke="#343a45"/><text x={left-8} y={y(max*f)+4} textAnchor="end">{(max*f).toLocaleString('pt-BR',{notation:'compact',maximumFractionDigits:1})}</text></g>)}
      {segments.map((parts,s)=><g key={s} className="comparison-series" data-territory={data.series[s].territorio.codigo}>{parts.map((part,i)=>part.length===1?<circle key={i} cx={x(part[0].index)} cy={y(part[0].value)} r="4" fill={colors[s]}/>:<path key={i} d={part.map((p,j)=>`${j?'L':'M'}${x(p.index)},${y(p.value)}`).join(' ')} fill="none" stroke={colors[s]} strokeWidth="2.5"/>)}</g>)}
      {active!==null&&<line x1={x(active)} x2={x(active)} y1={top} y2={bottom} stroke="#bbb" strokeDasharray="3 4"/>}
      {ticks.map(i=><text key={i} x={x(i)} y="226" textAnchor={i===0?'start':i===dates.length-1?'end':'middle'}>{(multipleYears?dates[i]:dates[i].slice(5)).split('-').reverse().join('/')}</text>)}
    </svg>{active!==null&&<p className="comparison-week" aria-live="polite">Semana de {dates[active].split('-').reverse().join('/')}</p>}</>}
    <ul className="comparison-legend">{data.series.map((s,i)=><li key={s.territorio.codigo}><i style={{background:colors[i]}}/><div><strong>{s.territorio.nome}</strong>{active!==null&&<span>{points[i].get(dates[active])==null?'Sem dados nesta semana':`${number(points[i].get(dates[active])!)} casos`}</span>}{s.semanas_com_dados===0&&<span className="comparison-no-data">Sem contagem completa no período</span>}<small>{s.municipios_cobertos} de {s.municipios_regiao} municípios com dados · {s.semanas_com_dados} semanas completas</small><small>Histórico armazenado: {s.qualidade.inicio_historico?s.qualidade.inicio_historico.split('-').reverse().join('/'):'—'} a {s.qualidade.fim_historico?s.qualidade.fim_historico.split('-').reverse().join('/'):'—'}</small>{s.territorio.tipo==='regiao'&&s.municipios_cobertos<s.municipios_regiao&&<small>Cobertura parcial</small>}</div></li>)}</ul>
    <p className="muted">{data.aviso} Lacunas permanecem sem dados.</p>
  </div>;
}
