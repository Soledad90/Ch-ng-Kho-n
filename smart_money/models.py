"""
Data models for the Smart Money trading system.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Candle:
    """Represents a single OHLCV candle."""

    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: Optional[str] = None

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError("Candle high must be >= low")
        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise ValueError("Candle prices must be positive")
        if self.volume < 0:
            raise ValueError("Volume must be non-negative")


@dataclass
class MarketData:
    """Full market data input for analysis."""

    candles: List[Candle]
    symbol: str = ""
    timeframe: str = ""
    # Optional pre-computed indicators
    rsi: Optional[List[float]] = None
    ma: Optional[List[float]] = None

    def __post_init__(self) -> None:
        if len(self.candles) < 10:
            raise ValueError("At least 10 candles are required for analysis")


@dataclass
class StructureResult:
    """Result from market structure analysis."""

    trend: str  # "BULLISH" | "BEARISH" | "SIDEWAYS" | "UNKNOWN"
    bos_detected: bool = False
    choch_detected: bool = False
    last_swing_high: Optional[float] = None
    last_swing_low: Optional[float] = None
    structure_clear: bool = False
    details: str = ""


@dataclass
class LiquidityResult:
    """Result from liquidity analysis."""

    sweep_detected: bool = False
    equal_highs: List[float] = field(default_factory=list)
    equal_lows: List[float] = field(default_factory=list)
    liquidity_pools: List[float] = field(default_factory=list)
    swept_level: Optional[float] = None
    stop_hunt_detected: bool = False
    details: str = ""


@dataclass
class ConfluenceResult:
    """Result from confluence analysis."""

    score: int = 0
    factors: List[str] = field(default_factory=list)
    order_block: Optional[float] = None
    fvg_zone: Optional[tuple] = None  # (low, high)
    fibonacci_ote: Optional[tuple] = None  # (0.618 level, 0.79 level)
    rsi_divergence: bool = False
    volume_spike: bool = False
    details: str = ""


@dataclass
class EntryResult:
    """Result from entry logic."""

    entry_price: Optional[float] = None
    entry_type: str = ""  # "ORDER_BLOCK" | "FVG" | "FIBONACCI_OTE"
    stoploss: Optional[float] = None
    take_profit: Optional[float] = None
    details: str = ""


@dataclass
class RiskResult:
    """Result from risk management."""

    rr_ratio: Optional[float] = None
    position_size: Optional[float] = None
    risk_per_trade: str = "1-2%"
    rr_acceptable: bool = False
    details: str = ""


@dataclass
class TradeDecision:
    """Final trade decision output — strict JSON-serialisable."""

    decision: str  # "TRADE" | "NO TRADE"
    trend: str = ""
    liquidity: str = ""
    confluence_score: str = ""
    entry: str = ""
    stoploss: str = ""
    take_profit: str = ""
    rr_ratio: str = ""
    risk_per_trade: str = "1-2%"
    position_size: str = ""
    reason: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "trend": self.trend,
            "liquidity": self.liquidity,
            "confluence_score": self.confluence_score,
            "entry": self.entry,
            "stoploss": self.stoploss,
            "take_profit": self.take_profit,
            "rr_ratio": self.rr_ratio,
            "risk_per_trade": self.risk_per_trade,
            "position_size": self.position_size,
            "reason": self.reason,
            "warnings": self.warnings,
        }
