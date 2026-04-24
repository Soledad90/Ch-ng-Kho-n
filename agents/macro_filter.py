"""Macro regime filter across multiple assets.

BTC  -> uses real on-chain MVRV from `data/mvrv_btc.csv` (via mvrv_agent).
ETH / SOL -> no public MVRV history without paid data. We approximate with
**Mayer Multiple** (price / 200-day SMA), a well-known proxy for long-term
valuation that is computable from D1 price data alone.

Both return the same `MacroSignal` shape so callers don't care which asset
is in play.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from . import mvrv_agent
from .data_sources import Asset, fetch_ohlc


Direction = Literal["bullish", "bearish", "none"]


@dataclass
class MacroSignal:
    asset: Asset
    kind: str              # "MVRV" | "MayerMultiple"
    value: float           # raw metric value
    regime: str            # Deep Value / Discount / Neutral / Hot / Euphoria
    direction: Direction   # bullish / bearish / none
    size_multiplier: float
    rationale: str


def _classify(metric_kind: str, value: float) -> tuple[str, Direction, float, str]:
    """Bin the metric into one of five regimes. Thresholds are tuned for BTC
    MVRV but also work for Mayer Multiple because both scale the same way
    (1.0 = spot at long-term mean)."""
    if metric_kind == "MVRV":
        # Bitbo MVRV ~ 1.0 is cost basis. Known tops >3.7, bottoms <1.0.
        dv, disc, hot, euph = 0.80, 1.00, 2.40, 3.70
    else:  # MayerMultiple
        # Classic Mayer Multiple thresholds (Trace Mayer 2013).
        dv, disc, hot, euph = 0.70, 1.00, 2.00, 2.40
    if value <= dv:
        return "Deep Value", "bullish", 1.50, f"{metric_kind}={value:.3f} <= {dv}"
    if value <= disc:
        return "Discount", "bullish", 1.15, f"{metric_kind}={value:.3f} <= {disc}"
    if value < hot:
        return "Neutral", "none", 1.00, f"{metric_kind}={value:.3f} in ({disc}, {hot})"
    if value < euph:
        return "Hot", "bearish", 0.60, f"{metric_kind}={value:.3f} in [{hot}, {euph})"
    return "Euphoria", "bearish", 0.25, f"{metric_kind}={value:.3f} >= {euph}"


def _mayer_multiple(asset: Asset, window: int = 200) -> float:
    c, _ = fetch_ohlc("1d", asset)
    if len(c) < window:
        raise RuntimeError(f"Not enough bars for {window}-SMA on {asset}")
    closes = [x.close for x in c[-window:]]
    sma = sum(closes) / window
    return c[-1].close / sma


def run(asset: Asset = "BTC") -> MacroSignal:
    if asset == "BTC":
        mv = mvrv_agent.run()
        # mvrv_agent uses "neutral" as the no-signal label
        dmap = {"bullish": "bullish", "bearish": "bearish", "neutral": "none"}
        return MacroSignal(
            asset="BTC", kind="MVRV", value=mv.mvrv, regime=mv.regime,
            direction=dmap.get(mv.direction, "none"),
            size_multiplier=mv.size_multiplier,
            rationale=f"MVRV={mv.mvrv:.3f}, percentile={mv.percentile:.1f}%, z={mv.z_score:.2f}",
        )
    # ETH / SOL
    mm = _mayer_multiple(asset)
    regime, direction, size_mult, rationale = _classify("MayerMultiple", mm)
    return MacroSignal(asset=asset, kind="MayerMultiple", value=round(mm, 4),
                       regime=regime, direction=direction,
                       size_multiplier=size_mult, rationale=rationale)
