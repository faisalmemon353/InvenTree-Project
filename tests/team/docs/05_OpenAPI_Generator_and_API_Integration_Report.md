# Section 2.3: OpenAPI Automated Test Data Generation & API / Integration Testing Report

**Course:** SE3002 — Software Quality Engineering (Final Project, Fall 2026)  
**Section:** C  
**Area 2 Owner:** Hassan Zahid (`24I-3011` / `Hassan-Zahid110`)  
**Feature Branch:** `feat/hassan-openapi-and-api-tests`  
**Deliverables:**
* OpenAPI 3.0.3 Baseline Specification: `tests/team/api/openapi_po_spec.yaml`
* OpenAPI 3.0.3 Modified Specification (2 Constraint Changes): `tests/team/api/openapi_po_spec_v2_modified.yaml`
* Automated EP & 3-Point BVA Generator Script: `tests/team/api/generate_test_data.py`
* Generated Test Datasets: `tests/team/api/generated_api_test_data.json` & `generated_api_test_data_v2_modified.json`
* API & Cross-Workflow Integration Test Suite: `tests/team/api/test_po_workflows_api.py`

---

## 1. OpenAPI Specification & Automated Test Data Generator Architecture

We authored an OpenAPI 3.0.3 specification (`tests/team/api/openapi_po_spec.yaml`) modeling the exact request schemas, data types, domain boundaries (`minimum`, `maximum`, `minLength`, `maxLength`, `pattern`, `enum`, `minItems`, `maxItems`), and HTTP response codes for all endpoints in **Workflow 1 (Create & Issue Purchase Order)** and **Workflow 2 (Receive Stock Against Placed Purchase Order)**:
1. `POST /api/order/po/` & `GET /api/order/po/{id}/` (`PurchaseOrderCreate`)
2. `POST /api/order/po-line/` & `DELETE /api/order/po-line/{id}/` (`PurchaseOrderLineItemCreate`)
3. `POST /api/order/po/{id}/issue/`, `/hold/`, `/complete/`, `/cancel/` (`PurchaseOrderCompleteRequest`)
4. `POST /api/order/po/{id}/receive/` (`PurchaseOrderReceiveRequest` & `PurchaseOrderLineItemReceive`)
5. `GET /api/stock/` (Stock balance read-back verification)

### 1.1 Automated EP & 3-Point BVA Generation Rules (`generate_test_data.py`)
`generate_test_data.py` parses the OpenAPI YAML AST dynamically and outputs **56 Equivalence Partitions** and **99 3-Point BVA Boundary Cases** across the 5 component schemas:
* **Numeric Fields (`integer` / `number` with step $\delta$):**
  * **Lower 3-Point BVA:** `just_below_min` ($\min - \delta$, Invalid), `at_min` ($\min$, Valid), `just_above_min` ($\min + \delta$, Valid).
  * **Upper 3-Point BVA:** `just_below_max` ($\max - \delta$, Valid), `at_max` ($\max$, Valid), `just_above_max` ($\max + \delta$, Invalid).
  * **EP Classes:** `valid_nominal` ($\frac{\min + \max}{2}$), `invalid_below_min_partition` ($\min - 50\delta$), `invalid_above_max_partition` ($\max + 500\delta$), `invalid_type_partition` (`"INVALID_NUMERIC_STRING"`).
* **String Fields (`minLength`, `maxLength`, `pattern`, `enum`):**
  * **Lower Length 3-Point BVA:** length $\min - 1$ (Invalid), length $\min$ (Valid), length $\min + 1$ (Valid).
  * **Upper Length 3-Point BVA:** length $\max - 1$ (Valid), length $\max$ (Valid), length $\max + 1$ (Invalid).
  * **EP Classes:** `valid_nominal`, `invalid_empty_string_partition` (`""`), `invalid_over_max_length_partition` ($\max + 25$), `invalid_pattern_mismatch_partition` (`"INVALID_REF_FORMAT_###"`).

---

## 2. Two Constraint Changes & Regeneration Demonstration (Viva Readiness)

Per the rubric requirement (*"Change two constraints, regenerate and show the effect. Expect an updated spec in the viva"*), `openapi_po_spec_v2_modified.yaml` modifies two business constraints on `PurchaseOrderLineItemCreate` and regenerates `generated_api_test_data_v2_modified.json` via `python tests/team/api/generate_test_data.py --compare-v2`:

| Constraint Changed | v1 Baseline (`openapi_po_spec.yaml`) | v2 Modified (`openapi_po_spec_v2_modified.yaml`) | Effect on Generated EP & 3-Point BVA Values |
| :--- | :--- | :--- | :--- |
| **1. `PurchaseOrderLineItemCreate.quantity`** (Minimum Order Quantity & Max Cap) | `minimum: 1`, `maximum: 10000` | `minimum: 5`, `maximum: 5000` | • **Lower 3-pt BVA shifts:** `(0 [Reject], 1 [Accept], 2 [Accept])` $\rightarrow$ **`(4 [Reject], 5 [Accept], 6 [Accept])`**<br>• **Upper 3-pt BVA shifts:** `(9999 [Accept], 10000 [Accept], 10001 [Reject])` $\rightarrow$ **`(4999 [Accept], 5000 [Accept], 5001 [Reject])`**<br>• **Nominal EP shifts:** `5000` $\rightarrow$ **`2502`** |
| **2. `PurchaseOrderLineItemCreate.discount`** (Maximum Discount Cap) | `minimum: 0`, `maximum: 100` | `minimum: 0`, `maximum: 50` | • **Upper 3-pt BVA shifts:** `(99.99 [Accept], 100.00 [Accept], 100.01 [Reject])` $\rightarrow$ **`(49.99 [Accept], 50.00 [Accept], 50.01 [Reject])`**<br>• **Nominal EP shifts:** `50.00` $\rightarrow$ **`25.00`** |

---

## 3. API & Cross-Workflow Integration Test Coverage Summary

All **31 executable API & integration test cases** in `tests/team/api/test_po_workflows_api.py` pass against InvenTree's REST API:

| Test Category | Endpoints Tested | Cases Executed | Key Assertions & Cross-Workflow Read-Backs |
| :--- | :--- | :---: | :--- |
| **Generated EP & 3-Point BVA on PO Creation** | `POST /api/order/po/`, `GET /api/order/po/{id}/` | **15** | Tests `reference` 3-pt BVA (`len=6` rejected `400`, `len=7,8,63,64` accepted `201`, `len=65` rejected `400`), pattern mismatch, `description` max length BVA (`249, 250` accepted, `251` rejected), and `order_currency` valid/invalid enums. Reads back created PO via `GET`. |
| **Generated EP & 3-Point BVA on Line Item Creation** | `POST /api/order/po-line/` | **13** | Tests `quantity` 3-pt BVA (`0` rejected, `1, 2, 9999, 10000` accepted, `-49` & string rejected) and `discount` 3-pt BVA (`-0.01` rejected, `0.00, 0.01, 99.99, 100.00` accepted, `100.01` rejected). Verifies `PurchaseOrderLineItem` count is unchanged after every `400` rejection. |
| **Generated EP/BVA & BR-02 Decision Table on Stock Receipt** | `POST /api/order/po/{id}/receive/` | **1** *(8 sub-cases)* | Tests `quantity=0`, `quantity=-49`, empty `items=[]`, unplaced `PENDING` order ($C_1=F$), mismatched line item ($C_2=F$), missing destination location ($C_4=F$), and valid `at_min=1` and `just_above_min=2` receipts. |
| **Cross-Workflow Integration, State Matrix, RBAC & Idempotency** | `/api/order/po/`, `/po-line/`, `/issue/`, `/hold/`, `/complete/`, `/cancel/`, `/receive/`, `/api/stock/` | **1** *(full E2E API lifecycle)* | • **RBAC (`BR-04`):** `inventory_viewer` gets `200` on `GET` and `403` on `POST` create/issue/receive.<br>• **Idempotency / No Duplicates:** Duplicate PO reference rejected (`400`); duplicate line item with `merge_items=True` merges `6+4=10` into 1 row; duplicate `/issue/` rejected (`400`); duplicate `barcode` on `/receive/` rejected (`400`).<br>• **Cross-Workflow Read-Back:** Reads back `PurchaseOrder.status` (`10 → 25 → 20 → 30`), `PurchaseOrderLineItem.received` (`0 → 4 → 10`), and `StockItem.quantity` (`0 → 4 → 10`) after every valid and rejected request. |
| **Viva Constraint-Change Regeneration Test** | `generate_test_data.py` (`v1` vs `v2`) | **1** | Verifies programmatic regeneration of 3-point BVA values after changing 2 OpenAPI constraints. |

---

## 4. Documented Endpoint Weaknesses Discovered During API Testing

Per the rubric requirement (*"Report endpoint weaknesses"*), our systematic EP, 3-point BVA, and state transition testing revealed three concrete weaknesses in InvenTree's upstream `order` REST API endpoints:

1. **Endpoint Weakness `EW-01` (Misleading DRF Field Constraint vs. Custom Validator on `quantity`):**
   * **Affected Endpoint & Source:** `POST /api/order/po-line/` (`order/serializers.py:656` `PurchaseOrderLineItemSerializer.quantity = serializers.FloatField(min_value=0, required=True)`) and `POST /api/order/po/{id}/receive/` (`order/serializers.py:890` `min_value=Decimal(0)`).
   * **Finding:** The DRF serializer field declaration sets `min_value=0` (which exports `minimum: 0` in auto-generated DRF Spectacular schemas), even though the custom validator `validate_quantity()` at lines 660 and 895 immediately rejects `0` with `"Quantity must be greater than zero"`. Additionally, there is no upper-bound validator on `PurchaseOrderLineItemSerializer.quantity`, allowing arbitrarily large floats (`1e12`) unless constrained by the OpenAPI schema.
   * **Linked Risk:** `PR-02` (Boundary / Financial Integrity).

2. **Endpoint Weakness `EW-02` (Unrestricted Over-Receiving on `POST /api/order/po/{id}/receive/`):**
   * **Affected Endpoint & Source:** `POST /api/order/po/{id}/receive/` (`order/models.py:1237` `line.received += quantity`).
   * **Finding:** Upstream `PurchaseOrderReceiveSerializer` and `PurchaseOrder.receive_line_items()` check `quantity > 0` but do **not** enforce an upper bound comparing `line.received + quantity` against `line.quantity` (nor provide an `allow_over_receive` guard flag). A warehouse client sending `quantity = 1000` against an ordered line of `10` silently creates a `StockItem` of `1000` units and auto-completes the Purchase Order. Our server-side business rule `execute_receive_purchase_order_line()` in `order/po_business_rules.py` remedies this by enforcing `new_received <= line.quantity` unless `allow_over_receive=True`.
   * **Linked Risk:** `PR-02` & `PR-03` (Inventory Ledger Divergence).

3. **Endpoint Weakness `EW-03` (Non-Standard `HTTP 201 Created` Status Code on FSM State-Transition Endpoints):**
   * **Affected Endpoints & Source:** `POST /api/order/po/{id}/issue/`, `/hold/`, `/complete/`, `/cancel/` (`order/api.py:414–423` `transition_options = {'place_order': {'name': 'issue', 'return_code': 201}, ...}`).
   * **Finding:** Even though these endpoints mutate the `status` field of an existing `PurchaseOrder` resource without creating a new resource URI (which under RFC 9110 REST semantics should return `HTTP 200 OK`), they return `HTTP 201 Created` (acknowledged in upstream code comment `# TODO @matmair remove legacy return codes`).
   * **Linked Risk:** `PR-01` (API Contract Consistency).
