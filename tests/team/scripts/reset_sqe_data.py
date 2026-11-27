#!/usr/bin/env python3
"""Deterministic database reset script for SE3002 SQE Final Project (Section C).

Removes any test-created Purchase Orders, PurchaseOrderLineItems, and StockItems
associated with the SQE synthetic suppliers/parts, then re-runs seed_sqe_data()
so every test run starts from an identical, reproducible state.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'src' / 'backend' / 'InvenTree'
CONFIG_DIR = REPO_ROOT / 'config'
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

os.environ.setdefault('INVENTREE_SITE_URL', 'http://localhost:8000')
os.environ.setdefault('INVENTREE_DB_ENGINE', 'sqlite3')
os.environ.setdefault('INVENTREE_DB_NAME', str(CONFIG_DIR / 'inventree_sqe.sqlite3'))
os.environ.setdefault('INVENTREE_MEDIA_ROOT', str(CONFIG_DIR / 'media'))
os.environ.setdefault('INVENTREE_STATIC_ROOT', str(CONFIG_DIR / 'static'))
os.environ.setdefault('INVENTREE_BACKUP_DIR', str(CONFIG_DIR / 'backup'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvenTree.settings')

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from company.models import Company  # noqa: E402
from order.models import PurchaseOrder, PurchaseOrderLineItem  # noqa: E402
from part.models import Part  # noqa: E402
from seed_sqe_data import seed_sqe_data  # noqa: E402
from stock.models import StockItem  # noqa: E402


@transaction.atomic
def reset_sqe_data() -> dict:
    """Wipe all dynamic SQE test records and restore baseline synthetic data."""
    sqe_parts = Part.objects.filter(IPN__in=['SQE-MCU-32', 'SQE-SEN-X1'])
    deleted_stock, _ = StockItem.objects.filter(part__in=sqe_parts).delete()

    sqe_suppliers = Company.objects.filter(
        name__in=['Acme Electronics Ltd', 'Beta Components Inc']
    )
    deleted_lines, _ = PurchaseOrderLineItem.objects.filter(
        order__supplier__in=sqe_suppliers
    ).delete()
    deleted_orders, _ = PurchaseOrder.objects.filter(
        supplier__in=sqe_suppliers
    ).delete()

    print(
        f'Cleaned dynamic state: {deleted_stock} stock records, '
        f'{deleted_lines} line items, {deleted_orders} purchase orders.'
    )
    summary = seed_sqe_data()
    return summary


if __name__ == '__main__':
    result = reset_sqe_data()
    print('=== SQE TEST ENVIRONMENT RESET TO BASELINE SUCCESSFULLY ===')
    for key, val in result.items():
        print(f'  {key}: {val}')
