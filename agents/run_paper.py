"""CLI: python -m agents.run_paper --assets BTC

One invocation = one paper-trading tick. Designed for cron/systemd:
  */15 * * * * cd /path/to/repo && python -m agents.run_paper --assets BTC
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .paper_trader import DEFAULT_DIR, tick, load_state, buyhold_pct


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--assets", default="BTC",
                   help="Comma-separated: BTC,ETH,SOL (default BTC)")
    p.add_argument("--risk", type=float, default=1.0,
                   help="Risk per trade % of equity (default 1.0)")
    p.add_argument("--timeframe", default="15m",
                   help="Exit-check timeframe (default 15m)")
    p.add_argument("--dir", default=str(DEFAULT_DIR),
                   help="State/trades output directory")
    p.add_argument("--summary", action="store_true",
                   help="Print summary and exit (no tick)")
    args = p.parse_args(argv)

    out_dir = Path(args.dir)
    assets = [a.strip().upper() for a in args.assets.split(",") if a.strip()]

    if args.summary:
        state = load_state(out_dir)
        print_summary(state)
        return 0

    diff = tick(assets=assets, risk_pct=args.risk, out_dir=out_dir,
                timeframe=args.timeframe)

    print(f"Tick @ assets={assets}")
    print(f"  opened : {len(diff['opened'])}")
    for o in diff["opened"]:
        print(f"    + {o['asset']} {o['direction']} entry={o['entry']:.2f} "
              f"SL={o['stop']:.2f} TP1={o['tp1']:.2f} conf={o['confluence_score']}/12")
    print(f"  closed : {len(diff['closed'])}")
    for c in diff["closed"]:
        print(f"    - {c['asset']} {c['direction']} exit={c['exit_price']:.2f} "
              f"reason={c['exit_reason']} R={c['r_multiple']} pnl={c['pnl_pct']}%")
    print(f"  equity : ${diff['equity']}")
    return 0


def print_summary(state: dict) -> None:
    n_closed = len(state["closed_trades"])
    n_open = len(state["open_positions"])
    print(f"Starting equity : ${state['starting_equity']:.2f}")
    print(f"Current  equity : ${state['equity']:.2f}")
    total_ret = (state["equity"] - state["starting_equity"]) / state["starting_equity"] * 100
    print(f"Total return    : {total_ret:+.2f}%")
    print(f"Closed trades   : {n_closed}")
    print(f"Open positions  : {n_open}")
    if n_closed:
        wins = sum(1 for t in state["closed_trades"] if t["r_multiple"] > 0)
        rs = [t["r_multiple"] for t in state["closed_trades"]]
        avg_r = sum(rs) / len(rs)
        print(f"Win rate        : {wins/n_closed*100:.1f}%")
        print(f"Avg R           : {avg_r:+.2f}")
        # buyhold comparison from earliest open_ts
        earliest = min(t["open_ts"] for t in state["closed_trades"])
        assets_traded = sorted({t["asset"] for t in state["closed_trades"]})
        print(f"\nBuy-and-hold since {earliest} (unix):")
        for a in assets_traded:
            bh = buyhold_pct(a, earliest)
            if bh is not None:
                print(f"  {a}: {bh:+.2f}%")
    for o in state["open_positions"]:
        print(f"\nOpen: {o['asset']} {o['direction']} entry={o['entry']:.2f} "
              f"SL={o['stop']:.2f} TP1={o['tp1']:.2f}")


if __name__ == "__main__":
    raise SystemExit(main())
