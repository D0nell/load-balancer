"""
Task 4 - Performance Analysis
Run: python analysis/test.py [a1|a2|a3|a4]
Requires: pip install aiohttp matplotlib requests
"""

import asyncio
import os
import sys
import time
from collections import Counter

import aiohttp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests

BASE_URL = "http://localhost:5000"
TOTAL_REQUESTS = 10_000
CONCURRENCY = 50  # max simultaneous requests
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


async def _fetch(session, semaphore, url):
    async with semaphore:
        for attempt in range(3):  # retry up to 3 times
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        msg = data.get("message", "")
                        return msg.replace("Hello from ", "").strip()
            except Exception:
                await asyncio.sleep(0.1 * (attempt + 1))
    return None


async def _load_test(n_requests=TOTAL_REQUESTS):
    url = f"{BASE_URL}/home"
    semaphore = asyncio.Semaphore(CONCURRENCY)
    connector = aiohttp.TCPConnector(limit=CONCURRENCY)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_fetch(session, semaphore, url) for _ in range(n_requests)]
        results = await asyncio.gather(*tasks)

    counter = Counter(r for r in results if r)
    failed = sum(1 for r in results if r is None)
    if failed:
        print(f"  Warning: {failed} requests failed")
    return counter


def _set_replicas(target_n):
    resp = requests.get(f"{BASE_URL}/rep", timeout=5).json()
    current = resp["message"]["replicas"]
    current_n = len(current)

    if current_n < target_n:
        requests.post(f"{BASE_URL}/add",
                      json={"n": target_n - current_n, "hostnames": []}, timeout=15)
    elif current_n > target_n:
        requests.delete(f"{BASE_URL}/rm",
                        json={"n": current_n - target_n, "hostnames": []}, timeout=15)

    time.sleep(6)  # wait for containers to be fully up


def experiment_a1():
    print("\n=== A-1: 10 000 requests across N=3 servers ===")
    _set_replicas(3)

    counter = asyncio.run(_load_test(TOTAL_REQUESTS))
    servers = sorted(counter.keys())
    counts = [counter[s] for s in servers]
    total = sum(counts)
    ideal = total / len(servers) if servers else 0

    print(f"  Total successful: {total}")
    print(f"  Distribution: { {s: counter[s] for s in servers} }")
    print(f"  Ideal per server: {ideal:.0f}")

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(servers, counts, color="steelblue", edgecolor="black", width=0.5)
    ax.bar_label(bars, padding=4, fontsize=10)
    ax.axhline(ideal, color="red", linestyle="--", linewidth=1.5,
               label=f"Ideal ({ideal:.0f})")
    ax.set_title("A-1: Request Distribution across N=3 Server Replicas\n(10 000 async requests)", fontsize=13)
    ax.set_xlabel("Server", fontsize=11)
    ax.set_ylabel("Requests Handled", fontsize=11)
    ax.set_ylim(0, max(counts) * 1.2)
    ax.legend()
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, "a1_bar_chart.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved → {path}")


def experiment_a2():
    print("\n=== A-2: Scalability — N from 2 to 6 ===")

    n_values = list(range(2, 7))
    actual_avgs = []
    ideal_avgs = []

    for n in n_values:
        print(f"  Testing N={n} …")
        _set_replicas(n)

        counter = asyncio.run(_load_test(TOTAL_REQUESTS))
        actual_avg = sum(counter.values()) / len(counter) if counter else 0
        ideal_avg = TOTAL_REQUESTS / n

        actual_avgs.append(actual_avg)
        ideal_avgs.append(ideal_avg)
        print(f"    Ideal={ideal_avg:.0f}  Actual avg={actual_avg:.0f}  "
              f"Total successful={sum(counter.values())}  Servers hit={len(counter)}")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(n_values, actual_avgs, marker="o", color="steelblue",
            linewidth=2, label="Actual avg load")
    ax.plot(n_values, ideal_avgs, marker="s", color="red",
            linewidth=2, linestyle="--", label="Ideal avg load")
    ax.set_title("A-2: Average Server Load vs Number of Replicas\n(10 000 async requests per run)", fontsize=13)
    ax.set_xlabel("Number of Server Replicas (N)", fontsize=11)
    ax.set_ylabel("Avg Requests per Server", fontsize=11)
    ax.set_xticks(n_values)
    ax.legend()
    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, "a2_line_chart.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  Saved → {path}")


def experiment_a3():
    print("\n=== A-3: Endpoint tests + failure recovery ===")
    _set_replicas(3)

    r = requests.get(f"{BASE_URL}/rep", timeout=5)
    print(f"\n  GET /rep → {r.status_code}: {r.json()}")

    r = requests.get(f"{BASE_URL}/home", timeout=5)
    print(f"\n  GET /home → {r.status_code}: {r.json()}")

    r = requests.get(f"{BASE_URL}/other", timeout=5)
    print(f"\n  GET /other → {r.status_code}: {r.json()}")

    r = requests.post(f"{BASE_URL}/add",
                      json={"n": 1, "hostnames": ["test_server"]}, timeout=10)
    print(f"\n  POST /add → {r.status_code}: {r.json()}")

    r = requests.delete(f"{BASE_URL}/rm",
                        json={"n": 1, "hostnames": ["test_server"]}, timeout=10)
    print(f"\n  DELETE /rm → {r.status_code}: {r.json()}")

    replicas = requests.get(f"{BASE_URL}/rep", timeout=5).json()["message"]["replicas"]
    victim = replicas[0]
    print(f"\n  Killing '{victim}' to simulate failure...")
    os.system(f"docker stop {victim} && docker rm {victim}")

    print("  Waiting 8s for heartbeat to detect and replace...")
    time.sleep(8)

    r = requests.get(f"{BASE_URL}/rep", timeout=5)
    print(f"\n  GET /rep after recovery → {r.status_code}: {r.json()}")


def experiment_a4():
    print("\n=== A-4: Modified hash functions ===")
    print("""
  To test with alternative hash functions, edit consistent_hash.py:

  Change _hash_virtual_server to use the assignment spec polynomial directly:
    def _hash_virtual_server(self, i, j):
        return (i**2 + j**2 + 2*j + 25) % self.slots

  And pass sequential server IDs instead of name-based hashes.
  Observation: slots cluster in a small region of the ring (slots 26-114
  for the first 3 servers), causing severe load imbalance — server_1 handles
  ~85% of traffic. This demonstrates WHY name-based or MD5 hashing is needed
  for real-world consistent hashing implementations.

  Current implementation uses MD5(server_name:j) for virtual server placement,
  which distributes slots evenly across all 512 ring positions.
    """)


EXPERIMENTS = {
    "a1": experiment_a1,
    "a2": experiment_a2,
    "a3": experiment_a3,
    "a4": experiment_a4,
}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        key = sys.argv[1].lower()
        fn = EXPERIMENTS.get(key)
        if fn:
            fn()
        else:
            print(f"Unknown experiment '{key}'. Choose from: {list(EXPERIMENTS)}")
    else:
        for name, fn in EXPERIMENTS.items():
            fn()