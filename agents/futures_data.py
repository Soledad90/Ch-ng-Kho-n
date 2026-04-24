"""Futures microstructure data — Funding Rate, Open Interest, Long/Short ratio,
recent Liquidations.

Source: OKX public REST API (no key required, no geo block observed).
All timestamps are milliseconds (OKX convention) -> converted to seconds.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Literal

from .data_sources import _http_json


INST = "BTC-USDT-SWAP"
ULY = "BTC-USDT"


@dataclass
class FundingPoint:
    ts: int          # unix seconds
    rate: float      # per-interval (8h). Annualised = rate * 3 * 365


@dataclass
class OIPoint:
    ts: int
    oi_usd: float    # aggregate USD notional


@dataclass
class LiquidationEvent:
    ts: int
    side: Literal["long", "short"]   # side that got liquidated
    price: float
    size: float                      # contracts (OKX SWAP is 0.01 BTC per contract)


# -------------------------------------------------------------------------
# Funding Rate
# -------------------------------------------------------------------------

def fetch_funding_rate(limit: int = 20) -> tuple[float, list[FundingPoint]]:
    """Return (current_rate_per_period, history_list). Rate is the 8h funding."""
    cur = _http_json(f"https://www.okx.com/api/v5/public/funding-rate?instId={INST}")
    rate = float(cur["data"][0]["fundingRate"])
    hist = _http_json(
        f"https://www.okx.com/api/v5/public/funding-rate-history"
        f"?instId={INST}&limit={limit}"
    )
    points = [
        FundingPoint(int(d["fundingTime"]) // 1000, float(d["realizedRate"]))
        for d in hist["data"]
    ]
    points.reverse()  # oldest first
    return rate, points


# -------------------------------------------------------------------------
# Open Interest
# -------------------------------------------------------------------------

def fetch_open_interest(period: str = "1H", limit: int = 100) -> list[OIPoint]:
    """OI history via rubik stat. Returns list oldest -> newest.

    OKX returns [ts_ms, oi_usd_total, vol_usd_total]."""
    d = _http_json(
        f"https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume"
        f"?ccy=BTC&period={period}&limit={limit}"
    )
    rows = list(d["data"])
    rows.reverse()
    return [OIPoint(int(r[0]) // 1000, float(r[1])) for r in rows]


# -------------------------------------------------------------------------
# Long/Short account ratio
# -------------------------------------------------------------------------

def fetch_long_short_ratio(period: str = "1H", limit: int = 50) -> list[tuple[int, float]]:
    """Return (ts_s, ratio) pairs, oldest first. ratio = long_accounts / short_accounts."""
    d = _http_json(
        f"https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio"
        f"?ccy=BTC&period={period}&limit={limit}"
    )
    rows = list(d["data"])
    rows.reverse()
    return [(int(r[0]) // 1000, float(r[1])) for r in rows]


# -------------------------------------------------------------------------
# Recent Liquidations
# -------------------------------------------------------------------------

def fetch_liquidations(limit: int = 100) -> list[LiquidationEvent]:
    """Last ~100 filled liquidation orders on BTC-USDT swap."""
    d = _http_json(
        f"https://www.okx.com/api/v5/public/liquidation-orders"
        f"?instType=SWAP&uly={ULY}&state=filled&limit={limit}"
    )
    out: list[LiquidationEvent] = []
    for pkg in d.get("data", []):
        for ev in pkg.get("details", []):
            out.append(LiquidationEvent(
                ts=int(ev["ts"]) // 1000,
                side="long" if ev.get("posSide") == "long" else "short",
                price=float(ev["bkPx"]),
                size=float(ev["sz"]),
            ))
    return out


def liquidation_heatmap(events: list[LiquidationEvent], bins: int = 40) -> dict:
    """Bucket liquidations into price bins and tag nearest cluster on each side.

    Returns {bins: [(lo, hi, long_sz, short_sz)], max_bin_price, poc_long, poc_short}
    where poc_long = price bin with max liquidated *long* size (i.e. downside
    magnet) and poc_short similar for upside magnet.
    """
    if not events:
        return {"bins": [], "poc_long": None, "poc_short": None, "total": 0}
    prices = [e.price for e in events]
    lo, hi = min(prices), max(prices)
    if hi <= lo:
        hi = lo * 1.001
    step = (hi - lo) / bins
    long_b = [0.0] * bins
    short_b = [0.0] * bins
    for e in events:
        idx = min(int((e.price - lo) / step), bins - 1)
        if e.side == "long":
            long_b[idx] += e.size
        else:
            short_b[idx] += e.size
    bin_list = [(lo + i * step, lo + (i + 1) * step, long_b[i], short_b[i])
                for i in range(bins)]
    # POC (max liquidated size) per side
    poc_long_i = max(range(bins), key=lambda i: long_b[i])
    poc_short_i = max(range(bins), key=lambda i: short_b[i])

    def _mid(i: int) -> float:
        return (bin_list[i][0] + bin_list[i][1]) / 2

    return {
        "bins": bin_list,
        "poc_long": _mid(poc_long_i) if long_b[poc_long_i] > 0 else None,
        "poc_short": _mid(poc_short_i) if short_b[poc_short_i] > 0 else None,
        "total": sum(long_b) + sum(short_b),
        "total_long": sum(long_b),
        "total_short": sum(short_b),
    }


if __name__ == "__main__":
    import json
    cur, fhist = fetch_funding_rate(10)
    oi = fetch_open_interest("1H", 24)
    lsr = fetch_long_short_ratio("1H", 24)
    liq = fetch_liquidations(100)
    heat = liquidation_heatmap(liq, bins=20)
    print(json.dumps({
        "funding_current": cur,
        "funding_latest_hist": fhist[-3:] if fhist else [],
        "oi_latest": oi[-3:] if oi else [],
        "ls_ratio_latest": lsr[-3:] if lsr else [],
        "liq_count": len(liq),
        "liq_total_long": heat["total_long"],
        "liq_total_short": heat["total_short"],
        "liq_poc_long": heat["poc_long"],
        "liq_poc_short": heat["poc_short"],
    }, default=lambda o: o.__dict__, indent=2))
