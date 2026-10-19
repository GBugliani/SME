import {ActionIcon} from './action-icon';
import {useEffect, useRef, useState, type FormEvent} from 'react';
import {api, ApiError, type User} from './api';
import {Notice, useTimedMessage} from './notifications';
import {DetectionSettings} from './detection-settings';
import {EmailSettings} from './email-settings';

type Profile = {id:number; nome:string; permissoes:string[]; sistema:boolean; administrador:boolean};
type Profiles = {perfis:Profile[]; permissoes:Record<string,string>};
type Users = {usuarios:User[]; count:number; page:number; pages:number};
type Audit = {registros:{id:number; usuario:string; acao:string; entidade:string; entidade_id:number; criada_em:string; detalhes:unknown}[]; page:number; pages:number};
const message = (e:unknown) => e instanceof Error ? e.message : 'Não foi possível concluir a operação.';

export function Administration({user,onExpired,onUserChanged}:{user:User;onExpired:()=>void;onUserChanged:(user:User)=>void}) {
  const [tab,setTab]=useState<'usuarios'|'perfis'|'auditoria'|'deteccao'|'email'>('usuarios');
  const [profiles,setProfiles]=useState<Profiles>({perfis:[],permissoes:{}});
  const [users,setUsers]=useState<Users>({usuarios:[],count:0,page:1,pages:1});
  const [audit,setAudit]=useState<Audit>({registros:[],page:1,pages:1});
  const [query,setQuery]=useState('');
  const [page,setPage]=useState(1);
  const [revision,setRevision]=useState(0);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useTimedMessage();
  const [success,setSuccess]=useTimedMessage(5000);
  const [resetUser,setResetUser]=useState<User|null>(null);
  const [editUser,setEditUser]=useState<User|'new'|null>(null);
  const [editProfile,setEditProfile]=useState<Profile|'new'|null>(null);
  const generation=useRef(0);
  useEffect(()=>{
    const version=++generation.current;
    setLoading(true);
    const timer=setTimeout(()=>{
      Promise.all([
        api<Profiles>('/administracao/perfis/'),
        tab==='usuarios' ? api<Users>(`/administracao/usuarios/?${new URLSearchParams({q:query,page:String(page)})}`) :
        tab==='auditoria' ? api<Audit>(`/administracao/auditoria/?page=${page}`) : Promise.resolve(null),
      ]).then(([p,result])=>{
        if(version!==generation.current)return;
        setProfiles(p);
        if(result&&'usuarios' in result)setUsers(result);
        if(result&&'registros' in result)setAudit(result);
      }).catch(e=>{if(version===generation.current){if(e instanceof ApiError&&e.status===401)onExpired();else setError(message(e));}})
        .finally(()=>{if(version===generation.current)setLoading(false);});
    },250);
    return()=>{clearTimeout(timer);generation.current++;};
  },[tab,query,page,revision]);
  function navigate(next:typeof tab){setTab(next);setPage(1);setEditUser(null);setEditProfile(null);setResetUser(null);setError('');setSuccess('');}
  async function saveUser(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setBusy(true);setError('');
    const form=new FormData(event.currentTarget);
    const body={nome:form.get('nome'),email:form.get('email'),ativo:form.get('ativo')==='on',perfil_id:Number(form.get('perfil_id')),
      ...(editUser==='new'?{password:form.get('password'),password_confirmation:form.get('password_confirmation')}:{})};
    try{
      const saved=await api<{user:User}>(editUser==='new'?'/administracao/usuarios/':`/administracao/usuarios/${(editUser as User).id}/`,editUser==='new'?'POST':'PUT',body);
      if(saved.user.id===user.id)onUserChanged(saved.user);
      setEditUser(null);setRevision(v=>v+1);setSuccess('Usuário salvo.');
    }catch(e){if(e instanceof ApiError&&e.status===401)onExpired();else setError(message(e));}
    finally{setBusy(false);}
  }
  async function resetPassword(event:FormEvent<HTMLFormElement>){
    event.preventDefault();if(!resetUser)return;setBusy(true);setError('');
    const form=new FormData(event.currentTarget);
    try{
      const result=await api<{login_required:boolean}>(`/administracao/usuarios/${resetUser.id}/senha/`,'POST',
        {password:form.get('password'),password_confirmation:form.get('password_confirmation'),admin_password:form.get('admin_password')});
      if(result.login_required){onExpired();return;}
      setResetUser(null);setRevision(v=>v+1);setSuccess('Senha redefinida. O usuário deverá entrar novamente com a nova senha.');
    }catch(e){if(e instanceof ApiError&&e.status===401)onExpired();else setError(message(e));}
    finally{setBusy(false);}
  }
  async function saveProfile(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setBusy(true);setError('');
    const form=new FormData(event.currentTarget);
    try{
      await api(editProfile==='new'?'/administracao/perfis/':`/administracao/perfis/${(editProfile as Profile).id}/`,editProfile==='new'?'POST':'PUT',
        {nome:form.get('nome'),permissoes:form.getAll('permissoes')});
      setEditProfile(null);setRevision(v=>v+1);setSuccess('Perfil salvo. As permissões já se aplicam às próximas solicitações dos usuários.');
    }catch(e){if(e instanceof ApiError&&e.status===401)onExpired();else setError(message(e));}
    finally{setBusy(false);}
  }
  const selectedUser=editUser&&editUser!=='new'?editUser:null;
  const selectedProfile=editProfile&&editProfile!=='new'?editProfile:null;
  return <section className="administration">
    <div className="page-heading"><div><span className="eyebrow">ADMINISTRAÇÃO</span><h1>{tab==='deteccao'?'Configuração da detecção':tab==='email'?'Envio de e-mails':'Usuários e acessos'}</h1><p className="muted">{tab==='email'?'Destinatários, grupos e histórico de envios.':tab==='deteccao'?'Métodos, parâmetros e reanálises.':'Contas, permissões e histórico de alterações.'}</p></div></div>
    <nav className="admin-tabs" aria-label="Administração">
      {(['usuarios','perfis','auditoria','deteccao','email'] as const).map(t=><button key={t} className={tab===t?'':'secondary'} aria-current={tab===t?'page':undefined} disabled={busy} onClick={()=>navigate(t)} data-icon="tab"><ActionIcon name={t==='usuarios'?'users':t==='perfis'?'shield':t==='deteccao'?'activity':t==='email'?'mail':'history'}/>{t==='usuarios'?'Usuários':t==='perfis'?'Perfis de acesso':t==='deteccao'?'Detecção':t==='email'?'E-mail':'Auditoria'}</button>)}
    </nav>
    <Notice message={error}/><Notice message={success} kind="success"/>
    {tab==='deteccao'?<DetectionSettings onExpired={onExpired}/>:tab==='email'?<EmailSettings onExpired={onExpired}/>:resetUser ? <section className="card form-card"><div className="section-heading"><h2>Redefinir senha</h2><button className="secondary" disabled={busy} onClick={()=>setResetUser(null)} data-icon="close"><ActionIcon name="close"/>Cancelar</button></div>
      <p><strong>{resetUser.nome}</strong><br/>{resetUser.email}</p>
      <form onSubmit={resetPassword}>
        <label>Sua senha de administrador<input name="admin_password" type="password" autoComplete="current-password" required maxLength={1024}/></label>
        <div className="form-grid"><label>Nova senha<input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={1024} required/></label><label>Confirmar nova senha<input name="password_confirmation" type="password" autoComplete="new-password" minLength={12} maxLength={1024} required/></label></div>
        <p className="muted">Use pelo menos 12 caracteres. As sessões dessa conta serão encerradas.{resetUser.id===user.id?' Você precisará entrar novamente.':''}</p>
        <div className="form-actions"><button type="submit" disabled={busy} data-icon="key"><ActionIcon name="key"/>{busy?'Redefinindo…':'Salvar nova senha'}</button></div>
      </form>
    </section> : editUser ? <section className="card form-card"><div className="section-heading"><h2>{editUser==='new'?'Cadastrar usuário':'Editar usuário'}</h2><button className="secondary" disabled={busy} onClick={()=>setEditUser(null)} data-icon="close"><ActionIcon name="close"/>Cancelar</button></div>
      <form key={selectedUser?.id||'new'} onSubmit={saveUser}>
        <div className="form-grid"><label>Nome<input name="nome" defaultValue={selectedUser?.nome||''} required maxLength={150} autoComplete="name"/></label><label>E-mail<input name="email" type="email" defaultValue={selectedUser?.email||''} required maxLength={254} autoComplete="email"/></label></div>
        <label>Perfil de acesso<select aria-label="Perfil de acesso" name="perfil_id" required defaultValue={selectedUser?.perfil_id??profiles.perfis.find(p=>selectedUser?.administrador?p.administrador:p.nome==='Usuário')?.id}>
          {profiles.perfis.map(p=><option value={p.id} key={p.id}>{p.nome}</option>)}
        </select></label>
        <label className="checkbox"><input type="checkbox" name="ativo" defaultChecked={selectedUser?.ativo??true}/>Conta ativa</label>
        {editUser==='new'?<><div className="form-grid"><label>Senha inicial<input name="password" type="password" minLength={12} maxLength={1024} required autoComplete="new-password"/></label><label>Confirmar senha<input name="password_confirmation" type="password" minLength={12} maxLength={1024} required autoComplete="new-password"/></label></div><p className="muted">Use pelo menos 12 caracteres. A redefinição de senha é feita pela administração.</p></>:<p className="muted">Desativar uma conta bloqueia seu acesso e preserva o histórico. Use Redefinir senha na lista de usuários quando necessário.</p>}
        <div className="form-actions"><button disabled={busy} type="submit" data-icon="save"><ActionIcon name="save"/>{busy?'Salvando…':'Salvar usuário'}</button></div>
      </form>
    </section> : editProfile ? <section className="card form-card"><div className="section-heading"><h2>{editProfile==='new'?'Criar perfil':'Editar perfil'}</h2><button className="secondary" disabled={busy} onClick={()=>setEditProfile(null)} data-icon="close"><ActionIcon name="close"/>Cancelar</button></div>
      <form key={selectedProfile?.id||'new'} onSubmit={saveProfile}>
        <label>Nome do perfil<input name="nome" defaultValue={selectedProfile?.nome||''} maxLength={80} required/></label>
        <fieldset className="permission-options"><legend>Permissões</legend><p className="muted">Todos os perfis podem consultar o monitoramento e as fontes. Selecione as ações adicionais.</p>
          {Object.entries(profiles.permissoes).map(([key,label])=><label className="checkbox" key={key}><input type="checkbox" name="permissoes" value={key} defaultChecked={selectedProfile?.permissoes.includes(key)||false}/>{label}</label>)}
        </fieldset>
        <p className="muted">Gerenciar usuários e perfis é exclusivo do perfil Administrador.</p>
        <div className="form-actions"><button disabled={busy} type="submit" data-icon="save"><ActionIcon name="save"/>{busy?'Salvando…':'Salvar perfil'}</button></div>
      </form>
    </section> : <section className="card source-list admin-list">
      <div className="section-heading"><h2>{tab==='usuarios'?'Usuários cadastrados':tab==='perfis'?'Perfis de acesso':'Histórico de ações'}</h2>
        {tab!=='auditoria'&&<button disabled={loading} onClick={()=>{setError('');tab==='usuarios'?setEditUser('new'):setEditProfile('new');}} data-icon="plus"><ActionIcon name="plus"/>{tab==='usuarios'?'Cadastrar usuário':'Criar perfil'}</button>}
      </div>
      {tab==='usuarios'&&<label className="source-search">Pesquisar usuários<input type="search" value={query} maxLength={200} onChange={e=>{setQuery(e.target.value);setPage(1);}} placeholder="Nome ou e-mail"/></label>}
      {loading?<p role="status">Carregando…</p>:tab==='usuarios'?<>
        {!users.usuarios.length?<p>Nenhum usuário encontrado.</p>:<div className="table-scroll"><table><thead><tr><th>Usuário</th><th>Perfil</th><th>Situação</th><th>Ações</th></tr></thead><tbody>
          {users.usuarios.map(u=><tr key={u.id}><td><strong>{u.nome}{u.id===user.id?' (você)':''}</strong><small>{u.email}</small></td><td data-label="Perfil">{u.perfil}</td><td data-label="Situação"><span className={`badge ${u.ativo?'':'inactive'}`}>{u.ativo?'Ativo':'Desativado'}</span></td><td data-label="Ações"><button className="secondary" aria-label={`Editar usuário ${u.email}`} onClick={()=>{setError('');setEditUser(u);}} data-icon="edit"><ActionIcon name="edit"/>Editar</button><button className="secondary" aria-label={`Redefinir senha de ${u.email}`} onClick={()=>{setError('');setSuccess('');setResetUser(u);}} data-icon="key"><ActionIcon name="key"/>Redefinir senha</button></td></tr>)}
        </tbody></table></div>}
        <Pagination page={users.page} pages={users.pages} onPage={setPage}/>
      </>:tab==='perfis'?<>
        <p className="muted">Os perfis padrão são fixos. Perfis personalizados permitem distribuir as tarefas sem conceder administração de contas.</p>
        <div className="table-scroll"><table><thead><tr><th>Perfil</th><th>Permissões</th><th>Ações</th></tr></thead><tbody>
          {profiles.perfis.map(p=><tr key={p.id}><td><strong>{p.nome}</strong>{p.sistema&&<small>Padrão do sistema</small>}</td><td data-label="Permissões">Consulta de dados e fontes{p.permissoes.map(key=><small key={key}>{profiles.permissoes[key]}</small>)}{p.administrador&&<small>Gerenciar usuários, perfis e auditoria</small>}</td><td data-label="Ações">{p.sistema?<span className="muted">Perfil fixo</span>:<button className="secondary" aria-label={`Editar perfil ${p.nome}`} onClick={()=>{setError('');setEditProfile(p);}} data-icon="edit"><ActionIcon name="edit"/>Editar</button>}</td></tr>)}
        </tbody></table></div>
      </>:<>
        {!audit.registros.length?<p>Nenhuma ação registrada.</p>:<div className="table-scroll"><table><thead><tr><th>Quando / responsável</th><th>Ação</th><th>Registro</th></tr></thead><tbody>
          {audit.registros.map(r=><tr key={r.id}><td>{new Date(r.criada_em).toLocaleString('pt-BR')}<small>{r.usuario}</small></td><td data-label="Ação">{actionLabels[r.acao]||r.acao.replaceAll('_',' ')}</td><td data-label="Registro">{entityLabels[r.entidade]||r.entidade}{r.entidade_id?` · ${r.entidade_id}`:''}{Object.keys(r.detalhes as object).length>0&&<details><summary>Ver alterações</summary><AuditDetails details={r.detalhes} permissions={profiles.permissoes}/></details>}</td></tr>)}
        </tbody></table></div>}
        <Pagination page={audit.page} pages={audit.pages} onPage={setPage}/>
      </>}
    </section>}
  </section>;
}

function Pagination({page,pages,onPage}:{page:number;pages:number;onPage:(page:number)=>void}){
  return <div className="pagination"><button className="secondary" disabled={page<=1} onClick={()=>onPage(page-1)} data-icon="arrowLeft"><ActionIcon name="arrowLeft"/>Anterior</button><span>Página {page} de {pages}</span><button className="secondary" disabled={page>=pages} onClick={()=>onPage(page+1)} data-icon="arrowRight"><ActionIcon name="arrowRight"/>Próxima</button></div>;
}

const actionLabels:Record<string,string>={usuario_criado:'Usuário criado',usuario_editado:'Usuário editado',usuario_cadastrado:'Conta cadastrada',perfil_criado:'Perfil criado',perfil_editado:'Perfil editado',dados_exportados:'Dados exportados',senha_alterada:'Senha alterada',senha_redefinida:'Senha redefinida pelo administrador',fonte_criada:'Fonte criada',fonte_atualizada:'Fonte atualizada',fonte_arquivada:'Fonte arquivada',fonte_restaurada:'Fonte restaurada',coleta_concluida:'Coleta concluída'};
const entityLabels:Record<string,string>={Usuario:'Usuário',PerfilAcesso:'Perfil de acesso',Exportacao:'Exportação',FonteEpidemiologica:'Fonte',ExecucaoColeta:'Coleta'};
function AuditDetails({details,permissions}:{details:unknown;permissions:Record<string,string>}){
  const data=details as Record<string,unknown>;
  const labels:Record<string,string>={nome:'Nome',email:'E-mail',perfil:'Perfil',ativo:'Conta ativa',permissoes:'Permissões',modo:'Conteúdo',formato:'Formato',registros:'Registros',tipo:'Recorte',codigo:'Código territorial',agravo:'Agravo',indicador:'Indicador',inicio:'De',fim:'Até'};
  function value(v:unknown):string{if(v===null||v===undefined||v==='')return '—';if(typeof v==='boolean')return v?'Sim':'Não';if(Array.isArray(v))return v.length?v.map(p=>permissions[String(p)]||String(p)).join(', '):'Somente consulta';return String(v);}
  if('antes' in data){
    const before=(data.antes||{}) as Record<string,unknown>,after=(data.depois||{}) as Record<string,unknown>;
    return <dl className="audit-details">{['nome','email','perfil','ativo','permissoes'].filter(k=>k in after||k in before).map(k=><div key={k}><dt>{labels[k]}</dt><dd>{Boolean(data.antes)&&<><span className="muted">Antes: {value(before[k])}</span><br/></>}{value(after[k])}</dd></div>)}</dl>;
  }
  const fields={...data,...((data.filtros||{}) as Record<string,unknown>)};
  return <dl className="audit-details">{Object.entries(fields).filter(([k,v])=>k!=='filtros'&&v!=='').map(([k,v])=><div key={k}><dt>{labels[k]||k}</dt><dd>{value(v)}</dd></div>)}</dl>;
}
