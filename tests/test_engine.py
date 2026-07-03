from __future__ import annotations

import unittest

from mini_exchange import MatchingEngine


class MatchingEngineTests(unittest.TestCase):
    def test_same_price_orders_match_fifo(self) -> None:
        engine = MatchingEngine()
        first = engine.submit_limit(side="sell", price=10000, quantity=5, owner="maker-a")
        second = engine.submit_limit(side="sell", price=10000, quantity=5, owner="maker-b")

        ack = engine.submit_limit(side="buy", price=10000, quantity=7, owner="taker")

        self.assertEqual(ack.status, "filled")
        self.assertEqual([trade.maker_order_id for trade in ack.trades], [first.order_id, second.order_id])
        self.assertEqual([trade.quantity for trade in ack.trades], [5, 2])
        self.assertEqual(engine.snapshot().asks[0].quantity, 3)

    def test_better_price_matches_before_older_worse_price(self) -> None:
        engine = MatchingEngine()
        worse = engine.submit_limit(side="sell", price=10100, quantity=4, owner="older")
        better = engine.submit_limit(side="sell", price=10050, quantity=4, owner="newer")

        ack = engine.submit_limit(side="buy", price=10100, quantity=8, owner="taker")

        self.assertEqual(ack.status, "filled")
        self.assertEqual([trade.maker_order_id for trade in ack.trades], [better.order_id, worse.order_id])
        self.assertEqual([trade.price for trade in ack.trades], [10050, 10100])

    def test_incoming_quantity_is_conserved_between_trades_and_resting(self) -> None:
        engine = MatchingEngine()
        engine.submit_limit(side="sell", price=10000, quantity=3)

        ack = engine.submit_limit(side="buy", price=10000, quantity=10)

        traded_quantity = sum(trade.quantity for trade in ack.trades)
        self.assertEqual(ack.requested_quantity, traded_quantity + ack.rested_quantity)
        self.assertEqual(ack.rested_quantity, 7)
        self.assertEqual(engine.snapshot().bids[0].quantity, 7)

    def test_sell_taker_matches_resting_bids_symmetrically(self) -> None:
        # The buy-taker path is exercised above; this covers the mirrored
        # branch where bids rest and an aggressive sell sweeps them.
        engine = MatchingEngine()
        best = engine.submit_limit(side="buy", price=10010, quantity=4, owner="bid-best")
        worse = engine.submit_limit(side="buy", price=10005, quantity=4, owner="bid-worse")

        ack = engine.submit_limit(side="sell", price=10005, quantity=6, owner="taker")

        self.assertEqual(ack.status, "filled")
        self.assertEqual(
            [trade.maker_order_id for trade in ack.trades], [best.order_id, worse.order_id]
        )
        # Taker sells into the best bid first and gets price improvement there
        self.assertEqual([trade.price for trade in ack.trades], [10010, 10005])
        self.assertEqual(engine.snapshot().bids[0].quantity, 2)

    def test_book_never_crosses_across_a_mixed_sequence(self) -> None:
        engine = MatchingEngine()
        flow = [
            ("buy", 10000, 5),
            ("sell", 10010, 5),
            ("buy", 10012, 3),   # crosses the ask
            ("sell", 9990, 4),   # crosses the bid
            ("buy", 10005, 6),
            ("sell", 10005, 2),  # crosses at the touch
            ("buy", 10030, 9),   # sweeps
            ("sell", 9980, 9),   # sweeps back
        ]
        for side, price, quantity in flow:
            engine.submit_limit(side=side, price=price, quantity=quantity)
            snapshot = engine.snapshot()
            if snapshot.best_bid is not None and snapshot.best_ask is not None:
                self.assertLess(
                    snapshot.best_bid,
                    snapshot.best_ask,
                    f"book crossed after {side} {quantity}@{price}",
                )

    def test_latency_last_us_is_most_recent_not_max(self) -> None:
        from mini_exchange.engine import LatencyRecorder

        recorder = LatencyRecorder()
        recorder.record(9_000)  # 9.0 us — the max
        recorder.record(1_000)  # 1.0 us — the most recent

        snapshot = recorder.snapshot()
        self.assertEqual(snapshot["last_us"], 1.0)
        self.assertEqual(snapshot["p99_us"], 9.0)

    def test_rejections_tell_callers_how_to_recover(self) -> None:
        engine = MatchingEngine()

        with self.assertRaisesRegex(ValueError, "positive integer ticks"):
            engine.submit_limit(side="buy", price=0, quantity=1)

        with self.assertRaisesRegex(ValueError, "positive integer lot size"):
            engine.submit_limit(side="sell", price=10000, quantity=0)

        with self.assertRaisesRegex(ValueError, "choose one and retry"):
            engine.submit_limit(side="hold", price=10000, quantity=1)


if __name__ == "__main__":
    unittest.main()
