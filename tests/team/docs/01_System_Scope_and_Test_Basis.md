# Section 1: System Selection, Test Scope & Test Basis

**Course:** SE3002 — Software Quality Engineering (Final Project, Fall 2026)  
**Section:** C  
**Team Members:**
| Name | Roll Number | Owned Technical Area (Section 6) | GitHub Username |
| :--- | :--- | :--- | :--- |
| **Faisal** | `24I-3032` | **Area 1:** Static Analysis (SonarQube & CFG), White-Box Unit Testing (100% Stmt/Branch, MCC, MC/DC), Mutation Testing & CI Quality Gate | `faisalmemon353` |
| **Hassan Zahid** | `24I-3011` | **Area 2:** OpenAPI Specification, Automated EP & 3-Point BVA Test Data Generator, API & Cross-Workflow Integration Testing | `hassanzahid-24i3011` |
| **Salman Ahmed** | `24I-3004` | **Area 3:** Use Case Specifications (6 Total), Playwright E2E Automation, Usability & Accessibility (Lighthouse + axe-core), Defensive Security (OWASP ZAP + `pip-audit`) & Performance/Recovery (k6 + Fault Injection) | `salmanahmed-24i3004` |

---

## 1. Repository & Baseline Metadata

| Attribute | Value |
| :--- | :--- |
| **MIS Name** | InvenTree — Open-Source Inventory Management System |
| **Upstream Repository URL** | https://github.com/inventree/InvenTree |
| **Team Repository URL** | https://github.com/faisalmemon353/InvenTree-Project |
| **Licence** | MIT License (`LICENSE` at repository root) |
| **Exact Upstream Baseline Commit Hash** | `b686d7cb64e0b09644d9e9afb0ce4997dfde0c1d` |
| **Upstream Commit Timestamp & Summary** | `2026-11-27 18:36:23 +1100` — `make login page load faster (#13073)` |
| **Baseline Git Tag** | `upstream-b686d7cb64e0b09644d9e9afb0ce4997dfde0c1d` |
| **Technology Stack** | Python 3.13 / Django / Django REST Framework (Backend), React / TypeScript / Mantine UI (Frontend), SQLite / PostgreSQL (Persistent Storage) |
| **Selected Module** | `order` (Purchasing Module — `src/backend/InvenTree/order/`) |

---

## 2. Two Related Workflows in One Module (`order`)

Both workflows operate within InvenTree's **`order` module** (`src/backend/InvenTree/order/models.py`, `serializers.py`, `api.py`, and `status_codes.py`) and interact with the `stock` module when receiving physical inventory.

### Workflow Overview Table

| Workflow | Starting Condition | User Action | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **Workflow 1: Create and Issue (Place) Purchase Order** (`PENDING` → `PLACED`) | 1. An active supplier `Company` (`is_supplier=True`, e.g., *Acme Electronics Ltd*), a purchasable `Part` (*Industrial Microcontroller MCU-32*), and a linked `SupplierPart` (`SKU: ACME-MCU-32`) exist.<br>2. Initial stock balance for `MCU-32` is `0`.<br>3. User is authenticated as **Purchasing Officer** (`purchasing_officer`). | 1. Create a new `PurchaseOrder` (`PO-SQE-0001`) for *Acme Electronics Ltd* via UI or `POST /api/order/po/`.<br>2. Add a `PurchaseOrderLineItem` for `ACME-MCU-32` with `quantity = 10` and `purchase_price = 25.00` via UI or `POST /api/order/po-line/`.<br>3. Issue (place) the order via UI ("Issue Order") or `POST /api/order/po/<id>/issue/`. | 1. `PurchaseOrder` is created in `PENDING (10)` state and transitions to `PLACED (20)` upon issuing.<br>2. `PurchaseOrder.issue_date` is populated with the current date.<br>3. `PurchaseOrderLineItem` records `quantity = 10`, `received = 0`, and `PurchaseOrder.total_price = 250.00`.<br>4. `StockItem` count for `MCU-32` remains `0`. |
| **Workflow 2: Receive Stock Against Placed Purchase Order** (`PLACED` → `COMPLETE`) | 1. `PurchaseOrder` `PO-SQE-0001` exists in `PLACED (20)` state.<br>2. Its `PurchaseOrderLineItem` has `quantity = 10` and `received = 0`.<br>3. Destination `StockLocation` (*Main Warehouse Bay A*) exists.<br>4. User is authenticated as **Purchasing Officer** (`purchasing_officer`). | 1. Submit a partial or full stock receipt against `PO-SQE-0001` via UI ("Receive Items") or `POST /api/order/po/<id>/receive/` specifying `line_item`, `quantity = 10` (or partial `4` then `6`), `location = Main Warehouse Bay A`, and `batch_code = BATCH-2026-01`. | 1. A new `StockItem` record is persisted in *Main Warehouse Bay A* with `quantity = 10` and `status = OK (10)`.<br>2. `PurchaseOrderLineItem.received` updates from `0` to `10` (`remaining() == 0`).<br>3. Because `pending_line_count == 0` and `PURCHASEORDER_AUTO_COMPLETE` is enabled, `PurchaseOrder.status` transitions from `PLACED (20)` to `COMPLETE (30)` and `complete_date` is set.<br>4. Completed order becomes locked (`check_locked() == True`). |

### Shared Records & Cross-Workflow Data Dependencies

| Shared Database Record / Field | Role in Workflow 1 (Create & Issue PO) | Role in Workflow 2 (Receive Stock Against PO) |
| :--- | :--- | :--- |
| **`PurchaseOrder.status`** (`order_purchaseorder.status`) | **Created & Mutated:** Initialized to `PENDING (10)` on creation; mutated to `PLACED (20)` by `place_order()` (`issue_order()`). | **Read & Mutated:** Read by `receive_line_items()` which enforces `self.status == PurchaseOrderStatus.PLACED (20)` before allowing receipt; automatically mutated to `COMPLETE (30)` when all lines reach `received >= quantity`. |
| **`PurchaseOrderLineItem.quantity` & `received`** (`order_purchaseorderlineitem`) | **Created:** `quantity` is written (`10`) and `received` is initialized to `0`. | **Read & Mutated:** `line_item` is locked with `select_for_update()`, validated against `order`, and `line.received` is incremented by the received `quantity` (`0 → 10`). |
| **`StockItem.quantity` & `purchase_order_id`** (`stock_stockitem`) | **Precondition (0 items):** No stock items exist for this PO prior to receipt. | **Created & Linked:** New `StockItem` record(s) are created with `purchase_order = PO`, `location = destination`, and `quantity = supplier_part.base_quantity(received_qty)`, increasing the part's total in-stock balance. |

---

## 3. Functional Requirements (10 Requirements Across Both Workflows)

Every requirement is derived directly from InvenTree's official documentation and verified against the baseline source code in `src/backend/InvenTree/order/`.

### Workflow 1 Functional Requirements (Create & Issue Purchase Order)

* **FR-01 (Purchase Order Creation & Reference Validation):** The system shall allow an authorized user to create a `PurchaseOrder` linked to a valid supplier `Company` (`is_supplier=True`) with a unique `reference` matching `PURCHASEORDER_REFERENCE_PATTERN` (default `PO-{ref:04d}`), initializing `status = PurchaseOrderStatus.PENDING (10)` and `creation_date = current_date()`. *(Source: `order/models.py::PurchaseOrder`, `order/validators.py::validate_purchase_order_reference`)*
* **FR-02 (Order Date & Company-Contact/Address Consistency):** When creating or updating a `PurchaseOrder`, the system shall validate that if both `start_date` and `target_date` are provided, `start_date <= target_date`, and that any specified `contact` or `address` belongs to the selected supplier `Company`. *(Source: `order/models.py::Order.clean`, lines 475–502)*
* **FR-03 (Line Item Creation, Supplier Matching & Positive Quantity):** The system shall allow adding a `PurchaseOrderLineItem` to an open `PurchaseOrder` only if `quantity > 0` and `supplier_part.supplier == purchase_order.supplier`, initializing `received = 0`. *(Source: `order/models.py::PurchaseOrder.add_line_item`, lines 894–971; `order/serializers.py::PurchaseOrderLineItemSerializer`, lines 658–828)*
* **FR-04 (Duplicate Line Item Merging & Total Price Recalculation):** When a `PurchaseOrderLineItem` is added with `merge_items=True` (or `group=True` in `add_line_item`) for a `SupplierPart` that already exists on the same order with matching `target_date` and `destination`, the system shall increment the existing line item's `quantity` rather than creating a duplicate row, and automatically recalculate `PurchaseOrder.total_price` factoring in line `discount` ($0\text{--}100\%$). *(Source: `order/models.py::TotalPriceMixin.calculate_total_price`, lines 197–256; `order/api.py::PurchaseOrderLineItemViewSet.create`, lines 651–704)*
* **FR-05 (Purchase Order Placement / Issuance Transition):** The system shall allow transitioning a `PurchaseOrder` from `PENDING (10)` or `ON_HOLD (25)` to `PLACED (20)` via `place_order()` (`POST /api/order/po/<id>/issue/`), setting `issue_date` to the current date, and shall reject issuing orders from `COMPLETE (30)` or `CANCELLED (40)` states. *(Source: `order/models.py::PurchaseOrder.place_order`, lines 974–994)*

### Workflow 2 Functional Requirements (Receive Stock Against Purchase Order)

* **FR-06 (Placed-Status Precondition for Stock Receipt):** The system shall only accept stock receipts (`receive_line_items` / `POST /api/order/po/<id>/receive/`) when `PurchaseOrder.status == PurchaseOrderStatus.PLACED (20)`, raising a `ValidationError` (`"Lines can only be received against an order marked as 'PLACED'"`) for `PENDING (10)`, `ON_HOLD (25)`, `COMPLETE (30)`, or `CANCELLED (40)` orders. *(Source: `order/models.py::PurchaseOrder.receive_line_items`, lines 1149–1152)*
* **FR-07 (Receipt Quantity, Destination Location & Barcode/Serial Uniqueness Validation):** When receiving stock against a line item, the system shall require a non-empty `items` list, a valid `quantity > 0` for each item, a resolved destination `StockLocation` (from item, request, line item, or order default), and unique `barcode` / `serial_numbers` values. *(Source: `order/serializers.py::PurchaseOrderLineItemReceiveSerializer` & `PurchaseOrderReceiveSerializer`, lines 854–1120)*
* **FR-08 (Partial Receipt & StockItem Creation with Tracking History):** When receiving a quantity less than the remaining ordered quantity (`0 < quantity < line.remaining()`), the system shall create a `StockItem` in the target `StockLocation` with `StockHistoryCode.RECEIVED_AGAINST_PURCHASE_ORDER`, increment `PurchaseOrderLineItem.received` by `quantity`, and keep `PurchaseOrder.status` as `PLACED (20)`. *(Source: `order/models.py::PurchaseOrder.receive_line_items`, lines 1236–1422)*
* **FR-09 (Full Receipt & Automatic Purchase Order Completion):** When receiving stock causes all line items on the `PurchaseOrder` to satisfy `received >= quantity` (`pending_line_count == 0`) and `PURCHASEORDER_AUTO_COMPLETE` is `True`, the system shall automatically transition `PurchaseOrder.status` to `COMPLETE (30)`, record `received_by = user`, and set `complete_date = current_date()`. *(Source: `order/models.py::PurchaseOrder.receive_line_items`, lines 1416–1422)*
* **FR-10 (Post-Receipt Line Deletion Protection & Completed Order Locking):** The system shall reject deleting any `PurchaseOrderLineItem` where `received > 0` (`"Cannot delete line items which have received stock"`), and once a `PurchaseOrder` is in `COMPLETE (30)` state (with `PURCHASEORDER_EDIT_COMPLETED_ORDERS=False`), `check_locked()` shall prevent modifying the order or adding/editing/deleting its line items. *(Source: `order/api.py::PurchaseOrderLineItemViewSet.check_received`, lines 706–730; `order/models.py::Order.save` & `check_locked`, lines 418–452)*

---

## 4. Four Business Rules (Mandatory Rubric Categories)

### BR-01: Boundary / Limit Rule — Order Line & Receipt Quantity and Discount Bounds
* **Rule Statement:**
  1. **Line Item Quantity (`add_line_item` & `PurchaseOrderLineItemSerializer`):** Ordered quantity must be strictly positive. In `PurchaseOrder.add_line_item()`, `quantity` is cast to `int` and must satisfy `quantity >= 1` (`quantity <= 0` raises `ValidationError("Quantity must be greater than zero")`). In `PurchaseOrderLineItemSerializer` and `PurchaseOrderLineItemReceiveSerializer`, `quantity` must satisfy `quantity > 0` (with `max_digits=15, decimal_places=5`, minimum positive step `0.00001`, and standard unit boundary `1`).
  2. **Line Item Discount (`OrderLineItem.discount`):** Discount percentage must satisfy $0 \le \text{discount} \le 100$ (`MinValueValidator(0)`, `MaxValueValidator(100)`).
  3. **Pending vs. Completed Line Threshold (`PurchaseOrderLineItem.is_completed`):** A line item remains pending while $\text{received} < \text{quantity}$ (`remaining = max(quantity - received, 0)`) and becomes completed at the exact boundary $\text{received} = \text{quantity}$ (and remains completed for $\text{received} > \text{quantity}$).
* **3-Point BVA Test Targets:**
  * Integer Line Quantity (`min = 1`): `0` (just below — reject), `1` (at boundary — accept), `2` (just above — accept).
  * Discount Percentage (`min = 0`, `max = 100`): `-0.01` (below min — reject), `0.00` (at min — accept), `0.01` (above min — accept); `99.99` (below max — accept), `100.00` (at max — accept), `100.01` (above max — reject).
  * Receipt Completion Boundary (`ordered_qty = 10`): receive `9` (`received = 9 < 10` → order stays `PLACED`), receive `1` more (`received = 10 == 10` → order auto-completes to `COMPLETE`), or single receipt of `11` (`received = 11 > 10` → order auto-completes to `COMPLETE`).

### BR-02: Multi-Condition Boolean Decision Rule — Stock Receipt Eligibility & Auto-Completion
* **Rule Statement:** A stock receipt operation (`PurchaseOrder.receive_line_items` via `PurchaseOrderReceiveSerializer`) succeeds and auto-completes the Purchase Order according to four Boolean preconditions ($C_1, C_2, C_3, C_4$) and two post-receipt Boolean conditions ($C_5, C_6$):
  * $C_1$: `order.status == PurchaseOrderStatus.PLACED` (`status == 20`)
  * $C_2$: `line_item.order == order` (the line item belongs to the target `PurchaseOrder`)
  * $C_3$: `quantity > 0` (the received quantity is strictly positive)
  * $C_4$: `destination_location is not None` (a valid `StockLocation` is provided directly or inherited from line/order)
  * $C_5$: `PURCHASEORDER_AUTO_COMPLETE == True` (global setting enabled)
  * $C_6$: `order.pending_line_count == 0` (all line items on the order now have `received >= quantity`)
* **Decision Outcomes:**
  * If $\neg C_1 \lor \neg C_2 \lor \neg C_3 \lor \neg C_4$: **Reject Receipt** (`ValidationError`, transaction rolled back, `StockItem` not created, `line.received` unchanged).
  * If $C_1 \land C_2 \land C_3 \land C_4 \land \neg(C_5 \land C_6)$: **Accept Partial Receipt** (`StockItem` created, `line.received` incremented, `order.status` remains `PLACED (20)`).
  * If $C_1 \land C_2 \land C_3 \land C_4 \land C_5 \land C_6$: **Accept Receipt & Auto-Complete Order** (`StockItem` created, `line.received` incremented, `order.status` transitions to `COMPLETE (30)`, `complete_date` set).

### BR-03: State Transition Rule — Purchase Order Lifecycle Finite State Machine (FSM)
* **Rule Statement:** `PurchaseOrder.status` is governed by `@inventree_transition` decorators on `PurchaseOrder` (`src/backend/InvenTree/order/models.py`, lines 973–1079) across states `PENDING (10)`, `PLACED (20)`, `ON_HOLD (25)`, `COMPLETE (30)`, and `CANCELLED (40)`:
  * **Allowed Transitions:**
    1. `PENDING (10) → PLACED (20)` via `place_order()` / `issue` endpoint.
    2. `PENDING (10) → ON_HOLD (25)` via `hold_order()` / `hold` endpoint.
    3. `PENDING (10) → CANCELLED (40)` via `cancel_order()` / `cancel` endpoint.
    4. `ON_HOLD (25) → PLACED (20)` via `place_order()` / `issue` endpoint.
    5. `ON_HOLD (25) → CANCELLED (40)` via `cancel_order()` / `cancel` endpoint.
    6. `PLACED (20) → ON_HOLD (25)` via `hold_order()` / `hold` endpoint.
    7. `PLACED (20) → COMPLETE (30)` via `complete_order()` / `complete` endpoint (or auto-complete on full receipt).
    8. `PLACED (20) → CANCELLED (40)` via `cancel_order()` / `cancel` endpoint.
  * **Disallowed Transitions (Must Be Rejected):**
    * `PENDING (10) → COMPLETE (30)` (cannot complete an unplaced order).
    * `ON_HOLD (25) → COMPLETE (30)` (cannot complete a held order without placing it first).
    * `COMPLETE (30) → PLACED (20)`, `COMPLETE (30) → ON_HOLD (25)`, `COMPLETE (30) → CANCELLED (40)` (terminal state).
    * `CANCELLED (40) → PLACED (20)`, `CANCELLED (40) → ON_HOLD (25)`, `CANCELLED (40) → COMPLETE (30)` (terminal state).
    * Receiving stock (`receive_line_items`) in any state other than `PLACED (20)`.

### BR-04: Supplier-Part Integrity & Role-Based Access Control (RBAC) Rule
* **Rule Statement:**
  1. **Supplier-Part Consistency & Open-Order Constraint:** Adding a `PurchaseOrderLineItem` requires `purchase_order.status in PurchaseOrderStatusGroups.OPEN` (`[10, 20, 25]`) AND `supplier_part.supplier == purchase_order.supplier`. If `purchase_order.status in [30, 40]` or `supplier_part.supplier != purchase_order.supplier`, the operation is rejected with `ValidationError`.
  2. **Role Permission Enforcement:** InvenTree's `RuleSet` RBAC (`users/permissions.py::check_user_permission`) requires `purchase_order` (`can_add`, `can_change`) to create, edit, or transition a `PurchaseOrder` / `PurchaseOrderLineItem`, and `purchase_order` (`can_change`) + `stock` (`can_add`, `can_change`) to receive stock items. A user with only `can_view=True` is permitted `GET` requests (`HTTP 200`) but denied `POST`, `PUT`, `PATCH`, and `DELETE` requests (`HTTP 403 Forbidden`).

---

## 5. Two User Roles with Different Permissions

| Role Name | Username | Password | Group & `RuleSet` Configuration | Allowed Actions in Scope | Denied Actions in Scope (`HTTP 403` / Hidden UI) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Role 1: Purchasing Officer** | `purchasing_officer` | `SQEPurchasingPass123!` | Group: `SQE_Purchasing_Officers`<br>• `purchase_order`: `view=True, add=True, change=True, delete=True`<br>• `stock`: `view=True, add=True, change=True, delete=False`<br>• `stock_location`: `view=True, add=False, change=False, delete=False`<br>• `part`: `view=True, add=False, change=False, delete=False` | • View all POs, line items, parts, suppliers, stock<br>• Create `PurchaseOrder` (`POST /api/order/po/`)<br>• Add/edit/delete unreceived `PurchaseOrderLineItem`<br>• Issue, hold, complete, or cancel PO<br>• Receive stock (`POST /api/order/po/<id>/receive/`) | • Delete `StockItem` records (`stock.can_delete=False`)<br>• Access Admin Center / modify user permissions (`admin=False`) |
| **Role 2: Inventory Viewer** | `inventory_viewer` | `SQEViewerPass123!` | Group: `SQE_Inventory_Viewers`<br>• `purchase_order`: `view=True, add=False, change=False, delete=False`<br>• `stock`: `view=True, add=False, change=False, delete=False`<br>• `stock_location`: `view=True, add=False, change=False, delete=False`<br>• `part`: `view=True, add=False, change=False, delete=False` | • View `PurchaseOrder` list and details (`GET /api/order/po/`)<br>• View `PurchaseOrderLineItem` list (`GET /api/order/po-line/`)<br>• View `StockItem` balances (`GET /api/stock/`) | • Create `PurchaseOrder` (`POST /api/order/po/` → `403`)<br>• Add `PurchaseOrderLineItem` (`POST /api/order/po-line/` → `403`)<br>• Issue/Place PO (`POST /api/order/po/<id>/issue/` → `403`)<br>• Receive stock (`POST /api/order/po/<id>/receive/` → `403`) |

---

## 6. Reproducible Commands for Installation, Running, Seeding & Resetting

All commands below use **Python 3.13** (`py -3.13`) from the repository root (`d:\SQE Project\InvenTree`).

### 6.1 Installation & Database Migration
```powershell
# 1. Create and activate Python 3.13 virtual environment
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install backend dependencies and test tools
pip install --upgrade pip
pip install -r src/backend/requirements.txt
pip install pytest pytest-django pytest-cov coverage mutmut requests pyyaml pip-audit

# 3. Run initial InvenTree database setup and migrations
cd src/backend/InvenTree
python manage.py migrate --noinput
cd ../../..
```

### 6.2 Seeding Synthetic Test Data
```powershell
# Seeds the 2 roles (purchasing_officer, inventory_viewer), suppliers (Acme Electronics Ltd, Beta Components Inc),
# parts (MCU-32, Sensor-X1), supplier parts (ACME-MCU-32, BETA-SEN-X1), stock location (Main Warehouse Bay A),
# and baseline Purchase Orders.
.\.venv\Scripts\python.exe tests/team/scripts/seed_sqe_data.py
```

### 6.3 Resetting Test Data Between Runs
```powershell
# Deterministically wipes all SQE synthetic orders, line items, and received stock items,
# then restores the exact initial baseline state (0 received stock, clean PENDING and PLACED test orders).
.\.venv\Scripts\python.exe tests/team/scripts/reset_sqe_data.py
```

### 6.4 Starting the Application Locally
```powershell
# Start the InvenTree Django web & API server on http://127.0.0.1:8000
cd src/backend/InvenTree
..\..\..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```
