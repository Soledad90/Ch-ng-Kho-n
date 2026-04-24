"""
Step 6 — Psychology Filter
Prevents low-quality or emotion-driven trades.

Rules:
  - No FOMO (setup must be clear and pre-planned)
  - No revenge trading (no multiple consecutive losses in context)
  - No weak signals (confluence score must be sufficient)
  - No ambiguous setups (trend must be clear)
"""

from .models import StructureResult, ConfluenceResult

_MIN_CONFLUENCE_FOR_CLEAR_SETUP = 3


def psychology_filter(
    structure: StructureResult,
    confluence: ConfluenceResult,
    consecutive_losses: int = 0,
) -> tuple:
    """
    STEP 6 — Apply psychology filter.

    Parameters
    ----------
    structure          : Result from Step 1
    confluence         : Result from Step 3
    consecutive_losses : Number of consecutive losses (supplied externally; default 0)

    Returns
    -------
    (passed: bool, reason: str)
    """
    warnings = []

    # Check 1: Setup clarity — trend must be unambiguous
    if not structure.structure_clear:
        return False, "Setup unclear — trend cannot be determined (FOMO prevention)."

    # Check 2: Weak signal — confluence too low
    if confluence.score < _MIN_CONFLUENCE_FOR_CLEAR_SETUP:
        return (
            False,
            f"Weak signal — confluence score {confluence.score} < {_MIN_CONFLUENCE_FOR_CLEAR_SETUP} (no trade).",
        )

    # Check 3: Revenge trading guard — skip if too many consecutive losses
    if consecutive_losses >= 3:
        warnings.append(
            f"Caution: {consecutive_losses} consecutive losses detected — review strategy before trading."
        )
        if consecutive_losses >= 5:
            return False, "Revenge trading risk — too many consecutive losses. Take a break."

    # Check 4: Sideways market — avoid choppy conditions
    if structure.trend == "SIDEWAYS":
        return False, "Market is sideways — setup not clear enough (FOMO prevention)."

    reason = "Psychology filter passed."
    if warnings:
        reason += " Warnings: " + "; ".join(warnings)

    return True, reason
