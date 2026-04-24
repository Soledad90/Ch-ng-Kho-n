"""Render MasterSignal in the AGENT.md Section 4 schema."""
from __future__ import annotations

import json
from pathlib import Path

from .master_agent import MasterSignal


def _fmt(x, n: int = 2) -> str:
    if x is None:
        return "—"
    if isinstance(x, (int, float)):
        return f"{x:,.{n}f}"
    return str(x)


def _zone(z) -> str:
    if z is None:
        return "—"
    lo, hi = z
    return f"${lo:,.2f} — ${hi:,.2f}"


def to_markdown(s: MasterSignal) -> str:
    conf_rows = "\n".join(
        f"| {i+1} | {c.name} | {'PASS' if c.passed else 'FAIL'} | {c.note} |"
        for i, c in enumerate(s.confluence)
    )
    hard_stops_md = "\n".join(f"- {h}" for h in s.hard_stops) or "- (none)"
    decision_badge = s.decision

    return f"""# BTC/USDT — {s.as_of}

## Decision: {decision_badge}  (Confluence {s.confluence_score}/8)

**Scenario A:** {s.scenario_a}
**Invalidation:** {s.invalidation}
**Size hint:** {s.size_hint}

### Hard-stops (AGENT.md)
{hard_stops_md}

---

## 1. Bias HTF

| Timeframe | Trend |
|-----------|-------|
| W1 (proxy) | {s.bias_w1} |
| D1 | {s.bias_d1} |
| H4 | {s.bias_h4} |

**Kết luận Bias:** **{s.bias_htf.upper()}** — {s.bias_reason}
**MVRV overlay:** {s.mvrv_regime} (value={s.mvrv_value:.2f}, direction={s.mvrv_direction})

## 2. POI & Liquidity

| Field | Value |
|---|---|
| D1 swing | ${_fmt(s.d1.swing_low)} — ${_fmt(s.d1.swing_high)} |
| Premium zone (upper 50%) | ${_fmt(s.poi.premium_zone[0])} — ${_fmt(s.poi.premium_zone[1])} |
| Discount zone (lower 50%) | ${_fmt(s.poi.discount_zone[0])} — ${_fmt(s.poi.discount_zone[1])} |
| Current price in | **{s.poi.current_in}** |
| OTE long (Fib 0.618-0.79) | ${_fmt(s.poi.ote_long[0])} — ${_fmt(s.poi.ote_long[1])} |
| OTE short (Fib 0.618-0.79) | ${_fmt(s.poi.ote_short[0])} — ${_fmt(s.poi.ote_short[1])} |
| Nearest support | ${_fmt(s.poi.nearest_support)} |
| Nearest resistance | ${_fmt(s.poi.nearest_resistance)} |

## 3. Trigger (M15)

| Field | Value |
|---|---|
| Liquidity sweep | {s.trigger.sweep} @ {_fmt(s.trigger.sweep_price)} |
| CHoCH | {s.trigger.choch} @ {_fmt(s.trigger.choch_price)} |
| Nearest unmitigated bullish FVG (below) | {_zone(s.trigger.nearest_fvg_long)} |
| Nearest unmitigated bearish FVG (above) | {_zone(s.trigger.nearest_fvg_short)} |
| Nearest unmitigated bullish OB (demand) | {_zone(s.trigger.nearest_ob_long)} |
| Nearest unmitigated bearish OB (supply) | {_zone(s.trigger.nearest_ob_short)} |

## 4. Futures Microstructure (OKX)

| Field | Value |
|---|---|
| Funding rate (per 8h) | {s.futures.funding_rate * 10000:.2f} bps → **{s.futures.funding_regime}** |
| OI trend (12x1h) | {s.futures.oi_trend} ({s.futures.oi_change_pct}%) |
| Long/Short account ratio | {s.futures.ls_ratio} |
| Liq magnet below (longs rekt) | ${_fmt(s.futures.liq_poc_long)} |
| Liq magnet above (shorts rekt) | ${_fmt(s.futures.liq_poc_short)} |
| Total liq volume (~100 events) | {s.futures.liq_total_long:.1f} long / {s.futures.liq_total_short:.1f} short |

## 5. Confluence Matrix (pass ≥ 7/12)

| # | Factor | Result | Note |
|---|--------|--------|------|
{conf_rows}

**Score: {s.confluence_score}/12** → {'ENOUGH' if s.confluence_score >= 7 else 'NOT ENOUGH'}

## 6. Execution Plan

| Field | Value |
|---|---|
| Direction | {s.direction.upper()} |
| Entry | ${_fmt(s.entry)} |
| Stop | ${_fmt(s.stop)} |
| TP1 | ${_fmt(s.tp1)} |
| TP2 | ${_fmt(s.tp2)} |
| RR(TP1) | {s.rr if s.rr is not None else '—'} |
| Risk per trade | {s.risk_pct}% of equity |

## Timeframe Snapshots

| TF | Close | EMA20 | EMA50 | EMA200 | RSI | MACD-hist | ATR | Trend |
|---|---|---|---|---|---|---|---|---|
| D1 | ${_fmt(s.d1.close)} | ${_fmt(s.d1.ema20)} | ${_fmt(s.d1.ema50)} | ${_fmt(s.d1.ema200)} | {_fmt(s.d1.rsi14,1)} | {_fmt(s.d1.macd_hist,2)} | ${_fmt(s.d1.atr14)} | {s.d1.trend} |
| H4 | ${_fmt(s.h4.close)} | ${_fmt(s.h4.ema20)} | ${_fmt(s.h4.ema50)} | ${_fmt(s.h4.ema200)} | {_fmt(s.h4.rsi14,1)} | {_fmt(s.h4.macd_hist,2)} | ${_fmt(s.h4.atr14)} | {s.h4.trend} |
| H1 | ${_fmt(s.h1.close)} | ${_fmt(s.h1.ema20)} | ${_fmt(s.h1.ema50)} | ${_fmt(s.h1.ema200)} | {_fmt(s.h1.rsi14,1)} | {_fmt(s.h1.macd_hist,2)} | ${_fmt(s.h1.atr14)} | {s.h1.trend} |
| M15 | ${_fmt(s.m15.close)} | ${_fmt(s.m15.ema20)} | ${_fmt(s.m15.ema50)} | ${_fmt(s.m15.ema200)} | {_fmt(s.m15.rsi14,1)} | {_fmt(s.m15.macd_hist,2)} | ${_fmt(s.m15.atr14)} | {s.m15.trend} |

---

Source: `{s.source}` · AGENT.md blueprint · Master Data Agent
"""


def to_json(s: MasterSignal) -> str:
    return json.dumps(s.to_dict(), indent=2, default=float)


def save(md: str, js: str, out_dir: Path, tag: str = "BTCUSDT_MASTER") -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md_path = out_dir / f"{stamp}_{tag}.md"
    js_path = out_dir / f"{stamp}_{tag}.json"
    md_path.write_text(md)
    js_path.write_text(js)
    return md_path, js_path
