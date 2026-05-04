# Testing the Decision Engine Webapp (`agents/webapp.py`)

Standalone stdlib `http.server` webapp that combines:

- **Master Data Agent** — TA + MVRV + OKX futures (`agents/master_agent.py`)
- **Coinglass v3 microstructure** — funding, liquidation heatmap, OI, sentiment (`agents/coinglass_*.py`)

Serves a single-page dashboard + JSON API. Default bind `127.0.0.1:8889`.

## Devin Secrets Needed

- `COINGLASS_API_KEY` (org-level secret; Hobbyist tier or higher needed for liquidation heatmap). Without this the Coinglass panels degrade gracefully and the augmented gate falls back to the base 7/12 — the webapp is **fully testable** in degraded mode.

## Run

```bash
cd ~/repos/Ch-ng-Kho-n
python -m agents.run_webapp --port 8889 > /tmp/webapp.log 2>&1 &
sleep 3
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8889/   # expect 200
```

Upstream calls are cached in-process for 30 s.

## Adversarial JSON checks (recommended over visual checks)

The frontend is a pure deterministic mapping of `/api/decision` JSON to DOM, so verifying the JSON shape is strictly more reliable than counting pixels. A useful check set after any change to `webapp._decision`:

```bash
curl -s 'http://127.0.0.1:8889/api/decision?asset=BTC' | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Gate must adapt when Coinglass is unavailable, not stay at 8/14:
assert d['confluence_gate'] in (7, 8), d
assert d['confluence_max'] in (12, 13, 14), d
# Augmented decision must NEVER be stricter than base when Coinglass
# is missing (regression for the bug Devin Review caught on PR #12):
cg = d['coinglass']
if not (cg['funding']['ok'] and cg['heatmap']['ok']):
    assert d['decision_augmented'] == d['decision'], d
print('OK')
"
```

Other one-liners worth running:

```bash
# limit=0 must NOT return all 720 candles (Python's c[-0:] quirk).
test "$(curl -s 'http://127.0.0.1:8889/api/candles?asset=BTC&tf=1h&limit=0')" = '[]' && echo PASS
# Unknown asset must return JSON error, not 500.
curl -s 'http://127.0.0.1:8889/api/decision?asset=ETH' | grep -q 'not supported' && echo PASS
```

## Smoke tests (offline, no network, no key)

```bash
python scripts/smoke_test.py   # expect 10/10
```

Includes `test_webapp_gate_no_coinglass` which stubs `master_agent.run` and asserts the gate falls back to 7/12 when Coinglass is unavailable.

## Field-name gotcha (DO NOT regress)

- Base `master_agent.ConfluenceItem` exposes fields `name`, `passed`, **`note`**.
- Coinglass extras emit `name`, `ok`, **`reason`**.
- The frontend `renderConfluence` JS must read `c.note` for base items and `c.reason` for extras. Reading `c.reason` on base items yields `undefined` and the Reason column renders blank.

## Browser/recording fallback

If Chrome will not launch on the test VM (observed: `google-chrome` exits with code 7 immediately, no log output, even with `--no-sandbox` / fresh `--user-data-dir` / headless), do **not** waste cycles fighting it. The JSON-shape evidence above is sufficient because the frontend is a deterministic mapping. Document this in the test report under "Escalations" and proceed with shell-only assertions.

If Chrome does work, point a CDP-attached Playwright at `http://localhost:29229` to drive it (don't relaunch).

## File map (for adversarial review)

- `agents/webapp.py:71-154` — `_decision()` builder. Watch for hard-coded gate constants.
- `agents/webapp.py:159-178` — `_candles_json()` `[-0:]` guard.
- `agents/webapp.py:344-361` — `renderConfluence` JS. Watch for `c.note` vs `c.reason`.
- `agents/coinglass_signals.py:221-281` — `coinglass_confluence` extras (name/ok/reason).
- `scripts/smoke_test.py` — offline regression suite (no network, no key).
