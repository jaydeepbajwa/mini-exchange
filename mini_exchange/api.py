from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .engine import MatchingEngine
from .seed import seeded_engine


class OrderRequest(BaseModel):
    side: Literal["buy", "sell"]
    price: int = Field(ge=1)
    quantity: int = Field(ge=1, le=100_000)
    owner: str = Field(default="dashboard", min_length=1, max_length=64)


class Feed:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)
        await websocket.send_json(message("snapshot"))

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, payload: dict[str, object]) -> None:
        stale: list[WebSocket] = []
        for websocket in self.connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                # A client that dropped mid-send can raise RuntimeError,
                # WebSocketDisconnect, or a transport-specific ConnectionClosed
                # depending on timing — any send failure means the same thing:
                # prune the socket so it can't leak.
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


engine: MatchingEngine = seeded_engine()
engine_lock = asyncio.Lock()
feed = Feed()

DEMO_FLOW = [
    ("buy", 10020, 4),
    ("sell", 10010, 5),
    ("buy", 10025, 7),
    ("sell", 10005, 6),
    ("buy", 10030, 3),
    ("sell", 10000, 8),
    ("buy", 10015, 9),
    ("sell", 10035, 10),
]


def message(event_type: str, ack: object | None = None) -> dict[str, object]:
    return {
        "type": event_type,
        "snapshot": engine.snapshot().to_dict(),
        "latency": engine.latency_snapshot(),
        "ack": ack.to_dict() if ack is not None else None,
        "trades": ack.to_dict()["trades"] if ack is not None else [],
    }


# The scripted flow rests more volume than it consumes, so an unattended
# server would grow the book (and every full-snapshot broadcast) forever.
# Reset to the seeded book every few cycles to keep the demo bounded.
DEMO_RESET_EVERY = len(DEMO_FLOW) * 3


async def demo_flow() -> None:
    global engine
    index = 0
    while True:
        await asyncio.sleep(1.4)
        async with engine_lock:
            if index and index % DEMO_RESET_EVERY == 0:
                engine = seeded_engine()
                payload = message("reset")
            else:
                side, price, quantity = DEMO_FLOW[index % len(DEMO_FLOW)]
                ack = engine.submit_limit(
                    side=side,
                    price=price,
                    quantity=quantity,
                    owner="demo-flow",
                )
                payload = message("demo_order", ack)
            index += 1
        await feed.broadcast(payload)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(demo_flow())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Mini Exchange",
    description="Price-time matching engine with WebSocket market data.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, object]:
    snapshot = engine.snapshot(depth=1)
    return {
        "status": "ok",
        "symbol": engine.symbol,
        "sequence": engine.sequence,
        "best_bid": snapshot.best_bid,
        "best_ask": snapshot.best_ask,
    }


@app.get("/snapshot")
async def snapshot() -> dict[str, object]:
    async with engine_lock:
        return message("snapshot")


@app.post("/orders")
async def submit_order(order: OrderRequest) -> dict[str, object]:
    async with engine_lock:
        try:
            ack = engine.submit_limit(
                side=order.side,
                price=order.price,
                quantity=order.quantity,
                owner=order.owner,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = message("order_ack", ack)
    await feed.broadcast(payload)
    return payload


@app.post("/reset")
async def reset() -> dict[str, object]:
    global engine
    async with engine_lock:
        engine = seeded_engine()
        payload = message("reset")
    await feed.broadcast(payload)
    return payload


@app.websocket("/ws/market-data")
async def market_data(websocket: WebSocket) -> None:
    await feed.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        feed.disconnect(websocket)


def main() -> None:
    import uvicorn

    uvicorn.run("mini_exchange.api:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
