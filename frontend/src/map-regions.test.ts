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
    expect(map.labels.map(label => label.name)).toEqual(intermediateRegions.map(region => region.name));
    expect(map.labels.every(label => Number.isFinite(label.x) && Number.isFinite(label.y))).toBe(true);
  });
});
