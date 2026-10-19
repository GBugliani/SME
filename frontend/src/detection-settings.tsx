import {ActionIcon} from './action-icon';
import {useEffect,useState,type FormEvent} from 'react';
import {api,ApiError,type Integration} from './api';
import {Notice,useTimedMessage} from './notifications';

export type DetectorConfig={id:number|null;metodo:string;nome:string;versao:number;versao_algoritmo:number;parametros:Record<string,number>;indicador:string;ativa:boolean;criada_em:string|null};
type Job={id:number;configuracao_id:number;status:string;total:number;processados:number;mensagem:string;criada_em:string;finalizada_em:string|null};
type Settings={metodos:Record<string,{nome:string;descricao:string;padrao:Record<string,number>}>;integracoes:Integration[];configuracoes:DetectorConfig[];ativas:DetectorConfig[];reanalises:Job[]};
const labels:Record<string,string>={janela:'Janela anterior (semanas)',desvios:'Multiplicador do desvio padrão',fator_mad:'Multiplicador do MAD',razao_minima:'Razão mínima sobre a referência',piso:'Piso do limiar (casos)'};
const status:Record<string,string>={pendente:'Na fila',executando:'Em execução',sucesso:'Concluída',erro:'Falha',substituida:'Substituída'};

export function DetectionSettings({onExpired}:{onExpired:()=>void}){
  const [data,setData]=useState<Settings|null>(null);
  const [scope,setScope]=useState('');const [method,setMethod]=useState('media_movel');
  const [parameters,setParameters]=useState<Record<string,number>>({});
  const [base,setBase]=useState<number|null>(null);const [busy,setBusy]=useState(false);
  const [error,setError]=useTimedMessage();const [success,setSuccess]=useTimedMessage(6000);
  async function load(initialize=false){
    try{const result=await api<Settings>('/deteccao/configuracoes/');setData(result);if(initialize)selectScope(scope,result);}
    catch(e){if(e instanceof ApiError&&e.status===401)onExpired();else setError(e instanceof Error?e.message:'Falha ao carregar configuração.');}
  }
  function selectScope(value:string,result=data){
    setScope(value);if(!result)return;
    const current=result.ativas.find(c=>c.indicador===value)||result.ativas.find(c=>!c.indicador);
    setBase(current?.id??null);setMethod(current?.metodo||'media_movel');
    setParameters({...current?.parametros||result.metodos.media_movel.padrao});
  }
  useEffect(()=>{void load(true);},[]);
  const pending=data?.reanalises.some(j=>['pendente','executando'].includes(j.status));
  useEffect(()=>{if(!pending)return;const timer=setInterval(()=>void load(),4000);return()=>clearInterval(timer);},[pending]);
  async function save(event:FormEvent){
    event.preventDefault();setBusy(true);setError('');
    try{const result=await api<{configuracao:DetectorConfig}>('/deteccao/configuracoes/','POST',{indicador:scope,metodo:method,parametros:parameters,base_id:base});
      setBase(result.configuracao.id);setSuccess('Configuração salva. A reanálise dos dados está na fila.');await load();
    }catch(e){if(e instanceof ApiError&&e.status===401)onExpired();else setError(e instanceof Error?e.message:'Falha ao salvar.');}
    finally{setBusy(false);}
  }
  async function reanalyze(id:number){
    setBusy(true);try{await api(`/deteccao/configuracoes/${id}/reanalisar/`,'POST',{});setSuccess('Reanálise adicionada à fila.');await load();}
    catch(e){if(e instanceof ApiError&&e.status===401)onExpired();else setError(e instanceof Error?e.message:'Falha ao reanalisar.');}finally{setBusy(false);}
  }
  async function useDefault(){
    setBusy(true);setError('');try{
      await api(`/deteccao/origens/${scope}/padrao/`,'POST',{});setSuccess('A origem voltou ao padrão. Reanálise adicionada à fila.');await load(true);
    }catch(e){if(e instanceof ApiError&&e.status===401)onExpired();else setError(e instanceof Error?e.message:'Falha ao restaurar padrão.');}finally{setBusy(false);}
  }
  if(!data)return <section className="card"><Notice message={error}/><p role="status">Carregando detecção…</p></section>;
  return <div className="detection-settings"><Notice message={error}/><Notice message={success} kind="success"/>
    <section className="card form-card"><div className="section-heading"><h2>Detecção de anomalias</h2><button className="secondary" disabled={busy} onClick={()=>void load(true)} data-icon="refresh"><ActionIcon name="refresh"/>Atualizar configuração</button></div>
      <p className="muted">A configuração padrão vale para as origens sem configuração própria. Cada alteração cria uma versão e reanalisa as séries armazenadas.</p>
      <form onSubmit={save}>
        <label>Aplicar a<select aria-label="Aplicar a" value={scope} disabled={busy} onChange={e=>selectScope(e.target.value)}><option value="">Padrão para todas as origens</option>{data.integracoes.map(i=><option key={i.codigo} value={i.codigo}>{i.publicador} · {i.agravo_nome}</option>)}</select></label>
        <label>Método<select aria-label="Método de detecção" value={method} disabled={busy} onChange={e=>{setMethod(e.target.value);setParameters({...data.metodos[e.target.value].padrao});}}>{Object.entries(data.metodos).map(([key,m])=><option key={key} value={key}>{m.nome}</option>)}</select></label>
        <p className="muted">{data.metodos[method].descricao}</p><div className="form-grid">{Object.entries(parameters).map(([key,value])=><label key={key}>{labels[key]}<input type="number" required value={Number.isFinite(value)?value:''} disabled={busy} step={key==='janela'?1:.1} min={key==='janela'?4:key==='razao_minima'?1:key==='piso'?0:.1} max={key==='janela'?52:key==='piso'?1000000:10} onChange={e=>setParameters(p=>({...p,[key]:e.target.value===''?NaN:Number(e.target.value)}))}/></label>)}</div>
        <p className="muted">Sem todas as semanas anteriores da janela, não há classificação. Uma sinalização estatística requer investigação e não confirma surto.</p>
        <div className="form-actions">{scope&&data.ativas.some(c=>c.indicador===scope)&&<button className="secondary" type="button" disabled={busy} onClick={()=>void useDefault()} data-icon="refresh"><ActionIcon name="refresh"/>Usar configuração padrão</button>}<button type="submit" disabled={busy} data-icon="save"><ActionIcon name="save"/>{busy?'Salvando…':'Salvar e reanalisar'}</button></div>
      </form>
    </section>
    <section className="card detection-history"><h2>Reanálise dos dados</h2>{data.reanalises.length?<ul className="job-list">{data.reanalises.map(j=><li key={j.id}><div><strong>{status[j.status]||j.status}</strong><small>{new Date(j.criada_em).toLocaleString('pt-BR')} · {j.status==='pendente'?'Aguardando início':`${j.processados} de ${j.total} séries`}</small><p>{j.mensagem}</p></div>{['erro','sucesso'].includes(j.status)&&data.ativas.some(c=>c.id===j.configuracao_id)&&<button className="secondary" disabled={busy} onClick={()=>void reanalyze(j.configuracao_id)} data-icon="refresh"><ActionIcon name="refresh"/>Reanalisar</button>}</li>)}</ul>:<p>Nenhuma reanálise solicitada.</p>}</section>
    <section className="card detection-history"><h2>Versões do detector</h2><ul className="job-list">{data.configuracoes.map(c=><li key={c.id}><div><strong>{c.nome} · versão {c.versao}</strong><small>{c.indicador?data.integracoes.find(i=>i.codigo===c.indicador)?.publicador+' · '+data.integracoes.find(i=>i.codigo===c.indicador)?.agravo_nome:'Configuração padrão'} · {c.ativa?'Ativa':'Histórica'}</small><p>{Object.entries(c.parametros).map(([k,v])=>`${labels[k]}: ${v}`).join(' · ')}</p></div></li>)}</ul></section>
  </div>;
}
