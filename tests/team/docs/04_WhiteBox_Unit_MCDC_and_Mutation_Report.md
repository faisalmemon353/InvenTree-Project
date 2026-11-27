# Section 2.2: White-Box Unit Testing (100% Coverage, MCC & MC/DC), Mutation Analysis & CI Quality Gate

**Course:** SE3002 — Software Quality Engineering (Final Project, Fall 2026)  
**Section:** C  
**Area 1 Owner:** Faisal (`24I-3032`)  
**Test Suite Location:** `tests/team/unit/test_whitebox_po_rules.py` & `tests/team/mutation/run_mutation_analysis.py`

---

## 1. 100% Statement and Branch Coverage Report & Uncovered Code Defense

Per the rubric requirement (*"100% statement and branch coverage of all server-side business logic; justify any uncovered code"*), we executed `pytest` with `coverage.py` (`--cov-branch`) across the server-side business logic modules governing our Purchase Order and Stock Receipt workflows:

| Server-Side Module | Statements | Missed Stmts | Branches | Partial/Missed Branches | Statement Coverage | Branch Coverage |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `src/backend/InvenTree/order/po_business_rules.py` | 97 | **0** | 46 | **0** | **100.0%** | **100.0%** |
| `src/backend/InvenTree/order/status_codes.py` | 52 | **0** | 0 | **0** | **100.0%** | **100.0%** |
| `src/backend/InvenTree/order/validators.py` | 36 | **0** | 0 | **0** | **100.0%** | **100.0%** |
| **Total In-Scope Business Logic** | **185** | **0** | **46** | **0** | **100.0%** | **100.0%** |

### Justification of Out-of-Scope / Uncovered Lines in Monolithic `order/models.py`
InvenTree's monolithic `order/models.py` (4,565 lines) bundles four separate sub-applications in a single file: `PurchaseOrder`, `SalesOrder` (lines 1504–2205, 2604–3250), `ReturnOrder` (lines 3251–3910), and `TransferOrder` (lines 3911–4565), along with external build-order serialization and third-party plugin event hooks.
* **Defense:** Per Section 1 of the project brief (*"choose two related workflows in one module"*), `SalesOrder`, `ReturnOrder`, `TransferOrder`, and external manufacturing `BuildOrder` lines are outside the two selected Purchasing workflows. All server-side business logic for **Workflow 1 (Create & Issue Purchase Order)** and **Workflow 2 (Receive Stock Against Placed Purchase Order)** — including all four business rules (`BR-01..BR-04`), status codes, reference validators, and `PurchaseOrder.place_order()` / `receive_line_items()` / `complete_order()` execution — achieves **100.0% statement and 100.0% branch coverage**.

---

## 2. Complete Multiple Condition Coverage (MCC) & MC/DC Independence Pairs

We constructed complete MCC truth tables and derived minimal MC/DC independence pairs for all three multi-condition Boolean decisions in our critical business-rule module (`order/po_business_rules.py`).

### 2.1 Decision 1 (`BR-04a` — `can_add_or_merge_line_item`): $D_{\text{add}} = A \land B \land C$
* **$A$:** `order_status in PurchaseOrderStatusGroups.OPEN` (`PENDING=10, PLACED=20, ON_HOLD=25`)
* **$B$:** `same_supplier` (`supplier_part.supplier == purchase_order.supplier`)
* **$C$:** `user_can_change_po` (`check_user_role(user, 'purchase_order', 'change')`)

#### Complete MCC Table ($2^3 = 8$ Combinations)
| MCC Row | $A$ (`is_open`) | $B$ (`same_supplier`) | $C$ (`can_change`) | Outcome $D_{\text{add}}$ | Executed In Unit Test |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **Row 1** | `F` | `F` | `F` | **`False`** | `test_br04_mcc_all_8_combinations_can_add_or_merge_line_item` |
| **Row 2** | `F` | `F` | `T` | **`False`** | `test_br04_mcc_all_8_combinations_can_add_or_merge_line_item` |
| **Row 3** | `F` | `T` | `F` | **`False`** | `test_br04_mcc_all_8_combinations_can_add_or_merge_line_item` |
| **Row 4** | `F` | `T` | `T` | **`False`** | `test_br04_mcc_all_8_combinations_can_add_or_merge_line_item` |
| **Row 5** | `T` | `F` | `F` | **`False`** | `test_br04_mcc_all_8_combinations_can_add_or_merge_line_item` |
| **Row 6** | `T` | `F` | `T` | **`False`** | `test_br04_mcc_all_8_combinations_can_add_or_merge_line_item` |
| **Row 7** | `T` | `T` | `F` | **`False`** | `test_br04_mcc_all_8_combinations_can_add_or_merge_line_item` |
| **Row 8** | `T` | `T` | `T` | **`True`** | `test_br04_mcc_all_8_combinations_can_add_or_merge_line_item` |

#### Derived MC/DC Independence Pairs ($N + 1 = 4$ Cases: `{Row 8, Row 4, Row 6, Row 7}`)
| Condition Tested | Independence Pair (MCC Rows) | Vector 1 $\rightarrow$ Outcome | Vector 2 $\rightarrow$ Outcome | Held Constant |
| :---: | :---: | :---: | :---: | :---: |
| **$A$** (`is_open`) | **(Row 8, Row 4)** | `(T, T, T)` $\rightarrow$ `True` | `(F, T, T)` $\rightarrow$ `False` | $B = T, C = T$ |
| **$B$** (`same_supplier`) | **(Row 8, Row 6)** | `(T, T, T)` $\rightarrow$ `True` | `(T, F, T)` $\rightarrow$ `False` | $A = T, C = T$ |
| **$C$** (`can_change`) | **(Row 8, Row 7)** | `(T, T, T)` $\rightarrow$ `True` | `(T, T, F)` $\rightarrow$ `False` | $A = T, B = T$ |

---

### 2.2 Decision 2 (`BR-02a` — `evaluate_stock_receipt_decision`): $D_{\text{recv}} = C_1 \land C_2 \land C_3 \land C_4$
* **$C_1$:** `order_status == PurchaseOrderStatus.PLACED.value (20)`
* **$C_2$:** `line_matches_order` (`line.order_id == po.pk`)
* **$C_3$:** `quantity_positive` (`qty_dec >= 1`)
* **$C_4$:** `has_destination` (`resolved_location is not None`)

#### Complete MCC Table ($2^4 = 16$ Combinations) & Derived MC/DC Pairs
All 16 combinations `(F,F,F,F)` through `(T,T,T,T)` are executed in `test_br02a_mcc_all_16_combinations_evaluate_stock_receipt_decision`. Only **Row 16 `(T, T, T, T)`** evaluates to `True`; Rows 1–15 evaluate to `False`.

| Condition Tested | Independence Pair (MCC Rows) | Vector 1 $\rightarrow$ Outcome | Vector 2 $\rightarrow$ Outcome | Held Constant |
| :---: | :---: | :---: | :---: | :---: |
| **$C_1$** (`is_placed`) | **(Row 16, Row 8)** | `(T, T, T, T)` $\rightarrow$ `True` | `(F, T, T, T)` $\rightarrow$ `False` | $C_2=T, C_3=T, C_4=T$ |
| **$C_2$** (`line_matches`) | **(Row 16, Row 12)** | `(T, T, T, T)` $\rightarrow$ `True` | `(T, F, T, T)` $\rightarrow$ `False` | $C_1=T, C_3=T, C_4=T$ |
| **$C_3$** (`qty_positive`) | **(Row 16, Row 14)** | `(T, T, T, T)` $\rightarrow$ `True` | `(T, T, F, T)` $\rightarrow$ `False` | $C_1=T, C_2=T, C_4=T$ |
| **$C_4$** (`has_destination`) | **(Row 16, Row 15)** | `(T, T, T, T)` $\rightarrow$ `True` | `(T, T, T, F)` $\rightarrow$ `False` | $C_1=T, C_2=T, C_3=T$ |

---

### 2.3 Decision 3 (`BR-02b` — `should_auto_complete_order`): $D_{\text{comp}} = E_1 \land E_2 \land (E_3 \lor \neg E_4)$
* **$E_1$:** `auto_complete_enabled` (`PURCHASEORDER_AUTO_COMPLETE == True`)
* **$E_2$:** `pending_line_count == 0` (all lines have `received >= quantity`)
* **$E_3$:** `allow_over_receive` (over-receipt policy flag)
* **$E_4$:** `has_over_received_line` (`new_received > line.quantity`)

#### Complete MCC Table ($2^4 = 16$ Combinations)
| MCC Row | $E_1$ | $E_2$ | $E_3$ | $E_4$ | Outcome $D_{\text{comp}}$ | Notes |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Rows 1–8** | `F` | `*` | `*` | `*` | **`False`** | Auto-complete disabled ($E_1 = F$) |
| **Rows 9–12** | `T` | `F` | `*` | `*` | **`False`** | Pending lines remain ($E_2 = F$) |
| **Row 13** | `T` | `T` | `F` | `F` | **`True`** | Exact receipt, no over-receive |
| **Row 14** | `T` | `T` | `F` | `T` | **`False`** | Over-received line when `allow_over_receive=False` |
| **Row 15** | `T` | `T` | `T` | `F` | **`True`** | Exact receipt with `allow_over_receive=True` |
| **Row 16** | `T` | `T` | `T` | `T` | **`True`** | Over-received line permitted by `allow_over_receive=True` |

#### Derived MC/DC Independence Pairs ($N + 1 = 5$ Cases: `{Row 5, Row 9, Row 13, Row 14, Row 16}`)
| Condition Tested | Independence Pair (MCC Rows) | Vector 1 $\rightarrow$ Outcome | Vector 2 $\rightarrow$ Outcome | Held Constant |
| :---: | :---: | :---: | :---: | :---: |
| **$E_1$** (`auto_complete`) | **(Row 13, Row 5)** | `(T, T, F, F)` $\rightarrow$ `True` | `(F, T, F, F)` $\rightarrow$ `False` | $E_2=T, E_3=F, E_4=F$ |
| **$E_2$** (`no_pending`) | **(Row 13, Row 9)** | `(T, T, F, F)` $\rightarrow$ `True` | `(T, F, F, F)` $\rightarrow$ `False` | $E_1=T, E_3=F, E_4=F$ |
| **$E_3$** (`allow_over`) | **(Row 16, Row 14)** | `(T, T, T, T)` $\rightarrow$ `True` | `(T, T, F, T)` $\rightarrow$ `False` | $E_1=T, E_2=T, E_4=T$ |
| **$E_4$** (`has_over_recv`) | **(Row 13, Row 14)** | `(T, T, F, F)` $\rightarrow$ `True` | `(T, T, F, T)` $\rightarrow$ `False` | $E_1=T, E_2=T, E_3=F$ |

---

## 3. Mutation Testing, Custom Mutation Operators & Analysis of 16 Surviving Mutants

### 3.1 Custom Business-Rule Mutation Operators (3 Added — Minimum 2 Required)

1. **`CustomOp1_POStatusGuardMutator` (Targets `BR-02` & `BR-03`):** Mutates `PurchaseOrderStatus.PLACED` status preconditions and FSM transition table entries (`ALLOWED_PO_TRANSITIONS`), injecting defects where stock receipts are allowed on `PENDING` or `ON_HOLD` orders or illegal transitions (`PENDING → COMPLETE`, `ON_HOLD → COMPLETE`, `COMPLETE → PLACED`, `CANCELLED → PLACED`) are permitted.
2. **`CustomOp2_OverReceiveBoundaryMutator` (Targets `BR-01`):** Mutates quantity and over-receive limits (`MIN_ORDER_QUANTITY = 1 → 0`, `new_received > line.quantity → new_received > line.quantity + 1` or `>=`), simulating domain boundary defects in warehouse receiving.
3. **`CustomOp3_RBACRoleEscalationMutator` (Targets `BR-04`):** Mutates `RuleSet` role permission checks in `check_po_role_permission()` by downgrading `'add'`, `'change'`, or `'delete'` to `'view'` (or weakening `has_po_change and has_stock_add` to `or`), simulating vertical privilege escalation from `inventory_viewer` to `purchasing_officer`.

### 3.2 Analysis of 16 Surviving Mutants (Initial Baseline Suite vs. Final Strengthened Suite)

When executed against our initial baseline unit test suite (which tested only happy-path nominal flows and basic MC/DC pairs), **16 out of 25 mutants survived** (initial score: `36.0%`). Below is the complete root-cause analysis of all **16 surviving mutants** (Rubric requires $\ge 15$) and how all 14 killable mutants were killed:

| Mutant ID | Operator | Rule | Mutation Introduced | Initial Status | Classification | How Killed / Why Equivalent | Final Status |
| :---: | :--- | :---: | :--- | :---: | :--- | :--- | :---: |
| **M-02** | `CustomOp1_POStatusGuardMutator` | `BR-02` | `order_status == PLACED` $\rightarrow$ `in (PLACED, ON_HOLD)` | SURVIVED | **Missing Test** | Added MCC Row 8 `(F,T,T,T)` & non-PLACED receipt rejection assertion | **KILLED** |
| **M-03** | `CustomOp1_POStatusGuardMutator` | `BR-03` | Allow `PENDING → COMPLETE` in `ALLOWED_PO_TRANSITIONS` | SURVIVED | **Missing Test** | Added `test_br03_disallowed_state_transitions(PENDING, COMPLETE)` | **KILLED** |
| **M-04** | `CustomOp1_POStatusGuardMutator` | `BR-03` | Allow `ON_HOLD → COMPLETE` in `ALLOWED_PO_TRANSITIONS` | SURVIVED | **Missing Test** | Added `test_br03_disallowed_state_transitions(ON_HOLD, COMPLETE)` | **KILLED** |
| **M-05** | `CustomOp1_POStatusGuardMutator` | `BR-03` | Allow terminal `COMPLETE → PLACED` transition | SURVIVED | **Missing Test** | Added `test_br03_disallowed_state_transitions(COMPLETE, PLACED)` | **KILLED** |
| **M-06** | `CustomOp1_POStatusGuardMutator` | `BR-03` | Allow terminal `CANCELLED → PLACED` transition | SURVIVED | **Missing Test** | Added `test_br03_disallowed_state_transitions(CANCELLED, PLACED)` | **KILLED** |
| **M-07** | `CustomOp2_OverReceiveBoundaryMutator` | `BR-01` | `qty_dec < 1` $\rightarrow$ `qty_dec < 0` (allows `qty = 0`) | SURVIVED | **Missing Test** | Added 3-point BVA `test_br01_invalid_quantity_bva_and_ep(invalid_qty=0)` | **KILLED** |
| **M-08** | `CustomOp2_OverReceiveBoundaryMutator` | `BR-01` | `new_received > line.quantity` $\rightarrow$ `> line.quantity + 1` | SURVIVED | **Weak Assertion** | Changed over-receive test input from `qty=20` to exact off-by-1 boundary `qty=11` (ordered `10`) | **KILLED** |
| **M-10** | `CustomOp3_RBACRoleEscalationMutator` | `BR-04` | `'create'` action checks `'view'` instead of `'add'` | SURVIVED | **Missing Test** | Added explicit RBAC assertion `check_po_role_permission(viewer, 'create') is False` | **KILLED** |
| **M-13** | `CustomOp3_RBACRoleEscalationMutator` | `BR-04` | `'delete_line'` action checks `'view'` instead of `'delete'` | SURVIVED | **Missing Test** | Added explicit RBAC assertion `check_po_role_permission(viewer, 'delete_line') is False` | **KILLED** |
| **M-14** | `ROR_RelationalOperatorMutator` | `BR-01` | `qty_dec < 1` $\rightarrow$ `qty_dec <= 1` | SURVIVED | **Missing Test** | Added 3-point BVA exact lower boundary test `qty = 1` | **KILLED** |
| **M-15** | `ROR_RelationalOperatorMutator` | `BR-01` | `qty_dec > 10000` $\rightarrow$ `qty_dec >= 10000` | SURVIVED | **Missing Test** | Added 3-point BVA exact upper boundary test `qty = 10000` | **KILLED** |
| **M-17** | `ROR_RelationalOperatorMutator` | `BR-01` | `disc_dec > 100` $\rightarrow$ `disc_dec >= 100` | SURVIVED | **Missing Test** | Added 3-point BVA exact upper boundary test `discount = 100.00` | **KILLED** |
| **M-18** | `ROR_RelationalOperatorMutator` | `BR-01` | `price_dec < 0` $\rightarrow$ `price_dec <= 0` | SURVIVED | **Missing Test** | Added boundary test `calculate_discounted_line_total(10, 0.00, 0) == 0.00` | **KILLED** |
| **M-19** | `AOR_ArithmeticOperatorMutator` | `BR-01` | `(100 - disc_dec)` $\rightarrow$ `(100 + disc_dec)` | SURVIVED | **Weak Assertion** | Strengthened assertion to check exact discounted price `200.00` at `discount=20%` (not just `discount=0%`) | **KILLED** |
| **M-24** | `ROR_RelationalOperatorMutator` | `BR-02` | `qty_dec >= 1` $\rightarrow$ `qty_dec >= 0` on line 219 | SURVIVED | **Equivalent** | Line 213 `validate_line_item_limits` already raises `ValidationError` if `qty_dec < 1`; thus `qty_dec >= 1` and `qty_dec >= 0` are semantically identical at line 219 | **SURVIVED (EQ)** |
| **M-25** | `ROR_RelationalOperatorMutator` | `BR-02` | `po.status != COMPLETE (30)` $\rightarrow$ `po.status < 30` on line 240 | SURVIVED | **Equivalent** | Line 217 guarantees `po.status` was `PLACED (20)` entering receipt, and `receive_line_items` can only leave it at `20` or `30`; for $\{20, 30\}$, `status != 30` $\equiv$ `status < 30` | **SURVIVED (EQ)** |

### 3.3 Final Mutation Score Summary
* **Total Mutants:** `25` (`13` custom business-rule mutants + `12` standard operator mutants)
* **Killed Mutants:** `23 / 25` (**92.0% Raw Mutation Score**)
* **Equivalent Mutants:** `2` (`M-24`, `M-25`)
* **Effective (Non-Equivalent) Mutation Score:** `23 / 23` (**100.0% of killable mutants killed**)

---

## 4. CI Quality Gate Thresholds & Justification (`.github/workflows/sqe-quality-gate.yml`)

| Quality Gate Check | Enforced Threshold | Justification from Empirical Evidence |
| :--- | :---: | :--- |
| **1. SonarQube / Static Analysis Gate** | **A Rating** (`0` Bugs, `0` Vulnerabilities, Debt Ratio $< 5\%$) & Verified CFG Complexity | Baseline static analysis of `order` showed `0` bugs, `0` vulnerabilities, and `0.2%` debt ratio (**A** ratings across Reliability, Security, Maintainability). Any PR introducing a new bug, vulnerability, or unverified complexity spike breaks the gate. |
| **2. White-Box Unit Coverage Gate** | **`--cov-fail-under=100`** (`100%` Statement & `100%` Branch Coverage) | Because `order/po_business_rules.py`, `order/status_codes.py`, and `order/validators.py` implement critical financial and inventory state transitions (`PR-01`, `PR-02`, `PR-03`, `PR-04`), any untested branch could hide an unvalidated state transition or quantity overflow. |
| **3. Mutation Score Gate** | **`--min-score 90.0`** ($\ge 90.0\%$ Raw / $100\%$ Non-Equivalent) | With `23/25` (`92.0%`) raw mutants killed and `2/25` (`8.0%`) proven mathematically equivalent, a `90.0%` raw threshold guarantees that **zero killable mutants** can survive on any merged pull request. |
