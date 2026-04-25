"""Standalone trading webapp — TA + MVRV + Coinglass.

A separate stdlib http.server (NOT the one in agents/dashboard.py from
PR #10) that combines:

    - Master Data Agent (TA + MVRV + OKX futures) — agents.master_agent
    - Coinglass v3 microstructure                 — agents.coinglass_*

into a single decision panel that recommends an OPTIMAL entry zone for
long/short with SL/TP1/TP2/RR per AGENT.md Section 4.

Endpoints:
    GET /                         single-page HTML dashboard
    GET /api/decision?asset=BTC   master signal + Coinglass overlay (JSON)
    GET /api/coinglass/funding    multi-exchange funding (JSON)
    GET /api/coinglass/liq        aggregated liquidation history (JSON)
    GET /api/coinglass/heatmap    raw heatmap grid (JSON)
    GET /api/coinglass/oi         OI-weighted OHLC (JSON)
    GET /api/candles?asset=BTC&tf=1h  spot OHLC for the chart (JSON)

Caching:
    Each upstream call is cached in-process for 30 s to avoid hammering
    Kraken/Coinglass. Cache is shared across all concurrent requests.

Auth:
    The webapp itself is unauthenticated — bind it to localhost. The
    Coinglass API key is read from the COINGLASS_API_KEY env var; if
    missing, Coinglass panels show "API key not set" but TA + MVRV
    work fully.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from . import master_agent
from . import coinglass_signals as cgs
from .coinglass_client import CoinglassClient
from .data_sources import fetch_ohlc


# -------------------------------------------------------------------------
# In-process cache (TTL)
# -------------------------------------------------------------------------

_CACHE_TTL = 30.0   # seconds — short enough for 15m bars, kind to upstream
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def _cached(key: str, ttl: float, produce: Callable[[], Any]) -> Any:
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    val = produce()
    with _cache_lock:
        _cache[key] = (now, val)
    return val


# -------------------------------------------------------------------------
# Singleton Coinglass client
# -------------------------------------------------------------------------

_client = CoinglassClient()


# -------------------------------------------------------------------------
# Decision builder
# -------------------------------------------------------------------------

def _decision(asset: str = "BTC") -> dict:
    """Master Data Agent + Coinglass overlay -> single decision dict.

    Catches every exception from the underlying agent (data sources can
    fail intermittently) and converts to a JSON-shaped error so the UI
    can render a friendly message instead of a 500.
    """
    try:
        try:
            sig = master_agent.run(asset=asset)  # type: ignore[arg-type]
        except TypeError:
            # main branch master_agent.run() has no `asset` kwarg yet
            if asset != "BTC":
                return {"error": f"asset={asset} not supported on this branch"}
            sig = master_agent.run()
        sig_d = sig.to_dict()
    except Exception as e:
        return {"error": f"master_agent failed: {e}"}

    current_price = sig.m15.close if sig.m15 else None
    if current_price is None:
        return {"error": "no current price (m15 unavailable)"}

    # ---- Coinglass overlay -----------------------------------------------
    raw_funding = _client.funding_rate_exchange_list(asset)
    raw_liq = _client.liquidation_aggregated_history(asset, "1h", 100)
    raw_heatmap = _client.liquidation_aggregated_heatmap(asset, "3d")
    raw_sent = _client.long_short_position_ratio(asset, "1h", 100)

    funding = cgs.funding_consensus(raw_funding)
    liq = cgs.liq_pressure(raw_liq, lookback=24)
    heatmap = cgs.heatmap_clusters(raw_heatmap, current_price)
    sent = cgs.sentiment(raw_sent)

    extra = cgs.coinglass_confluence(
        sig.direction, funding, liq, heatmap, sent, current_price,
    )

    # Augmented score: existing 12 factors + 2 Coinglass factors. Gate
    # raises proportionally from 7/12 (~58%) to 8/14 (~57%).
    cg_passed = sum(1 for it in extra if it["ok"])
    new_score = sig.confluence_score + cg_passed
    new_decision = "TRADE" if (
        new_score >= 8
        and sig.direction != "none"
        and sig.rr is not None
        and sig.rr >= 2.0
        and not sig.hard_stops
    ) else "NO_TRADE"

    # If Coinglass gives a stronger TP2 magnet, prefer it (only widen, never tighten).
    tp2 = sig_d.get("tp2")
    if sig.direction == "long":
        mag = heatmap.get("magnet_up")
        if mag and tp2 and mag["price"] > tp2:
            tp2 = mag["price"]
    elif sig.direction == "short":
        mag = heatmap.get("magnet_down")
        if mag and tp2 and mag["price"] < tp2:
            tp2 = mag["price"]

    sig_d["confluence_score_total"] = new_score
    sig_d["confluence_max"] = 14
    sig_d["decision_augmented"] = new_decision
    sig_d["tp2_augmented"] = tp2
    sig_d["coinglass"] = {
        "configured": _client.configured,
        "last_error": _client.last_error,
        "funding": funding,
        "liq_pressure": liq,
        "heatmap": heatmap,
        "sentiment": sent,
        "confluence_extra": extra,
    }
    return sig_d


# -------------------------------------------------------------------------
# Candle helper for the chart
# -------------------------------------------------------------------------

def _candles_json(asset: str, tf: str, limit: int) -> list[dict]:
    # Match dashboard.py's behaviour: limit<=0 returns []. Without this
    # guard `c[-0:]` evaluates to `c[:]` and silently returns ALL candles.
    if limit <= 0:
        return []

    def produce() -> list[dict]:
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


# -------------------------------------------------------------------------
# HTML page
# -------------------------------------------------------------------------

INDEX_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8" />
<title>Crypto Decision Engine</title>
<meta name="viewport" content="width=device-width,initial-scale=1" />
<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<style>
  :root { color-scheme: dark; }
  body { background:#0b0e14; color:#e6edf3; font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text',Roboto,Arial,sans-serif;
         margin:0; padding:0; }
  header { padding:14px 20px; background:#11151c; border-bottom:1px solid #1f2630;
           display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
  header h1 { font-size:18px; margin:0; font-weight:600; }
  header .meta { color:#7d8590; font-size:13px; }
  select, button { background:#1f2630; color:#e6edf3; border:1px solid #2a3340;
                   border-radius:6px; padding:6px 10px; font-size:13px; }
  main { display:grid; grid-template-columns: 2fr 1fr; gap:14px; padding:14px 20px; }
  .card { background:#11151c; border:1px solid #1f2630; border-radius:10px; padding:14px; }
  .card h2 { margin:0 0 10px; font-size:14px; color:#a8b3c1; font-weight:600;
             text-transform:uppercase; letter-spacing:0.5px; }
  #chart { height: 540px; }
  .pass { color:#3fb950 } .fail { color:#f85149 } .warn { color:#d29922 }
  .num { font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { text-align:left; padding:6px 4px; border-bottom:1px solid #1f2630; }
  th { color:#7d8590; font-weight:500; }
  .row { display:flex; gap:14px; align-items:center; flex-wrap:wrap; }
  .pill { padding:2px 8px; border-radius:99px; font-size:12px; }
  .pill.long  { background:#0f3a23; color:#3fb950; }
  .pill.short { background:#3a0f1a; color:#f85149; }
  .pill.none, .pill.unknown { background:#262b32; color:#7d8590; }
  .big { font-size:22px; font-weight:600; letter-spacing:-0.3px; }
  .err { color:#f85149; padding:10px; }
  details { margin-top:10px; }
  details summary { cursor:pointer; color:#7d8590; font-size:12px; }
</style></head><body>
<header>
  <h1>Crypto Decision Engine</h1>
  <span class="meta">TA + MVRV + Coinglass</span>
  <select id="asset"><option>BTC</option><option>ETH</option><option>SOL</option></select>
  <select id="tf"><option>1h</option><option selected>4h</option><option>1d</option></select>
  <button id="refresh">Refresh</button>
  <span id="asof" class="meta"></span>
</header>
<main>
  <section class="card" style="grid-row: span 2;">
    <h2>Price &amp; Zones</h2>
    <div id="chart"></div>
  </section>
  <section class="card">
    <h2>Decision</h2>
    <div id="decision">Loading...</div>
  </section>
  <section class="card">
    <h2>Coinglass Microstructure</h2>
    <div id="coinglass">Loading...</div>
  </section>
  <section class="card" style="grid-column: span 2;">
    <h2>Confluence Matrix</h2>
    <table id="confluence"><thead><tr><th>#</th><th>Factor</th><th>Pass</th><th>Reason</th></tr></thead><tbody></tbody></table>
  </section>
</main>
<script>
const $ = id => document.getElementById(id);
let chart, candleSeries;

function initChart() {
  chart = LightweightCharts.createChart($('chart'), {
    layout: { background:{color:'#11151c'}, textColor:'#a8b3c1' },
    grid:   { vertLines:{color:'#1f2630'}, horzLines:{color:'#1f2630'} },
    timeScale: { timeVisible:true, secondsVisible:false },
    rightPriceScale: { borderColor:'#1f2630' },
  });
  candleSeries = chart.addCandlestickSeries({
    upColor:'#3fb950', downColor:'#f85149',
    borderUpColor:'#3fb950', borderDownColor:'#f85149',
    wickUpColor:'#3fb950', wickDownColor:'#f85149',
  });
}

function fmt(x, d=2) {
  if (x === null || x === undefined) return '—';
  return Number(x).toLocaleString(undefined, {minimumFractionDigits:d, maximumFractionDigits:d});
}

function pill(direction) {
  if (!direction) return '<span class="pill none">none</span>';
  return `<span class="pill ${direction}">${direction}</span>`;
}

async function loadCandles(asset, tf) {
  const r = await fetch(`/api/candles?asset=${asset}&tf=${tf}&limit=300`);
  const rows = await r.json();
  if (!Array.isArray(rows)) { candleSeries.setData([]); return; }
  candleSeries.setData(rows);
}

function renderDecision(s) {
  if (s.error) {
    $('decision').innerHTML = `<div class="err">${s.error}</div>`;
    $('confluence').querySelector('tbody').innerHTML = '';
    return;
  }
  const dir = s.direction || 'none';
  const dec = s.decision_augmented || s.decision || '—';
  const score = s.confluence_score_total ?? s.confluence_score;
  const cap = s.confluence_max ?? 12;
  const tp2 = s.tp2_augmented ?? s.tp2;
  $('decision').innerHTML = `
    <div class="row" style="justify-content:space-between;">
      <div class="big">${dec}</div>
      <div>${pill(dir)} ${score}/${cap}</div>
    </div>
    <table>
      <tr><th>Bias HTF</th><td>${s.bias_htf} <span class="meta">(${s.bias_reason||''})</span></td></tr>
      <tr><th>MVRV</th><td>${fmt(s.mvrv_value,2)} — ${s.mvrv_regime} (${s.mvrv_direction})</td></tr>
      <tr><th>Entry</th><td class="num">${fmt(s.entry,2)}</td></tr>
      <tr><th>Stop</th><td class="num">${fmt(s.stop,2)}</td></tr>
      <tr><th>TP1</th><td class="num">${fmt(s.tp1,2)}</td></tr>
      <tr><th>TP2</th><td class="num">${fmt(tp2,2)} ${s.tp2_augmented && s.tp2_augmented !== s.tp2 ? '<span class="meta">(magnet)</span>' : ''}</td></tr>
      <tr><th>RR</th><td class="num">${fmt(s.rr,2)}</td></tr>
      <tr><th>Size</th><td>${s.size_hint||'—'}</td></tr>
    </table>
    ${s.hard_stops && s.hard_stops.length ? '<details open><summary>Hard stops</summary><ul>'+s.hard_stops.map(x=>`<li class="warn">${x}</li>`).join('')+'</ul></details>' : ''}
  `;
}

function renderCoinglass(cg) {
  if (!cg) { $('coinglass').innerHTML = '<div class="err">No data</div>'; return; }
  if (!cg.configured) {
    $('coinglass').innerHTML = '<div class="warn">COINGLASS_API_KEY not set — set it and restart to enable heatmap, multi-exchange funding, OI, and sentiment panels.</div>';
    return;
  }
  if (cg.last_error) {
    $('coinglass').innerHTML = `<div class="err">Coinglass error: ${cg.last_error}</div>`;
    return;
  }
  const f = cg.funding || {}, liq = cg.liq_pressure || {}, hm = cg.heatmap || {}, sent = cg.sentiment || {};
  const upMag = hm.magnet_up, dnMag = hm.magnet_down;
  $('coinglass').innerHTML = `
    <table>
      <tr><th>Funding (median, ${f.n_exchanges||0} ex)</th>
          <td>${fmt(f.median_pct,4)}% <span class="meta">${f.regime||'—'}</span></td></tr>
      <tr><th>Liq pressure (24h)</th>
          <td>longs ${fmt(liq.long_liq_usd,0)} / shorts ${fmt(liq.short_liq_usd,0)} <span class="meta">${liq.net_pressure||'—'}</span></td></tr>
      <tr><th>Magnet up</th><td>${upMag ? fmt(upMag.price,2)+' (+'+fmt(upMag.distance_pct,2)+'%)' : '—'}</td></tr>
      <tr><th>Magnet down</th><td>${dnMag ? fmt(dnMag.price,2)+' ('+fmt(dnMag.distance_pct,2)+'%)' : '—'}</td></tr>
      <tr><th>Top trader L/S</th><td>${fmt(sent.long_pct,1)}% / ${fmt(sent.short_pct,1)}% <span class="meta">${sent.skew||'—'}</span></td></tr>
    </table>
  `;
}

function renderConfluence(s) {
  const tbody = $('confluence').querySelector('tbody');
  if (s.error) { tbody.innerHTML = ''; return; }
  const all = (s.confluence||[]).map(c => ({name:c.name, ok:c.passed, reason:c.reason}));
  const extra = (s.coinglass && s.coinglass.confluence_extra) || [];
  const rows = [...all, ...extra];
  tbody.innerHTML = rows.map((c,i) =>
    `<tr><td>${i+1}</td><td>${c.name}</td>
     <td class="${c.ok?'pass':'fail'}">${c.ok?'PASS':'fail'}</td>
     <td><span class="meta">${c.reason||''}</span></td></tr>`).join('');
}

async function refresh() {
  const asset = $('asset').value, tf = $('tf').value;
  const [decisionResp, _] = await Promise.all([
    fetch(`/api/decision?asset=${asset}`).then(r=>r.json()),
    loadCandles(asset, tf),
  ]);
  $('asof').textContent = decisionResp.as_of ? `as_of ${decisionResp.as_of}` : '';
  renderDecision(decisionResp);
  renderCoinglass(decisionResp.coinglass);
  renderConfluence(decisionResp);
  chart.timeScale().fitContent();
}

initChart();
refresh();
$('refresh').addEventListener('click', refresh);
$('asset').addEventListener('change', refresh);
$('tf').addEventListener('change', refresh);
</script></body></html>
"""


# -------------------------------------------------------------------------
# HTTP handler
# -------------------------------------------------------------------------

class WebappHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        # Use stderr line format; less chatty than the default.
        print(f"[webapp] {self.address_string()} - {fmt % args}", flush=True)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, default=float).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib API)
        try:
            url = urllib.parse.urlparse(self.path)
            qs = dict(urllib.parse.parse_qsl(url.query))
            asset = (qs.get("asset") or "BTC").upper()

            if url.path == "/" or url.path == "/index.html":
                return self._send_html(INDEX_HTML)

            if url.path == "/api/decision":
                return self._send_json(_cached(
                    f"decision:{asset}", _CACHE_TTL, lambda: _decision(asset)
                ))

            if url.path == "/api/candles":
                tf = qs.get("tf", "1h")
                try:
                    limit = int(qs.get("limit", "300"))
                except ValueError:
                    limit = 300
                limit = max(0, min(limit, 720))
                return self._send_json(_candles_json(asset, tf, limit))

            if url.path == "/api/coinglass/funding":
                return self._send_json(_cached(
                    f"funding:{asset}", _CACHE_TTL,
                    lambda: cgs.funding_consensus(_client.funding_rate_exchange_list(asset)),
                ))

            if url.path == "/api/coinglass/liq":
                return self._send_json(_cached(
                    f"liq:{asset}", _CACHE_TTL,
                    lambda: cgs.liq_pressure(
                        _client.liquidation_aggregated_history(asset, "1h", 100)),
                ))

            if url.path == "/api/coinglass/heatmap":
                return self._send_json(_cached(
                    f"heatmap_raw:{asset}", _CACHE_TTL,
                    lambda: _client.liquidation_aggregated_heatmap(asset, "3d") or {},
                ))

            if url.path == "/api/coinglass/oi":
                return self._send_json(_cached(
                    f"oi:{asset}", _CACHE_TTL,
                    lambda: _client.oi_weight_ohlc_history(asset, "1h", 100) or [],
                ))

            return self._send_json({"error": f"unknown path: {url.path}"}, status=404)
        except Exception as e:
            return self._send_json({"error": f"server: {e}"}, status=500)


# -------------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------------

def serve(host: str = "127.0.0.1", port: int = 8889) -> None:
    """Start the threaded HTTP server. Blocks until KeyboardInterrupt."""
    srv = ThreadingHTTPServer((host, port), WebappHandler)
    print(f"[webapp] listening on http://{host}:{port}", flush=True)
    print(f"[webapp] coinglass configured: {_client.configured}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("[webapp] shutting down", flush=True)
        srv.shutdown()
