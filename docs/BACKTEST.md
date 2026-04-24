# Backtest Harness — Master Data Agent (D1-only)

Replay file-based historical D1 BTC candles through a **simplified variant**
của decision engine, đo win-rate / RR / drawdown.

## Điểm khác biệt so với live agent

| Aspect | Live `run_master` | Backtest `run_backtest` |
|---|---|---|
| Timeframes | D1 + H4 + H1 + M15 | D1 only |
| Futures (funding/OI/liq) | Có (OKX API) | Không — không có deep history miễn phí |
| Confluence Matrix | 12 yếu tố, gate ≥7 | 8 yếu tố, gate ≥5 (proportional) |
| MVRV | Live regime | Lookup CSV `data/mvrv_btc.csv` theo date |
| Sweep/CHoCH/OB/FVG | M15 | D1 cùng candles |

Backtest không claim mô phỏng chính xác live system 12-factor — mục đích là đo
**decision engine core** (bias+POI+trigger+OB/FVG+MVRV) có edge hay không.

## Fill validation + exit policy

**Entry là limit order** tại mid OTE (dưới close hiện tại cho long, trên cho
short). Nên trước khi walk-forward exit, backtest **kiểm tra limit có được fill
hay không**:

- **Phase 1 (fill validation)**: walk tối đa `fill_window` bars sau signal.
  Long chỉ được fill khi có bar nào đó `bar.low <= entry`; short cần
  `bar.high >= entry`. Nếu giá gap đi không bao giờ quay lại entry trong
  `fill_window` bar → **bỏ trade, không record**. Điều này tránh phantom fill
  khi market gap-away.
- **Phase 2 (exit walk)**: từ bar fill (inclusive) đi tối đa `max_hold` bar:
  - **Long**: nếu `low <= stop` → exit SL; nếu `high >= tp1` → exit TP1.
  - **Short**: mirror.
  - Pessimistic same-bar: chạm cả SL và TP trong 1 bar → SL thắng.
  - Hết `max_hold` bar → exit close của bar cuối (timeout).

Chỉ dùng TP1 (TP2 bỏ qua để thống kê nhất quán). Cooldown `cooldown_bars` sau
mỗi exit để tránh vào lại ngay bar vừa thoát. `bars_held` đếm từ bar fill, không
tính bar-chờ-fill.

## CLI

```bash
python -m agents.run_backtest
# mặc định: max_hold=20, min-score=5/8, RR>=2.0, cooldown=3, fill-window=5
python -m agents.run_backtest --min-score 4 --rr 1.5
python -m agents.run_backtest --fill-window 10          # gap-through rộng hơn
python -m agents.run_backtest --no-save
```

Output: `reports/backtest/YYYY-MM-DD_summary.md` + `_trades.csv`.

## Kết quả mẫu (2024-04 → 2026-04, Kraken, 720 bar)

Với `fill_window=5` (chỉ giữ trade thực sự được fill — không phantom fill):

| Config | n_trades | win_rate | avg_R | total_return | max_DD | vs buyhold |
|---|---|---|---|---|---|---|
| min_score=5, RR≥2 (live-equivalent) | 1 | 0% | -1.00 | -3.86% | 3.86% | 21.23% |
| min_score=4, RR≥1.5 | 1 | 0% | -1.00 | -3.86% | 3.86% | 21.23% |

> Ghi chú: trước khi thêm fill validation, phiên bản đầu tiên của backtest
> record 3 trade win_rate 66.7% ở cấu hình min_score=4 — phần lớn là **phantom
> fills** (limit entry tính ở mid OTE, nhưng thị trường gap qua và không quay
> lại touch entry). Sau khi thêm phase fill-validation, chỉ còn 1 trade thực sự
> fill — và trade đó hit SL. Kết luận: **window 720 bar hiện tại không đủ mẫu**
> để đo edge. Muốn conclude, phải chạy trên window dài hơn (Kraken paid/CSV
> local 5-10 năm).

## Đọc kết quả

- **win_rate + avg_R**: metric quan trọng nhất. `avg_R > 0` nghĩa là expectancy
  dương — mọi trade trung bình lời `avg_R * risk` đơn vị.
- **max_drawdown_pct**: compound drawdown trên equity curve (100% size mỗi trade).
- **buyhold_return_pct**: đối chứng — nếu total_return < buyhold mà max_DD thấp
  hơn đáng kể thì strategy vẫn có giá trị (Sharpe-like cao hơn).
- **sharpe_like**: `mean(pnl%) / stdev(pnl%)` — không annualised, chỉ so sánh
  tương đối giữa các cấu hình.

## Giới hạn

- **Không backtest intraday**: Kraken public free chỉ có ~720 D1 bar. Muốn sâu
  hơn (10 năm) cần Kraken OHLC paid / lưu CSV local.
- **Không có futures history**: các yếu tố #9-12 của live agent (funding/OI/liq)
  bị bỏ qua — kết quả backtest là **lower bound** của expectancy thật.
- **Entry = mid OTE** (từ `_build_execution`) với fill validation (bar.low/high
  phải chạm entry trong `fill_window` bar). Không mô hình hoá partial fill,
  slippage, fee hay spread.
- **No scaling out**: chỉ TP1, không tranche entries/exits như live.
- **Not look-ahead safe against MVRV bias**: MVRV regime được tính từ bộ phận
  lịch sử hiện có tại thời điểm T (percentile của toàn bộ hist từ 2011),
  không phải chỉ dữ liệu trước T. Đây là **mild look-ahead**. Nếu muốn chặt,
  tính percentile chỉ với MVRV trước ngày T.
