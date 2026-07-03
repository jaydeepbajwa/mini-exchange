from __future__ import annotations

from .engine import MatchingEngine


SEED_ORDERS = [
    ("buy", 10010, 14, "seed-bid-a"),
    ("buy", 10005, 22, "seed-bid-b"),
    ("buy", 10000, 31, "seed-bid-c"),
    ("buy", 9995, 18, "seed-bid-d"),
    ("sell", 10020, 16, "seed-ask-a"),
    ("sell", 10025, 24, "seed-ask-b"),
    ("sell", 10030, 27, "seed-ask-c"),
    ("sell", 10035, 19, "seed-ask-d"),
]


def seeded_engine() -> MatchingEngine:
    engine = MatchingEngine()
    for side, price, quantity, owner in SEED_ORDERS:
        engine.submit_limit(side=side, price=price, quantity=quantity, owner=owner)
    return engine
