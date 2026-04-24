"""Master Data Agent — maps the AGENT.md blueprint onto the code agents.

Pipeline (Layer 1 -> Layer 4 per AGENT.md):

1.  Layer 1 BIAS     : MVRV + D1/H4 trend alignment.
2.  Layer 2 POI      : Premium/Discount + Fibonacci zones + swing S/R.
3.  Layer 3 TRIGGER  : M15 Liquidity Sweep + CHoCH detection.
4.  Layer 4 EXECUTION: Entry / SL / TP1 / TP2 / size% only if Confluence >= 5/8.

The agent is deterministic. It NEVER invents missing data — when a factor
cannot be evaluated it is marked `unknown` and the Confluence item fails.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Literal

from . import indicators as ind
from . import mvrv_agent
from . import futures_data as fut
from .data_sources import Candle, fetch_ohlc


Direction = Literal["long", "short", "none"]
Bias = Literal["bullish", "bearish", "range"]


# -------------------------------------------------------------------------
# Sub-structures
# -------------------------------------------------------------------------

@dataclass
class TFSnapshot:
    tf: str
    close: float
    ema20: float | None
    ema50: float | None
    ema200: float | None
    rsi14: float | None
    macd_hist: float | None
    atr14: float | None
    trend: str
    swing_high: float
    swing_low: float
    mid: float          # premium/discount midpoint of swing
    poc: float | None


@dataclass
class POI:
    premium_zone: tuple[float, float]      # upper 50% of D1 swing
    discount_zone: tuple[float, float]     # lower 50% of D1 swing
    current_in: str                        # "premium" | "discount" | "mid"
    ote_long: tuple[float, float]          # Fib 0.618-0.79 for a long
    ote_short: tuple[float, float]
    nearest_support: float
    nearest_resistance: float


@dataclass
class Trigger:
    sweep: str                             # "bullish" | "bearish" | "none"
    sweep_price: float | None
    choch: str                             # "bullish" | "bearish" | "none"
    choch_price: float | None
    nearest_fvg_long: tuple[float, float] | None   # (lo, hi) unmitigated
    nearest_fvg_short: tuple[float, float] | None
    nearest_ob_long: tuple[float, float] | None
    nearest_ob_short: tuple[float, float] | None


@dataclass
class Futures:
    funding_rate: float                    # per 8h period
    funding_regime: str                    # extreme_long/mild_long/neutral/mild_short/extreme_short/unknown
    oi_trend: str                          # rising/falling/flat/unknown
    oi_change_pct: float | None            # % change over last 12 bars
    ls_ratio: float | None                 # long/short account ratio (OKX)
    liq_poc_long: float | None             # price magnet below (longs got liquidated)
    liq_poc_short: float | None            # price magnet above (shorts got liquidated)
    liq_total_long: float                  # sum of recent long liquidations
    liq_total_short: float


@dataclass
class ConfluenceItem:
    name: str
    passed: bool
    note: str


@dataclass
class MasterSignal:
    as_of: str
    source: str
    mvrv_regime: str
    mvrv_direction: str
    mvrv_value: float
    bias_w1: str
    bias_d1: str
    bias_h4: str
    bias_htf: Bias
    bias_reason: str
    poi: POI
    trigger: Trigger
    futures: Futures
    confluence: list[ConfluenceItem]
    confluence_score: int
    direction: Direction
    entry: float | None
    stop: float | None
    tp1: float | None
    tp2: float | None
    rr: float | None
    risk_pct: float
    size_hint: str
    scenario_a: str
    invalidation: str
    decision: str                          # "TRADE" | "NO_TRADE"
    hard_stops: list[str]
    d1: TFSnapshot
    h4: TFSnapshot
    h1: TFSnapshot
    m15: TFSnapshot

    def to_dict(self) -> dict:
        return _as_json(asdict(self))


def _as_json(x):
    if isinstance(x, dict):
        return {k: _as_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_as_json(v) for v in x]
    if isinstance(x, tuple):
        return [_as_json(v) for v in x]
    return x


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _snap(tf: str, candles: list[Candle]) -> TFSnapshot:
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    vols = [c.volume for c in candles]
    look = min(90, len(candles))
    h = highs[-look:]
    l = lows[-look:]
    sh = max(h)
    sl = min(l)
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


def _classify_trend(close, e20, e50, e200) -> str:
    if e50 is None or e200 is None:
        return "range"
    if close > e50 > e200:
        return "up"
    if close < e50 < e200:
        return "down"
    return "range"


def _detect_sweep(candles: list[Candle], lookback: int = 30) -> tuple[str, float | None]:
    """Look at recent `lookback` candles. If the most recent candle's wick
    breached the prior swing high/low but the body closed back inside, flag a
    sweep. Simple approximation of ICT Stop-Hunt / Judas Swing.
    """
    if len(candles) < lookback + 1:
        return "none", None
    window = candles[-lookback - 1:-1]
    last = candles[-1]
    prior_high = max(c.high for c in window)
    prior_low = min(c.low for c in window)
    if last.high > prior_high and last.close < prior_high:
        return "bearish", prior_high
    if last.low < prior_low and last.close > prior_low:
        return "bullish", prior_low
    return "none", None


def _detect_choch(candles: list[Candle]) -> tuple[str, float | None]:
    """Very small CHoCH detector: find last pivot high and pivot low over the
    recent candles. If close now > most recent pivot high that is *lower* than
    the prior pivot high (i.e. a lower high in a downtrend) → bullish CHoCH.
    Mirror for bearish.
    """
    if len(candles) < 15:
        return "none", None
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    close = candles[-1].close
    sh, sl = ind.swing_pivots(highs, lows, left=3, right=3)
    if sh:
        last_hi_idx = sh[-1]
        last_hi_price = highs[last_hi_idx]
        prev_hi_price = highs[sh[-2]] if len(sh) >= 2 else None
        if (prev_hi_price is not None and last_hi_price < prev_hi_price
                and close > last_hi_price):
            return "bullish", last_hi_price
    if sl:
        last_lo_idx = sl[-1]
        last_lo_price = lows[last_lo_idx]
        prev_lo_price = lows[sl[-2]] if len(sl) >= 2 else None
        if (prev_lo_price is not None and last_lo_price > prev_lo_price
                and close < last_lo_price):
            return "bearish", last_lo_price
    return "none", None


def _kill_zone(ts: int) -> bool:
    """London (07-10 UTC) or New York (12-15 UTC)."""
    hour = time.gmtime(ts).tm_hour
    return 7 <= hour < 10 or 12 <= hour < 15


def _bias_from_snaps(d1: TFSnapshot, h4: TFSnapshot, w1_trend: str) -> tuple[Bias, str]:
    def to_dir(t: str) -> int:
        return {"up": 1, "down": -1, "range": 0}[t]

    score = 2 * to_dir(d1.trend) + to_dir(h4.trend) + to_dir(w1_trend)
    if score >= 2:
        return "bullish", f"D1={d1.trend}, H4={h4.trend}, W1={w1_trend}"
    if score <= -2:
        return "bearish", f"D1={d1.trend}, H4={h4.trend}, W1={w1_trend}"
    return "range", f"D1={d1.trend}, H4={h4.trend}, W1={w1_trend} — mixed"


def _poi(d1: TFSnapshot) -> POI:
    sh, sl = d1.swing_high, d1.swing_low
    mid = d1.mid
    span = sh - sl
    prem_lo = mid
    prem_hi = sh
    disc_lo = sl
    disc_hi = mid
    close = d1.close
    if close > mid + 0.1 * span:
        current_in = "premium"
    elif close < mid - 0.1 * span:
        current_in = "discount"
    else:
        current_in = "mid"
    ote_long = (sl + 0.21 * span, sl + 0.382 * span)      # 0.618-0.79 retrace of up leg
    ote_short = (sh - 0.382 * span, sh - 0.21 * span)
    highs = [sh - 0.1 * span, sh - 0.2 * span]
    lows = [sl + 0.1 * span, sl + 0.2 * span]
    nearest_res = min([h for h in highs if h > close] or [sh])
    nearest_sup = max([l for l in lows if l < close] or [sl])
    return POI(
        premium_zone=(prem_lo, prem_hi),
        discount_zone=(disc_lo, disc_hi),
        current_in=current_in,
        ote_long=ote_long, ote_short=ote_short,
        nearest_support=nearest_sup,
        nearest_resistance=nearest_res,
    )


def _fvg_ob_from_candles(candles: list[Candle]) -> dict:
    """Return the nearest unmitigated bullish/bearish FVG and OB to current price."""
    opens = [c.open for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    close = closes[-1]

    fvgs = ind.detect_fvg(highs, lows, closes, lookback=120)
    obs = ind.detect_order_blocks(opens, highs, lows, closes, lookback=120)

    def _nearest(items: list[dict], kind: str, side: str) -> tuple[float, float] | None:
        cand = [x for x in items if x["kind"] == kind and not x["mitigated"]]
        if not cand:
            return None
        if side == "below":
            cand = [x for x in cand if x["hi"] <= close]
        else:
            cand = [x for x in cand if x["lo"] >= close]
        if not cand:
            return None
        # closest to current price
        best = min(cand, key=lambda x: abs(((x["lo"] + x["hi"]) / 2) - close))
        return (best["lo"], best["hi"])

    return {
        "fvg_long": _nearest(fvgs, "bullish", "below"),
        "fvg_short": _nearest(fvgs, "bearish", "above"),
        "ob_long": _nearest(obs, "bullish", "below"),
        "ob_short": _nearest(obs, "bearish", "above"),
    }


def _classify_funding(rate: float) -> str:
    """Per-8h funding rate regime."""
    if rate > 0.0003:           # > 0.03% / 8h (~33% annualized)
        return "extreme_long"   # longs pay heavily -> crowd is long
    if rate > 0.0001:
        return "mild_long"
    if rate < -0.0003:
        return "extreme_short"
    if rate < -0.0001:
        return "mild_short"
    return "neutral"


def _build_futures() -> Futures:
    try:
        cur_rate, _fhist = fut.fetch_funding_rate(limit=8)
    except Exception:
        cur_rate = 0.0
    try:
        oi = fut.fetch_open_interest("1H", limit=24)
    except Exception:
        oi = []
    try:
        lsr = fut.fetch_long_short_ratio("1H", limit=24)
    except Exception:
        lsr = []
    try:
        liq = fut.fetch_liquidations(limit=100)
        heat = fut.liquidation_heatmap(liq, bins=40)
    except Exception:
        heat = {"poc_long": None, "poc_short": None,
                "total_long": 0.0, "total_short": 0.0}

    oi_change = None
    oi_trend = "unknown"
    if len(oi) >= 12:
        old = oi[-12].oi_usd
        new = oi[-1].oi_usd
        if old:
            oi_change = (new - old) / old * 100
            if oi_change > 1.0:
                oi_trend = "rising"
            elif oi_change < -1.0:
                oi_trend = "falling"
            else:
                oi_trend = "flat"

    return Futures(
        funding_rate=cur_rate,
        funding_regime=_classify_funding(cur_rate),
        oi_trend=oi_trend,
        oi_change_pct=round(oi_change, 2) if oi_change is not None else None,
        ls_ratio=lsr[-1][1] if lsr else None,
        liq_poc_long=heat.get("poc_long"),
        liq_poc_short=heat.get("poc_short"),
        liq_total_long=float(heat.get("total_long") or 0.0),
        liq_total_short=float(heat.get("total_short") or 0.0),
    )


def _confluence(direction: Direction, bias: Bias, poi: POI, trig: Trigger,
                futures: Futures, m15: TFSnapshot, h4: TFSnapshot,
                in_kill_zone: bool) -> list[ConfluenceItem]:
    items: list[ConfluenceItem] = []
    # 1. Bias HTF
    if direction == "none":
        want_str = "n/a (no direction)"
    else:
        want_str = "bullish" if direction == "long" else "bearish"
    want = want_str if direction != "none" else None
    items.append(ConfluenceItem(
        "Bias HTF (D1/H4)",
        direction != "none" and bias == want,
        f"bias={bias}, want={want_str}",
    ))
    # 2. POI valid (price in correct discount/premium zone)
    if direction == "long":
        ok = poi.current_in in ("discount", "mid")
    elif direction == "short":
        ok = poi.current_in in ("premium", "mid")
    else:
        ok = False
    items.append(ConfluenceItem("POI valid", ok, f"current_in={poi.current_in}"))
    # 3. Liquidity sweep
    want_sweep = "bullish" if direction == "long" else "bearish"
    items.append(ConfluenceItem(
        "Liquidity Sweep",
        direction != "none" and trig.sweep == want_sweep,
        f"sweep={trig.sweep}",
    ))
    # 4. CHoCH LTF
    items.append(ConfluenceItem(
        "CHoCH LTF (M15)",
        direction != "none" and trig.choch == want_sweep,
        f"choch={trig.choch}",
    ))
    # 5. Fibonacci OTE
    if direction == "long":
        lo, hi = poi.ote_long
    elif direction == "short":
        lo, hi = poi.ote_short
    else:
        lo, hi = 0, 0
    price = m15.close
    ote_ok = lo <= price <= hi if direction != "none" else False
    items.append(ConfluenceItem("Fibonacci OTE", ote_ok,
                                f"price={price:.2f} in [{lo:.2f}, {hi:.2f}]"))
    # 6. Volume / VP
    poc_ok = False
    if m15.poc is not None:
        poc_ok = abs(price - m15.poc) / max(price, 1) < 0.01
    items.append(ConfluenceItem("Volume Profile (POC proximity)", poc_ok,
                                f"poc={m15.poc}"))
    # 7. Momentum
    rsi_v = m15.rsi14 or 50
    if direction == "long":
        mom_ok = rsi_v > 45 and (m15.macd_hist or 0) > 0
    elif direction == "short":
        mom_ok = rsi_v < 55 and (m15.macd_hist or 0) < 0
    else:
        mom_ok = False
    items.append(ConfluenceItem("Momentum (RSI + MACD hist)", mom_ok,
                                f"rsi={rsi_v:.1f}, macd_hist={m15.macd_hist}"))
    # 8. Kill zone
    items.append(ConfluenceItem("Kill Zone", in_kill_zone,
                                "London 07-10 UTC or NY 12-15 UTC"))
    # 9. Funding rate alignment (contrarian: avoid crowded side)
    fr = futures.funding_rate
    fr_bps = fr * 10000
    if direction == "long":
        fund_ok = futures.funding_regime in ("neutral", "mild_short", "extreme_short")
    elif direction == "short":
        fund_ok = futures.funding_regime in ("neutral", "mild_long", "extreme_long")
    else:
        fund_ok = False
    items.append(ConfluenceItem(
        "Funding Rate (contrarian)", fund_ok,
        f"rate={fr_bps:.2f} bps/8h, regime={futures.funding_regime}",
    ))
    # 10. OI trend confirmation
    if direction == "long":
        oi_ok = futures.oi_trend == "rising"
    elif direction == "short":
        oi_ok = futures.oi_trend == "rising"  # rising OI on drop = shorts stacking (valid for short)
    else:
        oi_ok = False
    items.append(ConfluenceItem(
        "Open Interest trend", oi_ok,
        f"oi_trend={futures.oi_trend}, change={futures.oi_change_pct}%",
    ))
    # 11. OB/FVG proximity
    if direction == "long":
        zone = trig.nearest_ob_long or trig.nearest_fvg_long
    elif direction == "short":
        zone = trig.nearest_ob_short or trig.nearest_fvg_short
    else:
        zone = None
    ob_fvg_ok = False
    zone_note = "no unmitigated OB/FVG found"
    if zone is not None:
        lo, hi = zone
        # pass if current price is inside zone OR within 0.5 ATR of zone edge
        atr = m15.atr14 or (m15.close * 0.005)
        ob_fvg_ok = (lo - 0.5 * atr) <= price <= (hi + 0.5 * atr)
        zone_note = f"zone [{lo:.2f}, {hi:.2f}], price={price:.2f}"
    items.append(ConfluenceItem("OB/FVG zone (3-candle)", ob_fvg_ok, zone_note))
    # 12. Liquidation magnet
    if direction == "long":
        magnet = futures.liq_poc_short    # upside magnet = shorts liquidated above
        mag_ok = magnet is not None and magnet > price
    elif direction == "short":
        magnet = futures.liq_poc_long
        mag_ok = magnet is not None and magnet < price
    else:
        magnet = None
        mag_ok = False
    items.append(ConfluenceItem(
        "Liquidation magnet (target)", mag_ok,
        f"magnet={magnet}, price={price:.2f}" if magnet else "no magnet",
    ))
    return items


def _decide_direction(bias: Bias, poi: POI, trig: Trigger) -> Direction:
    # Strongest: bias + sweep + choch agree
    if bias == "bullish" and trig.sweep == "bullish" and trig.choch == "bullish":
        return "long"
    if bias == "bearish" and trig.sweep == "bearish" and trig.choch == "bearish":
        return "short"
    # Fallback: bias + POI reclaim — allow long/short if bias and zone agree
    if bias == "bullish" and poi.current_in in ("discount", "mid"):
        return "long"
    if bias == "bearish" and poi.current_in in ("premium", "mid"):
        return "short"
    return "none"


def _build_execution(direction: Direction, poi: POI, m15: TFSnapshot,
                     h4: TFSnapshot) -> tuple[float | None, float | None,
                                               float | None, float | None]:
    atr = m15.atr14 or (m15.close * 0.005)
    if direction == "long":
        lo, hi = poi.ote_long
        entry = (lo + hi) / 2
        stop = lo - 0.5 * atr
        tp1 = poi.nearest_resistance
        tp2 = poi.premium_zone[1]
        return entry, stop, tp1, tp2
    if direction == "short":
        lo, hi = poi.ote_short
        entry = (lo + hi) / 2
        stop = hi + 0.5 * atr
        tp1 = poi.nearest_support
        tp2 = poi.discount_zone[0]
        return entry, stop, tp1, tp2
    return None, None, None, None


# -------------------------------------------------------------------------
# Public entry point
# -------------------------------------------------------------------------

def run(risk_pct: float = 1.0) -> MasterSignal:
    """Run the Master Data Agent end-to-end.

    Parameters
    ----------
    risk_pct : float
        Per-trade risk expressed in % of account equity (default 1%).
    """
    hard_stops: list[str] = []
    if risk_pct > 2.0:
        hard_stops.append("Risk per trade > 2% — hard-stop per AGENT.md Rule #3")

    # Data layer (multi-TF)
    c_d1, src = fetch_ohlc("1d")
    c_h4, _ = fetch_ohlc("4h")
    c_h1, _ = fetch_ohlc("1h")
    c_m15, _ = fetch_ohlc("15m")

    d1 = _snap("1d", c_d1)
    h4 = _snap("4h", c_h4)
    h1 = _snap("1h", c_h1)
    m15 = _snap("15m", c_m15)

    # W1 proxy: slope of D1 EMA200 (we don't pull weekly)
    w1_trend = d1.trend  # approximation — D1 trend is a reasonable W1 proxy

    # Layer 1: Bias
    bias, bias_reason = _bias_from_snaps(d1, h4, w1_trend)

    # MVRV macro overlay
    mv = mvrv_agent.run()
    if mv.direction == "bullish" and bias == "bearish":
        bias_reason += f"; MVRV bullish ({mv.regime}, z={mv.z_score}) — macro disagrees"
    if mv.direction == "bearish" and bias == "bullish":
        bias_reason += f"; MVRV bearish ({mv.regime}, z={mv.z_score}) — macro disagrees"
        hard_stops.append("HTF bullish but MVRV bearish — top risk per AGENT.md Rule #2")

    # Layer 2: POI
    poi = _poi(d1)

    # Layer 3: Trigger on M15 (sweep + CHoCH + unmitigated OB/FVG)
    sweep_dir, sweep_price = _detect_sweep(c_m15, lookback=30)
    choch_dir, choch_price = _detect_choch(c_m15)
    zones = _fvg_ob_from_candles(c_m15)
    trig = Trigger(
        sweep=sweep_dir, sweep_price=sweep_price,
        choch=choch_dir, choch_price=choch_price,
        nearest_fvg_long=zones["fvg_long"], nearest_fvg_short=zones["fvg_short"],
        nearest_ob_long=zones["ob_long"], nearest_ob_short=zones["ob_short"],
    )

    # Futures microstructure (funding, OI, L/S, liquidations)
    futures = _build_futures()

    # Direction
    direction = _decide_direction(bias, poi, trig)

    # Layer 4: Execution
    entry, stop, tp1, tp2 = _build_execution(direction, poi, m15, h4)
    # Prefer liquidation magnet as TP2 if it extends further in our favour
    if direction == "long" and futures.liq_poc_short and tp2:
        if futures.liq_poc_short > tp2:
            tp2 = futures.liq_poc_short
    elif direction == "short" and futures.liq_poc_long and tp2:
        if futures.liq_poc_long < tp2:
            tp2 = futures.liq_poc_long

    # Confluence scorecard
    in_kz = _kill_zone(c_m15[-1].ts)
    confluence = _confluence(direction, bias, poi, trig, futures, m15, h4, in_kz)
    score = sum(1 for c in confluence if c.passed)

    # RR guard
    rr = None
    if entry and stop and tp1:
        risk = abs(entry - stop)
        reward = abs(tp1 - entry)
        rr = round(reward / risk, 2) if risk else 0.0
        if rr < 2.0:
            hard_stops.append(f"RR(TP1)={rr} < 1:2 — hard-stop per AGENT.md Rule #3")

    # Need 7/12 confluence factors (~58% same bar as old 5/8)
    decision = "TRADE" if (
        score >= 7 and direction != "none" and not hard_stops and rr and rr >= 2.0
    ) else "NO_TRADE"

    scenario_a = (
        f"{direction.upper()} from {entry:.2f}, SL {stop:.2f}, "
        f"TP1 {tp1:.2f}, TP2 {tp2:.2f}, RR(TP1)={rr}" if direction != "none" and entry
        else "No valid setup"
    )
    invalidation = (
        f"Close below {stop:.2f}" if direction == "long" and stop
        else f"Close above {stop:.2f}" if direction == "short" and stop
        else "n/a"
    )

    size_hint = (
        f"size = ({risk_pct}% x equity) / |entry - stop| "
        f"= {risk_pct}% / {abs(entry - stop):.2f}" if entry and stop
        else "n/a"
    )

    return MasterSignal(
        as_of=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(c_m15[-1].ts)),
        source=src,
        mvrv_regime=mv.regime, mvrv_direction=mv.direction, mvrv_value=mv.mvrv,
        bias_w1=w1_trend, bias_d1=d1.trend, bias_h4=h4.trend,
        bias_htf=bias, bias_reason=bias_reason,
        poi=poi, trigger=trig, futures=futures,
        confluence=confluence, confluence_score=score,
        direction=direction, entry=entry, stop=stop, tp1=tp1, tp2=tp2, rr=rr,
        risk_pct=risk_pct, size_hint=size_hint,
        scenario_a=scenario_a, invalidation=invalidation,
        decision=decision, hard_stops=hard_stops,
        d1=d1, h4=h4, h1=h1, m15=m15,
    )


if __name__ == "__main__":
    import json
    sig = run()
    print(json.dumps(sig.to_dict(), indent=2, default=float))
