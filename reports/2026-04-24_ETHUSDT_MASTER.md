# ETH/USDT — 2026-04-24 09:15 UTC

## Decision: NO_TRADE  (Confluence 1/12)

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
| H4 | range |

**Kết luận Bias:** **RANGE** — D1=range, H4=range, W1=down — mixed
**MayerMultiple overlay:** Discount (value=0.8240, direction=bullish)

## 2. POI & Liquidity

| Field | Value |
|---|---|
| D1 swing | $1,744.56 — $3,040.36 |
| Premium zone (upper 50%) | $2,392.46 — $3,040.36 |
| Discount zone (lower 50%) | $1,744.56 — $2,392.46 |
| Current price in | **mid** |
| OTE long (Fib 0.618-0.79) | $2,016.68 — $2,239.56 |
| OTE short (Fib 0.618-0.79) | $2,545.36 — $2,768.24 |
| Nearest support | $2,003.72 |
| Nearest resistance | $2,781.20 |

## 3. Trigger (M15)

| Field | Value |
|---|---|
| Liquidity sweep | none @ — |
| CHoCH | none @ — |
| Nearest unmitigated bullish FVG (below) | — |
| Nearest unmitigated bearish FVG (above) | $2,310.88 — $2,313.81 |
| Nearest unmitigated bullish OB (demand) | — |
| Nearest unmitigated bearish OB (supply) | — |

## 4. Futures Microstructure (ETH-USDT-SWAP @ OKX)

| Field | Value |
|---|---|
| Funding rate (per 8h) | -0.50 bps → **neutral** |
| OI trend (12x1h) | rising (3.37%) |
| Long/Short account ratio | 1.73 |
| Liq magnet below (longs rekt) | $2,298.18 |
| Liq magnet above (shorts rekt) | $2,330.27 |
| Total liq volume (~100 events) | 44590.4 long / 17336.2 short |

## 5. Confluence Matrix (pass ≥ 7/12)

| # | Factor | Result | Note |
|---|--------|--------|------|
| 1 | Bias HTF (D1/H4) | FAIL | bias=range, want=n/a (no direction) |
| 2 | POI valid | FAIL | current_in=mid |
| 3 | Liquidity Sweep | FAIL | sweep=none |
| 4 | CHoCH LTF (M15) | FAIL | choch=none |
| 5 | Fibonacci OTE | FAIL | price=2308.01 in [0.00, 0.00] |
| 6 | Volume Profile (POC proximity) | FAIL | poc=2398.3175 |
| 7 | Momentum (RSI + MACD hist) | FAIL | rsi=42.9, macd_hist=0.23087691271700184 |
| 8 | Kill Zone | PASS | London 07-10 UTC or NY 12-15 UTC |
| 9 | Funding Rate (contrarian) | FAIL | rate=-0.50 bps/8h, regime=neutral |
| 10 | Open Interest trend | FAIL | oi_trend=rising, change=3.37% |
| 11 | OB/FVG zone (3-candle) | FAIL | no unmitigated OB/FVG found |
| 12 | Liquidation magnet (target) | FAIL | no magnet |

**Score: 1/12** → NOT ENOUGH

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
| D1 | $2,308.01 | $2,280.04 | $2,229.48 | $2,634.59 | 54.0 | -3.49 | $98.46 | range |
| H4 | $2,308.01 | $2,333.99 | $2,327.47 | $2,233.10 | 42.6 | -6.36 | $33.95 | range |
| H1 | $2,308.01 | $2,321.24 | $2,333.82 | $2,328.02 | 40.1 | 0.24 | $14.97 | range |
| M15 | $2,308.01 | $2,312.73 | $2,317.08 | $2,334.35 | 42.9 | 0.23 | $6.11 | down |

---

Source: `kraken` · AGENT.md blueprint · Master Data Agent
