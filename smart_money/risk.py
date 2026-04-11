"""
Step 5 — Risk Management
Calculates position size and verifies minimum risk-reward ratio.

Rules:
  - Risk per trade: 1–2 % of account
  - Minimum RR: 1:2
"""

from typing import Optional

from .models import EntryResult, RiskResult

_MIN_RR = 2.0
_DEFAULT_RISK_PCT = 0.01  # 1 %


def calculate_risk(
    entry: EntryResult,
    account_size: float = 10_000.0,
    risk_pct: float = _DEFAULT_RISK_PCT,
) -> RiskResult:
    """
    STEP 5 — Compute RR ratio and position size.

    Parameters
    ----------
    entry        : EntryResult from Step 4
    account_size : Total trading capital (default 10 000 in account currency)
    risk_pct     : Fraction of account to risk (default 1 %)
    """
    if entry.entry_price is None or entry.stoploss is None or entry.take_profit is None:
        return RiskResult(
            rr_acceptable=False,
            details="Missing entry / SL / TP — cannot calculate risk.",
        )

    risk_amount = abs(entry.entry_price - entry.stoploss)
    reward_amount = abs(entry.take_profit - entry.entry_price)

    if risk_amount == 0:
        return RiskResult(
            rr_acceptable=False,
            details="Risk amount is zero — invalid SL placement.",
        )

    rr_ratio = reward_amount / risk_amount
    rr_acceptable = rr_ratio >= _MIN_RR

    # Position size: (account_size × risk_pct) / risk_per_unit
    dollar_risk = account_size * risk_pct
    position_size = dollar_risk / risk_amount

    risk_pct_str = f"{risk_pct * 100:.0f}%"

    details = (
        f"RR: {rr_ratio:.2f} ({'OK' if rr_acceptable else 'BELOW MIN 1:2'}), "
        f"Position size: {round(position_size, 4)} units, "
        f"Dollar risk: {round(dollar_risk, 2)}"
    )

    return RiskResult(
        rr_ratio=round(rr_ratio, 2),
        position_size=round(position_size, 4),
        risk_per_trade=risk_pct_str,
        rr_acceptable=rr_acceptable,
        details=details,
    )
