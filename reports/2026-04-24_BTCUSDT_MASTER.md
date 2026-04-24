# BTC/USDT — 2026-04-24 07:30 UTC

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
| Nearest unmitigated bullish FVG (below) | — |
| Nearest unmitigated bearish FVG (above) | $77,749.30 — $77,791.80 |
| Nearest unmitigated bullish OB (demand) | $77,193.80 — $77,639.10 |
| Nearest unmitigated bearish OB (supply) | $78,158.40 — $78,169.10 |

## 4. Futures Microstructure (OKX)

| Field | Value |
|---|---|
| Funding rate (per 8h) | -0.13 bps → **neutral** |
| OI trend (12x1h) | flat (0.49%) |
| Long/Short account ratio | 0.78 |
| Liq magnet below (longs rekt) | $77,156.79 |
| Liq magnet above (shorts rekt) | $78,375.01 |
| Total liq volume (~100 events) | 10597.3 long / 6594.4 short |

## 5. Confluence Matrix (pass ≥ 7/12)

| # | Factor | Result | Note |
|---|--------|--------|------|
| 1 | Bias HTF (D1/H4) | FAIL | bias=range, want=n/a (no direction) |
| 2 | POI valid | FAIL | current_in=mid |
| 3 | Liquidity Sweep | FAIL | sweep=none |
| 4 | CHoCH LTF (M15) | FAIL | choch=none |
| 5 | Fibonacci OTE | FAIL | price=77745.20 in [0.00, 0.00] |
| 6 | Volume Profile (POC proximity) | PASS | poc=77767.54999999999 |
| 7 | Momentum (RSI + MACD hist) | FAIL | rsi=43.5, macd_hist=4.478477266027056 |
| 8 | Kill Zone | PASS | London 07-10 UTC or NY 12-15 UTC |
| 9 | Funding Rate (contrarian) | FAIL | rate=-0.13 bps/8h, regime=neutral |
| 10 | Open Interest trend | FAIL | oi_trend=flat, change=0.49% |
| 11 | OB/FVG zone (3-candle) | FAIL | no unmitigated OB/FVG found |
| 12 | Liquidation magnet (target) | FAIL | no magnet |

**Score: 2/12** → NOT ENOUGH

## 6. Execution Plan

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
| D1 | $77,745.20 | $74,468.90 | $72,783.71 | $82,561.06 | 63.4 | 373.14 | $2,433.43 | range |
| H4 | $77,745.20 | $77,476.59 | $76,281.57 | $72,841.99 | 54.2 | -78.42 | $974.70 | up |
| H1 | $77,745.20 | $77,979.01 | $77,803.21 | $76,251.81 | 45.4 | -40.41 | $423.89 | range |
| M15 | $77,745.20 | $77,851.62 | $77,937.29 | $77,780.98 | 43.5 | 4.48 | $149.81 | range |

---

Source: `kraken` · AGENT.md blueprint · Master Data Agent
