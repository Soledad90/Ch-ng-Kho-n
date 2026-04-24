"""Orchestrator — fuses MVRV and TA into an entry plan.

Decision matrix (MVRV x TA):

                 TA bullish    TA neutral    TA bearish
MVRV bullish     STRONG_BUY    BUY_DCA       WAIT_DIP
MVRV neutral     BUY           HOLD          REDUCE
MVRV bearish     TRIM          TRIM          EXIT

Entry-zone logic:
- STRONG_BUY / BUY: pullback to EMA20 (or VAL) clamped into Fib 0.382-0.618 band.
- BUY_DCA / WAIT_DIP: 3-tranche DCA at VAL, Fib 0.618, nearest support.
- TRIM / EXIT: use current price as exit reference; no entry zone.
- HOLD: neutral - entry zone = current +/- 1 ATR.

Stop = nearest support below entry minus 0.5 ATR.
TP1 = nearest resistance above entry.
TP2 = swing_high (or VAH if higher).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

from .mvrv_agent import MvrvSignal
from .ta_agent import TaSignal


@dataclass
class EntryPlan:
    action: str                         # STRONG_BUY|BUY|BUY_DCA|HOLD|WAIT_DIP|TRIM|REDUCE|EXIT
    confidence: float                   # 0..1
    entry_zone: tuple[float, float]
    tranches: list[tuple[float, float]] # [(price, weight)], sums to 1.0
    stop: float
    tp1: float
    tp2: float
    rr: float                           # reward : risk for TP1
    size_multiplier: float              # from MVRV
    rationale: list[str]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["entry_zone"] = list(self.entry_zone)
        d["tranches"] = [list(t) for t in self.tranches]
        return d


def _nearest(values: list[float], target: float, below: bool = True) -> float | None:
    cand = [v for v in values if (v <= target if below else v >= target)]
    if not cand:
        return None
    return max(cand) if below else min(cand)


def _combine_action(mvrv_dir: str, ta_dir: str) -> str:
    m = {"bullish": 1, "neutral": 0, "bearish": -1}[mvrv_dir]
    t = {"bullish": 1, "neutral": 0, "bearish": -1}[ta_dir]
    if m == 1 and t == 1:
        return "STRONG_BUY"
    if m == 1 and t == 0:
        return "BUY_DCA"
    if m == 1 and t == -1:
        return "WAIT_DIP"
    if m == 0 and t == 1:
        return "BUY"
    if m == 0 and t == 0:
        return "HOLD"
    if m == 0 and t == -1:
        return "REDUCE"
    if m == -1 and t == 1:
        return "TRIM"
    if m == -1 and t == 0:
        return "TRIM"
    return "EXIT"


def plan(mvrv: MvrvSignal, ta: TaSignal) -> EntryPlan:
    action = _combine_action(mvrv.direction, ta.direction)
    rationale: list[str] = [
        f"MVRV={mvrv.mvrv:.2f} ({mvrv.regime}, pctile {mvrv.percentile}%, z={mvrv.z_score})",
        f"TA trend={ta.trend}, momentum={ta.momentum}, cloud={ta.cloud_state}",
    ]

    close = ta.close
    atr = ta.atr14 or (close * 0.02)
    e20 = ta.ema20 or close
    fib382 = ta.fib["0.382"]
    fib618 = ta.fib["0.618"]
    vah = ta.vp_vah or ta.swing_high
    val = ta.vp_val or ta.swing_low
    poc = ta.vp_poc or close

    support_below = _nearest(ta.supports, close, below=True) or (close - 2 * atr)
    resistance_above = _nearest(ta.resistances, close, below=False) or (close + 2 * atr)

    if action in ("STRONG_BUY", "BUY"):
        # Want to buy a pullback -- aim just below EMA20, capped inside 0.382-0.618 fib
        lo = max(min(e20 - 0.5 * atr, fib618), val)
        hi = min(max(e20, fib382), poc + 0.5 * atr)
        if lo > hi:
            lo, hi = hi, lo
        entry = (lo, hi)
        tranches = [((lo + hi) / 2, 0.4), (lo, 0.35), (max(fib618, support_below), 0.25)]
    elif action in ("BUY_DCA", "WAIT_DIP"):
        # 3-tranche DCA from neutral zone deep to fib/support
        tranches = [
            (poc, 0.3),
            (fib618, 0.35),
            (support_below, 0.35),
        ]
        entry = (min(t[0] for t in tranches), max(t[0] for t in tranches))
    elif action == "HOLD":
        entry = (close - atr, close + atr)
        tranches = [(close, 1.0)]
    elif action in ("REDUCE", "TRIM"):
        entry = (close, close)  # no new entry
        tranches = []
    else:  # EXIT
        entry = (close, close)
        tranches = []

    stop_ref = min(support_below, min((t[0] for t in tranches), default=support_below))
    stop = stop_ref - 0.5 * atr
    tp1 = resistance_above
    tp2 = max(vah, ta.swing_high, tp1 + 2 * atr)

    # risk/reward for an average entry
    ref_entry = sum(p * w for p, w in tranches) if tranches else close
    risk = max(ref_entry - stop, 1e-6)
    reward = max(tp1 - ref_entry, 0.0)
    rr = round(reward / risk, 2) if risk else 0.0

    # confidence: agreement of MVRV and TA + RR
    base = 0.5
    if mvrv.direction == ta.direction and mvrv.direction != "neutral":
        base += 0.25
    if mvrv.direction != "neutral" and ta.direction != "neutral" and \
            mvrv.direction != ta.direction:
        base -= 0.15
    base += min(max(rr - 1.0, 0.0), 1.0) * 0.15
    confidence = round(min(max(base, 0.0), 1.0), 2)

    rationale.append(f"Action={action}, RR(TP1)={rr}, size x{mvrv.size_multiplier}")

    return EntryPlan(
        action=action,
        confidence=confidence,
        entry_zone=entry,
        tranches=tranches,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        rr=rr,
        size_multiplier=mvrv.size_multiplier,
        rationale=rationale,
    )
