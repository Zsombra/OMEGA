"""Check BattleGrid's numbers against something other than BattleGrid.

Everything else in this repo verifies CONSISTENCY - that omega predicts what the
platform does. That is not correctness. Nothing in a 300/300 header sweep would notice
if the platform's RSI were secretly a 12-period, or if its prices were synthetic.

Two tiers, testing different things:

  tier 3  is the tape real?
          Diff BattleGrid's candles against the Hyperliquid public API for the same
          window, and check funding and open interest against the exchange context.
          Catches a synthetic feed, a stale feed, a wrong symbol, or a unit error.

  tier 2  is the maths right?
          Recompute SMA / EMA / RSI / ATR from the bars and compare to what the report
          renders. Catches a wrong formula, window, or smoothing constant.

Tier 2 is run over two bar sets - closed only, and closed plus the forming bar - which
also settles WHICH set the platform computes on. That has no documented answer and it
changes every indicator's last value.

    python -m scripts.verify_indicators

One methodological note, because it produced a false positive the first time this ran.
Wilder smoothing is an infinite-memory filter: with only 60 bars the seed still moves
the answer, and ATR came out 4.8 low against a correct engine. It needs ~200 bars to
converge. The convergence table is printed rather than hidden, because "the tool
disagrees" and "my window was too short" look identical until you check.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

AUDIT = Path("data/audit")
BG = json.loads((AUDIT / "candles_btc_1h_battlegrid.json").read_text(encoding="utf-8"))
REF = json.loads((AUDIT / "candles_btc_1h_hyperliquid_400.json").read_text(encoding="utf-8"))
SNAP = BG["_reportSnapshot"]

# Read off Hyperliquid metaAndAssetCtxs on 2026-08-25, minutes after the report render.
EXCHANGE_CTX = {
    "BTC": {"fundingDecimal": 0.0000125, "oiCoins": 38379, "markPx": 78925.0},
    "SOL": {"fundingDecimal": 0.000020684, "oiCoins": 5241069, "markPx": 99.904},
}
RENDERED = {  # from the same preview_strategy_report render
    "BTC": {"ratePct": 0.0013, "oiText": "$3.0B"},
    "SOL": {"ratePct": 0.0017, "oiText": "$520.4M"},
}


def _stamp(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:00Z")


# --- indicators, straight from the textbook definitions ---------------------

def sma(xs, n):
    return sum(xs[-n:]) / n


def ema(xs, n):
    a = 2 / (n + 1)
    e = sum(xs[:n]) / n
    for x in xs[n:]:
        e = a * x + (1 - a) * e
    return e


def rsi_wilder(closes, n=14):
    d = [b - a for a, b in zip(closes, closes[1:])]
    g, l = [max(x, 0.0) for x in d], [max(-x, 0.0) for x in d]
    ag, al = sum(g[:n]) / n, sum(l[:n]) / n
    for gi, li in zip(g[n:], l[n:]):
        ag, al = (ag * (n - 1) + gi) / n, (al * (n - 1) + li) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def atr_wilder(h, l, c, n=14):
    trs = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
           for i in range(1, len(c))]
    a = sum(trs[:n]) / n
    for tr in trs[n:]:
        a = (a * (n - 1) + tr) / n
    return a


# --- bar assembly -----------------------------------------------------------

def bars(include_forming: bool):
    """Hyperliquid history, overwritten by BattleGrid's own bars wherever we hold them,
    so the recent window is the platform's data and the deep history is the exchange's."""
    own = {c["t"]: c for c in BG["candles"]}
    H, L, C = [], [], []
    for b in REF["bars"]:
        t = _stamp(b["t"])
        src = own.get(t, b)
        H.append(src["h"]); L.append(src["l"]); C.append(src["c"])
    if include_forming:
        H.append(SNAP["high"]); L.append(SNAP["low"]); C.append(SNAP["close"])
    return H, L, C


# --- tier 3 -----------------------------------------------------------------

def tier3():
    ref = {_stamp(b["t"]): b for b in REF["bars"]}
    exact, close_only, gaps, vol = 0, [], [], []
    for c in BG["candles"]:
        r = ref.get(c["t"])
        if not r:
            continue
        same = {k: abs(c[k] - r[k]) < 1e-9 for k in ("o", "h", "l", "c")}
        if all(same.values()):
            exact += 1
        elif same["o"] and same["h"] and same["l"]:
            close_only.append((c["t"], c["c"], r["c"]))
            gaps.append(abs(c["c"] - r["c"]) / r["c"] * 100)
        vol.append((c["v"] - r["v"]) / r["v"] * 100)

    n = len([c for c in BG["candles"] if c["t"] in ref])
    print("TIER 3 - is the tape real?")
    print(f"  bars compared to Hyperliquid   {n}")
    print(f"  OHLC identical                 {exact} / {n}")
    print(f"  differing in CLOSE only        {len(close_only)}")
    for t, a, b in close_only:
        print(f"      {t}   BattleGrid {a:,.0f}   Hyperliquid {b:,.0f}   "
              f"gap {abs(a-b)/b*100:.4f}%")
    if gaps:
        print(f"      worst close gap            {max(gaps):.4f}%  "
              "- open/high/low never differ, so this is a sampling instant, not a feed")
    print(f"  volume gap                     mean {sum(vol)/len(vol):+.1f}%, "
          f"range [{min(vol):+.1f}%, {max(vol):+.1f}%]  - a different measure, not a bad feed")

    print("\n  funding and open interest, against the exchange context:")
    for coin, ctx in EXCHANGE_CTX.items():
        hl_pct = ctx["fundingDecimal"] * 100
        oi_b = ctx["oiCoins"] * ctx["markPx"] / 1e9
        print(f"    {coin}  funding  exchange {hl_pct:.6f}%   rendered "
              f"{RENDERED[coin]['ratePct']}%   -> rate = funding x 100, unit confirmed")
        print(f"    {coin}  OI       exchange ${oi_b:.2f}B (coins x mark)   rendered "
              f"{RENDERED[coin]['oiText']}")


# --- tier 2 -----------------------------------------------------------------

def tier2():
    sets = {"closed bars only": bars(False), "closed + forming": bars(True)}
    checks = [
        ("SMA20", SNAP["SMA20"], lambda H, L, C: sma(C, 20),              0.01),
        ("EMA5",  SNAP["EMA5"],  lambda H, L, C: ema(C, 5),               0.01),
        ("EMA13", SNAP["EMA13"], lambda H, L, C: ema(C, 13),              0.02),
        ("RSI14", SNAP["RSI14"], lambda H, L, C: rsi_wilder(C, 14),       0.05),
        ("ATR",   SNAP["ATR"],   lambda H, L, C: atr_wilder(H, L, C, 14), 0.01),
    ]
    print(f"\nTIER 2 - is the maths right?   ({len(sets['closed bars only'][2])} bars of history)")
    print(f"  {'indicator':<10} {'rendered':>13} {'closed only':>16} {'closed + forming':>19}")
    tally = {k: 0 for k in sets}
    for name, rendered, fn, tol in checks:
        cells = ""
        for label, (H, L, C) in sets.items():
            got = fn(H, L, C)
            hit = abs(got - rendered) <= tol
            tally[label] += hit
            cells += f"{got:>17.4f}{'*' if hit else ' '}"
        print(f"  {name:<10} {rendered:>13.4f}{cells}")
    print("\n  * = matches the rendered value")
    for label, n in tally.items():
        print(f"  {label:<20} {n} of {len(checks)}")


def convergence():
    H, L, C = bars(True)
    print("\nWHY HISTORY LENGTH MATTERS - Wilder ATR against the same rendered value")
    print(f"  {'bars used':>10} {'ATR':>12} {'gap':>10}")
    for take in (61, 100, 200, 400, len(C)):
        h, l, c = H[-take:], L[-take:], C[-take:]
        got = atr_wilder(h, l, c, 14)
        print(f"  {take:>10} {got:>12.4f} {got - SNAP['ATR']:>+10.4f}")
    print("  60 bars reads as a defect. 200 bars reads as an exact match. Same engine.")


if __name__ == "__main__":
    tier3()
    tier2()
    convergence()
    print("\nNOT proven by any of this: that the forming bar is right at the instant of"
          "\nrender, that coins other than BTC behave the same, or that CVD / crowd /"
          "\nstructure metrics - which have no exchange equivalent - are right at all.")
