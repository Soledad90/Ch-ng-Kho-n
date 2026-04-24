"""Backtest the Master Data Agent decision engine on historical D1 BTC data.

Simplified variant:
- D1 only (Kraken public API caps at ~720 bars — we don't have H4/M15 for 2y).
- Futures microstructure (funding/OI/liq) DROPPED because no deep history
  without a paid Coinglass/CryptoQuant key. Confluence therefore scores /8
  instead of /12, with threshold 5/8 to stay proportionally equivalent.
- Entry/SL/TP use the same `_build_execution` formulas the live agent uses.

Exit policy:
- Walk forward bar-by-bar. First touch of SL -> loss. First touch of TP1 -> win.
  Time-out after `max_hold` bars -> exit at that bar's close.
- No multi-target scaling (TP2 ignored to keep stats comparable).
"""
from __future__ import annotations

import csv
import statistics
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from . import indicators as ind
from . import mvrv_agent
from .data_sources import Candle, fetch_ohlc
from .master_agent import (
    POI, Trigger, TFSnapshot, ConfluenceItem, Direction,
    _classify_trend, _poi, _detect_sweep, _detect_choch,
    _fvg_ob_from_candles, _build_execution,
)


@dataclass
class BacktestTrade:
    open_ts: int
    close_ts: int
    direction: str
    entry: float
    stop: float
    tp1: float
    exit_price: float
    exit_reason: str            # "tp1" | "sl" | "timeout"
    bars_held: int
    pnl_pct: float              # % return vs entry (position size = 100%)
    r_multiple: float           # realized (exit-entry) / (entry-stop) for long; mirror
    confluence_score: int


@dataclass
class BacktestStats:
    n_trades: int
    n_longs: int
    n_shorts: int
    win_rate: float
    avg_r: float
    median_r: float
    total_return_pct: float     # compound
    max_drawdown_pct: float
    buyhold_return_pct: float
    avg_bars_held: float
    longest_win_streak: int
    longest_loss_streak: int
    sharpe_like: float


def _date_of(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def _load_mvrv_map(csv_path: Path) -> dict[str, tuple[float, float]]:
    """date-string -> (mvrv, realized_price)"""
    out: dict[str, tuple[float, float]] = {}
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                out[row["date"]] = (float(row["mvrv"]), float(row["realized_price_usd"]))
            except (KeyError, ValueError):
                continue
    return out


def _mvrv_regime(mvrv_value: float, hist: list[float]) -> tuple[str, str]:
    """Classify by percentile (kept in sync with mvrv_agent logic)."""
    srt = sorted(hist)
    n = len(srt)
    if not n:
        return "unknown", "none"
    idx = sum(1 for v in srt if v <= mvrv_value)
    pct = idx / n * 100
    if pct <= 10:
        return "Deep Value", "bullish"
    if pct <= 30:
        return "Discount", "bullish"
    if pct < 70:
        return "Neutral", "none"
    if pct < 90:
        return "Hot", "bearish"
    return "Euphoria", "bearish"


def _snap_from_candles(tf: str, candles: list[Candle]) -> TFSnapshot | None:
    if len(candles) < 200:
        return None
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    vols = [c.volume for c in candles]
    look = min(90, len(candles))
    sh = max(highs[-look:])
    sl = min(lows[-look:])
    _, _, macd_hist = ind.macd(closes)
    vp = ind.volume_profile(highs, lows, closes, vols)
    trend = _classify_trend(closes[-1], ind.ema(closes, 20)[-1],
                            ind.ema(closes, 50)[-1], ind.ema(closes, 200)[-1])
    return TFSnapshot(
        tf=tf, close=closes[-1],
        ema20=ind.ema(closes, 20)[-1],
        ema50=ind.ema(closes, 50)[-1],
        ema200=ind.ema(closes, 200)[-1],
        rsi14=ind.rsi(closes, 14)[-1],
        macd_hist=macd_hist[-1],
        atr14=ind.atr(highs, lows, closes, 14)[-1],
        trend=trend,
        swing_high=sh, swing_low=sl, mid=(sh + sl) / 2,
        poc=vp.get("poc"),
    )


def _decide_backtest(candles: list[Candle], mvrv_dir: str) -> tuple[Direction, str, POI, Trigger, TFSnapshot, int]:
    snap = _snap_from_candles("1d", candles)
    if snap is None:
        return "none", "not-enough-bars", None, None, None, 0  # type: ignore

    # Bias: D1 trend + MVRV macro. If they disagree, bias=range.
    d1_trend = snap.trend
    if d1_trend == "up" and mvrv_dir != "bearish":
        bias = "bullish"
    elif d1_trend == "down" and mvrv_dir != "bullish":
        bias = "bearish"
    else:
        bias = "range"

    poi = _poi(snap)
    sweep_dir, sweep_price = _detect_sweep(candles, lookback=30)
    choch_dir, choch_price = _detect_choch(candles)
    zones = _fvg_ob_from_candles(candles)
    trig = Trigger(
        sweep=sweep_dir, sweep_price=sweep_price,
        choch=choch_dir, choch_price=choch_price,
        nearest_fvg_long=zones["fvg_long"], nearest_fvg_short=zones["fvg_short"],
        nearest_ob_long=zones["ob_long"], nearest_ob_short=zones["ob_short"],
    )

    # direction
    direction: Direction
    if bias == "bullish" and trig.sweep == "bullish" and trig.choch == "bullish":
        direction = "long"
    elif bias == "bearish" and trig.sweep == "bearish" and trig.choch == "bearish":
        direction = "short"
    elif bias == "bullish" and poi.current_in in ("discount", "mid"):
        direction = "long"
    elif bias == "bearish" and poi.current_in in ("premium", "mid"):
        direction = "short"
    else:
        direction = "none"

    # Confluence (8 factors, futures skipped in backtest)
    score = 0
    if direction != "none":
        want_sweep = "bullish" if direction == "long" else "bearish"
        # 1 bias HTF
        if bias == ("bullish" if direction == "long" else "bearish"):
            score += 1
        # 2 POI valid
        if direction == "long" and poi.current_in in ("discount", "mid"):
            score += 1
        elif direction == "short" and poi.current_in in ("premium", "mid"):
            score += 1
        # 3 sweep
        if trig.sweep == want_sweep:
            score += 1
        # 4 CHoCH
        if trig.choch == want_sweep:
            score += 1
        # 5 Fib OTE
        if direction == "long":
            lo, hi = poi.ote_long
        else:
            lo, hi = poi.ote_short
        if lo <= snap.close <= hi:
            score += 1
        # 6 Volume profile POC (±1%)
        if snap.poc and abs(snap.close - snap.poc) / snap.close < 0.01:
            score += 1
        # 7 Momentum
        rsi_v = snap.rsi14 or 50
        if direction == "long" and rsi_v > 45 and (snap.macd_hist or 0) > 0:
            score += 1
        elif direction == "short" and rsi_v < 55 and (snap.macd_hist or 0) < 0:
            score += 1
        # 8 OB/FVG zone proximity (±0.5 ATR)
        zone = (trig.nearest_ob_long or trig.nearest_fvg_long) if direction == "long" \
               else (trig.nearest_ob_short or trig.nearest_fvg_short)
        atr = snap.atr14 or (snap.close * 0.005)
        if zone:
            lo, hi = zone
            if (lo - 0.5 * atr) <= snap.close <= (hi + 0.5 * atr):
                score += 1

    return direction, bias, poi, trig, snap, score


def _walk_forward_exit(
    direction: str, entry: float, stop: float, tp1: float,
    future: list[Candle], max_hold: int, fill_window: int,
) -> tuple[int, float, str, int, int] | None:
    """Two-phase fill-then-exit simulator.

    Phase 1 (fill validation): walk forward up to `fill_window` bars and
    wait for price to actually touch the limit entry level. For a long,
    that means ``bar.low <= entry``; for a short, ``bar.high >= entry``.
    If the market gaps away and never pulls back within `fill_window`
    bars, return ``None`` (no fill, no trade recorded).

    Phase 2 (exit walk): starting from the fill bar, walk up to
    `max_hold` bars and return on first SL/TP1 touch, or time-out.
    Pessimistic same-bar rule: if a single bar touches both SL and TP1
    (including the fill bar), SL wins.

    Returns ``(close_ts, exit_price, reason, bars_held_from_entry, fill_idx)``
    where ``fill_idx`` is the 1-based offset from the signal bar at which
    the entry actually filled (1 = next bar). Returns ``None`` when the
    entry was never filled within ``fill_window``.
    """
    # Phase 1: find the fill bar.
    fill_idx: int | None = None
    for i, c in enumerate(future[:fill_window], start=1):
        if direction == "long" and c.low <= entry:
            fill_idx = i
            break
        if direction == "short" and c.high >= entry:
            fill_idx = i
            break
    if fill_idx is None:
        return None

    # Phase 2: walk from the fill bar (inclusive) through max_hold.
    bars = future[fill_idx - 1 : fill_idx - 1 + max_hold]
    for j, c in enumerate(bars, start=1):
        if direction == "long":
            if c.low <= stop:
                return c.ts, stop, "sl", j, fill_idx
            if c.high >= tp1:
                return c.ts, tp1, "tp1", j, fill_idx
        else:
            if c.high >= stop:
                return c.ts, stop, "sl", j, fill_idx
            if c.low <= tp1:
                return c.ts, tp1, "tp1", j, fill_idx
    if bars:
        last = bars[-1]
        return last.ts, last.close, "timeout", len(bars), fill_idx
    return None


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def run_backtest(
    max_hold: int = 20,
    confluence_min: int = 5,
    rr_min: float = 2.0,
    out_dir: str | None = "reports/backtest",
    cooldown_bars: int = 3,
    fill_window: int = 5,
) -> tuple[BacktestStats, list[BacktestTrade]]:
    """Replay the decision engine on historical D1 candles.

    Parameters
    ----------
    max_hold : bars to hold a trade before time-out exit.
    confluence_min : minimum score /8 to trade.
    rr_min : minimum RR(TP1) required.
    cooldown_bars : bars to skip after exit (to avoid opening at the same bar).
    fill_window : bars after signal within which the limit entry must be
        touched by price; if never touched, the trade is dropped (not
        recorded as filled). This prevents phantom fills on gap-away
        moves where price never revisits the OTE entry.
    """
    candles, source = fetch_ohlc("1d")
    if len(candles) < 250:
        raise RuntimeError(f"Need >=250 daily bars, got {len(candles)}")
    mvrv_map = _load_mvrv_map(Path(__file__).resolve().parent.parent / "data" / "mvrv_btc.csv")
    # IMPORTANT: keep this a list, NOT a set. Percentiles are a
    # frequency distribution — deduplicating unique MVRV values (~429
    # of them vs 5562 observations) skews the histogram towards rare
    # extremes and misclassifies ~47% of bars (e.g. MVRV=2.6 becomes
    # "Neutral"/direction=none under a set but is "Hot"/bearish under
    # the true CSV frequency).
    mvrv_hist = sorted(v[0] for v in mvrv_map.values())

    trades: list[BacktestTrade] = []
    i = 200
    last_exit_bar = -999
    while i < len(candles) - 1:
        if i < last_exit_bar + cooldown_bars:
            i += 1
            continue
        window = candles[: i + 1]
        date_str = _date_of(candles[i].ts)
        mvrv_tuple = mvrv_map.get(date_str)
        if mvrv_tuple is None:
            # approximate via most-recent known value
            nearest = max((d for d in mvrv_map if d <= date_str), default=None)
            mvrv_tuple = mvrv_map.get(nearest) if nearest else None
        if mvrv_tuple is None:
            i += 1
            continue
        mvrv_val, _realized = mvrv_tuple
        _regime, mvrv_dir = _mvrv_regime(mvrv_val, mvrv_hist)

        direction, _bias, poi, _trig, snap, score = _decide_backtest(window, mvrv_dir)
        if direction == "none" or snap is None:
            i += 1
            continue
        entry, stop, tp1, tp2 = _build_execution(direction, poi, snap, snap)
        if entry is None or stop is None or tp1 is None:
            i += 1
            continue
        risk = abs(entry - stop) or 1e-9
        reward = abs(tp1 - entry)
        rr = reward / risk
        if rr < rr_min or score < confluence_min:
            i += 1
            continue

        # Simulate fill-then-exit. Trade is only recorded if the market
        # actually trades through the limit entry within `fill_window`
        # bars (otherwise gap-away moves would produce phantom fills).
        future = candles[i + 1:]
        result = _walk_forward_exit(
            direction, entry, stop, tp1, future, max_hold, fill_window,
        )
        if result is None:
            # No fill within fill_window; walk forward one bar and retry.
            i += 1
            continue
        close_ts, exit_price, reason, held, fill_idx = result

        if direction == "long":
            pnl_pct = (exit_price - entry) / entry * 100
            r_mult = (exit_price - entry) / (entry - stop)
        else:
            pnl_pct = (entry - exit_price) / entry * 100
            r_mult = (entry - exit_price) / (stop - entry)

        trades.append(BacktestTrade(
            open_ts=candles[i].ts, close_ts=close_ts,
            direction=direction, entry=entry, stop=stop, tp1=tp1,
            exit_price=exit_price, exit_reason=reason, bars_held=held,
            pnl_pct=round(pnl_pct, 3), r_multiple=round(r_mult, 3),
            confluence_score=score,
        ))
        # Exit bar index in the full `candles` array =
        #   signal_bar (i) + fill_delay (fill_idx) + exit_offset (held - 1).
        # Example: fill_idx=3, held=2 -> fill at i+3, exit at i+3+1 = i+4.
        # Previously we used `i + held` which ignored fill delay and could
        # let the next signal scan start while the prior trade was still
        # (notionally) open, breaking cooldown enforcement.
        last_exit_bar = i + fill_idx + held - 1
        i = last_exit_bar + 1

    stats = _compute_stats(trades, candles)
    if out_dir:
        _save(out_dir, trades, stats, source)
    return stats, trades


def _compute_stats(trades: list[BacktestTrade], candles: list[Candle]) -> BacktestStats:
    if not trades:
        return BacktestStats(0, 0, 0, 0, 0, 0, 0, 0,
                             _buyhold(candles), 0, 0, 0, 0)
    wins = sum(1 for t in trades if t.r_multiple > 0)
    longs = sum(1 for t in trades if t.direction == "long")
    # compound equity curve
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for t in trades:
        equity *= 1 + t.pnl_pct / 100
        peak = max(peak, equity)
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)
    total_ret = (equity - 1) * 100
    rs = [t.r_multiple for t in trades]
    pnls = [t.pnl_pct for t in trades]
    mean_r = statistics.fmean(rs)
    stdev_pnl = statistics.pstdev(pnls) or 1.0
    # "sharpe-like" = mean / stdev of trade-level returns (not annualised)
    sharpe = statistics.fmean(pnls) / stdev_pnl
    # streaks
    win_streak = loss_streak = cur_w = cur_l = 0
    for t in trades:
        if t.r_multiple > 0:
            cur_w += 1; cur_l = 0
            win_streak = max(win_streak, cur_w)
        else:
            cur_l += 1; cur_w = 0
            loss_streak = max(loss_streak, cur_l)
    avg_held = statistics.fmean(t.bars_held for t in trades)

    return BacktestStats(
        n_trades=len(trades),
        n_longs=longs,
        n_shorts=len(trades) - longs,
        win_rate=round(wins / len(trades) * 100, 2),
        avg_r=round(mean_r, 3),
        median_r=round(statistics.median(rs), 3),
        total_return_pct=round(total_ret, 2),
        max_drawdown_pct=round(max_dd * 100, 2),
        buyhold_return_pct=round(_buyhold(candles), 2),
        avg_bars_held=round(avg_held, 1),
        longest_win_streak=win_streak,
        longest_loss_streak=loss_streak,
        sharpe_like=round(sharpe, 3),
    )


def _buyhold(candles: list[Candle]) -> float:
    if len(candles) < 2:
        return 0.0
    return (candles[-1].close - candles[0].close) / candles[0].close * 100


def _save(out_dir: str, trades: list[BacktestTrade], stats: BacktestStats,
          source: str) -> None:
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    tag = time.strftime("%Y-%m-%d", time.gmtime())

    # trades CSV
    tpath = base / f"{tag}_trades.csv"
    with tpath.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["open_date", "close_date", "direction", "entry", "stop",
                    "tp1", "exit_price", "exit_reason", "bars_held",
                    "pnl_pct", "r_multiple", "confluence_score"])
        for t in trades:
            w.writerow([
                _date_of(t.open_ts), _date_of(t.close_ts), t.direction,
                f"{t.entry:.2f}", f"{t.stop:.2f}", f"{t.tp1:.2f}",
                f"{t.exit_price:.2f}", t.exit_reason, t.bars_held,
                t.pnl_pct, t.r_multiple, t.confluence_score,
            ])

    # summary MD
    spath = base / f"{tag}_summary.md"
    with spath.open("w") as f:
        f.write(f"# Backtest Summary — BTC/USDT D1 (source: `{source}`)\n\n")
        f.write("| Metric | Value |\n|---|---|\n")
        d = asdict(stats)
        for k, v in d.items():
            f.write(f"| {k} | {v} |\n")
        f.write(f"\nTrades: `{tpath.name}` ({len(trades)} rows).\n")
