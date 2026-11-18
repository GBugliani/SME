export type SharedQuery={tipo:string;codigo:string;agravo:string;indicador:string;inicio:string;fim:string};
const keys=['consulta','tipo','codigo','agravo','indicador','inicio','fim'];
export function readSharedQuery(search:string):SharedQuery|null{
  const params=new URLSearchParams(search);
  if(!params.has('consulta'))return null;
  if(params.get('consulta')!=='1'||keys.some(key=>params.getAll(key).length>1))throw new Error('O link da consulta é inválido. Selecione os dados pelos filtros.');
  const query=Object.fromEntries(keys.slice(1).map(key=>[key,params.get(key)||''])) as SharedQuery;
  const validDate=(value:string)=>!value||(/^\d{4}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value))&&new Date(value).toISOString().slice(0,10)===value);
  if(!['municipio','regiao'].includes(query.tipo)||!/^\d{1,10}$/.test(query.codigo)||!query.agravo||!query.indicador||query.agravo.length>80||query.indicador.length>80||!validDate(query.inicio)||!validDate(query.fim)||(query.inicio&&query.fim&&query.inicio>query.fim))throw new Error('O link contém filtros ou datas inválidos. Revise a consulta pelos filtros.');
  return query;
}
export function sharedQueryUrl(base:string,query:SharedQuery):string{
  const url=new URL(base);url.search='';url.hash='';
  url.searchParams.set('consulta','1');
  for(const [key,value] of Object.entries(query))if(value)url.searchParams.set(key,value);
  return url.toString();
}
export function clearSharedQuery(){
  const url=new URL(window.location.href);
  for(const key of keys)url.searchParams.delete(key);
  window.history.replaceState(null,'',url);
}
