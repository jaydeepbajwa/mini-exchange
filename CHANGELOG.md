# Changelog

## 0.1.1 - 2026-07-03

### Fixed
- `latency.last_us` in `/snapshot` and WebSocket payloads reported the maximum
  sample instead of the most recent one (it was read after sorting).
- WebSocket broadcast now prunes a client on any send failure, not just
  `RuntimeError` — dead sockets could previously linger in the feed.
- The background demo flow resets to the seeded book every few cycles; it
  rests more volume than it consumes, so an unattended server previously grew
  the book (and every full-snapshot broadcast) without bound.

### Changed
- Default symbol renamed to the synthetic ticker `MINIX`.
- Removed unused `sequence`/`received_at_ns` fields from resting orders — time
  priority is carried by deque position, and the dead fields implied an
  ordering mechanism that wasn't there.
- `pydantic` declared as a direct dependency (it's imported directly).

### Added
- `scripts/bench.py`: reproducible latency/throughput benchmark; the README's
  performance table comes from this script.
- Tests: symmetric sell-taker matching, a book-never-crosses invariant over a
  mixed order sequence, and a regression test for `last_us`.
- Real dashboard screenshot in the README, replacing the hand-drawn mockup.

## 0.1.0 - 2026-07-03

- Added a Python limit order book with price-time priority matching.
- Added FastAPI endpoints and a WebSocket market-data feed.
- Added a React dashboard with depth, tape, and p50/p99 latency metrics.
- Added core invariant tests, CI, Docker demo path, MIT license, and build notes.
