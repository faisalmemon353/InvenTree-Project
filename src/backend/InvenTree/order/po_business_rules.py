"""Server-side business rules for Purchase Order creation, issuance, and stock receipt.

Covers the four mandatory SE3002 SQE business rules in the InvenTree 'order' module:
- BR-01 (Boundary / Limit Rule): Line item quantity [1..10000], discount [0..100], and over-receipt limit.
- BR-02 (Multi-Boolean Decision Rule): Stock receipt eligibility (4 conditions) and auto-completion (4 conditions).
- BR-03 (State Transition Rule): PurchaseOrder Finite State Machine (PENDING, PLACED, ON_HOLD, COMPLETE, CANCELLED).
- BR-04 (Supplier-Part & RBAC Rule): Open-order + supplier-part matching + RuleSet permission checks.
"""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError

from order.models import PurchaseOrder, PurchaseOrderLineItem
from order.status_codes import PurchaseOrderStatus, PurchaseOrderStatusGroups
from users.permissions import check_user_role

MIN_ORDER_QUANTITY = Decimal('1')
MAX_ORDER_QUANTITY = Decimal('10000')
MIN_DISCOUNT_PCT = Decimal('0')
MAX_DISCOUNT_PCT = Decimal('100')

# Allowed FSM transitions for PurchaseOrderStatus (BR-03)
ALLOWED_PO_TRANSITIONS: dict[int, set[int]] = {
    PurchaseOrderStatus.PENDING.value: {
        PurchaseOrderStatus.PLACED.value,
        PurchaseOrderStatus.ON_HOLD.value,
        PurchaseOrderStatus.CANCELLED.value,
    },
    PurchaseOrderStatus.ON_HOLD.value: {
        PurchaseOrderStatus.PLACED.value,
        PurchaseOrderStatus.CANCELLED.value,
    },
    PurchaseOrderStatus.PLACED.value: {
        PurchaseOrderStatus.ON_HOLD.value,
        PurchaseOrderStatus.COMPLETE.value,
        PurchaseOrderStatus.CANCELLED.value,
    },
    PurchaseOrderStatus.COMPLETE.value: set(),
    PurchaseOrderStatus.CANCELLED.value: set(),
}


def validate_line_item_limits(
    quantity: int | float | Decimal,
    discount: int | float | Decimal = Decimal('0'),
    max_order_qty: Decimal = MAX_ORDER_QUANTITY,
) -> tuple[Decimal, Decimal]:
    """Enforce BR-01 boundaries on line-item quantity and discount percentage.

    Boundaries:
    - quantity must satisfy MIN_ORDER_QUANTITY (1) <= quantity <= max_order_qty (10000)
    - discount must satisfy MIN_DISCOUNT_PCT (0) <= discount <= MAX_DISCOUNT_PCT (100)
    """
    qty_dec = Decimal(str(quantity))
    disc_dec = Decimal(str(discount))

    if qty_dec < MIN_ORDER_QUANTITY:
        raise ValidationError({'quantity': 'Quantity must be at least 1 unit'})

    if qty_dec > max_order_qty:
        raise ValidationError({'quantity': f'Quantity cannot exceed {max_order_qty} units'})

    if disc_dec < MIN_DISCOUNT_PCT:
        raise ValidationError({'discount': 'Discount cannot be less than 0%'})

    if disc_dec > MAX_DISCOUNT_PCT:
        raise ValidationError({'discount': 'Discount cannot exceed 100%'})

    return qty_dec, disc_dec


def calculate_discounted_line_total(
    quantity: int | float | Decimal,
    unit_price: int | float | Decimal,
    discount: int | float | Decimal = Decimal('0'),
) -> Decimal:
    """Calculate total line item price after applying validated BR-01 discount bounds."""
    qty_dec, disc_dec = validate_line_item_limits(quantity, discount)
    price_dec = Decimal(str(unit_price))

    if price_dec < Decimal('0'):
        raise ValidationError({'purchase_price': 'Unit purchase price cannot be negative'})

    discount_factor = (Decimal('100') - disc_dec) / Decimal('100')
    total = (qty_dec * price_dec * discount_factor).quantize(Decimal('0.01'))
    return total


def can_add_or_merge_line_item(
    order_status: int,
    same_supplier: bool,
    user_can_change_po: bool,
) -> bool:
    """Evaluate 3-condition Boolean decision rule (BR-04a) for adding/merging a PO line item.

    Conditions:
    - A: order_status in PurchaseOrderStatusGroups.OPEN (PENDING=10, PLACED=20, ON_HOLD=25)
    - B: same_supplier is True (supplier_part.supplier == purchase_order.supplier)
    - C: user_can_change_po is True (user has purchase_order.change permission)

    Decision: D = A and B and C
    """
    is_open_order = order_status in PurchaseOrderStatusGroups.OPEN
    if is_open_order and same_supplier and user_can_change_po:
        return True
    return False


def evaluate_stock_receipt_decision(
    order_status: int,
    line_matches_order: bool,
    quantity_positive: bool,
    has_destination: bool,
) -> bool:
    """Evaluate 4-condition Boolean decision rule (BR-02a) for stock receipt eligibility.

    Conditions:
    - C1: order_status == PurchaseOrderStatus.PLACED.value (20)
    - C2: line_matches_order is True (line_item.order_id == purchase_order.pk)
    - C3: quantity_positive is True (received_quantity >= 1)
    - C4: has_destination is True (valid destination StockLocation resolved)

    Decision: D_recv = C1 and C2 and C3 and C4
    """
    is_placed = order_status == PurchaseOrderStatus.PLACED.value
    if is_placed and line_matches_order and quantity_positive and has_destination:
        return True
    return False


def should_auto_complete_order(
    auto_complete_enabled: bool,
    pending_line_count: int,
    allow_over_receive: bool,
    has_over_received_line: bool,
) -> bool:
    """Evaluate 4-condition Boolean decision rule (BR-02b) for automatic PO completion.

    Conditions:
    - E1: auto_complete_enabled is True (PURCHASEORDER_AUTO_COMPLETE setting)
    - E2: pending_line_count == 0 (all lines satisfy received >= quantity)
    - E3: allow_over_receive is True (policy flag allowing received > quantity)
    - E4: has_over_received_line is True (at least one line has received > quantity)

    Decision: D_comp = E1 and E2 and (E3 or not E4)
    """
    no_pending_lines = pending_line_count == 0
    if auto_complete_enabled and no_pending_lines and (allow_over_receive or not has_over_received_line):
        return True
    return False


def validate_po_state_transition(current_status: int, target_status: int) -> bool:
    """Enforce BR-03 Finite State Machine transition rules for PurchaseOrder.status."""
    if current_status not in ALLOWED_PO_TRANSITIONS:
        raise ValidationError({'status': f'Unknown current order status: {current_status}'})

    allowed_targets = ALLOWED_PO_TRANSITIONS[current_status]
    if target_status not in allowed_targets:
        raise ValidationError({
            'status': f'Disallowed state transition from {current_status} to {target_status}'
        })
    return True


def check_po_role_permission(user, action: str) -> bool:
    """Enforce BR-04 Role-Based Access Control (RBAC) across Purchasing workflows.

    Supported actions:
    - 'view': requires purchase_order:view
    - 'create': requires purchase_order:add
    - 'issue' / 'hold' / 'cancel' / 'complete': requires purchase_order:change
    - 'receive': requires purchase_order:change AND stock:add
    - 'delete_line': requires purchase_order:delete
    """
    if user is None or not getattr(user, 'is_active', False):
        return False

    if action == 'view':
        return bool(check_user_role(user, 'purchase_order', 'view'))

    if action == 'create':
        return bool(check_user_role(user, 'purchase_order', 'add'))

    if action in ('issue', 'hold', 'cancel', 'complete'):
        return bool(check_user_role(user, 'purchase_order', 'change'))

    if action == 'receive':
        has_po_change = bool(check_user_role(user, 'purchase_order', 'change'))
        has_stock_add = bool(check_user_role(user, 'stock', 'add'))
        return has_po_change and has_stock_add

    if action == 'delete_line':
        return bool(check_user_role(user, 'purchase_order', 'delete'))

    raise ValueError(f'Unsupported PO RBAC action: {action}')


def execute_issue_purchase_order(po: PurchaseOrder, user) -> PurchaseOrder:
    """Execute Workflow 1 state transition (PENDING / ON_HOLD -> PLACED) with full rule validation."""
    if not check_po_role_permission(user, 'issue'):
        raise PermissionDenied('User lacks purchase_order:change permission to issue order')

    validate_po_state_transition(po.status, PurchaseOrderStatus.PLACED.value)

    if po.lines.count() < 1:
        raise ValidationError({'lines': 'Cannot issue a PurchaseOrder with zero line items'})

    po.place_order()
    po.refresh_from_db()
    return po


def execute_receive_purchase_order_line(
    po: PurchaseOrder,
    line: PurchaseOrderLineItem,
    quantity: int | float | Decimal,
    location,
    user,
    auto_complete: bool = True,
    allow_over_receive: bool = False,
):
    """Execute Workflow 2 stock receipt against a placed PO line item with BR-01..BR-04 enforcement."""
    if not check_po_role_permission(user, 'receive'):
        raise PermissionDenied('User lacks required permissions (purchase_order:change & stock:add)')

    qty_dec, _ = validate_line_item_limits(quantity, Decimal('0'))
    resolved_location = location or line.get_destination()

    eligible = evaluate_stock_receipt_decision(
        order_status=po.status,
        line_matches_order=(line.order_id == po.pk),
        quantity_positive=(qty_dec >= MIN_ORDER_QUANTITY),
        has_destination=(resolved_location is not None),
    )
    if not eligible:
        raise ValidationError('Stock receipt rejected by BR-02 eligibility decision rule')

    new_received = line.received + qty_dec
    is_over_received = new_received > line.quantity
    if is_over_received and not allow_over_receive:
        raise ValidationError({'quantity': 'Over-receiving beyond ordered quantity is not permitted'})

    created_items = po.receive_line_items(
        location=resolved_location,
        items=[{'line_item': line, 'quantity': qty_dec, 'location': resolved_location}],
        user=user,
    )
    po.refresh_from_db()
    line.refresh_from_db()

    if should_auto_complete_order(
        auto_complete_enabled=auto_complete,
        pending_line_count=po.pending_line_count,
        allow_over_receive=allow_over_receive,
        has_over_received_line=is_over_received,
    ):
        if po.status != PurchaseOrderStatus.COMPLETE.value:
            po.complete_order()
            po.refresh_from_db()

    return list(created_items)
