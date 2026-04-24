# Ch-ng-Kho-n

Hệ phân tích & quyết định vào lệnh gồm:

1. **MVRV Macro Filter** — regime định giá BTC (from charts.bitbo.io/mvrv) ánh
   xạ thành size multiplier cho portfolio (áp cho cả BTC và cổ phiếu VN như CII).
2. **Multi-Agent BTC Entry System** — 3 agent rule-based kết hợp MVRV + TA để
   ra entry zone, stop, TP1/TP2 cho BTC/USDT.

## Cấu trúc

```
CII_Analysis.csv                  # CII plan + MVRV rows (áp dụng filter)
data/mvrv_btc.csv                 # MVRV daily BTC 2011-2026
agents/                           # multi-agent system
  mvrv_agent.py                   #  - on-chain valuation
  ta_agent.py                     #  - technical analysis (Kraken OHLC)
  indicators.py                   #  - EMA/RSI/MACD/ATR/Ichimoku/Fib/VP/S-R
  data_sources.py                 #  - Kraken + CryptoCompare fetchers
  orchestrator.py                 #  - fuse MVRV + TA -> entry plan
  report.py                       #  - markdown + JSON output
  run.py                          #  - CLI entrypoint
scripts/compute_mvrv_filter.py    # apply MVRV regime rows to CII_Analysis.csv
scripts/smoke_test.py             # offline smoke tests
docs/MVRV_Filter.md               # thresholds & design of MVRV filter
docs/AGENTS.md                    # multi-agent architecture
reports/                          # generated markdown + JSON reports
```

## Quick start

```bash
# 1. Apply MVRV regime to CII allocation plan
python scripts/compute_mvrv_filter.py            # preview
python scripts/compute_mvrv_filter.py --apply    # write rows into CII_Analysis.csv

# 2. Generate a BTC entry plan
python -m agents.run                             # daily timeframe
python -m agents.run --tf 4h                     # 4-hour
python -m agents.run --no-save --json            # stdout JSON only

# 3. Run offline smoke tests
python scripts/smoke_test.py
```

Không có dependency ngoài stdlib Python 3.10+. Xem chi tiết:

- [`docs/MVRV_Filter.md`](docs/MVRV_Filter.md) — ngưỡng & rationale của MVRV filter.
- [`docs/AGENTS.md`](docs/AGENTS.md) — kiến trúc multi-agent.
