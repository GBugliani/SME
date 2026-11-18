import {useEffect,useState} from 'react';
import {api,ApiError,type Integration} from './api';
import type {Indicators,IndicatorOptions} from './monitoring';
import {Modal} from './modal';
import {ActionIcon} from './action-icon';
import {Notice,useTimedMessage} from './notifications';
type Favorite={codigo:string;nome:string};
export function Favorites({data,options,onSelect,onExpired}:{data:Indicators|null;options:IndicatorOptions|null;onSelect:(code:string,origin:Integration)=>void;onExpired:()=>void}){
  const [items,setItems]=useState<Favorite[]>([]),[open,setOpen]=useState(false),[busy,setBusy]=useState(false);
  const [error,setError]=useTimedMessage(),[success,setSuccess]=useTimedMessage();
  const city=data?.territorio.tipo==='municipio'?data.territorio:null;
  useEffect(()=>{let active=true;api<{favoritos:Favorite[]}>('/favoritos/').then(value=>{if(active)setItems(value.favoritos);}).catch(err=>{if(active){if(err instanceof ApiError&&err.status===401)onExpired();else setError('Não foi possível carregar os favoritos.');}});return()=>{active=false;};},[]);
  async function change(code:string,remove=false){
    setBusy(true);
    try{if(remove){await api(`/favoritos/${code}/`,'DELETE');setItems(items.filter(item=>item.codigo!==code));setSuccess('Município removido dos favoritos.');}else{const value=await api<{favoritos:Favorite[]}>('/favoritos/','POST',{codigo:code});setItems(value.favoritos);setSuccess('Município salvo nos favoritos.');}}
    catch(err){if(err instanceof ApiError&&err.status===401)onExpired();else setError(err instanceof Error?err.message:'Falha ao atualizar favoritos.');}finally{setBusy(false);}
  }
  return <><button className="secondary favorites-trigger" title="Municípios favoritos" aria-label="Municípios favoritos" onClick={()=>setOpen(true)}><ActionIcon name="star"/></button><Notice message={error}/><Notice message={success} kind="success"/>
    {open&&<Modal compact title="Municípios favoritos" onClose={()=>setOpen(false)}><div className="section-heading"><h2>Municípios favoritos</h2><button className="secondary" data-icon="close" aria-label="Fechar favoritos" onClick={()=>setOpen(false)}><ActionIcon name="close"/>Fechar</button></div>
      {city&&!items.some(item=>item.codigo===city.codigo)&&<button disabled={busy} onClick={()=>void change(city.codigo)}><ActionIcon name="star"/>Salvar {city.nome}</button>}
      {!items.length&&<p className="muted">Selecione um município no mapa ou nos filtros e salve-o aqui.</p>}
      <ul className="favorites-list">{items.map(item=>{const origins=options?.integracoes.filter(origin=>origin.codigos_com_dados?.includes(item.codigo))||[];const preferred=origins.find(origin=>origin.codigo===data?.integracao?.codigo)||origins[0];return <li key={item.codigo}><strong>{item.nome}</strong><small>IBGE {item.codigo}</small>{preferred?<button className="secondary" disabled={busy} onClick={()=>{onSelect(item.codigo,preferred);setOpen(false);}}>Ver {preferred.agravo_nome} · {preferred.publicador}</button>:<small>Sem dados disponíveis no catálogo atual.</small>}<button className="secondary" disabled={busy} aria-label={`Remover ${item.nome} dos favoritos`} onClick={()=>void change(item.codigo,true)}><ActionIcon name="trash"/>Remover</button></li>;})}</ul>
    </Modal>}
  </>;
}
