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

## Exit policy

Walk-forward bar-by-bar. Với mỗi nến sau khi mở:
- **Long**: nếu `low <= stop` → exit stop (SL); nếu `high >= tp1` → exit tp1 (TP).
- **Short**: mirror.
- Hết `max_hold` bar chưa chạm SL/TP → exit tại close của bar cuối (timeout).

Chỉ dùng TP1 (TP2 bỏ qua để thống kê nhất quán). Cooldown `cooldown_bars` sau
mỗi exit để tránh vào lại ngay bar vừa thoát.

## CLI

```bash
python -m agents.run_backtest
# với tham số mặc định: max_hold=20, min-score=5/8, RR>=2.0, cooldown=3
python -m agents.run_backtest --min-score 4 --rr 1.5
python -m agents.run_backtest --no-save
```

Output: `reports/backtest/YYYY-MM-DD_summary.md` + `_trades.csv`.

## Kết quả mẫu (2024-04 → 2026-04, Kraken, 720 bar)

| Config | n_trades | win_rate | avg_R | total_return | max_DD | vs buyhold |
|---|---|---|---|---|---|---|
| min_score=5, RR≥2 (live-equivalent) | 1 | 0% | -1.00 | -3.82% | 3.82% | 21.33% |
| min_score=4, RR≥1.5 | 3 | 66.7% | +1.66 | +23.62% | 3.86% | 21.33% |
| min_score=3, RR≥1.5 | 4 | 50% | +0.99 | +19.32% | 3.86% | 21.33% |

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
- **Entry = mid OTE** (từ `_build_execution`). Giả định fill ngay tại giá đó.
  Slippage/fee không mô hình hoá.
- **No scaling out**: chỉ TP1, không tranche entries/exits như live.
- **Not look-ahead safe against MVRV bias**: MVRV regime được tính từ bộ phận
  lịch sử hiện có tại thời điểm T (percentile của toàn bộ hist từ 2011),
  không phải chỉ dữ liệu trước T. Đây là **mild look-ahead**. Nếu muốn chặt,
  tính percentile chỉ với MVRV trước ngày T.
