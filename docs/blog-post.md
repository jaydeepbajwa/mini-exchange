# Mini Exchange Build Notes

This repo is the trading-systems anchor project from the roadmap: a small exchange that proves the mechanics I would expect to discuss in a trading-infra interview.

## What Broke

The easiest bug to introduce was matching same-price orders by whatever order a container happened to expose them. I kept each price level as a FIFO queue because the invariant is the whole point of the repo: if two sell orders rest at 100.00, the older order must fill first.

The second failure mode was UI latency that looked authoritative but measured the wrong thing. The dashboard now reports latency collected inside the matching engine, not browser timing or WebSocket delivery time.

## What I Would Redo

For a production-shaped sequel, I would add an append-only event log, deterministic replay, cancel/replace semantics, and a risk check before matching. The best-price lookup would move from dictionary scans to heaps or a sorted price ladder. I would also split public market data from private order acknowledgements because the current feed is intentionally demo-sized.

## Why This Fits My Story

LoopFX gave me the credibility to build a toy exchange without it reading like cosplay. This repo keeps that story concrete: price-time priority, observable latency, clear failure messages, and a dashboard that lets someone see the engine work without inventing data by hand.
