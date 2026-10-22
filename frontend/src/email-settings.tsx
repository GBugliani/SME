import {ActionIcon} from './action-icon';
import {useEffect,useState,type FormEvent} from 'react';
import {api,ApiError} from './api';
import {Notice,useTimedMessage} from './notifications';

type Group={id:number;nome:string;enderecos:string[]};
type Settings={habilitado:boolean;smtp_configurado:boolean;grupos:Group[];individuais:string[];grupos_selecionados:number[];destinatarios_resolvidos:number};
type Delivery={id:number;destinatario:string;assunto:string;status:string;tentativas:number;erro:string;criado_em:string;enviado_em:string|null;proxima_tentativa_em:string|null};
const status:Record<string,string>={pendente:'Na fila',enviando:'Enviando',enviado:'Enviado',erro:'Falha',cancelado:'Cancelado'};
const addresses=(text:string)=>text.split(/[\n,;]+/).map(s=>s.trim()).filter(Boolean);
const message=(error:unknown)=>error instanceof Error?error.message:'Não foi possível concluir a operação.';

export function EmailSettings({onExpired}:{onExpired:()=>void}){
  const [data,setData]=useState<Settings|null>(null);
  const [deliveries,setDeliveries]=useState<Delivery[]>([]);
  const [individuals,setIndividuals]=useState('');
  const [selected,setSelected]=useState<number[]>([]);
  const [editing,setEditing]=useState<Group|'new'|null>(null);
  const [groupName,setGroupName]=useState('');
  const [groupAddresses,setGroupAddresses]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useTimedMessage();const [success,setSuccess]=useTimedMessage(6000);
  function handle(error:unknown){if(error instanceof ApiError&&error.status===401)onExpired();else setError(message(error));}
  async function load(){
    try{
      const [config,history]=await Promise.all([
        api<Settings>('/administracao/email/'),
        api<{envios:Delivery[]}>('/administracao/email/envios/')]);
      setData(config);setIndividuals(config.individuais.join('\n'));
      setSelected(config.grupos_selecionados);setDeliveries(history.envios);
    }catch(e){handle(e);}
  }
  useEffect(()=>{void load();},[]);
  async function saveRecipients(event:FormEvent){
    event.preventDefault();setBusy(true);setError('');
    try{
      await api('/administracao/email/destinatarios/','PUT',{individuais:addresses(individuals),grupos:selected});
      await load();setSuccess('Destinatários salvos. Os próximos alertas usarão esta lista.');
    }catch(e){handle(e);}finally{setBusy(false);}
  }
  async function saveGroup(event:FormEvent){
    event.preventDefault();if(!editing)return;setBusy(true);setError('');
    try{
      await api(editing==='new'?'/administracao/email/grupos/':`/administracao/email/grupos/${editing.id}/`,editing==='new'?'POST':'PUT',
        {nome:groupName,enderecos:addresses(groupAddresses)});
      setEditing(null);await load();setSuccess('Grupo salvo.');
    }catch(e){handle(e);}finally{setBusy(false);}
  }
  async function deleteGroup(group:Group){
    if(!window.confirm(`Excluir o grupo “${group.nome}”?`))return;
    setBusy(true);setError('');
    try{await api(`/administracao/email/grupos/${group.id}/`,'DELETE');await load();setSuccess('Grupo excluído.');}
    catch(e){handle(e);}finally{setBusy(false);}
  }
  async function toggle(){
    if(!data)return;setBusy(true);setError('');
    try{await api('/administracao/email/','PUT',{habilitado:!data.habilitado});await load();setSuccess(data.habilitado?'Envio de e-mails desativado.':'Envio de e-mails ativado.');}
    catch(e){handle(e);}finally{setBusy(false);}
  }
  async function testSmtp(){
    setBusy(true);setError('');
    try{const result=await api<{destinatario:string}>('/administracao/email/teste/','POST',{});
      setSuccess(`O SMTP aceitou o teste para ${result.destinatario}. Confira a caixa de entrada.`);
    }catch(e){handle(e);}finally{setBusy(false);}
  }
  async function sendExample(){
    setBusy(true);setError('');
    try{const result=await api<{destinatario:string}>('/administracao/email/alerta-exemplo/','POST',{});
      setSuccess(`O SMTP aceitou o exemplo de alerta para ${result.destinatario}. Confira a caixa de entrada.`);
    }catch(e){handle(e);}finally{setBusy(false);}
  }
  async function retry(id:number){
    setBusy(true);setError('');
    try{await api(`/administracao/email/envios/${id}/tentar/`,'POST',{});await load();setSuccess('Envio colocado novamente na fila.');}
    catch(e){handle(e);}finally{setBusy(false);}
  }
  function edit(group:Group|'new'){
    setEditing(group);setGroupName(group==='new'?'':group.nome);
    setGroupAddresses(group==='new'?'':group.enderecos.join('\n'));setError('');
  }
  if(!data)return <section className="card"><Notice message={error}/><p role="status">Carregando envio de e-mails…</p></section>;
  return <div className="email-settings">
    <Notice message={error}/><Notice message={success} kind="success"/>
    <section className="card">
      <div className="section-heading"><h2>Alertas por e-mail</h2><span className={`badge ${data.habilitado?'':'inactive'}`}>{data.habilitado?'Ativado':'Desativado'}</span></div>
      <p>O painel de alertas continua disponível. O e-mail é enviado apenas para novas sinalizações de semanas encerradas recentemente, após a ativação deste canal.</p>
      <p className="muted">SMTP: {data.smtp_configurado?'configurado no servidor':'pendente no .env do servidor'} · {data.destinatarios_resolvidos} destinatário{data.destinatarios_resolvidos===1?'':'s'} único{data.destinatarios_resolvidos===1?'':'s'}.</p>
      {!data.smtp_configurado&&<p className="muted">Preencha host, porta, segurança, usuário, senha e remetente no .env; reinicie backend e mailer para aplicar.</p>}
      <div className="email-control-actions"><button type="button" disabled={busy||(!data.habilitado&&(!data.smtp_configurado||!data.destinatarios_resolvidos))} onClick={()=>void toggle()} data-icon="toggle"><ActionIcon name={data.habilitado?"pause":"check"}/>{data.habilitado?'Desativar envio':'Ativar envio'}</button>
        <button type="button" className="secondary" disabled={busy||!data.smtp_configurado} onClick={()=>void testSmtp()} data-icon="send"><ActionIcon name="send"/>Enviar teste para meu e-mail</button>
        <button type="button" className="secondary" disabled={busy||!data.smtp_configurado} onClick={()=>void sendExample()} data-icon="send"><ActionIcon name="send"/>Enviar exemplo de alerta</button></div>
      <p className="muted">O exemplo usa o alerta ativo mais recente e o mesmo conteúdo do envio automático. Ele será identificado como demonstração e enviado apenas para o e-mail da sua conta.</p>
    </section>
    <section className="card">
      <div className="section-heading"><h2>Destinatários</h2><span className="muted">Endereços individuais e grupos</span></div>
      <form onSubmit={saveRecipients}>
        <label>E-mails individuais<textarea value={individuals} onChange={e=>setIndividuals(e.target.value)} rows={4} placeholder="Um endereço por linha" aria-describedby="individual-help" disabled={busy}/></label>
        <p id="individual-help" className="muted">Um endereço por linha. Também é possível separar por vírgula.</p>
        <fieldset className="email-group-options"><legend>Grupos que receberão os alertas</legend>
          {data.grupos.length===0?<p className="muted">Cadastre um grupo abaixo para selecioná-lo aqui.</p>:data.grupos.map(group=><label className="checkbox" key={group.id}>
            <input type="checkbox" checked={selected.includes(group.id)} disabled={busy} onChange={e=>setSelected(old=>e.target.checked?[...old,group.id]:old.filter(id=>id!==group.id))}/>
            {group.nome} <span className="muted">({group.enderecos.length} endereço{group.enderecos.length===1?'':'s'})</span>
          </label>)}
        </fieldset>
        <p className="muted">Se um e-mail estiver em mais de um grupo, receberá uma única mensagem por alerta.</p>
        <div className="form-actions"><button type="submit" disabled={busy} data-icon="save"><ActionIcon name="save"/>{busy?'Salvando…':'Salvar destinatários'}</button></div>
      </form>
    </section>
    <section className="card">
      <div className="section-heading"><h2>Grupos de e-mail</h2><button type="button" className="secondary" disabled={busy} onClick={()=>edit('new')} data-icon="plus"><ActionIcon name="plus"/>Criar grupo</button></div>
      {editing&&<form className="email-group-editor" onSubmit={saveGroup}>
        <h3>{editing==='new'?'Novo grupo':`Editar ${editing.nome}`}</h3>
        <label>Nome do grupo<input value={groupName} maxLength={100} required onChange={e=>setGroupName(e.target.value)}/></label>
        <label>E-mails do grupo<textarea value={groupAddresses} rows={5} required placeholder="Um endereço por linha" onChange={e=>setGroupAddresses(e.target.value)}/></label>
        <div className="form-actions"><button type="button" className="secondary" disabled={busy} onClick={()=>setEditing(null)} data-icon="close"><ActionIcon name="close"/>Cancelar</button><button type="submit" disabled={busy} data-icon="save"><ActionIcon name="save"/>Salvar grupo</button></div>
      </form>}
      {data.grupos.length?<ul className="email-groups">{data.grupos.map(group=><li key={group.id}>
        <div><strong>{group.nome}</strong><small>{group.enderecos.length} endereço{group.enderecos.length===1?'':'s'}{data.grupos_selecionados.includes(group.id)?' · Selecionado':''}</small>
          <details><summary>Ver endereços</summary><p>{group.enderecos.join(', ')}</p></details></div>
        <div className="email-group-actions"><button className="secondary" disabled={busy} onClick={()=>edit(group)} data-icon="edit"><ActionIcon name="edit"/>Editar</button><button className="secondary" disabled={busy||data.grupos_selecionados.includes(group.id)} title={data.grupos_selecionados.includes(group.id)?'Remova o grupo dos destinatários antes de excluir':undefined} onClick={()=>void deleteGroup(group)} data-icon="trash"><ActionIcon name="trash"/>Excluir</button></div>
      </li>)}</ul>:<p className="muted">Nenhum grupo cadastrado.</p>}
    </section>
    <section className="card">
      <div className="section-heading"><h2>Últimos envios</h2><button type="button" className="secondary" onClick={()=>void load()} data-icon="refresh"><ActionIcon name="refresh"/>Atualizar</button></div>
      {deliveries.length?<div className="table-scroll"><table><thead><tr><th>Mensagem</th><th>Destinatário</th><th>Situação</th><th>Ação</th></tr></thead><tbody>{deliveries.map(row=><tr key={row.id}>
        <td><strong>{row.assunto}</strong><small>{new Date(row.criado_em).toLocaleString('pt-BR')}</small></td>
        <td data-label="Destinatário">{row.destinatario}</td>
        <td data-label="Situação">{status[row.status]||row.status}<small>{row.status==='enviado'&&row.enviado_em?new Date(row.enviado_em).toLocaleString('pt-BR'):`${row.tentativas} tentativa${row.tentativas===1?'':'s'}`}</small>{row.erro&&<small>{row.erro}</small>}</td>
        <td data-label="Ação">{row.status==='erro'&&<button className="secondary" disabled={busy} onClick={()=>void retry(row.id)} data-icon="refresh"><ActionIcon name="refresh"/>Tentar novamente</button>}</td>
      </tr>)}</tbody></table></div>:<p className="muted">Nenhum e-mail enviado ou na fila.</p>}
    </section>
  </div>;
}
