#!/usr/bin/env python3
"""
MVRV Macro Filter for the Ch-ng-Kho-n capital allocation system.

Reads `data/mvrv_btc.csv` (extracted from charts.bitbo.io/mvrv/) and derives
the current BTC MVRV regime, a size multiplier, and an adjusted capital
allocation plan for `CII_Analysis.csv`.

Regimes are defined on lifetime historical quantiles of the MVRV ratio:

    MVRV < 1.00                          -> Deep Value        (multiplier 1.50)
    1.00 <= MVRV < P50  (median 1.715)   -> Discount          (multiplier 1.15)
    P50  <= MVRV < P75  (1.29..2.19)     -> Neutral           (multiplier 1.00)
    P75  <= MVRV < P90  (2.19..2.79)     -> Hot               (multiplier 0.60)
    MVRV >= P90         (>= 2.79)        -> Euphoria          (multiplier 0.25)

Rationale: MVRV measures market cap vs. realized cap for BTC. Extremes
have historically marked macro bottoms (MVRV < 1) and tops (MVRV > 3.7).
We use it as a risk-on/risk-off gate for *all* positions in the system --
including VN equities like CII -- because crypto cycles lead global
risk-asset sentiment.

Usage:
    python scripts/compute_mvrv_filter.py
    python scripts/compute_mvrv_filter.py --apply   # rewrite CII_Analysis.csv
"""
from __future__ import annotations

import argparse
import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data" / "mvrv_btc.csv"
ANALYSIS = REPO / "CII_Analysis.csv"

REGIMES = [
    # (label, upper_bound_exclusive, size_multiplier, signal)
    ("Deep Value",  1.00, 1.50, "Aggressive buy -- macro bottom risk zone"),
    ("Discount",    None, 1.15, "Above-baseline buy -- mild optimism, still cheap"),
    ("Neutral",     None, 1.00, "Baseline allocation -- no macro edge"),
    ("Hot",         None, 0.60, "Reduce size, trim winners -- overvalued"),
    ("Euphoria",    None, 0.25, "Minimal new exposure, raise cash -- top risk"),
]


@dataclass
class MvrvStats:
    latest_date: str
    latest_mvrv: float
    latest_btc: float
    latest_realized: float
    p25: float
    p50: float
    p75: float
    p90: float
    mean: float
    stdev: float
    n: int


def quantile(sorted_values: list[float], p: float) -> float:
    i = p * (len(sorted_values) - 1)
    lo = int(i)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = i - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def load_stats(path: Path = DATA) -> MvrvStats:
    with path.open() as f:
        rows = list(csv.DictReader(f))
    mv = [float(r["mvrv"]) for r in rows]
    s = sorted(mv)
    latest = rows[-1]
    return MvrvStats(
        latest_date=latest["date"],
        latest_mvrv=float(latest["mvrv"]),
        latest_btc=float(latest["btc_price_usd"]),
        latest_realized=float(latest["realized_price_usd"]),
        p25=round(quantile(s, 0.25), 3),
        p50=round(quantile(s, 0.50), 3),
        p75=round(quantile(s, 0.75), 3),
        p90=round(quantile(s, 0.90), 3),
        mean=round(statistics.mean(mv), 3),
        stdev=round(statistics.stdev(mv), 3),
        n=len(mv),
    )


def classify(mvrv: float, st: MvrvStats) -> tuple[str, float, str]:
    if mvrv < 1.00:
        label, mult, signal = REGIMES[0][0], REGIMES[0][2], REGIMES[0][3]
    elif mvrv < st.p50:
        label, mult, signal = REGIMES[1][0], REGIMES[1][2], REGIMES[1][3]
    elif mvrv < st.p75:
        label, mult, signal = REGIMES[2][0], REGIMES[2][2], REGIMES[2][3]
    elif mvrv < st.p90:
        label, mult, signal = REGIMES[3][0], REGIMES[3][2], REGIMES[3][3]
    else:
        label, mult, signal = REGIMES[4][0], REGIMES[4][2], REGIMES[4][3]
    return label, mult, signal


def percentile_of(mvrv: float, path: Path = DATA) -> float:
    with path.open() as f:
        rows = list(csv.DictReader(f))
    mv = [float(r["mvrv"]) for r in rows]
    below = sum(1 for x in mv if x < mvrv)
    return round(below / len(mv) * 100, 1)


# ----- VND capital allocation helpers --------------------------------------

_BASELINE_PLAN_VND = [
    ("Month 04", 3_000_000),
    ("Month 05", 3_500_000),
    ("Month 06", 3_500_000),
]


def _fmt_vnd(x: int) -> str:
    return f"{x:,} VND"


def adjust_plan(multiplier: float) -> tuple[str, int]:
    parts = []
    total = 0
    for month, amount in _BASELINE_PLAN_VND:
        adj = int(round(amount * multiplier / 1000.0) * 1000)  # round to 1k VND
        parts.append(f"{month}: {_fmt_vnd(adj)}")
        total += adj
    return "; ".join(parts), total


# ----- CSV rewrite ---------------------------------------------------------

MVRV_ROW_KEYS = [
    "MVRV Regime",
    "MVRV Value",
    "MVRV Percentile",
    "MVRV Size Multiplier",
    "MVRV-Adjusted Capital Allocation",
    "MVRV-Adjusted Total (90d)",
    "MVRV Macro Signal",
    "MVRV Data As Of",
]


def apply_to_analysis(path: Path = ANALYSIS) -> None:
    st = load_stats()
    regime, mult, signal = classify(st.latest_mvrv, st)
    pct = percentile_of(st.latest_mvrv)
    plan, total = adjust_plan(mult)

    with path.open() as f:
        rows = list(csv.reader(f))
    # drop any previous MVRV-* rows so this is idempotent
    rows = [r for r in rows if not (r and r[0] in MVRV_ROW_KEYS)]

    additions = [
        ["MVRV Regime", regime],
        ["MVRV Value", f"{st.latest_mvrv:.2f}"],
        ["MVRV Percentile", f"{pct:.1f}%"],
        ["MVRV Size Multiplier", f"{mult:.2f}x"],
        ["MVRV-Adjusted Capital Allocation", plan],
        ["MVRV-Adjusted Total (90d)", _fmt_vnd(total)],
        ["MVRV Macro Signal", signal],
        ["MVRV Data As Of", st.latest_date],
    ]
    rows.extend(additions)

    with path.open("w", newline="") as f:
        csv.writer(f).writerows(rows)


# ----- CLI -----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Rewrite CII_Analysis.csv with current MVRV rows.")
    args = ap.parse_args()

    st = load_stats()
    regime, mult, signal = classify(st.latest_mvrv, st)
    pct = percentile_of(st.latest_mvrv)
    plan, total = adjust_plan(mult)

    print(f"Data: n={st.n} rows, as of {st.latest_date}")
    print(f"  MVRV={st.latest_mvrv:.2f}  percentile={pct:.1f}%")
    print(f"  BTC=${st.latest_btc:,.2f}  Realized=${st.latest_realized:,.2f}")
    print(f"  P25={st.p25}  P50={st.p50}  P75={st.p75}  P90={st.p90}")
    print()
    print(f"Regime: {regime}  (multiplier {mult:.2f}x)")
    print(f"Signal: {signal}")
    print(f"Adjusted plan: {plan}")
    print(f"Adjusted total: {_fmt_vnd(total)}")

    if args.apply:
        apply_to_analysis()
        print(f"\nWrote MVRV rows to {ANALYSIS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
