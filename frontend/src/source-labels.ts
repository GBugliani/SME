import type {Source} from './api';

export function territoryLabel(source:Source) {
  return `${source.recorte_nome}${source.recorte_uf?` / ${source.recorte_uf}`:''} · ${source.recorte_tipo==='municipio'?'IBGE':'Código'} ${source.recorte_codigo}`;
}

export function sourcePeriodLabel(source:Pick<Source,'url'|'nome'>) {
  try {
    const url=new URL(source.url);
    if(url.hostname!=='info.dengue.mat.br'||url.pathname!=='/api/alertcity')return source.nome;
    const first=url.searchParams.get('ey_start'),last=url.searchParams.get('ey_end');
    if(!first||!last||!/^\d{4}$/.test(first)||!/^\d{4}$/.test(last)||first>last)return source.nome;
    return `InfoDengue ${first}${first===last?'':`-${last}`}`;
  } catch {return source.nome;}
}
