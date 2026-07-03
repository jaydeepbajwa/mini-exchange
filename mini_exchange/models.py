from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"

    @property
    def opposite(self) -> "Side":
        return Side.SELL if self is Side.BUY else Side.BUY


@dataclass
class RestingOrder:
    order_id: str
    side: Side
    price: int
    remaining: int
    owner: str
    sequence: int
    received_at_ns: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "order_id": self.order_id,
            "side": self.side.value,
            "price": self.price,
            "remaining": self.remaining,
            "owner": self.owner,
            "sequence": self.sequence,
            "received_at_ns": self.received_at_ns,
        }


@dataclass(frozen=True)
class Trade:
    trade_id: str
    taker_order_id: str
    maker_order_id: str
    side: str
    price: int
    quantity: int
    sequence: int
    occurred_at_ns: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "trade_id": self.trade_id,
            "taker_order_id": self.taker_order_id,
            "maker_order_id": self.maker_order_id,
            "side": self.side,
            "price": self.price,
            "quantity": self.quantity,
            "sequence": self.sequence,
            "occurred_at_ns": self.occurred_at_ns,
        }


@dataclass(frozen=True)
class BookLevel:
    price: int
    quantity: int
    order_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "price": self.price,
            "quantity": self.quantity,
            "order_count": self.order_count,
        }


@dataclass(frozen=True)
class BookSnapshot:
    symbol: str
    sequence: int
    bids: list[BookLevel]
    asks: list[BookLevel]

    @property
    def best_bid(self) -> int | None:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> int | None:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "sequence": self.sequence,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid_price": self.mid_price,
            "bids": [level.to_dict() for level in self.bids],
            "asks": [level.to_dict() for level in self.asks],
        }


@dataclass(frozen=True)
class OrderAck:
    order_id: str
    status: str
    side: Side
    price: int
    requested_quantity: int
    rested_quantity: int
    trades: list[Trade]
    latency_us: float

    def to_dict(self) -> dict[str, object]:
        return {
            "order_id": self.order_id,
            "status": self.status,
            "side": self.side.value,
            "price": self.price,
            "requested_quantity": self.requested_quantity,
            "rested_quantity": self.rested_quantity,
            "trades": [trade.to_dict() for trade in self.trades],
            "latency_us": self.latency_us,
        }
