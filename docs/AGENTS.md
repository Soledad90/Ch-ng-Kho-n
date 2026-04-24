# Multi-Agent BTC Entry System

Hệ 3 agent **rule-based** (không LLM) dùng để chọn vùng vào lệnh tối ưu cho BTC/USDT:

```
                ┌──────────────────────────────┐
                │  Orchestrator (rules engine) │
                │  action, entry zone, stop,   │
                │  TP1/TP2, size multiplier    │
                └───────────────┬──────────────┘
                                │
             ┌──────────────────┼──────────────────┐
             ▼                                     ▼
    ┌──────────────────┐                  ┌──────────────────┐
    │  MVRV Agent      │                  │  TA Agent        │
    │  (on-chain val)  │                  │  (price action)  │
    └──────────────────┘                  └──────────────────┘
    data/mvrv_btc.csv                     Kraken OHLC (fallback CryptoCompare)
```

## 1. MVRV Agent — `agents/mvrv_agent.py`

Đọc `data/mvrv_btc.csv` (sinh từ charts.bitbo.io/mvrv) và tính:

- **Regime** (Deep Value / Discount / Neutral / Hot / Euphoria) dựa trên quantile lịch sử.
- **Size multiplier** theo regime (1.50 / 1.15 / 1.00 / 0.60 / 0.25).
- **Percentile** so với toàn bộ lịch sử (5.562 điểm).
- **Z-score 365 ngày** để phát hiện MVRV đang "nóng/lạnh" trong nội bộ regime.
- **Direction** (bullish / neutral / bearish) dựa trên regime và z-score.

## 2. TA Agent — `agents/ta_agent.py`

Kéo OHLC từ Kraken public API (`XBTUSD`, interval 1D/4H/1H; fallback: CryptoCompare `histoday/histohour`). Không cần API key.

Indicators (pure Python, file `agents/indicators.py`):

- **Core:** EMA(20, 50, 200), RSI(14), MACD(12, 26, 9), ATR(14).
- **Ichimoku (9, 26, 52):** Tenkan, Kijun, Senkou A/B; trạng thái giá vs. Cloud.
- **Fibonacci:** retracements 0.236/0.382/0.5/0.618/0.786 trên swing 90 candle gần nhất.
- **Support/Resistance:** swing pivots (left=5, right=5), clustered theo tolerance 1%.
- **Volume Profile:** 24 bins, 180 candle lookback; POC, VAH/VAL (70% value area).

Output của agent: `trend` (up/down/range), `momentum` (strong_up..strong_down), `cloud_state` (above/inside/below), `direction` (bullish/neutral/bearish).

## 3. Orchestrator — `agents/orchestrator.py`

Ma trận quyết định (MVRV dir × TA dir):

|                | TA bullish | TA neutral | TA bearish |
|----------------|------------|------------|------------|
| MVRV bullish   | STRONG_BUY | BUY_DCA    | WAIT_DIP   |
| MVRV neutral   | BUY        | HOLD       | REDUCE     |
| MVRV bearish   | TRIM       | TRIM       | EXIT       |

Logic vùng vào:

- **STRONG_BUY / BUY:** pullback về EMA20 ± 0.5·ATR, cắt vào dải Fib 0.382 – 0.618, sàn chặn bởi Value Area Low. 3 tranche (40 / 35 / 25%).
- **BUY_DCA / WAIT_DIP:** 3 tranche DCA tại POC / Fib 0.618 / support gần nhất (30 / 35 / 35%).
- **HOLD:** entry zone = close ± 1·ATR, 1 tranche.
- **REDUCE / TRIM / EXIT:** không entry mới.

Stop = support gần nhất dưới − 0.5·ATR.
TP1 = resistance gần nhất trên.
TP2 = max(VAH, swing high, TP1 + 2·ATR).

**Confidence** (0..1): khởi điểm 0.5, +0.25 khi MVRV và TA cùng hướng (khác neutral), −0.15 khi trái ngược, cộng thêm tối đa 0.15 theo RR(TP1).

## 4. CLI & Output — `agents/run.py`, `agents/report.py`

```bash
python -m agents.run                    # 1D, lưu reports/YYYY-MM-DD_BTCUSDT_1d.{md,json}
python -m agents.run --tf 4h            # 4H
python -m agents.run --no-save          # chỉ in ra stdout
python -m agents.run --json             # in JSON thay vì markdown
```

## Dependencies

**Không có** — pure Python stdlib 3.10+. Dữ liệu OHLC kéo qua `urllib.request` (HTTP), không cần `requests` / `pandas` / `numpy`.

## Giới hạn

- Kraken trả tối đa 720 candle; dải dài hạn (EMA 200 trên 1D → ~2 năm) vẫn đủ, nhưng nếu cần >2 năm 1D thì đổi sang Cryptocompare `histoday&limit=2000`.
- MVRV chỉ refresh khi `data/mvrv_btc.csv` được cập nhật. Script fetch tự động chưa có — nếu cần, thêm vào `scripts/fetch_mvrv.py` (requires cron job).
- Rules engine không tính tới order-book imbalance, funding rate, ETF flows. Có thể thêm làm agent thứ 4 sau.
- TA agent làm việc trên OHLC đóng; signal chỉ cập nhật sau khi candle đóng.
