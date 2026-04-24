"""Paper trading simulator — stateful forward runner.

On each invocation:
  1. Load state JSON (open positions + closed trades + equity).
  2. For each OPEN position, check if price has hit SL or TP1/TP2 since the
     last observation. First-touch wins; SL ties (same-bar SL+TP hit) go to SL.
  3. For each asset with NO open position, call master_agent.run(asset=...).
     If decision == TRADE, open a new paper position sized by risk_pct.
  4. Write state JSON + append to closed-trades CSV.

Designed to be run by a cron/systemd timer — each invocation is idempotent
for any outcome except actual candle data changes.
"""
from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from . import master_agent
from .data_sources import Candle, fetch_ohlc


@dataclass
class OpenPosition:
    asset: str
    direction: str              # long | short
    entry: float
    stop: float
    tp1: float
    tp2: float | None
    open_ts: int                # unix seconds
    size_pct: float             # % of equity risked (for reporting)
    confluence_score: int
    # Snapshot of equity at the bar where this position was opened. Used
    # to compute a stable dollar P&L even when other positions close in
    # the same tick and mutate state['equity'] before this one resolves.
    # Optional for backward-compat with pre-fix state.json files.
    equity_at_entry: float | None = None


@dataclass
class ClosedTrade:
    asset: str
    direction: str
    entry: float
    stop: float
    tp1: float
    tp2: float | None
    open_ts: int
    close_ts: int
    exit_price: float
    exit_reason: str            # sl | tp1 | tp2 | manual
    pnl_pct: float              # % return on notional (size = 100% of equity)
    r_multiple: float
    equity_after: float


DEFAULT_DIR = Path("reports/paper")
STATE_NAME = "state.json"
TRADES_CSV = "trades.csv"


# -------------------------------------------------------------------------
# State IO
# -------------------------------------------------------------------------

def _state_path(out_dir: Path) -> Path:
    return out_dir / STATE_NAME


def _csv_path(out_dir: Path) -> Path:
    return out_dir / TRADES_CSV


def load_state(out_dir: Path = DEFAULT_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = _state_path(out_dir)
    if not p.exists():
        return {
            "equity": 10_000.0,
            "starting_equity": 10_000.0,
            "last_tick_ts": 0,
            "open_positions": [],
            "closed_trades": [],
        }
    with p.open() as f:
        return json.load(f)


def save_state(state: dict, out_dir: Path = DEFAULT_DIR) -> None:
    with _state_path(out_dir).open("w") as f:
        json.dump(state, f, indent=2, default=float)


def _append_trade_csv(tr: ClosedTrade, out_dir: Path) -> None:
    p = _csv_path(out_dir)
    is_new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow([
                "asset", "direction", "entry", "stop", "tp1", "tp2",
                "open_ts", "close_ts", "exit_price", "exit_reason",
                "pnl_pct", "r_multiple", "equity_after",
            ])
        w.writerow([
            tr.asset, tr.direction, f"{tr.entry:.4f}", f"{tr.stop:.4f}",
            f"{tr.tp1:.4f}", "" if tr.tp2 is None else f"{tr.tp2:.4f}",
            tr.open_ts, tr.close_ts, f"{tr.exit_price:.4f}", tr.exit_reason,
            tr.pnl_pct, tr.r_multiple, f"{tr.equity_after:.2f}",
        ])


# -------------------------------------------------------------------------
# Position mgmt
# -------------------------------------------------------------------------

def _compute_exit(pos: OpenPosition, future: list[Candle], start_ts: int) -> tuple[int, float, str] | None:
    """Return (close_ts, exit_price, reason) if hit; else None."""
    for c in future:
        if c.ts < start_ts:
            continue
        # Pessimistic: if both SL and a TP hit in the same bar, treat SL as
        # first since we can't tell intrabar order. This under-reports wins.
        if pos.direction == "long":
            if c.low <= pos.stop:
                return c.ts, pos.stop, "sl"
            if c.high >= pos.tp1:
                # TP1 always lower than TP2 -> touched first in the bar.
                return c.ts, pos.tp1, "tp1"
        else:
            if c.high >= pos.stop:
                return c.ts, pos.stop, "sl"
            if c.low <= pos.tp1:
                return c.ts, pos.tp1, "tp1"
    return None


def _pnl(pos: OpenPosition, exit_price: float) -> tuple[float, float]:
    """Return (pnl_pct_on_full_notional, r_multiple)."""
    if pos.direction == "long":
        pnl_pct = (exit_price - pos.entry) / pos.entry * 100
        r_mult = (exit_price - pos.entry) / (pos.entry - pos.stop)
    else:
        pnl_pct = (pos.entry - exit_price) / pos.entry * 100
        r_mult = (pos.entry - exit_price) / (pos.stop - pos.entry)
    return pnl_pct, r_mult


# -------------------------------------------------------------------------
# Main tick
# -------------------------------------------------------------------------

def tick(
    assets: list[str],
    risk_pct: float = 1.0,
    out_dir: Path = DEFAULT_DIR,
    timeframe: str = "15m",
) -> dict:
    """One paper-trading iteration.

    Returns a diff summary: {"closed": [...], "opened": [...], "equity": float}.
    """
    state = load_state(out_dir)
    now_ts = int(time.time())
    diff = {"closed": [], "opened": [], "equity": state["equity"]}

    # ---- phase 1: check exits on open positions --------------------
    still_open: list[dict] = []
    # Snapshot the equity BEFORE any P&L applies this tick. Used as the
    # best-effort anchor for legacy positions that predate the
    # equity_at_entry field. If we read state["equity"] inside the loop
    # it would drift as earlier positions close, reintroducing the same
    # order-dependent P&L bug the anchor was meant to fix (and the wrong
    # anchor would also be persisted back to state.json for positions
    # that stay open).
    migration_equity: float = float(state["equity"])
    for pdict in state["open_positions"]:
        pdict.setdefault("equity_at_entry", migration_equity)
        pos = OpenPosition(**pdict)
        try:
            candles, _ = fetch_ohlc(timeframe, pos.asset)  # type: ignore[arg-type]
        except TypeError:
            # master_agent pre-multi-asset: fetch_ohlc has no asset arg
            candles, _ = fetch_ohlc(timeframe)
        exit_info = _compute_exit(pos, candles, start_ts=pos.open_ts + 1)
        if exit_info is None:
            still_open.append(pdict)
            continue
        close_ts, exit_price, reason = exit_info
        pnl_pct, r_mult = _pnl(pos, exit_price)
        # risk-based P&L: anchor at the equity recorded when the position
        # was opened (not the current, mutating equity). This keeps the
        # dollar P&L stable when multiple positions close in the same
        # tick — each position's result is based on the equity it was
        # actually sized against.
        # Fallback goes to migration_equity (the pre-loop snapshot), NOT
        # state["equity"]. dict.setdefault above will leave an explicit
        # null in state.json untouched -> pos.equity_at_entry stays None
        # -> this fallback fires. Using the mutating state["equity"]
        # here would reintroduce the same order-dependent drift.
        anchor = pos.equity_at_entry if pos.equity_at_entry is not None else migration_equity
        equity_delta = anchor * (pos.size_pct / 100.0) * r_mult
        state["equity"] += equity_delta
        tr = ClosedTrade(
            asset=pos.asset, direction=pos.direction, entry=pos.entry,
            stop=pos.stop, tp1=pos.tp1, tp2=pos.tp2,
            open_ts=pos.open_ts, close_ts=close_ts,
            exit_price=exit_price, exit_reason=reason,
            pnl_pct=round(pnl_pct, 3), r_multiple=round(r_mult, 3),
            equity_after=round(state["equity"], 2),
        )
        state["closed_trades"].append(asdict(tr))
        _append_trade_csv(tr, out_dir)
        diff["closed"].append(asdict(tr))
    state["open_positions"] = still_open

    # ---- phase 2: open new positions for each asset ----------------
    held_assets = {p["asset"] for p in state["open_positions"]}
    for asset in assets:
        if asset in held_assets:
            continue
        try:
            sig = master_agent.run(risk_pct=risk_pct, asset=asset)  # type: ignore[call-arg]
        except TypeError:
            # pre-multi-asset branch
            if asset != "BTC":
                continue
            sig = master_agent.run(risk_pct=risk_pct)
        if sig.decision != "TRADE" or sig.direction == "none":
            continue
        if not (sig.entry and sig.stop and sig.tp1):
            continue
        pos = OpenPosition(
            asset=asset, direction=sig.direction,
            entry=sig.entry, stop=sig.stop, tp1=sig.tp1, tp2=sig.tp2,
            open_ts=now_ts, size_pct=risk_pct,
            confluence_score=sig.confluence_score,
            equity_at_entry=state["equity"],
        )
        state["open_positions"].append(asdict(pos))
        diff["opened"].append(asdict(pos))

    state["last_tick_ts"] = now_ts
    diff["equity"] = round(state["equity"], 2)
    save_state(state, out_dir)
    return diff


# -------------------------------------------------------------------------
# Buy-and-hold comparison
# -------------------------------------------------------------------------

def buyhold_pct(asset: str, since_ts: int) -> float | None:
    """Compute % change of <asset> from `since_ts` until now."""
    try:
        candles, _ = fetch_ohlc("1d", asset)  # type: ignore[arg-type]
    except TypeError:
        candles, _ = fetch_ohlc("1d")
    start = next((c for c in candles if c.ts >= since_ts), None)
    if start is None or not candles:
        return None
    return (candles[-1].close - start.open) / start.open * 100
