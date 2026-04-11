"""
Smart Money Institutional Trading System — Main Orchestrator
Logic: Structure → Liquidity → Confluence → Execution → Risk → Psychology

Produces a strict JSON-serialisable TradeDecision output.
"""

import json
from typing import Optional

from .models import MarketData, TradeDecision
from .market_structure import analyze_structure
from .liquidity import analyze_liquidity
from .confluence import analyze_confluence
from .entry import calculate_entry
from .risk import calculate_risk
from .psychology import psychology_filter


def _fmt(value: Optional[float]) -> str:
    """Format an optional float for JSON output."""
    if value is None:
        return "[Unverified]"
    return str(round(value, 4))


class TradingSystem:
    """
    Institutional Smart Money Trading System.

    Usage
    -----
    >>> system = TradingSystem(account_size=10_000, risk_pct=0.01)
    >>> decision = system.analyze(market_data)
    >>> print(decision.to_json())
    """

    def __init__(
        self,
        account_size: float = 10_000.0,
        risk_pct: float = 0.01,
        consecutive_losses: int = 0,
    ) -> None:
        if not (0 < risk_pct <= 0.02):
            raise ValueError("risk_pct must be between 0 and 2% (0.0 < risk_pct <= 0.02)")
        if account_size <= 0:
            raise ValueError("account_size must be positive")

        self.account_size = account_size
        self.risk_pct = risk_pct
        self.consecutive_losses = consecutive_losses

    # ------------------------------------------------------------------
    # Verification checklist (per problem statement)
    # ------------------------------------------------------------------
    @staticmethod
    def _verify(structure_clear: bool, sweep: bool, confluence_ok: bool, rr_ok: bool) -> list:
        """Return a list of failed verification checks."""
        checks = []
        if not structure_clear:
            checks.append("Structure NOT clear")
        if not sweep:
            checks.append("Liquidity sweep NOT detected")
        if not confluence_ok:
            checks.append("Confluence < 3")
        if not rr_ok:
            checks.append("RR < 1:2")
        return checks

    # ------------------------------------------------------------------
    # Main analysis pipeline
    # ------------------------------------------------------------------
    def analyze(self, data: MarketData) -> "TradeDecision":
        """
        Run the full 6-step analysis pipeline and return a TradeDecision.

        Parameters
        ----------
        data : MarketData — OHLCV candles + optional indicators
        """
        warnings: list = []

        # ── STEP 1: Market Structure ──────────────────────────────────
        structure = analyze_structure(data)
        if not structure.structure_clear:
            failed = self._verify(False, False, False, False)
            return TradeDecision(
                decision="NO TRADE",
                trend=structure.trend,
                liquidity="[Unverified]",
                confluence_score="[Unverified]",
                reason=f"STEP 1 FAILED — {structure.details}",
                warnings=failed,
            )

        # ── STEP 2: Liquidity Analysis ────────────────────────────────
        liquidity = analyze_liquidity(data, structure.trend)
        if not liquidity.sweep_detected:
            failed = self._verify(True, False, False, False)
            return TradeDecision(
                decision="NO TRADE",
                trend=structure.trend,
                liquidity=liquidity.details,
                confluence_score="[Unverified]",
                reason=f"STEP 2 FAILED — {liquidity.details}",
                warnings=failed,
            )

        # ── STEP 3: Confluence ────────────────────────────────────────
        confluence = analyze_confluence(data, structure, liquidity)
        if confluence.score < 3:
            failed = self._verify(True, True, False, False)
            return TradeDecision(
                decision="NO TRADE",
                trend=structure.trend,
                liquidity=liquidity.details,
                confluence_score=str(confluence.score),
                reason=f"STEP 3 FAILED — {confluence.details}",
                warnings=failed,
            )

        # ── STEP 4: Entry Logic ───────────────────────────────────────
        entry = calculate_entry(data, structure, liquidity, confluence)
        if entry.entry_price is None:
            failed = self._verify(True, True, True, False)
            return TradeDecision(
                decision="NO TRADE",
                trend=structure.trend,
                liquidity=liquidity.details,
                confluence_score=str(confluence.score),
                reason=f"STEP 4 FAILED — {entry.details}",
                warnings=failed,
            )

        # ── STEP 5: Risk Management ───────────────────────────────────
        risk = calculate_risk(entry, self.account_size, self.risk_pct)
        if not risk.rr_acceptable:
            failed = self._verify(True, True, True, False)
            return TradeDecision(
                decision="NO TRADE",
                trend=structure.trend,
                liquidity=liquidity.details,
                confluence_score=str(confluence.score),
                entry=_fmt(entry.entry_price),
                stoploss=_fmt(entry.stoploss),
                take_profit=_fmt(entry.take_profit),
                rr_ratio=_fmt(risk.rr_ratio),
                reason=f"STEP 5 FAILED — RR={risk.rr_ratio} below minimum 1:2. {risk.details}",
                warnings=failed,
            )

        # ── STEP 6: Psychology Filter ─────────────────────────────────
        psych_ok, psych_reason = psychology_filter(
            structure, confluence, self.consecutive_losses
        )
        if not psych_ok:
            return TradeDecision(
                decision="NO TRADE",
                trend=structure.trend,
                liquidity=liquidity.details,
                confluence_score=str(confluence.score),
                entry=_fmt(entry.entry_price),
                stoploss=_fmt(entry.stoploss),
                take_profit=_fmt(entry.take_profit),
                rr_ratio=_fmt(risk.rr_ratio),
                reason=f"STEP 6 FAILED — {psych_reason}",
                warnings=["Psychology filter rejected trade"],
            )

        # ── ALL CHECKS PASSED ─────────────────────────────────────────
        if self.consecutive_losses >= 3:
            warnings.append(
                f"Caution: {self.consecutive_losses} consecutive losses. Proceed with care."
            )

        # Final verification
        failed_checks = self._verify(
            structure.structure_clear,
            liquidity.sweep_detected,
            confluence.score >= 3,
            risk.rr_acceptable,
        )
        if failed_checks:
            # Should not happen at this point, but guard defensively
            return TradeDecision(
                decision="NO TRADE",
                trend=structure.trend,
                liquidity=liquidity.details,
                confluence_score=str(confluence.score),
                reason="Verification failed after all steps.",
                warnings=failed_checks,
            )

        return TradeDecision(
            decision="TRADE",
            trend=structure.trend,
            liquidity=liquidity.details,
            confluence_score=f"{confluence.score}/5 — {', '.join(confluence.factors)}",
            entry=_fmt(entry.entry_price),
            stoploss=_fmt(entry.stoploss),
            take_profit=_fmt(entry.take_profit),
            rr_ratio=f"1:{_fmt(risk.rr_ratio)}",
            risk_per_trade=risk.risk_per_trade,
            position_size=_fmt(risk.position_size),
            reason=f"All conditions met. {psych_reason}",
            warnings=warnings,
        )

    def analyze_to_json(self, data: MarketData) -> str:
        """Convenience method — returns the decision as a formatted JSON string."""
        decision = self.analyze(data)
        return json.dumps(decision.to_dict(), ensure_ascii=False, indent=2)
