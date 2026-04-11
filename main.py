"""
Smart Money Institutional Trading System — CLI Demo

Usage:
    python main.py

This script runs the trading system against a synthetic data sample
and prints the JSON decision to stdout.
"""

import json
import random
from smart_money import TradingSystem
from smart_money.models import MarketData, Candle


def _generate_trending_candles(n: int = 60, trend: str = "BULLISH") -> list:
    """Generate synthetic OHLCV candles for demonstration."""
    random.seed(42)
    candles = []
    price = 100.0
    for i in range(n):
        if trend == "BULLISH":
            drift = random.uniform(-0.3, 0.6)
        else:
            drift = random.uniform(-0.6, 0.3)

        open_ = price + random.uniform(-0.2, 0.2)
        close = open_ + drift
        high = max(open_, close) + random.uniform(0, 0.4)
        low = min(open_, close) - random.uniform(0, 0.4)
        volume = random.uniform(500, 2000)

        candles.append(Candle(open=open_, high=high, low=low, close=close, volume=volume))
        price = close

    # Inject a liquidity sweep on the last candle for a realistic signal
    last = candles[-1]
    sweep_low = min(c.low for c in candles[-10:-1])
    candles[-1] = Candle(
        open=last.open,
        high=last.high,
        low=sweep_low - 0.05,   # wick below pool
        close=last.close + 0.3,  # close back above
        volume=last.volume * 2,  # volume spike
    )

    return candles


def main():
    print("=" * 60)
    print("Smart Money Institutional Trading System — Demo")
    print("=" * 60)

    candles = _generate_trending_candles(n=60, trend="BULLISH")
    data = MarketData(candles=candles, symbol="DEMO/USD", timeframe="H1")

    system = TradingSystem(account_size=10_000, risk_pct=0.01)
    result_json = system.analyze_to_json(data)

    print(result_json)


if __name__ == "__main__":
    main()
