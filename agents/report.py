"""Render MVRV + TA + Plan to markdown + JSON."""
from __future__ import annotations

import json
from pathlib import Path

from .mvrv_agent import MvrvSignal
from .orchestrator import EntryPlan
from .ta_agent import TaSignal


def _fmt(x: float | None, n: int = 2) -> str:
    return "-" if x is None else f"{x:,.{n}f}"


def to_markdown(mvrv: MvrvSignal, ta: TaSignal, plan: EntryPlan) -> str:
    tranches_md = (
        "\n".join(
            f"  - Tranche {i+1}: ${_fmt(p)} ({w*100:.0f}% of size)"
            for i, (p, w) in enumerate(plan.tranches)
        )
        or "  - (no new entry)"
    )
    supports_md = ", ".join(f"${_fmt(s)}" for s in ta.supports) or "-"
    resistances_md = ", ".join(f"${_fmt(r)}" for r in ta.resistances) or "-"

    return f"""# BTC/USDT Entry Plan — {mvrv.as_of}

## Decision: **{plan.action}**   (confidence {plan.confidence:.0%})

- Entry zone: **${_fmt(plan.entry_zone[0])} — ${_fmt(plan.entry_zone[1])}**
- Stop: ${_fmt(plan.stop)}
- TP1: ${_fmt(plan.tp1)}   |   TP2: ${_fmt(plan.tp2)}
- RR(TP1): **{plan.rr}**   |   Size multiplier (MVRV): **x{plan.size_multiplier}**

Tranches
{tranches_md}

Rationale
{chr(10).join('- ' + r for r in plan.rationale)}

---

## MVRV Agent (on-chain valuation)

| Field | Value |
|---|---|
| As of | {mvrv.as_of} |
| BTC price | ${_fmt(mvrv.btc_price)} |
| Realized price | ${_fmt(mvrv.realized_price)} |
| MVRV | {mvrv.mvrv:.2f} |
| Percentile (lifetime) | {mvrv.percentile:.1f}% |
| Z-score (365d) | {mvrv.z_score:+.2f} |
| Regime | **{mvrv.regime}** |
| Size multiplier | x{mvrv.size_multiplier} |
| Direction | {mvrv.direction} |
| Signal | {mvrv.signal} |

## TA Agent ({ta.timeframe}, source: {ta.source})

| Field | Value |
|---|---|
| Close | ${_fmt(ta.close)} |
| EMA 20 / 50 / 200 | ${_fmt(ta.ema20)} / ${_fmt(ta.ema50)} / ${_fmt(ta.ema200)} |
| RSI(14) | {_fmt(ta.rsi14, 1)} |
| MACD / signal / hist | {_fmt(ta.macd)} / {_fmt(ta.macd_signal)} / {_fmt(ta.macd_hist)} |
| ATR(14) | {_fmt(ta.atr14)} |
| Ichimoku Tenkan / Kijun | ${_fmt(ta.ichimoku_tenkan)} / ${_fmt(ta.ichimoku_kijun)} |
| Ichimoku Span A / B | ${_fmt(ta.ichimoku_span_a)} / ${_fmt(ta.ichimoku_span_b)} |
| Trend / Momentum / Cloud | {ta.trend} / {ta.momentum} / {ta.cloud_state} |
| Direction | {ta.direction} |
| Swing range | ${_fmt(ta.swing_low)} — ${_fmt(ta.swing_high)} |
| Fib 0.382 / 0.500 / 0.618 | ${_fmt(ta.fib['0.382'])} / ${_fmt(ta.fib['0.500'])} / ${_fmt(ta.fib['0.618'])} |
| Supports | {supports_md} |
| Resistances | {resistances_md} |
| Volume profile POC | ${_fmt(ta.vp_poc)} |
| Value area VAL / VAH | ${_fmt(ta.vp_val)} / ${_fmt(ta.vp_vah)} |
"""


def to_json(mvrv: MvrvSignal, ta: TaSignal, plan: EntryPlan) -> str:
    return json.dumps(
        {"mvrv": mvrv.to_dict(), "ta": ta.to_dict(), "plan": plan.to_dict()},
        indent=2,
        default=float,
    )


def save(md: str, payload: str, out_dir: Path, tag: str = "BTCUSDT_1d") -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md_path = out_dir / f"{stamp}_{tag}.md"
    js_path = out_dir / f"{stamp}_{tag}.json"
    md_path.write_text(md)
    js_path.write_text(payload)
    return md_path, js_path
