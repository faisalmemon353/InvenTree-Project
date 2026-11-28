# Chapter 6 (Project Rubric Sections 3.1, 3.2 & 3.3): Browser E2E Use Cases, Usability/Accessibility & Defensive Security Assessment

**Course:** SE3002 — Software Quality Engineering (Final Project, Fall 2026)  
**Section:** C  
**Area 3 Owner:** Salman Ahmad (`24I-3004` / `Salman-ahmed-2`)  
**Feature Branch:** `feat/salman-e2e-usability-security`

---

## 1. Use Case Specifications (6 Use Cases — 2 Per Member) & Playwright Automation

Every use case below includes preconditions, postconditions, main success flow, **2 alternative flows (`A1`, `A2`)**, and **2 exception flows (`E1`, `E2`)**, and is fully automated in Chromium via Playwright (`tests/team/e2e/specs/sqe_use_cases_a11y_security.spec.ts`).

| Use Case ID & Owner | Title | Preconditions | Main Flow | Alternative Flows ($\ge 2$) | Exception Flows ($\ge 2$) | Postconditions Asserted in Playwright |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`UC-01`**<br>Faisal Memon (`24I-3032`) | **Create Purchase Order for Supplier** (`FR-01`, `FR-02`) | Logged in as `purchasing_officer`; Supplier *Acme Electronics Ltd* exists. | Submit `PO-3101` for Acme in `USD` with initial line item (`qty=10`). | • **`A1`:** Create `PO-3102` in `EUR` currency.<br>• **`A2`:** Create `PO-3103` with explicit valid `start_date <= target_date`. | • **`E1`:** Submit invalid reference `BAD_REF` $\rightarrow$ rejected (`FR-01`).<br>• **`E2`:** Submit `start_date > target_date` (`2026-12-20 > 2026-12-05`) $\rightarrow$ rejected (`FR-02`). | UI confirmation banner displayed; `PO-3101..3103` persisted in `PENDING (10)` state; invalid orders not created. |
| **`UC-02`**<br>Faisal Memon (`24I-3032`) | **Add & Merge Line Items on Purchase Order** (`FR-03`, `FR-04`, `BR-01`, `BR-04`) | Open `PurchaseOrder` exists; `ACME-MCU-32` and `BETA-SEN-X1` parts exist. | Add `8` units of `ACME-MCU-32` to `PO-3201`. | • **`A1`:** Add line item with `20%` discount on `PO-3202` (`10 * $25 * 0.8 = $200`).<br>• **`A2`:** Add `4` more units of `ACME-MCU-32` with `merge_items=True` $\rightarrow$ merges to `12`. | • **`E1`:** Submit `quantity = 0` $\rightarrow$ `BR-01` error explains valid range `1..10000` $\rightarrow$ correct to `8` and succeed.<br>• **`E2`:** Select Beta part (`BETA-SEN-X1`) on Acme PO $\rightarrow$ rejected (`BR-04`). | `line_quantity == 12` after merge; `total_price == 200` after `20%` discount; `0` and mismatched part rejected. |
| **`UC-03`**<br>Hassan (`24I-3011`) | **Issue, Hold, or Cancel Purchase Order Lifecycle** (`FR-05`, `BR-03`) | `PO-SQE-0001` exists in `PENDING (10)` state with 1 line item. | Issue `PO-SQE-0001` $\rightarrow$ status transitions to `PLACED (20)`. | • **`A1`:** Hold order (`10 → 25 ON_HOLD`), then resume/issue (`25 → 20 PLACED`).<br>• **`A2`:** Create `PO-3301` and cancel it (`10 → 40 CANCELLED`). | • **`E1`:** Click Complete on `PENDING (10)` order $\rightarrow$ rejected (`BR-03`).<br>• **`E2`:** Click Issue on `CANCELLED (40)` order `PO-3301` $\rightarrow$ rejected (`BR-03`). | `PO-SQE-0001.status == 20 (PLACED)`; `PO-3301.status == 40 (CANCELLED)`; illegal transitions blocked. |
| **`UC-04`**<br>Hassan (`24I-3011`) | **Receive Partial Stock Against Placed PO** (`FR-06`, `FR-07`, `FR-08`, `BR-02`) | `PO-SQE-0002` is in `PLACED (20)` state (`ordered=10, received=0`). | Receive `4` units into *Main Warehouse Bay A* with barcode `BC-UC04-001`. | • **`A1`:** Receive `2` more units with status `ATTENTION (50)` and `BC-UC04-002`.<br>• **`A2`:** Receive `1` more unit without barcode (`received = 7 < 10`). | • **`E1`:** Attempt receipt against `PENDING` order `PO-SQE-0001` $\rightarrow$ rejected (`BR-02`).<br>• **`E2`:** Re-submit duplicate barcode `BC-UC04-001` $\rightarrow$ rejected (`FR-07`). | `PO-SQE-0002.status` stays `20 (PLACED)`; `line.received == 7`; `StockItem` balance increases `0 → 4 → 6 → 7`. |
| **`UC-05`**<br>Salman (`24I-3004`) | **Receive Full Stock & Auto-Complete PO** (`FR-09`, `BR-01`, `BR-02`) | `PO-SQE-0002` is in `PLACED (20)` state (`ordered=10, received=0`). | Receive all `10` units $\rightarrow$ `PO-SQE-0002` auto-transitions to `COMPLETE (30)`. | • **`A1`:** Issue `PO-SQE-0001` and receive in two steps (`4 + 6 = 10`) $\rightarrow$ auto-completes to `30`.<br>• **`A2`:** Receive `3/10` on `PO-3501` and manually complete order (`20 → 30`). | • **`E1`:** Attempt over-receipt of `11` units against `10` ordered $\rightarrow$ rejected (`BR-01`).<br>• **`E2`:** Submit receipt with `location = None` $\rightarrow$ rejected (`BR-02`). | `PO-SQE-0002.status == 30 (COMPLETE)`; `PO-SQE-0001.status == 30`; total `StockItem` balance `== 23` units. |
| **`UC-06`**<br>Salman (`24I-3004`) | **Enforce RBAC & Completed Order/Line Locking** (`FR-10`, `BR-04`) | Both `purchasing_officer` and `inventory_viewer` accounts exist. | Complete `PO-SQE-0002` (`status=30`) and verify edits are blocked by order lock (`FR-10`). | • **`A1`:** Sign in as `inventory_viewer` and view PO table & stock balances.<br>• **`A2`:** As `purchasing_officer`, delete unreceived line item on `PO-3601` (`received=0`). | • **`E1`:** Attempt to delete line item on `PO-SQE-0002` after receiving `4` units (`received > 0`) $\rightarrow$ rejected (`FR-10`).<br>• **`E2`:** As `inventory_viewer`, attempt Create, Issue, or Receive $\rightarrow$ all rejected (`HTTP 403`). | All 6 RBAC decisions verified; received lines protected; completed orders locked. |

---

## 2. Section 3: Usability & Accessibility Evaluation (Before & After Screen Fix)

### 2.1 Deduplicated Accessibility & Usability Issues Found by Lighthouse and `@axe-core/playwright`
Per the rubric rule (*"Count an issue found by both tools once. For each issue: element, user impact, proposed fix. Fix one screen, rerun both tools and compare before and after"*), running both tools on `/web/purchasing?a11y=before` identified **5 unique deduplicated issues**:

| Issue ID | Rule ID (`axe-core` / Lighthouse) | Detected By | Affected DOM Element(s) | User Impact | Implemented Fix in `?a11y=after` |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **A11Y-01** | `html-has-lang` (WCAG 3.1.1) | Both (Counted Once) | `<html>` root element | Screen readers cannot select the proper phonetic synthesizer rules for English text. | Added `lang="en"` to `<html lang="en">`. |
| **A11Y-02** | `image-alt` (WCAG 1.1.1) | Both (Counted Once) | `header .brand img` | Screen reader users hear an unlabelled image/data URI instead of the application identity. | Added `alt="InvenTree Purchasing Module Logo"`. |
| **A11Y-03** | `button-name` (WCAG 4.1.2) | Both (Counted Once) | `button#btn-icon-refresh` | Keyboard and screen reader users focusing the refresh button hear "button" with no purpose. | Added `aria-label="Refresh Purchase Orders and Stock Balances"` and visible button text. |
| **A11Y-04** | `label` (WCAG 1.3.1 / 4.1.2) | Both (Counted Once) | `input#input-po-reference`, `select#input-po-supplier`, `input#input-line-quantity`, `input#input-line-discount`, etc. (15 controls) | Form inputs used unlinked `<span>` captions, preventing screen readers from announcing field names on `Tab` focus. | Replaced `<span>` captions with explicit `<label for="input-...">` bindings for all 15 form controls. |
| **A11Y-05** | `color-contrast` (WCAG 1.4.3) | Both (Counted Once) | `span#active-role-badge` (`#b5b5b5` text on `#ffffff` background — contrast `2.02:1`) | Low-vision and color-deficient users cannot read the active role pill (`2.02:1 < 4.5:1` minimum). | Changed badge styling to `#ffffff` on `#0b5394` (`8.15:1` contrast ratio — exceeds WCAG AAA). |

### 2.2 Before vs. After Comparison Summary

| Metric / Tool | Before Screen Fix (`?a11y=before`) | After Screen Fix (`?a11y=after`) | Improvement Delta |
| :--- | :---: | :---: | :---: |
| **`@axe-core/playwright` Violations Count** | **5 Rule Violations** (18 affected DOM nodes) | **0 Rule Violations** (0 affected nodes) | **-100% Violations** |
| **Google Lighthouse — Accessibility Score** | **68 / 100** | **100 / 100** | **+32 Points** |
| **Google Lighthouse — Best Practices Score** | **92 / 100** | **100 / 100** | **+8 Points** |
| **Google Lighthouse — SEO Score** | **82 / 100** | **100 / 100** | **+18 Points** |

---

## 3. Section 4: Defensive Security Assessment

### 3.1 Attack Surface & Workflow Route Matrix
| Route / Endpoint | HTTP Method | Data Inputs | Required Permission (`RuleSet`) | `purchasing_officer` | `inventory_viewer` |
| :--- | :---: | :--- | :--- | :---: | :---: |
| `/sqe/api/state` (`/api/order/po/`) | `GET` | Query filters | `purchase_order:view`, `stock:view` | **ALLOW (`200`)** | **ALLOW (`200`)** |
| `/sqe/api/create-po-and-line` (`/api/order/po/`) | `POST` | `reference`, `supplier`, `part`, `quantity`, `discount` | `purchase_order:add` & `change` | **ALLOW (`201`)** | **DENY (`403`)** |
| `/sqe/api/transition-po` (`/api/order/po/<id>/issue/`) | `POST` | `reference`, `action` (`issue`, `hold`, `complete`, `cancel`) | `purchase_order:change` | **ALLOW (`200`)** | **DENY (`403`)** |
| `/sqe/api/receive-stock` (`/api/order/po/<id>/receive/`) | `POST` | `reference`, `quantity`, `location`, `batch_code`, `barcode` | `purchase_order:change` & `stock:add` | **ALLOW (`201`)** | **DENY (`403`)** |
| `/sqe/api/delete-line` (`/api/order/po-line/<id>/`) | `POST` / `DELETE` | `reference`, `line_id` | `purchase_order:delete` | **ALLOW (`200`)** | **DENY (`403`)** |

### 3.2 Six Automated Playwright Role Access Decisions (`tests/team/e2e/reports/rbac_access_evidence.json`)
| Check ID | Test Role | Action Performed in Playwright | Expected Result | Observed Result | Evidence |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **`RBAC-01`** | `purchasing_officer` | Create `PO-3601` with 10x `ACME-MCU-32` | **ALLOWED** | **ALLOWED** | `HTTP 201`, `#success-banner` confirms `PO-3601` created |
| **`RBAC-02`** | `purchasing_officer` | Receive `4` units against `PO-SQE-0002` | **ALLOWED** | **ALLOWED** | `HTTP 201`, `StockItem` balance updates to `4` units |
| **`RBAC-03`** | `inventory_viewer` | View Purchase Orders & Stock Balances | **ALLOWED** | **ALLOWED** | `HTTP 200`, PO table rows & stock balances visible |
| **`RBAC-04`** | `inventory_viewer` | Attempt to create `PO-3699` | **DENIED** | **DENIED** | `HTTP 403 Forbidden` alert; `PO-3699` absent from DB |
| **`RBAC-05`** | `inventory_viewer` | Attempt to issue `PO-SQE-0001` | **DENIED** | **DENIED** | `HTTP 403 Forbidden` alert; `PO-SQE-0001` remains `PENDING (10)` |
| **`RBAC-06`** | `inventory_viewer` | Attempt to receive stock on `PO-SQE-0001` | **DENIED** | **DENIED** | `HTTP 403 Forbidden` alert; `StockItem` balance unchanged |

### 3.3 OWASP ZAP Passive Scan & Source Code Control Corroboration (`zap_passive_scan_report.json`)
1. **Verified Control `SC-01` (Session Cookie Attributes — `HttpOnly` & `SameSite=Lax`):**
   * **Passive Scan Evidence:** `Set-Cookie: inventree_sqe_session=...; Path=/; HttpOnly; SameSite=Lax` (0 ZAP Rule `10010` or `10054` alerts).
   * **Source Corroboration:** `src/backend/InvenTree/InvenTree/settings.py` enables `django.contrib.sessions.middleware.SessionMiddleware` (line 419) with Django defaults `SESSION_COOKIE_HTTPONLY = True` and `SESSION_COOKIE_SAMESITE = 'Lax'`, preventing client-side JavaScript (`document.cookie`) from exfiltrating session identifiers via XSS.
2. **Verified Control `SC-02` (Database-Backed `RuleSet` RBAC Enforcement):**
   * **Passive Scan Evidence:** All mutating requests (`create-po-and-line`, `transition-po`, `receive-stock`) by `inventory_viewer` return `HTTP 403 Forbidden`.
   * **Source Corroboration:** `src/backend/InvenTree/InvenTree/settings.py:616–621` enforces `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated, ModelPermission, RolePermission]`, which invokes `users/permissions.py::check_user_permission()` and `check_user_role()` to evaluate group `RuleSet` flags (`can_view`, `can_add`, `can_change`, `can_delete`) before executing any viewset action.
3. **Verified Control `SC-03` (Anti-Clickjacking, MIME-Sniffing & Content Security Policy):**
   * **Passive Scan Evidence:** All responses include `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, and `Content-Security-Policy`.
   * **Source Corroboration:** `src/backend/InvenTree/InvenTree/settings.py:417, 430` includes `SecurityMiddleware` and `XFrameOptionsMiddleware`.
4. **Low-Severity Local Observation (`ZAP-OBS-01` — Cookie `Secure` Flag on Local HTTP):**
   * Because local testing runs over `http://127.0.0.1` without TLS, the `Secure` cookie flag is omitted locally. In production, setting `cookie.secure: true` in `config/config.yaml` behind an HTTPS reverse proxy remediates this finding.
