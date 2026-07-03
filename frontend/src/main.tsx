import React from "react";
import ReactDOM from "react-dom/client";
import { Activity, RefreshCw, SendHorizontal, Wifi, WifiOff } from "lucide-react";
import "./styles.css";

type Side = "buy" | "sell";

type Level = {
  price: number;
  quantity: number;
  order_count: number;
};

type Snapshot = {
  symbol: string;
  sequence: number;
  best_bid: number | null;
  best_ask: number | null;
  mid_price: number | null;
  bids: Level[];
  asks: Level[];
};

type Trade = {
  trade_id: string;
  maker_order_id: string;
  taker_order_id: string;
  side: Side;
  price: number;
  quantity: number;
  sequence: number;
};

type Latency = {
  count: number;
  last_us: number;
  p50_us: number;
  p99_us: number;
};

type MarketMessage = {
  type: string;
  snapshot: Snapshot;
  latency: Latency;
  trades: Trade[];
  ack: {
    order_id: string;
    status: string;
    latency_us: number;
  } | null;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const WS_URL =
  import.meta.env.VITE_WS_URL ??
  `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000/ws/market-data`;

const emptySnapshot: Snapshot = {
  symbol: "LOOPFX",
  sequence: 0,
  best_bid: null,
  best_ask: null,
  mid_price: null,
  bids: [],
  asks: [],
};

function formatPrice(price: number | null): string {
  if (price === null) {
    return "--";
  }
  return `$${(price / 100).toFixed(2)}`;
}

function formatLatency(value: number): string {
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(2)} ms`;
  }
  return `${value.toFixed(1)} us`;
}

function useMarketData() {
  const [snapshot, setSnapshot] = React.useState<Snapshot>(emptySnapshot);
  const [latency, setLatency] = React.useState<Latency>({
    count: 0,
    last_us: 0,
    p50_us: 0,
    p99_us: 0,
  });
  const [trades, setTrades] = React.useState<Trade[]>([]);
  const [connected, setConnected] = React.useState(false);

  React.useEffect(() => {
    let websocket: WebSocket | null = null;
    let retry: number | undefined;
    let closed = false;

    const connect = () => {
      websocket = new WebSocket(WS_URL);

      websocket.onopen = () => setConnected(true);
      websocket.onmessage = (event) => {
        const payload = JSON.parse(event.data) as MarketMessage;
        setSnapshot(payload.snapshot);
        setLatency(payload.latency);
        if (payload.trades.length > 0) {
          setTrades((current) => [...payload.trades, ...current].slice(0, 16));
        }
      };
      websocket.onclose = () => {
        setConnected(false);
        if (!closed) {
          retry = window.setTimeout(connect, 1_000);
        }
      };
    };

    connect();

    return () => {
      closed = true;
      if (retry !== undefined) {
        window.clearTimeout(retry);
      }
      websocket?.close();
    };
  }, []);

  return { snapshot, latency, trades, connected };
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LevelRow({ level, maxQuantity, side }: { level: Level; maxQuantity: number; side: Side }) {
  const width = maxQuantity === 0 ? 0 : Math.max(7, (level.quantity / maxQuantity) * 100);
  return (
    <div className={`level level-${side}`}>
      <span className="level-price">{formatPrice(level.price)}</span>
      <div className="level-bar" style={{ width: `${width}%` }} />
      <span className="level-quantity">{level.quantity}</span>
      <span className="level-count">{level.order_count}</span>
    </div>
  );
}

function BookSide({ title, levels, side }: { title: string; levels: Level[]; side: Side }) {
  const maxQuantity = Math.max(0, ...levels.map((level) => level.quantity));
  const visibleLevels = side === "sell" ? [...levels].reverse() : levels;

  return (
    <section className="book-side" aria-label={title}>
      <div className="side-heading">
        <span>{title}</span>
        <span>Qty</span>
        <span>Orders</span>
      </div>
      <div className="levels">
        {visibleLevels.map((level) => (
          <LevelRow key={`${side}-${level.price}`} level={level} maxQuantity={maxQuantity} side={side} />
        ))}
      </div>
    </section>
  );
}

function OrderBook({ snapshot }: { snapshot: Snapshot }) {
  return (
    <div className="book-shell">
      <BookSide title="Asks" levels={snapshot.asks} side="sell" />
      <div className="spread">
        <span>Mid</span>
        <strong>{formatPrice(snapshot.mid_price)}</strong>
      </div>
      <BookSide title="Bids" levels={snapshot.bids} side="buy" />
    </div>
  );
}

function OrderTicket({ onSubmitted }: { onSubmitted: (message: string) => void }) {
  const [price, setPrice] = React.useState(10020);
  const [quantity, setQuantity] = React.useState(5);
  const [busy, setBusy] = React.useState<Side | null>(null);

  const submit = async (side: Side) => {
    setBusy(side);
    try {
      const response = await fetch(`${API_BASE}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ side, price, quantity, owner: "dashboard" }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? "order rejected; fix the inputs and retry");
      }
      onSubmitted(`${payload.ack.order_id} ${payload.ack.status}`);
    } catch (error) {
      onSubmitted(error instanceof Error ? error.message : "order failed; retry");
    } finally {
      setBusy(null);
    }
  };

  return (
    <form className="ticket" onSubmit={(event) => event.preventDefault()}>
      <label>
        Price
        <input
          min={1}
          step={5}
          type="number"
          value={price}
          onChange={(event) => setPrice(Number(event.target.value))}
        />
      </label>
      <label>
        Quantity
        <input
          min={1}
          type="number"
          value={quantity}
          onChange={(event) => setQuantity(Number(event.target.value))}
        />
      </label>
      <div className="ticket-actions">
        <button className="buy-button" disabled={busy !== null} onClick={() => submit("buy")} type="button">
          <SendHorizontal aria-hidden="true" size={18} />
          Buy
        </button>
        <button className="sell-button" disabled={busy !== null} onClick={() => submit("sell")} type="button">
          <SendHorizontal aria-hidden="true" size={18} />
          Sell
        </button>
      </div>
    </form>
  );
}

function TradeTape({ trades }: { trades: Trade[] }) {
  return (
    <section className="tape" aria-label="Trade tape">
      <div className="panel-heading">
        <h2>Trade Tape</h2>
      </div>
      <div className="trade-list">
        {trades.map((trade) => (
          <div className={`trade trade-${trade.side}`} key={trade.trade_id}>
            <span>{trade.trade_id}</span>
            <strong>{formatPrice(trade.price)}</strong>
            <span>{trade.quantity}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function App() {
  const { snapshot, latency, trades, connected } = useMarketData();
  const [notice, setNotice] = React.useState("ready");

  const reset = async () => {
    const response = await fetch(`${API_BASE}/reset`, { method: "POST" });
    setNotice(response.ok ? "book reset" : "reset failed; check API logs");
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Mini Exchange</p>
          <h1>{snapshot.symbol}</h1>
        </div>
        <div className="status-strip">
          <span className={connected ? "status connected" : "status disconnected"}>
            {connected ? <Wifi aria-hidden="true" size={16} /> : <WifiOff aria-hidden="true" size={16} />}
            {connected ? "Live" : "Reconnecting"}
          </span>
          <button className="icon-button" onClick={reset} title="Reset seeded book" type="button">
            <RefreshCw aria-hidden="true" size={18} />
          </button>
        </div>
      </header>

      <section className="metrics-grid" aria-label="Exchange metrics">
        <Metric label="Best Bid" value={formatPrice(snapshot.best_bid)} />
        <Metric label="Best Ask" value={formatPrice(snapshot.best_ask)} />
        <Metric label="P50" value={formatLatency(latency.p50_us)} />
        <Metric label="P99" value={formatLatency(latency.p99_us)} />
      </section>

      <section className="workspace">
        <div className="primary-panel">
          <div className="panel-heading">
            <h2>Depth</h2>
            <span>Seq {snapshot.sequence}</span>
          </div>
          <OrderBook snapshot={snapshot} />
        </div>

        <aside className="side-panel">
          <div className="panel-heading">
            <h2>Order Ticket</h2>
            <span className="notice">
              <Activity aria-hidden="true" size={15} />
              {notice}
            </span>
          </div>
          <OrderTicket onSubmitted={setNotice} />
          <TradeTape trades={trades} />
        </aside>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
