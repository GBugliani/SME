import {Notice,useTimedMessage} from './notifications';
import {useEffect,useState,type FormEvent} from 'react';
import {api,ApiError,type Source,type Integration} from './api';

export function infoDengueParams(source?:Source) {
  if(!source)return null;
  try {const url=new URL(source.url);return url.hostname==='info.dengue.mat.br'&&url.pathname==='/api/alertcity'&&source.tipo==='json'?url.searchParams:null;}catch{return null;}
}

export function AssistedSourceForm({source,onSave,onCancel,onExpired,onManual}:{source?:Source;onSave:()=>void;onCancel:()=>void;onExpired:()=>void;onManual:()=>void}) {
  const params=infoDengueParams(source);
  const sivepYear=source?.integracao?.provedor==='sivep'?new URL(source.url).searchParams.get('ano'):null;
  const [catalog,setCatalog]=useState<{municipios:{codigo:string;nome:string}[];ano_atual:number;integracoes:Integration[]}|null>(null);
  const [provider,setProvider]=useState(source?.integracao?.provedor||'infodengue');
  const [disease,setDisease]=useState(source?.integracao?.agravo||params?.get('disease')||'dengue');
  const [city,setCity]=useState(source?.recorte_codigo||params?.get('geocode')||'');
  const [start,setStart]=useState(sivepYear||params?.get('ey_start')||'');
  const [end,setEnd]=useState(params?.get('ey_end')||'');
  const [first,setFirst]=useState(params?.get('ew_start')||'1');
  const [last,setLast]=useState(params?.get('ew_end')||'');
  const [active,setActive]=useState(source?.ativa??true);
  const [rolling,setRolling]=useState(source?.periodo_movel??false);
  const [busy,setBusy]=useState(false),[error,setError]=useTimedMessage();
  const contracts=catalog?.integracoes.filter(i=>i.provedor===provider)||[];
  const contract=contracts.find(i=>i.agravo===disease);
  const cities=catalog?.municipios.filter(m=>contract?.municipios==='SP'||contract?.municipios.includes(m.codigo));
  const locked=Boolean(source?.ultima_coleta_em);
  const providers=[...new Map(catalog?.integracoes.map(i=>[i.provedor,i.publicador])).entries()];
  function changeProvider(value:string){setProvider(value);const next=catalog?.integracoes.find(i=>i.provedor===value);setDisease(next?.agravo||'');setCity(next?.municipios==='SP'?'':next?.municipios[0]||'');}
  useEffect(()=>{let live=true;api<typeof catalog>('/fontes/catalogo/').then(data=>{if(!live||!data)return;setCatalog(data);if(!params&&!sivepYear){setStart(String(data.ano_atual));setEnd(String(data.ano_atual));}}).catch(err=>{if(live){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof ApiError&&err.fields?Object.values(err.fields).flat().join(' '):err instanceof Error?err.message:'Não foi possível salvar a fonte.');}});return()=>{live=false;};},[]);
  async function submit(event:FormEvent){event.preventDefault();setBusy(true);setError('');try{await api(source?`/fontes/${source.id}/`:'/fontes/',source?'PUT':'POST',{provedor:provider,agravo:disease,municipio:city,periodo_movel:provider!=='infogripe'&&rolling,ano_inicio:Number(start),ano_fim:Number(end),semana_inicio:Number(first),...(last?{semana_fim:Number(last)}:{}),ativa:active,...(source?{nome:source.nome}:{})});onSave();}catch(err){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof ApiError&&err.fields?Object.values(err.fields).flat().join(' '):err instanceof Error?err.message:'Não foi possível salvar a fonte.');}finally{setBusy(false);}}
  return <section className="card form-card"><div className="section-heading"><div><span className="eyebrow">FONTES DE DADOS</span><h2>{source?'Editar acompanhamento':'Adicionar acompanhamento'}</h2></div><button className="secondary" disabled={busy} onClick={onCancel}>Cancelar</button></div><form onSubmit={submit}>
    <div className="form-grid"><label>Provedor<select aria-label="Provedor" required disabled={busy||locked||!catalog} value={provider} onChange={e=>changeProvider(e.target.value)}>{providers.map(([code,name])=><option key={code} value={code}>{name}</option>)}</select></label>
    <label>Agravo<select aria-label="Agravo" required disabled={busy||locked||!catalog} value={disease} onChange={e=>setDisease(e.target.value)}>{contracts.map(i=><option key={i.codigo} value={i.agravo}>{i.agravo_nome}</option>)}</select></label></div>

    <label>Município<select aria-label="Município" required value={city} disabled={!catalog||busy||locked} onChange={e=>setCity(e.target.value)}><option value="">{catalog?'Selecione o município':'Carregando municípios…'}</option>{cities?.map(m=><option key={m.codigo} value={m.codigo}>{m.nome}</option>)}</select></label>
    {locked&&<p className="muted">Para mudar o provedor, agravo ou município, cadastre outra fonte. O histórico desta fonte será preservado.</p>}
    {contract&&<p className="muted">{contract.indicador_nome} · Base: {contract.base_original}. {contract.definicao}</p>}
    {provider!=='infogripe'&&<><label>Período de coleta<select aria-label="Período de coleta" disabled={busy} value={rolling?'movel':'fixo'} onChange={e=>setRolling(e.target.value==='movel')}><option value="fixo">Período fixo</option><option value="movel">Acompanhamento contínuo</option></select></label>{rolling&&<p className="muted">{provider==='infodengue'?'Consulta o ano atual e o anterior, em todas as semanas.':'Consulta o ano atual na versão publicada mais recente. Se o ano ainda não foi publicado, a tentativa fica registrada como falha.'} Os anos avançam automaticamente a cada coleta. O histórico já armazenado é mantido. Após salvar, use “Coletar agora” ou aguarde a coleta diária.</p>}</>}
    {provider==='infodengue'&&!rolling?<><div className="form-grid"><label>Ano inicial<input aria-label="Ano inicial" type="number" min="2010" max={catalog?.ano_atual} required value={start} onChange={e=>setStart(e.target.value)}/></label><label>Ano final<input aria-label="Ano final" type="number" min={start||2010} max={catalog?.ano_atual} required value={end} onChange={e=>setEnd(e.target.value)}/></label></div>
    <p className="muted">Até dois anos por fonte. Após salvar, use “Coletar agora” ou aguarde a coleta diária. A disponibilidade dos dados será conferida na coleta.</p>
    <details className="source-period-options"><summary>Ajustar semanas</summary><div className="form-grid"><label>Semana inicial<input type="number" min="1" max="53" required value={first} onChange={e=>setFirst(e.target.value)}/></label><label>Semana final<input type="number" min="1" max="53" placeholder="Última semana do ano" value={last} onChange={e=>setLast(e.target.value)}/></label></div></details></>:provider==='sivep'&&!rolling?<><label>Ano<input aria-label="Ano" type="number" min="2019" max={catalog?.ano_atual} required value={start} onChange={e=>setStart(e.target.value)}/></label><p className="muted">Um ano por acompanhamento. A coleta busca a versão publicada mais recente desse ano. Semanas e municípios sem registros ficam sem dados. Após salvar, use “Coletar agora” ou aguarde a coleta diária.</p></>:provider==='infogripe'?<p className="muted">Esta integração cobre São Paulo capital. A coleta lê o histórico semanal disponível no arquivo; escolha o período de visualização no Monitoramento.</p>:null}
    <label className="checkbox"><input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/>Habilitada para coleta diária</label>
    <Notice message={error}/><div className="source-setup-actions"><button type="button" className="text-button" disabled={busy} onClick={onManual}>Cadastrar outra fonte por URL</button><button disabled={busy||!catalog||!contract}>{busy?'Salvando…':'Salvar fonte'}</button></div>
  </form></section>;
}
