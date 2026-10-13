import {Notice,useTimedMessage} from './notifications';
import {useEffect,useState,type FormEvent} from 'react';
import {api,ApiError,type Source} from './api';

export function infoDengueParams(source?:Source) {
  if(!source)return null;
  try {const url=new URL(source.url);return url.hostname==='info.dengue.mat.br'&&url.pathname==='/api/alertcity'&&url.searchParams.get('disease')==='dengue'&&source.tipo==='json'?url.searchParams:null;}catch{return null;}
}

export function AssistedSourceForm({source,onSave,onCancel,onExpired,onManual}:{source?:Source;onSave:()=>void;onCancel:()=>void;onExpired:()=>void;onManual:()=>void}) {
  const params=infoDengueParams(source);
  const [catalog,setCatalog]=useState<{municipios:{codigo:string;nome:string}[];ano_atual:number}|null>(null);
  const [city,setCity]=useState(params?.get('geocode')||'');
  const [start,setStart]=useState(params?.get('ey_start')||'');
  const [end,setEnd]=useState(params?.get('ey_end')||'');
  const [first,setFirst]=useState(params?.get('ew_start')||'1');
  const [last,setLast]=useState(params?.get('ew_end')||'');
  const [active,setActive]=useState(source?.ativa??true);
  const [busy,setBusy]=useState(false),[error,setError]=useTimedMessage();
  useEffect(()=>{let live=true;api<typeof catalog>('/fontes/catalogo/').then(data=>{if(!live||!data)return;setCatalog(data);if(!params){setStart(String(data.ano_atual));setEnd(String(data.ano_atual));}}).catch(err=>{if(live){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof ApiError&&err.fields?Object.values(err.fields).flat().join(' '):err instanceof Error?err.message:'Não foi possível salvar a fonte.');}});return()=>{live=false;};},[]);
  async function submit(event:FormEvent){event.preventDefault();setBusy(true);setError('');try{await api(source?`/fontes/${source.id}/`:'/fontes/',source?'PUT':'POST',{provedor:'infodengue',municipio:city,ano_inicio:Number(start),ano_fim:Number(end),semana_inicio:Number(first),...(last?{semana_fim:Number(last)}:{}),ativa:active,...(source?{nome:source.nome}:{})});onSave();}catch(err){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof ApiError&&err.fields?Object.values(err.fields).flat().join(' '):err instanceof Error?err.message:'Não foi possível salvar a fonte.');}finally{setBusy(false);}}
  return <section className="card form-card"><div className="section-heading"><div><span className="eyebrow">INFODENGUE</span><h2>{source?'Editar acompanhamento':'Adicionar município'}</h2></div><button className="secondary" disabled={busy} onClick={onCancel}>Cancelar</button></div><p className="muted">Dados de dengue em São Paulo. Escolha o município e o período.</p><form onSubmit={submit}>
    <label>Município<select aria-label="Município" required value={city} disabled={!catalog||busy} onChange={e=>setCity(e.target.value)}><option value="">{catalog?'Selecione o município':'Carregando municípios…'}</option>{catalog?.municipios.map(m=><option key={m.codigo} value={m.codigo}>{m.nome}</option>)}</select></label>
    <div className="form-grid"><label>Ano inicial<input aria-label="Ano inicial" type="number" min="2010" max={catalog?.ano_atual} required value={start} onChange={e=>setStart(e.target.value)}/></label><label>Ano final<input aria-label="Ano final" type="number" min={start||2010} max={catalog?.ano_atual} required value={end} onChange={e=>setEnd(e.target.value)}/></label></div>
    <p className="muted">Até dois anos por fonte. Após salvar, use “Coletar agora” ou aguarde a coleta diária. A disponibilidade dos dados será conferida na coleta.</p>
    <details className="source-period-options"><summary>Ajustar semanas</summary><div className="form-grid"><label>Semana inicial<input type="number" min="1" max="53" required value={first} onChange={e=>setFirst(e.target.value)}/></label><label>Semana final<input type="number" min="1" max="53" placeholder="Última semana do ano" value={last} onChange={e=>setLast(e.target.value)}/></label></div></details>
    <label className="checkbox"><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>Habilitada para coleta</label>
    <Notice message={error}/><div className="source-setup-actions"><button type="button" className="text-button" disabled={busy} onClick={onManual}>Cadastrar outra fonte por URL</button><button disabled={busy||!catalog}>{busy?'Salvando…':'Salvar fonte'}</button></div>
  </form></section>;
}
