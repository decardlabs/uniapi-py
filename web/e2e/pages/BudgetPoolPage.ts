/**
 * Budget Pool Page Object Model
 *
 * Recharge flow: Budget Pool → Allocate → User Account
 */
import type { Locator, Page } from '@playwright/test';
import { expect } from '../fixtures';

export class BudgetPoolPage {
  readonly page: Page;

  // ── Top-level elements ──────────────────────────────────
  readonly heading: Locator;
  readonly poolTable: Locator;

  // ── Allocate Dialog ─────────────────────────────────────
  readonly allocateDialog: Locator;
  readonly allocateUserDropdown: Locator;
  readonly allocateUserSearchInput: Locator;
  readonly allocateAmountInput: Locator;
  readonly allocateRemarkInput: Locator;
  readonly allocateSubmitBtn: Locator;
  readonly allocateCancelBtn: Locator;

  // ── Recall Dialog ───────────────────────────────────────
  readonly recallDialog: Locator;

  constructor(page: Page) {
    this.page = page;

    this.heading = page.getByRole('heading', { name: /budget pool/i });
    this.poolTable = page.getByRole('table');

    // Allocate dialog selectors
    this.allocateDialog = page.getByRole('dialog');
    this.allocateUserDropdown = this.allocateDialog.locator(
      'button[role="combobox"]'
    );
    this.allocateUserSearchInput = page.getByPlaceholder(/type username/i);
    this.allocateAmountInput = this.allocateDialog.locator(
      'input[type="number"]'
    );
    this.allocateRemarkInput = this.allocateDialog.locator(
      'input[placeholder*="remark"], input[placeholder*="Remark"]'
    );
    this.allocateSubmitBtn = this.allocateDialog.getByRole('button', { name: /submit/i });
    this.allocateCancelBtn = this.allocateDialog.getByRole('button', { name: /cancel/i });

    this.recallDialog = page.locator('[role="dialog"]');
  }

  // ── Navigation ──────────────────────────────────────────

  async goto() {
    await this.page.goto('/pools');
    await expect(this.heading).toBeVisible({ timeout: 10000 });
    await this.page.waitForLoadState('networkidle');
  }

  // ── Helpers ─────────────────────────────────────────────

  /** Parse currency value from a monospace cell ("¥100.50") */
  private parseYuan(text: string | null): number {
    if (!text) return 0;
    return parseFloat(text.replace(/[¥,]/g, '').trim()) || 0;
  }

  /** Read the "Allocated" column value for a given pool row */
  async getPoolAllocated(rowIndex: number = 0): Promise<number> {
    const rows = this.poolTable.locator('tbody tr');
    const count = await rows.count();
    if (rowIndex >= count) return 0;
    // Allocated is typically the 6th column (0-indexed: 5)
    const cells = rows.nth(rowIndex).locator('td');
    const text = await cells.nth(5).textContent();
    return this.parseYuan(text);
  }

  /** Read the "Available" column value for a given pool row */
  async getPoolAvailable(rowIndex: number = 0): Promise<number> {
    const rows = this.poolTable.locator('tbody tr');
    const count = await rows.count();
    if (rowIndex >= count) return 0;
    // Available is typically the 7th column (0-indexed: 6)
    const cells = rows.nth(rowIndex).locator('td');
    const text = await cells.nth(6).textContent();
    return this.parseYuan(text);
  }

  /** Get pool ID from first row */
  async getFirstPoolId(): Promise<number> {
    const firstCell = this.poolTable.locator('tbody tr').first().locator('td').first();
    const text = await firstCell.textContent();
    return parseInt(text || '0', 10);
  }

  // ── Allocate Actions ────────────────────────────────────

  /** Click the Allocate (+) button on the first active pool row */
  async clickAllocateButton(poolRowIndex: number = 0) {
    const rows = this.poolTable.locator('tbody tr');
    const row = rows.nth(poolRowIndex);
    // The allocate button has a Plus icon and title="Allocate"
    await row.getByRole('button', { name: /allocate/i }).first().click();
    await expect(this.allocateDialog).toBeVisible({ timeout: 5000 });
  }

  /** Search for and select a target user in the allocate dialog */
  async searchAndSelectUser(username: string) {
    // Open the combobox dropdown
    await this.allocateUserDropdown.click();
    await this.page.waitForTimeout(300);

    // Type the username to trigger the search
    await this.allocateUserSearchInput.fill(username);
    await this.page.waitForTimeout(800); // Wait for debounced search

    // Click the first result in the dropdown list
    const option = this.page
      .locator('[cmdk-item], [role="option"]')
      .filter({ hasText: username })
      .first();
    await option.click();
    await this.page.waitForTimeout(300);
  }

  /** Fill the allocate amount */
  async fillAllocateAmount(amount: number) {
    await this.allocateAmountInput.fill(String(amount));
  }

  /** Fill allocate remark */
  async fillAllocateRemark(remark: string) {
    if (await this.allocateRemarkInput.isVisible()) {
      await this.allocateRemarkInput.fill(remark);
    }
  }

  /** Submit the allocate dialog */
  async submitAllocate() {
    await this.allocateSubmitBtn.click();
    // Wait for dialog to close (success) or error to appear
    await this.page.waitForTimeout(1500);
  }

  /** Complete full allocate flow */
  async allocateToUser(username: string, amount: number, remark?: string) {
    await this.searchAndSelectUser(username);
    await this.fillAllocateAmount(amount);
    if (remark) await this.fillAllocateRemark(remark);
    await this.submitAllocate();
  }

  // ── Verification Helpers ───────────────────────────────

  /** Check that notification with text appeared */
  async expectSuccessNotification(text: string) {
    const notification = this.page.locator('[role="alert"], .notification, [data-sonner-toaster]').filter({ hasText: text });
    await expect(notification.first()).toBeVisible({ timeout: 5000 });
  }

  /** Check that the allocate dialog is closed (submitted successfully) */
  async expectDialogClosed() {
    await expect(this.allocateDialog).not.toBeVisible({ timeout: 5000 });
  }
}
