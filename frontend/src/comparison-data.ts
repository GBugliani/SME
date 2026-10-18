type Series={serie:{data:string;casos:number|null}[]};
type Sample={index:number;value:number};

export function comparisonData(series:Series[]){
  const available=[...new Set(series.flatMap(s=>s.serie.map(p=>p.data)))].sort();
  const dates:string[]=[];
  if(available.length){
    const end=Date.parse(`${available.at(-1)}T00:00:00Z`);
    for(let day=Date.parse(`${available[0]}T00:00:00Z`);day<=end;day+=7*86400000)
      dates.push(new Date(day).toISOString().slice(0,10));
  }
  const maps=series.map(s=>new Map(s.serie.map(p=>[p.data,p.casos])));
  const segments=maps.map(map=>{
    const result:Sample[][]=[];let segment:Sample[]=[];
    dates.forEach((day,index)=>{
      const value=map.get(day);
      if(value==null){if(segment.length)result.push(segment);segment=[];}
      else segment.push({index,value});
    });
    if(segment.length)result.push(segment);
    return result;
  });
  return {dates,maps,segments,commonWeeks:dates.filter(day=>maps.length>0&&maps.every(m=>m.get(day)!=null)).length,
    seriesWithData:segments.filter(s=>s.length>0).length};
}

export function comparisonPeriod(start?:string|null,end?:string|null){
  const format=(value:string)=>value.split('-').reverse().join('/');
  if(start&&end)return `${format(start)} a ${format(end)}`;
  if(start)return `A partir de ${format(start)}`;
  if(end)return `Até ${format(end)}`;
  return 'Todo o histórico disponível';
}
