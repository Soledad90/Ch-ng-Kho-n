"""CLI entrypoint: run all agents -> print + save report.

Usage:
    python -m agents.run                       # 1d, save reports/
    python -m agents.run --tf 4h
    python -m agents.run --no-save             # print only
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import mvrv_agent, ta_agent, report
from .orchestrator import plan as make_plan


REPORTS = Path(__file__).resolve().parent.parent / "reports"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tf", default="1d", choices=["1d", "4h", "1h"],
                    help="timeframe for TA agent (default: 1d)")
    ap.add_argument("--no-save", action="store_true",
                    help="do not write files under reports/")
    ap.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    args = ap.parse_args(argv)

    mvrv = mvrv_agent.run()
    ta = ta_agent.run(args.tf)
    plan = make_plan(mvrv, ta)

    md = report.to_markdown(mvrv, ta, plan)
    js = report.to_json(mvrv, ta, plan)

    if args.json:
        print(js)
    else:
        print(md)

    if not args.no_save:
        md_p, js_p = report.save(md, js, REPORTS, f"BTCUSDT_{args.tf}")
        print(f"\nSaved: {md_p}\n       {js_p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
