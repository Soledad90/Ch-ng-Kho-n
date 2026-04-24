"""Stdlib HTTP dashboard for Master Data Agent signals.

Why stdlib (http.server) and not FastAPI? The repo has a hard no-third-party
dep policy. Client-side we use TradingView Lightweight Charts via CDN
(loaded at render time, no npm install needed).

Endpoints:
    GET /                         -> HTML dashboard
    GET /api/signal?asset=BTC     -> current MasterSignal as JSON
    GET /api/candles?asset=BTC&tf=15m&limit=200 -> recent OHLC
    GET /api/paper                -> paper trader state (if present)
    GET /api/health               -> {ok: true}

Run with: python -m agents.run_dashboard --port 8000
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import master_agent, master_report
from .data_sources import fetch_ohlc


# --- simple in-process cache (30s) ---
_CACHE: dict[str, tuple[float, object]] = {}
_LOCK = threading.Lock()
_CACHE_TTL = 30.0


def _cached(key: str, ttl: float, producer):
    with _LOCK:
        now = time.time()
        hit = _CACHE.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    val = producer()
    with _LOCK:
        _CACHE[key] = (time.time(), val)
    return val


# -------------------------------------------------------------------------
# Handlers
# -------------------------------------------------------------------------

def _signal_json(asset: str) -> dict:
    def produce():
        try:
            sig = master_agent.run(asset=asset)  # type: ignore[call-arg]
        except TypeError:
            # pre-multi-asset master_agent
            if asset != "BTC":
                return {"error": f"master_agent on this branch supports BTC only"}
            sig = master_agent.run()
        return sig.to_dict()
    return _cached(f"signal:{asset}", _CACHE_TTL, produce)


def _candles_json(asset: str, tf: str, limit: int) -> list[dict]:
    # Guard against `?limit=0` / negative values: `c[-0:]` is `c[:]`, which
    # would silently return ALL candles instead of an empty slice, and a
    # negative limit (`c[-(-n):]` = `c[n:]`) would bypass the caller's cap.
    if limit <= 0:
        return []
    def produce():
        try:
            c, _src = fetch_ohlc(tf, asset)  # type: ignore[arg-type]
        except TypeError:
            if asset != "BTC":
                return []
            c, _src = fetch_ohlc(tf)
        return [
            {"time": int(x.ts), "open": x.open, "high": x.high,
             "low": x.low, "close": x.close, "volume": x.volume}
            for x in c[-limit:]
        ]
    return _cached(f"candles:{asset}:{tf}:{limit}", _CACHE_TTL, produce)


def _paper_json(state_path: Path) -> dict:
    if not state_path.exists():
        return {"available": False, "note": "run agents.run_paper to initialise state"}
    with state_path.open() as f:
        st = json.load(f)
    st["available"] = True
    return st


# -------------------------------------------------------------------------
# HTML page
# -------------------------------------------------------------------------

INDEX_HTML = r"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>Master Data Agent Dashboard</title>
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; background: #0e1117; color: #e4e6eb; }
  h1 { margin: 0 0 0.5rem 0; font-size: 1.2rem; }
  .controls { margin-bottom: 1rem; }
  .controls label { margin-right: 1rem; }
  select, button { background: #1a1f29; color: #e4e6eb; border: 1px solid #2d3546; padding: 0.3rem 0.6rem; }
  .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; }
  .panel { background: #151a23; padding: 1rem; border-radius: 6px; border: 1px solid #2d3546; }
  #chart { height: 500px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { text-align: left; padding: 0.3rem 0.5rem; border-bottom: 1px solid #2d3546; }
  .badge-TRADE { color: #00d68f; font-weight: 600; }
  .badge-NO_TRADE { color: #ffaa00; font-weight: 600; }
  .pass { color: #00d68f; }
  .fail { color: #ff3d71; }
  pre { font-size: 0.75rem; overflow-x: auto; }
  a { color: #60a5fa; }
</style>
</head>
<body>
  <h1>Master Data Agent — BTC/ETH/SOL</h1>
  <div class="controls">
    <label>Asset:
      <select id="asset">
        <option>BTC</option><option>ETH</option><option>SOL</option>
      </select>
    </label>
    <label>Timeframe:
      <select id="tf">
        <option value="1d">1D</option>
        <option value="4h">4H</option>
        <option value="1h">1H</option>
        <option value="15m" selected>15M</option>
      </select>
    </label>
    <button onclick="load()">Refresh</button>
    <span id="status" style="margin-left:1rem;color:#888"></span>
  </div>

  <div class="grid">
    <div class="panel">
      <div id="chart"></div>
    </div>
    <div class="panel">
      <div id="decision"></div>
      <h3>Confluence</h3>
      <table id="confluence"><thead><tr><th>#</th><th>Factor</th><th>Result</th><th>Note</th></tr></thead><tbody></tbody></table>
    </div>
  </div>

  <div class="panel" style="margin-top:1rem;">
    <h3>Futures microstructure (OKX)</h3>
    <div id="futures"></div>
  </div>

  <div class="panel" style="margin-top:1rem;">
    <h3>Paper trading</h3>
    <div id="paper"></div>
  </div>

<script>
  const chart = LightweightCharts.createChart(document.getElementById('chart'), {
    layout: { background: { color: '#151a23' }, textColor: '#e4e6eb' },
    grid: { vertLines: { color: '#2d3546' }, horzLines: { color: '#2d3546' } },
    timeScale: { timeVisible: true, secondsVisible: false },
    rightPriceScale: { borderColor: '#2d3546' },
  });
  const candleSeries = chart.addCandlestickSeries({
    upColor: '#00d68f', downColor: '#ff3d71',
    borderUpColor: '#00d68f', borderDownColor: '#ff3d71',
    wickUpColor: '#00d68f', wickDownColor: '#ff3d71',
  });

  async function load() {
    const asset = document.getElementById('asset').value;
    const tf = document.getElementById('tf').value;
    document.getElementById('status').textContent = 'Loading…';
    try {
      const [sigRes, candlesRes, paperRes] = await Promise.all([
        fetch(`/api/signal?asset=${asset}`).then(r => r.json()),
        fetch(`/api/candles?asset=${asset}&tf=${tf}&limit=300`).then(r => r.json()),
        fetch(`/api/paper`).then(r => r.json()),
      ]);
      renderCandles(candlesRes, sigRes);
      renderSignal(sigRes);
      renderPaper(paperRes);
      document.getElementById('status').textContent = 'Loaded ' + new Date().toLocaleTimeString();
    } catch (e) {
      document.getElementById('status').textContent = 'Error: ' + e.message;
    }
  }

  function renderCandles(rows, sig) {
    // Don't try to render an error dict as OHLC rows.
    if (!Array.isArray(rows)) rows = [];
    candleSeries.setData(rows);
    // If the signal itself errored, skip zone overlays (they require trigger/futures fields).
    if (sig && sig.error) { chart.timeScale().fitContent(); return; }
    // Draw OB/FVG zones as price lines + liq magnets
    // (clear previous lines before re-drawing)
    if (window._lines) window._lines.forEach(l => candleSeries.removePriceLine(l));
    window._lines = [];
    const addZone = (pair, color, label) => {
      if (!pair) return;
      pair.forEach((v, i) => {
        const ln = candleSeries.createPriceLine({
          price: v, color, lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title: label + (i===0?' lo':' hi'),
        });
        window._lines.push(ln);
      });
    };
    const t = sig.trigger || {};
    addZone(t.nearest_fvg_long, '#00d68f', 'FVG-bull');
    addZone(t.nearest_fvg_short, '#ff3d71', 'FVG-bear');
    addZone(t.nearest_ob_long,  '#60a5fa', 'OB-bull');
    addZone(t.nearest_ob_short, '#f472b6', 'OB-bear');
    const f = sig.futures || {};
    if (f.liq_poc_long) {
      window._lines.push(candleSeries.createPriceLine({
        price: f.liq_poc_long, color: '#fbbf24', lineWidth: 1, lineStyle: 3,
        axisLabelVisible: true, title: 'Liq↓ magnet',
      }));
    }
    if (f.liq_poc_short) {
      window._lines.push(candleSeries.createPriceLine({
        price: f.liq_poc_short, color: '#fbbf24', lineWidth: 1, lineStyle: 3,
        axisLabelVisible: true, title: 'Liq↑ magnet',
      }));
    }
    chart.timeScale().fitContent();
  }

  function renderSignal(s) {
    if (s && s.error) {
      document.getElementById('decision').innerHTML =
        '<h2 style="color:#ff3d71">Signal unavailable</h2>' +
        '<div>' + s.error + '</div>';
      document.getElementById('confluence').querySelector('tbody').innerHTML = '';
      document.getElementById('futures').innerHTML = '';
      return;
    }
    const dec = s.decision || '—';
    const score = s.confluence_score;
    document.getElementById('decision').innerHTML =
      `<h2><span class="badge-${dec}">${dec}</span> &middot; Confluence ${score}/12</h2>` +
      `<div><b>Asset:</b> ${s.asset||'BTC'} (${s.macro_kind||'MVRV'}=${(s.mvrv_value||0).toFixed(4)}, ${s.mvrv_regime||'?'})</div>` +
      `<div><b>Bias HTF:</b> ${s.bias_htf} — ${s.bias_reason}</div>` +
      `<div><b>Scenario:</b> ${s.scenario_a||'—'}</div>` +
      `<div><b>Invalidation:</b> ${s.invalidation||'—'}</div>`;
    const tb = document.getElementById('confluence').querySelector('tbody');
    tb.innerHTML = (s.confluence||[]).map((c,i) =>
      `<tr><td>${i+1}</td><td>${c.name}</td><td class="${c.passed?'pass':'fail'}">${c.passed?'PASS':'FAIL'}</td><td>${c.note}</td></tr>`
    ).join('');
    const f = s.futures || {};
    document.getElementById('futures').innerHTML =
      `<table><tr><th>Funding (per 8h)</th><td>${((f.funding_rate||0)*10000).toFixed(2)} bps → ${f.funding_regime||'?'}</td></tr>` +
      `<tr><th>OI trend (12×1h)</th><td>${f.oi_trend} (${f.oi_change_pct}%)</td></tr>` +
      `<tr><th>L/S ratio</th><td>${f.ls_ratio}</td></tr>` +
      `<tr><th>Liq magnet ↓ (longs rekt)</th><td>${f.liq_poc_long}</td></tr>` +
      `<tr><th>Liq magnet ↑ (shorts rekt)</th><td>${f.liq_poc_short}</td></tr>` +
      `<tr><th>Total liq vol (~100 events)</th><td>${(f.liq_total_long||0).toFixed(1)} long / ${(f.liq_total_short||0).toFixed(1)} short</td></tr></table>`;
  }

  function renderPaper(p) {
    if (!p.available) {
      document.getElementById('paper').innerHTML = `<em>${p.note || 'no paper state'}</em>`;
      return;
    }
    const open = (p.open_positions||[]).map(o =>
      `<tr><td>${o.asset}</td><td>${o.direction}</td><td>${o.entry}</td><td>${o.stop}</td><td>${o.tp1}</td><td>${o.confluence_score}/12</td></tr>`
    ).join('');
    const closed = (p.closed_trades||[]).slice(-10).reverse().map(c =>
      `<tr><td>${c.asset}</td><td>${c.direction}</td><td>${c.exit_reason}</td><td>${c.r_multiple}</td><td>${c.pnl_pct}%</td><td>$${c.equity_after}</td></tr>`
    ).join('');
    document.getElementById('paper').innerHTML =
      `<div>Equity: <b>$${p.equity}</b> (starting $${p.starting_equity}) &middot; closed: ${p.closed_trades.length}, open: ${p.open_positions.length}</div>` +
      (open ? `<h4>Open</h4><table><tr><th>Asset</th><th>Dir</th><th>Entry</th><th>SL</th><th>TP1</th><th>Conf</th></tr>${open}</table>` : '') +
      (closed ? `<h4>Recent closed (last 10)</h4><table><tr><th>Asset</th><th>Dir</th><th>Reason</th><th>R</th><th>P&amp;L</th><th>Equity</th></tr>${closed}</table>` : '');
  }

  load();
  // auto-refresh every 60s
  setInterval(load, 60000);
</script>
</body></html>
"""


# -------------------------------------------------------------------------
# HTTP server
# -------------------------------------------------------------------------

def _make_handler(root: Path):
    paper_state = root / "reports" / "paper" / "state.json"

    class H(BaseHTTPRequestHandler):
        def _send_json(self, obj, status: int = 200) -> None:
            body = json.dumps(obj, default=float).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str) -> None:
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            # quieter default logging
            pass

        def do_GET(self) -> None:
            url = urlparse(self.path)
            qs = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/":
                    self._send_html(INDEX_HTML)
                elif url.path == "/api/health":
                    self._send_json({"ok": True, "ts": int(time.time())})
                elif url.path == "/api/signal":
                    asset = (qs.get("asset") or "BTC").upper()
                    self._send_json(_signal_json(asset))
                elif url.path == "/api/candles":
                    asset = (qs.get("asset") or "BTC").upper()
                    tf = qs.get("tf", "15m")
                    # Clamp to [0, 720]; _candles_json treats <=0 as empty.
                    try:
                        limit = int(qs.get("limit", "300"))
                    except ValueError:
                        limit = 300
                    limit = max(0, min(limit, 720))
                    self._send_json(_candles_json(asset, tf, limit))
                elif url.path == "/api/paper":
                    self._send_json(_paper_json(paper_state))
                else:
                    self._send_json({"error": "not found"}, status=404)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)

    return H


def serve(host: str = "127.0.0.1", port: int = 8000,
          root: Path | None = None) -> None:
    root = root or Path(__file__).resolve().parent.parent
    h = _make_handler(root)
    srv = ThreadingHTTPServer((host, port), h)
    print(f"Serving dashboard on http://{host}:{port}/  (root={root})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down.")
    finally:
        srv.server_close()
