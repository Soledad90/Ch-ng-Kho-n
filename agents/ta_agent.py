"""Technical-analysis agent — fetches BTC/USD OHLC and computes indicators.

Indicators: EMA(20/50/200), RSI(14), MACD(12,26,9), ATR(14),
            Ichimoku(9,26,52), Fibonacci of last swing, volume profile
            over last 180 candles, swing-pivot S/R.

Output: TaSignal — trend, momentum, volatility and key price levels.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal

from . import indicators as ind
from .data_sources import Candle, fetch_ohlc, iso_date

Trend = Literal["up", "down", "range"]


@dataclass
class TaSignal:
    as_of: str
    source: str
    timeframe: str
    close: float
    ema20: float | None
    ema50: float | None
    ema200: float | None
    rsi14: float | None
    macd: float | None
    macd_signal: float | None
    macd_hist: float | None
    atr14: float | None
    ichimoku_tenkan: float | None
    ichimoku_kijun: float | None
    ichimoku_span_a: float | None
    ichimoku_span_b: float | None
    trend: Trend
    momentum: str                  # "strong_up"|"up"|"flat"|"down"|"strong_down"
    cloud_state: str               # "above"|"inside"|"below"
    swing_high: float
    swing_low: float
    fib: dict[str, float]
    supports: list[float]
    resistances: list[float]
    vp_poc: float | None
    vp_vah: float | None
    vp_val: float | None
    direction: str                 # "bullish" | "bearish" | "neutral"

    def to_dict(self) -> dict:
        return asdict(self)


def _classify_trend(close: float, e20, e50, e200) -> Trend:
    if e50 is None or e200 is None:
        return "range"
    if close > e50 > e200:
        return "up"
    if close < e50 < e200:
        return "down"
    return "range"


def _classify_momentum(rsi_v, macd_hist) -> str:
    if rsi_v is None or macd_hist is None:
        return "flat"
    if rsi_v >= 60 and macd_hist > 0:
        return "strong_up"
    if rsi_v >= 50 and macd_hist > 0:
        return "up"
    if rsi_v <= 40 and macd_hist < 0:
        return "strong_down"
    if rsi_v <= 50 and macd_hist < 0:
        return "down"
    return "flat"


def _cloud_state(close: float, a, b) -> str:
    if a is None or b is None:
        return "inside"
    top, bot = max(a, b), min(a, b)
    if close > top:
        return "above"
    if close < bot:
        return "below"
    return "inside"


def _direction(trend: Trend, momentum: str, cloud: str) -> str:
    score = 0
    score += {"up": 1, "down": -1, "range": 0}[trend]
    score += {"strong_up": 2, "up": 1, "flat": 0, "down": -1, "strong_down": -2}[momentum]
    score += {"above": 1, "inside": 0, "below": -1}[cloud]
    if score >= 2:
        return "bullish"
    if score <= -2:
        return "bearish"
    return "neutral"


def run(tf: str = "1d") -> TaSignal:
    candles, source = fetch_ohlc(tf)  # type: ignore[arg-type]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    vols = [c.volume for c in candles]

    e20 = ind.ema(closes, 20)[-1]
    e50 = ind.ema(closes, 50)[-1]
    e200 = ind.ema(closes, 200)[-1]
    rsi_v = ind.rsi(closes, 14)[-1]
    macd_line, macd_sig, macd_hist = ind.macd(closes)
    atr_v = ind.atr(highs, lows, closes, 14)[-1]
    ich = ind.ichimoku(highs, lows, closes)

    # Fib off last 90-candle swing
    look = closes[-90:]
    h_look = highs[-90:]
    l_look = lows[-90:]
    sh_val = max(h_look)
    sl_val = min(l_look)
    fib = ind.fib_retracements(sh_val, sl_val)

    supports, resistances = ind.support_resistance(highs, lows, closes[-1])
    vp = ind.volume_profile(highs, lows, closes, vols)

    close = closes[-1]
    trend = _classify_trend(close, e20, e50, e200)
    momentum = _classify_momentum(rsi_v, macd_hist[-1])
    cloud = _cloud_state(close, ich["span_a"][-1], ich["span_b"][-1])

    return TaSignal(
        as_of=iso_date(candles[-1].ts),
        source=source,
        timeframe=tf,
        close=close,
        ema20=e20, ema50=e50, ema200=e200,
        rsi14=rsi_v,
        macd=macd_line[-1], macd_signal=macd_sig[-1], macd_hist=macd_hist[-1],
        atr14=atr_v,
        ichimoku_tenkan=ich["tenkan"][-1],
        ichimoku_kijun=ich["kijun"][-1],
        ichimoku_span_a=ich["span_a"][-1],
        ichimoku_span_b=ich["span_b"][-1],
        trend=trend,
        momentum=momentum,
        cloud_state=cloud,
        swing_high=sh_val,
        swing_low=sl_val,
        fib=fib,
        supports=supports[-5:],        # closest 5 below
        resistances=resistances[:5],   # closest 5 above
        vp_poc=vp["poc"], vp_vah=vp["vah"], vp_val=vp["val"],
        direction=_direction(trend, momentum, cloud),
    )


if __name__ == "__main__":
    import json
    sig = run()
    print(json.dumps(sig.to_dict(), indent=2, default=float))
