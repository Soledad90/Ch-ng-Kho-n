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
| **Lớp 4 — EXECUTION** (Entry/SL/TP/Size) | `_build_execution()` + `_confluence()` | M15 ATR + Bias + POI + Trigger + Futures | Entry/SL/TP1/TP2 (TP2 = liq magnet nếu xa hơn premium zone) nếu Confluence ≥ 7/12 và không vi phạm hard-stop |
| **Microstructure** (mới) | `_build_futures()` | OKX funding/OI/L-S/liquidations | `Futures(funding_regime, oi_trend, ls_ratio, liq_poc_long/short)` |

## Confluence Matrix (Mục 3 của AGENT.md — mở rộng)

12 yếu tố (so với 8 gốc trong AGENT.md — 4 yếu tố mới được thêm từ futures
microstructure + OB/FVG chính thức). Chấm pass/fail deterministic. Cần
**≥ 7/12** cộng với direction ≠ none, hard_stops rỗng, RR(TP1) ≥ 2.0
thì `decision="TRADE"`, ngược lại `NO_TRADE`.

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
| 9 | Funding Rate (contrarian) | Long: funding ≤ 0 (ít crowded long); Short: funding ≥ 0 |
| 10 | Open Interest trend | OI tăng ≥1% trong 12 bar H1 (dòng tiền mới vào) |
| 11 | OB/FVG zone (3-candle) | Giá trong vùng unmitigated OB/FVG cùng hướng (±0.5 ATR M15) |
| 12 | Liquidation magnet | Có POC liquidation ở hướng mục tiêu (longs dưới giá cho short, shorts trên giá cho long) |

### Dữ liệu futures microstructure

- **Funding Rate** (OKX `BTC-USDT-SWAP`): current + historical 8h rate. Regime:
  - `> 0.03%/8h` = extreme_long (crowded long — sắp bị "long squeeze")
  - `0.01 – 0.03%` = mild_long
  - `-0.01 – 0.01%` = neutral
  - `-0.03 – -0.01%` = mild_short
  - `< -0.03%` = extreme_short (crowded short)
- **Open Interest** (OKX rubik stat): tổng USD notional BTC futures. Tính % thay
  đổi giữa bar hiện tại và bar 12h trước.
- **Long/Short Account Ratio** (OKX rubik): tham chiếu tâm lý đám đông.
- **Liquidation Heatmap**: lấy 100 lệnh thanh lý gần nhất từ OKX public
  `liquidation-orders`, gom thành 40 bin giá, tìm POC cho long-liq (magnet dưới)
  và short-liq (magnet trên). Kết quả là vùng giá mà thanh lý gần đây tập trung
  → ứng viên TP / magnet.

### OB/FVG 3-candle (ICT chính thức)

- **Fair Value Gap bullish** @ candle `i`: `highs[i-2] < lows[i]`. Gap = range
  `(highs[i-2], lows[i])`. Mitigated = nến sau có wick re-enter midpoint.
- **Fair Value Gap bearish**: `lows[i-2] > highs[i]`. Gap = `(highs[i], lows[i-2])`.
- **Order Block bullish (demand)**: nến đỏ ngay trước nến xanh "impulsive"
  (body ≥ 1.5× ATR(14)). OB = body của nến đỏ.
- **Order Block bearish (supply)**: mirror.
- Agent chọn **zone gần nhất unmitigated** theo hướng lệnh làm yếu tố 11.

## Hard-stops (Mục 0 của AGENT.md)

Agent tự dán hard-stop vào output nếu:

- `risk_pct > 2.0%` — vi phạm Rule #3.
- HTF bullish nhưng MVRV bearish — macro divergence (đỉnh), vi phạm Rule #2.
- `RR(TP1) < 2.0` — vi phạm Rule #3.

Khi có ≥ 1 hard-stop, `decision` bị ép về `NO_TRADE` bất kể Confluence.

## Giới hạn / Ghi chú

- **W1 là proxy** từ trend D1 (chúng ta không pull khung tuần). Có thể thay bằng
  EMA-200 slope hoặc candles `1w` nếu cần.
- **Liquidation Heatmap**: dùng 100 lệnh thanh lý gần nhất của OKX — đủ cho
  approximation "vùng magnet" nhưng chưa phải heatmap full depth như Coinglass
  Pro. Nếu có Coinglass API key, dễ mở rộng thêm endpoint trong `futures_data.py`.
- **Coinglass public API** tại thời điểm dev đều trả 500/404 không key. Đang dùng
  OKX làm nguồn chính (không cần key, không bị geo-block).
- **OB/FVG**: logic 3-candle đã implement chính thức trong `indicators.detect_fvg`
  và `indicators.detect_order_blocks`. Tuy nhiên "impulsive" threshold (1.5× ATR)
  có thể chỉnh nếu cần nhạy hơn.
- **Funding / OI**: đã integrate (OKX public). Lưu ý funding OKX = current period
  (chưa settled), không phải realized. Để trading quyết định thuần, agent coi
  giá trị hiện tại là đủ tín hiệu.
- **Binance public API bị geo-block** ở VM Cognition. Nếu deploy ở nơi có access,
  có thể thêm Binance làm nguồn thứ 2 cho futures.
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
