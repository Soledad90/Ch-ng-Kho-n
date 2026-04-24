# BTC/USDT — 2026-04-24 07:45 UTC

## Decision: NO_TRADE  (Confluence 2/12)

**Scenario A:** No valid setup
**Invalidation:** n/a
**Size hint:** n/a

### Hard-stops (AGENT.md)
- (none)

---

## 1. Bias HTF

| Timeframe | Trend |
|-----------|-------|
| W1 (proxy) | down |
| D1 | range |
| H4 | up |

**Kết luận Bias:** **RANGE** — D1=range, H4=up, W1=down — mixed
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
| Funding rate (per 8h) | -0.09 bps → **neutral** |
| OI trend (12x1h) | flat (0.49%) |
| Long/Short account ratio | 0.78 |
| Liq magnet below (longs rekt) | $77,156.79 |
| Liq magnet above (shorts rekt) | $78,375.01 |
| Total liq volume (~100 events) | 10591.7 long / 6758.2 short |

## 5. Confluence Matrix (pass ≥ 7/12)

| # | Factor | Result | Note |
|---|--------|--------|------|
| 1 | Bias HTF (D1/H4) | FAIL | bias=range, want=n/a (no direction) |
| 2 | POI valid | FAIL | current_in=mid |
| 3 | Liquidity Sweep | FAIL | sweep=none |
| 4 | CHoCH LTF (M15) | FAIL | choch=none |
| 5 | Fibonacci OTE | FAIL | price=77735.70 in [0.00, 0.00] |
| 6 | Volume Profile (POC proximity) | PASS | poc=77767.54999999999 |
| 7 | Momentum (RSI + MACD hist) | FAIL | rsi=43.7, macd_hist=1.5220894902159046 |
| 8 | Kill Zone | PASS | London 07-10 UTC or NY 12-15 UTC |
| 9 | Funding Rate (contrarian) | FAIL | rate=-0.09 bps/8h, regime=neutral |
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
| D1 | $77,735.70 | $74,468.00 | $72,783.34 | $82,560.96 | 63.4 | 372.53 | $2,433.43 | range |
| H4 | $77,735.70 | $77,475.68 | $76,281.20 | $72,841.90 | 54.1 | -79.03 | $974.70 | up |
| H1 | $77,735.70 | $77,978.11 | $77,802.84 | $76,251.72 | 45.3 | -41.01 | $427.13 | range |
| M15 | $77,735.70 | $77,836.06 | $77,927.41 | $77,780.05 | 43.7 | 1.52 | $148.17 | range |

---

Source: `kraken` · AGENT.md blueprint · Master Data Agent
