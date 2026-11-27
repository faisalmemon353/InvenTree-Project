"""
SE3002 Software Quality Engineering — Section C
Step 5.2: Controlled Failure and Recovery Automated Test
Owner: Salman Ahmed (24I-3004)

Requirement (Section 5.2):
  Write 1 automated test using a fault injection or test double to simulate a failure
  (e.g., timeout, dependency unavailable, or rolled-back write) before a state-changing
  operation completes. Assert the persisted state after the failure, then restore the
  dependency, retry, and assert the expected final state without duplicate or partial records.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import django
import pytest
from django.db import OperationalError

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "src" / "backend" / "InvenTree"
CONFIG_DIR = REPO_ROOT / "config"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("INVENTREE_SITE_URL", "http://localhost:8000")
os.environ.setdefault("INVENTREE_DB_ENGINE", "sqlite3")
os.environ.setdefault("INVENTREE_DB_NAME", str(CONFIG_DIR / "inventree_sqe.sqlite3"))
os.environ.setdefault("INVENTREE_MEDIA_ROOT", str(CONFIG_DIR / "media"))
os.environ.setdefault("INVENTREE_STATIC_ROOT", str(CONFIG_DIR / "static"))
os.environ.setdefault("INVENTREE_BACKUP_DIR", str(CONFIG_DIR / "backup"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "InvenTree.settings")
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from order.models import PurchaseOrder, PurchaseOrderLineItem  # noqa: E402
from order.po_business_rules import execute_receive_purchase_order_line  # noqa: E402
from order.status_codes import PurchaseOrderStatus  # noqa: E402
from stock.models import StockItem, StockLocation  # noqa: E402


def test_controlled_db_failure_atomic_rollback_and_clean_retry_recovery():
    """
    Controlled Failure & Recovery Test (Salman Ahmed 24I-3004):
      1. Setup baseline: PLACED (20) Purchase Order PO-SQE-0002 with line item
         quantity=10, received=0, and 0 StockItems for that line item.
      2. Fault Injection: Use unittest.mock.patch on StockItem.save to raise
         django.db.OperationalError("Simulated database storage failure mid-transaction")
         during execute_receive_purchase_order_line() (inside @transaction.atomic).
      3. Assert Persisted State After Failure:
         - OperationalError is raised cleanly.
         - Atomic transaction rolled back all partial changes:
           * PurchaseOrder.status remains PLACED (20)
           * PurchaseOrderLineItem.received remains 0
           * StockItem count for this PurchaseOrder remains 0 (no orphan or partial record).
      4. Restore Dependency & Retry:
         - Exit the fault-injection patch context and retry execute_receive_purchase_order_line()
           with the exact same 10-unit receipt request.
      5. Assert Final Recovered State:
         - PurchaseOrder.status transitions to COMPLETE (30)
         - PurchaseOrderLineItem.received == 10
         - Exactly 1 StockItem exists with quantity == 10 (zero duplicate or partial records).
    """
    officer = User.objects.get(username="purchasing_officer")
    location = StockLocation.objects.first()
    po = PurchaseOrder.objects.get(reference="PO-SQE-0002")
    line = PurchaseOrderLineItem.objects.get(order=po)

    # Reset PO-SQE-0002 and its stock items to known clean baseline before test
    StockItem.objects.filter(purchase_order=po).delete()
    PurchaseOrder.objects.filter(pk=po.pk).update(
        status=PurchaseOrderStatus.PLACED.value
    )
    PurchaseOrderLineItem.objects.filter(pk=line.pk).update(received=Decimal("0"))
    po.refresh_from_db()
    line.refresh_from_db()

    baseline_stock_count = StockItem.objects.filter(purchase_order=po).count()
    assert po.status == PurchaseOrderStatus.PLACED.value
    assert line.received == Decimal("0")
    assert baseline_stock_count == 0

    # Phase 1: Inject dependency failure mid-transaction AFTER StockItem creation
    # (when audited_bulk_update writes PurchaseOrderLineItem.received) to verify @transaction.atomic
    # rolls back the newly bulk-created StockItem as well!
    with patch(
        "order.models.audited_bulk_update",
        side_effect=OperationalError(
            "Simulated storage dependency failure mid-transaction before line item commit"
        ),
    ):
        with pytest.raises(OperationalError, match="Simulated storage dependency failure"):
            execute_receive_purchase_order_line(
                po=po,
                line=line,
                quantity=Decimal("10"),
                location=location,
                user=officer,
                auto_complete=True,
                allow_over_receive=False,
            )

    # Phase 2: Assert persisted database state after failure (atomic rollback verification)
    po.refresh_from_db()
    line.refresh_from_db()
    post_failure_stock_count = StockItem.objects.filter(purchase_order=po).count()

    assert po.status == PurchaseOrderStatus.PLACED.value, (
        "PO status must remain PLACED (20) after rolled-back transaction"
    )
    assert line.received == Decimal("0"), (
        "Line item received count must remain 0 after rolled-back transaction"
    )
    assert post_failure_stock_count == 0, (
        "Zero partial or orphan StockItem records may exist after rolled-back failure"
    )

    # Phase 3: Dependency restored automatically upon exiting patch context -> Retry operation
    created_items = execute_receive_purchase_order_line(
        po=po,
        line=line,
        quantity=Decimal("10"),
        location=location,
        user=officer,
        auto_complete=True,
        allow_over_receive=False,
    )

    # Phase 4: Assert expected final recovered state without duplicate or partial records
    po.refresh_from_db()
    line.refresh_from_db()
    recovered_stock_items = list(StockItem.objects.filter(purchase_order=po))

    assert len(created_items) == 1
    assert po.status == PurchaseOrderStatus.COMPLETE.value, (
        "PO status must transition to COMPLETE (30) on clean retry"
    )
    assert line.received == Decimal("10"), (
        "Line item received count must equal 10 on clean retry"
    )
    assert len(recovered_stock_items) == 1, (
        "Exactly 1 StockItem record must exist (no duplicate records after retry)"
    )
    assert recovered_stock_items[0].quantity == Decimal("10")

    # Restore clean baseline state for subsequent test suites
    StockItem.objects.filter(purchase_order=po).delete()
    PurchaseOrder.objects.filter(pk=po.pk).update(
        status=PurchaseOrderStatus.PLACED.value
    )
    PurchaseOrderLineItem.objects.filter(pk=line.pk).update(received=Decimal("0"))
