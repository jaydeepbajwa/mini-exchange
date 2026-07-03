from __future__ import annotations

import math
from collections import deque
from time import perf_counter_ns
from typing import Deque

from .models import BookLevel, BookSnapshot, OrderAck, RestingOrder, Side, Trade


class LatencyRecorder:
    def __init__(self, max_samples: int = 1_000) -> None:
        self.max_samples = max_samples
        self.samples_us: Deque[float] = deque(maxlen=max_samples)

    def record(self, elapsed_ns: int) -> float:
        elapsed_us = elapsed_ns / 1_000
        self.samples_us.append(elapsed_us)
        return elapsed_us

    def snapshot(self) -> dict[str, float | int]:
        values = sorted(self.samples_us)
        return {
            "count": len(values),
            "last_us": values[-1] if values else 0.0,
            "p50_us": self._percentile(values, 0.50),
            "p99_us": self._percentile(values, 0.99),
        }

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        index = max(0, min(len(values) - 1, math.ceil(percentile * len(values)) - 1))
        return values[index]


class MatchingEngine:
    """Single-symbol limit order book with strict price-time matching."""

    def __init__(self, symbol: str = "LOOPFX") -> None:
        self.symbol = symbol
        self.bids: dict[int, Deque[RestingOrder]] = {}
        self.asks: dict[int, Deque[RestingOrder]] = {}
        self.sequence = 0
        self._next_order_number = 1
        self._next_trade_number = 1
        self._latency = LatencyRecorder()

    def submit_limit(
        self,
        *,
        side: Side | str,
        price: int,
        quantity: int,
        owner: str = "demo",
    ) -> OrderAck:
        parsed_side = self._parse_side(side)
        self._validate_price(price)
        self._validate_quantity(quantity)

        started_ns = perf_counter_ns()
        order_id = self._next_order_id()
        requested_quantity = quantity
        trades: list[Trade] = []

        while quantity > 0 and self._crosses(parsed_side, price):
            resting_price = self._best_price(parsed_side.opposite)
            if resting_price is None:
                break

            resting_level = self._book_for(parsed_side.opposite)[resting_price]
            while quantity > 0 and resting_level:
                maker = resting_level[0]
                fill_quantity = min(quantity, maker.remaining)
                maker.remaining -= fill_quantity
                quantity -= fill_quantity
                trades.append(
                    Trade(
                        trade_id=self._next_trade_id(),
                        taker_order_id=order_id,
                        maker_order_id=maker.order_id,
                        side=parsed_side.value,
                        price=maker.price,
                        quantity=fill_quantity,
                        sequence=self._next_sequence(),
                        occurred_at_ns=perf_counter_ns(),
                    )
                )
                if maker.remaining == 0:
                    resting_level.popleft()

            if not resting_level:
                del self._book_for(parsed_side.opposite)[resting_price]

        if quantity > 0:
            self._add_resting_order(
                RestingOrder(
                    order_id=order_id,
                    side=parsed_side,
                    price=price,
                    remaining=quantity,
                    owner=owner,
                    sequence=self._next_sequence(),
                    received_at_ns=perf_counter_ns(),
                )
            )

        latency_us = self._latency.record(perf_counter_ns() - started_ns)
        return OrderAck(
            order_id=order_id,
            status=self._status(requested_quantity, quantity, trades),
            side=parsed_side,
            price=price,
            requested_quantity=requested_quantity,
            rested_quantity=quantity,
            trades=trades,
            latency_us=latency_us,
        )

    def snapshot(self, depth: int = 10) -> BookSnapshot:
        return BookSnapshot(
            symbol=self.symbol,
            sequence=self.sequence,
            bids=self._levels(Side.BUY, depth),
            asks=self._levels(Side.SELL, depth),
        )

    def latency_snapshot(self) -> dict[str, float | int]:
        return self._latency.snapshot()

    def _add_resting_order(self, order: RestingOrder) -> None:
        book = self._book_for(order.side)
        if order.price not in book:
            book[order.price] = deque()
        book[order.price].append(order)

    def _book_for(self, side: Side) -> dict[int, Deque[RestingOrder]]:
        return self.bids if side is Side.BUY else self.asks

    def _best_price(self, side: Side) -> int | None:
        book = self._book_for(side)
        if not book:
            return None
        return max(book) if side is Side.BUY else min(book)

    def _crosses(self, side: Side, limit_price: int) -> bool:
        best_opposite = self._best_price(side.opposite)
        if best_opposite is None:
            return False
        if side is Side.BUY:
            return limit_price >= best_opposite
        return limit_price <= best_opposite

    def _levels(self, side: Side, depth: int) -> list[BookLevel]:
        prices = sorted(self._book_for(side), reverse=side is Side.BUY)
        levels: list[BookLevel] = []
        for price in prices[:depth]:
            orders = self._book_for(side)[price]
            levels.append(
                BookLevel(
                    price=price,
                    quantity=sum(order.remaining for order in orders),
                    order_count=len(orders),
                )
            )
        return levels

    def _next_order_id(self) -> str:
        order_id = f"O{self._next_order_number:06d}"
        self._next_order_number += 1
        return order_id

    def _next_trade_id(self) -> str:
        trade_id = f"T{self._next_trade_number:06d}"
        self._next_trade_number += 1
        return trade_id

    def _next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    @staticmethod
    def _parse_side(side: Side | str) -> Side:
        try:
            return side if isinstance(side, Side) else Side(side)
        except ValueError as exc:
            raise ValueError("side must be 'buy' or 'sell'; choose one and retry") from exc

    @staticmethod
    def _validate_price(price: int) -> None:
        if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
            raise ValueError(
                "price must be positive integer ticks; send cents like 10025 for $100.25"
            )

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("quantity must be a positive integer lot size; adjust and retry")

    @staticmethod
    def _status(
        requested_quantity: int,
        rested_quantity: int,
        trades: list[Trade],
    ) -> str:
        if rested_quantity == 0:
            return "filled"
        if trades and rested_quantity < requested_quantity:
            return "partial"
        return "resting"
