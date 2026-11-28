# Chapter 2 (Project Rubric Section 4.1): Test Plan, Three-Point Estimation, Risk Register, Exit Criteria & Traceability Matrix

**Course:** SE3002 — Software Quality Engineering (Final Project, Fall 2026)  
**Section:** C  
**System Under Test:** InvenTree (`order` Module — Purchase Order Creation/Issuance & Stock Receipt Workflows)  
**Baseline Commit:** `b686d7cb64e0b09644d9e9afb0ce4997dfde0c1d`

---

## 1. Test Plan

### 1.1 Test Scope
* **In-Scope Components:**
  * **Server-Side Business Logic (`src/backend/InvenTree/order/models.py`, `serializers.py`):** `Order.clean()`, `Order.check_locked()`, `TotalPriceMixin.calculate_total_price()`, `PurchaseOrder.clean()`, `PurchaseOrder.add_line_item()`, `PurchaseOrder.place_order()`, `PurchaseOrder.hold_order()`, `PurchaseOrder.complete_order()`, `PurchaseOrder.cancel_order()`, `PurchaseOrder.receive_line_items()`, `PurchaseOrderLineItem.clean()`, `PurchaseOrderLineItem.remaining()`, `PurchaseOrderLineItem.is_completed()`, `PurchaseOrderLineItemSerializer`, and `PurchaseOrderReceiveSerializer`.
  * **REST API Endpoints (`src/backend/InvenTree/order/api.py`):**
    * `GET / POST /api/order/po/` and `GET / PATCH / DELETE /api/order/po/<id>/`
    * `POST /api/order/po/<id>/issue/`, `/hold/`, `/complete/`, `/cancel/`
    * `POST /api/order/po/<id>/receive/`
    * `GET / POST /api/order/po-line/` and `GET / PATCH / DELETE /api/order/po-line/<id>/`
    * `GET /api/stock/` (cross-workflow stock balance verification)
  * **Browser UI Screens (React Frontend / Web UI):**
    * Login & Session Management (`/web/login`)
    * Purchasing Index & Purchase Order Creation Drawer (`/web/purchasing/index/purchaseorders`)
    * Purchase Order Detail, Line Item Management, Issue Order Modal, and Receive Line Items Modal (`/web/purchasing/purchase-order/<id>`)
    * Stock Location / Stock Items Verification Screen (`/web/stock/location/<id>`)
* **Out-of-Scope Components:** Manufacturing (`build`), Sales Orders (`SalesOrder`), Return Orders (`ReturnOrder`), third-party ERP plugins, and mobile barcode app.

### 1.2 Risk-Based Testing Approach
Testing depth and technique selection are governed directly by the risk score ($R = \text{Likelihood} \times \text{Impact}$, on a $1\text{--}25$ scale) from our $5 \times 5$ Risk Register:
* **Critical / High Risks ($R \ge 15$):** Tested exhaustively across **all three functional levels** (White-box Unit with 100% statement/branch coverage + MCC & MC/DC + custom mutation operators; API & Integration with automated OpenAPI EP & 3-point BVA + state transition matrix + idempotency/duplicate checks; and Playwright E2E + Failure/Recovery or RBAC security checks).
* **Medium Risks ($8 \le R \le 14$):** Tested across **two test levels** (Unit statement/branch + API EP/BVA or Playwright E2E alternative/exception flows, Lighthouse/axe-core scans, and k6 load testing).
* **Low Risks ($R \le 7$):** Verified via **single-level targeted checks** (Unit or passive OWASP ZAP / `pip-audit` dependency checks).

### 1.3 Team Roles & Area Ownership
| Member | Roll No. | Primary Responsibilities | Backup / Peer Reviewer |
| :--- | :--- | :--- | :--- |
| **Faisal Memon** | `24I-3032` | **Area 1 Owner:** SonarQube static analysis, CFG & Cyclomatic Complexity calculation, White-box unit testing (100% stmt/branch, MCC, MC/DC), `mutmut` mutation testing + 2 custom operators + 15 mutant analysis, GitHub Actions CI quality gate, Blocked PR & Fix PR. Co-author of Test Management. | Hassan Zahid |
| **Hassan Zahid** | `24I-3011` | **Area 2 Owner:** OpenAPI 3.0 specification for PO & receipt endpoints, Python automated EP & 3-point BVA generator script, spec constraint-change demonstration, `pytest` + `requests` API & cross-workflow integration test suite, endpoint weakness analysis. Co-author of Test Management. | Salman Ahmad |
| **Salman Ahmad** | `24I-3004` | **Area 3 Owner:** 6 Use Case specifications (2 per member) & Playwright E2E automation, Usability & Accessibility (keyboard navigation, Lighthouse + `@axe-core/playwright` before/after screen fix), Defensive Security (Access Matrix, Playwright RBAC checks, OWASP ZAP passive scan, `pip-audit`), Performance & Recovery (Grafana k6 1-VU & 5-VU runs, fault-injection recovery test). Co-author of Test Management. | Faisal Memon |

### 1.4 Test Environment & Test Data Strategy
* **Operating System & Hardware:** Windows 10/11 64-bit, x86_64 multi-core CPU, 16 GB RAM.
* **Runtime & Tool Versions:** Python `3.13`, Node.js `v24.11.1`, Docker `v29.7.2` (SonarQube Community Edition & OWASP ZAP), Grafana `k6 v2.2.0`, `pytest`, `coverage.py`, `mutmut`, Playwright (Chromium), `@axe-core/playwright`, Google Lighthouse, `pip-audit`.
* **Synthetic Data Management:** Managed deterministically via `tests/team/scripts/seed_sqe_data.py` and reset before every test suite run via `tests/team/scripts/reset_sqe_data.py`. No real customer or production data is used.

### 1.5 Entry, Exit, Suspension & Resumption Criteria
* **Entry Criteria:**
  1. Baseline commit `b686d7cb64e0b09644d9e9afb0ce4997dfde0c1d` is tagged and pushed to `main` and `dev`.
  2. Database migrations execute cleanly with zero errors, and `seed_sqe_data.py` creates all required synthetic records and both role accounts.
  3. OpenAPI specification and automated generator script produce valid JSON test datasets.
* **Suspension Criteria:**
  1. Application server fails to boot or database migration corruption prevents seeding/resetting data.
  2. A blocker defect (`S1 - Critical`) in `PurchaseOrder.place_order()` or `PurchaseOrder.receive_line_items()` prevents executing downstream workflow steps.
* **Resumption Criteria:**
  1. Blocker defect is patched on a dedicated fix branch, verified locally, and `reset_sqe_data.py` restores a clean baseline state.
* **Exit Criteria (Measurable Release Criteria — Tied to Highest Risks):**
  * **EC-01 (Functional / White-Box & Mutation Quality — Tied to Risks `PR-01`, `PR-02`, `PR-03`):** **100% statement and branch coverage** on the targeted server-side business-rule functions in `order` (with any uncovered lines formally justified), **100% pass rate** across all unit (MCC & MC/DC), API (EP & 3-point BVA), and Playwright E2E use-case flows, and a **mutation score $\ge 85\%$** after killing all non-equivalent surviving mutants among the analyzed sample.
  * **EC-02 (Security & Access Control — Tied to Risk `PR-04`):** **100% enforcement ($4/4$ automated Playwright RBAC checks passing)** ensuring the `inventory_viewer` role cannot create, issue, or receive Purchase Orders (`HTTP 403`), **zero High/Critical vulnerabilities** in `OWASP ZAP` passive scan on workflow routes, and all `pip-audit` findings triaged with documented remediation.
  * **EC-03 (Performance, Recovery & Accessibility — Tied to Risks `PR-05`, `PR-06`, `PR-08`):** Under Grafana k6 load testing (both 1 VUser and 5 concurrent VUsers over 60s steady-state), **$p_{95}$ response time $\le 500\text{ ms}$** and **unexpected failure rate $< 1.0\%$**, **zero duplicate or orphaned `StockItem` records** after controlled failure-and-recovery testing, and **Lighthouse Accessibility score $\ge 90$** (with zero Critical/Serious `axe-core` violations on the fixed screen).

---

## 2. Three-Point Effort Estimation (PERT) & Actual Effort Tracking

Using the PERT three-point estimation formula:
$$E = \frac{O + 4M + P}{6}, \quad \sigma = \frac{P - O}{6}$$
where $O$ = Optimistic hours, $M$ = Most Likely hours, and $P$ = Pessimistic hours.

| WBS Area | Owner | Optimistic ($O$) | Most Likely ($M$) | Pessimistic ($P$) | Expected Effort $E$ (hrs) | Std. Dev. $\sigma$ (hrs) | Actual Effort (hrs) | Variance ($\text{Actual} - E$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. System Scope, Seed/Reset & Test Plan/Risk Register** | All (Lead: Faisal Memon) | 5.0 | 7.0 | 11.0 | **7.33** | 1.00 | *7.50* | *+0.17* |
| **2. SonarQube Static Analysis & Hand-Calculated CFG** | Faisal Memon (`24I-3032`) | 3.0 | 4.5 | 7.0 | **4.67** | 0.67 | *4.50* | *-0.17* |
| **3. White-Box Unit Tests (100% Cov, MCC & MC/DC)** | Faisal Memon (`24I-3032`) | 8.0 | 11.0 | 16.0 | **11.33** | 1.33 | *TBD (Step 2)* | *TBD* |
| **4. Mutation Testing (`mutmut`, Custom Ops) & CI Gate** | Faisal Memon (`24I-3032`) | 6.0 | 9.0 | 14.0 | **9.33** | 1.33 | *TBD (Step 2)* | *TBD* |
| **5. OpenAPI Spec & Automated EP / 3-Point BVA Generator** | Hassan (`24I-3011`) | 5.0 | 7.5 | 11.0 | **7.67** | 1.00 | *TBD (Step 3)* | *TBD* |
| **6. API & Cross-Workflow Integration Test Suite** | Hassan (`24I-3011`) | 7.0 | 9.5 | 14.0 | **9.83** | 1.17 | *TBD (Step 3)* | *TBD* |
| **7. Use Case Specs (6) & Playwright E2E Automation** | Salman (`24I-3004`) | 7.0 | 10.0 | 15.0 | **10.33** | 1.33 | *TBD (Step 4)* | *TBD* |
| **8. Usability & Accessibility (Lighthouse, axe-core, Fix)** | Salman (`24I-3004`) | 4.0 | 6.0 | 9.0 | **6.17** | 0.83 | *TBD (Step 4)* | *TBD* |
| **9. Defensive Security (RBAC, OWASP ZAP, `pip-audit`)** | Salman (`24I-3004`) | 4.5 | 6.5 | 10.0 | **6.75** | 0.92 | *TBD (Step 4)* | *TBD* |
| **10. Performance (k6) & Controlled Failure/Recovery** | Salman (`24I-3004`) | 4.5 | 6.5 | 10.0 | **6.75** | 0.92 | *TBD (Step 5)* | *TBD* |
| **11. Defect RCA (5 Whys + Fishbone), GQM & Final Report** | All 3 Members | 5.0 | 7.0 | 11.0 | **7.33** | 1.00 | *TBD (Step 5)* | *TBD* |
| **Total Project Effort** | **Team of 3** | **59.0** | **84.5** | **128.0** | **87.50 hrs** | **3.52 hrs** | *Updated per step* | *Updated per step* |

---

## 3. Risk Register ($5 \times 5$ Likelihood $\times$ Impact Matrix)

**Scale Definition:**
* **Likelihood ($L \in \{1..5\}$):** `1` = Rare ($<10\%$), `2` = Unlikely ($10\text{--}30\%$), `3` = Possible ($30\text{--}60\%$), `4` = Likely ($60\text{--}85\%$), `5` = Almost Certain ($>85\%$).
* **Impact ($I \in \{1..5\}$):** `1` = Negligible, `2` = Minor, `3` = Moderate, `4` = Major (data corruption / security bypass / workflow failure), `5` = Catastrophic (inventory ledger divergence / unauthorized financial commitment).
* **Risk Score ($R = L \times I$):** **Critical/High:** $15\text{--}25$ | **Medium:** $8\text{--}14$ | **Low:** $1\text{--}7$.

### 3.1 Product Risks (9 Identified — Minimum 8 Required) & Project Risks (3 Identified — Minimum 2 Required)

| Risk ID | Category | Risk Description | Related Req / Rule | $L$ (1–5) | $I$ (1–5) | Score ($L \times I$) | Level | Assigned Testing Technique & Depth | Linked Exit Criterion |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- | :--- | :--- |
| **PR-01** | **Product** (State / Data Integrity) | Stock is received against a Purchase Order that is **not** in `PLACED (20)` state (e.g., `PENDING`, `ON_HOLD`, `COMPLETE`, or `CANCELLED`), creating phantom inventory without a valid supplier commitment. | `FR-06`, `BR-02`, `BR-03` | 4 | 5 | **20** | **CRITICAL** | **Exhaustive:** White-box Unit (MCC & MC/DC on `receive_line_items`), Full State Transition Matrix at API level (test every allowed & disallowed state), Custom Mutation Operator flipping `status != PLACED`. | `EC-01` |
| **PR-02** | **Product** (Boundary / Financial) | Zero, negative, or malformed quantities (`quantity <= 0`) or out-of-range discounts (`< 0` or `> 100`) are accepted on PO line items or stock receipts, corrupting `StockItem.quantity` and `PurchaseOrder.total_price`. | `FR-03`, `FR-04`, `FR-07`, `BR-01` | 4 | 5 | **20** | **CRITICAL** | **Exhaustive:** OpenAPI automated 3-point BVA (`just below`, `at`, `just above` 0, 1, 100) + EP invalid classes at API level; Unit tests with 100% branch coverage + BVA boundary mutation operator (`<=` to `<`); Playwright UI validation recovery test. | `EC-01` |
| **PR-03** | **Product** (Cross-Workflow / Concurrency) | Repeated or partially failed stock receipt requests cause duplicate `StockItem` records, lost updates on `PurchaseOrderLineItem.received`, or failure to auto-transition `PurchaseOrder` to `COMPLETE (30)` when `pending_line_count == 0`. | `FR-08`, `FR-09`, `BR-02` | 4 | 4 | **16** | **HIGH** | **Deep:** Controlled failure-and-recovery integration test with dependency fault injection; API repeated-request & cross-workflow read-back verification (`PO.status`, `line.received`, `StockItem.quantity`); MC/DC on auto-complete decision. | `EC-01`, `EC-03` |
| **PR-04** | **Product** (Security / RBAC) | An unauthorized user (`inventory_viewer` with `view`-only `RuleSet`) bypasses UI controls or calls REST API endpoints directly to create, issue, or receive a Purchase Order (Privilege Escalation / Broken Access Control). | `BR-04` | 3 | 5 | **15** | **HIGH** | **Deep:** Role Access Matrix + 4 automated Playwright RBAC checks across both roles + API `403 Forbidden` assertions + OWASP ZAP passive scan & source code review of `check_user_permission`. | `EC-02` |
| **PR-05** | **Product** (Integrity / Locking) | A completed (`COMPLETE (30)`) Purchase Order or a line item that has already received stock (`received > 0`) is modified or deleted, erasing the audit trail between physical stock and purchasing records. | `FR-10`, `BR-03` | 3 | 4 | **12** | **MEDIUM** | **Standard+:** White-box unit tests on `Order.check_locked()` and `PurchaseOrderLineItemViewSet.check_received()`; API `DELETE /api/order/po-line/<id>/` rejection test after partial receipt. | `EC-01` |
| **PR-06** | **Product** (Performance) | Under concurrent warehouse operations ($\ge 5$ simultaneous users receiving stock and querying POs), database row locking (`select_for_update()`) causes $p_{95}$ latency $> 500\text{ ms}$ or HTTP 5xx timeouts. | `FR-08`, `FR-09` | 3 | 4 | **12** | **MEDIUM** | **Standard+:** Grafana k6 load testing with 1 VUser and 5 concurrent VUsers (2 runs each, $\ge 60\text{s}$ steady state) measuring $p_{95}$ latency, RPS, and error percentage. | `EC-03` |
| **PR-07** | **Product** (Business Logic) | A `SupplierPart` belonging to Supplier B is added to a `PurchaseOrder` raised for Supplier A, or mismatched contact/address records are attached to the order. | `FR-02`, `FR-03`, `BR-04` | 3 | 3 | **9** | **MEDIUM** | **Standard:** Equivalence Partitioning (mismatched supplier ID / contact ID) at Unit (`Order.clean`, `PurchaseOrderLineItem.clean`) and API levels. | `EC-01` |
| **PR-08** | **Product** (Usability / Accessibility) | Warehouse operators using keyboard-only navigation or assistive technology cannot navigate the PO creation / stock receipt modals or understand validation error messages due to missing ARIA labels, focus traps, or low contrast. | `FR-01`, `FR-07` | 3 | 3 | **9** | **MEDIUM** | **Standard:** Playwright automated keyboard-only (`Tab`/`Enter`) test, invalid-input error clarity test, Google Lighthouse + `@axe-core/playwright` audit, and before/after UI screen fix. | `EC-03` |
| **PR-09** | **Product** (Security / Supply Chain) | Vulnerable third-party Python packages or insecure session cookie attributes (`HttpOnly`, `SameSite`) expose the MIS to session hijacking or known CVEs. | Security (Sec 4) | 2 | 3 | **6** | **LOW** | **Targeted:** `pip-audit` dependency vulnerability scan and OWASP ZAP passive cookie/header inspection corroborated by `settings.py` review. | `EC-02` |
| **PJ-01** | **Project** (Environment / CI) | Dirty database state between test runs causes flaky failures across unit, API, and Playwright E2E tests in local runs and GitHub Actions CI. | All FRs | 4 | 4 | **16** | **HIGH** | **Mitigation & Control:** Deterministic `reset_sqe_data.py` executed before every test run; isolated pytest transactions for unit tests; strict CI gate with zero escape hatches (`|| true` banned). | `EC-01` |
| **PJ-02** | **Project** (Viva / Spec Change) | Late change to business-rule constraints or OpenAPI specification during the Viva breaks hardcoded test data or leaves team members unable to predict failing pipeline gates. | Generator (Sec 2) | 3 | 4 | **12** | **MEDIUM** | **Mitigation & Control:** Fully data-driven API tests reading dynamically from `generate_test_data.py` (no hardcoded boundary literals); dry-run rehearsal of 2 OpenAPI constraint changes. | `EC-01` |
| **PJ-03** | **Project** (Team / Git History) | Merge conflicts or direct commits to `main` violate the repository branching policy or obscure individual commit ownership required for the Viva. | Submission (Sec 6) | 2 | 4 | **8** | **MEDIUM** | **Mitigation & Control:** Strict `main ← dev ← feat/<member>-<task>` branching model; every member commits and pushes their own feature branches and merges via PRs checked by GitHub Actions. | `EC-01` |

---

## 4. Requirements Traceability Matrix (RTM)

| Req / Rule ID | Description Summary | Risk ID | Unit Tests (`tests/team/unit/`) | API Tests (`tests/team/api/`) | E2E / Use Case (`tests/team/e2e/`) | Non-Functional (A11y / Sec / Perf) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FR-01** | Create `PurchaseOrder` (`PENDING`, unique ref, valid supplier) | `PR-07`, `PR-08` | `test_po_creation_and_reference` | `test_api_create_po_ep_bva` | `UC-01`, `UC-02` | Lighthouse / axe-core (PO Screen), ZAP |
| **FR-02** | Order `start_date <= target_date` & company contact/address match | `PR-07` | `test_order_clean_dates_and_company` | `test_api_po_date_and_contact_validation` | `UC-01` (Exception E1) | — |
| **FR-03** | Add `PurchaseOrderLineItem` (`quantity > 0`, matching supplier) | `PR-02`, `PR-07` | `test_add_line_item_boundaries_and_supplier` | `test_api_add_line_ep_bva` | `UC-02` (Main & Alt A1, Exc E1) | Usability Error Recovery Test |
| **FR-04** | Duplicate line item merge & `total_price` calculation with discount | `PR-02` | `test_line_merge_and_total_price_bva` | `test_api_line_merge_and_discount_bva` | `UC-02` (Alt A2) | — |
| **FR-05** | Issue/Place PO (`PENDING` / `ON_HOLD` → `PLACED`, `issue_date` set) | `PR-01`, `PR-04` | `test_po_fsm_transitions_and_issue` | `test_api_issue_po_transitions_and_idempotency` | `UC-03` (Main, Alt A1/A2, Exc E1/E2) | Playwright RBAC Check #1 & #2 |
| **FR-06** | Reject stock receipt unless `PurchaseOrder.status == PLACED (20)` | `PR-01` | `test_receive_requires_placed_status_mcdc` | `test_api_receive_disallowed_states` | `UC-04` (Exc E1) | — |
| **FR-07** | Receipt `quantity > 0`, destination `StockLocation`, unique barcode/serial | `PR-02`, `PR-08` | `test_receive_serializer_validation_mcdc` | `test_api_receive_ep_bva_inputs` | `UC-04` (Exc E2), `UC-05` (Exc E1/E2) | Keyboard Nav Test, Lighthouse / axe-core |
| **FR-08** | Partial stock receipt creates `StockItem`, increments `received`, stays `PLACED` | `PR-03`, `PR-06` | `test_receive_partial_line_item` | `test_api_partial_receipt_cross_workflow` | `UC-04` (Main & Alt A1) | k6 Load Test (1 VU & 5 VU) |
| **FR-09** | Full stock receipt auto-completes PO (`PLACED → COMPLETE`, `complete_date`) | `PR-03`, `PR-06` | `test_receive_full_auto_complete_mcdc` | `test_api_full_receipt_auto_complete` | `UC-05` (Main & Alt A1/A2) | Failure & Recovery Test |
| **FR-10** | Prevent deleting received line items & lock `COMPLETE` orders | `PR-05` | `test_locked_order_and_received_line_delete` | `test_api_reject_delete_received_line_and_edit_locked_po` | `UC-06` (Main, Alt A1/A2, Exc E1/E2) | — |
| **BR-01** | Boundary Rule: `quantity >= 1` (`> 0`), `0 <= discount <= 100`, `received >= quantity` | `PR-02` | `test_br01_quantity_and_discount_bva` + Custom Mutant #1 | `test_api_br01_generated_3pt_bva` | `UC-02` (Exc E1), `UC-04` (Exc E2) | Usability Invalid-to-Valid Flow |
| **BR-02** | Multi-Boolean Decision: Receipt eligibility ($C_1..C_4$) & auto-complete ($C_5, C_6$) | `PR-01`, `PR-03` | `test_br02_mcc_and_mcdc_pairs` (100% MCC + MC/DC) | `test_api_br02_decision_table` | `UC-04`, `UC-05` | Failure & Recovery Test |
| **BR-03** | State Transition Rule: All allowed & disallowed PO state transitions | `PR-01`, `PR-05` | `test_br03_state_transition_matrix` + Custom Mutant #2 | `test_api_br03_state_transitions` | `UC-03`, `UC-06` | — |
| **BR-04** | Supplier-part matching & Role-Based Access Control (`Purchasing Officer` vs `Viewer`) | `PR-04`, `PR-07` | `test_br04_supplier_match_and_rbac_permissions` | `test_api_br04_rbac_and_supplier_mismatch` | `UC-01`..`UC-06` + `test_rbac_matrix.spec.ts` | Playwright 4 Access Decisions, ZAP, `pip-audit` |
