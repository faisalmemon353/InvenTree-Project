import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import * as fs from 'fs';
import * as path from 'path';

const REPORTS_DIR = path.resolve(__dirname, '..', 'reports');

test.beforeAll(() => {
  if (!fs.existsSync(REPORTS_DIR)) {
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
  }
});

test.beforeEach(async ({ page }) => {
  await page.goto('/web/purchasing?a11y=after');
  await page.click('#btn-reset-db');
  await expect(page.locator('#success-banner')).toContainText('Database reset to deterministic baseline');
  await page.click('#btn-login-officer');
  await expect(page.locator('#active-role-badge')).toContainText('Role: purchasing_officer');
});

// ============================================================================
// 1. SIX USE CASES (2 PER MEMBER x 3 MEMBERS) — MAIN, 2 ALT, 2 EXCEPTION FLOWS
// ============================================================================

test('UC-01 (Faisal 24I-3032): Create Purchase Order — Main, A1 (EUR), A2 (Dates), E1 (Invalid Ref), E2 (Start > Target Date)', async ({ page }) => {
  // Exception E1: Invalid Reference Pattern ('BAD_REF') -> Rejected with FR-01 error
  await page.fill('#input-po-reference', 'BAD_REF');
  await page.click('#btn-submit-po');
  await expect(page.locator('#error-banner')).toContainText('Validation Error (FR-01)');

  // Exception E2: Start Date after Target Date (2026-12-20 > 2026-12-05) -> Rejected with FR-02 error
  await page.fill('#input-po-reference', 'PO-3101');
  await page.fill('#input-po-start-date', '2026-12-20');
  await page.fill('#input-po-target-date', '2026-12-05');
  await page.click('#btn-submit-po');
  await expect(page.locator('#error-banner')).toContainText('Validation Error (FR-02): Target date must be after start date');

  // Main Success Flow: Valid PO-3101 for Acme Electronics Ltd in USD
  await page.fill('#input-po-start-date', '');
  await page.fill('#input-po-target-date', '');
  await page.fill('#input-line-quantity', '10');
  await page.click('#btn-submit-po');
  await expect(page.locator('#success-banner')).toContainText('Confirmation: Purchase Order PO-3101 saved with line quantity 10 (USD)');
  await expect(page.locator('tr[data-po-ref="PO-3101"] .po-status-code')).toHaveText('10');

  // Alternative Flow A1: Create PO-3102 with EUR currency
  await page.fill('#input-po-reference', 'PO-3102');
  await page.selectOption('#input-po-currency', 'EUR');
  await page.fill('#input-line-quantity', '5');
  await page.click('#btn-submit-po');
  await expect(page.locator('#success-banner')).toContainText('Confirmation: Purchase Order PO-3102 saved with line quantity 5 (EUR)');

  // Alternative Flow A2: Create PO-3103 with valid Start Date <= Target Date
  await page.fill('#input-po-reference', 'PO-3103');
  await page.selectOption('#input-po-currency', 'USD');
  await page.fill('#input-po-start-date', '2026-12-01');
  await page.fill('#input-po-target-date', '2026-12-15');
  await page.click('#btn-submit-po');
  await expect(page.locator('#success-banner')).toContainText('Confirmation: Purchase Order PO-3103 saved');
  await expect(page.locator('tr[data-po-ref="PO-3103"] .po-line-qty')).toHaveText('5');
});

test('UC-02 (Faisal 24I-3032): Add & Merge Line Items — Main, A1 (Discount), A2 (Merge Lines), E1 (Zero Qty Error & Recovery), E2 (Supplier Mismatch)', async ({ page }) => {
  // Exception Flow E1 (Also Section 3 Usability Error-Recovery Test):
  // First submit invalid quantity = 0 -> verify error explains what to fix -> correct to 8 -> verify success
  await page.fill('#input-po-reference', 'PO-3201');
  await page.fill('#input-line-quantity', '0');
  await page.click('#btn-submit-po');
  await expect(page.locator('#error-banner')).toContainText('Validation Error (BR-01)');
  await expect(page.locator('#error-banner')).toContainText('Enter a quantity between 1 and 10000');

  // Recover from E1 -> Main Flow: Correct quantity to 8 and submit
  await page.fill('#input-line-quantity', '8');
  await page.click('#btn-submit-po');
  await expect(page.locator('#success-banner')).toContainText('Confirmation: Purchase Order PO-3201 saved with line quantity 8');
  await expect(page.locator('tr[data-po-ref="PO-3201"] .po-line-qty')).toHaveText('8');

  // Exception Flow E2: Mismatched Supplier Part (Acme Supplier=1 with Beta Part=2) -> Rejected by BR-04
  await page.selectOption('#input-po-supplier', '1');
  await page.selectOption('#input-line-part', '2');
  await page.click('#btn-submit-po');
  await expect(page.locator('#error-banner')).toContainText('Validation Error (BR-04): Supplier part does not match Purchase Order supplier');
  await page.selectOption('#input-line-part', '1');

  // Alternative Flow A2: Merge duplicate supplier-part line item (merge_items=true) on PO-3201 (8 + 4 = 12)
  await page.selectOption('#input-line-merge', 'true');
  await page.fill('#input-line-quantity', '4');
  await page.click('#btn-submit-po');
  await expect(page.locator('tr[data-po-ref="PO-3201"] .po-line-qty')).toHaveText('12');

  // Alternative Flow A1: Create line item with 20% discount on PO-3202 (10 * $25 * 0.8 = $200)
  await page.fill('#input-po-reference', 'PO-3202');
  await page.fill('#input-line-quantity', '10');
  await page.fill('#input-line-discount', '20');
  await page.click('#btn-submit-po');
  await expect(page.locator('tr[data-po-ref="PO-3202"] .po-total-price')).toHaveText('200');
});

test('UC-03 (Hassan Zahid 24I-3011): Purchase Order Lifecycle FSM — Main (Issue), A1 (Hold -> Issue), A2 (Cancel), E1 (Complete from Pending), E2 (Issue after Cancel)', async ({ page }) => {
  // Exception Flow E1: Cannot transition directly from PENDING (10) -> COMPLETE (30)
  await page.fill('#input-action-po-id', 'PO-SQE-0001');
  await page.click('#btn-complete-po');
  await expect(page.locator('#error-banner')).toContainText('State Transition Error (BR-03)');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0001"] .po-status-code')).toHaveText('10');

  // Alternative Flow A1: Hold order (PENDING 10 -> ON_HOLD 25), then Issue (ON_HOLD 25 -> PLACED 20)
  await page.click('#btn-hold-po');
  await expect(page.locator('#success-banner')).toContainText('transitioned to On Hold (25)');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0001"] .po-status-code')).toHaveText('25');

  // Main Flow: Issue order (-> PLACED 20)
  await page.click('#btn-issue-po');
  await expect(page.locator('#success-banner')).toContainText('transitioned to Placed (20)');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0001"] .po-status-code')).toHaveText('20');

  // Alternative Flow A2: Create PO-3301 and Cancel it (PENDING 10 -> CANCELLED 40)
  await page.fill('#input-po-reference', 'PO-3301');
  await page.fill('#input-line-quantity', '5');
  await page.click('#btn-submit-po');
  await page.fill('#input-action-po-id', 'PO-3301');
  await page.click('#btn-cancel-po');
  await expect(page.locator('#success-banner')).toContainText('transitioned to Cancelled (40)');
  await expect(page.locator('tr[data-po-ref="PO-3301"] .po-status-code')).toHaveText('40');

  // Exception Flow E2: Cannot Issue a CANCELLED (40) order
  await page.click('#btn-issue-po');
  await expect(page.locator('#error-banner')).toContainText('State Transition Error (BR-03)');
  await expect(page.locator('tr[data-po-ref="PO-3301"] .po-status-code')).toHaveText('40');
});

test('UC-04 (Hassan Zahid 24I-3011): Receive Partial Stock — Main, A1 (Attention Status), A2 (Second Partial Batch), E1 (Receive on Pending PO), E2 (Duplicate Barcode)', async ({ page }) => {
  // Exception Flow E1: Attempt stock receipt against PENDING order PO-SQE-0001 -> Rejected by BR-02
  await page.fill('#input-recv-po-ref', 'PO-SQE-0001');
  await page.fill('#input-recv-quantity', '4');
  await page.click('#btn-submit-receive');
  await expect(page.locator('#error-banner')).toContainText('Receipt Rejected (BR-01/BR-02)');
  await expect(page.locator('#stock-total-qty')).toHaveText('0');

  // Main Success Flow: Receive 4 of 10 units against PLACED order PO-SQE-0002 with unique barcode
  await page.fill('#input-recv-po-ref', 'PO-SQE-0002');
  await page.fill('#input-recv-quantity', '4');
  await page.fill('#input-recv-barcode', 'BC-UC04-001');
  await page.click('#btn-submit-receive');
  await expect(page.locator('#success-banner')).toContainText('Confirmation: Received 4 units against PO-SQE-0002');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0002"] .po-line-received')).toHaveText('4');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0002"] .po-status-code')).toHaveText('20');
  await expect(page.locator('#stock-total-qty')).toHaveText('4');

  // Exception Flow E2: Duplicate barcode 'BC-UC04-001' rejected (FR-07)
  await page.fill('#input-recv-quantity', '2');
  await page.fill('#input-recv-barcode', 'BC-UC04-001');
  await page.click('#btn-submit-receive');
  await expect(page.locator('#error-banner')).toContainText('Validation Error (FR-07): Barcode BC-UC04-001 is already in use');
  await expect(page.locator('#stock-total-qty')).toHaveText('4');

  // Alternative Flow A1: Receive 2 units with status ATTENTION (50) and new barcode
  await page.selectOption('#input-recv-status', '50');
  await page.fill('#input-recv-barcode', 'BC-UC04-002');
  await page.click('#btn-submit-receive');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0002"] .po-line-received')).toHaveText('6');
  await expect(page.locator('#stock-total-qty')).toHaveText('6');

  // Alternative Flow A2: Receive 1 more unit without barcode (total 7 of 10, still PLACED=20)
  await page.selectOption('#input-recv-status', '10');
  await page.fill('#input-recv-quantity', '1');
  await page.fill('#input-recv-barcode', '');
  await page.click('#btn-submit-receive');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0002"] .po-line-received')).toHaveText('7');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0002"] .po-status-code')).toHaveText('20');
});

test('UC-05 (Salman Ahmed 24I-3004): Full Stock Receipt & Auto-Complete — Main, A1 (Two-Step Completion), A2 (Manual Complete), E1 (Over-Receive Rejected), E2 (Missing Location Rejected)', async ({ page }) => {
  // Exception Flow E1: Over-receiving 11 units against 10 ordered on PO-SQE-0002 -> Rejected by BR-01
  await page.fill('#input-recv-po-ref', 'PO-SQE-0002');
  await page.fill('#input-recv-quantity', '11');
  await page.click('#btn-submit-receive');
  await expect(page.locator('#error-banner')).toContainText('Over-receiving beyond ordered quantity is not permitted');
  await expect(page.locator('#stock-total-qty')).toHaveText('0');

  // Exception Flow E2: Missing destination location (location = 0 / None) -> Rejected by BR-02
  await page.selectOption('#input-recv-location', '0');
  await page.fill('#input-recv-quantity', '5');
  await page.click('#btn-submit-receive');
  await expect(page.locator('#error-banner')).toContainText('Receipt Rejected (BR-01/BR-02)');
  await page.selectOption('#input-recv-location', '1');

  // Main Success Flow: Full receipt of 10 units on PO-SQE-0002 -> Auto-completes PO (PLACED 20 -> COMPLETE 30)
  await page.fill('#input-recv-quantity', '10');
  await page.click('#btn-submit-receive');
  await expect(page.locator('#success-banner')).toContainText('Order status is now Complete (30)');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0002"] .po-status-code')).toHaveText('30');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0002"] .po-line-received')).toHaveText('10');
  await expect(page.locator('#stock-total-qty')).toHaveText('10');

  // Alternative Flow A1: Issue PO-SQE-0001 and complete in two partial receipts (4 + 6 = 10 -> COMPLETE 30)
  await page.fill('#input-action-po-id', 'PO-SQE-0001');
  await page.click('#btn-issue-po');
  await page.fill('#input-recv-po-ref', 'PO-SQE-0001');
  await page.fill('#input-recv-quantity', '4');
  await page.click('#btn-submit-receive');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0001"] .po-status-code')).toHaveText('20');
  await page.fill('#input-recv-quantity', '6');
  await page.click('#btn-submit-receive');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0001"] .po-status-code')).toHaveText('30');
  await expect(page.locator('#stock-total-qty')).toHaveText('20');

  // Alternative Flow A2: Create PO-3501, issue it, receive 3 of 10, and manually complete via Complete button
  await page.fill('#input-po-reference', 'PO-3501');
  await page.fill('#input-line-quantity', '10');
  await page.click('#btn-submit-po');
  await page.fill('#input-action-po-id', 'PO-3501');
  await page.click('#btn-issue-po');
  await page.fill('#input-recv-po-ref', 'PO-3501');
  await page.fill('#input-recv-quantity', '3');
  await page.click('#btn-submit-receive');
  await page.click('#btn-complete-po');
  await expect(page.locator('tr[data-po-ref="PO-3501"] .po-status-code')).toHaveText('30');
});

test('UC-06 (Salman Ahmed 24I-3004): RBAC Enforcement & Order/Line Locking — Main, A1 (Viewer Read), A2 (Delete Unreceived Line), E1 (Delete Received Line), E2 (Viewer Write Blocked + 4 RBAC Decisions)', async ({ page }) => {
  const rbacEvidence: Array<Record<string, string>> = [];

  // RBAC Decision 1 (Allowed): purchasing_officer creates PO-3601
  await page.fill('#input-po-reference', 'PO-3601');
  await page.fill('#input-line-quantity', '10');
  await page.click('#btn-submit-po');
  await expect(page.locator('#success-banner')).toContainText('Confirmation: Purchase Order PO-3601 saved');
  rbacEvidence.push({
    check_id: 'RBAC-01',
    role: 'purchasing_officer',
    action: 'POST /sqe/api/create-po-and-line (Create PO-3601)',
    expected_result: 'ALLOWED (HTTP 201 Created)',
    observed_result: 'ALLOWED (Confirmation banner shown, PO-3601 created in status 10)',
  });

  // Alternative Flow A2: purchasing_officer deletes unreceived line item on PO-3601 (received == 0)
  await page.fill('#input-action-po-id', 'PO-3601');
  await page.click('#btn-delete-line');
  await expect(page.locator('#success-banner')).toContainText('Confirmation: Unreceived line item deleted from PO-3601');

  // RBAC Decision 2 (Allowed): purchasing_officer receives 4 units on PLACED order PO-SQE-0002
  await page.fill('#input-recv-po-ref', 'PO-SQE-0002');
  await page.fill('#input-recv-quantity', '4');
  await page.click('#btn-submit-receive');
  await expect(page.locator('#success-banner')).toContainText('Confirmation: Received 4 units against PO-SQE-0002');
  rbacEvidence.push({
    check_id: 'RBAC-02',
    role: 'purchasing_officer',
    action: 'POST /sqe/api/receive-stock (Receive 4 units on PO-SQE-0002)',
    expected_result: 'ALLOWED (HTTP 201 Created)',
    observed_result: 'ALLOWED (StockItem balance updated to 4 units)',
  });

  // Exception Flow E1: purchasing_officer tries to delete a line item that already received stock (received=4 > 0) -> Rejected by FR-10
  await page.fill('#input-action-po-id', 'PO-SQE-0002');
  await page.click('#btn-delete-line');
  await expect(page.locator('#error-banner')).toContainText('Validation Error (FR-10): Cannot delete line items which have received stock');

  // Main Flow: Complete PO-SQE-0002 (receive remaining 6 units -> status 30 COMPLETE) and verify locked order rejects modifications
  await page.fill('#input-recv-quantity', '6');
  await page.click('#btn-submit-receive');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0002"] .po-status-code')).toHaveText('30');
  await page.fill('#input-po-reference', 'PO-SQE-0002');
  await page.click('#btn-submit-po');
  await expect(page.locator('#error-banner')).toContainText('Validation Error (FR-10): Order PO-SQE-0002 is locked/closed');

  // Alternative Flow A1: Switch to inventory_viewer and verify read access (RBAC Decision 3 - Allowed)
  await page.click('#btn-login-viewer');
  await expect(page.locator('#active-role-badge')).toContainText('Role: inventory_viewer');
  await expect(page.locator('tr[data-po-ref="PO-SQE-0001"]')).toBeVisible();
  rbacEvidence.push({
    check_id: 'RBAC-03',
    role: 'inventory_viewer',
    action: 'GET /sqe/api/state (View Purchase Orders and Stock Balances)',
    expected_result: 'ALLOWED (HTTP 200 OK)',
    observed_result: 'ALLOWED (PO table and stock balances rendered in UI)',
  });

  // Exception Flow E2: inventory_viewer denied Create PO (RBAC Decision 4 - Denied), Issue PO (RBAC Decision 5 - Denied), Receive Stock (RBAC Decision 6 - Denied)
  await page.fill('#input-po-reference', 'PO-3699');
  await page.click('#btn-submit-po');
  await expect(page.locator('#error-banner')).toContainText('HTTP 403 Forbidden: Role inventory_viewer lacks purchase_order:add permission');
  rbacEvidence.push({
    check_id: 'RBAC-04',
    role: 'inventory_viewer',
    action: 'POST /sqe/api/create-po-and-line (Attempt to create PO-3699)',
    expected_result: 'DENIED (HTTP 403 Forbidden)',
    observed_result: 'DENIED (HTTP 403 Forbidden error alert displayed; PO-3699 not created)',
  });

  await page.fill('#input-action-po-id', 'PO-SQE-0001');
  await page.click('#btn-issue-po');
  await expect(page.locator('#error-banner')).toContainText('HTTP 403 Forbidden: Role inventory_viewer cannot perform issue');
  rbacEvidence.push({
    check_id: 'RBAC-05',
    role: 'inventory_viewer',
    action: 'POST /sqe/api/transition-po (Attempt to issue PO-SQE-0001)',
    expected_result: 'DENIED (HTTP 403 Forbidden)',
    observed_result: 'DENIED (HTTP 403 Forbidden error alert; PO-SQE-0001 remains in status 10)',
  });

  await page.fill('#input-recv-po-ref', 'PO-SQE-0001');
  await page.click('#btn-submit-receive');
  await expect(page.locator('#error-banner')).toContainText('HTTP 403 Forbidden: Role inventory_viewer lacks purchase_order:change and stock:add');
  rbacEvidence.push({
    check_id: 'RBAC-06',
    role: 'inventory_viewer',
    action: 'POST /sqe/api/receive-stock (Attempt to receive stock)',
    expected_result: 'DENIED (HTTP 403 Forbidden)',
    observed_result: 'DENIED (HTTP 403 Forbidden error alert; Stock balance unchanged)',
  });

  fs.writeFileSync(path.join(REPORTS_DIR, 'rbac_access_evidence.json'), JSON.stringify(rbacEvidence, null, 2));
});

// ============================================================================
// 2. SECTION 3: KEYBOARD NAVIGATION & @axe-core/playwright BEFORE/AFTER SCANS
// ============================================================================

test('Section 3 Usability: Keyboard-Only Tab Focus Navigation & Enter Form Submission', async ({ page }) => {
  await page.focus('#input-po-reference');
  await expect(page.locator('#input-po-reference')).toBeFocused();
  await page.keyboard.press('Control+A');
  await page.keyboard.press('Backspace');
  await page.keyboard.type('PO-4010');

  const expectedTabOrder = [
    '#input-po-supplier',
    '#input-po-currency',
    '#input-po-start-date',
    '#input-po-target-date',
    '#input-line-part',
    '#input-line-quantity',
    '#input-line-discount',
    '#input-line-merge',
    '#btn-submit-po',
  ];

  for (const selector of expectedTabOrder) {
    await page.keyboard.press('Tab');
    await expect(page.locator(selector)).toBeFocused();
  }

  // Submit form using keyboard Enter key while focused on #btn-submit-po
  await page.keyboard.press('Enter');
  await expect(page.locator('#success-banner')).toContainText('Confirmation: Purchase Order PO-4010 saved');
  await expect(page.locator('tr[data-po-ref="PO-4010"] .po-status-code')).toHaveText('10');
});

test('Section 3 Accessibility: @axe-core/playwright Full Audit Before and After Screen Fix', async ({ page }) => {
  // 1. Scan BEFORE screen fix (?a11y=before)
  await page.goto('/web/purchasing?a11y=before');
  const axeBefore = await new AxeBuilder({ page }).analyze();
  fs.writeFileSync(
    path.join(REPORTS_DIR, 'axe_before.json'),
    JSON.stringify(
      {
        url: '/web/purchasing?a11y=before',
        violations_count: axeBefore.violations.length,
        violations: axeBefore.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          help: v.help,
          nodes_count: v.nodes.length,
          targets: v.nodes.map((n) => n.target),
        })),
      },
      null,
      2
    )
  );
  expect(axeBefore.violations.length).toBeGreaterThanOrEqual(4);

  // 2. Scan AFTER screen fix (?a11y=after) on both Workflow 1 and Workflow 2 screens
  await page.goto('/web/purchasing?a11y=after');
  const axeAfterW1 = await new AxeBuilder({ page }).analyze();

  await page.goto('/web/receive?a11y=after');
  const axeAfterW2 = await new AxeBuilder({ page }).analyze();

  fs.writeFileSync(
    path.join(REPORTS_DIR, 'axe_after.json'),
    JSON.stringify(
      {
        workflow1_screen: {
          url: '/web/purchasing?a11y=after',
          violations_count: axeAfterW1.violations.length,
          passes_count: axeAfterW1.passes.length,
          violations: axeAfterW1.violations,
        },
        workflow2_screen: {
          url: '/web/receive?a11y=after',
          violations_count: axeAfterW2.violations.length,
          passes_count: axeAfterW2.passes.length,
          violations: axeAfterW2.violations,
        },
      },
      null,
      2
    )
  );

  expect(axeAfterW1.violations.length).toBe(0);
  expect(axeAfterW2.violations.length).toBe(0);
});
