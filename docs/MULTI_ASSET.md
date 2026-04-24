# Multi-asset support (BTC / ETH / SOL)

Master Data Agent giờ chạy được cho cả 3 asset qua flag `--asset`:

```bash
python -m agents.run_master --asset BTC   # default, dùng MVRV thật (bitbo.io)
python -m agents.run_master --asset ETH   # Mayer Multiple proxy
python -m agents.run_master --asset SOL   # Mayer Multiple proxy
```

## Macro overlay

| Asset | Metric | Nguồn |
|---|---|---|
| BTC | MVRV (Market Value / Realized Value) | `data/mvrv_btc.csv` (bitbo.io, 5.562 dòng) |
| ETH | Mayer Multiple = Close / SMA200(D1) | Kraken/CC OHLC live |
| SOL | Mayer Multiple = Close / SMA200(D1) | Kraken/CC OHLC live |

### Vì sao không dùng MVRV thật cho ETH/SOL?

MVRV on-chain cần **realized price** — tổng giá trị UTXO/coin tính theo giá
chúng được move lần cuối. Cho BTC có data miễn phí (bitbo.io). Với ETH/SOL:

- Glassnode / CryptoQuant / Santiment có ETH realized price nhưng đều **paid**.
- ETH Proof-of-Stake + smart contract → realized price concept phức tạp hơn
  (staked ETH, ETH in contracts, LP tokens...).
- SOL: ít provider support; Mayer Multiple là fallback duy nhất miễn phí.

### Mayer Multiple — thresholds

Do Trace Mayer đề xuất (2013) ban đầu cho BTC. Thresholds dùng ở đây:

| Regime | Mayer Multiple | Direction | Size multiplier |
|---|---|---|---|
| Deep Value | ≤ 0.70 | bullish | 1.50× |
| Discount | ≤ 1.00 | bullish | 1.15× |
| Neutral | 1.00–2.00 | none | 1.00× |
| Hot | 2.00–2.40 | bearish | 0.60× |
| Euphoria | ≥ 2.40 | bearish | 0.25× |

ETH/SOL có volatility cao hơn BTC → ngưỡng 2.40 cho top rủi ro đôi khi quá
nghiêm với ETH/SOL (cả hai thường chạy Mayer 2.5–3.5 trong pha tăng mạnh).
Có thể tune lại theo per-asset nếu cần.

## Futures data

OKX có đầy đủ 3 asset:
- `BTC-USDT-SWAP`, `ETH-USDT-SWAP`, `SOL-USDT-SWAP` → funding/OI/L-S/liq đều có.
- `futures_data.fetch_*(asset=...)` routes đúng instId/ccy.

## Giới hạn

- **ETH/SOL không có real on-chain macro** → tín hiệu macro kém tin cậy hơn BTC.
  Mayer Multiple chỉ là proxy technical, không bắt được realized cost basis
  thật của holders.
- **Mayer thresholds copy từ BTC**: chưa tune per-asset. Có thể backtest để tìm
  ngưỡng tối ưu cho ETH/SOL nhưng chưa làm.
- **Futures microstructure**: ETH/SOL có OI/L-S/liq thấp hơn BTC nhiều lần
  → magnets thường ít rõ nét, dễ noise. Cần xem xét khi đọc signal.
- **Không auto-correlate**: nếu BTC bearish thì ETH/SOL gần như chắc chắn
  bearish. Agent hiện tại chạy độc lập từng asset; muốn cross-asset filter
  (ví dụ "chỉ long ETH nếu BTC bias ≥ range") cần extend thêm.
