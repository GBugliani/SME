import {useRef, useState} from 'react';
import type {Indicators} from './monitoring';
import {Notice, useTimedMessage} from './notifications';

export function ExportData({data,onExpired}:{data:Indicators|null;onExpired:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [mode,setMode]=useState('agregados');
  const [format,setFormat]=useState('csv');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useTimedMessage();
  async function download(){
    if(!data?.integracao||!data.serie.length)return;
    setBusy(true);setError('');
    const params=new URLSearchParams({tipo:data.territorio.tipo,codigo:data.territorio.codigo,agravo:data.agravo,
      indicador:data.integracao.codigo,inicio:data.serie[0].data,fim:data.serie.at(-1)!.data,modo:mode,formato:format});
    try{
      const response=await fetch(`/api/indicadores/exportar/?${params}`,{credentials:'same-origin'});
      if(response.status===401){onExpired();return;}
      if(!response.ok){const result=await response.json().catch(()=>({}));throw new Error(result.error||'Não foi possível exportar os dados.');}
      const blob=await response.blob();
      const url=URL.createObjectURL(blob);
      const link=document.createElement('a');link.href=url;link.download=`sme-${mode}-${data.territorio.codigo}.${format}`;
      document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30_000);
      dialog.current?.close();
    }catch(e){setError(e instanceof Error?e.message:'Falha na exportação.');}
    finally{setBusy(false);}
  }
  return <div className="export-control"><button className="secondary filter-trigger" disabled={!data?.serie.length} onClick={()=>{setError('');dialog.current?.showModal();}}>Exportar</button>
    <dialog ref={dialog} className="filter-dialog export-dialog" aria-labelledby="export-title" onCancel={e=>{if(busy)e.preventDefault();}}>
      <div className="filter-dialog-heading"><h2 id="export-title">Exportar dados</h2><button className="secondary" disabled={busy} aria-label="Fechar exportação" onClick={()=>dialog.current?.close()}>Fechar</button></div>
      <p>{data?.territorio.nome} · {data?.agravo_nome}</p><p className="muted">O arquivo usa o recorte, o período e a origem exibidos no painel.</p>
      <label>Conteúdo<select aria-label="Conteúdo" value={mode} disabled={busy} onChange={e=>{setMode(e.target.value);if(e.target.value==='brutos')setFormat('json');}}><option value="agregados">Dados agregados por semana</option><option value="brutos">Registros brutos por município</option></select></label>
      <label>Formato<select aria-label="Formato" value={format} disabled={busy||mode==='brutos'} onChange={e=>setFormat(e.target.value)}>{mode==='agregados'&&<option value="csv">CSV · Planilha</option>}<option value="json">JSON · Dados e metadados</option></select></label>
      <p className="muted">{mode==='brutos'?'Registros dos lotes usados no painel, sem somar municípios. Inclui campos do coletor, fonte e lote; não é o arquivo nacional completo.':'Inclui contagens, cobertura e origem dos dados. Valores ausentes não são convertidos em zero.'}</p>
      <Notice message={error}/><div className="filter-actions"><button disabled={busy} onClick={()=>void download()}>{busy?'Preparando…':'Baixar arquivo'}</button></div>
    </dialog>
  </div>;
}
