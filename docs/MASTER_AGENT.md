# Master Data Agent — AGENT.md ↔ code mapping

Master Data Agent là lớp **điều phối** biến [`AGENT.md`](../AGENT.md) (blueprint
LLM / rule book SMC-ICT) thành 1 pipeline Python rule-based chạy được trên dữ liệu
OHLC thật. Mọi yếu tố nào không thể đo được deterministic từ dữ liệu OHLC sẽ được
đánh dấu rõ ràng là **unknown** — Agent không bao giờ bịa dữ liệu.

## Mapping theo 4 lớp AGENT.md

| Lớp AGENT.md | Code | Dữ liệu vào | Output |
|---|---|---|---|
| **Lớp 1 — BIAS** (Xu hướng HTF + Vĩ mô) | `_bias_from_snaps()` + `MVRV Agent` | D1 + H4 trend (+ D1 làm proxy W1) + MVRV regime/z-score | `bias_htf ∈ {bullish, bearish, range}` + macro overlay |
| **Lớp 2 — POI** (Order Block / FVG / Premium-Discount) | `_poi()` | D1 swing high/low | `POI` — premium/discount zones, OTE long/short (Fib 0.618–0.79), nearest S/R |
| **Lớp 3 — TRIGGER** (Sweep + CHoCH) | `_detect_sweep()` + `_detect_choch()` | M15 candles (30 bar lookback) | `Trigger(sweep, choch)` với direction `{bullish, bearish, none}` |
| **Lớp 4 — EXECUTION** (Entry/SL/TP/Size) | `_build_execution()` + `_confluence()` | M15 ATR + Bias + POI + Trigger | Entry/SL/TP1/TP2 nếu Confluence ≥ 5/8 và không vi phạm hard-stop |

## Confluence Matrix (Mục 3 của AGENT.md)

8 yếu tố, chấm pass/fail deterministic. Cần **≥ 5/8** cộng với direction ≠ none,
hard_stops rỗng, RR(TP1) ≥ 2.0 thì `decision="TRADE"`, ngược lại `NO_TRADE`.

| # | Factor | Pass khi… |
|---|---|---|
| 1 | Bias HTF (D1/H4) | Bias HTF == hướng lệnh |
| 2 | POI valid | `current_in` là discount(long)/premium(short)/mid |
| 3 | Liquidity Sweep | Nến gần nhất wick phá swing trước rồi đóng lại trong |
| 4 | CHoCH LTF | M15 có pivot break ngược hướng prior trend |
| 5 | Fibonacci OTE | Giá hiện tại trong vùng 0.618-0.79 của leg tương ứng |
| 6 | Volume Profile (POC) | Giá trong ±1% quanh POC M15 |
| 7 | Momentum | RSI + MACD hist cùng hướng lệnh (ngưỡng 45/55 và dấu MACD) |
| 8 | Kill Zone | Giờ UTC ∈ {07-10 London, 12-15 NY} |

## Hard-stops (Mục 0 của AGENT.md)

Agent tự dán hard-stop vào output nếu:

- `risk_pct > 2.0%` — vi phạm Rule #3.
- HTF bullish nhưng MVRV bearish — macro divergence (đỉnh), vi phạm Rule #2.
- `RR(TP1) < 2.0` — vi phạm Rule #3.

Khi có ≥ 1 hard-stop, `decision` bị ép về `NO_TRADE` bất kể Confluence.

## Giới hạn / Ghi chú

- **W1 là proxy** từ trend D1 (chúng ta không pull khung tuần). Có thể thay bằng
  EMA-200 slope hoặc candles `1w` nếu cần.
- **Liquidity Heatmap** (Coinglass) chưa được feed vào agent. Yếu tố sweep hiện
  chỉ dựa trên wick OHLC — approximation, không đo thanh lý thực sự.
- **OB/FVG** chính thức chưa detect (cần logic 3-candle imbalance). Hiện xấp xỉ
  bằng Fib OTE + POI zone.
- **Funding rate / OI / Open Interest**: chưa tích hợp. Nếu thêm, làm agent mới
  rồi nối vào Confluence Matrix (mở rộng thành n/9 hoặc n/10).
- Agent **không** thay thế con người trong việc đọc chart. Output luôn đính kèm
  Scenario A + Invalidation để người dùng tự verify trước khi bấm lệnh.

## CLI

```bash
python -m agents.run_master                  # risk=1.0%, save reports/
python -m agents.run_master --risk 2.0       # max 2% per AGENT.md
python -m agents.run_master --json           # JSON output
python -m agents.run_master --no-save        # stdout only
```

Output lưu tại `reports/YYYY-MM-DD_BTCUSDT_MASTER.{md,json}`.
