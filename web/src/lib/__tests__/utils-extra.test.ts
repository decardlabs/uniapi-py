import { describe, it, expect } from 'vitest';
import { generateUUIDv4, formatNumber } from '@/lib/utils';

describe('generateUUIDv4', () => {
  it('returns a string matching UUID v4 format', () => {
    const uuid = generateUUIDv4();
    expect(uuid).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });

  it('generates unique values on successive calls', () => {
    const uuids = new Set(Array.from({ length: 100 }, () => generateUUIDv4()));
    expect(uuids.size).toBe(100);
  });
});

describe('formatNumber', () => {
  it('formats integers', () => {
    expect(formatNumber(42)).toBe('42');
  });

  it('formats large numbers with abbreviations', () => {
    expect(formatNumber(1234567)).toMatch(/^\d+\.?\d*M$/);
    expect(formatNumber(1234)).toMatch(/^\d+\.?\d*K$/);
  });

  it('formats zero', () => {
    expect(formatNumber(0)).toBe('0');
  });

  it('formats negative numbers', () => {
    expect(formatNumber(-5)).toBe('-5');
  });

  it('formats floats', () => {
    const result = formatNumber(3.14);
    expect(result).toContain('3');
    expect(result).toContain('14');
  });
});
