# Dashboard (stdlib HTTP + Lightweight Charts)

Live web UI cho Master Data Agent. Chạy bằng stdlib `http.server` (không
thêm dependency Python), client-side dùng TradingView Lightweight Charts
từ CDN (không `npm install`, chỉ 1 link `<script>`).

## Tại sao không dùng FastAPI?

Repo có policy "stdlib-only". FastAPI (+ uvicorn, starlette, pydantic)
yêu cầu pip install → phá rule. `http.server.ThreadingHTTPServer` đủ
cho dashboard cá nhân, handle concurrency bằng threading.

## Chạy

```bash
python -m agents.run_dashboard                 # 127.0.0.1:8000
python -m agents.run_dashboard --port 8080     # đổi port
python -m agents.run_dashboard --host 0.0.0.0  # expose LAN
```

Truy cập `http://127.0.0.1:8000/` trong browser.

## Endpoints

| Path | Mô tả |
|---|---|
| `GET /` | HTML dashboard |
| `GET /api/health` | `{ok: true, ts: <unix>}` |
| `GET /api/signal?asset=BTC` | MasterSignal hiện tại (JSON) |
| `GET /api/candles?asset=BTC&tf=15m&limit=300` | OHLC (tới 720 bar) |
| `GET /api/paper` | Paper-trader state (nếu `reports/paper/state.json` tồn tại) |

Response cache 30s in-memory — tránh hit Kraken/OKX khi mở nhiều tab.

## Dashboard renders

- **Candle chart** (TradingView Lightweight Charts):
  - OB-bull (xanh lam), OB-bear (hồng), FVG-bull (xanh lá), FVG-bear (đỏ) vẽ dạng price lines với label.
  - Liq magnet long/short vẽ dạng đường nét đứt vàng.
- **Confluence matrix**: bảng 12 yếu tố với PASS/FAIL màu + note.
- **Futures microstructure**: funding, OI trend, L/S ratio, liq volumes.
- **Paper trading**: equity hiện tại, open positions, 10 trades gần nhất.

Auto-refresh mỗi 60s. Bấm Refresh để cập nhật ngay.

## Giới hạn

- **Không HTTPS, không auth**: chỉ dùng localhost hoặc LAN tin cậy. Muốn public cần reverse-proxy + TLS (nginx/caddy) hoặc chấp nhận plaintext.
- **Không WebSocket**: client poll 60s, không push realtime. Đủ cho D1/H4
  timeframe; nếu cần M1/tick data realtime phải đổi sang SSE hoặc WS.
- **Single-process cache**: khi chạy nhiều instance trên cùng port không
  được (threading-only). Nếu cần HA thì trước mặt cần load balancer.
- **Lightweight Charts v4 từ CDN**: cần internet ở máy client để load
  script. Muốn offline: tải về `static/` và serve từ handler.
