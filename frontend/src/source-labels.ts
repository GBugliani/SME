import type {Source} from './api';

export function territoryLabel(source:Source) {
  return `${source.recorte_nome}${source.recorte_uf?` / ${source.recorte_uf}`:''} · ${source.recorte_tipo==='municipio'?'IBGE':'Código'} ${source.recorte_codigo}`;
}

export function sourcePeriodLabel(source:Pick<Source,'url'|'nome'|'integracao'|'periodo_movel'>&{url_coleta?:string}) {
  try {
    if(source.periodo_movel)return `${source.integracao?.publicador||'Fonte'} · ${source.integracao?.agravo_nome||''} · ${['sivep','esus'].includes(source.integracao?.provedor||'')?'Ano atual automático':'Ano atual e anterior automáticos'}`;
    const url=new URL(source.url);
    if(['sivep','esus'].includes(source.integracao?.provedor||''))return `${source.integracao?.publicador} ${url.searchParams.get('ano')||''} · ${source.integracao?.agravo_nome}`;
    if(url.hostname!=='info.dengue.mat.br'||url.pathname!=='/api/alertcity')return source.integracao?`${source.integracao.publicador} · ${source.integracao.agravo_nome}`:source.nome;
    const first=url.searchParams.get('ey_start'),last=url.searchParams.get('ey_end');
    if(!first||!last||!/^\d{4}$/.test(first)||!/^\d{4}$/.test(last)||first>last)return source.integracao?`${source.integracao.publicador} · ${source.integracao.agravo_nome}`:source.nome;
    return `InfoDengue ${first}${first===last?'':`-${last}`} · ${source.integracao?.agravo_nome||url.searchParams.get('disease')||''}`;
  } catch {return source.integracao?`${source.integracao.publicador} · ${source.integracao.agravo_nome}`:source.nome;}
}
