import {ActionIcon} from './action-icon';
import {createPortal} from 'react-dom';
import {useCallback,useEffect,useRef,useState,type ReactNode} from 'react';

export function Notice({message,kind='error',children}:{message:string;kind?:'error'|'success';children?:ReactNode}) {
  const [visible,setVisible]=useState(false);
  const toast=useRef<HTMLDivElement>(null);

  useEffect(()=>{setVisible(Boolean(message));const timer=setTimeout(()=>setVisible(false),8000);return()=>clearTimeout(timer);},[message]);
  useEffect(()=>{if(visible)toast.current?.showPopover();},[visible,message]);

  return visible?createPortal(<div ref={toast} popover="manual" className={`notice toast ${kind}`} role={kind==='error'?'alert':'status'}><span className="toast-symbol" aria-hidden="true"><ActionIcon name={kind==='success'?'check':'bell'}/></span><div className="toast-content">{message}{children}</div><button type="button" className="toast-close" aria-label="Fechar aviso" onClick={()=>setVisible(false)}><ActionIcon name="close"/></button></div>,document.body):null;
}

export function useTimedMessage(duration=8000):[string,(message:string)=>void] {
  const [message,setMessage]=useState('');
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const show=useCallback((value:string)=>{
    if(timer.current!==null)clearTimeout(timer.current);
    timer.current=null;setMessage(value);
    if(value)timer.current=setTimeout(()=>{timer.current=null;setMessage('');},duration);
  },[duration]);
  useEffect(()=>()=>{if(timer.current!==null)clearTimeout(timer.current);},[]);
  return [message,show];
}
