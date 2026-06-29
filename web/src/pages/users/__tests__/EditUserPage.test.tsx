import { describe, expect, it } from 'vitest';

describe('EditUserPage layout', () => {
  const getSource = (): string => {
    const path = require('path');
    const fs = require('fs');
    return fs.readFileSync(path.resolve(process.cwd(), 'src/pages/users/EditUserPage.tsx'), 'utf-8');
  };

  it('Group should be in its own full-width row, not paired with Balance', () => {
    const source = getSource();
    // Balance and Group should NOT be inside the same grid row
    const balanceGridRow = source.match(/grid-cols-1 md:grid-cols-2[\s\S]*?Balance[\s\S]*?Group/);
    expect(balanceGridRow).toBeNull();
  });

  it('Balance should be a standalone full-width row with Input disabled', () => {
    const source = getSource();
    // Balance should be wrapped in its own FormItem outside any grid
    const balanceSection = source.match(/fields\.balance\.label[\s\S]{0,200}Input disabled value=\{formatYuan/);
    expect(balanceSection).not.toBeNull();
    // Should NOT be in a grid-cols-2 layout
    const balanceInGrid = source.match(/grid-cols-1 md:grid-cols-2[\s\S]{0,50}Balance/);
    expect(balanceInGrid).toBeNull();
  });

  it('Register Time should be a standalone full-width row with Input disabled', () => {
    const source = getSource();
    const hasDisabledInput = source.includes("Input disabled value={formatTimestamp(createdAt)}");
    expect(hasDisabledInput).toBe(true);
  });

  it('Last Modified should be a standalone full-width row with Input disabled', () => {
    const source = getSource();
    const hasDisabledInput = source.includes("Input disabled value={formatTimestamp(updatedAt)}");
    expect(hasDisabledInput).toBe(true);
  });

  it('No plain divs remain for Balance or timestamp display', () => {
    const source = getSource();
    const divCount = (source.match(/className="p-2 bg-muted rounded-md/g) || []).length;
    expect(divCount).toBe(0);
  });
});
