#!/usr/bin/env python3
"""Deterministic synthetic data seeding script for SE3002 SQE Final Project (Section C).

Creates/updates:
1. Superuser admin account ('sqe_admin') for administrative inspection.
2. Two test roles with distinct RuleSet permissions:
   - Role 1: Purchasing Officer ('purchasing_officer' / 'SQEPurchasingPass123!')
   - Role 2: Inventory Viewer ('inventory_viewer' / 'SQEViewerPass123!')
3. Two Supplier companies ('Acme Electronics Ltd', 'Beta Components Inc') and one Internal company.
4. Part Category ('Electronics'), two purchasable Parts ('Industrial Microcontroller MCU-32',
   'Precision Pressure Sensor SEN-X1'), and linked SupplierParts ('ACME-MCU-32', 'BETA-SEN-X1').
5. Destination StockLocation ('Main Warehouse Bay A').
6. Baseline Purchase Orders:
   - 'PO-SQE-0001' (PENDING, 10x ACME-MCU-32) — ready for Workflow 1 (Issue Order).
   - 'PO-SQE-0002' (PLACED, 10x ACME-MCU-32) — ready for Workflow 2 (Receive Stock).
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

# Add InvenTree backend to sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'src' / 'backend' / 'InvenTree'
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvenTree.settings')

import django  # noqa: E402

django.setup()

from django.contrib.auth.models import Group, User  # noqa: E402
from django.db import transaction  # noqa: E402

from allauth.account.models import EmailAddress  # noqa: E402
from djmoney.money import Money  # noqa: E402

from common.settings import set_global_setting  # noqa: E402
from company.models import Company, Contact, SupplierPart  # noqa: E402
from order.models import PurchaseOrder, PurchaseOrderLineItem  # noqa: E402
from order.status_codes import PurchaseOrderStatus  # noqa: E402
from part.models import Part, PartCategory  # noqa: E402
from stock.models import StockItem, StockLocation  # noqa: E402
from users.models import ApiToken, RuleSet  # noqa: E402


def configure_group_rulesets(group: Group, full_write_roles: set[str], view_only_roles: set[str]) -> None:
    """Assign explicit RuleSet permissions to a Django Group."""
    for rule_name, _label in RuleSet.RULESET_CHOICES if hasattr(RuleSet, 'RULESET_CHOICES') else []:
        pass

    from users.ruleset import RULESET_NAMES

    for role_name in RULESET_NAMES:
        ruleset, _ = RuleSet.objects.get_or_create(group=group, name=role_name)
        if role_name in full_write_roles:
            ruleset.can_view = True
            ruleset.can_add = True
            ruleset.can_change = True
            ruleset.can_delete = role_name == 'purchase_order'
        elif role_name in view_only_roles:
            ruleset.can_view = True
            ruleset.can_add = False
            ruleset.can_change = False
            ruleset.can_delete = False
        else:
            ruleset.can_view = False
            ruleset.can_add = False
            ruleset.can_change = False
            ruleset.can_delete = False
        ruleset.save()
    group.save()


def ensure_verified_user(username: str, email: str, password: str, first_name: str, last_name: str, is_staff: bool = False, is_superuser: bool = False) -> User:
    """Create or update a test user and mark their primary email as verified."""
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
        },
    )
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.is_active = True
    user.is_staff = is_staff
    user.is_superuser = is_superuser
    user.set_password(password)
    user.save()

    EmailAddress.objects.update_or_create(
        user=user,
        email=email,
        defaults={'verified': True, 'primary': True},
    )
    return user


@transaction.atomic
def seed_sqe_data() -> dict:
    """Seed all synthetic records for the SQE project and return summary metadata."""
    # Ensure deterministic global settings for our test basis
    set_global_setting('PURCHASEORDER_AUTO_COMPLETE', True)
    set_global_setting('PURCHASEORDER_EDIT_COMPLETED_ORDERS', False)
    set_global_setting('PURCHASEORDER_MERGE_LINE_ITEMS', True)

    # 1. Create Admin user
    admin_user = ensure_verified_user(
        username='sqe_admin',
        email='admin@sqe.local',
        password='SQEAdminPass123!',
        first_name='SQE',
        last_name='Administrator',
        is_staff=True,
        is_superuser=True,
    )

    # 2. Create Groups & Role Users
    po_officer_group, _ = Group.objects.get_or_create(name='SQE_Purchasing_Officers')
    configure_group_rulesets(
        po_officer_group,
        full_write_roles={'purchase_order', 'stock'},
        view_only_roles={'stock_location', 'part', 'part_category', 'sales_order', 'return_order'},
    )

    viewer_group, _ = Group.objects.get_or_create(name='SQE_Inventory_Viewers')
    configure_group_rulesets(
        viewer_group,
        full_write_roles=set(),
        view_only_roles={'purchase_order', 'stock', 'stock_location', 'part', 'part_category'},
    )

    officer_user = ensure_verified_user(
        username='purchasing_officer',
        email='officer@sqe.local',
        password='SQEPurchasingPass123!',
        first_name='Faisal',
        last_name='Officer',
        is_staff=False,
        is_superuser=False,
    )
    officer_user.groups.set([po_officer_group])

    viewer_user = ensure_verified_user(
        username='inventory_viewer',
        email='viewer@sqe.local',
        password='SQEViewerPass123!',
        first_name='Salman',
        last_name='Viewer',
        is_staff=False,
        is_superuser=False,
    )
    viewer_user.groups.set([viewer_group])

    # Ensure API tokens exist for both roles
    for usr, token_name in [(officer_user, 'sqe-officer-token'), (viewer_user, 'sqe-viewer-token'), (admin_user, 'sqe-admin-token')]:
        if not ApiToken.objects.filter(user=usr, name=token_name, revoked=False).exists():
            ApiToken.objects.create(user=usr, name=token_name)

    # 3. Create Suppliers & Contacts
    acme_supplier, _ = Company.objects.update_or_create(
        name='Acme Electronics Ltd',
        defaults={
            'description': 'Primary SQE synthetic electronic components supplier',
            'is_supplier': True,
            'is_customer': False,
            'is_manufacturer': True,
            'active': True,
            'currency': 'USD',
        },
    )
    Contact.objects.update_or_create(
        company=acme_supplier,
        name='Alice Vance (Acme Sales)',
        defaults={'email': 'alice@acme-electronics.local', 'role': 'Account Manager'},
    )

    beta_supplier, _ = Company.objects.update_or_create(
        name='Beta Components Inc',
        defaults={
            'description': 'Secondary SQE synthetic supplier for mismatch testing',
            'is_supplier': True,
            'is_customer': False,
            'is_manufacturer': True,
            'active': True,
            'currency': 'USD',
        },
    )
    Contact.objects.update_or_create(
        company=beta_supplier,
        name='Bob Miller (Beta Sales)',
        defaults={'email': 'bob@beta-components.local', 'role': 'Sales Rep'},
    )

    # 4. Create StockLocation
    warehouse_loc, _ = StockLocation.objects.update_or_create(
        name='Main Warehouse Bay A',
        defaults={
            'description': 'Primary receiving bay for SQE purchase order stock receipts',
        },
    )

    # 5. Create PartCategory, Parts, and SupplierParts
    category, _ = PartCategory.objects.update_or_create(
        name='SQE Microcontrollers & Sensors',
        defaults={'description': 'Synthetic part category for SQE testing'},
    )

    mcu_part, _ = Part.objects.update_or_create(
        name='Industrial Microcontroller MCU-32',
        IPN='SQE-MCU-32',
        defaults={
            'description': '32-bit ARM Cortex industrial microcontroller for PO & receipt workflows',
            'category': category,
            'active': True,
            'purchaseable': True,
            'salable': True,
            'trackable': False,
            'virtual': False,
            'default_location': warehouse_loc,
        },
    )

    sensor_part, _ = Part.objects.update_or_create(
        name='Precision Pressure Sensor SEN-X1',
        IPN='SQE-SEN-X1',
        defaults={
            'description': 'Secondary industrial sensor part for multi-line and mismatch tests',
            'category': category,
            'active': True,
            'purchaseable': True,
            'salable': True,
            'trackable': False,
            'virtual': False,
            'default_location': warehouse_loc,
        },
    )

    acme_mcu_sp, _ = SupplierPart.objects.update_or_create(
        part=mcu_part,
        supplier=acme_supplier,
        SKU='ACME-MCU-32',
        defaults={
            'description': 'Acme 32-bit Microcontroller SKU (1x pack)',
        },
    )

    beta_sen_sp, _ = SupplierPart.objects.update_or_create(
        part=sensor_part,
        supplier=beta_supplier,
        SKU='BETA-SEN-X1',
        defaults={
            'description': 'Beta Pressure Sensor SKU (1x pack)',
        },
    )

    # 6. Create Baseline Purchase Orders
    # Clean any existing baseline POs with references PO-SQE-0001 / PO-SQE-0002 first
    StockItem.objects.filter(part__in=[mcu_part, sensor_part]).delete()
    PurchaseOrder.objects.filter(reference__startswith='PO-SQE-').delete()

    # Workflow 1 starting PO (PENDING = 10)
    po_pending = PurchaseOrder.objects.create(
        reference='PO-SQE-0001',
        supplier=acme_supplier,
        supplier_reference='ACME-QUO-101',
        description='SQE Workflow 1 Baseline Purchase Order (Pending -> Placed)',
        status=PurchaseOrderStatus.PENDING.value,
        destination=warehouse_loc,
        created_by=officer_user,
    )
    PurchaseOrderLineItem.objects.create(
        order=po_pending,
        part=acme_mcu_sp,
        quantity=Decimal('10'),
        received=Decimal('0'),
        purchase_price=Money(25, 'USD'),
        reference='LINE-MCU-01',
        destination=warehouse_loc,
    )

    # Workflow 2 starting PO (PLACED = 20)
    po_placed = PurchaseOrder.objects.create(
        reference='PO-SQE-0002',
        supplier=acme_supplier,
        supplier_reference='ACME-QUO-102',
        description='SQE Workflow 2 Baseline Purchase Order (Placed -> Receive Stock -> Complete)',
        status=PurchaseOrderStatus.PENDING.value,
        destination=warehouse_loc,
        created_by=officer_user,
    )
    po_placed_line = PurchaseOrderLineItem.objects.create(
        order=po_placed,
        part=acme_mcu_sp,
        quantity=Decimal('10'),
        received=Decimal('0'),
        purchase_price=Money(25, 'USD'),
        reference='LINE-MCU-02',
        destination=warehouse_loc,
    )
    po_placed.place_order()

    summary = {
        'roles': {
            'purchasing_officer': officer_user.username,
            'inventory_viewer': viewer_user.username,
            'sqe_admin': admin_user.username,
        },
        'suppliers': {
            'acme_id': acme_supplier.pk,
            'beta_id': beta_supplier.pk,
        },
        'parts': {
            'mcu_part_id': mcu_part.pk,
            'sensor_part_id': sensor_part.pk,
            'acme_mcu_supplier_part_id': acme_mcu_sp.pk,
            'beta_sen_supplier_part_id': beta_sen_sp.pk,
        },
        'location_id': warehouse_loc.pk,
        'orders': {
            'po_pending_id': po_pending.pk,
            'po_pending_ref': po_pending.reference,
            'po_placed_id': po_placed.pk,
            'po_placed_ref': po_placed.reference,
            'po_placed_line_id': po_placed_line.pk,
        },
        'initial_mcu_stock_count': StockItem.objects.filter(part=mcu_part).count(),
    }
    return summary


if __name__ == '__main__':
    result = seed_sqe_data()
    print('=== SQE SYNTHETIC DATA SEEDED SUCCESSFULLY ===')
    for key, val in result.items():
        print(f'  {key}: {val}')
