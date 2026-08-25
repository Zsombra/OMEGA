"""Resolve the flow-block tier-C verdicts that were sample-limited.

`tier_c_coherence.json` marked SMART_RETAIL, CONFIDENCE and PERP_SPOT_* "not
verifiable" because a two-coin render carried no discriminating case. That was true of
the sample, not of the metrics. This is 25 crypto coins.

    python -m scripts.flow_sample
"""
from __future__ import annotations

from collections import Counter

# Rendered 2026-08-25, 1h anchor, ranked CRYPTO limit 25.
# coin, perpSpotFlow, perpSpotStr, perpSpotConf, smartRetail, flowAlign, conf,
# oiVel, oiRegime, upBias%, buyPres, chg1h%
ROWS = [
    ("AAVE", "neutral", "low", "false", "confirmed", "divergent", "moderate", "accelerating", "new longs", 80.0, 0.70, 0.49),
    ("AVAX", "neutral", "high", "false", "hidden accumulation", "aligned bearish", "moderate", "decelerating", "long liquidation", 28.6, 0.62, -0.41),
    ("BNB", "neutral", "low", "false", "confirmed", "aligned bearish", "moderate", "decelerating", "new shorts", 0.0, 0.12, -0.41),
    ("BTC", "neutral", "moderate", "false", None, "aligned bearish", "moderate", "decelerating", "new shorts", 20.0, 0.47, -0.36),
    ("CRV", "neutral", "high", "false", "hidden distribution", "divergent", "moderate", "decelerating", "long liquidation", 83.3, 0.28, -2.02),
    ("DOGE", "spot_led_accumulation", "high", "false", None, "aligned bearish", "high", "accelerating", "long liquidation", 37.5, 0.55, -1.09),
    ("ENA", "neutral", "high", "false", "hidden distribution", "divergent", "moderate", "decelerating", "long liquidation", 66.7, 0.34, -1.05),
    ("ETH", "neutral", "moderate", "false", None, "aligned bearish", "high", "decelerating", "new shorts", 40.0, 0.44, -0.32),
    ("FARTCOIN", "neutral", "low", "false", None, "aligned bearish", "high", "accelerating", "new shorts", 22.2, 0.56, -0.78),
    ("GRAM", "neutral", "low", "false", "hidden distribution", "aligned bullish", "moderate", "accelerating", "long liquidation", 100.0, 0.25, -1.58),
    ("HYPE", "spot_led_accumulation", "moderate", "false", None, "neutral", "moderate", "decelerating", "long liquidation", 50.0, 0.41, -0.49),
    ("JUP", "spot_led_accumulation", "moderate", "false", None, "neutral", "moderate", "decelerating", "long liquidation", 50.0, 0.53, -2.44),
    ("LDO", "neutral", "low", "false", "hidden distribution", "divergent", "high", "accelerating", "new shorts", 80.0, 0.36, -0.89),
    ("LINK", "neutral", "high", "false", None, "divergent", "moderate", "accelerating", "new shorts", 60.0, 0.25, -1.11),
    ("LTC", "neutral", "low", "false", None, "aligned bearish", "high", "decelerating", "long liquidation", 33.3, 0.53, -0.60),
    ("PENGU", "neutral", "high", "false", "hidden accumulation", "divergent", "high", "decelerating", "short covering", 0.0, 0.86, 1.38),
    ("PEPE", "neutral", "moderate", "false", None, "divergent", "moderate", "decelerating", "long liquidation", 40.0, 0.11, -1.00),
    ("PUMP", "neutral", "low", "false", "hidden distribution", "divergent", "high", "decelerating", "long liquidation", 100.0, 0.40, -3.28),
    ("PURR", None, None, None, "hidden distribution", "divergent", "moderate", "decelerating", "long liquidation", 87.5, 0.38, -2.04),
    ("SOL", "neutral", "low", "false", "confirmed", "divergent", "high", "decelerating", "long liquidation", 22.2, 0.37, -0.99),
    ("SUI", "neutral", "low", "false", None, "aligned bearish", "moderate", "decelerating", "new shorts", 42.9, 0.35, -1.32),
    ("TRUMP", "neutral", "high", "false", "hidden distribution", "divergent", "moderate", "accelerating", "long liquidation", 75.0, 0.30, -2.16),
    ("UNI", "spot_led_accumulation", "low", "false", None, "divergent", "moderate", "decelerating", "new longs", 87.5, 0.55, 0.22),
    ("XRP", "neutral", "high", "false", None, "aligned bearish", "high", "accelerating", "new shorts", 25.0, 0.49, -1.06),
    ("ZEC", "neutral", "high", "false", "confirmed", "divergent", "moderate", "decelerating", "long liquidation", 0.0, 0.35, -2.93),
]
SR, FA, UP, BP = 4, 5, 9, 10


def main() -> int:
    print(f"{len(ROWS)} crypto coins\n")
    for i, name in ((1, "perpSpotFlow"), (2, "perpSpotStr"), (3, "perpSpotConf"),
                    (4, "smartRetail"), (5, "flowAlign"), (6, "conf"), (7, "oiVel"),
                    (8, "oiRegime")):
        print(f"  {name:<14} {dict(Counter(r[i] for r in ROWS))}")

    print("\n--- SMART_RETAIL: flow pressure vs crowd bias ---")
    print("  hypothesis: buyPres>0.5 is bullish flow, upBias>50 is bullish crowd.")
    print("  agree -> confirmed; flow bull + crowd bear -> hidden accumulation;")
    print("  flow bear + crowd bull -> hidden distribution.\n")
    hits = miss = 0
    for r in ROWS:
        if r[SR] is None:
            continue
        fb, cb = r[BP] > 0.5, r[UP] > 50
        want = "confirmed" if fb == cb else (
            "hidden accumulation" if fb else "hidden distribution")
        ok = want == r[SR]
        hits, miss = hits + ok, miss + (not ok)
        if not ok:
            print(f"    MISS {r[0]:<9} buyPres {r[BP]:.2f} upBias {r[UP]:>5.1f}%  "
                  f"predicted {want!r} got {r[SR]!r}")
    print(f"  {hits} of {hits+miss} non-null cases fit.")

    nulls = [r for r in ROWS if r[SR] is None]
    print(f"\n  and the {len(nulls)} nulls - how close to neutral are they?")
    dist = lambda r: min(abs(r[BP] - 0.5) * 2, abs(r[UP] - 50) / 50)
    nd = sorted(dist(r) for r in nulls)
    vd = sorted(dist(r) for r in ROWS if r[SR] is not None)
    print(f"    null      : neutrality distance {nd[0]:.2f} .. {nd[-1]:.2f}")
    print(f"    non-null  : neutrality distance {vd[0]:.2f} .. {vd[-1]:.2f}")
    print("    -> nulls sit nearer neutral on the weaker of the two axes, so the label")
    print("       needs BOTH sides far enough from neutral. The exact cut is bracketed,")
    print("       not pinned: the ranges overlap.")

    print("\n--- FLOW_ALIGN, same two inputs ---")
    ok = 0
    for r in ROWS:
        fb, cb = r[BP] > 0.5, r[UP] > 50
        want = ("aligned bullish" if fb and cb else
                "aligned bearish" if not fb and not cb else "divergent")
        ok += want == r[FA]
    print(f"  {ok} of {len(ROWS)} fit the same rule -> FLOW_ALIGN does NOT use buyPres")
    print("  and upBias the way SMART_RETAIL does. AVAX is the clean counterexample:")
    print("  buyPres 0.62 (bullish) with upBias 28.6% (bearish) is a divergence, and")
    print("  SMART_RETAIL calls it 'hidden accumulation' - but FLOW_ALIGN says")
    print("  'aligned bearish'. Two metrics on the same pair of inputs disagreeing")
    print("  means FLOW_ALIGN reads a different flow proxy, most likely CVD direction.")

    print("\n--- constants: values that never varied in 25 coins ---")
    for i, name in ((3, "perpSpotConf"),):
        vals = {r[i] for r in ROWS if r[i] is not None}
        print(f"  {name:<14} {vals}  <- only one value observed")
    for i, name, vocab in (
            (1, "perpSpotFlow", {"confirmed_bull", "confirmed_bear", "perp_led_fragile",
                                 "spot_led_accumulation", "neutral"}),
            (6, "conf", {"high", "moderate", "low"}),
            (7, "oiVel", {"accelerating", "decelerating", "steady"})):
        seen = {r[i] for r in ROWS if r[i] is not None}
        print(f"  {name:<14} unobserved labels: {sorted(vocab - seen) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
