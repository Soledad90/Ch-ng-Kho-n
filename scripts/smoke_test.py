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


def test_coinglass_signals_synthetic() -> None:
    """Pure helpers in agents.coinglass_signals — fully offline.

    The webapp's confluence augmentation only uses these adapter
    functions (not the HTTP client), so as long as their classification
    logic is correct, the augmented decision is correct too.
    """
    from agents import coinglass_signals as cgs

    # ---- funding_consensus -----------------------------------------------
    assert cgs.funding_consensus(None)["regime"] == "unknown"
    f = cgs.funding_consensus([
        {"exchange": "Binance", "rate": 0.0004},  # extreme long
        {"exchange": "OKX",     "rate": 0.0005},
        {"exchange": "Bybit",   "rate": 0.0006},
    ])
    assert f["ok"] and f["regime"] == "extreme_long" and f["n_exchanges"] == 3
    f2 = cgs.funding_consensus([
        {"exchange": "Binance", "rate": -0.0005},
        {"exchange": "OKX",     "rate": -0.0006},
    ])
    assert f2["regime"] == "extreme_short"

    # ---- oi_trend --------------------------------------------------------
    rows = [{"close": 100 + i} for i in range(20)]
    t = cgs.oi_trend(rows, lookback=12)
    assert t["ok"] and t["trend"] == "rising" and t["change_pct"] > 1.0
    flat = cgs.oi_trend([{"close": 100} for _ in range(20)], lookback=12)
    assert flat["trend"] == "flat"
    assert cgs.oi_trend(None)["trend"] == "unknown"

    # ---- liq_pressure ----------------------------------------------------
    longs_flush = [{"long_liq_usd": 100, "short_liq_usd": 10} for _ in range(24)]
    lp = cgs.liq_pressure(longs_flush)
    assert lp["net_pressure"] == "longs_flushed"
    shorts_squeeze = [{"long_liq_usd": 10, "short_liq_usd": 100} for _ in range(24)]
    assert cgs.liq_pressure(shorts_squeeze)["net_pressure"] == "shorts_squeezed"
    assert cgs.liq_pressure(None)["net_pressure"] == "unknown"

    # ---- heatmap_clusters -----------------------------------------------
    # y prices: 90, 95, 100, 105, 110. current_price = 100.
    # Heaviest cell above is yIdx=4 (110); below is yIdx=0 (90).
    hm = {
        "y": [90, 95, 100, 105, 110],
        "data": [
            [0, 0, 50],   # below cluster
            [1, 0, 30],
            [0, 4, 80],   # above cluster (largest)
            [1, 4, 70],
            [0, 3, 5],    # tiny noise above 100 at 105
        ],
    }
    h = cgs.heatmap_clusters(hm, current_price=100)
    assert h["ok"]
    assert h["magnet_up"]["price"] == 110
    assert h["magnet_down"]["price"] == 90
    # missing heatmap -> ok False
    assert not cgs.heatmap_clusters(None, 100)["ok"]
    # malformed cells silently skipped
    bad = cgs.heatmap_clusters({"y": [10, 20], "data": [["x", "y", "z"]]}, 15)
    assert not bad["ok"]

    # ---- sentiment -------------------------------------------------------
    assert cgs.sentiment([{"long_pct": 70, "short_pct": 30, "ratio": 2.3}])["skew"] == "crowd_long"
    assert cgs.sentiment([{"long_pct": 30, "short_pct": 70, "ratio": 0.43}])["skew"] == "crowd_short"
    assert cgs.sentiment([{"long_pct": 50, "short_pct": 50, "ratio": 1.0}])["skew"] == "balanced"
    assert cgs.sentiment(None)["skew"] == "unknown"

    # ---- coinglass_confluence (decision augmentation) -------------------
    # Long trade + crowd-short funding + magnet up within 5% -> both PASS
    funding = {"ok": True, "regime": "extreme_short"}
    heatmap = {"ok": True, "magnet_up": {"price": 102.0, "distance_pct": 2.0,
                                          "intensity": 1.0},
               "magnet_down": None}
    extra = cgs.coinglass_confluence("long", funding, lp, heatmap, sent={}, current_price=100)
    assert [e["ok"] for e in extra] == [True, True], extra

    # Long trade + crowd-LONG funding -> funding item FAILS
    extra2 = cgs.coinglass_confluence(
        "long", {"ok": True, "regime": "extreme_long"}, lp, heatmap,
        sent={}, current_price=100,
    )
    assert extra2[0]["ok"] is False
    # No direction -> both fail
    extra3 = cgs.coinglass_confluence("none", funding, lp, heatmap, sent={}, current_price=100)
    assert all(not e["ok"] for e in extra3)
    print("[OK] coinglass_signals adapters (funding/oi/liq/heatmap/sentiment + confluence)")


def test_coinglass_client_no_key() -> None:
    """Without COINGLASS_API_KEY the client must short-circuit cleanly."""
    import os
    from agents.coinglass_client import CoinglassClient

    saved = os.environ.pop("COINGLASS_API_KEY", None)
    try:
        c = CoinglassClient()
        assert not c.configured
        # Each public method should return None and set last_error.
        assert c.funding_rate_exchange_list("BTC") is None
        assert c.last_error and "not set" in c.last_error
        assert c.liquidation_aggregated_history("BTC") is None
        assert c.liquidation_aggregated_heatmap("BTC") is None
        assert c.oi_weight_ohlc_history("BTC") is None
        assert c.long_short_position_ratio("BTC") is None
    finally:
        if saved is not None:
            os.environ["COINGLASS_API_KEY"] = saved
    print("[OK] coinglass client gracefully degrades without API key")


def test_webapp_gate_no_coinglass() -> None:
    """When Coinglass data is missing the augmented gate must NOT
    become stricter than the base master_agent gate.

    Regression for: gate hard-coded at 8 with cg_passed=0 and only 12
    base factors → effective threshold 8/12 (67%) vs base 7/12 (58%).
    """
    import os
    import sys

    saved = os.environ.pop("COINGLASS_API_KEY", None)

    try:
        class FakeSnap:
            def __init__(self) -> None:
                self.close = 70_000.0

        class FakeSig:
            def __init__(self) -> None:
                self.direction = "long"
                self.confluence_score = 7
                self.decision = "TRADE"
                self.rr = 2.5
                self.hard_stops: list = []
                self.m15 = FakeSnap()
            def to_dict(self) -> dict:
                return {
                    "direction": self.direction,
                    "decision": self.decision,
                    "confluence_score": self.confluence_score,
                    "rr": self.rr,
                    "tp2": 78_000.0,
                }

        def fake_run(asset: str = "BTC"):
            return FakeSig()

        from agents import webapp
        # Patch the master_agent reference imported into webapp's namespace
        # AND force the Coinglass client to be unconfigured.
        saved_run = webapp.master_agent.run
        saved_key = webapp._client.api_key
        webapp.master_agent.run = fake_run
        webapp._client.api_key = None

        out = webapp._decision("BTC")
        assert "error" not in out, out
        assert out["confluence_max"] == 12, out["confluence_max"]
        assert out["confluence_gate"] == 7, out["confluence_gate"]
        assert out["confluence_score_total"] == 7, out["confluence_score_total"]
        # 7 base factors >= gate 7 → augmented decision must be TRADE,
        # matching what master_agent would emit. Pre-fix: NO_TRADE.
        assert out["decision_augmented"] == "TRADE", out["decision_augmented"]

        # Per-source `errors` map (regression for: last_error overwritten
        # by every call so frontend hid valid panels). All 4 calls fail
        # identically without the key, so all 4 entries are populated.
        errs = out["coinglass"]["errors"]
        assert set(errs.keys()) == {"funding", "liq", "heatmap", "sentiment"}, errs
        for src, msg in errs.items():
            assert msg == "COINGLASS_API_KEY not set", (src, msg)

        # confluence_extra items must carry per-factor `evaluable` flags
        # so the frontend can render them independently (regression for:
        # frontend AND-gated visibility while backend counted per-factor).
        for ex in out["coinglass"]["confluence_extra"]:
            assert ex["evaluable"] is False, ex
            assert ex["source"] in ("funding", "heatmap"), ex
    finally:
        if saved is not None:
            os.environ["COINGLASS_API_KEY"] = saved
        try:
            webapp.master_agent.run = saved_run  # type: ignore[name-defined]
            webapp._client.api_key = saved_key   # type: ignore[name-defined]
        except NameError:
            pass
    print("[OK] webapp gate falls back to 7/12 when Coinglass unavailable")


def test_coinglass_extras_partial_evaluability() -> None:
    """When only funding (or only heatmap) returns data, backend counts
    that single factor in confluence_max and the corresponding extra
    item must carry `evaluable=True` so the frontend renders one row,
    not zero. Regression for: frontend `funding.ok && heatmap.ok` AND
    gate hiding all extras when only one source succeeded.
    """
    from agents import coinglass_signals as cgs

    funding_ok = {"ok": True, "regime": "extreme_short"}
    heatmap_missing = {"ok": False, "magnet_up": None, "magnet_down": None}
    extras = cgs.coinglass_confluence(
        "long", funding_ok, {}, heatmap_missing, {}, current_price=100.0,
    )
    assert len(extras) == 2
    funding_item = next(e for e in extras if e["source"] == "funding")
    heatmap_item = next(e for e in extras if e["source"] == "heatmap")
    assert funding_item["evaluable"] is True, funding_item
    assert funding_item["ok"] is True, funding_item
    assert heatmap_item["evaluable"] is False, heatmap_item

    # Symmetric: only heatmap evaluable.
    funding_missing = {"ok": False, "regime": "unknown"}
    heatmap_ok = {"ok": True,
                  "magnet_up": {"price": 102.0, "distance_pct": 2.0,
                                "intensity": 1.0},
                  "magnet_down": None}
    extras2 = cgs.coinglass_confluence(
        "long", funding_missing, {}, heatmap_ok, {}, current_price=100.0,
    )
    f2 = next(e for e in extras2 if e["source"] == "funding")
    h2 = next(e for e in extras2 if e["source"] == "heatmap")
    assert f2["evaluable"] is False, f2
    assert h2["evaluable"] is True, h2
    assert h2["ok"] is True, h2
    print("[OK] coinglass extras carry per-factor evaluable flags")


def main() -> int:
    test_mvrv_agent_live()
    test_indicators_synthetic()
    test_orchestrator_matrix()
    test_master_agent_pieces()
    test_fvg_ob_synthetic()
    test_futures_classify()
    test_liq_heatmap()
    test_coinglass_signals_synthetic()
    test_coinglass_client_no_key()
    test_webapp_gate_no_coinglass()
    test_coinglass_extras_partial_evaluability()
    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
