"""Public OHLC data sources for BTC (stdlib only).

Primary: Kraken public OHLC (no key, up to 720 candles).
Fallback: CryptoCompare histoday/histohour (no key for low volume).
"""
from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Literal

Timeframe = Literal["1d", "4h", "1h", "15m", "5m"]
Asset = Literal["BTC", "ETH", "SOL"]

_KRAKEN_PAIR = {"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD"}
_CC_SYMBOL = {"BTC": "BTC", "ETH": "ETH", "SOL": "SOL"}

_KRAKEN_INTERVAL = {"1d": 1440, "4h": 240, "1h": 60, "15m": 15, "5m": 5}
_CC_INTERVAL = {
    "1d": "histoday", "4h": "histohour", "1h": "histohour",
    "15m": "histominute", "5m": "histominute",
}


@dataclass
class Candle:
    ts: int           # unix seconds, open time
    open: float
    high: float
    low: float
    close: float
    volume: float


def _http_json(url: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "chngkhoan-agent/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_kraken(pair: str = "XBTUSD", tf: Timeframe = "1d") -> list[Candle]:
    interval = _KRAKEN_INTERVAL[tf]
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    d = _http_json(url)
    if d.get("error"):
        raise RuntimeError(f"kraken error: {d['error']}")
    # the response key isn't always the requested pair; pick the non-'last' key
    key = next(k for k in d["result"] if k != "last")
    rows = d["result"][key]
    return [
        Candle(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6]))
        for r in rows
    ]


def fetch_cryptocompare(symbol: str = "BTC", tsym: str = "USD",
                        tf: Timeframe = "1d", limit: int = 500) -> list[Candle]:
    endpoint = _CC_INTERVAL[tf]
    aggregate = {"5m": 5, "15m": 15, "1h": 1, "4h": 4, "1d": 1}[tf]
    url = (f"https://min-api.cryptocompare.com/data/v2/{endpoint}"
           f"?fsym={symbol}&tsym={tsym}&limit={limit}&aggregate={aggregate}")
    d = _http_json(url)
    if d.get("Response") != "Success":
        raise RuntimeError(f"cryptocompare error: {d}")
    return [
        Candle(int(r["time"]), float(r["open"]), float(r["high"]),
               float(r["low"]), float(r["close"]), float(r["volumefrom"]))
        for r in d["Data"]["Data"]
        if r["high"] > 0
    ]


def fetch_ohlc(tf: Timeframe = "1d", asset: Asset = "BTC") -> tuple[list[Candle], str]:
    """Try Kraken first, fall back to CryptoCompare. Returns (candles, source)."""
    errors: list[str] = []
    pair = _KRAKEN_PAIR.get(asset, "XBTUSD")
    sym = _CC_SYMBOL.get(asset, "BTC")
    try:
        c = fetch_kraken(pair, tf)
        if c:
            return c, "kraken"
        errors.append("kraken returned empty data")
    except Exception as e:
        errors.append(f"kraken failed: {e}")
    try:
        c = fetch_cryptocompare(sym, "USD", tf)
        if c:
            return c, "cryptocompare"
        errors.append("cryptocompare returned empty data")
    except Exception as e:
        errors.append(f"cryptocompare failed: {e}")
    raise RuntimeError("; ".join(errors))


def iso_date(ts: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))
