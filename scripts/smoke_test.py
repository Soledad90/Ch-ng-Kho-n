#!/usr/bin/env python3
"""Offline smoke tests for the agent system.

Does NOT hit the network. Validates:
- MVRV agent against the committed CSV.
- Indicators on synthetic series (monotonic up, flat, oscillating).
- Orchestrator decision matrix for each (MVRV dir, TA dir) combination.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import indicators as ind
from agents import mvrv_agent
from agents.orchestrator import plan as make_plan
from agents.mvrv_agent import MvrvSignal
from agents.ta_agent import TaSignal


def _fake_ta(direction: str) -> TaSignal:
    close = 70_000.0
    if direction == "bullish":
        trend, momentum, cloud = "up", "strong_up", "above"
    elif direction == "bearish":
        trend, momentum, cloud = "down", "strong_down", "below"
    else:
        trend, momentum, cloud = "range", "flat", "inside"
    fib = ind.fib_retracements(90_000.0, 60_000.0)
    return TaSignal(
        as_of="2026-04-24", source="fake", timeframe="1d", close=close,
        ema20=68_000.0, ema50=67_000.0, ema200=72_000.0,
        rsi14=55.0, macd=10.0, macd_signal=5.0, macd_hist=5.0, atr14=1_500.0,
        ichimoku_tenkan=69_000.0, ichimoku_kijun=67_000.0,
        ichimoku_span_a=68_000.0, ichimoku_span_b=66_000.0,
        trend=trend, momentum=momentum, cloud_state=cloud,
        swing_high=90_000.0, swing_low=60_000.0, fib=fib,
        supports=[65_000.0, 67_000.0, 69_500.0],
        resistances=[72_000.0, 78_000.0, 85_000.0],
        vp_poc=70_000.0, vp_vah=85_000.0, vp_val=62_000.0,
        direction=direction,
    )


def _fake_mvrv(direction: str) -> MvrvSignal:
    if direction == "bullish":
        regime, mv, mult, z = "Discount", 1.30, 1.15, -0.80
    elif direction == "bearish":
        regime, mv, mult, z = "Hot", 2.40, 0.60, 1.50
    else:
        regime, mv, mult, z = "Neutral", 1.80, 1.00, 0.20
    return MvrvSignal(
        as_of="2026-04-24", mvrv=mv, realized_price=54_000.0, btc_price=70_000.0,
        percentile=35.0, z_score=z, regime=regime, size_multiplier=mult,
        signal="test", direction=direction,
    )


def test_mvrv_agent_live() -> None:
    sig = mvrv_agent.run()
    assert 0 <= sig.percentile <= 100
    assert sig.regime in {"Deep Value", "Discount", "Neutral", "Hot", "Euphoria"}
    assert sig.direction in {"bullish", "bearish", "neutral"}
    assert sig.size_multiplier > 0
    print(f"[OK] MVRV: {sig.regime}  mvrv={sig.mvrv:.2f}  dir={sig.direction}")


def test_indicators_synthetic() -> None:
    # monotonic up: RSI -> 100, EMA climbs
    up = [100.0 + i for i in range(200)]
    assert ind.ema(up, 20)[-1] > up[50]
    assert ind.rsi(up, 14)[-1] is not None and ind.rsi(up, 14)[-1] > 90
    # flat: RSI ~ 50 (actually undefined -> 100 in pure-gain case; test small noise)
    import random
    random.seed(0)
    flat = [100.0 + random.uniform(-0.01, 0.01) for _ in range(200)]
    r = ind.rsi(flat, 14)[-1]
    assert r is not None and 30 < r < 70
    # ATR non-negative
    highs = [c + 1 for c in up]
    lows = [c - 1 for c in up]
    assert ind.atr(highs, lows, up, 14)[-1] > 0
    # Fib sane
    fib = ind.fib_retracements(100.0, 50.0)
    assert fib["0.500"] == 75.0
    print("[OK] indicators")


def test_orchestrator_matrix() -> None:
    expected = {
        ("bullish", "bullish"): "STRONG_BUY",
        ("bullish", "neutral"): "BUY_DCA",
        ("bullish", "bearish"): "WAIT_DIP",
        ("neutral", "bullish"): "BUY",
        ("neutral", "neutral"): "HOLD",
        ("neutral", "bearish"): "REDUCE",
        ("bearish", "bullish"): "TRIM",
        ("bearish", "neutral"): "TRIM",
        ("bearish", "bearish"): "EXIT",
    }
    for (m, t), want in expected.items():
        p = make_plan(_fake_mvrv(m), _fake_ta(t))
        assert p.action == want, f"({m},{t}) -> {p.action} want {want}"
    print(f"[OK] orchestrator matrix ({len(expected)} combos)")


def test_master_agent_pieces() -> None:
    """Offline tests for master-agent helpers that don't need network."""
    from agents import master_agent as m
    from agents.data_sources import Candle
    # _kill_zone
    assert m._kill_zone(int(__import__("calendar").timegm((2026, 4, 24, 8, 0, 0, 0, 0, 0)))) is True
    assert m._kill_zone(int(__import__("calendar").timegm((2026, 4, 24, 3, 0, 0, 0, 0, 0)))) is False
    # _detect_sweep: craft 31 candles with last one wicking above prior high
    base = [Candle(i, 100.0, 101.0, 99.0, 100.0, 1.0) for i in range(30)]
    wick = Candle(31, 100.0, 105.0, 99.5, 100.5, 1.0)  # high>prev_high, close<prev_high
    d, px = m._detect_sweep(base + [wick], lookback=30)
    assert d == "bearish" and px == 101.0
    # _poi classification
    snap = m.TFSnapshot(
        tf="1d", close=85.0, ema20=None, ema50=None, ema200=None,
        rsi14=None, macd_hist=None, atr14=1.0, trend="up",
        swing_high=100.0, swing_low=50.0, mid=75.0, poc=None,
    )
    poi = m._poi(snap)
    assert poi.current_in == "premium", poi.current_in
    print("[OK] master-agent helpers")


def main() -> int:
    test_mvrv_agent_live()
    test_indicators_synthetic()
    test_orchestrator_matrix()
    test_master_agent_pieces()
    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
