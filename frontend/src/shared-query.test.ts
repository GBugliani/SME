import {describe,expect,it} from 'vitest';
import {readSharedQuery,sharedQueryUrl} from './shared-query';

const query={tipo:'municipio',codigo:'3550308',agravo:'dengue',indicador:'infodengue_dengue',inicio:'2026-01-04',fim:'2026-10-25'};
describe('links de consulta',()=>{
  it('restaura todos os filtros e remove parâmetros alheios do link copiado',()=>{
    const url=new URL(sharedQueryUrl('https://sme.example.org/?token=privado#outro',query));
    expect(readSharedQuery(url.search)).toEqual(query);
    expect(url.searchParams.has('token')).toBe(false);
    expect(url.hash).toBe('');
  });
  it('aceita região e período aberto sem inventar datas',()=>{
    const region={...query,tipo:'regiao',codigo:'350001',inicio:'',fim:''};
    expect(readSharedQuery(new URL(sharedQueryUrl('http://localhost:8080/',region)).search)).toEqual(region);
  });
  it('rejeita datas inexistentes, intervalos invertidos e parâmetros repetidos',()=>{
    for(const value of [{...query,inicio:'2026-02-30'},{...query,inicio:'2026-12-01'}]){
      expect(()=>readSharedQuery(new URL(sharedQueryUrl('https://sme.example.org/',value)).search)).toThrow();
    }
    expect(()=>readSharedQuery(new URL(sharedQueryUrl('https://sme.example.org/',query)).search+'&codigo=123')).toThrow();
  });
  it('não inicia consulta em uma visita comum',()=>{
    expect(readSharedQuery('')).toBeNull();
    expect(readSharedQuery('?origem=site')).toBeNull();
  });
});
