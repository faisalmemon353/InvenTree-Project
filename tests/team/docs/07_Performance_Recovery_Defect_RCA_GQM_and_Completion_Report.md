# Chapter 7 (Project Rubric Sections 4.2, 4.3, 4.4, 5.1, 5.2 & 7): Performance, Recovery, Defect Management, Root Cause Analysis, GQM Progress & Test Completion Report

**Course:** SE3002 — Software Quality Engineering (Fall 2026) | **Section:** C  
**System Under Test (SUT):** InvenTree (`https://github.com/inventree/InvenTree`, commit `b686d7cb64e0b09644d9e9afb0ce4997dfde0c1d`, MIT License)  
**Team Repository:** `https://github.com/faisalmemon353/InvenTree-Project`  
**Step 5 Primary Owner:** Salman Ahmad (`24I-3004`, GitHub: `Salman-ahmed-2`)  
**Shared Management Co-Owners:** Faisal Memon (`24I-3032`, GitHub: `faisalmemon353`) & Hassan Zahid (`24I-3011`, GitHub: `Hassan-Zahid110`)

---

## 1. Performance & Load Testing with Grafana k6 (Section 5.1)

### 1.1 Critical Operation & Pre-Test Threshold Justification

Before executing load tests, we selected the primary cross-workflow operation cycle of the Purchasing & Stock Receipt subsystem:
- **Target Operation:** Authenticated Purchase Order & Stock Balance State Query + Purchase Order Line Creation/Merge Cycle (`GET /sqe/api/state?role=purchasing_officer` followed by `POST /sqe/api/create-po-and-line`), implemented in `tests/team/performance/po_load_test.js` and orchestrated by `tests/team/performance/run_k6_benchmarks.py`.
- **Pre-Test Response-Time Threshold:**
  $$p_{95} \le 500.0\text{ ms}$$
  *Justification:* Interactive MIS warehouse operations require sub-500 ms 95th-percentile server response times so procurement officers and receiving clerks do not double-submit orders or barcode scans (`EC-03`).
- **Pre-Test Failure-Rate Threshold:**
  $$\text{Unexpected Failure Rate} < 1.0\%\quad (\text{Target: } 0.00\%)$$
  *Justification:* Every authenticated valid request must return `HTTP 200 OK` (`GET /sqe/api/state`) or `HTTP 201 Created` (`POST /sqe/api/create-po-and-line`) without `5xx` server errors or SQLite lock failures.

### 1.2 Experimental Setup & Reproducibility Controls

- **Load Testing Tool:** Grafana `k6 v2.2.0` (`constant-vus` executor).
- **Controlled Environment:** Identical InvenTree commit build, Windows 10 x64 workstation, Python `3.13.9`, SQLite database `config/inventree_sqe.sqlite3`, and identical starting data (reset via `POST /sqe/api/reset` plus 3 warm-up requests before every run).
- **Workload Matrix:**
  1. **1 Simulated User (`1 VUser`) — Run twice (`Run-1A` and `Run-1B`):** 60 seconds of continuous steady-state load per run.
  2. **5 Concurrent Simulated Users (`5 VUsers`) — Run twice (`Run-2A` and `Run-2B`):** 60 seconds of continuous steady-state load per run.

### 1.3 Live Grafana k6 Load Test Results (4 Runs $\times$ 60s = 240s Total Steady-State Load)

All raw Grafana `k6` outputs and JSON summary exports are persisted in `tests/team/performance/logs/run_1vu_1.txt`, `run_1vu_2.txt`, `run_5vu_1.txt`, `run_5vu_2.txt`, and `tests/team/performance/k6_benchmark_summary.json`.

| Run ID | Simulated Users (VUsers) | Steady-State Duration | Total Requests Completed | Requests / sec (RPS) | Average Latency (ms) | Median $p_{50}$ Latency (ms) | 95th-Percentile $p_{95}$ (ms) | Max Latency (ms) | Failure Rate (%) | Threshold Verdict ($p_{95} \le 500\text{ ms}$, $\text{Fail} < 1\%$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Run-1A (1-VU #1)** | 1 VUser | 60 s | 480 | **8.00 req/s** | 46.60 ms | 41.32 ms | **101.83 ms** | 290.89 ms | **0.00%** | **PASS** |
| **Run-1B (1-VU #2)** | 1 VUser | 60 s | 420 | **6.99 req/s** | 66.22 ms | 48.03 ms | **168.08 ms** | 599.21 ms | **0.00%** | **PASS** |
| **1-VU Mean** | **1 VUser** | **60 s (x2)** | **450 avg** | **7.50 req/s** | **56.41 ms** | **44.68 ms** | **134.96 ms** | **445.05 ms** | **0.00%** | **PASS** |
| **Run-2A (5-VU #1)** | 5 VUsers | 60 s | 1,224 | **20.27 req/s** | 169.18 ms | 159.25 ms | **337.30 ms** | 711.61 ms | **0.00%** | **PASS** |
| **Run-2B (5-VU #2)** | 5 VUsers | 60 s | 922 | **15.20 req/s** | 248.10 ms | 238.12 ms | **424.70 ms** | 826.95 ms | **0.00%** | **PASS** |
| **5-VU Mean** | **5 VUsers** | **60 s (x2)** | **1,073 avg** | **17.73 req/s** | **208.64 ms** | **198.69 ms** | **381.00 ms** | **769.28 ms** | **0.00%** | **PASS** |

### 1.4 Performance Analysis & N+1 Query Bottleneck Discovery

1. **Throughput Scaling (`1-VU` vs. `5-VU`):** Scaling from 1 VUser to 5 concurrent VUsers increased mean throughput by **$2.36\times$** (from **7.50 req/s** to **17.73 req/s**) while maintaining a **0.00% failure rate** across all 3,046 total HTTP requests.
2. **Latency Under Concurrency:** Mean $p_{95}$ response time increased from **134.96 ms** (1-VU) to **381.00 ms** (5-VU), remaining **23.8% below** the pre-test `500.0 ms` SLA threshold in every individual run (`337.30 ms` in Run-2A and `424.70 ms` in Run-2B).
3. **Diagnostic Finding (`DEF-08` — N+1 Query in `GET /sqe/api/state`):** During initial 5-VU calibration runs prior to query optimization, iterating over `PurchaseOrder.objects.all()` executed 2 separate SQLite queries per order (`po.lines.first()` and `po.lines.count()`), causing $p_{95}$ latency to cross `503.12 ms` under 5-VU load. Adding `.prefetch_related('lines')` reduced per-request database round-trips from $2N + 1$ to $2$ constant queries and brought 5-VU $p_{95}$ latency down to **337.30 ms – 424.70 ms**.

---

## 2. Controlled Failure and Recovery Test (Section 5.2)

### 2.1 Fault-Injection Design (`tests/team/integration/test_failure_recovery.py`)

We engineered an automated pytest test (`test_controlled_db_failure_atomic_rollback_and_clean_retry_recovery`) that targets the state-changing Workflow 2 stock receipt transaction (`execute_receive_purchase_order_line` $\rightarrow$ `PurchaseOrder.receive_line_items`, which is wrapped in `@transaction.atomic` at `src/backend/InvenTree/order/models.py:1122`):

1. **Starting State:** Purchase Order `PO-SQE-0002` is in `PLACED (20)` status with 1 line item (`LINE-MCU-02`, `quantity = 10`, `received = 0`) and `0` `StockItem` records associated with the order.
2. **Fault Injection Mid-Transaction:** Using `unittest.mock.patch("order.models.audited_bulk_update", side_effect=OperationalError("Simulated storage dependency failure mid-transaction before line item commit"))`, we inject a database `OperationalError` **after** `bulk_create_and_fetch(StockItem, ...)` has already inserted the new `StockItem` row into SQLite inside `receive_line_items()`, right when `audited_bulk_update` attempts to persist `PurchaseOrderLineItem.received`.
3. **Persisted State Verification After Failure (Atomic Rollback):**
   - `pytest.raises(OperationalError)` confirms the exception surfaces cleanly without silent corruption.
   - Re-querying the database via `po.refresh_from_db()`, `line.refresh_from_db()`, and `StockItem.objects.filter(purchase_order=po).count()` verifies that `@transaction.atomic` rolled back the entire unit of work:
     - `PurchaseOrder.status == 20 (PLACED)`
     - `PurchaseOrderLineItem.received == Decimal('0')`
     - `StockItem.objects.filter(purchase_order=po).count() == 0` (the bulk-created `StockItem` row was completely rolled back; zero orphan or partial records exist).
4. **Dependency Restoration & Retry Verification:**
   - Exiting the `with patch(...)` block restores `audited_bulk_update`, and retrying `execute_receive_purchase_order_line(po=po, line=line, quantity=Decimal('10'), ...)` succeeds cleanly:
     - `PurchaseOrder.status == 30 (COMPLETE)`
     - `PurchaseOrderLineItem.received == Decimal('10')`
     - `len(StockItem.objects.filter(purchase_order=po)) == 1` with `quantity == Decimal('10')` (zero duplicate or partial records).

---

## 3. Defect Management, Triage & Root Cause Analysis (Section 4.3)

### 3.1 Logged Defect Register across Testing Levels

All defects and quality weaknesses discovered across Static Analysis (Step 1), White-Box Unit & Mutation Testing (Step 2), OpenAPI/API Testing (Step 3), Playwright E2E / Accessibility / Security Auditing (Step 4), and k6 Load Testing (Step 5) are cataloged below with explicit severity, priority, status, and triage decisions:

| Defect ID | Summary / Title | Discovery Technique & Step | Category | Target Location | Severity | Priority | Status | Triage Decision |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **DEF-01** | Upstream `PurchaseOrder.receive_line_items()` permits unrestricted over-receiving beyond `line.quantity` without server-side guard | White-Box Unit & Custom Mutation Operator `CustomOp2` (Step 2) | Business Logic / Inventory Integrity | `order/models.py:1237` & `order/po_business_rules.py:241` | **High** | **P1** | **Fixed & Verified** | Enforce strict server-side `new_received > line.quantity` guard in `execute_receive_purchase_order_line` unless `allow_over_receive=True` |
| **DEF-02** | Potential `NoneType` dereference (`self.order.company`) in `PurchaseOrderLineItem.clean()` when `order` FK is unassigned | SonarQube Static Analysis & CFG Basis Path `P2` (Step 1 & Step 2) | Null-Safety / Defensive Validation | `order/models.py:3245` (`OrderLineItem.clean`) | **Medium** | **P2** | **Mitigated / Documented** | Guarded at serializer and `po_business_rules` entry points; logged upstream defensive check recommendation |
| **DEF-03** | Purchasing & Stock Receipt UI screen violates 6 WCAG 2.1 AA rules (`label`, `select-name`, `button-name`, `color-contrast`, `html-has-lang`, `image-alt`) | `@axe-core/playwright` & Google Lighthouse Accessibility Audit (Step 4) | Accessibility (WCAG 2.1 AA) | `sqe_web_portal_server.py:124-155` | **High** | **P1** | **Fixed & Verified** | Remediated all 6 violations; `@axe-core/playwright` improved from 6 violations to **0 violations (41 passes)** and Lighthouse from **68/100 to 100/100** |
| **DEF-04** | `PurchaseOrder.place_order()` allows issuing a Purchase Order with zero line items (`lines.count() == 0`) | FSM State Transition & API Integration Testing (Step 3) | State Transition / Business Logic | `order/models.py:980` & `order/po_business_rules.py:207` | **Medium** | **P2** | **Fixed & Verified** | Added mandatory `po.lines.count() < 1` rejection (`ValidationError`) in `execute_issue_purchase_order()` |
| **DEF-05** | `PurchaseOrderCompleteSerializer` defaults `accept_incomplete` loosely without enforcing `pending_line_count == 0` | OpenAPI Contract & Auto-Completion MC/DC Testing (Step 3) | API Contract / State Integrity | `order/serializers.py:725` & `order/po_business_rules.py:135` | **Medium** | **P2** | **Fixed & Verified** | Enforced `should_auto_complete_order()` MC/DC logic requiring `pending_line_count == 0` and no unauthorized over-receipt |
| **DEF-06** | Missing explicit compound RBAC check requiring both `purchase_order:change` and `stock:add` on direct model stock receipt helper | RBAC Role Matrix & Custom Mutator `CustomOp3` (Step 2 & Step 4) | Security / Access Control (RBAC) | `order/po_business_rules.py:189-193` | **High** | **P1** | **Fixed & Verified** | Enforced compound `has_po_change and has_stock_add` check in `check_po_role_permission(user, 'receive')`; verified via Playwright RBAC-06 (`HTTP 403`) |
| **DEF-07** | Missing `Permissions-Policy` HTTP response header on web portal responses | OWASP ZAP Passive Scan (Step 4) | Security Hardening Header | `sqe_web_portal_server.py:497` | **Low** | **P3** | **Accepted Risk (Deferred)** | Low-severity informational finding; core anti-XSS/clickjacking headers (`CSP`, `X-Frame-Options`, `X-Content-Type-Options`, `HttpOnly`) are active |
| **DEF-08** | N+1 SQLite query bottleneck in `GET /sqe/api/state` (`po.lines.first()` & `po.lines.count()` inside loop) causing 5-VU $p_{95} > 500\text{ ms}$ | Grafana `k6` 5-VU Concurrent Load Testing (Step 5) | Performance / Database Query | `sqe_web_portal_server.py:552` | **Medium** | **P2** | **Fixed & Verified** | Added `.prefetch_related('lines')`, reducing 5-VU $p_{95}$ from `503.12 ms` to **381.00 ms mean** (`PASS`) |

---

### 3.2 Pareto Analysis of Defects by Category

Grouping the 8 logged defects across our quality evaluation reveals where defects concentrated:

| Defect Category | Defect Count | Percentage of Total (%) | Cumulative Percentage (%) | Defect IDs |
| :--- | :---: | :---: | :---: | :--- |
| **1. Business Logic & State Transition Integrity** | 3 | 37.5% | **37.5%** | `DEF-01`, `DEF-04`, `DEF-05` |
| **2. Security & Access Control (RBAC / Headers)** | 2 | 25.0% | **62.5%** | `DEF-06`, `DEF-07` |
| **3. Accessibility & UI Compliance (WCAG 2.1 AA)** | 1 | 12.5% | **75.0%** | `DEF-03` |
| **4. Performance & Database Query Scaling** | 1 | 12.5% | **87.5%** | `DEF-08` |
| **5. Null-Safety & Defensive Static Guards** | 1 | 12.5% | **100.0%** | `DEF-02` |
| **Total** | **8** | **100.0%** | **100.0%** | `DEF-01` .. `DEF-08` |

```mermaid
xychart-beta
    title "Pareto Analysis of Discovered Defects by Category"
    x-axis ["Business Logic & FSM", "Security & RBAC", "Accessibility (WCAG)", "Performance (N+1)", "Null-Safety"]
    y-axis "Defect Count" 0 --> 8
    bar [3, 2, 1, 1, 1]
    line [3, 5, 6, 7, 8]
```

**Pareto Insight (80/20 Rule):** Over **75% of all defects** (`6 of 8`) originated in **Business Logic/State Transitions**, **Security/RBAC**, and **Accessibility** — validating our risk register prioritization (`PR-01`, `PR-02`, `PR-03`, `PR-05`, `PR-06`) in Step 1.

---

### 3.3 Full Root Cause Analysis (5 Whys + Fishbone Diagram) for Major Defect 1 (`DEF-01`)

#### Defect 1: `DEF-01` — Unrestricted Over-Receiving in `PurchaseOrder.receive_line_items()` (Severity: High, P1)

- **5 Whys Analysis:**
  1. **Why did stock receipt allow receiving 25 units against a Purchase Order line item that only ordered 10 units?**  
     Because `PurchaseOrder.receive_line_items()` in `src/backend/InvenTree/order/models.py:1237` increments `line.received += quantity` after checking only `if quantity < 0`, without comparing `line.received + quantity` against `line.quantity`.
  2. **Why did `receive_line_items()` omit an upper-bound comparison against `line.quantity`?**  
     Because the upstream model method assumed the front-end UI or serializer would pre-warn the user, treating over-delivery as an implicit default rather than an explicit policy flag (`allow_over_receive`).
  3. **Why did relying on client/UI warnings create a high-severity inventory integrity defect?**  
     Because direct REST API callers or automated warehouse barcode scanners bypass UI warnings, causing `StockItem.quantity` and inventory valuation to inflate beyond approved Purchase Order budgets (`BR-01` / `FR-06`).
  4. **Why was this gap not caught by standard line-coverage unit tests?**  
     Because standard happy-path tests only pass `quantity == line.quantity` (`10 == 10`); only 3-point Boundary Value Analysis (`quantity = 11` when `ordered = 10`) and our custom domain mutation operator (`CustomOp2_OverReceiveBoundaryMutator`: mutating `>` to `>=`) expose boundary off-by-one and over-receipt flaws.
  5. **Root Cause:** Absence of a domain-level invariant guard (`new_received > line.quantity and not allow_over_receive`) inside the server-side transactional business rule layer, combined with missing upper-boundary BVA and domain-specific mutation tests.

```mermaid
flowchart LR
    subgraph Fishbone_DEF01["Ishikawa (Fishbone) Diagram — DEF-01: Unrestricted Stock Over-Receiving"]
        direction LR
        C1["Architecture & Design<br/>Validation split between UI warning<br/>and model layer; no allow_over_receive flag"] --> EFFECT
        C2["Code & Implementation<br/>order/models.py:1237 only checks<br/>quantity < 0 before line.received += quantity"] --> EFFECT
        C3["Requirements & Rules<br/>Implicit assumption in upstream repo<br/>that over-shipment is always acceptable"] --> EFFECT
        C4["Testing & Verification<br/>Happy-path tests omitted 3-point BVA<br/>(ordered + 1) and boundary mutation operators"] --> EFFECT
        EFFECT["DEF-01 (High / P1)<br/>Unrestricted Over-Receiving<br/>Inflates StockItem.quantity"]
    end
```

- **Corrective Action Taken:** Implemented strict server-side upper-bound enforcement in `execute_receive_purchase_order_line()` (`src/backend/InvenTree/order/po_business_rules.py:240-243`) and `should_auto_complete_order()` (`lines 135-151`), raising `ValidationError({'quantity': 'Over-receiving beyond ordered quantity is not permitted'})` whenever `line.received + qty_dec > line.quantity` and `allow_over_receive=False`.
- **Preventive Action Taken:** Added `CustomOp2_OverReceiveBoundaryMutator` to `tests/team/mutation/run_mutation_analysis.py` (enforced in `.github/workflows/sqe-quality-gate.yml` at $\ge 90\%$ mutation score) and Playwright E2E test `UC-05 E1` so any regression weakening the `>` comparison fails CI immediately.

---

### 3.4 Full Root Cause Analysis (5 Whys + Fishbone Diagram) for Major Defect 2 (`DEF-03`)

#### Defect 2: `DEF-03` — WCAG 2.1 AA Form Label, Button Name, and Color Contrast Violations (Severity: High, P1)

- **5 Whys Analysis:**
  1. **Why did the baseline Purchasing & Stock Receipt UI fail `@axe-core/playwright` with 6 violations and score 68/100 on Google Lighthouse Accessibility?**  
     Because form inputs used visual `<span>` captions instead of `<label for="...">` bindings, the header refresh control was an empty `<button>` without accessible text, the status pill used low-contrast `#b5b5b5` on `#ffffff` (`2.03:1` < `4.5:1`), `<html>` lacked a `lang` attribute, and the brand `<img>` lacked `alt` text.
  2. **Why were `<span>` tags and low-contrast styles used during initial UI construction?**  
     Because initial prototyping focused purely on visual layout for sighted mouse users rather than programmatic ARIA semantics (`for`/`id` association) and WCAG 2.1 AA contrast ratios.
  3. **Why did this block keyboard and assistive-technology users?**  
     Screen readers could not announce the purpose of the 15 form controls (`input-po-reference`, `select-role`, `input-recv-quantity`, etc.) or the icon refresh button during Tab traversal.
  4. **Why was an iterative accessibility audit needed even after adding `aria-label` to `#btn-icon-refresh`?**  
     Because `@axe-core/playwright`'s `label-content-name-mismatch` rule requires a control's programmatic `aria-label` (`"Refresh Data - Purchase Orders and Stock Balances"`) to contain the exact visible text string (`"Refresh Data"`).
  5. **Root Cause:** Lack of automated accessibility linting (`@axe-core/playwright` and Lighthouse) in the front-end acceptance workflow and reliance on visual-only form markup instead of semantic HTML5 label associations.

```mermaid
flowchart LR
    subgraph Fishbone_DEF03["Ishikawa (Fishbone) Diagram — DEF-03: WCAG 2.1 AA Accessibility Violations"]
        direction LR
        A1["HTML Markup Semantics<br/>Used <span> instead of <label for=...><br/>and omitted <html lang='en'> & img alt"] --> EFFECT2
        A2["CSS & Visual Design<br/>Status badge #b5b5b5 on #ffffff<br/>(2.03:1 ratio vs 4.5:1 WCAG AA minimum)"] --> EFFECT2
        A3["ARIA Naming Rules<br/>Icon button lacked accessible name;<br/>aria-label initially mismatched visible text"] --> EFFECT2
        A4["QA Process<br/>Accessibility checks were not automated<br/>in Playwright E2E suite prior to Step 4"] --> EFFECT2
        EFFECT2["DEF-03 (High / P1)<br/>6 axe-core WCAG 2.1 AA Violations<br/>& Lighthouse Score 68/100"]
    end
```

- **Corrective Action Taken:** Bound all 15 form inputs/selects to explicit `<label for="...">` elements, upgraded the status pill to `#ffffff` on `#0b5394` (`7.54:1` contrast ratio), added `<html lang="en">` and `alt="InvenTree Purchasing Module Logo"`, and aligned `#btn-icon-refresh` visible text and `aria-label`. Verified **0 violations (41 passes)** in `@axe-core/playwright` and **100/100** in Google Lighthouse Accessibility.
- **Preventive Action Taken:** Embedded `@axe-core/playwright` zero-violation assertions (`expect(afterResults.violations.length).toBe(0)`) directly inside `tests/team/e2e/specs/sqe_use_cases_a11y_security.spec.ts` alongside automated keyboard-only `Tab`/`Enter` focus navigation verification.

---

## 4. Weekly Progress Report, Control Actions & GQM Metrics (Section 4.2)

### 4.1 Weekly Progress & Control Actions Log

| Week / Milestone | Planned Scope (PERT Schedule) | Actual Completed Deliverables | Schedule / Quality Variance | Control Action Taken |
| :--- | :--- | :--- | :--- | :--- |
| **Week 1 (Step 1)** | Scope definition, Risk Register, RTM, SonarQube static analysis, and CFG $V(G)$ calculation (Faisal Memon `24I-3032`) | Completed `01_System_Scope_and_Test_Basis.md`, `02_Test_Plan_Risk_Register_and_RTM.md`, `03_Static_Analysis_SonarQube_and_CFG.md`, and live SonarQube scan (`7,637` NCLOC, $V(G)=14$ verified) | Shallow clone rejected initial push to `origin`; local SonarQube container needed fresh token | Re-initialized clean root baseline commit tagged `upstream-b686d7cb64e0b09644d9e9afb0ce4997dfde0c1d` and automated SonarQube scan script |
| **Week 2 (Step 2)** | White-box unit tests (100% statement/branch), MCC/MC/DC, custom mutation operators ($\ge 15$ survivors analyzed), and CI Quality Gate PRs (Faisal Memon `24I-3032`) | 47 unit tests with **100.00% statement & branch coverage** (`185/185` stmts, `46/46` branches), **92.0% raw / 100.0% non-equivalent mutation score**, Blocked PR #1 and Documented Fix PR #2 | 11 upstream InvenTree GitHub Actions workflows triggered unrelated matrix jobs on PRs; 16 baseline mutants survived initial weak suite | Disabled upstream `*.yaml.disabled` workflows so `sqe-quality-gate.yml` is authoritative; added 16 targeted boundary/RBAC assertions to kill all non-equivalent survivors |
| **Week 3 (Step 3)** | OpenAPI 3.0 spec, automated EP & 3-point BVA generator, 2-constraint Viva diff, and API/integration test suite (Hassan Zahid `24I-3011`) | `openapi_po_spec.yaml` (v1 & v2), `generate_test_data.py` (82 EP + 117 3-point BVA values), and **33/33 passing API & cross-workflow integration tests** merged via PR #3 | Full Django test runner took $>45\text{s}$ per run due to 300 migrations | Adopted `-p no:django` against pre-migrated `config/inventree_sqe.sqlite3`, cutting API suite execution time to `1.8s` |
| **Week 4 (Step 4 & 5)** | 6 Use Cases, Playwright E2E, Usability & Accessibility Before/After fix, Security (RBAC, ZAP, `pip-audit`), Grafana `k6` load testing, Failure/Recovery, and Final Report (Salman Ahmad `24I-3004`) | **8/8 Playwright tests** (`37.4s`), Lighthouse `68 -> 100`, axe-core `6 -> 0` violations, ZAP + `pip-audit` (`0` vulnerabilities), **4 $\times$ 60s `k6` load runs**, **1/1 Failure/Recovery test**, and full RCA/GQM/Completion Report | SQLite lock contention under multi-threaded server and N+1 query in `/sqe/api/state` during 5-VU `k6` test | Switched to serialized `HTTPServer` with `fast_reset_orders_and_stock()` (`5 ms`) and added `.prefetch_related('lines')`, achieving `0.00%` failures and 5-VU $p_{95} = 381.00\text{ ms}$ |

---

### 4.2 Goal-Question-Metric (GQM) Evaluation Table

We defined three project-level **Goal-Question-Metric (GQM)** objectives in our Test Plan and evaluated them against live empirical measurements at project completion:

| GQM Goal | Questions | Metric Name & Formula | Target Threshold | Actual Measured Value | Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Goal 1 (Code & Defect Quality):** Ensure high defect detection efficiency and low latent defect density in the InvenTree `order` module (`7.637` KLOC). | **Q1.1:** What is the discovered and resolved defect density across the scoped subsystem?<br/>**Q1.2:** Do any white-box mutations survive our unit test suite? | **Defect Density:** $\frac{\text{Total Confirmed Defects}}{\text{KLOC in } order/}$<br/>**Mutation Score:** $\frac{\text{Killed Mutants}}{\text{Total Non-Equivalent Mutants}} \times 100\%$ | Documented & $100\%$ High/Med fixed<br/>Mutation Score $\ge 90.0\%$ | **$1.05\text{ defects/KLOC}$** ($8 / 7.637\text{ KLOC}$; $7/7$ High/Med fixed, $1$ Low accepted)<br/>**$92.0\%$ raw / $100.0\%$ non-equivalent** ($23/23$ killed) | **MET** |
| **Goal 2 (Requirements & Risk Coverage):** Achieve complete verification coverage across all functional requirements, business rules, and use-case flows. | **Q2.1:** What percentage of functional requirements (`FR-01..FR-10`) and business rules (`BR-01..BR-04`) are covered by passing automated tests?<br/>**Q2.2:** Are all 6 use cases (Main + 2 Alternatives + 2 Exceptions) verified end-to-end? | **Requirements Coverage:** $\frac{\text{Verified FRs & BRs}}{\text{Total Scoped FRs & BRs}} \times 100\%$<br/>**Use-Case Path Coverage:** $\frac{\text{Passing E2E Use-Case Flows}}{\text{Total Specified Flows}} \times 100\%$ | $100.0\%$ FR & BR coverage<br/>$100.0\%$ Use-Case flow coverage | **$100.0\%$** ($10/10$ FRs + $4/4$ BRs covered across 89 automated tests)<br/>**$100.0\%$** ($30/30$ flows across `UC-01..UC-06` passing in Playwright) | **MET** |
| **Goal 3 (Resolution Stability & Operational Readiness):** Ensure defect fixes do not introduce regressions and system meets non-functional SLAs. | **Q3.1:** What percentage of resolved defects had to be reopened after verification?<br/>**Q3.2:** Does the system meet WCAG 2.1 AA accessibility, RBAC security, and $p_{95} \le 500\text{ ms}$ load thresholds? | **Defect Reopen Rate:** $\frac{\text{Reopened Defects}}{\text{Total Resolved Defects}} \times 100\%$<br/>**k6 5-VU $p_{95}$ & Failure Rate** | Reopen Rate $= 0.0\%$<br/>$p_{95} \le 500\text{ ms}$, Fail $< 1.0\%$ | **$0.0\%$ Reopen Rate** ($0 / 7$ resolved defects reopened)<br/>**$p_{95} = 381.00\text{ ms}$ (5-VU), $0.00\%$ failure** | **MET** |

---

## 5. Test Completion Report & Release Recommendation (Section 4.4)

### 5.1 Summary of What Was Tested vs. Not Tested & Plan Deviations

- **Tested Within Scope (100% Executed):**
  1. **Static Analysis (Step 1):** SonarQube `v26.9.0.129388` scan on `src/backend/InvenTree/order/` (`7,637` NCLOC) and manual 21-node CFG Cyclomatic Complexity verification ($V(G)=14$) on `PurchaseOrderLineItem.clean()`.
  2. **White-Box Unit, MC/DC & Mutation Testing (Step 2):** 47 pytest unit tests (`100.00%` statement and branch coverage across `order.po_business_rules`, `order.status_codes`, and `order.validators`, plus all 14 basis paths of `PurchaseOrderLineItem.clean()`), complete 16-row MCC truth tables and minimal MC/DC pairs, and 25 mutants (`92.0%` raw / `100.0%` non-equivalent score).
  3. **CI Quality Gate (Step 2):** GitHub Actions workflow `.github/workflows/sqe-quality-gate.yml` demonstrated on Blocked PR #1 (Red X) and Documented Fix PR #2 (Red X $\rightarrow$ Green Checkmark $\rightarrow$ Merged).
  4. **OpenAPI Specification, Automated Test Data Generator & API Suite (Step 3):** OpenAPI 3.0 spec (`openapi_po_spec.yaml`), automated EP (82 partitions) & 3-point BVA (117 boundary values) generator (`generate_test_data.py`), 2-constraint Viva diff (`openapi_po_spec_v2_modified.yaml`), and 33 passing API & cross-workflow integration tests (`test_po_workflows_api.py`).
  5. **Use-Case E2E, Usability, Accessibility & Security Testing (Step 4):** 6 detailed Use Cases (`UC-01..UC-06`), 8 passing Playwright Chromium/Edge automated tests (`sqe_use_cases_a11y_security.spec.ts`), keyboard-only navigation, Lighthouse (`68 -> 100`) & `@axe-core/playwright` (`6 -> 0` violations) screen remediation, 6 automated RBAC checks (`RBAC-01..06`), OWASP ZAP passive scan + 3 source-code security control corroborations, and `pip-audit` (`166` packages, `0` vulnerabilities).
  6. **Performance & Failure/Recovery Testing (Step 5):** 4 $\times$ 60s Grafana `k6` steady-state load runs (`1-VU` twice and `5-VU` twice) and 1 automated fault-injection `@transaction.atomic` rollback & retry test (`test_failure_recovery.py`).
- **Not Tested (Out of Scope per Section 1.1):**
  - Unrelated InvenTree modules (`build`, `return_order`, `sales_order`, `plugin`, third-party ERP hardware drivers), destructive penetration testing / brute-force credential attacks (prohibited by Section 3.3), and distributed multi-node PostgreSQL cluster failover.
- **Deviations from Initial Plan:**
  - *Deviation 1:* Used `-p no:django` with our pre-migrated SQLite database `config/inventree_sqe.sqlite3` so unit, API, and integration suites execute in `1–12 seconds` rather than re-running 300 InvenTree migrations.
  - *Deviation 2:* Configured Playwright (`channel: 'msedge'`) against the dedicated SQLite-backed SQE web portal server (`sqe_web_portal_server.py`) on port `8765` to deterministically toggle `?a11y=before` and `?a11y=after` screen states in automated CI and local runs.

---

### 5.2 Open Defects & Residual Risk Re-Assessment (`PR-01..PR-09`)

Only **1 Low-severity informational finding (`DEF-07`)** remains open (`Permissions-Policy` header omitted on local portal responses; all critical headers `Content-Security-Policy`, `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, and `HttpOnly; SameSite=Lax` cookies are active). All 7 High and Medium defects (`DEF-01..DEF-06`, `DEF-08`) are **Fixed & Verified**.

| Risk ID | Product Risk Description | Initial Exposure ($L \times I$) | Verification Evidence & Mitigation Applied | Residual Exposure ($L' \times I'$) | Residual Status |
| :--- | :--- | :---: | :--- | :---: | :---: |
| **PR-01** | Unrestricted over-receiving inflates `StockItem.quantity` (`BR-01`) | $4 \times 5 = \mathbf{20}$ (Critical) | Fixed in `DEF-01`; verified by 3-point BVA, `CustomOp2` mutator, and Playwright `UC-05 E1` | $1 \times 5 = \mathbf{5}$ (Low) | **Mitigated** |
| **PR-02** | Disallowed PO state transitions corrupt workflow lifecycle (`BR-03`) | $3 \times 5 = \mathbf{15}$ (High) | Verified across all 5 states in `test_po_workflows_api.py` and `UC-03 E1/E2` | $1 \times 5 = \mathbf{5}$ (Low) | **Mitigated** |
| **PR-03** | Unauthorized `inventory_viewer` modifies POs or receives stock (`BR-04`) | $3 \times 5 = \mathbf{15}$ (High) | Fixed in `DEF-06`; verified by `CustomOp3` mutator and Playwright `RBAC-01..06` (`HTTP 403`) | $1 \times 5 = \mathbf{5}$ (Low) | **Mitigated** |
| **PR-04** | Mid-transaction failure leaves orphan `StockItem` or desynced `received` count | $3 \times 4 = \mathbf{12}$ (High) | Verified `@transaction.atomic` rollback & retry in `test_failure_recovery.py` | $1 \times 4 = \mathbf{4}$ (Low) | **Mitigated** |
| **PR-05** | Premature PO auto-completion while pending lines remain (`BR-02`) | $3 \times 4 = \mathbf{12}$ (High) | Fixed in `DEF-05`; verified by 16-row MCC truth table, MC/DC pairs, and `UC-04`/`UC-05` | $1 \times 4 = \mathbf{4}$ (Low) | **Mitigated** |
| **PR-06** | Supplier mismatch between `PurchaseOrder.supplier` and `SupplierPart.supplier` | $3 \times 3 = \mathbf{9}$ (Medium) | Verified by CFG path `P12`, API BVA suite, and Playwright `UC-02 E2` | $1 \times 3 = \mathbf{3}$ (Low) | **Mitigated** |
| **PR-07** | Duplicate `StockItem` creation on repeated or retried receipt requests | $2 \times 4 = \mathbf{8}$ (Medium) | Verified by duplicate barcode rejection (`UC-04 E2`) and recovery retry test | $1 \times 4 = \mathbf{4}$ (Low) | **Mitigated** |
| **PR-08** | WCAG 2.1 AA accessibility barriers block keyboard or screen-reader users | $4 \times 3 = \mathbf{12}$ (High) | Fixed in `DEF-03`; Lighthouse `68 -> 100` and `@axe-core/playwright` `6 -> 0` violations | $1 \times 3 = \mathbf{3}$ (Low) | **Mitigated** |
| **PR-09** | Concurrent multi-user load degrades response latency above `500 ms` SLA | $3 \times 3 = \mathbf{9}$ (Medium) | Fixed N+1 query (`DEF-08`); 5-VU `k6` mean $p_{95} = 381.00\text{ ms} \le 500\text{ ms}$, `0.00%` fail | $1 \times 3 = \mathbf{3}$ (Low) | **Mitigated** |

---

### 5.3 Exit Criteria Evaluation & Final Release Recommendation

We compare our final measured results directly against the three measurable Exit Criteria (`EC-01`, `EC-02`, `EC-03`) established in Section 4.1 (`02_Test_Plan_Risk_Register_and_RTM.md`):

| Exit Criterion ID | Target Exit Criterion Specification (from Test Plan) | Actual Measured Project Result | Status |
| :--- | :--- | :--- | :---: |
| **EC-01 (White-Box, Mutation & CI Gate)** | $\ge 90\%$ statement & branch coverage on scoped white-box units, $\ge 85\%$ mutation score with $\ge 15$ survivors analyzed, and green GitHub Actions CI Quality Gate. | **100.00% statement & branch coverage** (`185/185` stmts, `46/46` branches); **92.0% raw / 100.0% non-equivalent mutation score** (`16` baseline survivors analyzed & killed); green `SQE Quality Gate` on `dev`. | **PASSED** |
| **EC-02 (Functional, API, E2E, A11y & Security)** | $100\%$ of scoped requirements (`FR-01..FR-10`, `BR-01..BR-04`) and use cases (`UC-01..UC-06`) passing; $0$ open High/Critical defects; $0$ `@axe-core` violations after fix; $100\%$ RBAC & dependency checks passing. | **33/33 API tests + 8/8 Playwright E2E/A11y/RBAC tests + 1/1 Recovery test passing** (`89/89` total tests passing); **0 open High/Medium defects**; **0 `@axe-core` violations (Lighthouse 100/100)**; **0 vulnerable packages (`pip-audit`)**. | **PASSED** |
| **EC-03 (Performance & Recovery SLA)** | Grafana `k6` steady-state (60s) 95th-percentile latency $p_{95} \le 500\text{ ms}$ and unexpected failure rate $< 1.0\%$ across 1-VU (x2) and 5-VU (x2) runs; clean atomic rollback & recovery under fault injection. | **1-VU Mean $p_{95} = 134.96\text{ ms}$ (`0.00%` fail)** and **5-VU Mean $p_{95} = 381.00\text{ ms}$ (`0.00%` fail)** across all 4 $\times$ 60s runs; **100% atomic rollback & zero-duplicate recovery** verified. | **PASSED** |

> **FINAL RELEASE / HOLD RECOMMENDATION: APPROVE FOR RELEASE (`RELEASE`)**  
> All three measurable Exit Criteria (`EC-01`, `EC-02`, `EC-03`) have been quantitatively satisfied with zero open High or Medium defects and low residual risk ($\le 5$) across all nine product risks `PR-01..PR-09`. The Purchasing & Stock Receipt subsystem is **recommended for release**.

---

## 6. Section 7 — Mandatory AI-Use Record

In accordance with **Section 7 (Integrity and AI-Use Policy)** of the SE3002 Project Guidelines, the table below discloses how AI assistance was used during the project, the raw output produced, and what our team manually verified, corrected, and validated against the live InvenTree system:

| Step / Area | Team Member | AI Tool Used | Purpose of Use | Summary of AI Output | What Was Manually Checked, Changed & Verified on the Real System |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Step 1: Static Analysis & CFG** | Faisal Memon (`24I-3032`) | Antigravity AI Assistant | Drafting CFG node/edge mapping template and automating SonarScanner CLI invocation script | Generated initial AST/CFG node table and Python wrapper for SonarQube REST API | Manually traced every `if`/`elif`/`for` branch in `src/backend/InvenTree/order/models.py` (`OrderLineItem.clean` & `PurchaseOrderLineItem.clean`), verified $V(G) = 33 - 21 + 2 = 14$ against live SonarQube `v26.9.0.129388` dashboard metric (`14`), and captured live localhost:9000 evidence. |
| **Step 2: White-Box Unit, MC/DC & Mutation** | Faisal Memon (`24I-3032`) | Antigravity AI Assistant | Scaffolding MCC truth tables, custom AST mutation runner structure, and GitHub Actions YAML | Proposed initial unit test cases and 3 custom business-rule mutation operators | Verified `100.00%` statement/branch coverage in `pytest --cov`, inspected all 16 surviving mutants from the baseline suite, wrote 16 new targeted tests to kill all non-equivalent mutants (`23/23`), proved equivalence for `M-24` & `M-25`, and triggered real GitHub Actions runs on Blocked PR #1 and Documented Fix PR #2. |
| **Step 3: OpenAPI Generator & API Tests** | Hassan Zahid (`24I-3011`) | Antigravity AI Assistant | Structuring OpenAPI 3.0 YAML schema and Python parser for EP & 3-point BVA generation | Generated YAML schema draft and boundary calculation logic in `generate_test_data.py` | Verified every endpoint path and status code against InvenTree's DRF `PurchaseOrderSerializer` and `PurchaseOrderReceiveSerializer`, fixed Windows `weasyprint` import behavior, validated the 2-constraint Viva diff (`quantity: [5..5000]`, `discount: [0..50]`), and ran all 33 API tests against SQLite. |
| **Step 4: Use Cases, Playwright E2E, A11y & Security** | Salman Ahmad (`24I-3004`) | Antigravity AI Assistant | Boilerplate for Playwright TypeScript specs and OWASP ZAP passive header scanner | Drafted Playwright locators and accessibility test harness | Discovered and fixed a real `@axe-core/playwright` `label-content-name-mismatch` violation on `#btn-icon-refresh`, fixed SQLite lock contention by implementing `fast_reset_orders_and_stock()`, and verified all 8 Playwright specs, Lighthouse (`68 -> 100`), ZAP, and `pip-audit` (`166` packages). |
| **Step 5: Grafana k6 Load, Recovery & RCA** | Salman Ahmad (`24I-3004`) | Antigravity AI Assistant | Writing `po_load_test.js` k6 script, fault-injection test, and formatting Mermaid Fishbone/Pareto diagrams | Drafted initial k6 script and `StockItem.save` mock target | Discovered `PurchaseOrder.receive_line_items()` uses `bulk_create_and_fetch()` (bypassing `StockItem.save`), retargeted fault injection to `order.models.audited_bulk_update` to prove real `@transaction.atomic` rollback of bulk-created stock items, fixed an N+1 query (`DEF-08`) with `.prefetch_related('lines')`, and executed 4 full 60-second live `k6` runs (`240s` total). |
