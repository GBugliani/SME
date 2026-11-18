import {useEffect,useRef,type ReactNode} from 'react';
export function Modal({title,onClose,children,compact=false}:{title:string;onClose:()=>void;children:ReactNode;compact?:boolean}){
  const ref=useRef<HTMLDialogElement>(null);
  useEffect(()=>{ref.current?.showModal();const previous=document.body.style.overflow;document.body.style.overflow='hidden';return()=>{document.body.style.overflow=previous;};},[]);
  return <dialog ref={ref} className={`source-modal ${compact?'confirmation-modal':''}`} aria-label={title} onCancel={event=>{event.preventDefault();onClose();}}>{children}</dialog>;
}
