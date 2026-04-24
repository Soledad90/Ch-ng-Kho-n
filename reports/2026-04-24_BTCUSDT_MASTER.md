# BTC/USDT — 2026-04-24 07:15 UTC

## Decision: NO_TRADE  (Confluence 2/8)

**Scenario A:** No valid setup
**Invalidation:** n/a
**Size hint:** n/a

### Hard-stops (AGENT.md)
- (none)

---

## 1. Bias HTF

| Timeframe | Trend |
|-----------|-------|
| W1 (proxy) | range |
| D1 | range |
| H4 | up |

**Kết luận Bias:** **RANGE** — D1=range, H4=up, W1=range — mixed
**MVRV overlay:** Discount (value=1.44, direction=bullish)

## 2. POI & Liquidity

| Field | Value |
|---|---|
| D1 swing | $60,500.00 — $90,438.30 |
| Premium zone (upper 50%) | $75,469.15 — $90,438.30 |
| Discount zone (lower 50%) | $60,500.00 — $75,469.15 |
| Current price in | **mid** |
| OTE long (Fib 0.618-0.79) | $66,787.04 — $71,936.43 |
| OTE short (Fib 0.618-0.79) | $79,001.87 — $84,151.26 |
| Nearest support | $66,487.66 |
| Nearest resistance | $84,450.64 |

## 3. Trigger (M15)

| Field | Value |
|---|---|
| Liquidity sweep | none @ — |
| CHoCH | none @ — |

## 4. Confluence Matrix (pass ≥ 5/8)

| # | Factor | Result | Note |
|---|--------|--------|------|
| 1 | Bias HTF (D1/H4) | FAIL | bias=range, want=n/a (no direction) |
| 2 | POI valid | FAIL | current_in=mid |
| 3 | Liquidity Sweep | FAIL | sweep=none |
| 4 | CHoCH LTF (M15) | FAIL | choch=none |
| 5 | Fibonacci OTE | FAIL | price=77735.00 in [0.00, 0.00] |
| 6 | Volume Profile (POC proximity) | PASS | poc=77767.54999999999 |
| 7 | Momentum (RSI + MACD hist) | FAIL | rsi=43.0, macd_hist=6.074947536691823 |
| 8 | Kill Zone | PASS | London 07-10 UTC or NY 12-15 UTC |

**Score: 2/8** → NOT ENOUGH

## 5. Execution Plan

| Field | Value |
|---|---|
| Direction | NONE |
| Entry | $— |
| Stop | $— |
| TP1 | $— |
| TP2 | $— |
| RR(TP1) | — |
| Risk per trade | 1.0% of equity |

## Timeframe Snapshots

| TF | Close | EMA20 | EMA50 | EMA200 | RSI | MACD-hist | ATR | Trend |
|---|---|---|---|---|---|---|---|---|
| D1 | $77,735.00 | $74,467.93 | $72,783.31 | $82,560.96 | 63.3 | 372.49 | $2,433.43 | range |
| H4 | $77,735.00 | $77,475.62 | $76,281.17 | $72,841.89 | 54.1 | -79.07 | $974.70 | up |
| H1 | $77,735.00 | $77,978.04 | $77,802.81 | $76,251.71 | 45.3 | -41.06 | $420.53 | range |
| M15 | $77,735.00 | $77,863.04 | $77,945.22 | $77,781.31 | 43.0 | 6.07 | $156.70 | range |

---

Source: `kraken` · AGENT.md blueprint · Master Data Agent
