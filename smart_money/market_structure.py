"""
Step 1 — Market Structure Analysis
Identifies trend direction, BOS (Break of Structure) and CHoCH (Change of Character).
"""

from typing import List, Tuple

from .models import Candle, MarketData, StructureResult

# Minimum number of candles between swing points
_SWING_LOOKBACK = 3


def _find_swing_highs_lows(candles: List[Candle]) -> Tuple[List[float], List[float]]:
    """Return lists of swing-high prices and swing-low prices.

    Adjacent candles that share the same local extreme (e.g., the last impulse
    candle and the first pullback candle both showing the same high) are
    deduplicated so that only one entry per swing level is returned.
    """
    high_indices: List[int] = []
    low_indices: List[int] = []
    n = len(candles)

    for i in range(_SWING_LOOKBACK, n - _SWING_LOOKBACK):
        window_h = [c.high for c in candles[i - _SWING_LOOKBACK: i + _SWING_LOOKBACK + 1]]
        window_l = [c.low for c in candles[i - _SWING_LOOKBACK: i + _SWING_LOOKBACK + 1]]

        if candles[i].high == max(window_h):
            # Skip if the previous swing high is adjacent (duplicate cluster)
            if not high_indices or i - high_indices[-1] > 1:
                high_indices.append(i)
        if candles[i].low == min(window_l):
            if not low_indices or i - low_indices[-1] > 1:
                low_indices.append(i)

    highs = [candles[i].high for i in high_indices]
    lows = [candles[i].low for i in low_indices]
    return highs, lows


def _detect_trend(highs: List[float], lows: List[float]) -> str:
    """Determine trend from sequences of swing highs and lows."""
    if len(highs) < 2 or len(lows) < 2:
        return "UNKNOWN"

    higher_highs = all(highs[i] > highs[i - 1] for i in range(1, len(highs)))
    higher_lows = all(lows[i] > lows[i - 1] for i in range(1, len(lows)))
    lower_highs = all(highs[i] < highs[i - 1] for i in range(1, len(highs)))
    lower_lows = all(lows[i] < lows[i - 1] for i in range(1, len(lows)))

    if higher_highs and higher_lows:
        return "BULLISH"
    if lower_highs and lower_lows:
        return "BEARISH"

    # Relaxed majority rule
    hh_count = sum(highs[i] > highs[i - 1] for i in range(1, len(highs)))
    hl_count = sum(lows[i] > lows[i - 1] for i in range(1, len(lows)))
    lh_count = sum(highs[i] < highs[i - 1] for i in range(1, len(highs)))
    ll_count = sum(lows[i] < lows[i - 1] for i in range(1, len(lows)))

    total_h = len(highs) - 1
    total_l = len(lows) - 1

    if total_h > 0 and total_l > 0:
        if hh_count / total_h >= 0.6 and hl_count / total_l >= 0.6:
            return "BULLISH"
        if lh_count / total_h >= 0.6 and ll_count / total_l >= 0.6:
            return "BEARISH"

    return "SIDEWAYS"


def _detect_bos(candles: List[Candle], highs: List[float], lows: List[float], trend: str) -> bool:
    """
    BOS: price closes beyond the most recent significant swing high (bullish) or low (bearish).
    """
    if not candles:
        return False

    last_close = candles[-1].close

    if trend == "BULLISH" and highs:
        return last_close > highs[-1]
    if trend == "BEARISH" and lows:
        return last_close < lows[-1]

    return False


def _detect_choch(candles: List[Candle], highs: List[float], lows: List[float], trend: str) -> bool:
    """
    CHoCH: price closes in the opposite direction of the prevailing trend,
    suggesting a potential trend reversal.
    """
    if not candles:
        return False

    last_close = candles[-1].close

    if trend == "BULLISH" and lows:
        return last_close < lows[-1]
    if trend == "BEARISH" and highs:
        return last_close > highs[-1]

    return False


def analyze_structure(data: MarketData) -> StructureResult:
    """
    STEP 1 — Analyse market structure.
    Returns a StructureResult with trend, BOS/CHoCH flags and swing levels.
    """
    candles = data.candles
    highs, lows = _find_swing_highs_lows(candles)

    trend = _detect_trend(highs, lows)

    if trend == "UNKNOWN":
        return StructureResult(
            trend="UNKNOWN",
            structure_clear=False,
            details="Cannot determine trend — insufficient swing data.",
        )

    bos = _detect_bos(candles, highs, lows, trend)
    choch = _detect_choch(candles, highs, lows, trend)

    last_swing_high = highs[-1] if highs else None
    last_swing_low = lows[-1] if lows else None

    structure_clear = trend in ("BULLISH", "BEARISH")

    details_parts = [f"Trend: {trend}"]
    if bos:
        details_parts.append("BOS detected")
    if choch:
        details_parts.append("CHoCH detected")

    return StructureResult(
        trend=trend,
        bos_detected=bos,
        choch_detected=choch,
        last_swing_high=last_swing_high,
        last_swing_low=last_swing_low,
        structure_clear=structure_clear,
        details=", ".join(details_parts),
    )
