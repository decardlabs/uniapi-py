import { renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useDashboardCharts } from '../hooks/useDashboardCharts';
import type { ModelRow, UserRow, TokenRow } from '../types';

/**
 * Factory: build a ModelRow with defaults.
 * Tests only care about a few fields; omit the rest = 0 / ''.
 */
function model(overrides: Partial<ModelRow> = {}): ModelRow {
  return {
    day: '2026-06-24',
    model_name: 'gpt-4',
    request_count: 0,
    quota: 0,
    prompt_tokens: 0,
    completion_tokens: 0,
    ...overrides,
  };
}

describe('useDashboardCharts', () => {
  // ── rangeTotals ──

  it('rangeTotals sums requests, tokens, quota across rows', () => {
    const rows: ModelRow[] = [
      model({ model_name: 'gpt-4', request_count: 3, prompt_tokens: 100, completion_tokens: 50, quota: 150 }),
      model({ model_name: 'claude-3', request_count: 2, prompt_tokens: 200, completion_tokens: 100, quota: 300 }),
    ];
    const { result } = renderHook(() => useDashboardCharts(rows, [], [], 'tokens'));

    expect(result.current.rangeTotals.requests).toBe(5);
    expect(result.current.rangeTotals.tokens).toBe(450);  // 100+50 + 200+100
    expect(result.current.rangeTotals.quota).toBe(450);   // 150 + 300
    expect(result.current.rangeTotals.uniqueModels).toBe(2);
  });

  it('rangeTotals handles empty rows', () => {
    const { result } = renderHook(() => useDashboardCharts([], [], [], 'tokens'));
    expect(result.current.rangeTotals.requests).toBe(0);
    expect(result.current.rangeTotals.tokens).toBe(0);
    expect(result.current.rangeTotals.uniqueModels).toBe(0);
  });

  it('rangeTotals calculates averages correctly', () => {
    const rows: ModelRow[] = [
      model({ day: '2026-06-24', request_count: 10, prompt_tokens: 500, completion_tokens: 500, quota: 1000 }),
      model({ day: '2026-06-25', request_count: 20, prompt_tokens: 1000, completion_tokens: 0, quota: 500 }),
    ];
    const { result } = renderHook(() => useDashboardCharts(rows, [], [], 'tokens'));

    // tokens per request
    const totalTokens = (500 + 500) + (1000 + 0); // 2000
    const totalRequests = 30;
    expect(result.current.rangeTotals.avgTokensPerRequest).toBe(totalTokens / totalRequests);

    // daily avg
    expect(result.current.rangeTotals.avgDailyRequests).toBe(30 / 2);
    expect(result.current.rangeTotals.avgDailyTokens).toBe(2000 / 2);
  });

  // ── dailyAgg ──

  it('dailyAgg groups by day and sums metrics', () => {
    const rows: ModelRow[] = [
      model({ day: '2026-06-24', model_name: 'gpt-4', request_count: 3, prompt_tokens: 100, completion_tokens: 50, quota: 150 }),
      model({ day: '2026-06-24', model_name: 'claude-3', request_count: 2, prompt_tokens: 200, completion_tokens: 100, quota: 300 }),
      model({ day: '2026-06-25', model_name: 'gpt-4', request_count: 5, prompt_tokens: 400, completion_tokens: 200, quota: 600 }),
    ];
    const { result } = renderHook(() => useDashboardCharts(rows, [], [], 'tokens'));

    expect(result.current.dailyAgg).toHaveLength(2);
    const day1 = result.current.dailyAgg.find((d) => d.date === '2026-06-24')!;
    expect(day1.requests).toBe(5);
    expect(day1.tokens).toBe(450); // (100+50) + (200+100)

    const day2 = result.current.dailyAgg.find((d) => d.date === '2026-06-25')!;
    expect(day2.requests).toBe(5);
    expect(day2.tokens).toBe(600);
  });

  it('dailyAgg sorts by date ascending', () => {
    const rows: ModelRow[] = [
      model({ day: '2026-06-25' }),
      model({ day: '2026-06-24' }),
      model({ day: '2026-06-26' }),
    ];
    const { result } = renderHook(() => useDashboardCharts(rows, [], [], 'tokens'));
    const dates = result.current.dailyAgg.map((d) => d.date);
    expect(dates).toEqual(['2026-06-24', '2026-06-25', '2026-06-26']);
  });

  // ── modelLeaders ──

  it('modelLeaders picks the top model in each dimension', () => {
    const rows: ModelRow[] = [
      model({ model_name: 'gpt-4', request_count: 10, prompt_tokens: 100, completion_tokens: 0, quota: 500 }),
      model({ model_name: 'claude-3', request_count: 5, prompt_tokens: 500, completion_tokens: 500, quota: 1000 }),
      model({ model_name: 'gemini', request_count: 8, prompt_tokens: 50, completion_tokens: 50, quota: 200 }),
    ];
    const { result } = renderHook(() => useDashboardCharts(rows, [], [], 'tokens'));

    expect(result.current.modelLeaders.mostRequested?.model).toBe('gpt-4');
    expect(result.current.modelLeaders.mostTokens?.model).toBe('claude-3');
    expect(result.current.modelLeaders.mostQuota?.model).toBe('claude-3');
  });

  it('modelLeaders returns null for empty data', () => {
    const { result } = renderHook(() => useDashboardCharts([], [], [], 'tokens'));
    expect(result.current.modelLeaders.mostRequested).toBeNull();
    expect(result.current.modelLeaders.mostTokens).toBeNull();
    expect(result.current.modelLeaders.mostQuota).toBeNull();
  });

  // ── rangeInsights ──

  it('rangeInsights finds busiest and token-heavy days', () => {
    const rows: ModelRow[] = [
      model({ day: '2026-06-24', request_count: 10, prompt_tokens: 100, completion_tokens: 100 }),
      model({ day: '2026-06-24', model_name: 'claude-3', request_count: 5, prompt_tokens: 200, completion_tokens: 200 }),
      model({ day: '2026-06-25', request_count: 20, prompt_tokens: 50, completion_tokens: 50 }),
    ];
    const { result } = renderHook(() => useDashboardCharts(rows, [], [], 'tokens'));

    // June 24: 15 requests, 600 tokens
    // June 25: 20 requests, 100 tokens
    expect(result.current.rangeInsights.busiestDay?.date).toBe('2026-06-25');
    expect(result.current.rangeInsights.tokenHeavyDay?.date).toBe('2026-06-24');
  });

  // ── timeSeries ──

  it('timeSeries converts dailyAgg to chart format', () => {
    const rows: ModelRow[] = [
      model({ day: '2026-06-24', request_count: 3, prompt_tokens: 100, completion_tokens: 50, quota: 150 }),
    ];
    const { result } = renderHook(() => useDashboardCharts(rows, [], [], 'tokens'));

    expect(result.current.timeSeries).toHaveLength(1);
    expect(result.current.timeSeries[0]).toEqual({
      date: '2026-06-24',
      requests: 3,
      quota: 150,
      tokens: 150,
    });
  });

  // ── computeStackedSeries / modelStackedData ──

  it('modelStackedData groups by model across days', () => {
    const rows: ModelRow[] = [
      model({ day: '2026-06-24', model_name: 'gpt-4', prompt_tokens: 100, completion_tokens: 50 }),
      model({ day: '2026-06-24', model_name: 'claude-3', prompt_tokens: 200, completion_tokens: 100 }),
      model({ day: '2026-06-25', model_name: 'gpt-4', prompt_tokens: 50, completion_tokens: 25 }),
    ];
    const { result } = renderHook(() => useDashboardCharts(rows, [], [], 'tokens'));

    expect(result.current.modelKeys).toEqual(['gpt-4', 'claude-3']);
    expect(result.current.modelStackedData).toHaveLength(2);
    // June 24: gpt-4 tokens = 150, claude-3 tokens = 300
    const d24 = result.current.modelStackedData.find((d) => d.date === '2026-06-24')!;
    expect(d24['gpt-4']).toBe(150);
    expect(d24['claude-3']).toBe(300);
  });

  it('modelStackedData respects statisticsMetric=requests', () => {
    const rows: ModelRow[] = [
      model({ day: '2026-06-24', model_name: 'gpt-4', request_count: 3 }),
      model({ day: '2026-06-24', model_name: 'claude-3', request_count: 5 }),
    ];
    const hookRequests = renderHook(() => useDashboardCharts(rows, [], [], 'requests'));
    const d24 = hookRequests.result.current.modelStackedData.find((d) => d.date === '2026-06-24')!;
    expect(d24['gpt-4']).toBe(3);
    expect(d24['claude-3']).toBe(5);
  });

  it('modelStackedData respects statisticsMetric=expenses', () => {
    const rows: ModelRow[] = [
      model({ day: '2026-06-24', model_name: 'gpt-4', quota: 150 }),
      model({ day: '2026-06-24', model_name: 'claude-3', quota: 300 }),
    ];
    const hook = renderHook(() => useDashboardCharts(rows, [], [], 'expenses'));
    const d24 = hook.result.current.modelStackedData.find((d) => d.date === '2026-06-24')!;
    expect(d24['gpt-4']).toBe(150);
    expect(d24['claude-3']).toBe(300);
  });

  // ── userRows / tokenRows ──

  it('userStackedData groups by username', () => {
    const userRows: UserRow[] = [
      { day: '2026-06-24', username: 'alice', user_id: 1, request_count: 5, quota: 100, prompt_tokens: 50, completion_tokens: 25 },
      { day: '2026-06-24', username: 'bob', user_id: 2, request_count: 3, quota: 60, prompt_tokens: 30, completion_tokens: 15 },
    ];
    const { result } = renderHook(() => useDashboardCharts([], userRows, [], 'tokens'));
    expect(result.current.userKeys).toEqual(['alice', 'bob']);
    const d24 = result.current.userStackedData.find((d) => d.date === '2026-06-24')!;
    expect(d24['alice']).toBe(75);
    expect(d24['bob']).toBe(45);
  });

  it('tokenStackedData groups by token_name(username)', () => {
    const tokenRows: TokenRow[] = [
      { day: '2026-06-24', username: 'alice', token_name: 'tk-1', user_id: 1, request_count: 2, quota: 40, prompt_tokens: 20, completion_tokens: 10 },
    ];
    const { result } = renderHook(() => useDashboardCharts([], [], tokenRows, 'tokens'));
    expect(result.current.tokenKeys).toEqual(['tk-1(alice)']);
  });
});
