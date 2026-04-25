# Crypto Decision Engine — Webapp

A standalone single-page webapp that combines the **Master Data Agent**
(TA + MVRV + OKX futures) with **Coinglass v3 microstructure**
(multi-exchange funding, aggregated liquidations, heatmap, OI-weighted
price, top-trader sentiment) into a single decision panel that
recommends an optimal long/short entry zone.

This is a **separate** http server from the dashboard in `agents/dashboard.py`
(per user request). They can run side-by-side on different ports.

## Run

```bash
# Optional: enable Coinglass panels (Hobbyist tier or higher)
export COINGLASS_API_KEY=...

# Defaults to http://127.0.0.1:8889
python -m agents.run_webapp

# Or expose on the LAN
python -m agents.run_webapp --host 0.0.0.0 --port 8889
```

The webapp itself is unauthenticated — only bind it to `0.0.0.0` if
you trust your network. Coinglass calls always go out to
`open-api-v3.coinglass.com` over HTTPS.

## What you see

- **Price & Zones**: candle chart (TradingView Lightweight Charts CDN).
- **Decision**: bias HTF, MVRV regime, entry/SL/TP1/TP2/RR, augmented confluence score `x/14`, and the final TRADE / NO_TRADE call.
- **Coinglass Microstructure**: median funding across exchanges, 24h liquidation pressure, nearest heatmap magnets up/down, top-trader long/short skew. Shows a friendly "API key not set" banner when `COINGLASS_API_KEY` is missing.
- **Confluence Matrix**: all 12 base factors from the Master Data Agent + 2 extra Coinglass factors, with per-row pass/fail and reason.

## Decision logic

The webapp augments `master_agent.run()` (12-factor confluence, 7/12 gate)
with two Coinglass-derived factors:

1. **Funding consensus (multi-exchange)** — passes when the median
   funding rate across all listed exchanges is on the *opposite* side
   of the trade direction (crowd-short funding is bullish for a long
   entry, crowd-long funding is bullish for a short entry).
2. **Liquidation magnet within 5%** — passes when the heaviest heatmap
   cluster in the trade direction sits within 5% of current price
   (gives a high-conviction TP1 anchor).

The augmented gate is **8/14 (~57%)**, proportionally equivalent to
the base 7/12 (~58%).

If the Coinglass heatmap reveals a magnet that sits *further* than the
existing TP2 (computed from premium/discount swing), the webapp
**widens** TP2 to the magnet price (it never tightens TP2). The
displayed `TP2 (magnet)` indicator reflects this.

## Endpoints (JSON)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/` | Single-page HTML dashboard |
| `GET` | `/api/decision?asset=BTC` | Master signal + Coinglass overlay |
| `GET` | `/api/candles?asset=BTC&tf=1h&limit=300` | Spot OHLC for the chart (capped at 720) |
| `GET` | `/api/coinglass/funding?asset=BTC` | Multi-exchange funding consensus |
| `GET` | `/api/coinglass/liq?asset=BTC` | 24h liquidation pressure |
| `GET` | `/api/coinglass/heatmap?asset=BTC` | Raw heatmap grid (model 2) |
| `GET` | `/api/coinglass/oi?asset=BTC` | OI-weighted OHLC history |

All upstream calls are cached in-process for **30 s** to avoid
hammering Kraken/Coinglass when the page is left open.

## Graceful degradation

- **No API key** → Coinglass panels show "API key not set", confluence
  drops to base 12 factors, decision unaffected for the remaining
  factors.
- **Network error / Coinglass down** → `last_error` from the client is
  surfaced in the UI; cached previous values continue to serve until
  TTL expires.
- **`limit=0` on candles** → returns `[]` (Python's `[-0:]` quirk
  that would otherwise return all candles is guarded explicitly).
- **Unknown asset** → if the underlying `master_agent.run()` does not
  accept the `asset` kwarg yet (older branches), the webapp returns
  `{"error": "..."}` and the UI shows a red banner instead of garbled
  output.

## Testing

```bash
# Offline smoke (no network, no API key needed)
python scripts/smoke_test.py

# Live spot-check against running server
python -m agents.run_webapp &
curl -s http://127.0.0.1:8889/api/decision | python -m json.tool | head -40
kill %1
```
