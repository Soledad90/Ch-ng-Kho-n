# Crypto Trading System (`Soledad90/Ch-ng-Kho-n`)

A disciplined, deterministic, **stdlib-only** crypto trading workbench for BTC/USDT (with ETH/SOL extensions for multi-asset). Every component is rule-based — no LLM, no `pandas`/`numpy`, no third-party deps. The North Star is `AGENT.md`'s rule: **trade is an edge of probability × RR × discipline, never of emotion**.

This is the single authoritative reference. Read this whole file before doing anything in the repo.

---

## 0. Hard rules (from `AGENT.md`)

- Confluence Matrix ≥ threshold before any trade (currently ≥ 7/12 base, or ≥ 8/14 when full Coinglass).
- Risk ≤ 1–2% per trade. **RR ≥ 1:2** is a hard stop.
- Never trade against HTF bias (W1/D1/H4) without a confirmed CHoCH on M15/M5.
- Daily/weekly drawdown circuit-breakers: −3%/day or −5%/week → STOP.
- No FOMO, no revenge trades, no leverage ≥ 50x.
- Output must follow `AGENT.md` Section 4 schema: bias / POI / scenario A / invalidation / execution / confluence scorecard / risk plan.

The webapp's `decision_augmented` and `confluence_score_total` JSON fields **are** the machine encoding of this discipline — never bypass them.

---

## 1. Architecture

```
                    ┌──────────────────────────────┐
                    │   master_agent.run()         │
                    │   12-factor Confluence       │
                    │   bias / POI / TP1 / TP2 / RR│
                    └─────────┬──────────────────┘
             ┌──────────┼───────────────────────┐
             ▼                                            ▼
   ┌────────────────┐    ┌───────────────┐    ┌──────────────┐
   │ ta_agent.py     │    │ mvrv_agent.py │    │ futures_data │
   │ (Kraken OHLC,  │    │ (5562 daily  │    │ (OKX public:│
   │  D1/H4/H1/M15) │    │  rows of MVRV)│   │  funding/OI/│
   │  EMA/RSI/MACD/ │    │  Discount/Hot │    │  liq events) │
   │  Ichimoku/Fib/ │    │  regime + size│   └──────────────┘
   │  S/R/VP/FVG/OB │    │  multiplier   │
   └────────────────┘    └───────────────┘
```

**Augmented (webapp only)**: Coinglass v3 adds 2 extra factors (multi-exchange funding consensus + liquidation magnet within 5%) on top of the 12 base factors. Gate becomes 8/14 when both are evaluable; otherwise falls back to 7/12 — **never stricter than `master_agent` alone**.

## 2. The Confluence Matrix (12 base + 2 augmented)

| # | Factor | Source | Pass when... |
|--:|---|---|---|
| 1 | HTF bias D1/H4/W1 | `ta_agent` | EMA + structure agree with trade direction |
| 2 | POI (OB / FVG / Premium-Discount) hit | `indicators.detect_*` | Price at unmitigated POI |
| 3 | Liquidity sweep (EQH/EQL or prior swing) | `master_agent` | Recent wick swept obvious liquidity |
| 4 | M15/M5 CHoCH | `master_agent` | Counter-direction CHoCH after sweep |
| 5 | Fib OTE 0.618–0.79 | `indicators.fib_levels` | Entry inside OTE band |
| 6 | Volume Profile (POC / VAH / VAL) | `indicators.volume_profile` | POC/HVN aligns with entry |
| 7 | Momentum (RSI / Stoch / MACD) | `indicators.*` | Divergence or exit-of-extreme aligned |
| 8 | Kill zone / session | `master_agent` | London or NY open, not Asia dead hours |
| 9 | Funding regime (OKX) | `futures_data.funding` | Crowd opposite to trade direction |
| 10 | OI divergence | `futures_data.oi` | OI rising into trade direction |
| 11 | OB / FVG (3-candle ICT) | `indicators.detect_fvg/ob` | Setup candle pattern present |
| 12 | MVRV regime | `mvrv_agent` | Macro tailwind (Discount→bullish, Hot→bearish) |
| 13 | Funding consensus multi-exchange | Coinglass | Median funding opposite to trade direction |
| 14 | Liquidation magnet within 5% | Coinglass heatmap | Big magnet ahead in trade direction |

Factors 13–14 only count when their underlying source returned data (`evaluable=True`). When unavailable, `confluence_max` falls back to 12 and the gate to 7.

## 3. CLI entry points

| Purpose | Command | Output |
|---|---|---|
| One-shot decision | `python -m agents.run_master` | `reports/YYYY-MM-DD_BTCUSDT_MASTER.md` + JSON |
| Live webapp (TA+MVRV+Coinglass) | `python -m agents.run_webapp --port 8889` | http://127.0.0.1:8889 |
| Forward paper-trading sim | `python -m agents.run_paper` | `state.json` + `paper_log.csv` |
| Backtest 720-bar D1 | `python -m agents.run_backtest` | win-rate / RR / max-DD stats |
| Cron loop + alerts | `python -m agents.run_scheduler` | Telegram / Discord / email on NO_TRADE→TRADE |
| Legacy multi-agent (`PR #5`) | `python -m agents.run --tf 1d` | Markdown + JSON tranche plan |

All commands are stdlib-only. Network calls (Kraken / OKX / Coinglass) go through `urllib.request`; failures degrade gracefully.

## 4. Devin secrets

- `COINGLASS_API_KEY` (org-level secret) — Hobbyist tier or higher needed for liquidation heatmap. Without this, the webapp fully works in **degraded mode**: confluence_max=12, gate=7, and `decision_augmented` matches `decision` (i.e. master_agent verdict). The graceful path is intentional and is exercised by smoke tests.
- Telegram / Discord / SMTP creds for the scheduler are optional and only requested if the user runs `agents.run_scheduler` with live alerts enabled.

## 5. JSON contract — `/api/decision?asset=BTC`

The frontend in `agents/webapp.py` is a **deterministic mapping** of this JSON to DOM. Verifying the JSON shape is strictly more reliable than counting pixels. Adversarial post-condition checks any future change must satisfy:

```python
import json, urllib.request
d = json.loads(urllib.request.urlopen('http://127.0.0.1:8889/api/decision?asset=BTC').read())

# Gate must adapt; never stricter than 7/12 when Coinglass is missing
assert d['confluence_max'] in (12, 13, 14)
assert d['confluence_gate'] in (7, 8)
cg = d['coinglass']
if not (cg['funding']['ok'] and cg['heatmap']['ok']):
    assert d['decision_augmented'] == d['decision']

# Per-source error map (introduced in 2eba5d4) — not a single last_error gate
assert set(cg['errors']) == {'funding', 'liq', 'heatmap', 'sentiment'}

# Each Coinglass extra carries an `evaluable` flag tied to its source
for ex in cg['confluence_extra']:
    assert ex['source'] in ('funding', 'heatmap')
    assert isinstance(ex['evaluable'], bool)

# Other endpoints
assert urllib.request.urlopen('http://127.0.0.1:8889/api/candles?limit=0').read() == b'[]'
```

## 6. Field-name gotchas (DO NOT regress)

- Base `master_agent.ConfluenceItem` — fields `name`, `passed`, **`note`**.
- Coinglass extras (`coinglass_signals.coinglass_confluence`) — fields `name`, `ok`, **`reason`**, `evaluable`, `source`.
- The frontend must read `c.note` for base items and `c.reason` for extras. Reading `c.reason` on a base item yields `undefined` and the Reason column renders blank.
- The frontend must filter Coinglass rows with `c.evaluable` (per-factor), **not** an AND gate `funding.ok && heatmap.ok`. The backend counts `cg_evaluable = int(funding.ok) + int(heatmap.ok)` so 1 ok source must produce 1 visible row, not 0.
- `_client.last_error` is overwritten by every API call. Do **not** gate the whole Coinglass panel on it. Use `coinglass.errors = {funding, liq, heatmap, sentiment}` (per-source snapshot) instead.

## 7. Tests

```bash
python scripts/smoke_test.py   # expect 11/11 (offline, no key, no network)
```

Regression tests already in place:

- `test_webapp_gate_no_coinglass` — stubbed master_agent + no key → gate falls back to 7/12; `decision_augmented` is **not** stricter than base.
- `test_coinglass_extras_partial_evaluability` — only funding (or only heatmap) returns data → corresponding extra has `evaluable=True`, the other has `evaluable=False`.
- The smoke suite is offline (no network, no API key). Adding a network-dependent test is a red flag.

## 8. Webapp testing recipe

```bash
cd ~/repos/Ch-ng-Kho-n
python -m agents.run_webapp --port 8889 > /tmp/webapp.log 2>&1 &
sleep 3
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8889/      # expect 200
curl -s 'http://127.0.0.1:8889/api/decision?asset=BTC' | python3 -m json.tool | head
test "$(curl -s 'http://127.0.0.1:8889/api/candles?asset=BTC&tf=1h&limit=0')" = '[]' && echo PASS
curl -s 'http://127.0.0.1:8889/api/decision?asset=ETH' | grep -q 'not supported' && echo PASS
```

## 9. Known VM caveats

- **Chrome will not launch on the test VM** (`google-chrome` exits with code 7 immediately, no log output, even with `--no-sandbox` / fresh `--user-data-dir` / headless). Do not waste cycles fighting it. Verify webapp behaviour at the JSON layer (above) and re-use the existing `~/screenshots/screenshot_5fb8779573544fef9f1bf96d1e00ef20.png` only as a 🔴 BEFORE reference for the 14/12 + blank-Reason bug.
- If Chrome ever does work, a Playwright script can attach to the existing browser via CDP at `http://localhost:29229` rather than relaunching.
- Repo is stdlib-only: do not introduce `requests`, `pandas`, `numpy`, `httpx`, `aiohttp`, `fastapi`, etc. Use `urllib.request` and hand-rolled JSON.

## 10. File map (open these to review or extend)

- `AGENT.md` — trading discipline (the system prompt; do **not** soften).
- `agents/master_agent.py` — 12-factor Confluence Matrix builder + decision.
- `agents/ta_agent.py` + `agents/indicators.py` — EMA/RSI/MACD/ATR/Ichimoku/Fib/S-R/Volume Profile/FVG/OB.
- `agents/mvrv_agent.py` + `data/mvrv_btc.csv` — macro filter (5562 daily rows, 2011–2026).
- `agents/futures_data.py` — OKX public funding/OI/liq.
- `agents/coinglass_client.py` — stdlib `urllib` Coinglass v3 wrapper, graceful no-key path.
- `agents/coinglass_signals.py` — raw Coinglass → regime/cluster/sentiment dicts; `coinglass_confluence(...)` emits the 2 extras with `evaluable`+`source`.
- `agents/webapp.py` — standalone HTTP server. Watch lines 71–173 (decision builder), 180–199 (`_candles_json` `[-0:]` guard), 332–372 (`renderCoinglass`), 374–392 (`renderConfluence`). These are where every regression Devin Review caught lives.
- `agents/dashboard.py` — separate older dashboard (PR #10). **Not** the same as webapp.
- `agents/paper_trader.py` / `agents/run_paper.py` — stateful forward simulator.
- `agents/backtest.py` / `agents/run_backtest.py` — walk-forward replay.
- `agents/scheduler.py` / `agents/alerts.py` / `agents/run_scheduler.py` — cron loop + alerts.
- `scripts/smoke_test.py` — offline regression suite (must stay 11/11).
- `docs/AGENTS.md`, `docs/MASTER_AGENT.md`, `docs/WEBAPP.md`, `docs/BACKTEST.md`, `docs/PAPER_TRADING.md`, `docs/DASHBOARD.md`, `docs/SCHEDULER.md`, `docs/MULTI_ASSET.md`, `docs/MVRV_Filter.md` — deep docs per subsystem.
