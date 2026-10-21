import { describe, expect, it } from 'vitest';
import municipalities from './municipalities.json';
import { buildMapRegions, getIntermediateRegionIndex, intermediateRegions } from './map-regions';

describe('regiões geográficas intermediárias de São Paulo', () => {
  it('classifica todos os 645 municípios nas 11 regiões do IBGE', () => {
    expect(municipalities).toHaveLength(645);
    expect(intermediateRegions).toHaveLength(11);
    expect(municipalities.every(city => getIntermediateRegionIndex(city.id) >= 0)).toBe(true);
    expect(new Set(municipalities.map(city => getIntermediateRegionIndex(city.id))).size).toBe(11);
    expect(getIntermediateRegionIndex('3550308')).toBe(getIntermediateRegionIndex('3548500')); // São Paulo e Santos
    expect(getIntermediateRegionIndex('3509502')).not.toBe(getIntermediateRegionIndex('3550308')); // Campinas
  });

  it('desenha divisões entre regiões e posiciona um nome para cada uma', () => {
    const map = buildMapRegions(municipalities);
    expect((map.borders.match(/M/g) ?? []).length).toBeGreaterThan(100);
    expect(map.outlines).toHaveLength(intermediateRegions.length);
    expect(map.outlines.every(outline => outline.length > 0)).toBe(true);
    expect(map.labels.map(label => label.name)).toEqual(intermediateRegions.map(region => region.name));
    expect(map.labels.every(label => Number.isFinite(label.x) && Number.isFinite(label.y))).toBe(true);
  });

  it('contorna a região sem redesenhar os limites entre seus municípios', () => {
    const map = buildMapRegions([
      { id: '3550308', path: 'M0,0L1,0L1,1L0,1Z' },
      { id: '3548500', path: 'M1,0L2,0L2,1L1,1Z' },
      { id: '3509502', path: 'M2,0L3,0L3,1L2,1Z' },
    ]);
    const saoPaulo = getIntermediateRegionIndex('3550308');
    const campinas = getIntermediateRegionIndex('3509502');

    expect(map.outlines[saoPaulo]).not.toContain('M1,0L1,1');
    expect(map.outlines[saoPaulo]).toContain('M2,0L2,1');
    expect(map.outlines[campinas]).toContain('M2,0L2,1');
    expect(map.borders).toContain('M2,0L2,1');
  });
});
