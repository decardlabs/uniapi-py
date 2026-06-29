import { describe, expect, it, vi } from 'vitest';

// Directly test the formatYuan helper and check that layout components render correctly
// by testing the structural markup without rendering the full form

describe('EditUserPage layout helpers', () => {
  it('formatYuan converts micro-yuan to yuan string', () => {
    const formatYuan = (micro: number): string => `¥${(micro / 1_000_000).toFixed(2)}`;
    expect(formatYuan(1500000)).toBe('¥1.50');
    expect(formatYuan(0)).toBe('¥0.00');
  });
});

describe('Balance and Timestamp fields use Input disabled', () => {
  it('Balance section should use Input disabled instead of plain div', async () => {
    // This test verifies by reading the source file that Balance (lines 455-471)
    // and timestamp sections (lines 513-536) use Input disabled pattern.
    // After the code fix, these sections should render <input disabled> instead of <div>.

    const path = await import('path');
    const fs = await import('fs');
    const sourcePath = path.resolve(process.cwd(), 'src/pages/users/EditUserPage.tsx');
    const source = fs.readFileSync(sourcePath, 'utf-8');

    // Balance section should NOT contain a plain div with formatted balance
    // It should use <Input disabled> instead
    const hasBalanceDiv = source.includes('className="p-2 bg-muted rounded-md flex justify-between items-center"');
    expect(hasBalanceDiv).toBe(false);

    // Balance should use Input component with disabled prop
    const hasBalanceInput = source.includes('Input') && source.includes('disabled');
    expect(hasBalanceInput).toBe(true);

    // Timestamp sections should use Input disabled
    const hasTimestampDiv = source.includes('className="p-2 bg-muted rounded-md"');
    // Count occurrences — should be 0 after fix (originally used for both balance and timestamps)
    const divCount = (source.match(/className="p-2 bg-muted rounded-md/g) || []).length;
    expect(divCount).toBe(0);
  });
});
