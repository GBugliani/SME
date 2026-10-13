import {useEffect, useId, useRef, useState} from 'react';
import type {User} from './api';

export function AccountMenu({user, onPassword, onLogout}: {user:User; onPassword:()=>void; onLogout:()=>void}) {
  const [open,setOpen]=useState(false);
  const container=useRef<HTMLDivElement>(null);
  const trigger=useRef<HTMLButtonElement>(null);
  const id=useId();
  const name=user.nome.trim() || user.email;
  const distinctName=name.toLowerCase() !== user.email.trim().toLowerCase();
  useEffect(()=>{
    if(!open) return;
    const outside=(event:PointerEvent)=>{if(!container.current?.contains(event.target as Node))setOpen(false);};
    const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'){setOpen(false);trigger.current?.focus();}};
    document.addEventListener('pointerdown',outside);
    document.addEventListener('keydown',escape);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};
  },[open]);
  function select(action:()=>void){setOpen(false);trigger.current?.focus();action();}
  return <div className="profile-control" ref={container} onBlur={event=>{if(!event.currentTarget.contains(event.relatedTarget as Node|null))setOpen(false);}}>
    <button className="profile-trigger secondary" ref={trigger} aria-label={`Perfil de ${name}`} title={name} aria-expanded={open} aria-controls={id} onClick={()=>setOpen(value=>!value)}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></svg>
    </button>
    {open && <div id={id} className="profile-panel" aria-label="Opções da conta">
      <div className="profile-identity"><strong>{name}</strong>{distinctName && <small>{user.email}</small>}<span>{user.administrador?'Administrador':'Usuário'}</span></div>
      <button onClick={()=>select(onPassword)}>Alterar senha</button>
      <button onClick={()=>select(onLogout)}>Sair</button>
    </div>}
  </div>;
}
