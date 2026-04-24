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


def test_fvg_ob_synthetic() -> None:
    from agents import indicators as ind
    # Construct synthetic bullish FVG: candles with big gap at index 2
    opens = [100, 101, 105, 110, 112]
    highs = [102, 103, 108, 112, 115]  # highs[0]=102 < lows[2]=107 -> bullish FVG at idx 2
    lows = [100, 101, 107, 110, 112]
    closes = [101, 102, 107, 111, 114]
    fvgs = ind.detect_fvg(highs, lows, closes, lookback=10)
    assert any(f["kind"] == "bullish" and f["idx"] == 2 for f in fvgs), fvgs
    # Construct OB: big impulsive up candle preceded by down candle
    # need >14 candles for ATR; ATR of flat base is ~2, impulse body must be 3
    opens = [100] * 14 + [99, 110]
    highs = [101] * 14 + [100, 120]
    lows = [99] * 14 + [97, 109]
    closes = [100] * 14 + [97, 119]   # idx 14 is down, idx 15 is big up (body=9)
    obs = ind.detect_order_blocks(opens, highs, lows, closes, lookback=20,
                                   impulse_atr_mult=1.5)
    assert any(o["kind"] == "bullish" and o["idx"] == 14 for o in obs), obs
    print("[OK] FVG + OB detectors")


def test_futures_classify() -> None:
    from agents.master_agent import _classify_funding
    assert _classify_funding(0.0) == "neutral"
    assert _classify_funding(0.0005) == "extreme_long"
    assert _classify_funding(0.00015) == "mild_long"
    assert _classify_funding(-0.0005) == "extreme_short"
    assert _classify_funding(-0.00015) == "mild_short"
    print("[OK] funding classifier")


def test_liq_heatmap() -> None:
    from agents.futures_data import LiquidationEvent, liquidation_heatmap
    events = [
        LiquidationEvent(0, "long", 100.0, 1.0),
        LiquidationEvent(1, "long", 100.5, 2.0),   # cluster
        LiquidationEvent(2, "short", 110.0, 3.0),  # cluster
        LiquidationEvent(3, "short", 120.0, 1.0),
    ]
    h = liquidation_heatmap(events, bins=10)
    assert h["total_long"] == 3.0
    assert h["total_short"] == 4.0
    assert h["poc_long"] is not None and abs(h["poc_long"] - 100.0) < 3.0
    assert h["poc_short"] is not None and abs(h["poc_short"] - 110.0) < 3.0
    print("[OK] liquidation heatmap")


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


def test_backtest_offline() -> None:
    """Exercise run_backtest on synthetic candles (no network).

    Keeps the smoke suite's offline contract. We patch fetch_ohlc to
    return 500 deterministic daily bars that cover dates present in
    data/mvrv_btc.csv, so the MVRV date-lookup inside run_backtest
    resolves without falling back to 'unknown'.
    """
    import math
    from unittest.mock import patch
    from agents import backtest as bt
    from agents.data_sources import Candle

    # 2022-01-01 UTC; 500 daily bars -> covers into 2023-05. These dates
    # all exist in the committed MVRV CSV.
    start_ts = 1_640_995_200
    day = 86_400
    bars: list[Candle] = []
    for i in range(500):
        # mild noisy uptrend + sinusoid so EMA/RSI/MACD aren't all zero
        base = 40_000 + i * 50 + 2_000 * math.sin(i / 17.0)
        h = base * 1.02
        l = base * 0.98
        o = base * 0.995
        c = base * 1.003
        bars.append(Candle(start_ts + i * day, o, h, l, c, 100.0))

    with patch.object(bt, "fetch_ohlc", return_value=(bars, "synthetic")):
        stats, trades = bt.run_backtest(
            max_hold=10, confluence_min=6, rr_min=3.0,
            out_dir=None, cooldown_bars=5,
        )

    assert stats.n_trades == len(trades)
    for t in trades:
        assert t.r_multiple != 0
        if t.direction == "long":
            assert t.stop < t.entry < t.tp1
        else:
            assert t.stop > t.entry > t.tp1
    print(f"[OK] backtest engine (offline, n={stats.n_trades}, win_rate={stats.win_rate}%)")


def main() -> int:
    test_mvrv_agent_live()
    test_indicators_synthetic()
    test_orchestrator_matrix()
    test_master_agent_pieces()
    test_fvg_ob_synthetic()
    test_futures_classify()
    test_liq_heatmap()
    test_backtest_offline()
    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
