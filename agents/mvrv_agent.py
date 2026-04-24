"""MVRV Agent — reads BTC MVRV series and emits valuation regime.

Reuses `data/mvrv_btc.csv` produced from charts.bitbo.io/mvrv.
Also computes a rolling MVRV Z-Score (mean-reverting bands) to detect
divergence vs. price even within the same regime.
"""
from __future__ import annotations

import csv
import math
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "mvrv_btc.csv"

# Regime boundaries — keep in sync with scripts/compute_mvrv_filter.py
REGIMES = [
    ("Deep Value",  1.50, "Aggressive buy -- macro bottom risk zone"),
    ("Discount",    1.15, "Above-baseline buy -- mild optimism, still cheap"),
    ("Neutral",     1.00, "Baseline allocation -- no macro edge"),
    ("Hot",         0.60, "Reduce size, trim winners -- overvalued"),
    ("Euphoria",    0.25, "Minimal new exposure, raise cash -- top risk"),
]


@dataclass
class MvrvSignal:
    as_of: str
    mvrv: float
    realized_price: float
    btc_price: float
    percentile: float      # vs. full history, 0..100
    z_score: float         # rolling 365d z-score of MVRV
    regime: str
    size_multiplier: float
    signal: str
    direction: str         # "bullish" | "bearish" | "neutral"

    def to_dict(self) -> dict:
        return asdict(self)


def _quantile(sorted_values: list[float], p: float) -> float:
    i = p * (len(sorted_values) - 1)
    lo = int(i)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = i - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def _classify(mvrv: float, p50: float, p75: float, p90: float) -> tuple[str, float, str]:
    if mvrv < 1.00:
        return REGIMES[0][0], REGIMES[0][1], REGIMES[0][2]
    if mvrv < p50:
        return REGIMES[1][0], REGIMES[1][1], REGIMES[1][2]
    if mvrv < p75:
        return REGIMES[2][0], REGIMES[2][1], REGIMES[2][2]
    if mvrv < p90:
        return REGIMES[3][0], REGIMES[3][1], REGIMES[3][2]
    return REGIMES[4][0], REGIMES[4][1], REGIMES[4][2]


def _direction(regime: str, z: float) -> str:
    if regime in ("Deep Value", "Discount") and z < 0:
        return "bullish"
    if regime in ("Hot", "Euphoria") and z > 0:
        return "bearish"
    if z > 1:
        return "bearish"
    if z < -1:
        return "bullish"
    return "neutral"


def run(data_path: Path = DATA) -> MvrvSignal:
    rows = list(csv.DictReader(data_path.open()))
    mv_series = [float(r["mvrv"]) for r in rows]
    latest = rows[-1]
    mv = float(latest["mvrv"])

    s = sorted(mv_series)
    p50 = _quantile(s, 0.50)
    p75 = _quantile(s, 0.75)
    p90 = _quantile(s, 0.90)
    below = sum(1 for x in mv_series if x < mv)
    percentile = round(below / len(mv_series) * 100, 1)

    tail = mv_series[-365:] if len(mv_series) >= 365 else mv_series
    mu = statistics.mean(tail)
    sd = statistics.stdev(tail) if len(tail) > 1 else 0.0
    z = round((mv - mu) / sd, 2) if sd else 0.0

    regime, mult, signal = _classify(mv, p50, p75, p90)

    return MvrvSignal(
        as_of=latest["date"],
        mvrv=mv,
        realized_price=float(latest["realized_price_usd"]),
        btc_price=float(latest["btc_price_usd"]),
        percentile=percentile,
        z_score=z,
        regime=regime,
        size_multiplier=mult,
        signal=signal,
        direction=_direction(regime, z),
    )


if __name__ == "__main__":
    import json
    sig = run()
    print(json.dumps(sig.to_dict(), indent=2))
