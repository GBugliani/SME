import {useRef,useState} from 'react';
import {ActionIcon} from './action-icon';
import {Modal} from './modal';
import {Notice,useTimedMessage} from './notifications';
import type {Indicators} from './monitoring';
import {sharedQueryUrl} from './shared-query';

export function ShareQuery({data}:{data:Indicators|null}){
  const [busy,setBusy]=useState(false);
  const [fallback,setFallback]=useState('');
  const [success,setSuccess]=useTimedMessage();
  const input=useRef<HTMLInputElement>(null);
  async function copy(){
    if(!data?.integracao)return;
    const link=sharedQueryUrl(window.location.href,{tipo:data.territorio.tipo,codigo:data.territorio.codigo,agravo:data.agravo,indicador:data.integracao.codigo,inicio:data.filtros?.inicio||'',fim:data.filtros?.fim||''});
    setBusy(true);
    try{
      if(!navigator.clipboard?.writeText)throw new Error('Clipboard indisponível');
      await navigator.clipboard.writeText(link);setSuccess('Link da consulta copiado. Quem abrir precisará entrar no SME.');
    }catch{setFallback(link);}finally{setBusy(false);}
  }
  return <><button type="button" className="secondary filter-trigger share-query-trigger" disabled={busy||!data?.integracao} onClick={()=>void copy()}><ActionIcon name="link"/>{busy?'Copiando…':'Copiar link da consulta'}</button><Notice message={success} kind="success"/>
    {fallback&&<Modal compact title="Copiar link da consulta" onClose={()=>setFallback('')}><div className="section-heading"><h2>Link da consulta</h2><button className="secondary" onClick={()=>setFallback('')} aria-label="Fechar link da consulta"><ActionIcon name="close"/></button></div><p>O navegador não permitiu a cópia automática. Selecione e copie o link abaixo.</p><label>Link<input ref={input} readOnly value={fallback} onFocus={event=>event.target.select()} style={{width:'100%'}}/></label><p className="muted">O link abre os dados atuais do recorte e exige login.</p><div className="filter-actions"><button onClick={()=>{input.current?.focus();input.current?.select();}}>Selecionar link</button></div></Modal>}
  </>;
}
