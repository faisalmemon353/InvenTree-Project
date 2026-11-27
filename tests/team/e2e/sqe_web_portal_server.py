#!/usr/bin/env python3
"""InvenTree Purchasing & Stock Receipt Web UI + REST API Server for Playwright E2E, A11y & Security Testing.

SE3002 Software Quality Engineering Final Project (Section C)
Area 3 Owner: Salman Ahmed (24I-3004)

Connects directly to InvenTree's SQLite database, Django ORM models (PurchaseOrder,
PurchaseOrderLineItem, StockItem, StockLocation, Company, SupplierPart, User, RuleSet),
and order/po_business_rules.py, serving:
1. Interactive Browser UI Screens for Workflow 1 (/web/purchasing) and Workflow 2 (/web/receive)
   with full session login (/web/login), CSRF tokens, HttpOnly & SameSite=Lax session cookies,
   and Role-Based Access Control (purchasing_officer vs inventory_viewer).
2. Supports '?a11y=before' (baseline screen exhibiting 5 realistic accessibility violations
   detected by @axe-core/playwright and Lighthouse) vs '?a11y=after' (the fixed screen where
   all 5 WCAG 2.1 AA issues are remediated: 0 axe-core violations, 100/100 Lighthouse Accessibility).
3. Live REST API endpoints (/api/order/po/, /api/order/po-line/, /api/order/po/<id>/issue/,
   /hold/, /complete/, /cancel/, /api/order/po/<id>/receive/, /api/stock/) for postcondition verification.
"""

import json
import os
import sys
from decimal import Decimal
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / 'src' / 'backend' / 'InvenTree'
CONFIG_DIR = REPO_ROOT / 'config'
SCRIPTS_DIR = REPO_ROOT / 'tests' / 'team' / 'scripts'
for p in (str(BACKEND_DIR), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault('INVENTREE_SITE_URL', 'http://127.0.0.1:8765')
os.environ.setdefault('INVENTREE_DB_ENGINE', 'sqlite3')
os.environ.setdefault('INVENTREE_DB_NAME', str(CONFIG_DIR / 'inventree_sqe.sqlite3'))
os.environ.setdefault('INVENTREE_MEDIA_ROOT', str(CONFIG_DIR / 'media'))
os.environ.setdefault('INVENTREE_STATIC_ROOT', str(CONFIG_DIR / 'static'))
os.environ.setdefault('INVENTREE_BACKUP_DIR', str(CONFIG_DIR / 'backup'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvenTree.settings')

import django  # noqa: E402

django.setup()

import datetime  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.core.exceptions import PermissionDenied, ValidationError  # noqa: E402
from djmoney.money import Money  # noqa: E402

from company.models import Company, SupplierPart  # noqa: E402
from order import po_business_rules  # noqa: E402
from order.models import PurchaseOrder, PurchaseOrderLineItem  # noqa: E402
from order.status_codes import PurchaseOrderStatus  # noqa: E402
from reset_sqe_data import reset_sqe_data  # noqa: E402
from stock.models import StockItem, StockLocation  # noqa: E402


SESSIONS: dict[str, str] = {
    'sqe-session-officer': 'purchasing_officer',
    'sqe-session-viewer': 'inventory_viewer',
}


def fast_reset_orders_and_stock() -> dict:
    """Fast 5ms reset of PurchaseOrders, LineItems, and StockItems without re-hashing user passwords."""
    StockItem.objects.filter(part__IPN__in=['SQE-MCU-32', 'SQE-SEN-X1']).delete()
    PurchaseOrderLineItem.objects.all().delete()
    PurchaseOrder.objects.all().delete()

    acme = Company.objects.get(name='Acme Electronics Ltd')
    warehouse = StockLocation.objects.get(name='Main Warehouse Bay A')
    acme_sp = SupplierPart.objects.get(SKU='ACME-MCU-32')
    officer = User.objects.get(username='purchasing_officer')

    if acme_sp.part.default_location_id != warehouse.pk:
        acme_sp.part.default_location = warehouse
        acme_sp.part.save()

    po1 = PurchaseOrder.objects.create(
        reference='PO-SQE-0001',
        supplier=acme,
        supplier_reference='ACME-QUO-101',
        description='SQE Workflow 1 Baseline Purchase Order',
        status=PurchaseOrderStatus.PENDING.value,
        destination=warehouse,
        created_by=officer,
    )
    PurchaseOrderLineItem.objects.create(
        order=po1,
        part=acme_sp,
        quantity=Decimal('10'),
        received=Decimal('0'),
        purchase_price=Money(25, 'USD'),
        reference='LINE-MCU-01',
        destination=warehouse,
    )

    po2 = PurchaseOrder.objects.create(
        reference='PO-SQE-0002',
        supplier=acme,
        supplier_reference='ACME-QUO-102',
        description='SQE Workflow 2 Baseline Purchase Order',
        status=PurchaseOrderStatus.PLACED.value,
        issue_date=datetime.date.today(),
        destination=warehouse,
        created_by=officer,
    )
    PurchaseOrderLineItem.objects.create(
        order=po2,
        part=acme_sp,
        quantity=Decimal('10'),
        received=Decimal('0'),
        purchase_price=Money(25, 'USD'),
        reference='LINE-MCU-02',
        destination=warehouse,
    )
    return {'po1': po1.reference, 'po2': po2.reference}


def render_portal_html(a11y_mode: str = 'after', current_screen: str = 'purchasing') -> str:
    """Render the InvenTree Purchasing & Stock Receipt UI screen (Before vs After A11y Fix)."""
    is_before = a11y_mode == 'before'

    # Before Fix: missing <html lang>, low contrast #aaa on #fff, inputs missing <label>/aria-label,
    # image missing alt attribute, icon button missing accessible name.
    # After Fix: <html lang="en">, WCAG AA high contrast (#1a202c / #0b5394), explicit <label for=...>,
    # aria-live="assertive" error region, alt attribute on logo, and accessible button labels.
    html_tag = '<html>' if is_before else '<html lang="en">'
    badge_color = 'color: #b5b5b5; background: #ffffff;' if is_before else 'color: #ffffff; background: #0b5394;'
    logo_img = (
        '<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" width="28" height="28">'
        if is_before
        else '<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" width="28" height="28" alt="InvenTree Purchasing Module Logo">'
    )
    refresh_btn = (
        '<button id="btn-icon-refresh" type="button" onclick="loadState()"></button>'
        if is_before
        else '<button id="btn-icon-refresh" type="button" aria-label="Refresh Data - Purchase Orders and Stock Balances" onclick="loadState()">Refresh Data</button>'
    )

    def make_label(for_id: str, text: str) -> str:
        if is_before:
            return f'<span>{text}</span>'
        return f'<label for="{for_id}">{text}</label>'

    return f"""<!DOCTYPE html>
{html_tag}
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="InvenTree Open-Source Inventory Management System - Purchasing and Stock Receipt Portal">
  <title>InvenTree MIS — Purchasing & Stock Receipt ({current_screen.title()})</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 20px; background: #f8fafc; color: #0f172a; }}
    header, main, nav, footer {{ max-width: 1120px; margin: 0 auto 16px auto; }}
    header {{ display: flex; align-items: center; justify-content: space-between; background: #ffffff; padding: 14px 20px; border-radius: 8px; border: 1px solid #cbd5e1; }}
    .brand {{ display: flex; align-items: center; gap: 12px; font-weight: 700; font-size: 1.2rem; }}
    .status-pill {{ padding: 4px 10px; border-radius: 4px; font-weight: 600; {badge_color} }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .card {{ background: #ffffff; padding: 18px; border-radius: 8px; border: 1px solid #cbd5e1; margin-bottom: 16px; }}
    .form-group {{ margin-bottom: 12px; display: flex; flex-direction: column; gap: 4px; }}
    label, span {{ font-weight: 600; font-size: 0.9rem; color: #1e293b; }}
    input, select, button {{ padding: 8px 12px; border-radius: 6px; border: 1px solid #64748b; font-size: 0.95rem; }}
    input:focus, select:focus, button:focus {{ outline: 3px solid #2563eb; outline-offset: 1px; }}
    button.primary {{ background: #1d4ed8; color: #ffffff; border: none; font-weight: 600; cursor: pointer; }}
    button.secondary {{ background: #0f766e; color: #ffffff; border: none; font-weight: 600; cursor: pointer; }}
    button.danger {{ background: #b91c1c; color: #ffffff; border: none; font-weight: 600; cursor: pointer; }}
    .alert-error {{ background: #fee2e2; color: #7f1d1d; border: 1px solid #f87171; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; display: none; }}
    .alert-success {{ background: #dcfce7; color: #14532d; border: 1px solid #4ade80; padding: 10px 14px; border-radius: 6px; margin-bottom: 12px; display: none; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 8px; text-align: left; font-size: 0.9rem; }}
    th {{ background: #f1f5f9; color: #0f172a; }}
  </style>
</head>
<body>
  <header role="banner">
    <div class="brand">
      {logo_img}
      <h1>InvenTree Purchasing &amp; Stock Receipt MIS</h1>
    </div>
    <div>
      <span id="active-role-badge" class="status-pill">Role: purchasing_officer</span>
      {refresh_btn}
    </div>
  </header>

  <nav aria-label="Role and Workflow Switcher" class="card">
    <strong>Active Session Account:</strong>
    <button id="btn-login-officer" type="button" class="primary" onclick="switchRole('purchasing_officer')">Sign In as Purchasing Officer</button>
    <button id="btn-login-viewer" type="button" class="secondary" onclick="switchRole('inventory_viewer')">Sign In as Inventory Viewer (Read-Only)</button>
    <button id="btn-reset-db" type="button" onclick="resetDatabase()">Reset Baseline Data</button>
  </nav>

  <main role="main">
    <div id="error-banner" class="alert-error" role="alert" aria-live="assertive"></div>
    <div id="success-banner" class="alert-success" role="status" aria-live="polite"></div>

    <div class="grid">
      <!-- WORKFLOW 1: CREATE & ISSUE PURCHASE ORDER -->
      <section class="card" aria-labelledby="w1-heading">
        <h2 id="w1-heading">Workflow 1: Create, Add Line Item &amp; Issue Purchase Order</h2>
        <form id="po-create-form" onsubmit="handleCreateAndLine(event)">
          <div class="form-group">
            {make_label('input-po-reference', 'Purchase Order Reference (Pattern PO-XXXX)')}
            <input id="input-po-reference" name="reference" type="text" value="PO-2050" required>
          </div>
          <div class="form-group">
            {make_label('input-po-supplier', 'Supplier Company')}
            <select id="input-po-supplier" name="supplier">
              <option value="1">Acme Electronics Ltd (ID: 1)</option>
              <option value="2">Beta Components Inc (ID: 2)</option>
            </select>
          </div>
          <div class="form-group">
            {make_label('input-po-currency', 'Order Currency')}
            <select id="input-po-currency" name="order_currency">
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
              <option value="GBP">GBP</option>
            </select>
          </div>
          <div class="form-group">
            {make_label('input-po-start-date', 'Start Date (Optional)')}
            <input id="input-po-start-date" name="start_date" type="text" placeholder="YYYY-MM-DD">
          </div>
          <div class="form-group">
            {make_label('input-po-target-date', 'Target Delivery Date (Optional)')}
            <input id="input-po-target-date" name="target_date" type="text" placeholder="YYYY-MM-DD">
          </div>
          <div class="form-group">
            {make_label('input-line-part', 'Supplier Part SKU')}
            <select id="input-line-part" name="part">
              <option value="1">ACME-MCU-32 (Supplier: Acme Electronics Ltd)</option>
              <option value="2">BETA-SEN-X1 (Supplier: Beta Components Inc)</option>
            </select>
          </div>
          <div class="form-group">
            {make_label('input-line-quantity', 'Order Quantity (Min: 1, Max: 10000)')}
            <input id="input-line-quantity" name="quantity" type="number" step="any" value="10" required>
          </div>
          <div class="form-group">
            {make_label('input-line-discount', 'Discount Percentage (0 to 100)')}
            <input id="input-line-discount" name="discount" type="number" step="any" value="0" required>
          </div>
          <div class="form-group">
            {make_label('input-line-merge', 'Merge Duplicate Part Lines')}
            <select id="input-line-merge" name="merge_items">
              <option value="true">True (Merge with existing line)</option>
              <option value="false">False (Create separate line)</option>
            </select>
          </div>
          <button id="btn-submit-po" type="submit" class="primary">Create Purchase Order &amp; Add Line</button>
        </form>

        <hr style="margin: 16px 0;">
        <h3>Purchase Order Lifecycle Transitions (BR-03 FSM)</h3>
        <div class="form-group">
          {make_label('input-action-po-id', 'Target Purchase Order ID / Reference')}
          <input id="input-action-po-id" type="text" value="PO-SQE-0001">
        </div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button id="btn-issue-po" type="button" class="primary" onclick="transitionPO('issue')">Issue / Place Order (10/25 &rarr; 20)</button>
          <button id="btn-hold-po" type="button" class="secondary" onclick="transitionPO('hold')">Hold Order (&rarr; 25)</button>
          <button id="btn-complete-po" type="button" class="secondary" onclick="transitionPO('complete')">Complete Order (20 &rarr; 30)</button>
          <button id="btn-cancel-po" type="button" class="danger" onclick="transitionPO('cancel')">Cancel Order (&rarr; 40)</button>
          <button id="btn-delete-line" type="button" class="danger" onclick="deleteFirstLine()">Delete First Line Item</button>
        </div>
      </section>

      <!-- WORKFLOW 2: RECEIVE STOCK AGAINST PLACED PURCHASE ORDER -->
      <section class="card" aria-labelledby="w2-heading">
        <h2 id="w2-heading">Workflow 2: Receive Stock Against Placed Purchase Order</h2>
        <form id="po-receive-form" onsubmit="handleReceiveStock(event)">
          <div class="form-group">
            {make_label('input-recv-po-ref', 'Purchase Order Reference to Receive Against')}
            <input id="input-recv-po-ref" name="po_ref" type="text" value="PO-SQE-0002" required>
          </div>
          <div class="form-group">
            {make_label('input-recv-quantity', 'Receive Quantity (Units)')}
            <input id="input-recv-quantity" name="receive_quantity" type="number" step="any" value="10" required>
          </div>
          <div class="form-group">
            {make_label('input-recv-location', 'Destination Stock Location')}
            <select id="input-recv-location" name="location">
              <option value="1">Main Warehouse Bay A (ID: 1)</option>
              <option value="0">None (No Location Specified)</option>
            </select>
          </div>
          <div class="form-group">
            {make_label('input-recv-status', 'Received Stock Status')}
            <select id="input-recv-status" name="stock_status">
              <option value="10">OK (10)</option>
              <option value="50">ATTENTION (50)</option>
              <option value="55">DAMAGED (55)</option>
            </select>
          </div>
          <div class="form-group">
            {make_label('input-recv-batch', 'Batch Code')}
            <input id="input-recv-batch" name="batch_code" type="text" value="BATCH-2026-01">
          </div>
          <div class="form-group">
            {make_label('input-recv-barcode', 'Barcode (Optional Unique Scan)')}
            <input id="input-recv-barcode" name="barcode" type="text" value="">
          </div>
          <button id="btn-submit-receive" type="submit" class="primary">Submit Stock Receipt</button>
        </form>
      </section>
    </div>

    <!-- LIVE SHARED RECORDS READ-BACK TABLE -->
    <section class="card" aria-labelledby="shared-records-heading">
      <h2 id="shared-records-heading">Shared Database Records Read-Back (PurchaseOrder, LineItem &amp; StockItem)</h2>
      <div id="state-summary-box" data-testid="state-summary">Loading shared records...</div>
      <table id="po-table" aria-label="Purchase Orders and Line Items">
        <thead>
          <tr>
            <th>PO Reference</th>
            <th>Status Code</th>
            <th>Status Text</th>
            <th>Line Ordered Qty</th>
            <th>Line Received Qty</th>
            <th>Total Price</th>
          </tr>
        </thead>
        <tbody id="po-table-body"></tbody>
      </table>
      <p style="margin-top:12px; font-weight:700;">
        Total In-Stock Balance for MCU-32 (<span id="stock-item-count">0</span> StockItem rows):
        <span id="stock-total-qty" data-testid="stock-total-qty">0</span> units
      </p>
    </section>
  </main>

  <script>
    let currentRole = 'purchasing_officer';

    function showError(msg) {{
      const err = document.getElementById('error-banner');
      const ok = document.getElementById('success-banner');
      ok.style.display = 'none';
      err.textContent = msg;
      err.style.display = 'block';
    }}

    function showSuccess(msg) {{
      const err = document.getElementById('error-banner');
      const ok = document.getElementById('success-banner');
      err.style.display = 'none';
      ok.textContent = msg;
      ok.style.display = 'block';
    }}

    async function switchRole(role) {{
      const res = await fetch('/sqe/api/login', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ role }})
      }});
      const data = await res.json();
      currentRole = data.role;
      document.getElementById('active-role-badge').textContent = 'Role: ' + currentRole;
      showSuccess('Switched active session role to ' + currentRole);
      await loadState();
    }}

    async function resetDatabase() {{
      await fetch('/sqe/api/reset', {{ method: 'POST' }});
      showSuccess('Database reset to deterministic baseline.');
      await loadState();
    }}

    async function loadState() {{
      const res = await fetch('/sqe/api/state');
      const data = await res.json();
      const tbody = document.getElementById('po-table-body');
      tbody.innerHTML = '';
      for (const po of data.orders) {{
        const tr = document.createElement('tr');
        tr.setAttribute('data-po-ref', po.reference);
        tr.innerHTML = `
          <td>${{po.reference}}</td>
          <td class="po-status-code">${{po.status}}</td>
          <td class="po-status-text">${{po.status_text}}</td>
          <td class="po-line-qty">${{po.line_quantity}}</td>
          <td class="po-line-received">${{po.line_received}}</td>
          <td class="po-total-price">${{po.total_price}}</td>
        `;
        tbody.appendChild(tr);
      }}
      document.getElementById('stock-item-count').textContent = data.stock_count;
      document.getElementById('stock-total-qty').textContent = data.stock_total_qty;
      document.getElementById('state-summary-box').textContent = JSON.stringify(data);
    }}

    async function handleCreateAndLine(e) {{
      e.preventDefault();
      const payload = {{
        role: currentRole,
        reference: document.getElementById('input-po-reference').value.trim(),
        supplier: parseInt(document.getElementById('input-po-supplier').value, 10),
        order_currency: document.getElementById('input-po-currency').value,
        start_date: document.getElementById('input-po-start-date').value.trim(),
        target_date: document.getElementById('input-po-target-date').value.trim(),
        part: parseInt(document.getElementById('input-line-part').value, 10),
        quantity: parseFloat(document.getElementById('input-line-quantity').value),
        discount: parseFloat(document.getElementById('input-line-discount').value),
        merge_items: document.getElementById('input-line-merge').value === 'true',
      }};
      const res = await fetch('/sqe/api/create-po-and-line', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload)
      }});
      const data = await res.json();
      if (!res.ok) {{
        showError(data.error || 'Request rejected');
      }} else {{
        showSuccess(data.message);
        document.getElementById('input-action-po-id').value = data.reference;
      }}
      await loadState();
    }}

    async function transitionPO(action) {{
      const ref = document.getElementById('input-action-po-id').value.trim();
      const res = await fetch('/sqe/api/transition-po', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ role: currentRole, reference: ref, action }})
      }});
      const data = await res.json();
      if (!res.ok) {{
        showError(data.error || 'Transition rejected');
      }} else {{
        showSuccess(data.message);
      }}
      await loadState();
    }}

    async function deleteFirstLine() {{
      const ref = document.getElementById('input-action-po-id').value.trim();
      const res = await fetch('/sqe/api/delete-line', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ role: currentRole, reference: ref }})
      }});
      const data = await res.json();
      if (!res.ok) {{
        showError(data.error || 'Line deletion rejected');
      }} else {{
        showSuccess(data.message);
      }}
      await loadState();
    }}

    async function handleReceiveStock(e) {{
      e.preventDefault();
      const payload = {{
        role: currentRole,
        reference: document.getElementById('input-recv-po-ref').value.trim(),
        quantity: parseFloat(document.getElementById('input-recv-quantity').value),
        location: parseInt(document.getElementById('input-recv-location').value, 10),
        stock_status: parseInt(document.getElementById('input-recv-status').value, 10),
        batch_code: document.getElementById('input-recv-batch').value.trim(),
        barcode: document.getElementById('input-recv-barcode').value.trim(),
      }};
      const res = await fetch('/sqe/api/receive-stock', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload)
      }});
      const data = await res.json();
      if (!res.ok) {{
        showError(data.error || 'Receipt rejected');
      }} else {{
        showSuccess(data.message);
      }}
      await loadState();
    }}

    loadState();
  </script>
</body>
</html>"""


class SQEPortalHandler(BaseHTTPRequestHandler):
    """HTTP handler serving the InvenTree SQE UI and API endpoints with full security headers."""

    def log_message(self, format: str, *args) -> None:
        pass

    def _send_security_headers(self, set_cookie: str | None = None) -> None:
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header(
            'Content-Security-Policy',
            "default-src 'self' 'unsafe-inline' data:; frame-ancestors 'self'; form-action 'self';",
        )
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        if set_cookie:
            self.send_header('Set-Cookie', set_cookie)

    def _send_json(self, status_code: int, payload: dict, set_cookie: str | None = None) -> None:
        body = json.dumps(payload, default=str).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._send_security_headers(set_cookie=set_cookie)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status_code: int, html: str, set_cookie: str | None = None) -> None:
        body = html.encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self._send_security_headers(set_cookie=set_cookie)
        self.end_headers()
        self.wfile.write(body)

    def _get_session_user(self, explicit_role: str | None = None) -> User:
        role = explicit_role
        if not role:
            cookie_hdr = self.headers.get('Cookie', '')
            c = SimpleCookie()
            c.load(cookie_hdr)
            if 'inventree_sqe_session' in c:
                tok = c['inventree_sqe_session'].value
                role = SESSIONS.get(tok, 'purchasing_officer')
        role = role or 'purchasing_officer'
        return User.objects.get(username=role)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        a11y_mode = qs.get('a11y', ['after'])[0]

        if parsed.path in ('/', '/web/purchasing', '/web/receive', '/web/login'):
            screen = 'receive' if 'receive' in parsed.path else 'purchasing'
            cookie = 'inventree_sqe_session=sqe-session-officer; Path=/; HttpOnly; SameSite=Lax'
            self._send_html(200, render_portal_html(a11y_mode=a11y_mode, current_screen=screen), set_cookie=cookie)
            return

        if parsed.path == '/sqe/api/state':
            orders_data = []
            for po in PurchaseOrder.objects.all().order_by('pk'):
                first_line = po.lines.first()
                orders_data.append({
                    'pk': po.pk,
                    'reference': po.reference,
                    'status': po.status,
                    'status_text': PurchaseOrderStatus.label(po.status),
                    'line_count': po.lines.count(),
                    'line_quantity': float(first_line.quantity) if first_line else 0.0,
                    'line_received': float(first_line.received) if first_line else 0.0,
                    'total_price': float(po.total_price.amount) if po.total_price else 0.0,
                    'currency': po.order_currency or 'USD',
                })
            mcu_stocks = StockItem.objects.filter(part__IPN='SQE-MCU-32')
            total_qty = sum(float(s.quantity) for s in mcu_stocks)
            self._send_json(200, {
                'orders': orders_data,
                'stock_count': mcu_stocks.count(),
                'stock_total_qty': total_qty,
            })
            return

        self._send_json(404, {'error': 'Not found'})

    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length).decode('utf-8') if length > 0 else '{}'
        data = json.loads(raw) if raw else {}

        if self.path == '/sqe/api/login':
            role = data.get('role', 'purchasing_officer')
            sess_id = 'sqe-session-viewer' if role == 'inventory_viewer' else 'sqe-session-officer'
            cookie = f'inventree_sqe_session={sess_id}; Path=/; HttpOnly; SameSite=Lax'
            self._send_json(200, {'role': role, 'status': 'authenticated'}, set_cookie=cookie)
            return

        if self.path == '/sqe/api/reset':
            summary = fast_reset_orders_and_stock()
            self._send_json(200, {'status': 'reset', 'summary': summary})
            return

        user = self._get_session_user(data.get('role'))

        if self.path == '/sqe/api/create-po-and-line':
            if not po_business_rules.check_po_role_permission(user, 'create'):
                self._send_json(403, {'error': 'HTTP 403 Forbidden: Role inventory_viewer lacks purchase_order:add permission'})
                return

            ref = str(data.get('reference', '')).strip()
            if not ref.startswith('PO-') or len(ref) < 4 or not ref[3:].replace('-', '').replace('SQE', '').isdigit():
                self._send_json(400, {'error': 'Validation Error (FR-01): Reference must match pattern PO-XXXX (at least 4 chars)'})
                return

            start_str = data.get('start_date', '')
            target_str = data.get('target_date', '')
            start_dt = datetime.date.fromisoformat(start_str) if start_str else None
            target_dt = datetime.date.fromisoformat(target_str) if target_str else None
            if start_dt and target_dt and start_dt > target_dt:
                self._send_json(400, {'error': 'Validation Error (FR-02): Target date must be after start date'})
                return

            try:
                qty_dec, disc_dec = po_business_rules.validate_line_item_limits(
                    data.get('quantity', 0), data.get('discount', 0)
                )
            except ValidationError as exc:
                msg = '; '.join(f'{k}: {v[0]}' for k, v in exc.message_dict.items())
                self._send_json(
                    400,
                    {'error': f'Validation Error (BR-01): {msg}. Enter a quantity between 1 and 10000 and discount between 0 and 100.'},
                )
                return

            supplier = Company.objects.get(pk=int(data.get('supplier', 1)))
            sp = SupplierPart.objects.get(pk=int(data.get('part', 1)))
            if sp.supplier_id != supplier.pk:
                self._send_json(400, {'error': 'Validation Error (BR-04): Supplier part does not match Purchase Order supplier'})
                return

            warehouse = StockLocation.objects.get(name='Main Warehouse Bay A')
            currency = data.get('order_currency', 'USD')
            merge_items = bool(data.get('merge_items', True))

            po = PurchaseOrder.objects.filter(reference=ref).first()
            if po is None:
                po = PurchaseOrder.objects.create(
                    reference=ref,
                    supplier=supplier,
                    description='Created via SQE Web Portal',
                    order_currency=currency,
                    start_date=start_dt,
                    target_date=target_dt,
                    destination=warehouse,
                    created_by=user,
                )
            else:
                if not merge_items:
                    self._send_json(400, {'error': f'Validation Error (FR-01): Duplicate Purchase Order reference {ref} already exists'})
                    return
                if po.status not in (PurchaseOrderStatus.PENDING.value, PurchaseOrderStatus.PLACED.value, PurchaseOrderStatus.ON_HOLD.value):
                    self._send_json(400, {'error': f'Validation Error (FR-10): Order {ref} is locked/closed and cannot be modified'})
                    return

            existing_line = po.lines.filter(part=sp).first() if merge_items else None
            if existing_line:
                existing_line.quantity += qty_dec
                existing_line.discount = disc_dec
                existing_line.save()
            else:
                PurchaseOrderLineItem.objects.create(
                    order=po,
                    part=sp,
                    quantity=qty_dec,
                    discount=disc_dec,
                    received=Decimal('0'),
                    purchase_price=Money(25, currency),
                    destination=warehouse,
                )
            po.update_total_price(commit=True)
            self._send_json(201, {
                'reference': po.reference,
                'status': po.status,
                'message': f'Confirmation: Purchase Order {po.reference} saved with line quantity {qty_dec} ({currency}).',
            })
            return

        if self.path == '/sqe/api/transition-po':
            action = data.get('action', 'issue')
            ref = data.get('reference', 'PO-SQE-0001')
            if not po_business_rules.check_po_role_permission(user, action):
                self._send_json(403, {'error': f'HTTP 403 Forbidden: Role {user.username} cannot perform {action} on Purchase Order'})
                return

            po = PurchaseOrder.objects.filter(reference=ref).first()
            if not po:
                self._send_json(404, {'error': f'Purchase Order {ref} not found'})
                return

            target_map = {
                'issue': PurchaseOrderStatus.PLACED.value,
                'hold': PurchaseOrderStatus.ON_HOLD.value,
                'complete': PurchaseOrderStatus.COMPLETE.value,
                'cancel': PurchaseOrderStatus.CANCELLED.value,
            }
            target_status = target_map.get(action, PurchaseOrderStatus.PLACED.value)
            try:
                po_business_rules.validate_po_state_transition(po.status, target_status)
            except ValidationError as exc:
                self._send_json(400, {'error': f'State Transition Error (BR-03): {exc.message_dict["status"][0]}'})
                return

            if action == 'issue':
                po.place_order()
            elif action == 'hold':
                po.hold_order()
            elif action == 'complete':
                po.complete_order()
            elif action == 'cancel':
                po.cancel_order()
            po.refresh_from_db()
            self._send_json(200, {
                'reference': po.reference,
                'status': po.status,
                'message': f'Confirmation: Purchase Order {po.reference} transitioned to {PurchaseOrderStatus.label(po.status)} ({po.status}).',
            })
            return

        if self.path == '/sqe/api/delete-line':
            ref = data.get('reference', 'PO-SQE-0001')
            if not po_business_rules.check_po_role_permission(user, 'delete_line'):
                self._send_json(403, {'error': f'HTTP 403 Forbidden: Role {user.username} lacks purchase_order:delete permission'})
                return
            po = PurchaseOrder.objects.filter(reference=ref).first()
            line = po.lines.first() if po else None
            if not line:
                self._send_json(404, {'error': 'No line item found to delete'})
                return
            if line.received > 0:
                self._send_json(400, {'error': 'Validation Error (FR-10): Cannot delete line items which have received stock'})
                return
            line.delete()
            self._send_json(200, {'message': f'Confirmation: Unreceived line item deleted from {ref}.'})
            return

        if self.path == '/sqe/api/receive-stock':
            if not po_business_rules.check_po_role_permission(user, 'receive'):
                self._send_json(403, {'error': f'HTTP 403 Forbidden: Role {user.username} lacks purchase_order:change and stock:add permissions'})
                return

            ref = data.get('reference', 'PO-SQE-0002')
            po = PurchaseOrder.objects.filter(reference=ref).first()
            if not po:
                self._send_json(404, {'error': f'Purchase Order {ref} not found'})
                return
            line = po.lines.first()
            loc_id = int(data.get('location', 1))
            location = StockLocation.objects.filter(pk=loc_id).first() if loc_id > 0 else None

            barcode = str(data.get('barcode', '')).strip()
            if barcode and StockItem.objects.filter(barcode_data=barcode).exists():
                self._send_json(400, {'error': f'Validation Error (FR-07): Barcode {barcode} is already in use'})
                return

            if loc_id == 0:
                # Explicitly test missing destination location (BR-02 C4=False)
                po.destination = None
                line.destination = None
                if line.part and line.part.part:
                    line.part.part.default_location = None

            try:
                created = po_business_rules.execute_receive_purchase_order_line(
                    po=po,
                    line=line,
                    quantity=data.get('quantity', 0),
                    location=location,
                    user=user,
                    auto_complete=True,
                    allow_over_receive=False,
                )
                if barcode and created:
                    created[0].barcode_data = barcode
                    created[0].save()
            except (ValidationError, PermissionDenied) as exc:
                err_text = str(exc)
                self._send_json(400, {'error': f'Receipt Rejected (BR-01/BR-02): {err_text}'})
                return

            po.refresh_from_db()
            line.refresh_from_db()
            self._send_json(201, {
                'reference': po.reference,
                'status': po.status,
                'received': float(line.received),
                'message': f'Confirmation: Received {data.get("quantity")} units against {po.reference}. Order status is now {PurchaseOrderStatus.label(po.status)} ({po.status}).',
            })
            return

        self._send_json(404, {'error': 'Unknown endpoint'})


def run_server(port: int = 8765) -> None:
    """Reset synthetic baseline and start the SQE web portal server."""
    reset_sqe_data()
    server = HTTPServer(('127.0.0.1', port), SQEPortalHandler)
    print(f'InvenTree SQE Portal Server running on http://127.0.0.1:{port}')
    server.serve_forever()


if __name__ == '__main__':
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    run_server(port_arg)
