import {useEffect, useLayoutEffect, useRef, useState} from 'react';
import {ActionIcon} from './action-icon';
import type {Integration} from './api';
import type {IndicatorOptions} from './monitoring';

export type PickedCity = {id:string; name:string; x:number; y:number};

export function availableCityIntegrations(options:IndicatorOptions|null, cityCode:string):Integration[] {
  return options?.integracoes.filter(item=>item.codigos_com_dados?.includes(cityCode)) ?? [];
}

export function MapCityPicker({city, options, onSelect, onClose}: {
  city:PickedCity;
  options:IndicatorOptions|null;
  onSelect:(integration:Integration)=>void;
  onClose:()=>void;
}) {
  const integrations=availableCityIntegrations(options,city.id);
  const panel=useRef<HTMLDivElement>(null);
  const [position,setPosition]=useState({x:city.x+14,y:city.y+14});
  useLayoutEffect(()=>{
    const box=panel.current?.getBoundingClientRect();
    if(!box)return;
    panel.current?.querySelector<HTMLButtonElement>('.map-city-picker-options button, .map-city-picker-heading button')?.focus({preventScroll:true});
    setPosition({
      x:Math.max(12,Math.min(city.x+14,window.innerWidth-box.width-12)),
      y:Math.max(12,Math.min(city.y+14,window.innerHeight-box.height-12)),
    });
  },[city]);
  useEffect(()=>{
    const key=(event:KeyboardEvent)=>{if(event.key==='Escape')onClose();};
    const outside=(event:PointerEvent)=>{if(!panel.current?.contains(event.target as Node))onClose();};
    document.addEventListener('keydown',key);
    document.addEventListener('pointerdown',outside);
    return()=>{document.removeEventListener('keydown',key);document.removeEventListener('pointerdown',outside);};
  },[onClose]);
  return <div ref={panel} className="map-city-picker" role="dialog" aria-label={`Selecionar monitoramento de ${city.name}`} style={{left:position.x,top:position.y}}>
    <div className="map-city-picker-heading"><div><strong>{city.name}</strong><span>São Paulo · IBGE {city.id}</span></div><button type="button" className="secondary" aria-label="Fechar seleção do município" onClick={onClose} data-icon="close"><ActionIcon name="close"/></button></div>
    {options===null?<p>Carregando séries disponíveis…</p>:integrations.length===0?<p>Não há dados processados para este município.</p>:<><p>{integrations.length===1?'Selecione a série disponível:':'Selecione o agravo e a origem:'}</p><div className="map-city-picker-options">{integrations.map(item=><button type="button" className="secondary" key={item.codigo} onClick={()=>onSelect(item)} data-icon="arrowRight"><span><strong>{item.agravo_nome}</strong><small>{item.publicador} · {item.indicador_nome}</small></span><ActionIcon name="arrowRight"/></button>)}</div></>}
  </div>;
}
