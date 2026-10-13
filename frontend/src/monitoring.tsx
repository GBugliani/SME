import {Notice,useTimedMessage} from './notifications';
import { useEffect, useId, useLayoutEffect, useRef, useState, type FormEvent } from 'react';
import { api, ApiError } from './api';

export type Point = { data: string; ano: number | null; semana: number | null; casos: number | null; anomalia: boolean; referencia: number | null; limiar: number | null; municipios_com_dados: number };
export type Indicators = { territorio: {tipo:string; codigo:string; nome:string}; agravo:string; serie:Point[]; casos_total:number; semanas_com_dados:number; semanas_sem_dados:number; tendencia_percentual:number|null; anomalias:number; municipios_cobertos:number; municipios_regiao:number; codigos_cobertos:string[]; fontes:{id:number; nome:string; url:string}[]; coletado_em:string|null; atualizado_em:string|null; detector:{metodo:string; versao:number; parametros:Record<string,number>} };
type Options = { municipios:{codigo:string; nome:string; regiao_codigo:string}[]; regioes:{codigo:string; nome:string}[]; agravos:{codigo:string; nome:string}[] };
export const number = (value:number) => value.toLocaleString('pt-BR');
export function trend(value:number|null|undefined) {
  if (value == null) return 'Base insuficiente';
  if (Math.abs(value)<0.05) return 'Estável';
  return `${value>0?'Alta':'Queda'} de ${Math.abs(value).toLocaleString('pt-BR',{maximumFractionDigits:1})}%`;
}

export function IndicatorFilters({ onData, onExpired, refresh }: {onData:(data:Indicators|null)=>void; onExpired:()=>void; refresh:number}) {
  const [options,setOptions]=useState<Options|null>(null);
  const [type,setType]=useState('municipio');
  const [code,setCode]=useState('');
  const [disease,setDisease]=useState('dengue');
  const [start,setStart]=useState('');
  const [end,setEnd]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useTimedMessage();
  const filterDialog=useRef<HTMLDialogElement>(null);
  const [expanded,setExpanded]=useState(false);
  const requestVersion = useRef(0);
  const callback = useRef(onData); callback.current=onData;
  async function query(t:string,c:string,a:string,s:string,e:string) {
    // Mantém a consulta anterior visível até a nova estar pronta, sem desmontar o painel/mapa.
    const version=++requestVersion.current; setBusy(true); setError('');
    try {
      const params = new URLSearchParams({tipo:t,codigo:c,agravo:a});
      if(s)params.set('inicio',s); if(e)params.set('fim',e);
      const data=await api<Indicators>(`/indicadores/?${params}`);
      if(version===requestVersion.current){callback.current(data);filterDialog.current?.close();}
    } catch(err) {if(version===requestVersion.current){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof Error?err.message:'Falha na consulta.');}}
    finally {if(version===requestVersion.current)setBusy(false);}
  }
  useEffect(()=>{
    let active=true; setBusy(true);
    api<Options>('/indicadores/opcoes/').then(data=>{
      if(!active)return; setOptions(data); setStart(''); setEnd(''); setDisease('dengue');
      const first=data.municipios.find(m=>m.codigo==='3550308')||data.municipios[0];
      if(first){setType('municipio');setCode(first.codigo);void query('municipio',first.codigo,'dengue','','');}
      else {setBusy(false);callback.current(null);}
    }).catch(err=>{if(active){setBusy(false);if(err instanceof ApiError&&err.status===401)onExpired();else setError(err.message);}});
    return()=>{active=false;requestVersion.current++;};
  },[refresh]);
  const territories=type==='municipio'?options?.municipios:options?.regioes;
  function submit(event:FormEvent){event.preventDefault();void query(type,code,disease,start,end);}
  return <div className="filter-control"><button className="filter-trigger secondary" aria-haspopup="dialog" aria-expanded={expanded} onClick={()=>{filterDialog.current?.showModal();setExpanded(true);}}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="#171717"/><circle cx="15" cy="17" r="3" fill="#171717"/></svg>Filtrar</button>
  <Notice message={!expanded?error:''}/>
  <dialog ref={filterDialog} className="filter-dialog" aria-labelledby="filter-title" onClose={()=>setExpanded(false)}><div className="filter-dialog-heading"><h2 id="filter-title">Filtros</h2><button className="secondary filter-close" type="button" aria-label="Fechar filtros" onClick={()=>filterDialog.current?.close()}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div><form onSubmit={submit}>
    <label>Recorte<select aria-label="Recorte" value={type} onChange={e=>{const t=e.target.value;setType(t);setCode((t==='municipio'?options?.municipios:options?.regioes)?.[0]?.codigo||'');}}><option value="municipio">Município</option><option value="regiao">Região imediata</option></select></label>
    <label>Agravo<select aria-label="Agravo" value={disease} onChange={e=>setDisease(e.target.value)}>{options?.agravos.length?options.agravos.map(a=><option key={a.codigo} value={a.codigo}>{a.nome}</option>):<option value="dengue">Dengue</option>}</select></label>
    <label className="filter-territory">{type==='municipio'?'Município':'Região'}<select aria-label={type==='municipio'?'Município':'Região'} required value={code} onChange={e=>setCode(e.target.value)}><option value="">Selecione</option>{territories?.map(t=><option key={t.codigo} value={t.codigo}>{t.nome}</option>)}</select></label>
    <label>De<input aria-label="De" type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label>Até<input aria-label="Até" type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label>
    <small className="filter-period-note">Datas de início das semanas epidemiológicas.</small>
    <div className="filter-message"><Notice message={error}/></div>{options&&!options.municipios.length&&<p className="muted filter-message">Nenhuma série processada disponível. Cadastre uma fonte compatível e execute a coleta.</p>}
    <div className="filter-actions"><button type="button" className="secondary" onClick={()=>filterDialog.current?.close()}>Fechar</button><button disabled={busy||!code} type="submit">{busy?'Consultando…':'Aplicar filtros'}</button></div>
  </form></dialog></div>;
}

export function SeriesChart({ data }: {data:Indicators|null}) {
  const [details,setDetails]=useState(false);
  const [active,setActive]=useState<number|null>(null);
  const [cursor,setCursor]=useState<{x:number;y:number}|null>(null);
  const tooltip=useRef<HTMLDivElement>(null);
  const tooltipId=useId();
  useEffect(()=>{setActive(null);setCursor(null);},[data]);
  useLayoutEffect(()=>{
    if(cursor && tooltip.current)tooltip.current.style.top=`${Math.max(8,Math.min(cursor.y-20,innerHeight-tooltip.current.getBoundingClientRect().height-8))}px`;
  },[cursor,active]);
  if(!data||!data.serie.length)return <section className="card series-card"><span className="eyebrow">EVOLUÇÃO TEMPORAL</span><h3>Série de casos</h3><div className="chart-empty"><span>{data?'Nenhum registro no período':'Selecione uma série'}</span></div></section>;
  const points=data.serie, max=Math.max(1,...points.map(p=>p.casos??0));
  const plotLeft=84, plotRight=340, plotWidth=plotRight-plotLeft;
  const x=(i:number)=>plotLeft+i/Math.max(1,points.length-1)*plotWidth;
  const y=(v:number)=>166-v/max*140;
  let path='',previous=false;
  points.forEach((p,i)=>{if(p.casos==null){previous=false;return;}path+=`${previous?'L':'M'}${x(i)},${y(p.casos)} `;previous=true;});
  const averages=points.map((_,i)=>{const sample=points.slice(Math.max(0,i-3),i+1);return sample.length===4&&sample.every(p=>p.casos!=null)?sample.reduce((sum,p)=>sum+(p.casos??0),0)/4:null;});
  let averagePath='';previous=false;averages.forEach((v,i)=>{if(v==null){previous=false;return;}averagePath+=`${previous?'L':'M'}${x(i)},${y(v)} `;previous=true;});
  const selected=active!==null ? points[active] : null;
  function selectPoint(svg:SVGSVGElement,clientX:number,clientY:number,followCursor=false){
    const matrix=svg.getScreenCTM();if(!matrix)return;
    const position=new DOMPoint(clientX,clientY).matrixTransform(matrix.inverse());
    setActive(Math.max(0,Math.min(points.length-1,Math.round((position.x-plotLeft)/plotWidth*(points.length-1)))));
    setCursor(followCursor?{x:clientX,y:clientY}:null);
  }
  return <section className="card series-card"><span className="eyebrow">EVOLUÇÃO TEMPORAL</span><h3>{data.territorio.nome}</h3><p className="series-period">{points[0].data.split('-').reverse().join('/')} — {points.at(-1)!.data.split('-').reverse().join('/')}</p>
    <div className="chart-interaction"><svg viewBox="0 0 360 210" className="series-chart" role="img" tabIndex={0} aria-label={`Histórico de casos de dengue em ${data.territorio.nome}. Use as setas para consultar as semanas.`} aria-describedby={selected?tooltipId:undefined}
      onPointerMove={event=>{if(event.pointerType!=='touch')selectPoint(event.currentTarget,event.clientX,event.clientY,true);}}
      onPointerDown={event=>selectPoint(event.currentTarget,event.clientX,event.clientY,event.pointerType!=='touch')}
      onPointerLeave={event=>{if(event.pointerType!=='touch')setActive(null);}}
      onFocus={()=>setActive(value=>value??0)} onBlur={()=>setActive(null)}
      onKeyDown={event=>{if(['ArrowLeft','ArrowRight','Home','End','Escape'].includes(event.key)){setCursor(null);event.preventDefault();if(event.key==='Escape')setActive(null);else setActive(value=>event.key==='Home'?0:event.key==='End'?points.length-1:Math.max(0,Math.min(points.length-1,(value??0)+(event.key==='ArrowRight'?1:-1))));}}}>
      <rect x={x(Math.max(0,points.length-4))} y="26" width={plotRight-x(Math.max(0,points.length-4))} height="140" fill="#8cabee16"/>
      {[0,.5,1].map(f=><g key={f}><line x1={plotLeft} x2={plotRight} y1={y(max*f)} y2={y(max*f)} stroke="#343a45"/><text className="chart-axis-value" x={plotLeft-8} y={y(max*f)+4} textAnchor="end">{(max*f).toLocaleString('pt-BR',{notation:'compact',maximumFractionDigits:1})}</text></g>)}
      <path d={path} fill="none" stroke="#8cabee" strokeWidth="2"/><path d={averagePath} fill="none" stroke="#ddd" strokeWidth="1.5" strokeDasharray="5 4"/>
      {points.map((p,i)=>p.anomalia&&p.casos!=null?<circle key={p.data} cx={x(i)} cy={y(p.casos)} r="4" fill="#efb768"><title>{p.data}: {number(p.casos)} casos; acima do limiar {p.limiar?.toFixed(1)}</title></circle>:null)}
      {selected && active!==null && <g aria-hidden="true"><line x1={x(active)} x2={x(active)} y1="26" y2="166" stroke="#b8cbf1" strokeDasharray="3 4"/>{selected.casos!==null && <circle cx={x(active)} cy={y(selected.casos)} r="4" fill="#8cabee" stroke="#111" strokeWidth="2"/>}</g>}
      {[0,Math.floor((points.length-1)/2),points.length-1].filter((v,i,a)=>a.indexOf(v)===i).map(i=><text key={i} x={x(i)} y="192" textAnchor={i===0?'start':i===points.length-1?'end':'middle'}>{points[i].data.slice(5).split('-').reverse().join('/')}</text>)}
    </svg>{selected && active!==null && <div id={tooltipId} role="tooltip" ref={tooltip} className={`chart-tooltip ${cursor?'chart-tooltip-follow':active>=(points.length-1)/2?'chart-tooltip-right':''}`} style={cursor?{left:cursor.x-12,top:cursor.y-20,maxWidth:Math.max(1,Math.min(280,cursor.x-24))}:{left:`${x(active)/360*100}%`}}><strong>Semana de {selected.data.split('-').reverse().join('/')}</strong><dl><div><dt>Casos</dt><dd>{selected.casos===null?'Sem dados':number(selected.casos)}</dd></div><div><dt>Média de 4 semanas</dt><dd>{averages[active]===null?'Base insuficiente':averages[active]!.toLocaleString('pt-BR',{maximumFractionDigits:1})}</dd></div></dl>{selected.anomalia && <span className="anomaly-key">Acima do padrão</span>}</div>}</div><ul className="chart-legend" aria-label="Legenda do gráfico">
      <li><svg className="legend-symbol" viewBox="0 0 20 16" aria-hidden="true"><path d="M1 8h18" stroke="#8cabee" strokeWidth="2"/></svg><span>Casos notificados por semana</span></li>
      <li><svg className="legend-symbol" viewBox="0 0 20 16" aria-hidden="true"><path d="M1 8h18" stroke="#ddd" strokeWidth="2" strokeDasharray="4 3"/></svg><span>Média das últimas 4 semanas</span></li>
      <li><svg className="legend-symbol" viewBox="0 0 20 16" aria-hidden="true"><circle cx="10" cy="8" r="3.5" fill="#efb768"/></svg><span>Semana acima do padrão</span></li>
      <li><svg className="legend-symbol" viewBox="0 0 20 16" aria-hidden="true"><rect x="2" y="2" width="16" height="12" rx="2" fill="#8cabee26" stroke="#526a94"/></svg><span>Últimas 4 semanas do período</span></li>
    </ul>
    <p><strong>{trend(data.tendencia_percentual)}</strong><br/><small>Média das últimas 4 semanas comparada às 4 anteriores do período.</small></p>
    {data.semanas_sem_dados>0&&<p className="muted">{data.semanas_sem_dados} semanas sem dados completos; lacunas não representam zero casos.</p>}
    <div className="detector-note"><strong>{data.anomalias} {data.anomalias===1?'semana sinalizada':'semanas sinalizadas'}</strong><small>Sinalização estatística; não confirma surto.</small><details><summary>Critério da sinalização</summary><p>Detector exploratório: média das 8 semanas anteriores. Limiar: maior valor entre média + 3 desvios, 2 × média e 5 casos. Sem base completa, não há classificação.</p></details></div>
    <button className="text-button" onClick={()=>setDetails(v=>!v)} aria-expanded={details}>{details?'Ocultar registros':'Ver registros semanais'}</button>
    {details&&<div className="table-scroll series-records"><table><thead><tr><th>Semana</th><th>Casos</th><th>Sinalização</th></tr></thead><tbody>{points.map(p=><tr key={p.data}><td>{p.ano&&p.semana?`${p.ano} · SE ${p.semana}`:p.data}</td><td>{p.casos==null?'Sem dados':number(p.casos)}</td><td>{p.anomalia?'Acima do limiar':'—'}</td></tr>)}</tbody></table></div>}
  </section>;
}

export function PasswordDialog({onClose,onExpired}:{onClose:()=>void;onExpired:()=>void}) {
  const close=useRef(onClose);close.current=onClose;
  const [closing,setClosing]=useState(false);
  const ref=useRef<HTMLDialogElement>(null); const [old,setOld]=useState('');const [password,setPassword]=useState('');const [confirmation,setConfirmation]=useState('');const [error,setError]=useTimedMessage();const [busy,setBusy]=useState(false);const [done,setDone]=useState(false);
  useEffect(()=>{ref.current?.showModal();},[]);
  useEffect(()=>{if(!done)return;setClosing(false);const fade=setTimeout(()=>setClosing(true),4780);const timer=setTimeout(()=>close.current(),5000);return()=>{clearTimeout(fade);clearTimeout(timer);};},[done]);
  async function submit(e:FormEvent){e.preventDefault();setBusy(true);setError('');try{await api('/auth/password/','POST',{old_password:old,new_password:password,confirmation});setDone(true);setOld('');setPassword('');setConfirmation('');}catch(err){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof Error?err.message:'Não foi possível alterar a senha.');}finally{setBusy(false);}}
  return <dialog ref={ref} className="password-dialog card" aria-labelledby="password-title" onCancel={onClose}><h2 id="password-title">Alterar senha</h2>{done?<><p className={`notice ${closing?'notice-leaving':''}`} role="status">Senha alterada. Outras sessões serão encerradas ao tentar acessar o sistema.</p><button onClick={onClose}>Fechar</button></>:<form onSubmit={submit}><label>Senha atual<input type="password" autoComplete="current-password" required value={old} onChange={e=>setOld(e.target.value)}/></label><label>Nova senha<input type="password" autoComplete="new-password" minLength={12} required value={password} onChange={e=>setPassword(e.target.value)}/></label><label>Confirmar nova senha<input type="password" autoComplete="new-password" minLength={12} required value={confirmation} onChange={e=>setConfirmation(e.target.value)}/></label><Notice message={error}/><div className="form-actions"><button disabled={busy}>{busy?'Salvando…':'Salvar senha'}</button><button type="button" className="secondary" disabled={busy} onClick={onClose}>Cancelar</button></div></form>}</dialog>;
}
