# Paper Trading Simulator

Stateful forward runner. Mỗi lần chạy `python -m agents.run_paper` = một "tick":

1. Load state từ `reports/paper/state.json` (tạo mới nếu chưa có).
2. Với mỗi open position: kiểm tra candle mới nhất → đã chạm SL hoặc TP1 chưa.
3. Với mỗi asset chưa có position: gọi `master_agent.run(asset=...)`; nếu `decision=TRADE` → mở position mới.
4. Lưu lại state + append CSV `reports/paper/trades.csv`.

Thiết kế để chạy bằng cron/systemd (xem PR E).

## CLI

```bash
# Tick một lần cho BTC
python -m agents.run_paper --assets BTC

# Đa asset (cần PR B merged)
python -m agents.run_paper --assets BTC,ETH,SOL

# Risk 0.5% mỗi trade
python -m agents.run_paper --assets BTC --risk 0.5

# Đọc summary (không tick)
python -m agents.run_paper --summary
```

## Exit policy (conservative / pessimistic)

- Walk-forward bar-by-bar trên timeframe (`--timeframe`, default M15).
- Trong một bar:
  - **Long**: nếu `low <= stop` → SL (ưu tiên trước TP — pessimistic); nếu không, `high >= tp1` → TP1.
  - **Short**: mirror.
- TP2 không được dùng làm exit (sẽ báo trong record nhưng không trigger close) — để thống kê đơn giản và nhất quán với backtest harness.

Vì chọn pessimistic (SL first in same-bar tie), paper trader **under-reports**
win-rate vs thực tế. Đây là bias an toàn: live stats sẽ không tệ hơn paper.

## State & persistence

`reports/paper/state.json`:

```json
{
  "equity": 10000.0,
  "starting_equity": 10000.0,
  "last_tick_ts": 1777022710,
  "open_positions": [
    {"asset": "BTC", "direction": "long", "entry": ..., "stop": ...,
     "tp1": ..., "tp2": ..., "open_ts": ..., "size_pct": 1.0,
     "confluence_score": 8}
  ],
  "closed_trades": [{ ... }, ...]
}
```

`reports/paper/trades.csv`: append-only, một dòng mỗi lần close.

## P&L mô hình

Gain/loss trên equity = `equity × (size_pct% / 100) × R_multiple`.

Ví dụ: equity $10,000, risk 1%, R=+2 → equity += $10,000 × 0.01 × 2 = +$200.
Tương đương với "risk 1% để win 2R" quy ước.

Lưu ý: `pnl_pct` trong CSV là return **trên entry price** (100% notional),
khác với `r_multiple × size_pct` (return trên equity). Cả 2 đều record.

## Giới hạn

- **Không mô hình fee/slippage**. Live sẽ kém hơn paper.
- **Entry giả định fill ngay tại `sig.entry`** — không check liệu giá có
  thực sự chạm entry zone hay không. Paper trade có thể mở ở giá không
  đạt được ngoài đời.
- **Single position per asset**: cho đơn giản; không scaling in/out.
- **Không resume scenario**: nếu anh stop cron rồi restart sau vài ngày,
  paper trader sẽ bỏ sót exit có thể đã xảy ra trong khoảng gap — chỉ
  check với candle data có sẵn tại lần tick kế tiếp (đã đúng nhờ
  `open_ts + 1` lookup) nhưng nếu gap dài hơn 720 bar (giới hạn Kraken
  free) thì miss.
- **Timezone**: tất cả ts dùng unix seconds, UTC.

## So sánh với Backtest

| Aspect | Backtest (PR #7) | Paper Trader |
|---|---|---|
| Direction | Quá khứ → đo edge | Forward-only, realtime |
| Dữ liệu | Hết history có sẵn | Tick-by-tick |
| State | In-memory | Persistent JSON |
| Fee/slippage | Không | Không (có thể thêm sau) |
| Multi-asset | Không (hard-coded BTC) | Có (CLI flag) |
| Tốc độ | 1 run = toàn history | 1 tick = 1 snapshot |
