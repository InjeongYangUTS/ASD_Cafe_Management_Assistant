"""
Student 4 (Stella Kwon) - Order & Kitchen Management
Non-functional requirement measurements.

Produces the response-time and throughput figures quoted in section 2.5.2 of
the technical report. Run it against whichever stack you want to report on -
the local dev servers or the Docker containers - and paste the table.

    python3 tests/nfr_bench.py
    python3 tests/nfr_bench.py --samples 50

Reports, per endpoint: mean, median (p50) and 95th percentile in milliseconds,
then a concurrency check and the cost of a write that fans out to Student 2's
Menu API and Student 3's Inventory API.
"""

import argparse
import concurrent.futures as futures
import statistics
import time

import requests

DB_URL = "http://localhost:7400"
BACKEND_URL = "http://localhost:8400"
FRONTEND_URL = "http://localhost:5400"

ENDPOINTS = [
    ("GET /api/orders (list with items)", BACKEND_URL + "/api/orders?limit=50"),
    ("GET /api/order-status (kitchen board)", BACKEND_URL + "/api/order-status"),
    ("GET /api/menu (read-through to Student 2)", BACKEND_URL + "/api/menu"),
    ("GET /db/orders/1 (database service)", DB_URL + "/db/orders/1"),
    ("GET /kitchen (rendered page)", FRONTEND_URL + "/kitchen"),
    ("GET /ui/kitchen/board (HTMX partial)", FRONTEND_URL + "/ui/kitchen/board"),
]

# Service targets stated in the report as NFR2.
TARGET_P95_MS = 300


def sample(url, n):
    times = []
    ok = True
    for _ in range(n):
        start = time.perf_counter()
        try:
            response = requests.get(url, timeout=15)
            ok = ok and response.status_code < 400
        except requests.RequestException:
            ok = False
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    return {
        "mean": statistics.mean(times),
        "p50": times[len(times) // 2],
        "p95": times[max(0, int(len(times) * 0.95) - 1)],
        "ok": ok,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--concurrent", type=int, default=100)
    args = parser.parse_args()

    print("Student 4 - NFR measurements  (%d samples per endpoint)\n"
          % args.samples)
    print("%-44s %8s %8s %8s  %s" % ("Endpoint", "mean", "p50", "p95", "target"))
    print("-" * 82)

    worst = 0.0
    for label, url in ENDPOINTS:
        result = sample(url, args.samples)
        worst = max(worst, result["p95"])
        verdict = "PASS" if result["p95"] < TARGET_P95_MS and result["ok"] else "FAIL"
        print("%-44s %7.1fms %7.1fms %7.1fms  %s"
              % (label, result["mean"], result["p50"], result["p95"], verdict))

    print("\nNFR2  p95 under %d ms on every endpoint: %s (worst %.1f ms)"
          % (TARGET_P95_MS, "PASS" if worst < TARGET_P95_MS else "FAIL", worst))

    # ---- concurrency -------------------------------------------------
    start = time.perf_counter()
    with futures.ThreadPoolExecutor(20) as pool:
        codes = list(pool.map(
            lambda _: requests.get(BACKEND_URL + "/api/order-status",
                                   timeout=30).status_code,
            range(args.concurrent),
        ))
    elapsed = time.perf_counter() - start

    print("\nNFR3  %d concurrent reads (20 threads): %.2fs, %.0f req/s, "
          "all 200: %s"
          % (args.concurrent, elapsed, args.concurrent / elapsed,
             all(code == 200 for code in codes)))

    # ---- a write that fans out to two peer services -------------------
    start = time.perf_counter()
    created = requests.post(
        BACKEND_URL + "/api/orders",
        json={"channel": "TAKEAWAY", "customer_name": "NFR benchmark",
              "items": [{"menu_id": 2, "quantity": 2}]},
        timeout=30,
    )
    write_ms = (time.perf_counter() - start) * 1000

    if created.status_code == 201:
        order = created.json()["order"]
        integration = created.json()["integration"]
        print("\nNFR4  POST /api/orders end to end: %.0f ms "
              "(price source: %s, stock deducted: %s)"
              % (write_ms, integration["price_source"],
                 integration["stock_deducted"]))
        requests.delete(DB_URL + "/db/orders/%d" % order["id"], timeout=15)
        print("      benchmark order removed - no test data left behind")
    else:
        print("\nNFR4  POST /api/orders failed: %d" % created.status_code)


if __name__ == "__main__":
    main()
