# BTC/USDT — 2026-04-24 09:15 UTC

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
**MVRV overlay:** Discount (value=1.4400, direction=bullish)

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
| CHoCH | bearish @ 77,578.30 |
| Nearest unmitigated bullish FVG (below) | — |
| Nearest unmitigated bearish FVG (above) | $77,633.90 — $77,778.20 |
| Nearest unmitigated bullish OB (demand) | — |
| Nearest unmitigated bearish OB (supply) | $77,778.20 — $77,813.50 |

## 4. Futures Microstructure (BTC-USDT-SWAP @ OKX)

| Field | Value |
|---|---|
| Funding rate (per 8h) | -0.03 bps → **neutral** |
| OI trend (12x1h) | flat (-0.21%) |
| Long/Short account ratio | 0.8 |
| Liq magnet below (longs rekt) | $77,040.77 |
| Liq magnet above (shorts rekt) | $78,375.01 |
| Total liq volume (~100 events) | 8950.2 long / 6713.6 short |

## 5. Confluence Matrix (pass ≥ 7/12)

| # | Factor | Result | Note |
|---|--------|--------|------|
| 1 | Bias HTF (D1/H4) | FAIL | bias=range, want=n/a (no direction) |
| 2 | POI valid | FAIL | current_in=mid |
| 3 | Liquidity Sweep | FAIL | sweep=none |
| 4 | CHoCH LTF (M15) | FAIL | choch=bearish |
| 5 | Fibonacci OTE | FAIL | price=77492.30 in [0.00, 0.00] |
| 6 | Volume Profile (POC proximity) | PASS | poc=77767.54999999999 |
| 7 | Momentum (RSI + MACD hist) | FAIL | rsi=37.6, macd_hist=-13.399521394278054 |
| 8 | Kill Zone | PASS | London 07-10 UTC or NY 12-15 UTC |
| 9 | Funding Rate (contrarian) | FAIL | rate=-0.03 bps/8h, regime=neutral |
| 10 | Open Interest trend | FAIL | oi_trend=flat, change=-0.21% |
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
| D1 | $77,492.30 | $74,444.81 | $72,773.79 | $82,558.54 | 62.4 | 357.00 | $2,436.75 | range |
| H4 | $77,492.30 | $77,469.65 | $76,325.36 | $72,887.45 | 52.3 | -120.54 | $946.58 | up |
| H1 | $77,492.30 | $77,910.77 | $77,787.86 | $76,278.45 | 42.0 | -58.72 | $427.51 | range |
| M15 | $77,492.30 | $77,762.15 | $77,874.98 | $77,774.80 | 37.6 | -13.40 | $171.82 | range |

---

Source: `kraken` · AGENT.md blueprint · Master Data Agent
