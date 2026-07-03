"""Measure matching-engine latency and throughput.

The README quotes numbers from this script so they are reproducible, not
invented. Run it yourself:

    python3 scripts/bench.py

Deterministic order flow (seeded RNG), timed around engine.submit_limit()
only — no network, no serialization, no event loop.
"""

from __future__ import annotations

import platform
import random
import statistics
from time import perf_counter_ns

from mini_exchange.engine import MatchingEngine

ORDERS = 100_000
PRICE_BAND = (9_900, 10_100)
MAX_QUANTITY = 50
SEED = 7


def run() -> None:
    rng = random.Random(SEED)
    engine = MatchingEngine()
    samples_ns: list[int] = []

    for _ in range(ORDERS):
        side = "buy" if rng.random() < 0.5 else "sell"
        price = rng.randint(*PRICE_BAND)
        quantity = rng.randint(1, MAX_QUANTITY)
        started = perf_counter_ns()
        engine.submit_limit(side=side, price=price, quantity=quantity, owner="bench")
        samples_ns.append(perf_counter_ns() - started)

    total_s = sum(samples_ns) / 1_000_000_000
    quantiles = statistics.quantiles([s / 1_000 for s in samples_ns], n=100)
    snapshot = engine.snapshot()

    print(f"machine:    {platform.machine()} / Python {platform.python_version()}")
    print(f"orders:     {ORDERS:,} (seeded RNG, band {PRICE_BAND[0]}-{PRICE_BAND[1]})")
    print(f"throughput: {ORDERS / total_s:,.0f} orders/sec (matching time only)")
    print(f"p50:        {quantiles[49]:.1f} us")
    print(f"p99:        {quantiles[98]:.1f} us")
    print(f"book depth: {len(engine.bids)} bid levels / {len(engine.asks)} ask levels")
    if snapshot.best_bid is not None and snapshot.best_ask is not None:
        assert snapshot.best_bid < snapshot.best_ask, "book crossed during bench"
        print(f"final book: {snapshot.best_bid} / {snapshot.best_ask} (uncrossed)")


if __name__ == "__main__":
    run()
