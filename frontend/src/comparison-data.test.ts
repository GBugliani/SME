import {describe,it,expect} from 'vitest';
import {comparisonData,comparisonPeriod} from './comparison-data';
const series=(rows:[string,number|null][])=>({serie:rows.map(([data,casos])=>({data,casos}))});

describe('comparação territorial',()=>{
  it('mantém as semanas intermediárias entre históricos de anos diferentes',()=>{
    const result=comparisonData([series([['2023-12-31',5]]),series([['2026-01-04',10]])]);
    expect(result.dates).toHaveLength(106);
    expect(result.dates).toContain('2025-12-28');
    expect(result.commonWeeks).toBe(0);
    expect(result.segments.map(s=>s[0][0].index)).toEqual([0,105]);
  });
  it('separa pontos isolados e lacunas, sem conectar semanas ausentes',()=>{
    const result=comparisonData([series([['2024-01-07',3],['2024-01-14',null],['2024-01-21',5]])]);
    expect(result.segments[0]).toEqual([[{index:0,value:3}],[{index:2,value:5}]]);
  });
  it('trata zero como dado válido e conta semanas comuns',()=>{
    const result=comparisonData([series([['2024-01-07',0],['2024-01-14',0]]),series([['2024-01-07',1],['2024-01-14',null]])]);
    expect(result.commonWeeks).toBe(1);
    expect(result.seriesWithData).toBe(2);
    expect(result.segments[0][0]).toHaveLength(2);
  });
  it('distingue série sem contagem de série com pontos',()=>{
    const result=comparisonData([series([['2024-01-07',null]]),series([])]);
    expect(result.seriesWithData).toBe(0);
    expect(result.commonWeeks).toBe(0);
    expect(result.segments).toEqual([[],[]]);
  });
  it('exibe os filtros efetivos, incluindo datas em aberto',()=>{
    expect(comparisonPeriod()).toBe('Todo o histórico disponível');
    expect(comparisonPeriod('2025-01-01',null)).toBe('A partir de 01/01/2025');
    expect(comparisonPeriod(null,'2026-01-01')).toBe('Até 01/01/2026');
    expect(comparisonPeriod('2024-01-01','2024-12-31')).toBe('01/01/2024 a 31/12/2024');
  });
});
