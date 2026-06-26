import { act, renderHook } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { STORAGE_KEYS } from '@/lib/storage';
import { useConversationPersistence } from '../useConversationPersistence';

// Mock generateUUIDv4 to return deterministic IDs
vi.mock('@/lib/utils', async () => {
  const actual = await vi.importActual('@/lib/utils');
  let counter = 0;
  return {
    ...actual,
    generateUUIDv4: vi.fn(() => {
      counter += 1;
      return `mock-uuid-${counter}`;
    }),
  };
});

describe('useConversationPersistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('starts with a fresh conversation when storage is empty', () => {
    const { result } = renderHook(() => useConversationPersistence({}));
    expect(result.current.messages).toEqual([]);
    expect(result.current.conversationId).toBeTruthy();
    expect(result.current.conversationCreated).toBeGreaterThan(0);
    expect(result.current.conversationCreatedBy).toBe('unknown');
  });

  it('restores a saved conversation from localStorage', () => {
    const saved = {
      id: 'saved-id-1',
      timestamp: 1000,
      createdBy: 'test-user',
      messages: [{ role: 'user', content: 'hi', timestamp: 500 }],
    };
    localStorage.setItem(STORAGE_KEYS.CONVERSATION, JSON.stringify(saved));

    const { result } = renderHook(() => useConversationPersistence({ username: 'test-user' }));
    expect(result.current.messages).toEqual(saved.messages);
    expect(result.current.conversationId).toBe('saved-id-1');
    expect(result.current.conversationCreated).toBe(1000);
    expect(result.current.conversationCreatedBy).toBe('test-user');
  });

  it('falls back to username from options when saved conversation has no createdBy', () => {
    const saved = {
      id: 'saved-id-2',
      timestamp: 2000,
      messages: [],
    };
    localStorage.setItem(STORAGE_KEYS.CONVERSATION, JSON.stringify(saved));

    const { result } = renderHook(() => useConversationPersistence({ username: 'alice' }));
    expect(result.current.conversationCreatedBy).toBe('alice');
  });

  it('persists messages to localStorage when they change', () => {
    const { result } = renderHook(() => useConversationPersistence({}));

    act(() => {
      result.current.setMessages([{ role: 'user', content: 'hello', timestamp: 3000 }]);
    });

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.CONVERSATION)!);
    expect(stored.messages).toEqual([{ role: 'user', content: 'hello', timestamp: 3000 }]);
  });

  it('clearConversation resets state and removes from localStorage', () => {
    const saved = {
      id: 'to-clear',
      timestamp: 5000,
      createdBy: 'bob',
      messages: [{ role: 'user', content: 'test', timestamp: 4000 }],
    };
    localStorage.setItem(STORAGE_KEYS.CONVERSATION, JSON.stringify(saved));

    const { result } = renderHook(() => useConversationPersistence({ username: 'bob' }));
    expect(result.current.conversationId).toBe('to-clear');

    act(() => {
      result.current.clearConversation();
    });

    expect(result.current.messages).toEqual([]);
    expect(result.current.conversationId).toMatch(/^mock-uuid-/);
    // A fresh empty conversation is saved back by the persist effect
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.CONVERSATION)!);
    expect(stored.messages).toEqual([]);
  });

  it('handles invalid saved data gracefully', () => {
    localStorage.setItem(STORAGE_KEYS.CONVERSATION, 'invalid-json');
    const { result } = renderHook(() => useConversationPersistence({}));
    // Falls back to a fresh conversation
    expect(result.current.messages).toEqual([]);
    expect(result.current.conversationId).toBeTruthy();
  });
});
