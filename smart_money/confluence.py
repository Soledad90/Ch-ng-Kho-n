"""
Step 3 — Confluence Analysis
Scores the trade setup; requires at least 3 confluence factors to proceed.

Mandatory factors (checked in order):
  1. Structure alignment
  2. Liquidity sweep
  3. POI — Order Block (OB) or Fair-Value Gap (FVG)

Optional factors:
  4. RSI divergence
  5. Volume spike
"""

from typing import List, Optional

from .models import Candle, MarketData, StructureResult, LiquidityResult, ConfluenceResult

_VOLUME_SPIKE_MULTIPLIER = 1.5  # volume > 1.5× rolling average
_VOLUME_LOOKBACK = 20
_OB_LOOKBACK = 15  # candles to scan for order blocks
_FVG_LOOKBACK = 10  # candles to scan for FVG
_RSI_OVERSOLD = 35
_RSI_OVERBOUGHT = 65


def _find_order_block(candles: List[Candle], trend: str) -> Optional[float]:
    """
    An Order Block (OB) is the last opposing candle before a strong impulsive move.
    For a BULLISH setup: the last bearish candle before an up-move.
    For a BEARISH setup: the last bullish candle before a down-move.
    """
    recent = candles[-_OB_LOOKBACK:]
    if trend == "BULLISH":
        for i in range(len(recent) - 2, 0, -1):
            c = recent[i]
            next_c = recent[i + 1]
            if c.close < c.open and next_c.close > next_c.open and next_c.close > c.high:
                return (c.open + c.close) / 2  # mid of OB candle
    elif trend == "BEARISH":
        for i in range(len(recent) - 2, 0, -1):
            c = recent[i]
            next_c = recent[i + 1]
            if c.close > c.open and next_c.close < next_c.open and next_c.close < c.low:
                return (c.open + c.close) / 2
    return None


def _find_fvg(candles: List[Candle], trend: str) -> Optional[tuple]:
    """
    A Fair-Value Gap (FVG) exists when there is a price gap between candle[i-1].high
    and candle[i+1].low (bullish) or candle[i-1].low and candle[i+1].high (bearish).
    Returns a (low, high) tuple for the gap zone, or None.
    """
    recent = candles[-_FVG_LOOKBACK:]
    for i in range(1, len(recent) - 1):
        prev = recent[i - 1]
        nxt = recent[i + 1]
        if trend == "BULLISH" and nxt.low > prev.high:
            return (prev.high, nxt.low)
        if trend == "BEARISH" and nxt.high < prev.low:
            return (nxt.high, prev.low)
    return None


def _find_fibonacci_ote(last_swing_high: Optional[float], last_swing_low: Optional[float]) -> Optional[tuple]:
    """Return the Optimal Trade Entry (OTE) zone: Fibonacci 0.618–0.79 retracement."""
    if last_swing_high is None or last_swing_low is None:
        return None
    rng = last_swing_high - last_swing_low
    if rng <= 0:
        return None
    fib_618 = last_swing_high - 0.618 * rng
    fib_79 = last_swing_high - 0.79 * rng
    return (round(fib_79, 8), round(fib_618, 8))  # (lower, upper)


def _detect_rsi_divergence(rsi: Optional[List[float]], candles: List[Candle], trend: str) -> bool:
    """
    Detect simple RSI divergence:
    - Bullish divergence: price makes lower low, RSI makes higher low.
    - Bearish divergence: price makes higher high, RSI makes lower high.
    """
    if not rsi or len(rsi) < 2 or len(candles) < 2:
        return False

    last_price = candles[-1].close
    prev_price = candles[-2].close
    last_rsi = rsi[-1]
    prev_rsi = rsi[-2]

    if trend == "BULLISH" and last_price < prev_price and last_rsi > prev_rsi:
        return True
    if trend == "BEARISH" and last_price > prev_price and last_rsi < prev_rsi:
        return True
    return False


def _detect_volume_spike(candles: List[Candle]) -> bool:
    """Volume of the last candle is significantly above recent average."""
    if len(candles) < _VOLUME_LOOKBACK + 1:
        return False
    avg_volume = sum(c.volume for c in candles[-_VOLUME_LOOKBACK - 1: -1]) / _VOLUME_LOOKBACK
    if avg_volume == 0:
        return False
    return candles[-1].volume > avg_volume * _VOLUME_SPIKE_MULTIPLIER


def analyze_confluence(
    data: MarketData,
    structure: StructureResult,
    liquidity: LiquidityResult,
) -> ConfluenceResult:
    """
    STEP 3 — Score confluence.
    Mandatory: structure alignment + liquidity sweep + POI (OB or FVG).
    Optional:  RSI divergence, volume spike.
    """
    candles = data.candles
    trend = structure.trend
    factors: List[str] = []
    score = 0

    # Factor 1: Structure alignment
    if structure.structure_clear and trend in ("BULLISH", "BEARISH"):
        factors.append("Structure alignment")
        score += 1

    # Factor 2: Liquidity sweep
    if liquidity.sweep_detected:
        factors.append("Liquidity sweep")
        score += 1

    # Factor 3: POI — Order Block
    ob = _find_order_block(candles, trend)
    fvg = _find_fvg(candles, trend)
    ote = _find_fibonacci_ote(structure.last_swing_high, structure.last_swing_low)

    poi_found = ob is not None or fvg is not None
    if poi_found:
        poi_label = []
        if ob is not None:
            poi_label.append(f"OB@{round(ob, 4)}")
        if fvg is not None:
            fvg_mid = round((fvg[0] + fvg[1]) / 2, 4)
            poi_label.append(f"FVG@{fvg_mid}")
        factors.append(f"POI ({', '.join(poi_label)})")
        score += 1

    # Optional factor 4: RSI divergence
    rsi_div = _detect_rsi_divergence(data.rsi, candles, trend)
    if rsi_div:
        factors.append("RSI divergence")
        score += 1

    # Optional factor 5: Volume spike
    vol_spike = _detect_volume_spike(candles)
    if vol_spike:
        factors.append("Volume spike")
        score += 1

    details = f"Score {score}/5. Factors: {factors}"

    return ConfluenceResult(
        score=score,
        factors=factors,
        order_block=ob,
        fvg_zone=fvg,
        fibonacci_ote=ote,
        rsi_divergence=rsi_div,
        volume_spike=vol_spike,
        details=details,
    )
