/**
 * SE3002 Software Quality Engineering - Section C
 * Step 5.1: Grafana k6 Load Testing Script (Purchase Order & Stock Receipt Workflow)
 * Owner: Salman Ahmed (24I-3004)
 *
 * Pre-Test Thresholds (Section 5.1):
 *   - 95th-percentile response time: p(95) <= 500 ms
 *   - Unexpected failure rate: http_req_failed < 1.0% (0.01)
 *
 * Workload Profile:
 *   - Constant VUs (1 VUser or 5 concurrent VUsers) for 60 seconds steady-state,
 *     on the exact same build, machine, and reset baseline DB.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const TARGET_VUS = __ENV.TARGET_VUS ? parseInt(__ENV.TARGET_VUS, 10) : 1;
const STEADY_DURATION = __ENV.STEADY_DURATION || '60s';
const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8765';

export const unexpectedFailureRate = new Rate('unexpected_failure_rate');
export const workflowDuration = new Trend('po_workflow_latency_ms', true);

export const options = {
  scenarios: {
    steady_state_load: {
      executor: 'constant-vus',
      vus: TARGET_VUS,
      duration: STEADY_DURATION,
      gracefulStop: '2s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<=500'],
    http_req_failed: ['rate<0.01'],
    unexpected_failure_rate: ['rate<0.01'],
  },
};

export default function () {
  // 1. Read current Purchase Orders and Stock Balances state (GET /sqe/api/state)
  const stateRes = http.get(`${BASE_URL}/sqe/api/state?role=purchasing_officer`, {
    tags: { operation: 'get_po_and_stock_state' },
  });

  const stateOk = check(stateRes, {
    'GET /sqe/api/state HTTP 200': (r) => r.status === 200,
    'GET /sqe/api/state returns orders & stock': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.orders) && typeof body.stock_count === 'number';
      } catch (e) {
        return false;
      }
    },
  });

  unexpectedFailureRate.add(!stateOk);
  workflowDuration.add(stateRes.timings.duration);

  // 2. Execute authenticated Purchase Order creation & line item validation cycle
  //    Merging into a per-VU active Purchase Order (PO-1001..PO-1005) prevents
  //    unbounded table bloat over 60s steady-state while exercising full DB write + total_price recalculation
  const numericRef = `PO-${1000 + __VU}`;
  const createPayload = JSON.stringify({
    role: 'purchasing_officer',
    reference: numericRef,
    description: `k6 load benchmark order VU=${__VU} iter=${__ITER}`,
    order_currency: 'USD',
    quantity: 1,
    purchase_price: 25.0,
    discount: 5.0,
    merge_items: true,
  });

  const createRes = http.post(`${BASE_URL}/sqe/api/create-po-and-line`, createPayload, {
    headers: { 'Content-Type': 'application/json' },
    tags: { operation: 'create_po_and_line_item' },
  });

  const createOk = check(createRes, {
    'POST /sqe/api/create-po-and-line HTTP 201 Created': (r) => r.status === 201,
  });

  unexpectedFailureRate.add(!createOk);
  workflowDuration.add(createRes.timings.duration);

  sleep(0.15);
}
