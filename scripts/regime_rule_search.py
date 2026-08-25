"""Search for REGIME_TREND's rule over every operand the contract actually exposes.

Task 2 of the plan. The method is the one that cracked PRICE_ZONE: instead of guessing
one or two hypotheses and concluding "unidentified" when they fail, enumerate every
candidate the available columns can express and score them all - then report the best fit
AND its margin, so a weak winner is visible as weak.

Operands available beside REGIME_TREND in a single render: MA_ALIGN (price stacked
against EMA20/SMA20/SMA50), ADX, and dist_SMA20. That is the whole toolkit. If none of
them explains the label, the honest conclusion is that REGIME_TREND reads something the
column layer does not expose - which is a different statement from "we could not be
bothered".

    python -m scripts.regime_rule_search
"""
from __future__ import annotations

import itertools
from collections import Counter

# 4h anchor, 78 coins, 2026-08-25. (coin, regTrend, regMom, MAalign, ADX, distSMA20)
ROWS = [
    ("AAPL","ranging","bullish","mixed",16.4,-0.01),("AAVE","trending up","bullish","mixed",35.1,-1.75),
    ("AIXBT","trending up","bullish","mixed",31.7,-1.02),("AMD","ranging","bearish","mixed",37.0,1.94),
    ("AMZN","ranging","bearish","mixed",23.2,0.22),("APT","trending down","bullish","mixed",16.5,-4.40),
    ("AVAX","trending up","bullish","mixed",24.4,-0.76),("BABA","ranging","neutral","mixed",31.2,1.24),
    ("BNB","trending up","bullish","mixed",61.4,-0.09),("BRENTOIL","ranging","bullish","mixed",37.5,-4.13),
    ("BTC","trending up","bullish","mixed",57.4,1.32),("CAKE","trending up","bullish","mixed",47.6,0.37),
    ("CL","ranging","bullish","bearish",35.2,-3.65),("COIN","ranging","bullish","mixed",28.5,1.51),
    ("COPPER","trending up","neutral","bullish",30.4,1.79),("CRCL","trending up","diverging","mixed",33.6,3.34),
    ("CRV","trending up","bullish","mixed",18.8,-1.68),("CRWV","ranging","bearish","mixed",28.6,1.62),
    ("DOGE","trending up","bullish","mixed",33.3,-2.55),("ENA","trending up","bullish","mixed",52.9,-3.39),
    ("ETH","trending up","diverging","mixed",49.2,0.62),("EUR","trending up","bullish","mixed",36.7,-0.13),
    ("EWJ","ranging","bearish","mixed",18.4,0.24),("EWY","ranging","bullish","mixed",18.3,0.89),
    ("FARTCOIN","trending up","diverging","mixed",24.3,-0.34),("GOLD","trending up","diverging","mixed",25.3,0.19),
    ("GOOGL","ranging","bearish","bullish",25.3,0.37),("GRAM","trending down","neutral","mixed",23.4,-0.80),
    ("HIMS","ranging","bullish","mixed",36.4,-1.39),("HOOD","ranging","diverging","mixed",29.9,3.40),
    ("HYPE","trending up","bullish","mixed",48.2,2.25),("INTC","ranging","bearish","mixed",43.8,-0.71),
    ("JP225","ranging","bearish","mixed",24.3,0.35),("JPY","trending down","bullish","bullish",26.4,0.09),
    ("JUP","trending down","bullish","bullish",37.4,1.81),("LDO","trending up","bullish","mixed",35.1,-0.45),
    ("LINK","trending up","bullish","mixed",30.2,-0.34),("LTC","trending up","bullish","mixed",41.0,-1.86),
    ("MELANIA","trending up","bullish","mixed",57.2,-1.58),("MET","trending up","bullish","mixed",39.1,-5.74),
    ("META","ranging","bearish","bullish",32.8,2.06),("MOODENG","ranging","bullish","mixed",18.1,-3.08),
    ("MSFT","trending up","neutral","bullish",20.1,0.90),("MSTR","trending up","bullish","bullish",42.7,4.71),
    ("MU","ranging","bearish","bearish",33.8,-1.84),("NATGAS","ranging","bullish","mixed",16.6,0.25),
    ("NFLX","trending up","bullish","bullish",19.1,2.91),("NVDA","ranging","bearish","bearish",32.3,-0.93),
    ("ORCL","ranging","bearish","mixed",18.0,-0.33),("PALLADIUM","ranging","bearish","mixed",13.3,-0.93),
    ("PENGU","trending up","bullish","mixed",43.5,4.68),("PEPE","trending up","bullish","mixed",38.1,-2.19),
    ("PLATINUM","trending up","bullish","mixed",25.0,-1.24),("PLTR","trending up","neutral","mixed",30.5,-2.33),
    ("POPCAT","ranging","bullish","bullish",42.3,4.59),("PUMP","trending up","bullish","mixed",24.4,-7.77),
    ("PURR","trending up","bullish","bullish",55.7,5.81),("RIVN","ranging","diverging","mixed",53.0,0.24),
    ("SHIB","trending up","bullish","mixed",30.3,-0.01),("SILVER","trending up","bullish","mixed",23.7,-0.21),
    ("SKHX","ranging","bullish","mixed",22.6,-0.62),("SMSN","ranging","bullish","bearish",24.1,-1.03),
    ("SNDK","ranging","bearish","bearish",33.0,-4.05),("SNX","ranging","bullish","mixed",35.4,1.22),
    ("SOL","trending up","diverging","mixed",45.4,2.15),("SP500","ranging","bearish","mixed",18.8,0.08),
    ("SUI","trending up","bullish","mixed",30.0,-3.46),("TRUMP","trending up","bullish","mixed",49.4,-7.31),
    ("TSLA","ranging","bullish","mixed",23.7,-0.51),("TSM","ranging","bearish","mixed",17.4,-0.12),
    ("UNI","trending up","bullish","mixed",33.6,0.13),("URNM","trending up","bullish","mixed",36.8,3.00),
    ("USAR","ranging","bearish","mixed",22.9,0.18),("WIF","trending up","bullish","mixed",53.7,-1.28),
    ("WLFI","trending up","diverging","mixed",36.6,1.13),("XRP","trending up","bullish","mixed",70.6,-0.89),
    ("XYZ100","ranging","bearish","mixed",40.6,-0.05),("ZEC","trending up","bullish","mixed",56.7,-3.05),
]
TREND, MOM, ALIGN, ADX, DSMA = 1, 2, 3, 4, 5


def baseline(idx):
    """Always predicting the most common label - the floor any rule must beat."""
    c = Counter(r[idx] for r in ROWS)
    return c.most_common(1)[0][1] / len(ROWS), c.most_common(1)[0][0]


def score(fn, idx):
    return sum(fn(r) == r[idx] for r in ROWS) / len(ROWS)


def main() -> int:
    n = len(ROWS)
    base, common = baseline(TREND)
    print(f"{n} coins, 4h anchor\n")
    print(f"REGIME_TREND distribution: {dict(Counter(r[TREND] for r in ROWS))}")
    print(f"baseline - always say {common!r}: {base:.0%}\n")

    cands = []
    # MA_ALIGN mapped onto the trend vocabulary, every permutation
    labels = ["trending up", "trending down", "ranging"]
    for perm in itertools.permutations(labels):
        m = dict(zip(["bullish", "bearish", "mixed"], perm))
        cands.append((f"MA_ALIGN -> {perm[0]}/{perm[1]}/{perm[2]}",
                      lambda r, m=m: m[r[ALIGN]]))
    # ADX thresholds: ranging below, direction from dist_SMA20 above
    for t in (15, 20, 25, 30, 35, 40):
        cands.append((f"ADX<{t} ranging, else sign(dist_SMA20)",
                      lambda r, t=t: "ranging" if r[ADX] < t else
                      ("trending up" if r[DSMA] > 0 else "trending down")))
        cands.append((f"ADX<{t} ranging, else sign(MA_ALIGN)",
                      lambda r, t=t: "ranging" if r[ADX] < t else
                      ("trending up" if r[ALIGN] == "bullish" else
                       "trending down" if r[ALIGN] == "bearish" else "ranging")))
    # dist_SMA20 bands
    for t in (0.0, 0.5, 1.0, 2.0):
        cands.append((f"|dist_SMA20|<{t} ranging, else its sign",
                      lambda r, t=t: "ranging" if abs(r[DSMA]) < t else
                      ("trending up" if r[DSMA] > 0 else "trending down")))

    scored = sorted(((score(f, TREND), name) for name, f in cands), reverse=True)
    print("best candidate rules for REGIME_TREND:")
    for s, name in scored[:6]:
        flag = "  <- beats baseline" if s > base else ""
        print(f"  {s:>6.0%}  {name}{flag}")
    top, runner = scored[0][0], scored[1][0]
    print(f"\n  best {top:.0%} vs baseline {base:.0%} vs runner-up {runner:.0%}")
    if top <= base + 0.05:
        print("  NO candidate meaningfully beats simply always predicting the mode.")
        print("  REGIME_TREND reads something the column layer does not expose.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
