# SOL/USDT — 2026-04-24 09:15 UTC

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
| D1 | down |
| H4 | range |

**Kết luận Bias:** **BEARISH** — D1=down, H4=range, W1=down; MayerMultiple bullish (Deep Value) — macro disagrees
**MayerMultiple overlay:** Deep Value (value=0.6941, direction=bullish)

## 2. POI & Liquidity

| Field | Value |
|---|---|
| D1 swing | $67.40 — $128.16 |
| Premium zone (upper 50%) | $97.78 — $128.16 |
| Discount zone (lower 50%) | $67.40 — $97.78 |
| Current price in | **discount** |
| OTE long (Fib 0.618-0.79) | $80.16 — $90.61 |
| OTE short (Fib 0.618-0.79) | $104.95 — $115.40 |
| Nearest support | $79.55 |
| Nearest resistance | $116.01 |

## 3. Trigger (M15)

| Field | Value |
|---|---|
| Liquidity sweep | none @ — |
| CHoCH | none @ — |
| Nearest unmitigated bullish FVG (below) | — |
| Nearest unmitigated bearish FVG (above) | $85.24 — $85.39 |
| Nearest unmitigated bullish OB (demand) | $84.78 — $85.06 |
| Nearest unmitigated bearish OB (supply) | — |

## 4. Futures Microstructure (SOL-USDT-SWAP @ OKX)

| Field | Value |
|---|---|
| Funding rate (per 8h) | 0.30 bps → **neutral** |
| OI trend (12x1h) | rising (1.72%) |
| Long/Short account ratio | 2.53 |
| Liq magnet below (longs rekt) | $85.40 |
| Liq magnet above (shorts rekt) | $86.56 |
| Total liq volume (~100 events) | 6916.2 long / 3630.1 short |

## 5. Confluence Matrix (pass ≥ 7/12)

| # | Factor | Result | Note |
|---|--------|--------|------|
| 1 | Bias HTF (D1/H4) | FAIL | bias=bearish, want=n/a (no direction) |
| 2 | POI valid | FAIL | current_in=discount |
| 3 | Liquidity Sweep | FAIL | sweep=none |
| 4 | CHoCH LTF (M15) | FAIL | choch=none |
| 5 | Fibonacci OTE | FAIL | price=85.13 in [0.00, 0.00] |
| 6 | Volume Profile (POC proximity) | PASS | poc=85.84729166666668 |
| 7 | Momentum (RSI + MACD hist) | FAIL | rsi=35.9, macd_hist=-0.023928541420532787 |
| 8 | Kill Zone | PASS | London 07-10 UTC or NY 12-15 UTC |
| 9 | Funding Rate (contrarian) | FAIL | rate=0.30 bps/8h, regime=neutral |
| 10 | Open Interest trend | FAIL | oi_trend=rising, change=1.72% |
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
| D1 | $85.13 | $85.31 | $87.01 | $116.05 | 49.6 | 0.19 | $3.72 | down |
| H4 | $85.13 | $86.06 | $85.91 | $85.47 | 43.7 | -0.17 | $1.18 | range |
| H1 | $85.13 | $85.73 | $86.06 | $85.93 | 38.1 | -0.03 | $0.49 | range |
| M15 | $85.13 | $85.47 | $85.63 | $86.07 | 35.9 | -0.02 | $0.22 | down |

---

Source: `kraken` · AGENT.md blueprint · Master Data Agent
