"""White-Box Unit Test Suite for SE3002 SQE Project (Section C) — Faisal (24I-3032).

Targets 100% statement and branch coverage across:
- src/backend/InvenTree/order/po_business_rules.py
- src/backend/InvenTree/order/status_codes.py
- src/backend/InvenTree/order/validators.py

Covers:
1. All 4 Business Rules (BR-01 Boundary, BR-02 Multi-Boolean Decision, BR-03 State Transition FSM, BR-04 RBAC & Supplier Match).
2. Complete Multiple Condition Coverage (MCC) truth tables (8-row and 16-row tables) and explicit MC/DC independence pairs.
3. 3-Point Boundary Value Analysis (just below, at, just above every boundary) and Equivalence Partitioning (1 invalid value per test).
4. State Transition Matrix (every allowed transition and disallowed transitions from every state).
5. End-to-end model execution for Workflow 1 (Issue PO) and Workflow 2 (Receive Stock & Auto-Complete).
"""

import itertools
import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'src' / 'backend' / 'InvenTree'
CONFIG_DIR = REPO_ROOT / 'config'
SCRIPTS_DIR = REPO_ROOT / 'tests' / 'team' / 'scripts'
for p in (str(BACKEND_DIR), str(SCRIPTS_DIR)):
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
from django.core.exceptions import PermissionDenied, ValidationError  # noqa: E402
from djmoney.money import Money  # noqa: E402

from common.settings import set_global_setting  # noqa: E402
from company.models import Company, SupplierPart  # noqa: E402
from order import po_business_rules, status_codes, validators  # noqa: E402
from order.models import PurchaseOrder, PurchaseOrderLineItem  # noqa: E402
from order.status_codes import PurchaseOrderStatus  # noqa: E402
from seed_sqe_data import seed_sqe_data  # noqa: E402
from stock.models import StockItem, StockLocation  # noqa: E402


# ============================================================================
# 1. BR-01: 3-POINT BOUNDARY VALUE ANALYSIS & EQUIVALENCE PARTITIONING
# ============================================================================

@pytest.mark.parametrize(
    'qty,discount,expected_qty,expected_disc',
    [
        # Quantity lower boundary (min = 1): at (1), just above (2), nominal (500)
        (1, 0, Decimal('1'), Decimal('0')),
        (2, 0, Decimal('2'), Decimal('0')),
        (500, 15, Decimal('500'), Decimal('15')),
        # Quantity upper boundary (max = 10000): just below (9999), at (10000)
        (9999, 0, Decimal('9999'), Decimal('0')),
        (10000, 0, Decimal('10000'), Decimal('0')),
        # Discount lower boundary (min = 0): at (0), just above (0.01)
        (10, Decimal('0.00'), Decimal('10'), Decimal('0.00')),
        (10, Decimal('0.01'), Decimal('10'), Decimal('0.01')),
        # Discount upper boundary (max = 100): just below (99.99), at (100.00)
        (10, Decimal('99.99'), Decimal('10'), Decimal('99.99')),
        (10, Decimal('100.00'), Decimal('10'), Decimal('100.00')),
    ],
)
def test_br01_valid_bva_and_ep_limits(qty, discount, expected_qty, expected_disc):
    """Test BR-01 valid Equivalence Partitions and 3-point BVA valid boundary points."""
    q, d = po_business_rules.validate_line_item_limits(qty, discount)
    assert q == expected_qty
    assert d == expected_disc


@pytest.mark.parametrize(
    'invalid_qty,valid_discount,err_field,err_substring',
    [
        # Quantity just below lower limit (0) and negative EP (-5)
        (0, 0, 'quantity', 'at least 1'),
        (Decimal('0.99'), 0, 'quantity', 'at least 1'),
        (-5, 0, 'quantity', 'at least 1'),
        # Quantity just above upper limit (10001) and extreme EP (50000)
        (10001, 0, 'quantity', 'cannot exceed 10000'),
        (Decimal('10000.01'), 0, 'quantity', 'cannot exceed 10000'),
        (50000, 0, 'quantity', 'cannot exceed 10000'),
    ],
)
def test_br01_invalid_quantity_bva_and_ep(invalid_qty, valid_discount, err_field, err_substring):
    """Test BR-01 invalid quantity boundaries (one invalid input value per test)."""
    with pytest.raises(ValidationError) as exc_info:
        po_business_rules.validate_line_item_limits(invalid_qty, valid_discount)
    assert err_field in exc_info.value.message_dict
    assert err_substring in exc_info.value.message_dict[err_field][0]


@pytest.mark.parametrize(
    'valid_qty,invalid_discount,err_field,err_substring',
    [
        # Discount just below lower limit (-0.01) and negative EP (-20)
        (10, Decimal('-0.01'), 'discount', 'less than 0%'),
        (10, -20, 'discount', 'less than 0%'),
        # Discount just above upper limit (100.01) and extreme EP (150)
        (10, Decimal('100.01'), 'discount', 'cannot exceed 100%'),
        (10, 150, 'discount', 'cannot exceed 100%'),
    ],
)
def test_br01_invalid_discount_bva_and_ep(valid_qty, invalid_discount, err_field, err_substring):
    """Test BR-01 invalid discount boundaries (one invalid input value per test)."""
    with pytest.raises(ValidationError) as exc_info:
        po_business_rules.validate_line_item_limits(valid_qty, invalid_discount)
    assert err_field in exc_info.value.message_dict
    assert err_substring in exc_info.value.message_dict[err_field][0]


def test_br01_calculate_discounted_line_total_bva():
    """Test discounted line total calculation at 0%, nominal 20%, and 100% discount boundaries."""
    assert po_business_rules.calculate_discounted_line_total(10, Decimal('25.00'), 0) == Decimal('250.00')
    assert po_business_rules.calculate_discounted_line_total(10, Decimal('25.00'), 20) == Decimal('200.00')
    assert po_business_rules.calculate_discounted_line_total(10, Decimal('25.00'), 100) == Decimal('0.00')
    assert po_business_rules.calculate_discounted_line_total(10, Decimal('0.00'), 0) == Decimal('0.00')

    with pytest.raises(ValidationError) as exc_info:
        po_business_rules.calculate_discounted_line_total(10, Decimal('-0.01'), 0)
    assert 'purchase_price' in exc_info.value.message_dict


# ============================================================================
# 2. COMPLETE MCC TRUTH TABLES & MC/DC INDEPENDENCE PAIRS (BR-02 & BR-04)
# ============================================================================

def test_br04_mcc_all_8_combinations_can_add_or_merge_line_item():
    """Complete Multiple Condition Coverage (MCC: 2^3 = 8 rows) for can_add_or_merge_line_item.

    Decision: D = A and B and C
      A = order_status in OPEN (10=PENDING -> True, 30=COMPLETE -> False)
      B = same_supplier (True / False)
      C = user_can_change_po (True / False)
    """
    mcc_results = {}
    for a_open, b_same_sup, c_perm in itertools.product([False, True], repeat=3):
        status_val = PurchaseOrderStatus.PENDING.value if a_open else PurchaseOrderStatus.COMPLETE.value
        outcome = po_business_rules.can_add_or_merge_line_item(status_val, b_same_sup, c_perm)
        expected = a_open and b_same_sup and c_perm
        assert outcome is expected
        mcc_results[(a_open, b_same_sup, c_perm)] = outcome

    assert len(mcc_results) == 8
    # Verify MC/DC Independence Pairs from the MCC table:
    # Pair for A (B=T, C=T): (T,T,T)=True vs (F,T,T)=False
    assert mcc_results[(True, True, True)] is True and mcc_results[(False, True, True)] is False
    # Pair for B (A=T, C=T): (T,T,T)=True vs (T,F,T)=False
    assert mcc_results[(True, True, True)] is True and mcc_results[(True, False, True)] is False
    # Pair for C (A=T, B=T): (T,T,T)=True vs (T,T,F)=False
    assert mcc_results[(True, True, True)] is True and mcc_results[(True, True, False)] is False


def test_br02a_mcc_all_16_combinations_evaluate_stock_receipt_decision():
    """Complete Multiple Condition Coverage (MCC: 2^4 = 16 rows) for evaluate_stock_receipt_decision.

    Decision: D_recv = C1 and C2 and C3 and C4
      C1 = order_status == PLACED (20 -> True, 10 -> False)
      C2 = line_matches_order
      C3 = quantity_positive
      C4 = has_destination
    """
    mcc_table = {}
    for c1, c2, c3, c4 in itertools.product([False, True], repeat=4):
        status_val = PurchaseOrderStatus.PLACED.value if c1 else PurchaseOrderStatus.PENDING.value
        actual = po_business_rules.evaluate_stock_receipt_decision(status_val, c2, c3, c4)
        expected = c1 and c2 and c3 and c4
        assert actual is expected
        mcc_table[(c1, c2, c3, c4)] = actual

    assert len(mcc_table) == 16
    # Verify MC/DC Independence Pairs for C1, C2, C3, C4:
    # C1 independence pair: (T,T,T,T)=True vs (F,T,T,T)=False
    assert mcc_table[(True, True, True, True)] is True and mcc_table[(False, True, True, True)] is False
    # C2 independence pair: (T,T,T,T)=True vs (T,F,T,T)=False
    assert mcc_table[(True, True, True, True)] is True and mcc_table[(True, False, True, True)] is False
    # C3 independence pair: (T,T,T,T)=True vs (T,T,F,T)=False
    assert mcc_table[(True, True, True, True)] is True and mcc_table[(True, True, False, True)] is False
    # C4 independence pair: (T,T,T,T)=True vs (T,T,T,F)=False
    assert mcc_table[(True, True, True, True)] is True and mcc_table[(True, True, True, False)] is False

    # Also verify every non-PLACED status (ON_HOLD=25, COMPLETE=30, CANCELLED=40) evaluates C1=False (kills M-02)
    for non_placed in (
        PurchaseOrderStatus.PENDING.value,
        PurchaseOrderStatus.ON_HOLD.value,
        PurchaseOrderStatus.COMPLETE.value,
        PurchaseOrderStatus.CANCELLED.value,
    ):
        assert po_business_rules.evaluate_stock_receipt_decision(non_placed, True, True, True) is False


def test_br02b_mcc_all_16_combinations_should_auto_complete_order():
    """Complete Multiple Condition Coverage (MCC: 2^4 = 16 rows) for should_auto_complete_order.

    Decision: D_comp = E1 and E2 and (E3 or not E4)
      E1 = auto_complete_enabled
      E2 = (pending_line_count == 0)
      E3 = allow_over_receive
      E4 = has_over_received_line
    """
    mcc_table = {}
    for e1, e2, e3, e4 in itertools.product([False, True], repeat=4):
        pending_count = 0 if e2 else 1
        actual = po_business_rules.should_auto_complete_order(e1, pending_count, e3, e4)
        expected = e1 and e2 and (e3 or not e4)
        assert actual is expected
        mcc_table[(e1, e2, e3, e4)] = actual

    assert len(mcc_table) == 16
    # Verify MC/DC Independence Pairs from the 16-row MCC table:
    # E1 independence pair (E2=T, E3=F, E4=F): (T,T,F,F)=True vs (F,T,F,F)=False
    assert mcc_table[(True, True, False, False)] is True
    assert mcc_table[(False, True, False, False)] is False
    # E2 independence pair (E1=T, E3=F, E4=F): (T,T,F,F)=True vs (T,F,F,F)=False
    assert mcc_table[(True, True, False, False)] is True
    assert mcc_table[(True, False, False, False)] is False
    # E3 independence pair (E1=T, E2=T, E4=T): (T,T,T,T)=True vs (T,T,F,T)=False
    assert mcc_table[(True, True, True, True)] is True
    assert mcc_table[(True, True, False, True)] is False
    # E4 independence pair (E1=T, E2=T, E3=F): (T,T,F,F)=True vs (T,T,F,T)=False
    assert mcc_table[(True, True, False, False)] is True
    assert mcc_table[(True, True, False, True)] is False


# ============================================================================
# 3. BR-03: COMPLETE STATE TRANSITION TESTING MATRIX
# ============================================================================

@pytest.mark.parametrize(
    'source_status,target_status',
    [
        # Every allowed transition in PurchaseOrder lifecycle
        (PurchaseOrderStatus.PENDING.value, PurchaseOrderStatus.PLACED.value),
        (PurchaseOrderStatus.PENDING.value, PurchaseOrderStatus.ON_HOLD.value),
        (PurchaseOrderStatus.PENDING.value, PurchaseOrderStatus.CANCELLED.value),
        (PurchaseOrderStatus.ON_HOLD.value, PurchaseOrderStatus.PLACED.value),
        (PurchaseOrderStatus.ON_HOLD.value, PurchaseOrderStatus.CANCELLED.value),
        (PurchaseOrderStatus.PLACED.value, PurchaseOrderStatus.ON_HOLD.value),
        (PurchaseOrderStatus.PLACED.value, PurchaseOrderStatus.COMPLETE.value),
        (PurchaseOrderStatus.PLACED.value, PurchaseOrderStatus.CANCELLED.value),
    ],
)
def test_br03_allowed_state_transitions(source_status, target_status):
    """Test every allowed state transition in the PurchaseOrder lifecycle FSM."""
    assert po_business_rules.validate_po_state_transition(source_status, target_status) is True


@pytest.mark.parametrize(
    'source_status,disallowed_target',
    [
        # Disallowed transitions from PENDING (10)
        (PurchaseOrderStatus.PENDING.value, PurchaseOrderStatus.COMPLETE.value),
        (PurchaseOrderStatus.PENDING.value, PurchaseOrderStatus.PENDING.value),
        # Disallowed transitions from ON_HOLD (25)
        (PurchaseOrderStatus.ON_HOLD.value, PurchaseOrderStatus.COMPLETE.value),
        (PurchaseOrderStatus.ON_HOLD.value, PurchaseOrderStatus.PENDING.value),
        # Disallowed transitions from PLACED (20)
        (PurchaseOrderStatus.PLACED.value, PurchaseOrderStatus.PENDING.value),
        (PurchaseOrderStatus.PLACED.value, PurchaseOrderStatus.PLACED.value),
        # Disallowed transitions from terminal COMPLETE (30)
        (PurchaseOrderStatus.COMPLETE.value, PurchaseOrderStatus.PLACED.value),
        (PurchaseOrderStatus.COMPLETE.value, PurchaseOrderStatus.ON_HOLD.value),
        (PurchaseOrderStatus.COMPLETE.value, PurchaseOrderStatus.CANCELLED.value),
        # Disallowed transitions from terminal CANCELLED (40)
        (PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.PLACED.value),
        (PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.ON_HOLD.value),
        (PurchaseOrderStatus.CANCELLED.value, PurchaseOrderStatus.COMPLETE.value),
        # Invalid/unknown source state (999)
        (999, PurchaseOrderStatus.PLACED.value),
    ],
)
def test_br03_disallowed_state_transitions(source_status, disallowed_target):
    """Test disallowed changes of state from every state in the FSM."""
    with pytest.raises(ValidationError) as exc_info:
        po_business_rules.validate_po_state_transition(source_status, disallowed_target)
    assert 'status' in exc_info.value.message_dict


# ============================================================================
# 4. BR-04 & WORKFLOW 1 / WORKFLOW 2 SERVER-SIDE EXECUTION TESTS
# ============================================================================

def test_br04_rbac_permissions_and_workflows_execution():
    """Verify RBAC role matrix and end-to-end execution of Workflow 1 and Workflow 2."""
    seed_sqe_data()
    officer = User.objects.get(username='purchasing_officer')
    viewer = User.objects.get(username='inventory_viewer')

    # Null / inactive user check
    assert po_business_rules.check_po_role_permission(None, 'view') is False
    inactive_user = User(username='inactive_temp', is_active=False)
    assert po_business_rules.check_po_role_permission(inactive_user, 'view') is False

    # Officer permissions (allowed for all PO & stock receipt actions)
    for act in ('view', 'create', 'issue', 'hold', 'cancel', 'complete', 'receive', 'delete_line'):
        assert po_business_rules.check_po_role_permission(officer, act) is True

    # Viewer permissions (allowed for 'view', denied for all mutating actions)
    assert po_business_rules.check_po_role_permission(viewer, 'view') is True
    for denied_act in ('create', 'issue', 'hold', 'cancel', 'complete', 'receive', 'delete_line'):
        assert po_business_rules.check_po_role_permission(viewer, denied_act) is False

    # MC/DC independence pairs for 'receive' (has_po_change AND has_stock_add) — kills M-12
    with patch('order.po_business_rules.check_user_role', side_effect=lambda u, r, p: r == 'purchase_order'):
        assert po_business_rules.check_po_role_permission(officer, 'receive') is False
    with patch('order.po_business_rules.check_user_role', side_effect=lambda u, r, p: r == 'stock'):
        assert po_business_rules.check_po_role_permission(officer, 'receive') is False

    # Unknown action raises ValueError
    with pytest.raises(ValueError, match='Unsupported PO RBAC action'):
        po_business_rules.check_po_role_permission(officer, 'invalid_action')

    # --- Workflow 1: Issue Purchase Order (PO-SQE-0001: PENDING -> PLACED) ---
    po1 = PurchaseOrder.objects.get(reference='PO-SQE-0001')
    assert po1.status == PurchaseOrderStatus.PENDING.value

    # Viewer cannot issue PO
    with pytest.raises(PermissionDenied, match='lacks purchase_order:change'):
        po_business_rules.execute_issue_purchase_order(po1, viewer)

    # Empty PO (0 line items) cannot be issued
    acme = Company.objects.get(name='Acme Electronics Ltd')
    empty_po = PurchaseOrder.objects.create(
        reference='PO-SQE-9001',
        supplier=acme,
        description='Empty PO test',
        status=PurchaseOrderStatus.PENDING.value,
    )
    with pytest.raises(ValidationError) as exc_info:
        po_business_rules.execute_issue_purchase_order(empty_po, officer)
    assert 'lines' in exc_info.value.message_dict

    # Officer issues PO-SQE-0001 -> transitions to PLACED (20)
    issued_po = po_business_rules.execute_issue_purchase_order(po1, officer)
    assert issued_po.status == PurchaseOrderStatus.PLACED.value
    assert issued_po.issue_date is not None

    # --- Workflow 2: Receive Stock Against Placed PO (PO-SQE-0001: PLACED -> COMPLETE) ---
    line1 = issued_po.lines.first()
    warehouse = StockLocation.objects.get(name='Main Warehouse Bay A')

    # Viewer cannot receive stock
    with pytest.raises(PermissionDenied, match='lacks required permissions'):
        po_business_rules.execute_receive_purchase_order_line(
            issued_po, line1, Decimal('4'), warehouse, viewer
        )

    # Cannot receive against a PENDING PO (BR-02 rejection)
    with pytest.raises(ValidationError, match='rejected by BR-02'):
        po_business_rules.execute_receive_purchase_order_line(
            empty_po, line1, Decimal('4'), warehouse, officer
        )

    # Over-receiving when allow_over_receive=False is rejected (BR-01)
    with pytest.raises(ValidationError) as exc_info:
        po_business_rules.execute_receive_purchase_order_line(
            issued_po, line1, Decimal('11'), warehouse, officer, allow_over_receive=False
        )
    assert 'quantity' in exc_info.value.message_dict

    # Partial receipt of 4 units (ordered 10) -> creates StockItem(4), PO stays PLACED (20)
    created_partial = po_business_rules.execute_receive_purchase_order_line(
        issued_po, line1, Decimal('4'), warehouse, officer, auto_complete=True
    )
    assert len(created_partial) == 1
    assert created_partial[0].quantity == Decimal('4')
    assert line1.received == Decimal('4')
    assert issued_po.status == PurchaseOrderStatus.PLACED.value

    # Remaining receipt of 6 units with auto_complete=False -> PO stays PLACED (20), then complete when True
    set_global_setting('PURCHASEORDER_AUTO_COMPLETE', False)
    created_rest = po_business_rules.execute_receive_purchase_order_line(
        issued_po, line1, Decimal('6'), None, officer, auto_complete=True
    )
    assert len(created_rest) == 1
    assert line1.received == Decimal('10')
    assert issued_po.status == PurchaseOrderStatus.COMPLETE.value
    assert issued_po.complete_date is not None
    set_global_setting('PURCHASEORDER_AUTO_COMPLETE', True)

    # Also test receiving when InvenTree's built-in auto-complete already completed the order
    po2 = PurchaseOrder.objects.get(reference='PO-SQE-0002')
    line2 = po2.lines.first()
    created_po2 = po_business_rules.execute_receive_purchase_order_line(
        po2, line2, Decimal('10'), warehouse, officer, auto_complete=True
    )
    assert len(created_po2) == 1
    assert po2.status == PurchaseOrderStatus.COMPLETE.value

    # And test receiving partial with auto_complete=False so should_auto_complete_order returns False
    po3 = PurchaseOrder.objects.create(
        reference='PO-SQE-9002',
        supplier=acme,
        description='Partial receipt no auto-complete test',
        status=PurchaseOrderStatus.PENDING.value,
        destination=warehouse,
    )
    sp = SupplierPart.objects.get(SKU='ACME-MCU-32')
    line3 = PurchaseOrderLineItem.objects.create(
        order=po3,
        part=sp,
        quantity=Decimal('10'),
        received=Decimal('0'),
        purchase_price=Money(25, 'USD'),
        destination=warehouse,
    )
    po3.place_order()
    set_global_setting('PURCHASEORDER_AUTO_COMPLETE', False)
    po_business_rules.execute_receive_purchase_order_line(
        po3, line3, Decimal('11'), warehouse, officer, auto_complete=False, allow_over_receive=True
    )
    assert po3.status == PurchaseOrderStatus.PLACED.value
    set_global_setting('PURCHASEORDER_AUTO_COMPLETE', True)


# ============================================================================
# 5. 100% COVERAGE OF order/status_codes.py AND order/validators.py
# ============================================================================

def test_order_status_codes_and_validators_full_coverage():
    """Verify 100% statement and branch coverage of order/status_codes.py and order/validators.py."""
    # Verify status code classes and groups
    assert PurchaseOrderStatus.PENDING.value in status_codes.PurchaseOrderStatusGroups.OPEN
    assert PurchaseOrderStatus.CANCELLED.value in status_codes.PurchaseOrderStatusGroups.FAILED
    assert PurchaseOrderStatus.COMPLETE.value in status_codes.PurchaseOrderStatusGroups.COMPLETE
    assert status_codes.SalesOrderStatus.PENDING.value in status_codes.SalesOrderStatusGroups.OPEN
    assert status_codes.ReturnOrderStatus.PENDING.value in status_codes.ReturnOrderStatusGroups.OPEN
    assert status_codes.TransferOrderStatus.PENDING.value in status_codes.TransferOrderStatusGroups.OPEN

    # Verify all reference generator and pattern/field validator functions in order/validators.py
    assert isinstance(validators.generate_next_purchase_order_reference(), str)
    assert isinstance(validators.generate_next_sales_order_reference(), str)
    assert isinstance(validators.generate_next_return_order_reference(), str)
    assert isinstance(validators.generate_next_transfer_order_reference(), str)

    with (
        patch('order.models.PurchaseOrder.validate_reference_pattern') as m_po_pat,
        patch('order.models.SalesOrder.validate_reference_pattern') as m_so_pat,
        patch('order.models.ReturnOrder.validate_reference_pattern') as m_ro_pat,
        patch('order.models.TransferOrder.validate_reference_pattern') as m_to_pat,
        patch('order.models.PurchaseOrder.validate_reference_field') as m_po_fld,
        patch('order.models.SalesOrder.validate_reference_field') as m_so_fld,
        patch('order.models.ReturnOrder.validate_reference_field') as m_ro_fld,
        patch('order.models.TransferOrder.validate_reference_field') as m_to_fld,
    ):
        validators.validate_purchase_order_reference_pattern('PO-{ref:04d}')
        validators.validate_sales_order_reference_pattern('SO-{ref:04d}')
        validators.validate_return_order_reference_pattern('RMA-{ref:04d}')
        validators.validate_transfer_order_reference_pattern('TO-{ref:04d}')

        validators.validate_purchase_order_reference('PO-0001')
        validators.validate_sales_order_reference('SO-0001')
        validators.validate_return_order_reference('RMA-0001')
        validators.validate_transfer_order_reference('TO-0001')

        assert m_po_pat.called and m_so_pat.called and m_ro_pat.called and m_to_pat.called
        assert m_po_fld.called and m_so_fld.called and m_ro_fld.called and m_to_fld.called
