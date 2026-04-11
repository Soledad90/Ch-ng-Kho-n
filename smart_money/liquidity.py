"""
Step 2 — Liquidity Analysis
Identifies liquidity pools, equal highs/lows and stop-hunt sweeps.
"""

from typing import List, Optional

from .models import Candle, MarketData, LiquidityResult

# Tolerance for "equal" highs / lows (as % of price)
_EQUAL_TOLERANCE = 0.002  # 0.2 %
# How far back to look for liquidity pools
_POOL_LOOKBACK = 30


def _find_equal_levels(prices: List[float]) -> List[float]:
    """Return prices that are clustered within tolerance (equal highs or equal lows)."""
    equal: List[float] = []
    for i, p in enumerate(prices):
        for j, q in enumerate(prices):
            if i != j and abs(p - q) / max(p, q) <= _EQUAL_TOLERANCE:
                if p not in equal:
                    equal.append(round(p, 8))
    return equal


def _detect_stop_hunt(candles: List[Candle], pools: List[float], trend: str) -> tuple:
    """
    A stop hunt occurs when price briefly pierces a liquidity level but then
    closes back on the other side (pin-bar / wick behaviour).
    Returns (detected: bool, swept_level: Optional[float])
    """
    if not pools or len(candles) < 2:
        return False, None

    last = candles[-1]

    for level in pools:
        if trend == "BULLISH":
            # Price wicked below a prior low (swept sell-side liquidity) then closed above it
            if last.low < level and last.close > level:
                return True, level
        elif trend == "BEARISH":
            # Price wicked above a prior high (swept buy-side liquidity) then closed below it
            if last.high > level and last.close < level:
                return True, level
        else:
            # Both directions in sideways
            if (last.low < level and last.close > level) or (
                last.high > level and last.close < level
            ):
                return True, level

    return False, None


def _build_liquidity_pools(candles: List[Candle]) -> List[float]:
    """Collect recent swing highs and lows as liquidity pool candidates."""
    recent = candles[-_POOL_LOOKBACK:]
    pools: List[float] = []
    n = len(recent)
    for i in range(1, n - 1):
        if recent[i].high > recent[i - 1].high and recent[i].high > recent[i + 1].high:
            pools.append(recent[i].high)
        if recent[i].low < recent[i - 1].low and recent[i].low < recent[i + 1].low:
            pools.append(recent[i].low)
    return pools


def analyze_liquidity(data: MarketData, trend: str) -> LiquidityResult:
    """
    STEP 2 — Analyse liquidity.
    Returns a LiquidityResult with pools, equal levels and sweep detection.
    """
    candles = data.candles
    pools = _build_liquidity_pools(candles)

    highs = [c.high for c in candles[-_POOL_LOOKBACK:]]
    lows = [c.low for c in candles[-_POOL_LOOKBACK:]]

    equal_highs = _find_equal_levels(highs)
    equal_lows = _find_equal_levels(lows)

    # Add equal levels to pools
    all_pools = list(set(pools + equal_highs + equal_lows))

    sweep_detected, swept_level = _detect_stop_hunt(candles, all_pools, trend)

    details_parts: List[str] = []
    if equal_highs:
        details_parts.append(f"Equal highs at {[round(h, 4) for h in equal_highs[:3]]}")
    if equal_lows:
        details_parts.append(f"Equal lows at {[round(l, 4) for l in equal_lows[:3]]}")
    if sweep_detected:
        details_parts.append(f"Liquidity sweep at {swept_level}")
    else:
        details_parts.append("No liquidity sweep detected")

    return LiquidityResult(
        sweep_detected=sweep_detected,
        equal_highs=equal_highs,
        equal_lows=equal_lows,
        liquidity_pools=all_pools,
        swept_level=swept_level,
        stop_hunt_detected=sweep_detected,
        details=", ".join(details_parts) if details_parts else "No liquidity data",
    )
