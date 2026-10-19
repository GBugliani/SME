import {ActionIcon} from './action-icon';
import {useEffect,useRef,useState} from 'react';
import {api,ApiError,type Integration} from './api';
import {Notice,useTimedMessage} from './notifications';
import type {DetectorConfig} from './detection-settings';

type Alert={id:number;titulo:string;mensagem:string;ativa:boolean;motivo_encerramento:string;revisao:number;lida:boolean;territorio:{codigo:string;nome:string};data_referencia:string;observado:number;referencia:number;limiar:number;configuracao:DetectorConfig;agravo:string;publicador:string;url_origem:string;lote_id:number;coletado_em:string};
type Page={alertas:Alert[];page:number;pages:number;count:number;nao_lidas:number;nao_lidas_total:number};
const emptyFilters={codigo:'',agravo:'',indicador:'',inicio:'',fim:''};
type Catalog={municipios:{codigo:string;nome:string}[];agravos:{codigo:string;nome:string}[];integracoes:Integration[]};

export function AlertCenter({onExpired}:{onExpired:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);const [open,setOpen]=useState(false);
  const [data,setData]=useState<Page|null>(null);const [page,setPage]=useState(1);
  const [situation,setSituation]=useState('ativas');const [busy,setBusy]=useState(false);
  const [filters,setFilters]=useState(emptyFilters),[draft,setDraft]=useState(emptyFilters);
  const [catalog,setCatalog]=useState<Catalog|null>(null),[unread,setUnread]=useState(0),[loading,setLoading]=useState(false);
  const [error,setError]=useTimedMessage();const [success,setSuccess]=useTimedMessage(5000);const generation=useRef(0);
  async function load(){
    if(document.hidden)return;
    const version=++generation.current;
    setLoading(true);
    try{const result=await api<Page>(`/alertas/?${new URLSearchParams({...filters,page:String(page),situacao:situation})}`);if(version===generation.current){setData(result);setUnread(result.nao_lidas_total);}}
    catch(e){if(version===generation.current){if(e instanceof ApiError&&e.status===401)onExpired();else if(open)setError(e instanceof Error?e.message:'Falha ao carregar alertas.');}}
    finally{if(version===generation.current)setLoading(false);}
  }
  useEffect(()=>{void load();const timer=setInterval(()=>void load(),open?15000:60000);return()=>{clearInterval(timer);generation.current++;};},[page,situation,open,filters]);
  useEffect(()=>{if(!open)return;let live=true;api<Catalog>('/alertas/opcoes/').then(result=>{if(live)setCatalog(result);}).catch(e=>{if(live){if(e instanceof ApiError&&e.status===401)onExpired();else setError('Não foi possível carregar as opções de filtro.');}});return()=>{live=false;};},[open]);
  async function read(alert:Alert){
    setBusy(true);try{await api(`/alertas/${alert.id}/ler/`,'POST',{revisao:alert.revisao});await load();}
    catch(e){if(e instanceof ApiError&&e.status===401)onExpired();else setError(e instanceof Error?e.message:'Falha ao marcar alerta.');}finally{setBusy(false);}
  }
  async function readAll(){
    setBusy(true);setError('');setSuccess('');
    try{
      const result=await api<{marcadas:number}>('/alertas/ler-todas/','POST',{});
      await load();
      setSuccess(result.marcadas===1?'1 alerta marcado como lido.':`${result.marcadas} alertas marcados como lidos.`);
    }catch(e){if(e instanceof ApiError&&e.status===401)onExpired();else setError(e instanceof Error?e.message:'Falha ao marcar os alertas.');}
    finally{setBusy(false);}
  }
  return <div className="alert-control"><button className="secondary alert-trigger" aria-label={`Alertas${unread?`: ${unread} não lidos`:''}`} aria-haspopup="dialog" onClick={()=>{setSituation('ativas');setPage(1);setOpen(true);dialog.current?.showModal();}}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M9 21h6"/></svg>{unread?<span className="alert-count">{unread>99?'99+':unread}</span>:null}</button>
    <dialog ref={dialog} className="filter-dialog alerts-dialog" aria-labelledby="alerts-title" onClose={()=>{setOpen(false);setSituation('ativas');setPage(1);setFilters(emptyFilters);setDraft(emptyFilters);}}><div className="filter-dialog-heading"><h2 id="alerts-title">Alertas epidemiológicos</h2><button className="secondary" onClick={()=>dialog.current?.close()} data-icon="close"><ActionIcon name="close"/>Fechar</button></div>
      <p className="muted">Semanas com crescimento fora do critério configurado. Confira a data de referência: alertas históricos não indicam ocorrência atual. A sinalização requer investigação.</p>
      {unread>0&&<div className="alert-bulk-actions"><span>{unread} {unread===1?'sinalização vigente não lida':'sinalizações vigentes não lidas'}, inclusive em outras páginas.</span><button type="button" className="secondary" disabled={busy||loading} onClick={()=>void readAll()} data-icon="check"><ActionIcon name="check"/>Marcar todas como lidas</button></div>}
      <label>Situação<select aria-label="Situação dos alertas" value={situation} onChange={e=>{setSituation(e.target.value);setPage(1);}}><option value="ativas">Sinalizações vigentes nos dados</option><option value="encerradas">Encerradas por revisão/configuração</option><option value="todas">Todas</option></select></label>
      <form className="alert-filters" onSubmit={e=>{e.preventDefault();setError('');setData(null);setFilters({...draft});setPage(1);}}>
        <label>Município<select aria-label="Município dos alertas" value={draft.codigo} onChange={e=>setDraft({...draft,codigo:e.target.value})}><option value="">Todos os municípios</option>{catalog?.municipios.map(m=><option key={m.codigo} value={m.codigo}>{m.nome}</option>)}</select></label>
        <label>Agravo<select aria-label="Agravo dos alertas" value={draft.agravo} onChange={e=>setDraft({...draft,agravo:e.target.value,indicador:''})}><option value="">Todos os agravos</option>{catalog?.agravos.map(a=><option key={a.codigo} value={a.codigo}>{a.nome}</option>)}</select></label>
        <label className="alert-origin-filter">Origem / indicador<select aria-label="Origem dos alertas" value={draft.indicador} onChange={e=>setDraft({...draft,indicador:e.target.value})}><option value="">Todas as origens</option>{catalog?.integracoes.filter(i=>!draft.agravo||i.agravo===draft.agravo).map(i=><option key={i.codigo} value={i.codigo}>{i.publicador} · {i.agravo_nome}</option>)}</select></label>
        <label>De<input aria-label="Início dos alertas" type="date" value={draft.inicio} onChange={e=>setDraft({...draft,inicio:e.target.value})}/></label>
        <label>Até<input aria-label="Fim dos alertas" type="date" min={draft.inicio||undefined} value={draft.fim} onChange={e=>setDraft({...draft,fim:e.target.value})}/></label>
        <p className="alert-filter-note">Datas de início das semanas epidemiológicas. As opções incluem alertas históricos.</p>
        <div className="alert-filter-actions"><button type="button" className="secondary" onClick={()=>{setDraft(emptyFilters);setFilters({...emptyFilters});setPage(1);setError('');}} data-icon="close"><ActionIcon name="close"/>Limpar filtros</button><button type="submit" disabled={loading} data-icon="filter"><ActionIcon name="filter"/>Aplicar filtros</button></div>
      </form>
      <Notice message={error}/><Notice message={success} kind="success"/>{!data?<p role="status">{loading?'Carregando…':'Não foi possível consultar os alertas.'}</p>:!data.alertas.length?<p>Nenhum alerta com os filtros selecionados.</p>:<ul className="alert-list" aria-busy={loading}>{data.alertas.map(a=><li key={a.id} className={a.lida?'alert-read':'alert-unread'}><div className="alert-item-heading"><h3>{a.territorio.nome} · {a.agravo}</h3><span className="badge inactive">{a.ativa?'Sinalização':'Encerrada'}</span></div><strong>Semana de {a.data_referencia.split('-').reverse().join('/')}</strong><p>{a.mensagem}</p><small>{a.publicador} · {a.configuracao.nome} · versão {a.configuracao.versao}</small>{a.motivo_encerramento&&<p>{a.motivo_encerramento}</p>}<details><summary>Origem e cálculo</summary><p>Observado: {a.observado.toLocaleString('pt-BR')} · Referência: {a.referencia.toLocaleString('pt-BR',{maximumFractionDigits:1})} · Limiar: {a.limiar.toLocaleString('pt-BR',{maximumFractionDigits:1})}</p><p>Lote {a.lote_id} · Coletado em {new Date(a.coletado_em).toLocaleString('pt-BR')}</p><a href={a.url_origem} target="_blank" rel="noreferrer">Ver origem ↗</a></details>{a.lida?<small>Lido por você</small>:<button className="secondary" disabled={busy} onClick={()=>void read(a)} data-icon="check"><ActionIcon name="check"/>Marcar como lido</button>}</li>)}</ul>}
      {data&&data.pages>1&&<div className="pagination"><button className="secondary" disabled={page<=1} onClick={()=>setPage(p=>p-1)} data-icon="arrowLeft"><ActionIcon name="arrowLeft"/>Anterior</button><span>{data.page} / {data.pages}</span><button className="secondary" disabled={page>=data.pages} onClick={()=>setPage(p=>p+1)} data-icon="arrowRight"><ActionIcon name="arrowRight"/>Próxima</button></div>}
    </dialog>
  </div>;
}
