import {createRoot} from 'react-dom/client';
import {Modal} from './modal';
export function confirmAction(message:string):Promise<boolean>{
  return new Promise(resolve=>{
    const host=document.createElement('div');document.body.appendChild(host);
    const root=createRoot(host);
    const finish=(value:boolean)=>{root.unmount();host.remove();resolve(value);};
    root.render(<Modal compact title="Confirmar ação" onClose={()=>finish(false)}><h2>Confirmar ação</h2><p>{message}</p><div className="filter-actions"><button className="secondary" onClick={()=>finish(false)}>Cancelar</button><button onClick={()=>finish(true)}>Confirmar</button></div></Modal>);
  });
}
