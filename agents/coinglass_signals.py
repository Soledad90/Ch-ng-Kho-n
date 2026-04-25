"""Convert raw Coinglass data into trading signals.

The raw shapes returned by ``CoinglassClient`` are useful for charts
but the decision engine wants compact regime labels. This module is
the translator. It only ever returns plain dicts/scalars so the result
can be JSON-serialised straight into webapp responses.

Signals derived:
    - funding_consensus      : multi-exchange funding spread + median regime
    - oi_trend               : rising / falling / flat over last 12 bars
    - liq_pressure           : long_liq_usd vs short_liq_usd over last 24 bars
    - heatmap_clusters       : nearest big magnet above / below current price
    - sentiment              : top-trader long% vs short% (extreme tail flag)

Each signal also reports an ``ok`` flag — False means data was missing
or the API call failed, in which case the corresponding confluence item
must FAIL (we never give a false PASS on missing data).
"""
from __future__ import annotations

import statistics
from typing import Any


# -------------------------------------------------------------------------
# Funding
# -------------------------------------------------------------------------

def funding_consensus(rows: list[dict] | None) -> dict:
    """Median funding rate across exchanges + spread + regime.

    A *consensus* extreme reading (median past the threshold) is much
    stronger evidence than a single exchange — that's why we want
    multi-exchange funding from Coinglass instead of OKX-only.
    """
    if not rows:
        return {"ok": False, "median_rate": None, "spread": None, "regime": "unknown",
                "n_exchanges": 0}
    rates = [r["rate"] for r in rows if r.get("rate") is not None]
    if not rates:
        return {"ok": False, "median_rate": None, "spread": None, "regime": "unknown",
                "n_exchanges": 0}
    med = statistics.median(rates)
    spread = max(rates) - min(rates)
    if med > 0.0003:
        regime = "extreme_long"
    elif med > 0.0001:
        regime = "mild_long"
    elif med < -0.0003:
        regime = "extreme_short"
    elif med < -0.0001:
        regime = "mild_short"
    else:
        regime = "neutral"
    return {
        "ok": True,
        "median_rate": med,
        "median_pct": med * 100,
        "spread": spread,
        "spread_pct": spread * 100,
        "regime": regime,
        "n_exchanges": len(rates),
    }


# -------------------------------------------------------------------------
# Open interest
# -------------------------------------------------------------------------

def oi_trend(rows: list[dict] | None, lookback: int = 12) -> dict:
    """% change in OI-weighted price over ``lookback`` bars."""
    if not rows or len(rows) < lookback + 1:
        return {"ok": False, "trend": "unknown", "change_pct": None}
    old = rows[-lookback - 1]["close"]
    new = rows[-1]["close"]
    if not old:
        return {"ok": False, "trend": "unknown", "change_pct": None}
    change = (new - old) / old * 100
    if change > 1.0:
        trend = "rising"
    elif change < -1.0:
        trend = "falling"
    else:
        trend = "flat"
    return {"ok": True, "trend": trend, "change_pct": round(change, 2)}


# -------------------------------------------------------------------------
# Liquidation pressure
# -------------------------------------------------------------------------

def liq_pressure(rows: list[dict] | None, lookback: int = 24) -> dict:
    """Net long-vs-short liq USD over recent bars.

    Net positive = longs got hit more (price likely flushed lower into
    a magnet); net negative = shorts got hit more (squeeze upward).
    The "side that just got hit" usually does not trade in that
    direction again immediately — it's a contrarian / exhaustion read.
    """
    if not rows:
        return {"ok": False, "long_liq_usd": 0.0, "short_liq_usd": 0.0,
                "net_pressure": "unknown"}
    recent = rows[-lookback:]
    long_total = sum(r["long_liq_usd"] for r in recent)
    short_total = sum(r["short_liq_usd"] for r in recent)
    total = long_total + short_total
    if total <= 0:
        return {"ok": True, "long_liq_usd": long_total, "short_liq_usd": short_total,
                "net_pressure": "flat"}
    if long_total > short_total * 1.5:
        net = "longs_flushed"   # price recently dumped — magnet hit below
    elif short_total > long_total * 1.5:
        net = "shorts_squeezed"  # price recently pumped — magnet hit above
    else:
        net = "balanced"
    return {
        "ok": True,
        "long_liq_usd": long_total,
        "short_liq_usd": short_total,
        "net_pressure": net,
        "long_share_pct": round(long_total / total * 100, 1),
    }


# -------------------------------------------------------------------------
# Heatmap clusters
# -------------------------------------------------------------------------

def heatmap_clusters(heatmap: dict | None, current_price: float) -> dict:
    """Nearest large liquidation magnet above and below current price.

    Coinglass heatmap (model 2) format:
        {"y": [price0, price1, ...], "data": [[xIdx, yIdx, value], ...]}

    We collapse across all x bins (time), summing intensity per y price
    level. The biggest cluster strictly above current price is the
    "magnet up" target; biggest strictly below is the "magnet down"
    target. These are extremely useful as TP1/TP2 candidates.
    """
    if not heatmap or "y" not in heatmap or "data" not in heatmap:
        return {"ok": False, "magnet_up": None, "magnet_down": None}
    y = heatmap.get("y") or []
    if not y:
        return {"ok": False, "magnet_up": None, "magnet_down": None}
    intensity: dict[int, float] = {}
    for cell in heatmap.get("data") or []:
        # Cell shape: [xIdx, yIdx, value]. Defensively skip malformed rows.
        try:
            yi = int(cell[1])
            v = float(cell[2])
        except (IndexError, TypeError, ValueError):
            continue
        intensity[yi] = intensity.get(yi, 0.0) + v
    if not intensity:
        return {"ok": False, "magnet_up": None, "magnet_down": None}

    above: list[tuple[float, float]] = []
    below: list[tuple[float, float]] = []
    for yi, v in intensity.items():
        if yi < 0 or yi >= len(y):
            continue
        try:
            price = float(y[yi])
        except (TypeError, ValueError):
            continue
        if price > current_price:
            above.append((price, v))
        elif price < current_price:
            below.append((price, v))

    def _peak(rows: list[tuple[float, float]]) -> dict | None:
        if not rows:
            return None
        price, v = max(rows, key=lambda x: x[1])
        # distance % to use as confluence-proximity threshold
        dist_pct = (price - current_price) / current_price * 100
        return {"price": price, "intensity": v, "distance_pct": round(dist_pct, 2)}

    return {
        "ok": True,
        "magnet_up": _peak(above),
        "magnet_down": _peak(below),
    }


# -------------------------------------------------------------------------
# Sentiment
# -------------------------------------------------------------------------

def sentiment(rows: list[dict] | None) -> dict:
    """Top-trader long/short read from latest sample.

    Extreme readings (>= 65/35 either way) are contrarian. A balanced
    book (within 50 +/- 5) is just noise.
    """
    if not rows:
        return {"ok": False, "long_pct": None, "short_pct": None, "skew": "unknown"}
    last = rows[-1]
    lp, sp = last.get("long_pct"), last.get("short_pct")
    if lp is None or sp is None:
        return {"ok": False, "long_pct": None, "short_pct": None, "skew": "unknown"}
    if lp >= 65:
        skew = "crowd_long"
    elif sp >= 65:
        skew = "crowd_short"
    else:
        skew = "balanced"
    return {
        "ok": True,
        "long_pct": lp,
        "short_pct": sp,
        "ratio": last.get("ratio"),
        "skew": skew,
    }


# -------------------------------------------------------------------------
# Confluence augmentation
# -------------------------------------------------------------------------

def coinglass_confluence(
    direction: str,            # "long" | "short" | "none"
    funding: dict,
    liq: dict,
    heatmap: dict,
    sent: dict,
    current_price: float,
) -> list[dict]:
    """Two extra confluence items from Coinglass-derived signals.

    Item A — funding consensus AGAINST the trade direction (crowd is
    on the other side, so squeeze/flush in our direction is more likely).

    Item B — heatmap magnet exists in the trade direction within a
    reasonable distance (gives a high-conviction TP1).
    """
    items: list[dict] = []

    # A. Funding consensus against direction
    fund_ok = False
    fund_reason = "unknown"
    if direction != "none" and funding.get("ok"):
        regime = funding["regime"]
        # Long trade thrives when crowd is short (mild_short / extreme_short).
        # Short trade thrives when crowd is long.
        if direction == "long" and regime in ("mild_short", "extreme_short"):
            fund_ok = True
        elif direction == "short" and regime in ("mild_long", "extreme_long"):
            fund_ok = True
        fund_reason = f"regime={regime}"
    items.append({
        "name": "Funding consensus (multi-exchange)",
        "ok": fund_ok,
        "reason": fund_reason,
    })

    # B. Heatmap magnet in our favour within 5%
    hm_ok = False
    hm_reason = "no heatmap"
    if direction != "none" and heatmap.get("ok"):
        if direction == "long":
            mag = heatmap.get("magnet_up")
            if mag and 0 < mag["distance_pct"] <= 5:
                hm_ok = True
                hm_reason = f"magnet_up @ {mag['price']:.2f} (+{mag['distance_pct']}%)"
            elif mag:
                hm_reason = f"magnet_up too far (+{mag['distance_pct']}%)"
        else:  # short
            mag = heatmap.get("magnet_down")
            if mag and -5 <= mag["distance_pct"] < 0:
                hm_ok = True
                hm_reason = f"magnet_down @ {mag['price']:.2f} ({mag['distance_pct']}%)"
            elif mag:
                hm_reason = f"magnet_down too far ({mag['distance_pct']}%)"
    items.append({
        "name": "Liquidation magnet within 5%",
        "ok": hm_ok,
        "reason": hm_reason,
    })

    return items
