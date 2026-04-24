# Ch-ng-Kho-n

Hệ phân tích & quyết định vào lệnh gồm 3 lớp:

1. **Trading Agent Blueprint** (`AGENT.md`) — rule book SMC/ICT + Price Action + Volume Profile + Tâm lý. 7 nguyên tắc tối cao, khung tư duy 4 lớp (Bias → POI → Trigger → Execution), quy trình 5 bước Wait·Watch·Confirm·Execute·Forget, Confluence Matrix 8 yếu tố (pass khi ≥ 5/8), output schema cố định, hard-stops.
2. **Multi-Agent BTC Entry System** (`agents/`) — code rule-based: MVRV + TA (EMA/RSI/MACD/ATR/Ichimoku/Fib/VP/S-R) → entry zone, stop, TP1/TP2.
3. **Master Data Agent** (`agents/master_agent.py`) — orchestrator **mapping code agents → AGENT.md blueprint**. Kéo dữ liệu đa khung, chấm Confluence Matrix deterministic, từ chối trade khi < 5/8, output đúng schema Mục 4 của `AGENT.md`.

## Cấu trúc

```
AGENT.md                              # blueprint (system prompt cho LLM)
CII_Analysis.csv                      # CII plan + MVRV rows
data/mvrv_btc.csv                     # MVRV daily BTC 2011-2026
agents/
  mvrv_agent.py                       # on-chain regime
  ta_agent.py                         # single-timeframe TA
  indicators.py                       # EMA/RSI/MACD/ATR/Ichimoku/Fib/VP/SR
  data_sources.py                     # Kraken + CryptoCompare fetchers
  orchestrator.py                     # baseline 3x3 entry plan
  master_agent.py                     # AGENT.md mapping (multi-TF, Confluence 8)
  run.py                              # CLI for baseline orchestrator
  run_master.py                       # CLI for Master Data Agent
  report.py                           # markdown/JSON output
scripts/
  compute_mvrv_filter.py              # apply MVRV regime rows to CII_Analysis.csv
  smoke_test.py                       # offline tests
docs/
  AGENTS.md                           # multi-agent architecture
  MVRV_Filter.md                      # MVRV regime thresholds
  MASTER_AGENT.md                     # Master Data Agent design (mapping AGENT.md <-> code)
  PHAN_TICH_KY_THUAT.md               # từ điển SMC/ICT/VP/Kill Zones
  CHECKLIST_KY_LUAT.md                # checklist A-F
templates/
  TRADE_ANALYSIS_TEMPLATE.md          # template phân tích 1 lệnh
  TRADE_ANALYSIS_TEMPLATE.csv         # nhật ký lệnh 23 cột
reports/                              # báo cáo tự sinh
```

## Quick start

```bash
# 1. Master Data Agent — phân tích BTC theo AGENT.md (multi-timeframe + Confluence 8)
python -m agents.run_master                       # default BTC/USDT
python -m agents.run_master --no-save             # stdout only

# 2. Baseline Multi-Agent entry plan (1 timeframe)
python -m agents.run                              # 1D
python -m agents.run --tf 4h                      # 4H

# 3. Apply MVRV regime to CII allocation
python scripts/compute_mvrv_filter.py --apply

# 4. Offline smoke tests
python scripts/smoke_test.py
```

Triết lý: **Xác suất × RR × Kỷ luật > Cảm xúc × FOMO**.
Stdlib Python 3.10+, không dependency ngoài.

Xem thêm:
- [`AGENT.md`](AGENT.md) — blueprint đầy đủ.
- [`docs/MASTER_AGENT.md`](docs/MASTER_AGENT.md) — cách code agent map vào blueprint.
- [`docs/AGENTS.md`](docs/AGENTS.md) — kiến trúc multi-agent cũ.
- [`docs/PHAN_TICH_KY_THUAT.md`](docs/PHAN_TICH_KY_THUAT.md) — từ điển SMC/ICT.
- [`docs/CHECKLIST_KY_LUAT.md`](docs/CHECKLIST_KY_LUAT.md) — checklist kỷ luật.
