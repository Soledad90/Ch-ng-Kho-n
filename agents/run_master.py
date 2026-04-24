"""CLI entrypoint for the Master Data Agent (AGENT.md mapping).

Usage:
    python -m agents.run_master                      # default: risk=1.0%
    python -m agents.run_master --risk 2.0           # 2% risk
    python -m agents.run_master --no-save            # stdout only
    python -m agents.run_master --json               # emit JSON
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import master_agent, master_report


REPORTS = Path(__file__).resolve().parent.parent / "reports"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--risk", type=float, default=1.0,
                    help="risk per trade in %% of equity (AGENT.md caps at 2.0)")
    ap.add_argument("--asset", choices=["BTC", "ETH", "SOL"], default="BTC",
                    help="asset to analyse (default BTC)")
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    sig = master_agent.run(risk_pct=args.risk, asset=args.asset)
    md = master_report.to_markdown(sig)
    js = master_report.to_json(sig)

    print(js if args.json else md)

    if not args.no_save:
        md_p, js_p = master_report.save(md, js, REPORTS, asset=args.asset)
        print(f"\nSaved: {md_p}\n       {js_p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
