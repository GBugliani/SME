import {useCallback,useEffect,useRef,useState,type ReactNode} from 'react';

export function Notice({message,kind='error',children}:{message:string;kind?:'error'|'success';children?:ReactNode}) {
  const [visible,setVisible]=useState(message);
  const [leaving,setLeaving]=useState(false);
  useEffect(()=>{
    if(message){setVisible(message);setLeaving(false);return;}
    setLeaving(true);
    const timer=setTimeout(()=>setVisible(''),220);
    return()=>clearTimeout(timer);
  },[message]);
  return visible?<div className={`${kind} notice ${leaving?'notice-leaving':''}`} role={kind==='error'?'alert':'status'}>{visible}{children}</div>:null;
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
