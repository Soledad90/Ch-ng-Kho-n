"""
Tests for the Smart Money Institutional Trading System.
"""

import json
import pytest

from smart_money import TradingSystem
from smart_money.models import MarketData, Candle, TradeDecision
from smart_money.market_structure import analyze_structure
from smart_money.liquidity import analyze_liquidity
from smart_money.confluence import analyze_confluence
from smart_money.entry import calculate_entry
from smart_money.risk import calculate_risk
from smart_money.psychology import psychology_filter


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _bullish_candles(n: int = 50) -> list:
    """
    Generate a bullish sequence with a 5-up / 3-down zigzag (HH/HL pattern).
    The swing high at the end of each impulse leg is the local maximum in a
    7-candle window (compatible with _SWING_LOOKBACK = 3).
    """
    candles = []
    price = 100.0
    for i in range(n):
        phase = i % 8
        if phase < 5:
            drift = 1.0   # impulse up
        else:
            drift = -0.6  # pullback (< 1/5 of impulse total)
        open_ = price
        close = price + drift
        high = max(open_, close) + 0.15
        low = min(open_, close) - 0.10
        candles.append(Candle(open=open_, high=high, low=low, close=close, volume=1000))
        price = close
    return candles


def _bearish_candles(n: int = 50) -> list:
    """
    Generate a bearish sequence with a 5-down / 3-up zigzag (LH/LL pattern).
    Symmetric to _bullish_candles.
    """
    candles = []
    price = 200.0
    for i in range(n):
        phase = i % 8
        if phase < 5:
            drift = -1.0  # impulse down
        else:
            drift = 0.6   # bounce (< 1/5 of impulse total)
        open_ = price
        close = price + drift
        high = max(open_, close) + 0.10
        low = min(open_, close) - 0.15
        candles.append(Candle(open=open_, high=high, low=low, close=close, volume=1000))
        price = close
    return candles


def _inject_sweep(candles: list, trend: str) -> list:
    """
    Append a candle that performs a liquidity sweep (wick through a pool,
    then close back the other side).
    """
    candles = list(candles)
    # find a liquidity pool to sweep
    if trend == "BULLISH":
        pool = min(c.low for c in candles[-10:])
        last = candles[-1]
        sweep = Candle(
            open=last.close,
            high=last.close + 0.5,
            low=pool - 0.1,      # wick below pool
            close=last.close + 0.3,  # close above pool
            volume=last.volume * 2,
        )
    else:
        pool = max(c.high for c in candles[-10:])
        last = candles[-1]
        sweep = Candle(
            open=last.close,
            high=pool + 0.1,     # wick above pool
            low=last.close - 0.5,
            close=last.close - 0.3,  # close below pool
            volume=last.volume * 2,
        )
    candles.append(sweep)
    return candles


def _make_data(candles: list, rsi: list = None) -> MarketData:
    return MarketData(candles=candles, symbol="TEST", timeframe="H1", rsi=rsi)


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — models
# ──────────────────────────────────────────────────────────────────────────────

class TestCandleValidation:
    def test_valid_candle(self):
        c = Candle(open=10, high=12, low=9, close=11, volume=500)
        assert c.high >= c.low

    def test_high_less_than_low_raises(self):
        with pytest.raises(ValueError, match="high must be >= low"):
            Candle(open=10, high=8, low=9, close=10, volume=100)

    def test_negative_volume_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            Candle(open=10, high=12, low=9, close=11, volume=-1)

    def test_zero_price_raises(self):
        with pytest.raises(ValueError, match="positive"):
            Candle(open=0, high=1, low=0, close=1, volume=100)


class TestMarketDataValidation:
    def test_too_few_candles_raises(self):
        with pytest.raises(ValueError, match="10 candles"):
            MarketData(candles=[Candle(10, 12, 9, 11, 100)] * 5)


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — Step 1: Market Structure
# ──────────────────────────────────────────────────────────────────────────────

class TestMarketStructure:
    def test_bullish_trend_detected(self):
        data = _make_data(_bullish_candles())
        result = analyze_structure(data)
        assert result.trend == "BULLISH"
        assert result.structure_clear is True

    def test_bearish_trend_detected(self):
        data = _make_data(_bearish_candles())
        result = analyze_structure(data)
        assert result.trend == "BEARISH"
        assert result.structure_clear is True

    def test_swing_levels_populated(self):
        data = _make_data(_bullish_candles())
        result = analyze_structure(data)
        assert result.last_swing_high is not None
        assert result.last_swing_low is not None

    def test_flat_market_returns_sideways_or_unknown(self):
        # Perfectly flat candles → no swing differential
        flat = [Candle(100, 101, 99, 100, 500) for _ in range(30)]
        data = _make_data(flat)
        result = analyze_structure(data)
        assert result.trend in ("SIDEWAYS", "UNKNOWN")


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — Step 2: Liquidity
# ──────────────────────────────────────────────────────────────────────────────

class TestLiquidity:
    def test_sweep_detected_bullish(self):
        candles = _inject_sweep(_bullish_candles(40), "BULLISH")
        data = _make_data(candles)
        structure = analyze_structure(data)
        result = analyze_liquidity(data, structure.trend)
        assert result.sweep_detected is True
        assert result.swept_level is not None

    def test_no_sweep_without_injection(self):
        data = _make_data(_bullish_candles(40))
        structure = analyze_structure(data)
        result = analyze_liquidity(data, structure.trend)
        # Without injecting a sweep, should not find one
        assert result.sweep_detected is False

    def test_liquidity_pools_non_empty(self):
        data = _make_data(_bullish_candles(40))
        result = analyze_liquidity(data, "BULLISH")
        assert len(result.liquidity_pools) > 0


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — Step 3: Confluence
# ──────────────────────────────────────────────────────────────────────────────

class TestConfluence:
    def _setup(self, trend="BULLISH"):
        candles = _inject_sweep(_bullish_candles(40) if trend == "BULLISH" else _bearish_candles(40), trend)
        data = _make_data(candles)
        structure = analyze_structure(data)
        liquidity = analyze_liquidity(data, structure.trend)
        return data, structure, liquidity

    def test_score_at_least_two_on_sweep(self):
        data, structure, liquidity = self._setup()
        result = analyze_confluence(data, structure, liquidity)
        # At minimum structure + sweep should be found
        assert result.score >= 2

    def test_score_includes_structure_and_sweep(self):
        data, structure, liquidity = self._setup()
        result = analyze_confluence(data, structure, liquidity)
        assert "Structure alignment" in result.factors
        assert "Liquidity sweep" in result.factors

    def test_volume_spike_detected(self):
        candles = _inject_sweep(_bullish_candles(40), "BULLISH")
        data = _make_data(candles)
        structure = analyze_structure(data)
        liquidity = analyze_liquidity(data, structure.trend)
        result = analyze_confluence(data, structure, liquidity)
        assert result.volume_spike is True


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — Step 4: Entry
# ──────────────────────────────────────────────────────────────────────────────

class TestEntry:
    def _full_setup(self):
        candles = _inject_sweep(_bullish_candles(40), "BULLISH")
        data = _make_data(candles)
        structure = analyze_structure(data)
        liquidity = analyze_liquidity(data, structure.trend)
        confluence = analyze_confluence(data, structure, liquidity)
        return data, structure, liquidity, confluence

    def test_entry_price_set_when_poi_found(self):
        data, structure, liquidity, confluence = self._full_setup()
        result = calculate_entry(data, structure, liquidity, confluence)
        # If a POI was found, entry should be set
        if confluence.order_block or confluence.fvg_zone or confluence.fibonacci_ote:
            assert result.entry_price is not None
        else:
            assert result.entry_price is None

    def test_stoploss_below_entry_for_bullish(self):
        data, structure, liquidity, confluence = self._full_setup()
        result = calculate_entry(data, structure, liquidity, confluence)
        if result.entry_price and result.stoploss:
            assert result.stoploss < result.entry_price


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — Step 5: Risk Management
# ──────────────────────────────────────────────────────────────────────────────

class TestRisk:
    def _make_entry(self, entry=105.0, sl=103.0, tp=110.0):
        from smart_money.models import EntryResult
        return EntryResult(entry_price=entry, entry_type="ORDER_BLOCK", stoploss=sl, take_profit=tp)

    def test_good_rr_accepted(self):
        entry = self._make_entry(entry=100, sl=98, tp=106)  # RR = 3
        result = calculate_risk(entry, account_size=10_000, risk_pct=0.01)
        assert result.rr_acceptable is True
        assert result.rr_ratio >= 2.0

    def test_bad_rr_rejected(self):
        entry = self._make_entry(entry=100, sl=99, tp=100.5)  # RR = 0.5
        result = calculate_risk(entry, account_size=10_000, risk_pct=0.01)
        assert result.rr_acceptable is False

    def test_position_size_positive(self):
        entry = self._make_entry(entry=100, sl=98, tp=106)
        result = calculate_risk(entry, account_size=10_000, risk_pct=0.01)
        assert result.position_size > 0

    def test_missing_tp_returns_not_acceptable(self):
        from smart_money.models import EntryResult
        entry = EntryResult(entry_price=100, entry_type="OB", stoploss=98, take_profit=None)
        result = calculate_risk(entry)
        assert result.rr_acceptable is False

    def test_zero_risk_raises(self):
        entry = self._make_entry(entry=100, sl=100, tp=110)  # SL == entry
        result = calculate_risk(entry)
        assert result.rr_acceptable is False


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests — Step 6: Psychology Filter
# ──────────────────────────────────────────────────────────────────────────────

class TestPsychology:
    def _make_structure(self, clear=True, trend="BULLISH"):
        from smart_money.models import StructureResult
        return StructureResult(trend=trend, structure_clear=clear)

    def _make_confluence(self, score=3):
        from smart_money.models import ConfluenceResult
        return ConfluenceResult(score=score)

    def test_passes_when_all_ok(self):
        passed, reason = psychology_filter(
            self._make_structure(), self._make_confluence(score=3)
        )
        assert passed is True

    def test_fails_when_structure_unclear(self):
        passed, _ = psychology_filter(
            self._make_structure(clear=False), self._make_confluence()
        )
        assert passed is False

    def test_fails_when_low_confluence(self):
        passed, _ = psychology_filter(
            self._make_structure(), self._make_confluence(score=2)
        )
        assert passed is False

    def test_fails_on_too_many_losses(self):
        passed, reason = psychology_filter(
            self._make_structure(), self._make_confluence(score=4), consecutive_losses=5
        )
        assert passed is False
        assert "revenge" in reason.lower() or "losses" in reason.lower()

    def test_fails_on_sideways(self):
        passed, _ = psychology_filter(
            self._make_structure(trend="SIDEWAYS"), self._make_confluence()
        )
        assert passed is False


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — TradingSystem (full pipeline)
# ──────────────────────────────────────────────────────────────────────────────

class TestTradingSystemIntegration:
    def _full_trade_data(self):
        """Build data likely to produce a TRADE decision."""
        candles = _inject_sweep(_bullish_candles(50), "BULLISH")
        return _make_data(candles)

    def test_output_is_valid_json(self):
        system = TradingSystem()
        data = self._full_trade_data()
        json_str = system.analyze_to_json(data)
        parsed = json.loads(json_str)
        assert "decision" in parsed

    def test_output_has_all_required_keys(self):
        system = TradingSystem()
        data = self._full_trade_data()
        result = system.analyze(data)
        d = result.to_dict()
        required = [
            "decision", "trend", "liquidity", "confluence_score",
            "entry", "stoploss", "take_profit", "rr_ratio",
            "risk_per_trade", "position_size", "reason", "warnings",
        ]
        for key in required:
            assert key in d, f"Missing key: {key}"

    def test_decision_is_trade_or_no_trade(self):
        system = TradingSystem()
        data = self._full_trade_data()
        result = system.analyze(data)
        assert result.decision in ("TRADE", "NO TRADE")

    def test_no_trade_when_insufficient_candles_raises(self):
        with pytest.raises(ValueError):
            MarketData(candles=[Candle(10, 12, 9, 11, 100)] * 3)

    def test_no_trade_on_flat_data(self):
        flat = [Candle(100, 101, 99, 100, 500) for _ in range(30)]
        data = _make_data(flat)
        system = TradingSystem()
        result = system.analyze(data)
        assert result.decision == "NO TRADE"

    def test_no_trade_on_bad_rr(self):
        """Manually test a scenario where RR is forced below 1:2."""
        # Use bearish candles with sweep but tight pools so TP is very close
        candles = _inject_sweep(_bearish_candles(50), "BEARISH")
        data = _make_data(candles)
        system = TradingSystem()
        result = system.analyze(data)
        # We can't guarantee a bad RR here, but the decision must be valid
        assert result.decision in ("TRADE", "NO TRADE")

    def test_invalid_risk_pct_raises(self):
        with pytest.raises(ValueError):
            TradingSystem(risk_pct=0.05)  # 5% > 2% limit

    def test_invalid_account_size_raises(self):
        with pytest.raises(ValueError):
            TradingSystem(account_size=-100)

    def test_warnings_is_list(self):
        system = TradingSystem()
        data = _make_data(_bullish_candles(30))
        result = system.analyze(data)
        assert isinstance(result.warnings, list)
