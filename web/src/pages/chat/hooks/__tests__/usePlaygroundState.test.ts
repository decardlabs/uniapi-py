import { act, renderHook } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { STORAGE_KEYS } from '@/lib/storage';
import { usePlaygroundState } from '../usePlaygroundState';

// Mock auth store
vi.mock('@/lib/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    user: { username: 'testuser' },
  })),
}));

// Mock model capabilities
const mockCapabilities = vi.hoisted(() => ({
  supportsTopK: true,
  supportsFrequencyPenalty: true,
  supportsPresencePenalty: true,
  supportsMaxCompletionTokens: true,
  supportsStop: true,
  supportsReasoningEffort: true,
  supportsThinking: true,
}));

vi.mock('@/lib/model-capabilities', () => ({
  getModelCapabilities: vi.fn(() => mockCapabilities),
  isOpenAIMediumOnlyReasoningModel: vi.fn(() => false),
}));

// Mock storage + uuid utils
let uuidCounter = 0;
vi.mock('@/lib/utils', () => ({
  loadFromStorage: vi.fn((key: string, defaultValue: unknown) => {
    try {
      const item = localStorage.getItem(key);
      return item ? JSON.parse(item) : defaultValue;
    } catch {
      return defaultValue;
    }
  }),
  saveToStorage: vi.fn((key: string, data: unknown) => {
    try {
      localStorage.setItem(key, JSON.stringify(data));
    } catch (e) {
      console.warn('Failed to save to localStorage:', e);
    }
  }),
  clearStorage: vi.fn((key: string) => {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.warn('Failed to clear localStorage:', e);
    }
  }),
  generateUUIDv4: vi.fn(() => {
    uuidCounter += 1;
    return `mock-uuid-${uuidCounter}`;
  }),
  Message: {},
}));

describe('usePlaygroundState', () => {
  beforeEach(() => {
    localStorage.clear();
    mockCapabilities.supportsTopK = true;
    mockCapabilities.supportsFrequencyPenalty = true;
    mockCapabilities.supportsPresencePenalty = true;
    mockCapabilities.supportsMaxCompletionTokens = true;
    mockCapabilities.supportsStop = true;
    mockCapabilities.supportsReasoningEffort = true;
    mockCapabilities.supportsThinking = true;
  });

  it('initializes with default values when storage is empty', () => {
    const { result } = renderHook(() => usePlaygroundState());

    // Conversation
    expect(result.current.messages).toEqual([]);
    expect(result.current.conversationId).toBeTruthy();
    expect(result.current.conversationCreatedBy).toBe('testuser');

    // Parameters — defaults
    expect(result.current.temperature).toEqual([0.7]);
    expect(result.current.maxTokens).toEqual([4096]);
    expect(result.current.reasoningEffort).toBe('high');
    expect(result.current.thinkingEnabled).toBe(false);

    // UI state
    expect(result.current.isMobileSidebarOpen).toBe(false);
    expect(result.current.showPreview).toBe(false);
    expect(result.current.exportDialogOpen).toBe(false);
    expect(result.current.attachedImages).toEqual([]);
  });

  it('restores saved conversation from localStorage', () => {
    const savedConversation = {
      id: 'restored-conv-1',
      timestamp: 1000,
      createdBy: 'testuser',
      messages: [{ role: 'user', content: 'hi', timestamp: 500 }],
    };
    localStorage.setItem(STORAGE_KEYS.CONVERSATION, JSON.stringify(savedConversation));

    const { result } = renderHook(() => usePlaygroundState());

    expect(result.current.messages).toEqual(savedConversation.messages);
    expect(result.current.conversationId).toBe('restored-conv-1');
    expect(result.current.conversationCreated).toBe(1000);
  });

  it('restores saved parameters from localStorage', () => {
    const savedParams = {
      temperature: [0.1],
      maxTokens: [512],
      topP: [0.9],
      topK: [40],
      frequencyPenalty: [0.0],
      presencePenalty: [0.0],
      maxCompletionTokens: [4096],
      stopSequences: '',
      reasoningEffort: 'low',
      thinkingEnabled: true,
      thinkingBudgetTokens: [5000],
      systemMessage: 'Custom prompt',
      showReasoningContent: false,
      focusModeEnabled: false,
    };
    localStorage.setItem(STORAGE_KEYS.PARAMETERS, JSON.stringify(savedParams));

    const { result } = renderHook(() => usePlaygroundState());

    expect(result.current.temperature).toEqual([0.1]);
    expect(result.current.maxTokens).toEqual([512]);
    expect(result.current.reasoningEffort).toBe('low');
    expect(result.current.thinkingEnabled).toBe(true);
  });

  it('persists conversation to localStorage when messages change', () => {
    const { result } = renderHook(() => usePlaygroundState());

    act(() => {
      result.current.setMessages([{ role: 'user', content: 'persist this', timestamp: 500 }]);
    });

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.CONVERSATION)!);
    expect(stored.messages).toEqual([{ role: 'user', content: 'persist this', timestamp: 500 }]);
  });

  it('persists parameters to localStorage when they change', () => {
    const { result } = renderHook(() => usePlaygroundState());

    act(() => {
      result.current.setTemperature([0.5]);
    });

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.PARAMETERS)!);
    expect(stored.temperature).toEqual([0.5]);
  });

  it('clearConversation resets state and clears storage', () => {
    const savedConversation = {
      id: 'to-clear',
      timestamp: 5000,
      createdBy: 'testuser',
      messages: [{ role: 'user', content: 'old', timestamp: 4000 }],
    };
    localStorage.setItem(STORAGE_KEYS.CONVERSATION, JSON.stringify(savedConversation));

    const { result } = renderHook(() => usePlaygroundState());

    act(() => {
      result.current.clearConversation();
    });

    expect(result.current.messages).toEqual([]);
    expect(localStorage.getItem(STORAGE_KEYS.CONVERSATION)).toBeNull();
  });

  it('validates parameters against model capabilities when model is saved', () => {
    const savedParams = {
      temperature: [0.7],
      maxTokens: [4096],
      topP: [1.0],
      topK: [20],
      frequencyPenalty: [0.5],
      presencePenalty: [0.3],
      maxCompletionTokens: [2048],
      stopSequences: '\n',
      reasoningEffort: 'high',
      thinkingEnabled: true,
      thinkingBudgetTokens: [8000],
      systemMessage: 'Test',
      showReasoningContent: true,
      focusModeEnabled: true,
    };
    localStorage.setItem(STORAGE_KEYS.PARAMETERS, JSON.stringify(savedParams));
    localStorage.setItem(STORAGE_KEYS.MODEL, JSON.stringify('saved-model'));

    // Disable these capabilities for the saved model
    mockCapabilities.supportsTopK = false;
    mockCapabilities.supportsStop = false;
    mockCapabilities.supportsThinking = false;

    const { result } = renderHook(() => usePlaygroundState());

    // Unsupported params should be reset to defaults
    expect(result.current.topK).toEqual([40]); // default
    expect(result.current.stopSequences).toBe(''); // default
    expect(result.current.thinkingEnabled).toBe(false); // default
    expect(result.current.thinkingBudgetTokens).toEqual([10000]); // default

    // Supported params should keep their saved values
    expect(result.current.temperature).toEqual([0.7]);
  });
});
