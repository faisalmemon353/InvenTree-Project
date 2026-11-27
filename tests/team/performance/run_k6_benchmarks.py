"""
SE3002 Software Quality Engineering — Section C
Step 5.1: Automated Grafana k6 Load Benchmark Runner (1-VU x 2 and 5-VU x 2, 60s each)
Owner: Salman Ahmed (24I-3004)

Requirements (Section 5.1):
  - Select 1 critical operation and set 1 response-time threshold (p95 <= 500 ms)
    and 1 failure-rate threshold (< 1.0%) before testing.
  - Run a load test (Grafana k6) with 1 simulated user and with 5 concurrent simulated users,
    each twice, measuring at least 60 seconds of steady-state load per run on the same build,
    machine, and starting data.
  - Report 95th-percentile response time (p95), requests completed per second (RPS),
    and failure percentage for each run.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PERF_DIR = REPO_ROOT / "tests" / "team" / "performance"
LOGS_DIR = PERF_DIR / "logs"
SUMMARY_JSON = PERF_DIR / "k6_benchmark_summary.json"
K6_SCRIPT = PERF_DIR / "po_load_test.js"
SERVER_SCRIPT = REPO_ROOT / "tests" / "team" / "e2e" / "sqe_web_portal_server.py"
BASE_URL = "http://127.0.0.1:8765"


def print_summary_table(data: dict) -> None:
    print("=" * 102)
    print("SQE SECTION C — GRAFANA k6 LOAD TESTING BENCHMARK SUMMARY (Salman Ahmed 24I-3004)")
    print("=" * 102)
    print(f"Target Operation       : {data['target_operation']}")
    print(
        f"Pre-Test Thresholds    : p95 <= {data['thresholds']['p95_ms_max']} ms | "
        f"Unexpected Failure Rate < {data['thresholds']['failure_rate_pct_max']}%"
    )
    print(f"Steady-State Duration  : {data['steady_state_duration_sec']} seconds per run (4 runs = 240s total load)")
    print("-" * 102)
    print(
        f"{'Run ID':<16} | {'VUsers':<8} | {'Duration':<10} | {'Total Reqs':<11} | "
        f"{'RPS (req/s)':<12} | {'p95 (ms)':<10} | {'Fail %':<8} | {'Verdict':<8}"
    )
    print("-" * 102)
    for r in data["runs"]:
        print(
            f"{r['run_id']:<16} | {r['vus']:<8} | {r['duration_sec']:<8}s | "
            f"{r['total_requests']:<11} | {r['rps']:<12.2f} | {r['p95_ms']:<10.2f} | "
            f"{r['failure_pct']:<7.2f}% | {r['verdict']:<8}"
        )
    print("-" * 102)
    agg = data["aggregates"]
    print(
        f"1-VU Mean (Runs 1A & 1B) : p95 = {agg['1vu_mean_p95_ms']:.2f} ms | "
        f"RPS = {agg['1vu_mean_rps']:.2f} req/s | Failure Rate = {agg['1vu_mean_failure_pct']:.2f}%"
    )
    print(
        f"5-VU Mean (Runs 2A & 2B) : p95 = {agg['5vu_mean_p95_ms']:.2f} ms | "
        f"RPS = {agg['5vu_mean_rps']:.2f} req/s | Failure Rate = {agg['5vu_mean_failure_pct']:.2f}%"
    )
    print("=" * 102)


def reset_starting_data() -> None:
    req = urllib.request.Request(
        f"{BASE_URL}/sqe/api/reset",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        assert resp.status == 200


def run_all_benchmarks(duration_sec: int = 60) -> dict:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Start the local SQE portal server if not already listening
    server_proc = None
    try:
        urllib.request.urlopen(f"{BASE_URL}/sqe/api/state", timeout=2)
    except Exception:
        server_proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            try:
                urllib.request.urlopen(f"{BASE_URL}/sqe/api/state", timeout=2)
                break
            except Exception:
                time.sleep(0.5)

    run_configs = [
        ("Run-1A (1-VU #1)", 1, "run_1vu_1"),
        ("Run-1B (1-VU #2)", 1, "run_1vu_2"),
        ("Run-2A (5-VU #1)", 5, "run_5vu_1"),
        ("Run-2B (5-VU #2)", 5, "run_5vu_2"),
    ]

    runs_output = []
    try:
        for run_label, vus, slug in run_configs:
            # Ensure identical starting data before each run + 3-request warm-up
            reset_starting_data()
            for _ in range(3):
                urllib.request.urlopen(f"{BASE_URL}/sqe/api/state", timeout=5).read()

            summary_export_path = LOGS_DIR / f"{slug}_summary.json"
            txt_log_path = LOGS_DIR / f"{slug}.txt"

            cmd = [
                "k6",
                "run",
                "--env",
                f"TARGET_VUS={vus}",
                "--env",
                f"STEADY_DURATION={duration_sec}s",
                "--env",
                f"BASE_URL={BASE_URL}",
                "--summary-export",
                str(summary_export_path),
                str(K6_SCRIPT),
            ]
            print(f"Executing {run_label}: VUs={vus}, Duration={duration_sec}s ...")
            proc = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            txt_log_path.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")

            raw = json.loads(summary_export_path.read_text(encoding="utf-8"))
            metrics = raw["metrics"]
            p95_ms = float(metrics["http_req_duration"]["p(95)"])
            med_ms = float(metrics["http_req_duration"]["med"])
            avg_ms = float(metrics["http_req_duration"]["avg"])
            max_ms = float(metrics["http_req_duration"]["max"])
            total_reqs = int(metrics["http_reqs"]["count"])
            rps = float(metrics["http_reqs"]["rate"])
            unexp_fail_rate = float(metrics.get("unexpected_failure_rate", {}).get("value", 0.0)) * 100.0

            reset_starting_data()

            passed = p95_ms <= 500.0 and unexp_fail_rate < 1.0
            runs_output.append(
                {
                    "run_id": run_label,
                    "slug": slug,
                    "vus": vus,
                    "duration_sec": duration_sec,
                    "total_requests": total_reqs,
                    "rps": round(rps, 2),
                    "avg_ms": round(avg_ms, 2),
                    "median_ms": round(med_ms, 2),
                    "p95_ms": round(p95_ms, 2),
                    "max_ms": round(max_ms, 2),
                    "failure_pct": round(unexp_fail_rate, 2),
                    "verdict": "PASS" if passed else "FAIL",
                }
            )
    finally:
        try:
            reset_starting_data()
        except Exception:
            pass
        if server_proc is not None:
            server_proc.terminate()

    r1 = [r for r in runs_output if r["vus"] == 1]
    r5 = [r for r in runs_output if r["vus"] == 5]

    summary_data = {
        "target_operation": "GET /sqe/api/state & POST /sqe/api/create-po-and-line (Purchase Order & Stock State Cycle)",
        "tool": "Grafana k6 v2.2.0",
        "steady_state_duration_sec": duration_sec,
        "thresholds": {
            "p95_ms_max": 500.0,
            "failure_rate_pct_max": 1.0,
        },
        "runs": runs_output,
        "aggregates": {
            "1vu_mean_p95_ms": round(sum(r["p95_ms"] for r in r1) / len(r1), 2),
            "1vu_mean_rps": round(sum(r["rps"] for r in r1) / len(r1), 2),
            "1vu_mean_failure_pct": round(sum(r["failure_pct"] for r in r1) / len(r1), 2),
            "5vu_mean_p95_ms": round(sum(r["p95_ms"] for r in r5) / len(r5), 2),
            "5vu_mean_rps": round(sum(r["rps"] for r in r5) / len(r5), 2),
            "5vu_mean_failure_pct": round(sum(r["failure_pct"] for r in r5) / len(r5), 2),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print_summary_table(summary_data)
    return summary_data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Display stored k6 benchmark summary table from k6_benchmark_summary.json without re-running 240s load",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Steady-state duration in seconds per run (default: 60)",
    )
    args = parser.parse_args()

    if args.summary_only and SUMMARY_JSON.exists():
        data = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
        print_summary_table(data)
    else:
        run_all_benchmarks(duration_sec=args.duration)


if __name__ == "__main__":
    main()
