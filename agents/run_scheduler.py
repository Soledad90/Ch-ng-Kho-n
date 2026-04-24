"""CLI: python -m agents.run_scheduler [--once | --loop] [--interval 900] [--assets BTC,ETH,SOL]"""
from __future__ import annotations

import argparse
from pathlib import Path

from .scheduler import DEFAULT_STATE, run_loop, tick


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assets", default="BTC",
                   help="Comma-separated asset list (default BTC)")
    p.add_argument("--interval", type=int, default=900,
                   help="Seconds between ticks in loop mode (default 900 = 15m)")
    p.add_argument("--once", action="store_true",
                   help="Run a single tick and exit (for cron)")
    p.add_argument("--loop", action="store_true",
                   help="Run forever, sleeping --interval between ticks")
    p.add_argument("--state", default=str(DEFAULT_STATE),
                   help="State file path")
    p.add_argument("--test-alert", action="store_true",
                   help="Send a test alert through all configured channels and exit")
    args = p.parse_args(argv)

    assets = [a.strip().upper() for a in args.assets.split(",") if a.strip()]
    state = Path(args.state)

    if args.test_alert:
        from . import alerts as al
        r = al.dispatch(
            subject="[Master Data Agent] test alert",
            body="If you see this, your alert channels work!\n"
                 "Configure TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / "
                 "DISCORD_WEBHOOK_URL / SMTP_* env vars.",
        )
        print(r.summary())
        return 0 if r.any_ok() else 2

    if args.once or not args.loop:
        fired = tick(assets, state)
        print(f"tick fired {len(fired)} alerts")
        for e in fired:
            print(f"  - {e.asset}: {e.previous_decision}->{e.new_decision} {e.direction}")
        return 0

    run_loop(assets, args.interval, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
