"""Coinglass API v3 client — stdlib-only.

Wraps the subset of Coinglass v3 endpoints used by the trading webapp.
Designed to gracefully degrade when the API key is missing or the
service is unreachable: every public method returns either a list of
dicts or ``None`` and never raises to the caller (errors are captured
in ``last_error`` for surfacing in the UI).

Auth:
    The API key is read from the ``COINGLASS_API_KEY`` environment
    variable. If unset, all calls short-circuit to ``None`` so the
    webapp can still render TA + MVRV without futures microstructure.

Why not pandas / the official SDK:
    Project policy is stdlib-only. We hand-roll the urllib request
    layer + JSON parsing here. Output shapes are intentionally simple
    Python primitives so they can be JSON-serialised straight into the
    HTTP responses our webapp returns.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


BASE = "https://open-api-v3.coinglass.com/api/"
DEFAULT_TIMEOUT = 8.0   # seconds — Coinglass is occasionally slow


@dataclass
class CoinglassClient:
    """Thin synchronous wrapper. One instance per webapp process is fine."""

    api_key: str | None = field(
        default_factory=lambda: os.environ.get("COINGLASS_API_KEY") or None
    )
    base: str = BASE
    timeout: float = DEFAULT_TIMEOUT
    last_error: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Low-level
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict | None:
        """Issue a GET, return the parsed JSON ``data`` field or ``None``.

        ``last_error`` is set on every failure path so the UI can show a
        meaningful message instead of an empty panel.
        """
        if not self.configured:
            self.last_error = "COINGLASS_API_KEY not set"
            return None
        params = params or {}
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base}{path}"
        if qs:
            url = f"{url}?{qs}"
        req = urllib.request.Request(
            url,
            headers={
                "accept": "application/json",
                "CG-API-KEY": self.api_key or "",
                "user-agent": "ch-ng-kho-n-webapp/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            self.last_error = f"HTTP {e.code}: {e.reason}"
            return None
        except (urllib.error.URLError, TimeoutError) as e:
            self.last_error = f"network: {e}"
            return None
        except json.JSONDecodeError as e:
            self.last_error = f"bad json: {e}"
            return None
        # Coinglass envelopes everything under {"code": "0", "msg": "...", "data": ...}.
        # Treat any non-zero code as an error and surface the message.
        code = str(payload.get("code", ""))
        if code not in ("0", "00000"):
            self.last_error = f"coinglass: code={code} msg={payload.get('msg')}"
            return None
        self.last_error = None
        return payload

    # ------------------------------------------------------------------
    # Public endpoints (subset)
    # ------------------------------------------------------------------

    def funding_rate_exchange_list(self, symbol: str = "BTC") -> list[dict] | None:
        """Current funding rate per exchange for a symbol.

        Returns a list like:
            [{"exchange": "Binance", "rate": 0.0001, "next_at": ...}, ...]
        Coinglass returns nested arrays of perpetual contracts; we
        flatten to one row per exchange and pick the USDT-margined
        perpetual rate when multiple are listed.
        """
        raw = self._get("futures/fundingRate/exchange-list", {"symbol": symbol})
        if not raw:
            return None
        rows: list[dict] = []
        # Schema (v3): data: [ { "symbol": "BTC", "stablecoinMarginList": [...], ... }, ... ]
        for entry in (raw.get("data") or []):
            sm = entry.get("stablecoinMarginList") or []
            if not sm:
                continue
            for ex in sm:
                rate = ex.get("fundingRate")
                if rate is None:
                    continue
                rows.append({
                    "exchange": ex.get("exchangeName"),
                    "rate": float(rate),
                    "rate_pct": float(rate) * 100,
                    "next_at": ex.get("nextFundingTime"),
                })
        return rows or None

    def liquidation_aggregated_history(
        self, symbol: str = "BTC", interval: str = "1h", limit: int = 100,
    ) -> list[dict] | None:
        """Aggregated liquidation totals per bar.

        Returns a list like:
            [{"ts": ..., "long_liq_usd": ..., "short_liq_usd": ...}, ...]
        Sorted oldest-first.
        """
        raw = self._get(
            "futures/liquidation/aggregated-history",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        if not raw:
            return None
        out: list[dict] = []
        for row in (raw.get("data") or []):
            try:
                out.append({
                    "ts": int(row.get("t") or row.get("createTime") or 0) // 1000,
                    "long_liq_usd": float(row.get("longLiquidationUsd") or 0.0),
                    "short_liq_usd": float(row.get("shortLiquidationUsd") or 0.0),
                })
            except (TypeError, ValueError):
                continue
        return out or None

    def liquidation_aggregated_heatmap(
        self, symbol: str = "BTC", range_: str = "3d",
    ) -> dict | None:
        """Aggregated liquidation heatmap (model 2) — price/density grid.

        Heatmap format from Coinglass:
            { "y": [price1, price2, ...],
              "data": [[xIdx, yIdx, value], ...],
              "maxLiqValue": ... }
        We pass it through almost verbatim — the webapp's frontend
        knows how to render this shape.
        """
        raw = self._get(
            "futures/liquidation/aggregated-heatmap/model2",
            {"symbol": symbol, "range": range_},
        )
        if not raw:
            return None
        return raw.get("data") or None

    def oi_weight_ohlc_history(
        self, symbol: str = "BTC", interval: str = "1h", limit: int = 100,
    ) -> list[dict] | None:
        """Open-interest-weighted OHLC across exchanges."""
        raw = self._get(
            "futures/openInterest/ohlc-aggregated-history",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        if not raw:
            return None
        out: list[dict] = []
        for row in (raw.get("data") or []):
            try:
                out.append({
                    "ts": int(row.get("t") or 0) // 1000,
                    "open": float(row.get("o") or 0),
                    "high": float(row.get("h") or 0),
                    "low": float(row.get("l") or 0),
                    "close": float(row.get("c") or 0),
                })
            except (TypeError, ValueError):
                continue
        return out or None

    def long_short_position_ratio(
        self, symbol: str = "BTC", interval: str = "1h", limit: int = 100,
    ) -> list[dict] | None:
        """Top-trader long/short position ratio history (Binance default)."""
        raw = self._get(
            "futures/topLongShortPositionRatio/history",
            {"symbol": symbol, "interval": interval, "limit": limit, "exchange": "Binance"},
        )
        if not raw:
            return None
        out: list[dict] = []
        for row in (raw.get("data") or []):
            try:
                out.append({
                    "ts": int(row.get("t") or 0) // 1000,
                    "long_pct": float(row.get("longAccount") or 0),
                    "short_pct": float(row.get("shortAccount") or 0),
                    "ratio": float(row.get("longShortRatio") or 0),
                })
            except (TypeError, ValueError):
                continue
        return out or None
