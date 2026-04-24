"""Technical indicators in pure Python (stdlib only).

Each function takes a list[float] or list[Candle] and returns aligned output
(same length, None for undefined leading values). Designed for OHLC time-series
in chronological order (oldest -> newest).
"""
from __future__ import annotations

from typing import Sequence


# ---------- helpers --------------------------------------------------------

def _sma(xs: Sequence[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(xs)
    s = 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(xs: Sequence[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(xs)
    k = 2.0 / (n + 1)
    # seed with SMA of first n
    if len(xs) < n:
        return out
    seed = sum(xs[:n]) / n
    out[n - 1] = seed
    for i in range(n, len(xs)):
        prev = out[i - 1]
        out[i] = xs[i] * k + prev * (1 - k)  # type: ignore[operator]
    return out


# ---------- core indicators ------------------------------------------------

def rsi(closes: Sequence[float], n: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains, losses = 0.0, 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    avg_g, avg_l = gains / n, losses / n
    if avg_l == 0:
        out[n] = 100.0
    else:
        rs = avg_g / avg_l
        out[n] = 100 - 100 / (1 + rs)
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        g = max(d, 0)
        l = max(-d, 0)
        avg_g = (avg_g * (n - 1) + g) / n
        avg_l = (avg_l * (n - 1) + l) / n
        if avg_l == 0:
            out[i] = 100.0
        else:
            rs = avg_g / avg_l
            out[i] = 100 - 100 / (1 + rs)
    return out


def macd(closes: Sequence[float], fast: int = 12, slow: int = 26, sig: int = 9):
    ef = ema(closes, fast)
    es = ema(closes, slow)
    macd_line: list[float | None] = [
        (a - b) if (a is not None and b is not None) else None
        for a, b in zip(ef, es)
    ]
    # signal = EMA of macd_line (skip None)
    defined = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    sig_line: list[float | None] = [None] * len(closes)
    if len(defined) >= sig:
        seed = sum(v for _, v in defined[:sig]) / sig
        sig_line[defined[sig - 1][0]] = seed
        k = 2.0 / (sig + 1)
        prev = seed
        for i in range(sig, len(defined)):
            idx, v = defined[i]
            prev = v * k + prev * (1 - k)
            sig_line[idx] = prev
    hist = [
        (a - b) if (a is not None and b is not None) else None
        for a, b in zip(macd_line, sig_line)
    ]
    return macd_line, sig_line, hist


def atr(highs: Sequence[float], lows: Sequence[float],
        closes: Sequence[float], n: int = 14) -> list[float | None]:
    tr: list[float] = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    # Wilder smoothing (RMA)
    out: list[float | None] = [None] * len(closes)
    if len(tr) < n:
        return out
    seed = sum(tr[:n]) / n
    out[n - 1] = seed
    for i in range(n, len(tr)):
        prev = out[i - 1]
        out[i] = (prev * (n - 1) + tr[i]) / n  # type: ignore[operator]
    return out


# ---------- Ichimoku -------------------------------------------------------

def ichimoku(highs: Sequence[float], lows: Sequence[float],
             closes: Sequence[float],
             tenkan: int = 9, kijun: int = 26, senkou_b: int = 52):
    def _mid(period: int) -> list[float | None]:
        out: list[float | None] = [None] * len(highs)
        for i in range(period - 1, len(highs)):
            hh = max(highs[i - period + 1:i + 1])
            ll = min(lows[i - period + 1:i + 1])
            out[i] = (hh + ll) / 2
        return out

    t = _mid(tenkan)
    k = _mid(kijun)
    span_a: list[float | None] = [
        ((a + b) / 2) if (a is not None and b is not None) else None
        for a, b in zip(t, k)
    ]
    span_b = _mid(senkou_b)
    return {"tenkan": t, "kijun": k, "span_a": span_a, "span_b": span_b}


# ---------- Fibonacci retracement -----------------------------------------

def fib_retracements(swing_high: float, swing_low: float) -> dict[str, float]:
    d = swing_high - swing_low
    return {
        "0.000": swing_high,
        "0.236": swing_high - d * 0.236,
        "0.382": swing_high - d * 0.382,
        "0.500": swing_high - d * 0.500,
        "0.618": swing_high - d * 0.618,
        "0.786": swing_high - d * 0.786,
        "1.000": swing_low,
    }


# ---------- Support / Resistance (pivot-based) -----------------------------

def swing_pivots(highs: Sequence[float], lows: Sequence[float],
                 left: int = 5, right: int = 5) -> tuple[list[int], list[int]]:
    """Return (swing_high_indexes, swing_low_indexes)."""
    sh, sl = [], []
    for i in range(left, len(highs) - right):
        hi_ok = all(highs[i] >= highs[i - j] for j in range(1, left + 1)) and \
                all(highs[i] >= highs[i + j] for j in range(1, right + 1))
        lo_ok = all(lows[i] <= lows[i - j] for j in range(1, left + 1)) and \
                all(lows[i] <= lows[i + j] for j in range(1, right + 1))
        if hi_ok:
            sh.append(i)
        if lo_ok:
            sl.append(i)
    return sh, sl


def support_resistance(highs: Sequence[float], lows: Sequence[float],
                       current: float, left: int = 5, right: int = 5,
                       tol: float = 0.01) -> tuple[list[float], list[float]]:
    """Return (supports_below_current, resistances_above_current), clustered."""
    sh, sl = swing_pivots(highs, lows, left, right)
    resistances = [highs[i] for i in sh if highs[i] > current]
    supports = [lows[i] for i in sl if lows[i] < current]

    def cluster(levels: list[float]) -> list[float]:
        levels = sorted(levels)
        out: list[float] = []
        for lv in levels:
            if out and abs(lv - out[-1]) / out[-1] < tol:
                out[-1] = (out[-1] + lv) / 2
            else:
                out.append(lv)
        return out

    return cluster(supports), cluster(resistances)


# ---------- Volume profile -------------------------------------------------

def volume_profile(highs: Sequence[float], lows: Sequence[float],
                   closes: Sequence[float], volumes: Sequence[float],
                   bins: int = 24, lookback: int = 180) -> dict:
    """Return {bins: [(lo, hi, vol), ...], poc, vah, val} over last `lookback`."""
    i0 = max(0, len(closes) - lookback)
    hi = max(highs[i0:])
    lo = min(lows[i0:])
    if hi <= lo:
        return {"bins": [], "poc": None, "vah": None, "val": None}
    step = (hi - lo) / bins
    buckets = [0.0] * bins
    for j in range(i0, len(closes)):
        # distribute volume evenly across candle range
        r_lo, r_hi, v = lows[j], highs[j], volumes[j]
        start = max(int((r_lo - lo) / step), 0)
        end = min(int((r_hi - lo) / step), bins - 1)
        span = max(end - start + 1, 1)
        share = v / span
        for b in range(start, end + 1):
            buckets[b] += share

    bin_list = [(lo + i * step, lo + (i + 1) * step, buckets[i]) for i in range(bins)]
    poc_idx = max(range(bins), key=lambda i: buckets[i])
    poc = (bin_list[poc_idx][0] + bin_list[poc_idx][1]) / 2

    # value area = 70% of total volume around POC
    total = sum(buckets)
    target = total * 0.70
    left = right = poc_idx
    acc = buckets[poc_idx]
    while acc < target and (left > 0 or right < bins - 1):
        l_v = buckets[left - 1] if left > 0 else -1
        r_v = buckets[right + 1] if right < bins - 1 else -1
        if l_v >= r_v and left > 0:
            left -= 1
            acc += buckets[left]
        elif right < bins - 1:
            right += 1
            acc += buckets[right]
        else:
            break
    val = bin_list[left][0]
    vah = bin_list[right][1]
    return {"bins": bin_list, "poc": poc, "vah": vah, "val": val}
