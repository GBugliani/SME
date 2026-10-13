import {useEffect,useRef,useState} from 'react';
import {api,ApiError,type Source,type SourcePage} from './api';
import {territoryLabel,sourcePeriodLabel} from './source-labels';
import {Notice,useTimedMessage} from './notifications';

export function SourceFeed({page,onExpired}:{page:SourcePage;onExpired:()=>void}) {
  const [items,setItems]=useState<Source[]>([]),[more,setMore]=useState(false);
  const [error,setError]=useTimedMessage();
  const list=useRef<HTMLDivElement>(null),next=useRef(2),version=useRef(0),busy=useRef(false),pages=useRef(page.pages);
  useEffect(()=>{
    const request=++version.current;next.current=2;pages.current=page.pages;busy.current=false;setMore(false);setError('');
    if(page.page===1)setItems(page.sources);
    else {setItems([]);api<SourcePage>('/fontes/?page=1').then(data=>{if(request===version.current){setItems(data.sources);pages.current=data.pages;}}).catch(err=>{if(request===version.current){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err.message);}});}
    if(list.current)list.current.scrollTop=0;
    return()=>{version.current++;};
  },[page,onExpired,setError]);
  useEffect(()=>{
    const node=list.current;if(!node)return;
    const measure=()=>{const rows=Array.from(node.children).slice(0,3);node.style.maxHeight=`${rows.reduce((sum,row)=>sum+row.getBoundingClientRect().height,0)}px`;};
    const observer=new ResizeObserver(measure);observer.observe(node);Array.from(node.children).slice(0,3).forEach(row=>observer.observe(row));measure();return()=>observer.disconnect();
  },[items]);
  async function loadMore(){
    if(busy.current||next.current>pages.current)return;
    busy.current=true;setMore(true);const request=version.current;
    try{const data=await api<SourcePage>(`/fontes/?page=${next.current}`);if(request===version.current){setItems(old=>[...old,...data.sources.filter(s=>!old.some(v=>v.id===s.id))]);next.current++;pages.current=data.pages;}}
    catch(err){if(request===version.current){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof Error?err.message:'Não foi possível carregar mais fontes.');}}
    finally{if(request===version.current){busy.current=false;setMore(false);}}
  }
  return <><div ref={list} className="source-feed" tabIndex={0} role="list" aria-label="Lista de fontes cadastradas" onScroll={e=>{const node=e.currentTarget;if(node.scrollTop+node.clientHeight>=node.scrollHeight-40)void loadMore();}}>{items.map(s=><div key={s.id} role="listitem"><span className={`source-dot ${s.ativa?'enabled':''}`}/><div><strong>{territoryLabel(s)}</strong><small>{sourcePeriodLabel(s)}</small><span className="feed-status">{s.ativa?'Habilitada':'Desabilitada'} · {s.tipo.toUpperCase()}</span></div></div>)}</div>{more&&<small role="status">Carregando mais fontes…</small>}<Notice message={error}/></>;
}
