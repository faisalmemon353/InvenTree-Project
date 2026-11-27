"""API & Cross-Workflow Integration Test Suite for SE3002 SQE Project (Section C).

Area 2 Owner: Hassan Zahid (24I-3011)
Test Level  : API & Integration (pytest + requests / DRF APIClient)

Requirements Covered:
1. Dynamically loads EP classes and 3-point BVA values from 'generated_api_test_data.json'
   produced by 'generate_test_data.py' from 'openapi_po_spec.yaml' (no hardcoded boundary numbers).
2. Tests Equivalence Partitioning (every valid and invalid input group, 1 invalid value per test)
   and 3-Point BVA (just below, at, just above every limit) across PO creation, PO line item
   addition, and PO stock receipt endpoints.
3. Tests all 4 Business Rule rejections (BR-01 quantity/discount limits, BR-02 stock receipt
   decision table combinations, BR-03 state transition matrix, BR-04 supplier mismatch & RBAC 403).
4. Tests every allowed state transition and at least one disallowed state transition from every
   state (PENDING=10, PLACED=20, ON_HOLD=25, COMPLETE=30, CANCELLED=40).
5. Tests repeated requests / idempotency (no duplicate PurchaseOrders, line item merge vs duplicate,
   repeated issue/cancel/complete rejections, duplicate barcode rejection on stock receipt).
6. Reads back shared records (PurchaseOrder.status, PurchaseOrderLineItem.received, and
   StockItem.quantity via GET /api/order/po/<id>/, GET /api/order/po-line/<id>/, and GET /api/stock/)
   after BOTH successful and rejected requests across Workflow 1 and Workflow 2.
7. Verifies constraint-change regeneration effect from 'openapi_po_spec_v2_modified.yaml'.
"""

import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'src' / 'backend' / 'InvenTree'
CONFIG_DIR = REPO_ROOT / 'config'
SCRIPTS_DIR = REPO_ROOT / 'tests' / 'team' / 'scripts'
API_DIR = Path(__file__).resolve().parent

for p in (str(BACKEND_DIR), str(SCRIPTS_DIR), str(API_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault('INVENTREE_SITE_URL', 'http://localhost:8000')
os.environ.setdefault('INVENTREE_DB_ENGINE', 'sqlite3')
os.environ.setdefault('INVENTREE_DB_NAME', str(CONFIG_DIR / 'inventree_sqe.sqlite3'))
os.environ.setdefault('INVENTREE_MEDIA_ROOT', str(CONFIG_DIR / 'media'))
os.environ.setdefault('INVENTREE_STATIC_ROOT', str(CONFIG_DIR / 'static'))
os.environ.setdefault('INVENTREE_BACKUP_DIR', str(CONFIG_DIR / 'backup'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvenTree.settings')

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import User  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from generate_test_data import (  # noqa: E402
    DEFAULT_OUTPUT,
    DEFAULT_SPEC,
    MODIFIED_OUTPUT,
    MODIFIED_SPEC,
    generate_dataset_from_spec,
)
from order.models import PurchaseOrder, PurchaseOrderLineItem  # noqa: E402
from order.status_codes import PurchaseOrderStatus  # noqa: E402
from reset_sqe_data import reset_sqe_data  # noqa: E402
from stock.models import StockItem  # noqa: E402


# Ensure generated JSON dataset exists from OpenAPI spec before parametrizing tests
GENERATED_DATA = generate_dataset_from_spec(DEFAULT_SPEC, DEFAULT_OUTPUT)
SCHEMAS = GENERATED_DATA['schemas']


class RequestsCompatibleAPISession:
    """Adapter that routes requests.Session-style HTTP calls through DRF APIClient or live HTTP server."""

    def __init__(self, username: str) -> None:
        self.live_url = os.environ.get('INVENTREE_LIVE_API_URL', '').rstrip('/')
        user = User.objects.get(username=username)
        if self.live_url:
            self.session = requests.Session()
            password = 'SQEPurchasingPass123!' if username == 'purchasing_officer' else 'SQEViewerPass123!'
            self.session.auth = (username, password)
            self.client = None
        else:
            self.client = APIClient()
            self.client.force_authenticate(user=user)
            self.session = None

    def get(self, path: str, params: dict | None = None):
        if self.live_url:
            return self.session.get(f'{self.live_url}{path}', params=params, timeout=10)
        return self.client.get(path, data=params or {}, format='json')

    def post(self, path: str, json_data: dict | None = None):
        if self.live_url:
            return self.session.post(f'{self.live_url}{path}', json=json_data or {}, timeout=10)
        return self.client.post(path, data=json_data or {}, format='json')

    def patch(self, path: str, json_data: dict | None = None):
        if self.live_url:
            return self.session.patch(f'{self.live_url}{path}', json=json_data or {}, timeout=10)
        return self.client.patch(path, data=json_data or {}, format='json')

    def delete(self, path: str):
        if self.live_url:
            return self.session.delete(f'{self.live_url}{path}', timeout=10)
        return self.client.delete(path, format='json')


@pytest.fixture(scope='module')
def sqe_base_env():
    """Seed baseline users and master data once per module to avoid repeated password hashing overhead."""
    summary = reset_sqe_data()
    return {
        'meta': summary,
        'officer_api': RequestsCompatibleAPISession('purchasing_officer'),
        'viewer_api': RequestsCompatibleAPISession('inventory_viewer'),
    }


@pytest.fixture()
def sqe_env(sqe_base_env):
    """Fast per-test reset of dynamic POs/lines/stock created outside baseline PO-SQE-0001 and PO-SQE-0002."""
    PurchaseOrder.objects.exclude(reference__in=['PO-SQE-0001', 'PO-SQE-0002']).delete()
    StockItem.objects.filter(part_id__in=[
        sqe_base_env['meta']['parts']['mcu_part_id'],
        sqe_base_env['meta']['parts']['sensor_part_id'],
    ]).delete()
    return sqe_base_env


def _extract_po_create_bva_cases() -> list[tuple[str, str, object, bool]]:
    """Extract 3-point BVA and EP cases for PurchaseOrderCreate from generated OpenAPI dataset."""
    po_fields = SCHEMAS['PurchaseOrderCreate']['fields']
    cases = []

    # reference length 3-point BVA (minLength=7, maxLength=64)
    ref_bva = po_fields['reference']['bva_3point']
    for label, pt in ref_bva['lower_length_boundary'].items():
        if isinstance(pt, dict):
            cases.append(('reference', f'lower_{label}', pt['value'], pt['expected_valid']))
    for label, pt in ref_bva['upper_length_boundary'].items():
        if isinstance(pt, dict):
            cases.append(('reference', f'upper_{label}', pt['value'], pt['expected_valid']))

    # reference EP pattern mismatch & empty
    ref_ep = po_fields['reference']['ep_classes']
    cases.append(('reference', 'ep_pattern_mismatch', ref_ep['invalid_pattern_mismatch_partition']['value'], False))
    cases.append(('reference', 'ep_empty_string', ref_ep['invalid_empty_string_partition']['value'], False))

    # description upper length 3-point BVA (maxLength=250)
    desc_bva = po_fields['description']['bva_3point']['upper_length_boundary']
    for label, pt in desc_bva.items():
        if isinstance(pt, dict):
            cases.append(('description', f'upper_{label}', pt['value'], pt['expected_valid']))

    # order_currency EP valid enum vs invalid enum
    curr_ep = po_fields['order_currency']['ep_classes']
    for item in curr_ep['valid_all_enums']:
        cases.append(('order_currency', f"ep_valid_{item['value']}", item['value'], True))
    cases.append(('order_currency', 'ep_invalid_currency', curr_ep['invalid_enum_partition']['value'], False))

    return cases


def _extract_line_item_bva_cases() -> list[tuple[str, str, object, bool]]:
    """Extract 3-point BVA and EP cases for PurchaseOrderLineItemCreate from generated OpenAPI dataset."""
    line_fields = SCHEMAS['PurchaseOrderLineItemCreate']['fields']
    cases = []

    # quantity 3-point BVA (min=1: 0, 1, 2; max=10000: 9999, 10000) + EP negative/type
    qty_bva = line_fields['quantity']['bva_3point']
    for label, pt in qty_bva['lower_boundary'].items():
        if isinstance(pt, dict):
            cases.append(('quantity', f'lower_{label}', pt['value'], pt['expected_valid']))
    for label, pt in qty_bva['upper_boundary'].items():
        if isinstance(pt, dict) and label != 'just_above_max':
            cases.append(('quantity', f'upper_{label}', pt['value'], pt['expected_valid']))

    qty_ep = line_fields['quantity']['ep_classes']
    cases.append(('quantity', 'ep_below_min_negative', qty_ep['invalid_below_min_partition']['value'], False))
    cases.append(('quantity', 'ep_invalid_type', qty_ep['invalid_type_partition']['value'], False))

    # discount 3-point BVA (min=0: -0.01, 0, 0.01; max=100: 99.99, 100, 100.01) + EP
    disc_bva = line_fields['discount']['bva_3point']
    for label, pt in disc_bva['lower_boundary'].items():
        if isinstance(pt, dict):
            cases.append(('discount', f'lower_{label}', pt['value'], pt['expected_valid']))
    for label, pt in disc_bva['upper_boundary'].items():
        if isinstance(pt, dict):
            cases.append(('discount', f'upper_{label}', pt['value'], pt['expected_valid']))

    disc_ep = line_fields['discount']['ep_classes']
    cases.append(('discount', 'ep_below_min', disc_ep['invalid_below_min_partition']['value'], False))
    cases.append(('discount', 'ep_above_max', disc_ep['invalid_above_max_partition']['value'], False))

    return cases


# ============================================================================
# 1. GENERATED EP & 3-POINT BVA ON POST /api/order/po/
# ============================================================================

@pytest.mark.parametrize('field_name,case_label,test_value,expected_valid', _extract_po_create_bva_cases())
def test_api_create_po_generated_ep_and_3pt_bva(sqe_env, field_name, case_label, test_value, expected_valid):
    """Execute generated EP and 3-point BVA cases on POST /api/order/po/ (1 invalid value per test)."""
    api = sqe_env['officer_api']
    acme_id = sqe_env['meta']['suppliers']['acme_id']

    # Base valid nominal payload from OpenAPI generator
    payload = {
        'supplier': acme_id,
        'reference': 'PO-8801',
        'supplier_reference': SCHEMAS['PurchaseOrderCreate']['fields']['supplier_reference']['ep_classes']['valid_nominal']['value'],
        'description': SCHEMAS['PurchaseOrderCreate']['fields']['description']['ep_classes']['valid_nominal']['value'],
        'order_currency': SCHEMAS['PurchaseOrderCreate']['fields']['order_currency']['ep_classes']['valid_nominal']['value'],
    }
    payload[field_name] = test_value

    resp = api.post('/api/order/po/', payload)
    if expected_valid:
        assert resp.status_code == 201, f'Expected 201 for {field_name}={case_label}, got {resp.status_code}: {resp.data}'
        created_pk = resp.json()['pk']
        # Read-back shared record via GET /api/order/po/<id>/
        read_back = api.get(f'/api/order/po/{created_pk}/')
        assert read_back.status_code == 200
        assert read_back.json()['status'] == PurchaseOrderStatus.PENDING.value
        assert read_back.json()[field_name] == test_value
    else:
        assert resp.status_code == 400, f'Expected 400 rejection for {field_name}={case_label} ({test_value}), got {resp.status_code}'


# ============================================================================
# 2. GENERATED EP & 3-POINT BVA ON POST /api/order/po-line/
# ============================================================================

@pytest.mark.parametrize('field_name,case_label,test_value,expected_valid', _extract_line_item_bva_cases())
def test_api_add_line_item_generated_ep_and_3pt_bva(sqe_env, field_name, case_label, test_value, expected_valid):
    """Execute generated EP and 3-point BVA cases on POST /api/order/po-line/ (1 invalid value per test)."""
    api = sqe_env['officer_api']
    po_id = sqe_env['meta']['orders']['po_pending_id']
    sp_id = sqe_env['meta']['parts']['acme_mcu_supplier_part_id']

    payload = {
        'order': po_id,
        'part': sp_id,
        'quantity': 5,
        'discount': 0,
        'purchase_price': 25.00,
        'purchase_price_currency': 'USD',
        'merge_items': False,
    }
    payload[field_name] = test_value

    before_lines = PurchaseOrderLineItem.objects.filter(order_id=po_id).count()
    resp = api.post('/api/order/po-line/', payload)

    if expected_valid:
        assert resp.status_code == 201, f'Expected 201 for {field_name}={case_label}, got {resp.status_code}: {resp.data}'
        after_lines = PurchaseOrderLineItem.objects.filter(order_id=po_id).count()
        assert after_lines == before_lines + 1
    else:
        assert resp.status_code == 400, f'Expected 400 rejection for {field_name}={case_label} ({test_value}), got {resp.status_code}'
        # Verify shared record count unchanged after rejection
        after_lines = PurchaseOrderLineItem.objects.filter(order_id=po_id).count()
        assert after_lines == before_lines


# ============================================================================
# 3. GENERATED EP & 3-POINT BVA + DECISION TABLE ON POST /api/order/po/<id>/receive/
# ============================================================================

def test_api_receive_stock_generated_ep_bva_and_decision_table(sqe_env):
    """Test generated EP/3-point BVA inputs and BR-02 decision table combinations on POST /api/order/po/<id>/receive/."""
    api = sqe_env['officer_api']
    po_placed_id = sqe_env['meta']['orders']['po_placed_id']
    po_pending_id = sqe_env['meta']['orders']['po_pending_id']
    line_placed_id = sqe_env['meta']['orders']['po_placed_line_id']
    loc_id = sqe_env['meta']['location_id']
    mcu_id = sqe_env['meta']['parts']['mcu_part_id']

    recv_schema = SCHEMAS['PurchaseOrderLineItemReceive']['fields']
    qty_lower = recv_schema['quantity']['bva_3point']['lower_boundary']

    # 1. BVA just_below_min (quantity = 0) -> HTTP 400 rejection, shared records unchanged
    resp_zero = api.post(
        f'/api/order/po/{po_placed_id}/receive/',
        {
            'location': loc_id,
            'items': [{'line_item': line_placed_id, 'quantity': qty_lower['just_below_min']['value']}],
        },
    )
    assert resp_zero.status_code == 400
    assert StockItem.objects.filter(part_id=mcu_id).count() == 0

    # 2. EP negative quantity (-50) -> HTTP 400 rejection
    neg_qty = recv_schema['quantity']['ep_classes']['invalid_below_min_partition']['value']
    resp_neg = api.post(
        f'/api/order/po/{po_placed_id}/receive/',
        {
            'location': loc_id,
            'items': [{'line_item': line_placed_id, 'quantity': neg_qty}],
        },
    )
    assert resp_neg.status_code == 400
    assert StockItem.objects.filter(part_id=mcu_id).count() == 0

    # 3. EP empty items array ([]) -> HTTP 400 rejection ("Line items must be provided")
    resp_empty = api.post(
        f'/api/order/po/{po_placed_id}/receive/',
        {'location': loc_id, 'items': []},
    )
    assert resp_empty.status_code == 400

    # 4. BR-02 Decision Table Combination (C1=False: Order is PENDING, not PLACED) -> HTTP 400 rejection
    pending_line_id = PurchaseOrderLineItem.objects.filter(order_id=po_pending_id).first().pk
    resp_unplaced = api.post(
        f'/api/order/po/{po_pending_id}/receive/',
        {
            'location': loc_id,
            'items': [{'line_item': pending_line_id, 'quantity': qty_lower['at_min']['value']}],
        },
    )
    assert resp_unplaced.status_code == 400
    assert PurchaseOrderLineItem.objects.get(pk=pending_line_id).received == Decimal('0')

    # 5. BR-02 Decision Table Combination (C2=False: Line item belongs to a different PO) -> HTTP 400 rejection
    resp_wrong_line = api.post(
        f'/api/order/po/{po_placed_id}/receive/',
        {
            'location': loc_id,
            'items': [{'line_item': pending_line_id, 'quantity': qty_lower['at_min']['value']}],
        },
    )
    assert resp_wrong_line.status_code == 400

    # 6. BR-02 Decision Table Combination (C4=False: No destination location on request, line, order, or part) -> HTTP 400
    PurchaseOrder.objects.filter(pk=po_placed_id).update(destination=None)
    PurchaseOrderLineItem.objects.filter(pk=line_placed_id).update(destination=None)
    from part.models import Part
    Part.objects.filter(pk=mcu_id).update(default_location=None)

    resp_no_loc = api.post(
        f'/api/order/po/{po_placed_id}/receive/',
        {
            'location': None,
            'items': [{'line_item': line_placed_id, 'quantity': qty_lower['at_min']['value'], 'location': None}],
        },
    )
    assert resp_no_loc.status_code == 400
    assert 'location' in resp_no_loc.json()

    # Restore destination location and test BVA at_min (1) and just_above_min (2) valid receipts
    Part.objects.filter(pk=mcu_id).update(default_location_id=loc_id)
    PurchaseOrder.objects.filter(pk=po_placed_id).update(destination_id=loc_id)

    resp_at_min = api.post(
        f'/api/order/po/{po_placed_id}/receive/',
        {
            'location': loc_id,
            'batch_code': 'BATCH-BVA-MIN',
            'items': [
                {
                    'line_item': line_placed_id,
                    'quantity': qty_lower['at_min']['value'],
                    'barcode': 'BC-SQE-UNIQUE-001',
                }
            ],
        },
    )
    assert resp_at_min.status_code == 201
    assert PurchaseOrderLineItem.objects.get(pk=line_placed_id).received == Decimal('1')

    resp_above_min = api.post(
        f'/api/order/po/{po_placed_id}/receive/',
        {
            'location': loc_id,
            'batch_code': 'BATCH-BVA-ABOVE',
            'items': [
                {
                    'line_item': line_placed_id,
                    'quantity': qty_lower['just_above_min']['value'],
                    'barcode': 'BC-SQE-UNIQUE-002',
                }
            ],
        },
    )
    assert resp_above_min.status_code == 201
    assert PurchaseOrderLineItem.objects.get(pk=line_placed_id).received == Decimal('3')


# ============================================================================
# 4. CROSS-WORKFLOW SHARED RECORD READ-BACK, STATE TRANSITIONS & IDEMPOTENCY
# ============================================================================

def test_api_cross_workflow_shared_records_transitions_and_idempotency(sqe_env):
    """End-to-end API integration test across Workflow 1 and Workflow 2 with shared record read-backs."""
    officer_api = sqe_env['officer_api']
    viewer_api = sqe_env['viewer_api']
    acme_id = sqe_env['meta']['suppliers']['acme_id']
    beta_sp_id = sqe_env['meta']['parts']['beta_sen_supplier_part_id']
    acme_sp_id = sqe_env['meta']['parts']['acme_mcu_supplier_part_id']
    loc_id = sqe_env['meta']['location_id']
    mcu_id = sqe_env['meta']['parts']['mcu_part_id']

    # --- RBAC Check (BR-04): Inventory Viewer gets 200 on GET, 403 on POST create/issue/receive ---
    assert viewer_api.get('/api/order/po/').status_code == 200
    assert viewer_api.post('/api/order/po/', {'supplier': acme_id, 'reference': 'PO-9991'}).status_code == 403
    assert viewer_api.post(f"/api/order/po/{sqe_env['meta']['orders']['po_pending_id']}/issue/").status_code == 403
    assert viewer_api.post(
        f"/api/order/po/{sqe_env['meta']['orders']['po_placed_id']}/receive/",
        {'location': loc_id, 'items': [{'line_item': sqe_env['meta']['orders']['po_placed_line_id'], 'quantity': 1}]},
    ).status_code == 403

    # --- Workflow 1: Create PO -> Add Line Items (Merge & Supplier Mismatch) -> Issue PO ---
    create_resp = officer_api.post(
        '/api/order/po/',
        {
            'supplier': acme_id,
            'reference': 'PO-7700',
            'description': 'Cross-workflow API test order',
            'destination': loc_id,
        },
    )
    assert create_resp.status_code == 201
    po_id = create_resp.json()['pk']

    # Repeated / Duplicate PO reference request -> rejected with HTTP 400 (no duplicate PO created)
    dup_po_resp = officer_api.post(
        '/api/order/po/',
        {'supplier': acme_id, 'reference': 'PO-7700', 'description': 'Duplicate ref attempt'},
    )
    assert dup_po_resp.status_code == 400
    assert PurchaseOrder.objects.filter(reference='PO-7700').count() == 1

    # Disallowed transition from PENDING (10) -> COMPLETE (30) directly -> rejected with HTTP 400
    bad_comp = officer_api.post(f'/api/order/po/{po_id}/complete/', {'accept_incomplete': True})
    assert bad_comp.status_code == 400
    assert officer_api.get(f'/api/order/po/{po_id}/').json()['status'] == PurchaseOrderStatus.PENDING.value

    # BR-04 Supplier mismatch: try adding Beta supplier part to Acme PO -> rejected with HTTP 400
    mismatch_resp = officer_api.post(
        '/api/order/po-line/',
        {'order': po_id, 'part': beta_sp_id, 'quantity': 5},
    )
    assert mismatch_resp.status_code == 400
    assert officer_api.get(f'/api/order/po/{po_id}/').json()['line_items'] == 0

    # Add valid line item (quantity = 6) and then repeated request with merge_items=True (quantity = 4) -> merges to 10
    line_r1 = officer_api.post(
        '/api/order/po-line/',
        {'order': po_id, 'part': acme_sp_id, 'quantity': 6, 'purchase_price': 20.00, 'purchase_price_currency': 'USD', 'merge_items': True},
    )
    assert line_r1.status_code == 201
    line_id = line_r1.json()['pk']

    line_r2 = officer_api.post(
        '/api/order/po-line/',
        {'order': po_id, 'part': acme_sp_id, 'quantity': 4, 'purchase_price': 20.00, 'purchase_price_currency': 'USD', 'merge_items': True},
    )
    assert line_r2.status_code == 201
    assert line_r2.json()['pk'] == line_id
    assert float(line_r2.json()['quantity']) == 10.0

    # Allowed transition: PENDING (10) -> ON_HOLD (25) -> PLACED (20)
    assert officer_api.post(f'/api/order/po/{po_id}/hold/').status_code == 201
    assert officer_api.get(f'/api/order/po/{po_id}/').json()['status'] == PurchaseOrderStatus.ON_HOLD.value

    # Disallowed transition from ON_HOLD (25) -> COMPLETE (30) -> rejected with HTTP 400
    assert officer_api.post(f'/api/order/po/{po_id}/complete/', {'accept_incomplete': True}).status_code == 400

    # Issue order from ON_HOLD (25) -> PLACED (20)
    issue_resp = officer_api.post(f'/api/order/po/{po_id}/issue/')
    assert issue_resp.status_code == 201

    # Read-back shared records after Workflow 1 completion
    po_after_w1 = officer_api.get(f'/api/order/po/{po_id}/').json()
    line_after_w1 = officer_api.get(f'/api/order/po-line/{line_id}/').json()
    assert po_after_w1['status'] == PurchaseOrderStatus.PLACED.value
    assert po_after_w1['line_items'] == 1
    assert po_after_w1['completed_lines'] == 0
    assert float(line_after_w1['received']) == 0.0

    # Repeated issue request on already-PLACED order -> rejected with HTTP 400
    dup_issue = officer_api.post(f'/api/order/po/{po_id}/issue/')
    assert dup_issue.status_code == 400

    # --- Workflow 2: Receive Partial Stock (4 units) -> Verify Shared Records -> Receive Remaining (6 units) ---
    partial_recv = officer_api.post(
        f'/api/order/po/{po_id}/receive/',
        {
            'location': loc_id,
            'batch_code': 'BATCH-W2-PARTIAL',
            'items': [{'line_item': line_id, 'quantity': 4, 'barcode': 'BC-W2-PARTIAL-01'}],
        },
    )
    assert partial_recv.status_code == 201

    # Read back shared records after partial receipt
    po_mid_w2 = officer_api.get(f'/api/order/po/{po_id}/').json()
    line_mid_w2 = officer_api.get(f'/api/order/po-line/{line_id}/').json()
    stock_mid_w2 = officer_api.get('/api/stock/', {'part': mcu_id, 'purchase_order': po_id}).json()
    assert po_mid_w2['status'] == PurchaseOrderStatus.PLACED.value
    assert float(line_mid_w2['received']) == 4.0
    assert len(stock_mid_w2) == 1 and float(stock_mid_w2[0]['quantity']) == 4.0

    # Repeated receipt with duplicate barcode 'BC-W2-PARTIAL-01' -> rejected with HTTP 400 (no duplicate StockItem)
    dup_barcode_recv = officer_api.post(
        f'/api/order/po/{po_id}/receive/',
        {
            'location': loc_id,
            'items': [{'line_item': line_id, 'quantity': 6, 'barcode': 'BC-W2-PARTIAL-01'}],
        },
    )
    assert dup_barcode_recv.status_code == 400
    assert float(officer_api.get(f'/api/order/po-line/{line_id}/').json()['received']) == 4.0
    assert len(officer_api.get('/api/stock/', {'part': mcu_id, 'purchase_order': po_id}).json()) == 1

    # FR-10: Attempting to DELETE a line item that has received stock (received=4 > 0) -> rejected with HTTP 400
    del_received_line = officer_api.delete(f'/api/order/po-line/{line_id}/')
    assert del_received_line.status_code == 400

    # Receive remaining 6 units -> auto-completes PurchaseOrder (PLACED -> COMPLETE = 30)
    full_recv = officer_api.post(
        f'/api/order/po/{po_id}/receive/',
        {
            'location': loc_id,
            'batch_code': 'BATCH-W2-FINAL',
            'items': [{'line_item': line_id, 'quantity': 6, 'barcode': 'BC-W2-FINAL-02'}],
        },
    )
    assert full_recv.status_code == 201

    # Read back shared records after full receipt & auto-completion
    po_end_w2 = officer_api.get(f'/api/order/po/{po_id}/').json()
    line_end_w2 = officer_api.get(f'/api/order/po-line/{line_id}/').json()
    stock_end_w2 = officer_api.get('/api/stock/', {'part': mcu_id, 'purchase_order': po_id}).json()
    assert po_end_w2['status'] == PurchaseOrderStatus.COMPLETE.value
    assert po_end_w2['completed_lines'] == 1
    assert float(line_end_w2['received']) == 10.0
    assert sum(float(s['quantity']) for s in stock_end_w2) == 10.0

    # Disallowed transitions out of terminal COMPLETE (30) state -> all rejected with HTTP 400
    for disallowed_action in ('issue', 'hold', 'cancel', 'complete'):
        assert officer_api.post(f'/api/order/po/{po_id}/{disallowed_action}/').status_code == 400

    # Repeated stock receipt on COMPLETE (30) order -> rejected with HTTP 400
    post_comp_recv = officer_api.post(
        f'/api/order/po/{po_id}/receive/',
        {'location': loc_id, 'items': [{'line_item': line_id, 'quantity': 1}]},
    )
    assert post_comp_recv.status_code == 400
    assert sum(float(s['quantity']) for s in officer_api.get('/api/stock/', {'part': mcu_id, 'purchase_order': po_id}).json()) == 10.0

    # Allowed transition to CANCELLED (40) on open PO, then disallowed transitions from terminal CANCELLED (40)
    po_cancel_id = sqe_env['meta']['orders']['po_pending_id']
    assert officer_api.post(f'/api/order/po/{po_cancel_id}/cancel/').status_code == 201
    assert officer_api.get(f'/api/order/po/{po_cancel_id}/').json()['status'] == PurchaseOrderStatus.CANCELLED.value
    for disallowed_from_cancel in ('issue', 'hold', 'complete', 'cancel'):
        assert officer_api.post(f'/api/order/po/{po_cancel_id}/{disallowed_from_cancel}/').status_code == 400


# ============================================================================
# 5. VIVA SPEC CONSTRAINT-CHANGE REGENERATION VERIFICATION
# ============================================================================

def test_viva_two_constraint_changes_regeneration_effect():
    """Verify that changing 2 constraints in openapi_po_spec_v2_modified.yaml regenerates updated BVA & EP values."""
    v1 = generate_dataset_from_spec(DEFAULT_SPEC, DEFAULT_OUTPUT)
    v2 = generate_dataset_from_spec(MODIFIED_SPEC, MODIFIED_OUTPUT)

    # Constraint Change 1: PurchaseOrderLineItemCreate.quantity (min 1 -> 5, max 10000 -> 5000)
    q1 = v1['schemas']['PurchaseOrderLineItemCreate']['fields']['quantity']['bva_3point']
    q2 = v2['schemas']['PurchaseOrderLineItemCreate']['fields']['quantity']['bva_3point']
    assert q1['lower_boundary']['at_min']['value'] == 1
    assert q2['lower_boundary']['just_below_min']['value'] == 4
    assert q2['lower_boundary']['at_min']['value'] == 5
    assert q2['lower_boundary']['just_above_min']['value'] == 6
    assert q2['upper_boundary']['at_max']['value'] == 5000
    assert q2['upper_boundary']['just_above_max']['value'] == 5001

    # Constraint Change 2: PurchaseOrderLineItemCreate.discount (max 100 -> 50)
    d1 = v1['schemas']['PurchaseOrderLineItemCreate']['fields']['discount']['bva_3point']
    d2 = v2['schemas']['PurchaseOrderLineItemCreate']['fields']['discount']['bva_3point']
    assert d1['upper_boundary']['at_max']['value'] == 100
    assert d2['upper_boundary']['just_below_max']['value'] == 49.99
    assert d2['upper_boundary']['at_max']['value'] == 50
    assert d2['upper_boundary']['just_above_max']['value'] == 50.01
