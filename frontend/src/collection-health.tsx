import {useEffect,useRef,useState} from 'react';
import {api,ApiError,type CollectionRun} from './api';
import {ActionIcon} from './action-icon';
import {Modal} from './modal';
import {Notice,useTimedMessage} from './notifications';

type Routine={run_id:string;tipo:string;status:string;iniciada_em:string;finalizada_em:string|null;previstas:number;contagens:Record<string,number>};
type HealthSource={id:number;nome:string;municipio:string;codigo:string;situacao:string;atrasada:boolean;ultima_tentativa:string|null;ultima_sucesso:string|null;ultima_semana:string|null;processamento_falhou:boolean;mensagem:string};
type Health={resumo:Record<string,number>;limite_atraso_horas:number;atualizado_em:string;agendamento:{ultima:Routine|null;ultima_rotina:Routine|null;proxima_prevista:string;monitoramento_disponivel:boolean;sem_confirmacao:boolean};fontes:HealthSource[];page:number;pages:number;count:number};
const date=(value:string|null)=>value?new Date(value).toLocaleString('pt-BR'):'Não registrada';
const states:Record<string,string>={ok:'Com registros',falhas:'Falha',atrasadas:'Atrasadas',vazias:'Sem registros',executando:'Em execução',sem_coleta:'Sem tentativa'};
const routineStates:Record<string,string>={concluida:'Concluída',com_falhas:'Encerrada com falhas',executando:'Em execução',sem_confirmacao:'Sem confirmação de conclusão'};

export function CollectionHealth({canCollect,onExpired}:{canCollect:boolean;onExpired:()=>void}){
  const [data,setData]=useState<Health|null>(null);
  const [filter,setFilter]=useState('');
  const [search,setSearch]=useState('');
  const [page,setPage]=useState(1);
  const [revision,setRevision]=useState(0);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState<number|null>(null);
  const [error,setError]=useTimedMessage();
  const [success,setSuccess]=useTimedMessage();
  const [history,setHistory]=useState<{source:HealthSource;runs:CollectionRun[]}|null>(null);
  const generation=useRef(0);
  useEffect(()=>{
    const timer=setInterval(()=>{if(!document.hidden)setRevision(v=>v+1);},60000);
    return()=>clearInterval(timer);
  },[]);
  useEffect(()=>{
    const version=++generation.current;setLoading(true);
    const timer=setTimeout(()=>{
      const params=new URLSearchParams({situacao:filter,q:search,page:String(page)});
      api<Health>(`/fontes/saude/?${params}`).then(value=>{if(version===generation.current)setData(value);})
        .catch(err=>{if(version===generation.current){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err.message);}})
        .finally(()=>{if(version===generation.current)setLoading(false);});
    },250);
    return()=>{clearTimeout(timer);generation.current++;};
  },[filter,search,page,revision]);
  async function showHistory(source:HealthSource){
    try{const value=await api<{execucoes:CollectionRun[]}>(`/fontes/${source.id}/coletas/`);setHistory({source,runs:value.execucoes});}
    catch(err){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof Error?err.message:'Falha ao consultar histórico.');}
  }
  async function collect(source:HealthSource){
    setBusy(source.id);setError('');
    try{const value=await api<{execucao:CollectionRun}>(`/fontes/${source.id}/coletas/`,'POST',{});setSuccess(`${source.municipio}: ${value.execucao.mensagem}`);}
    catch(err){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof Error?err.message:'Falha na coleta.');}
    finally{setBusy(null);setRevision(v=>v+1);}
  }
  const routine=data?.agendamento.ultima;
  const lastManual=data?.agendamento.ultima_rotina;
  return <section className="collection-health">
    <Notice message={error}/><Notice message={success} kind="success"/>
    <section className="card"><div className="section-heading"><h2>Saúde das coletas</h2><button className="secondary" disabled={loading} onClick={()=>setRevision(v=>v+1)}><ActionIcon name="refresh"/>Atualizar</button></div>
      <p className="muted">Fontes habilitadas e compatíveis com a coleta automática. Atualização da tela a cada minuto.</p>
      {data&&<><div className="collection-health-summary">
        <div><span>Última rotina agendada registrada</span><strong>{routine?routineStates[routine.status]:'Acompanhamento por fonte'}</strong><small>{routine?date(routine.iniciada_em):'O agendamento atual não informa início e conclusão da rotina. Consulte as tentativas de cada fonte abaixo.'}</small>{routine&&<small>{routine.contagens.sucesso} com registros · {routine.contagens.vazia} sem registros · {routine.contagens.erro} falhas · {routine.contagens.executando} em execução · {routine.contagens.sem_confirmacao} sem confirmação, de {routine.previstas} fontes</small>}{routine?.finalizada_em&&<small>Encerramento: {date(routine.finalizada_em)}</small>}</div>
        <div><span>Próxima execução prevista</span><strong>{date(data.agendamento.proxima_prevista)}</strong><small>Rotina diária às 6h, horário de Brasília.</small></div>
      </div>{data.agendamento.monitoramento_disponivel&&data.agendamento.sem_confirmacao&&<p className="health-warning" role="status">Ainda não há confirmação da execução agendada mais recente. O início pode estar atrasado ou o registro ainda não chegou.</p>}
      {lastManual?.tipo==='manual'&&<p className="muted">Última rotina disparada manualmente: {date(lastManual.iniciada_em)} · {routineStates[lastManual.status]}. Ela não confirma o funcionamento do agendamento.</p>}
      <div className="collection-health-counts">{[['total','Fontes monitoradas'],['ok','Com registros'],['falhas','Falhas'],['atrasadas','Atrasadas'],['vazias','Sem registros'],['executando','Em execução'],['sem_coleta','Sem tentativa']].map(([key,label])=><div key={key}><strong>{data.resumo[key]}</strong><span>{label}</span></div>)}</div>
      <p className="muted">Atrasada: sem coleta bem-sucedida há mais de {data.limite_atraso_horas} horas.</p><small>Atualizado em {date(data.atualizado_em)}</small></>}
    </section>
    <section className="card"><div className="health-filters"><label>Situação<select value={filter} onChange={e=>{setFilter(e.target.value);setPage(1);}}><option value="">Todas</option>{['falhas','atrasadas','vazias','executando','sem_coleta'].map(key=><option key={key} value={key}>{key==='falhas'?'Falhas':states[key]}</option>)}</select></label><label>Pesquisar fontes<input type="search" maxLength={200} value={search} placeholder="Município, IBGE ou fonte" onChange={e=>{setSearch(e.target.value);setPage(1);}}/></label></div>
    {loading?<p role="status">Atualizando coletas…</p>:data?<>{!data.fontes.length?<p>Nenhuma fonte encontrada nesta situação.</p>:<div className="table-scroll"><table><thead><tr><th>Município / fonte</th><th>Situação</th><th>Última tentativa</th><th>Último sucesso</th><th>Última semana com dados</th><th>Ações</th></tr></thead><tbody>{data.fontes.map(source=><tr key={source.id}><td><strong>{source.municipio}</strong><small>IBGE {source.codigo}</small><small>{source.nome}</small></td><td data-label="Situação"><span className="badge inactive">{source.processamento_falhou?'Falha no processamento':states[source.situacao]}</span>{source.atrasada&&<small className="processing-error">Coleta atrasada</small>}{source.mensagem&&<small>{source.mensagem}</small>}</td><td data-label="Última tentativa">{date(source.ultima_tentativa)}</td><td data-label="Último sucesso">{date(source.ultima_sucesso)}</td><td data-label="Última semana com dados">{source.ultima_semana?source.ultima_semana.split('-').reverse().join('/'):'Sem dados'}<small>A semana publicada pode ser anterior à coleta.</small></td><td data-label="Ações"><div className="source-actions"><button className="secondary" onClick={()=>void showHistory(source)}><ActionIcon name="history"/>Histórico</button>{canCollect&&<button className="secondary" disabled={busy!==null||source.situacao==='executando'} onClick={()=>void collect(source)}><ActionIcon name="play"/>{busy===source.id?'Coletando…':'Coletar agora'}</button>}</div></td></tr>)}</tbody></table></div>}<div className="pagination"><button className="secondary" disabled={data.page<=1} onClick={()=>setPage(data.page-1)}>Anterior</button><span>Página {data.page} de {data.pages} · {data.count} fontes</span><button className="secondary" disabled={data.page>=data.pages} onClick={()=>setPage(data.page+1)}>Próxima</button></div></>:<p>Não foi possível carregar as coletas. Use Atualizar para tentar novamente.</p>}
    </section>
    {history&&<Modal title="Histórico de coleta" onClose={()=>setHistory(null)}><section className="card collection-history"><div className="section-heading"><div><h2>Coletas · {history.source.municipio}</h2><small>{history.source.nome}</small></div><button className="secondary" onClick={()=>setHistory(null)}><ActionIcon name="close"/>Fechar histórico</button></div>{history.runs.length?<ul>{history.runs.map(run=><li key={run.id}><strong>{({sucesso:'Concluída',vazia:'Sem registros',erro:'Falha',executando:'Executando'})[run.status]} · {date(run.iniciada_em)}</strong><p>{run.mensagem}</p><small>{run.quantidade_registros} registros · {run.origem==='airflow'?'Airflow':run.origem==='inicial'?'Coleta inicial':'Manual'}{run.repetida?' · Conteúdo já armazenado':''}</small></li>)}</ul>:<p>Nenhuma coleta registrada.</p>}</section></Modal>}
  </section>;
}
