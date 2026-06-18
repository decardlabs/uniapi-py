import * as React from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';

import { NotificationsProvider } from '@/components/ui/notifications';
import { normalizeChannelType } from './helpers';
import { EditChannelPage } from './EditChannelPage';

// Remove jest.mock for vitest compatibility
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k: string, optionsOrDefault?: string | Record<string, unknown>) => {
      if (typeof optionsOrDefault === 'string') return optionsOrDefault;
      if (typeof optionsOrDefault === 'object' && optionsOrDefault !== null) {
        const dv = optionsOrDefault['defaultValue'];
        return typeof dv === 'string' ? dv : k;
      }
      return k;
    },
    i18n: { language: 'en' },
  }),
}));

describe('normalizeChannelType', () => {
  it('returns numbers as-is when finite', () => {
    expect(normalizeChannelType(14)).toBe(14);
    expect(normalizeChannelType(0)).toBe(0);
  });

  it('parses numeric strings', () => {
    expect(normalizeChannelType('33')).toBe(33);
    expect(normalizeChannelType(' 51 ')).toBe(51);
  });

  it('treats blank values as null', () => {
    expect(normalizeChannelType('')).toBeNull();
    expect(normalizeChannelType('   ')).toBeNull();
    expect(normalizeChannelType(null)).toBeNull();
    expect(normalizeChannelType(undefined)).toBeNull();
  });

  it('filters out non-finite values', () => {
    expect(normalizeChannelType(Number.NaN)).toBeNull();
    expect(normalizeChannelType('NaN')).toBeNull();
    expect(normalizeChannelType(Infinity)).toBeNull();
  });
});

describe('EditChannelPage', () => {
  it('renders dynamic parameter fields from template', () => {
    // Render the page (would require more setup for full integration)
    // Workaround: use React.createElement to avoid JSX parse issues
    const result = render(
      React.createElement(
        MemoryRouter,
        null,
        React.createElement(NotificationsProvider, null, React.createElement(EditChannelPage))
      )
    );
    // Check for a known template field label (from i18n)
    expect(result.container.innerHTML).toMatch(/API Key|Region|Custom Field/);
  });
});
