"""Scheduler: periodic Master Data Agent runs with alert on decision flip.

On each cycle:
  1. For each asset in `assets`: run master_agent.run(asset=...).
  2. Compare against last decision stored in state file.
  3. If decision flipped NO_TRADE -> TRADE, OR direction changed while
     TRADE, send an alert via alerts.dispatch (Telegram/Discord/email).
  4. Persist state.

Designed to run as a long-lived process (`--loop`) or once per cron tick
(`--once`).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from . import alerts, master_agent


DEFAULT_STATE = Path("reports/scheduler/state.json")


@dataclass
class AlertEvent:
    asset: str
    previous_decision: str
    new_decision: str
    direction: str
    confluence_score: int
    reason: str


def _format_alert(sig, event: AlertEvent) -> tuple[str, str]:
    subject = f"[{event.asset}/USDT] {event.previous_decision} → {event.new_decision} ({event.direction.upper()}, {event.confluence_score}/12)"
    lines = [
        f"Asset: {event.asset}/USDT",
        f"Flip: {event.previous_decision} → {event.new_decision}",
        f"Reason: {event.reason}",
        "",
        f"Decision : {sig.decision}",
        f"Direction: {sig.direction}",
        f"Entry    : {sig.entry}",
        f"Stop     : {sig.stop}",
        f"TP1      : {sig.tp1}",
        f"TP2      : {sig.tp2}",
        f"RR(TP1)  : {sig.rr}",
        f"Confluence: {sig.confluence_score}/12",
        f"Bias HTF : {sig.bias_htf} — {sig.bias_reason}",
        f"{sig.macro_kind if hasattr(sig, 'macro_kind') else 'MVRV'}: {sig.mvrv_value} ({sig.mvrv_regime})",
        "",
        f"As of: {sig.as_of}",
    ]
    return subject, "\n".join(lines)


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {"last": {}}
    with path.open() as f:
        return json.load(f)


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(state, f, indent=2, default=float)


def _run_agent(asset: str):
    try:
        return master_agent.run(asset=asset)  # type: ignore[call-arg]
    except TypeError:
        # pre-multi-asset master_agent
        if asset != "BTC":
            return None
        return master_agent.run()


def tick(assets: list[str], state_path: Path = DEFAULT_STATE,
         env: dict | None = None) -> list[AlertEvent]:
    """Run one cycle. Returns list of events that triggered alerts."""
    state = _load_state(state_path)
    last = state.get("last", {})
    fired: list[AlertEvent] = []
    for asset in assets:
        sig = _run_agent(asset)
        if sig is None:
            continue
        prev = last.get(asset, {})
        prev_dec = prev.get("decision", "UNKNOWN")
        prev_dir = prev.get("direction", "none")
        evt = None
        if prev_dec != "TRADE" and sig.decision == "TRADE":
            evt = AlertEvent(asset=asset, previous_decision=prev_dec,
                             new_decision=sig.decision, direction=sig.direction,
                             confluence_score=sig.confluence_score,
                             reason="NO_TRADE -> TRADE (confluence gate passed)")
        elif prev_dec == "TRADE" and sig.decision == "TRADE" and prev_dir != sig.direction:
            evt = AlertEvent(asset=asset, previous_decision=prev_dec,
                             new_decision=sig.decision, direction=sig.direction,
                             confluence_score=sig.confluence_score,
                             reason=f"direction flipped {prev_dir} -> {sig.direction}")
        if evt is not None:
            subject, body = _format_alert(sig, evt)
            result = alerts.dispatch(subject, body, env=env)
            fired.append(evt)
            last[asset] = {"decision": sig.decision, "direction": sig.direction,
                           "ts": int(time.time()), "last_alert": result.summary()}
        else:
            last[asset] = {"decision": sig.decision, "direction": sig.direction,
                           "ts": int(time.time())}
    state["last"] = last
    state["last_tick_ts"] = int(time.time())
    _save_state(state_path, state)
    return fired


def run_loop(assets: list[str], interval: int,
             state_path: Path = DEFAULT_STATE) -> None:
    print(f"[scheduler] assets={assets} interval={interval}s state={state_path}")
    while True:
        try:
            fired = tick(assets, state_path)
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            print(f"[scheduler {ts}] fired={len(fired)} alerts")
            for e in fired:
                print(f"  -> {e.asset}: {e.previous_decision}->{e.new_decision} {e.direction} ({e.reason})")
        except Exception as ex:
            print(f"[scheduler] tick error: {ex!r}")
        time.sleep(interval)
