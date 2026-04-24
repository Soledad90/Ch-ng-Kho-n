"""
Step 4 — Entry Logic
Determines the optimal entry price, stoploss and take-profit.

Entry priority:
  1. Order Block (OB)
  2. Fair-Value Gap (FVG)
  3. Fibonacci OTE zone (0.618–0.79)

Stoploss: beyond the swept liquidity level.
Take Profit: next liquidity pool in the trend direction.
"""

from typing import Optional

from .models import (
    MarketData,
    StructureResult,
    LiquidityResult,
    ConfluenceResult,
    EntryResult,
)

_SL_BUFFER_PCT = 0.001  # 0.1% buffer beyond sweep level


def _next_take_profit(
    trend: str,
    liquidity: LiquidityResult,
    current_price: float,
) -> Optional[float]:
    """Return the nearest liquidity pool in the direction of the trade."""
    pools = sorted(liquidity.liquidity_pools)
    if not pools:
        return None

    if trend == "BULLISH":
        targets = [p for p in pools if p > current_price]
        return min(targets) if targets else None
    if trend == "BEARISH":
        targets = [p for p in pools if p < current_price]
        return max(targets) if targets else None
    return None


def calculate_entry(
    data: MarketData,
    structure: StructureResult,
    liquidity: LiquidityResult,
    confluence: ConfluenceResult,
) -> EntryResult:
    """
    STEP 4 — Determine entry, stoploss and take-profit.
    """
    trend = structure.trend
    current_price = data.candles[-1].close

    entry_price: Optional[float] = None
    entry_type = ""

    # Priority 1: Order Block
    if confluence.order_block is not None:
        entry_price = confluence.order_block
        entry_type = "ORDER_BLOCK"

    # Priority 2: FVG
    elif confluence.fvg_zone is not None:
        fvg_low, fvg_high = confluence.fvg_zone
        entry_price = (fvg_low + fvg_high) / 2
        entry_type = "FVG"

    # Priority 3: Fibonacci OTE midpoint
    elif confluence.fibonacci_ote is not None:
        ote_low, ote_high = confluence.fibonacci_ote
        entry_price = (ote_low + ote_high) / 2
        entry_type = "FIBONACCI_OTE"

    if entry_price is None:
        return EntryResult(details="No valid POI found for entry.")

    # Stoploss: beyond the swept liquidity level
    stoploss: Optional[float] = None
    if liquidity.swept_level is not None:
        if trend == "BULLISH":
            stoploss = round(liquidity.swept_level * (1 - _SL_BUFFER_PCT), 8)
        else:
            stoploss = round(liquidity.swept_level * (1 + _SL_BUFFER_PCT), 8)
    else:
        # Fallback: use last swing level
        if trend == "BULLISH" and structure.last_swing_low is not None:
            stoploss = round(structure.last_swing_low * (1 - _SL_BUFFER_PCT), 8)
        elif trend == "BEARISH" and structure.last_swing_high is not None:
            stoploss = round(structure.last_swing_high * (1 + _SL_BUFFER_PCT), 8)

    # Take Profit: next liquidity pool
    take_profit = _next_take_profit(trend, liquidity, current_price)

    details_parts = [f"Entry type: {entry_type}", f"Entry: {round(entry_price, 4)}"]
    if stoploss:
        details_parts.append(f"SL: {round(stoploss, 4)}")
    if take_profit:
        details_parts.append(f"TP: {round(take_profit, 4)}")

    return EntryResult(
        entry_price=round(entry_price, 8),
        entry_type=entry_type,
        stoploss=stoploss,
        take_profit=take_profit,
        details=", ".join(details_parts),
    )
