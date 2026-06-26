import { act, renderHook } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { STORAGE_KEYS } from '@/lib/storage';
import { usePlaygroundParameters } from '../usePlaygroundParameters';

const _caps = vi.hoisted(() => ({
  supportsTopK: true, supportsFrequencyPenalty: true, supportsPresencePenalty: true,
  supportsMaxCompletionTokens: true, supportsStop: true, supportsReasoningEffort: true, supportsThinking: true,
}));

let _mediumOnly = false;

vi.mock('@/lib/model-capabilities', () => ({
  getModelCapabilities: vi.fn(() => _caps),
  isOpenAIMediumOnlyReasoningModel: vi.fn(() => _mediumOnly),
}));

// Complete mock — avoids loading the real module (axios etc.)
vi.mock('@/lib/utils', () => ({
  loadFromStorage: vi.fn((_k: string, _d: unknown) => {
    try { const v = localStorage.getItem(_k); return v ? JSON.parse(v) : _d; } catch { return _d; }
  }),
  saveToStorage: vi.fn((_k: string, _d: unknown) => {
    try { localStorage.setItem(_k, JSON.stringify(_d)); } catch {}
  }),
}));

describe('usePlaygroundParameters', () => {
  const dsp = 'You are a helpful assistant.';

  beforeEach(() => {
    localStorage.clear();
    _mediumOnly = false;
    Object.assign(_caps, { supportsTopK: true, supportsFrequencyPenalty: true, supportsPresencePenalty: true, supportsMaxCompletionTokens: true, supportsStop: true, supportsReasoningEffort: true, supportsThinking: true });
  });

  it('defaults and restore', () => {
    const { result: r1 } = renderHook(() => usePlaygroundParameters({ defaultSystemPrompt: dsp, selectedModel: '' }));
    expect(r1.current.temperature).toEqual([0.7]);
    expect(r1.current.reasoningEffort).toBe('high');

    act(() => { r1.current.setTemperature([0.3]); });
    act(() => { r1.current.handleReasoningEffortChange('medium'); });

    const { result: r2 } = renderHook(() => usePlaygroundParameters({ defaultSystemPrompt: dsp, selectedModel: '' }));
    expect(r2.current.temperature).toEqual([0.3]);
    expect(r2.current.reasoningEffort).toBe('medium');
  });

  it('capabilities and medium-only', () => {
    _mediumOnly = true;
    const { result } = renderHook(() => usePlaygroundParameters({ defaultSystemPrompt: dsp, selectedModel: 'o3-m' }));
    act(() => { result.current.handleReasoningEffortChange('high'); });
    expect(result.current.reasoningEffort).toBe('medium');

    act(() => { result.current.handleReasoningEffortChange('none'); });
    expect(result.current.reasoningEffort).toBe('none');

    _caps.supportsTopK = false;
    const { result: r2 } = renderHook(() => usePlaygroundParameters({ defaultSystemPrompt: dsp, selectedModel: 'x' }));
    expect(r2.current.topK).toEqual([40]);
  });
});
