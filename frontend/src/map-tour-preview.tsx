import {ActionIcon} from './action-icon';
import type {Integration} from './api';
import type {MapLatestWeek, MapSignal} from './monitoring';

export function MapTourPreview({cityName,integrations,latestWeek,signal,onSelect,onEngagementChange}:{cityName:string;integrations:Integration[];latestWeek?:MapLatestWeek;signal?:MapSignal;onSelect:()=>void;onEngagementChange:(engaged:boolean)=>void}) {
  const primary=integrations[0];
  if(!primary)return null;
  const diseases=[...new Set(integrations.map(item=>item.agravo_nome))];
  const visibleDiseases=diseases.slice(0,2).join(' · ');
  return <button type="button" className="map-tour-preview" onClick={onSelect} onMouseEnter={()=>onEngagementChange(true)} onMouseLeave={event=>onEngagementChange(event.currentTarget===document.activeElement)} onFocus={()=>onEngagementChange(true)} onBlur={event=>onEngagementChange(event.currentTarget.matches(':hover'))}>
    <span className="map-tour-preview-eyebrow">MUNICÍPIO EM DESTAQUE</span>
    <strong>{cityName}</strong>
    <span className="map-tour-preview-diseases">{visibleDiseases}{diseases.length>2?` e mais ${diseases.length-2}`:''}</span>
    <small>{integrations.length} {integrations.length===1?'série disponível':'séries disponíveis'}</small>
    {latestWeek&&<span className="map-tour-preview-latest"><b>{latestWeek.casos.toLocaleString('pt-BR')}</b><span>{latestWeek.casos===1?'caso':'casos'} de {primary.agravo_nome}<small>Semana de {latestWeek.data_referencia.split('-').reverse().join('/')}</small></span></span>}
    {signal&&<small>Casos acima do limiar de sinalização · semana de {signal.data_referencia.split('-').reverse().join('/')}</small>}
    <span className="map-tour-preview-action">Ver dados de {primary.agravo_nome}<ActionIcon name="arrowRight"/></span>
  </button>;
}
