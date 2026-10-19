import immediateRegions from './regions.json';

type Municipality = { id: string; path: string };
type Point = { x: number; y: number };

// IBGE, Divisão Regional do Brasil em Regiões Geográficas Imediatas e Intermediárias (2017).
// Os códigos das regiões imediatas 350001–350053 já estão em regions.json.
// https://biblioteca.ibge.gov.br/visualizacao/livros/liv100600.pdf
export const intermediateRegions = [
  { code: '3501', name: 'São Paulo', shortName: 'São Paulo', first: 1, last: 2 },
  { code: '3502', name: 'Sorocaba', shortName: 'Sorocaba', first: 3, last: 8 },
  { code: '3503', name: 'Bauru', shortName: 'Bauru', first: 9, last: 12 },
  { code: '3504', name: 'Marília', shortName: 'Marília', first: 13, last: 17 },
  { code: '3505', name: 'Presidente Prudente', shortName: 'Pres. Prudente', first: 18, last: 21 },
  { code: '3506', name: 'Araçatuba', shortName: 'Araçatuba', first: 22, last: 24 },
  { code: '3507', name: 'São José do Rio Preto', shortName: 'S. J. Rio Preto', first: 25, last: 30 },
  { code: '3508', name: 'Ribeirão Preto', shortName: 'Ribeirão Preto', first: 31, last: 35 },
  { code: '3509', name: 'Araraquara', shortName: 'Araraquara', first: 36, last: 37 },
  { code: '3510', name: 'Campinas', shortName: 'Campinas', first: 38, last: 48 },
  { code: '3511', name: 'São José dos Campos', shortName: 'S. J. Campos', first: 49, last: 53 },
] as const;

const regionByCity = new Map<string, number>();
for (const [immediateCode, cities] of Object.entries(immediateRegions as Record<string, string[]>)) {
  const number = Number(immediateCode.slice(-2));
  const region = intermediateRegions.findIndex(item => number >= item.first && number <= item.last);
  for (const code of cities) regionByCity.set(code, region);
}

export function getIntermediateRegionIndex(cityCode: string) {
  return regionByCity.get(cityCode) ?? -1;
}

export type RegionLabel = { code: string; name: string; shortName: string; x: number; y: number };
export type MapRegions = { borders: string; labels: RegionLabel[] };
type PlacedRegionLabel = RegionLabel & { offsetX: number; offsetY: number };

function rings(path: string): Point[][] {
  return (path.match(/M[^Z]*Z/g) ?? []).map(ring =>
    Array.from(ring.matchAll(/[ML](-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/g), match => ({ x: Number(match[1]), y: Number(match[2]) })),
  ).filter(points => points.length >= 3);
}

function centroid(points: Point[]) {
  let area = 0, x = 0, y = 0;
  for (let i = 0; i < points.length; i++) {
    const a = points[i], b = points[(i + 1) % points.length];
    const cross = a.x * b.y - b.x * a.y;
    area += cross;
    x += (a.x + b.x) * cross;
    y += (a.y + b.y) * cross;
  }
  if (Math.abs(area) < 0.001) return null;
  return { area: Math.abs(area / 2), x: x / (3 * area), y: y / (3 * area) };
}

export function buildMapRegions(cities: Municipality[]): MapRegions {
  const edges = new Map<string, { a: Point; b: Point; regions: Set<number> }>();
  const centers = intermediateRegions.map(() => ({ weight: 0, x: 0, y: 0 }));

  for (const city of cities) {
    const region = getIntermediateRegionIndex(city.id);
    if (region < 0) continue;
    for (const points of rings(city.path)) {
      const center = centroid(points);
      if (center) {
        centers[region].weight += center.area;
        centers[region].x += center.x * center.area;
        centers[region].y += center.y * center.area;
      }
      for (let i = 0; i < points.length; i++) {
        const a = points[i], b = points[(i + 1) % points.length];
        const aKey = `${a.x},${a.y}`, bKey = `${b.x},${b.y}`;
        const key = aKey < bKey ? `${aKey}|${bKey}` : `${bKey}|${aKey}`;
        const edge = edges.get(key);
        if (edge) edge.regions.add(region);
        else edges.set(key, { a, b, regions: new Set([region]) });
      }
    }
  }

  return {
    borders: Array.from(edges.values()).filter(edge => edge.regions.size > 1)
      .map(edge => `M${edge.a.x},${edge.a.y}L${edge.b.x},${edge.b.y}`).join(''),
    labels: intermediateRegions.map((item, index) => ({
      code: item.code, name: item.name, shortName: item.shortName,
      x: centers[index].weight ? centers[index].x / centers[index].weight : 0,
      y: centers[index].weight ? centers[index].y / centers[index].weight : 0,
    })),
  };
}

export function placeRegionLabels(labels: RegionLabel[], pixelsPerUnit: number, compact: boolean): PlacedRegionLabel[] {
  const scale = Math.max(0.01, pixelsPerUnit);
  const placed: { left: number; top: number; right: number; bottom: number }[] = [];
  const offsets = compact
    ? [[0, 0], [0, -17], [0, 17], [-24, 0], [24, 0], [-32, -18], [32, -18], [-32, 18], [32, 18], [0, -34], [0, 34], [-52, -12], [52, -12], [-52, 12], [52, 12], [0, -51], [0, 51]]
    : [[0, 0], [0, -21], [0, 21], [-30, 0], [30, 0], [-45, -20], [45, -20], [-45, 20], [45, 20]];

  return [...labels].sort((a, b) => a.y - b.y || a.x - b.x).map(label => {
    const name = compact ? label.shortName : label.name;
    const width = name.length * (compact ? 5.8 : 6.8) + 8;
    const height = compact ? 15 : 18;
    let best: { x: number; y: number; score: number; rect: { left: number; top: number; right: number; bottom: number } } | null = null;
    for (const [x, y] of offsets) {
      const centerX = label.x * scale + x, centerY = label.y * scale + y;
      const rect = { left: centerX - width / 2, right: centerX + width / 2, top: centerY - height / 2, bottom: centerY + height / 2 };
      const overlap = placed.reduce((sum, other) => sum + Math.max(0, Math.min(rect.right, other.right) - Math.max(rect.left, other.left)) * Math.max(0, Math.min(rect.bottom, other.bottom) - Math.max(rect.top, other.top)), 0);
      const score = overlap * 100 + Math.hypot(x, y);
      if (!best || score < best.score) best = { x, y, score, rect };
      if (score === 0) break;
    }
    if (!best) return { ...label, offsetX: 0, offsetY: 0 };
    placed.push(best.rect);
    return { ...label, offsetX: best.x, offsetY: best.y };
  });
}

export function MapRegionLabels({ labels, pixelsPerUnit, focusedCode, onSelect }: { labels: RegionLabel[]; pixelsPerUnit: number; focusedCode: string | null; onSelect: (code: string) => void }) {
  const scale = Math.max(0.01, pixelsPerUnit);
  const inverseScale = 1 / scale;
  const visibleLabels = focusedCode ? labels.filter(label => label.code === focusedCode) : labels;
  const positioned = placeRegionLabels(visibleLabels, scale, window.matchMedia('(max-width: 760px)').matches);
  return <g className="map-region-labels">{positioned.map(label =>
    <g key={label.code} className={focusedCode ? '' : 'map-region-label-button'} role={focusedCode ? undefined : 'button'} tabIndex={focusedCode ? undefined : 0} aria-label={focusedCode ? undefined : `Ampliar região de ${label.name}`} onClick={focusedCode ? undefined : () => onSelect(label.code)} onKeyDown={focusedCode ? undefined : event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(label.code); } }} data-map-region={label.code} data-region-x={label.x} data-region-y={label.y} data-offset-x={label.offsetX} data-offset-y={label.offsetY} transform={`translate(${label.x + label.offsetX / scale} ${label.y + label.offsetY / scale}) scale(${inverseScale})`}>
      {(label.offsetX !== 0 || label.offsetY !== 0) && <line x1={-label.offsetX} y1={-label.offsetY} x2="0" y2="0"/>}
      <text className="region-name-full" textAnchor="middle" dominantBaseline="central">{label.name}</text>
      <text className="region-name-short" textAnchor="middle" dominantBaseline="central">{label.shortName}</text>
    </g>,
  )}</g>;
}
