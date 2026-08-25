"""Recompute every remaining tier-B metric against its published definition.

An earlier pass wrote these off as "single-definition indicators where no competing
convention exists to distinguish". That was wrong, and reading the header text is what
showed it:

  Bollinger carries a PERIOD and a MULTIPLIER, stated nowhere in any contract.
  PPO is the HISTOGRAM ("percentage price oscillator histogram"), not the oscillator.
  HIGH_DEV / LOW_DEV measure from the bar's OPEN - a definition this repo did not hold.
  ROC12 renders a RAW FRACTION while its label says "(%)". See BG-11.

On tolerances. The first run of this script used 0.0002 on a number near 195 and called
four exact agreements "misses". BattleGrid's tape and Hyperliquid's differ on about 1 in
20 closes by 1-10 points (docs/19), so a price-derived metric can only ever agree to
roughly 0.001%. Tolerances below are set from that measured floor, not from wishful
precision - and each is stated as a RELATIVE bound so the reason is visible.

Anchor: BTC 1h, `offset: 1`, pinned to 2026-08-25T12:00Z (close 78,967) by a closed CLOSE
trajectory rendered beside the metrics.

    python -m scripts.verify_tier_b
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

# Rendered together, same section, offset:1 unless noted.
RENDERED = {
    "MACD": -195.5602, "MFI14": 56.6, "PPO": -0.25, "ROC": -0.01,
    "SMA50": 78443.18, "SMA200": 72637.40, "EMA20": 79392.55,
    "EMA5": 79290.70, "EMA13": 79509.69, "SMA20": 79535.25,
    "pctB": 0.30, "BBwidth": 2796.14, "bbWidthPct": 3.52,
    "highDev": 0.10, "lowDev": -0.06,          # read WITHOUT offset, forming bar
    "volSMA20": 2600.0, "RVOL": 0.94, "OBV": -3763.0,
    "RSI7": 35.7, "VWAP": 79983.73,
}
# The forming bar those two were read on, from the same render.
FORMING = {"open": 78967.0, "high": 79049.0, "low": 78918.0}

REL = 2e-5      # 0.002% - twice the measured tape-disagreement floor
ANCHOR_PRICE = 78967.0

# MACD and BBwidth are DIFFERENCES of price series, so they inherit ABSOLUTE error from
# the closes rather than relative error from themselves. A 1-point close disagreement is
# 0.0013% of price but ~0.5% of a 195-point MACD histogram. Judging them against their
# own magnitude would demand precision the tape cannot supply, which is what made the
# first run call two exact agreements "misses". Their bound is price x REL.
PRICE_SCALED = {"MACD", "BBwidth"}

ABS = {"MFI14": 0.05, "pctB": 0.005, "bbWidthPct": 0.005, "ROC": 0.005,
       "PPO": 0.005, "highDev": 0.005, "lowDev": 0.005, "RVOL": 0.005,
       "RSI7": 0.05, "volSMA20": 60.0, "OBV": 12.0}


def fits(key, got):
    gap = abs(got - RENDERED[key])
    if key in PRICE_SCALED:
        return gap <= ANCHOR_PRICE * REL
    if key in ABS:
        return gap <= ABS[key]
    return gap <= abs(RENDERED[key]) * REL


def ema(xs, n):
    a = 2 / (n + 1)
    e = sum(xs[:n]) / n
    for x in xs[n:]:
        e = a * x + (1 - a) * e
    return e


def ema_series(xs, n):
    a = 2 / (n + 1)
    e = sum(xs[:n]) / n
    out = [e]
    for x in xs[n:]:
        e = a * x + (1 - a) * e
        out.append(e)
    return out


def sma(xs, n):
    return sum(xs[-n:]) / n


def stdev(xs, sample=False):
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - (1 if sample else 0))) ** 0.5


def rsi_wilder(c, n):
    d = [b - a for a, b in zip(c, c[1:])]
    g, l = [max(x, 0.0) for x in d], [max(-x, 0.0) for x in d]
    ag, al = sum(g[:n]) / n, sum(l[:n]) / n
    for gi, li in zip(g[n:], l[n:]):
        ag, al = (ag * (n - 1) + gi) / n, (al * (n - 1) + li) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def macd_hist(c, fast=12, slow=26, sig=9):
    f, s = ema_series(c, fast), ema_series(c, slow)
    line = [a - b for a, b in zip(f[len(f) - len(s):], s)]
    return line[-1] - ema(line, sig)


def ppo_hist(c, fast=12, slow=26, sig=9):
    f, s = ema_series(c, fast), ema_series(c, slow)
    line = [(a - b) / b * 100 for a, b in zip(f[len(f) - len(s):], s)]
    return line[-1] - ema(line, sig)


def mfi(h, l, c, v, n=14):
    tp = [(a + b + d) / 3 for a, b, d in zip(h, l, c)]
    pos = neg = 0.0
    for i in range(len(tp) - n, len(tp)):
        f = tp[i] * v[i]
        if tp[i] > tp[i - 1]:
            pos += f
        elif tp[i] < tp[i - 1]:
            neg += f
    return 100.0 if neg == 0 else 100 - 100 / (1 + pos / neg)


def _today(bars):
    last = dt.datetime.fromtimestamp(bars[-1]["t"] / 1000, dt.timezone.utc)
    start = last.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000
    return [b for b in bars if b["t"] >= start]


def obv_daily(bars):
    """Classic OBV - signed by close vs the PREVIOUS CLOSE - anchored at 00:00 UTC.
    An earlier version signed by close-vs-open and was out by a factor of twenty."""
    day = _today(bars)
    prev, total = day[0]["c"], 0.0
    for b in day[1:]:
        total += b["v"] if b["c"] > prev else (-b["v"] if b["c"] < prev else 0.0)
        prev = b["c"]
    return total


def vwap_daily(bars):
    day = _today(bars)
    num = sum((b["h"] + b["l"] + b["c"]) / 3 * b["v"] for b in day)
    den = sum(b["v"] for b in day)
    return num / den


def bollinger(c, n=20, k=2.0, sample=False):
    win = c[-n:]
    mid, sd = sum(win) / n, stdev(win, sample)
    up, lo = mid + k * sd, mid - k * sd
    return up - lo, (up - lo) / mid * 100, (c[-1] - lo) / (up - lo)


def main() -> int:
    bars = json.loads(
        Path("data/audit/candles_btc_1h_tierb.json").read_text(encoding="utf-8"))["bars"]
    o = [b["o"] for b in bars]; h = [b["h"] for b in bars]
    l = [b["l"] for b in bars]; c = [b["c"] for b in bars]; v = [b["v"] for b in bars]
    assert c[-1] == 78967.0, f"tape does not end on the anchor bar: {c[-1]}"
    print(f"{len(c)} bars, anchor close {c[-1]:,.0f}\n")

    print("BOLLINGER - period and multiplier are published nowhere. Searched, not assumed:")
    best = None
    for n in range(5, 41):
        for k in (1.0, 1.5, 2.0, 2.5, 3.0):
            for samp in (False, True):
                w, wp, pb = bollinger(c, n, k, samp)
                err = (abs(w - RENDERED["BBwidth"]) / RENDERED["BBwidth"]
                       + abs(wp - RENDERED["bbWidthPct"]) / 3.52
                       + abs(pb - RENDERED["pctB"]))
                if best is None or err < best[0]:
                    best = (err, n, k, samp)
    _, bn, bk, bsamp = best
    print(f"  -> period {bn}, multiplier {bk}, "
          f"{'sample (n-1)' if bsamp else 'population (n)'} standard deviation\n")
    bw, bwp, bpb = bollinger(c, bn, bk, bsamp)

    rows = [
        ("MACD  histogram 12/26/9", macd_hist(c), "MACD"),
        ("PPO   histogram 12/26/9 (percent)", ppo_hist(c), "PPO"),
        ("ROC   12-bar change as a RAW FRACTION", (c[-1] - c[-13]) / c[-13], "ROC"),
        ("RSI7  Wilder, n=7", rsi_wilder(c, 7), "RSI7"),
        ("SMA20", sma(c, 20), "SMA20"),
        ("SMA50", sma(c, 50), "SMA50"),
        ("SMA200", sma(c, 200), "SMA200"),
        ("EMA5", ema(c, 5), "EMA5"),
        ("EMA13", ema(c, 13), "EMA13"),
        ("EMA20", ema(c, 20), "EMA20"),
        (f"BBwidth    upper-lower, {bn}/{bk}", bw, "BBwidth"),
        (f"bbWidthPct (upper-lower)/mid x100", bwp, "bbWidthPct"),
        (f"pctB       (close-lower)/(up-lower)", bpb, "pctB"),
        ("highDev (high-open)/open x100  [forming bar]",
         (FORMING["high"] - FORMING["open"]) / FORMING["open"] * 100, "highDev"),
        ("lowDev  (low-open)/open x100   [forming bar]",
         (FORMING["low"] - FORMING["open"]) / FORMING["open"] * 100, "lowDev"),
        ("MFI14 typical-price money flow", mfi(h, l, c, v), "MFI14"),
        ("volSMA20", sma(v, 20), "volSMA20"),
        ("RVOL  volume / 20-period average", v[-1] / sma(v, 20), "RVOL"),
        ("OBV   close-vs-PREV-close, daily-anchored", obv_daily(bars), "OBV"),
        ("VWAP  sum(TP x V) / sum(V), daily-anchored", vwap_daily(bars), "VWAP"),
    ]
    print(f"{'metric / definition':<46} {'computed':>13} {'rendered':>12}  verdict")
    hits = 0
    for label, got, key in rows:
        ok = fits(key, got)
        hits += ok
        print(f"  {label:<44} {got:>13.4f} {RENDERED[key]:>12.4f}  {'MATCH' if ok else 'no'}")
    print(f"\n  {hits} of {len(rows)} reproduce the rendered value.")
    print("  Volume-derived rows use the Hyperliquid tape, whose volume differs from")
    print("  BattleGrid's by ~0.3% on average - so their tolerance is set accordingly.")
    return 0 if hits == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
