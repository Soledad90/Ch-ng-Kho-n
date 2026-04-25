"""CLI entry: ``python -m agents.run_webapp [--host H] [--port P]``."""
from __future__ import annotations

import argparse

from . import webapp


def main() -> None:
    p = argparse.ArgumentParser(prog="run_webapp")
    p.add_argument("--host", default="127.0.0.1",
                   help="Bind host (default 127.0.0.1; use 0.0.0.0 to expose).")
    p.add_argument("--port", type=int, default=8889,
                   help="Bind port (default 8889).")
    args = p.parse_args()
    webapp.serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
