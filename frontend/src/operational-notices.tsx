import {useEffect,useState} from 'react';
import {api,ApiError} from './api';
import {ActionIcon} from './action-icon';
import {Modal} from './modal';
import {Notice,useTimedMessage} from './notifications';
type Item={id:string;titulo:string;mensagem:string};
export function OperationalNotices({userId,onExpired,onHealth}:{userId:number;onExpired:()=>void;onHealth:()=>void}){
  const [items,setItems]=useState<Item[]>([]),[open,setOpen]=useState(false);
  const [notice,setNotice]=useTimedMessage();
  const [error,setError]=useTimedMessage();
  useEffect(()=>{
    let active=true;
    async function load(){
      if(document.hidden)return;
      try{
        const data=await api<{avisos:Item[]}>('/administracao/coletas/avisos/');if(!active)return;
        setItems(data.avisos);
        const key=`sme-avisos-operacionais-${userId}`;
        let seen:string[]=[];
        try{seen=JSON.parse(sessionStorage.getItem(key)||'[]');if(!Array.isArray(seen))seen=[];}catch{}
        const fresh=data.avisos.filter(item=>!seen.includes(item.id));
        if(fresh.length){setNotice(fresh.map(item=>`${item.titulo}: ${item.mensagem}`).join(' '));try{sessionStorage.setItem(key,JSON.stringify([...seen,...fresh.map(item=>item.id)].slice(-50)));}catch{}}
      }catch(err){if(active&&err instanceof ApiError&&err.status===401)onExpired();else if(active)setError('Não foi possível consultar os avisos operacionais.');}
    }
    void load();const timer=setInterval(()=>void load(),60000);return()=>{active=false;clearInterval(timer);};
  },[userId]);
  return <><button className="secondary operational-trigger" title="Avisos operacionais" aria-label={`Avisos operacionais${items.length?`: ${items.length}`:''}`} onClick={()=>setOpen(true)}><ActionIcon name="activity"/>{items.length>0&&<span className="alert-count">{items.length}</span>}</button><Notice message={notice}/><Notice message={error}/>
    {open&&<Modal compact title="Avisos operacionais" onClose={()=>setOpen(false)}><div className="section-heading"><h2>Avisos operacionais</h2><button className="secondary" data-icon="close" aria-label="Fechar avisos operacionais" onClick={()=>setOpen(false)}><ActionIcon name="close"/>Fechar</button></div>{items.length?<ul className="operational-list">{items.map(item=><li key={item.id}><strong>{item.titulo}</strong><p>{item.mensagem}</p></li>)}</ul>:<p>Nenhum aviso operacional ativo.</p>}<button onClick={()=>{setOpen(false);onHealth();}}>Abrir Saúde das coletas</button></Modal>}
  </>;
}
