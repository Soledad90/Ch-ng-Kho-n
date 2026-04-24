"""CLI: python -m agents.run_backtest [--max-hold N] [--min-score N] [--rr N]"""
from __future__ import annotations

import argparse
from dataclasses import asdict

from .backtest import run_backtest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max-hold", type=int, default=20,
                   help="Max bars to hold a trade (default 20)")
    p.add_argument("--min-score", type=int, default=5,
                   help="Minimum confluence score out of 8 (default 5)")
    p.add_argument("--rr", type=float, default=2.0,
                   help="Minimum RR(TP1) (default 2.0)")
    p.add_argument("--cooldown", type=int, default=3,
                   help="Bars to skip after exit (default 3)")
    p.add_argument("--no-save", action="store_true")
    args = p.parse_args()

    stats, trades = run_backtest(
        max_hold=args.max_hold,
        confluence_min=args.min_score,
        rr_min=args.rr,
        cooldown_bars=args.cooldown,
        out_dir=None if args.no_save else "reports/backtest",
    )
    print(f"\n=== Backtest BTC/USDT D1 ===")
    print(f"  max_hold={args.max_hold} bars | confluence>={args.min_score}/8 | RR>={args.rr}")
    for k, v in asdict(stats).items():
        print(f"  {k:22s} {v}")
    if trades:
        print(f"\n  First trade: {trades[0]}")
        print(f"  Last trade : {trades[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
