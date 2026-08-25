"""Resolve the tier-C verdicts that were sample-limited rather than unverifiable.

`data/audit/tier_c_coherence.json` marked REGIME_TREND / REGIME_VOL / REGIME_MOM
"not verifiable" and flagged that all three coins in a 3-coin render read "trending up"
while all three had negative momentum. That was a real concern but the wrong conclusion:
three observations cannot distinguish "stuck" from "coincidence". This is the same
question against 30 coins.

    python -m scripts.regime_sample
"""
from __future__ import annotations

from collections import Counter

# Rendered 2026-08-25, 1h anchor, ranked ALL limit 30.
# coin, regTrend, regVol, regMom, ADX, atrPct, chg24h, zone, swingHi, swingLo, close
ROWS = [
    ("AAPL", "ranging", "normal", "bullish", 22.7, 0.37, -0.06, "near high", 313.45, 307.72, 310.55),
    ("AAVE", "trending up", "normal", "bearish", 28.9, 2.07, -1.17, "mid-range", 136.50, 124.58, 130.85),
    ("BRENTOIL", "trending down", "normal", "bearish", 44.3, 0.73, -3.12, "near low", 91.25, 87.30, 87.80),
    ("BTC", "trending up", "normal", "neutral", 23.1, 0.89, -0.07, "near low", 81299.00, 78553.00, 78943.00),
    ("CL", "trending down", "normal", "bearish", 45.8, 0.77, -3.41, "near low", 85.84, 81.81, 82.28),
    ("CRCL", "trending up", "normal", "diverging", 22.1, 1.71, 1.45, "mid-range", 90.09, 84.53, 88.96),
    ("DOGE", "trending up", "normal", "bearish", 13.8, 1.49, -0.78, "near low", 0.0932, 0.0886, 0.0894),
    ("ENA", "trending up", "normal", "bearish", 25.3, 2.59, -3.06, "mid-range", 0.1598, 0.1466, 0.1481),
    ("ETH", "trending up", "normal", "neutral", 18.6, 1.00, -0.45, "near low", 2532.50, 2452.90, 2470.60),
    ("EWY", "ranging", "normal", "bullish", 21.9, 0.80, 3.52, "near high", 180.02, 170.26, 179.28),
    ("FARTCOIN", "ranging", "normal", "bearish", 11.1, 3.04, -0.27, "mid-range", 0.1939, 0.1710, 0.1794),
    ("GOLD", "trending up", "normal", "bearish", 20.0, 0.37, -1.45, "near low", 4696.90, 4609.50, 4614.80),
    ("GOOGL", "ranging", "normal", "neutral", 18.0, 0.33, 0.35, "near high", 350.98, 347.19, 349.24),
    ("HYPE", "trending up", "normal", "bearish", 17.5, 1.53, 0.79, "mid-range", 82.00, 76.92, 79.63),
    ("META", "trending up", "normal", "bullish", 30.2, 0.39, 1.35, "near high", 568.74, 556.26, 567.71),
    ("MSTR", "trending up", "normal", "bearish", 24.6, 1.57, -0.16, "mid-range", 127.88, 118.84, 122.50),
    ("MU", "trending down", "normal", "bearish", 23.6, 1.06, 3.31, "mid-range", 946.61, 893.60, 933.48),
    ("NVDA", "trending down", "normal", "neutral", 36.8, 0.44, 1.72, "near high", 212.64, 207.74, 212.47),
    ("PUMP", "trending up", "normal", "bearish", 26.6, 3.11, -2.49, "mid-range", 0.0050, 0.0045, 0.0046),
    ("SILVER", "trending up", "normal", "bearish", 15.9, 0.75, -2.97, "near low", 69.94, 67.49, 67.65),
    ("SKHX", "trending up", "normal", "bearish", 28.0, 1.39, 5.64, "mid-range", 1239.60, 1130.60, 1224.80),
    ("SMSN", "ranging", "normal", "bearish", 26.0, 1.08, 4.09, "near high", 188.94, 177.71, 187.08),
    ("SNDK", "trending down", "normal", "bearish", 25.9, 1.61, 3.30, "mid-range", 1565.30, 1454.90, 1523.10),
    ("SOL", "trending up", "normal", "neutral", 30.9, 1.64, -1.13, "mid-range", 103.15, 95.37, 97.94),
    ("SP500", "ranging", "normal", "bullish", 24.3, 0.14, 0.33, "near high", 7694.20, 7642.40, 7677.90),
    ("TRUMP", "trending up", "normal", "bearish", 18.8, 2.92, -3.35, "mid-range", 2.53, 2.27, 2.31),
    ("TSLA", "trending up", "normal", "neutral", 47.8, 0.48, 0.62, "near high", 354.67, 347.85, 351.60),
    ("XRP", "trending up", "normal", "bearish", 14.7, 1.64, -1.18, "mid-range", 1.55, 1.45, 1.46),
    ("XYZ100", "trending down", "normal", "bullish", 25.0, 0.27, 0.92, "near high", 29327.00, 28932.00, 29274.00),
    ("ZEC", "trending up", "normal", "bearish", 23.1, 2.26, -0.93, "mid-range", 868.00, 797.13, 823.13),
]


def main() -> int:
    n = len(ROWS)
    trend = Counter(r[1] for r in ROWS)
    vol = Counter(r[2] for r in ROWS)
    mom = Counter(r[3] for r in ROWS)
    print(f"{n} coins\n")
    print("REGIME_TREND", dict(trend))
    print("REGIME_VOL  ", dict(vol))
    print("REGIME_MOM  ", dict(mom))

    print("\n--- the concern: is REGIME_TREND stuck? ---")
    print(f"  three distinct values appear, {trend.most_common(1)[0][1]}/{n} at the mode.")
    print("  NOT stuck. The earlier 3-of-3 'trending up' was small-sample coincidence.")

    print("\n--- but does its DIRECTION agree with price? ---")
    up = [r for r in ROWS if r[1] == "trending up"]
    dn = [r for r in ROWS if r[1] == "trending down"]
    up_neg = sum(1 for r in up if r[6] < 0)
    dn_pos = sum(1 for r in dn if r[6] > 0)
    print(f"  'trending up'   {len(up):>2} coins, {up_neg} with a NEGATIVE 24h change "
          f"({up_neg/len(up):.0%})")
    print(f"  'trending down' {len(dn):>2} coins, {dn_pos} with a POSITIVE 24h change "
          f"({dn_pos/len(dn):.0%})")
    agree = sum(1 for r in ROWS if r[1] == "trending up" and r[6] > 0) + \
            sum(1 for r in ROWS if r[1] == "trending down" and r[6] < 0)
    directional = len(up) + len(dn)
    print(f"  agreement with the 24h sign: {agree}/{directional} = {agree/directional:.0%}")
    print("  A label independent of 24h direction would sit near 50%. This is INVERTED.")
    print("  Not proof of a defect - REGIME_TREND's horizon is undocumented and a")
    print("  multi-day trend can oppose the last 24h - but it is the opposite of what")
    print("  a naive reading of the label predicts, on 24 directional coins.")

    print("\n--- REGIME_VOL ---")
    ap = sorted(r[5] for r in ROWS)
    print(f"  every one of {n} coins reads 'normal'.")
    print(f"  atrPct spans {ap[0]:.2f}% to {ap[-1]:.2f}% - a {ap[-1]/ap[0]:.0f}x range.")
    print("  Consistent with a per-coin-relative measure where nothing is currently")
    print("  extreme, and also consistent with a value that never changes. 30 coins at")
    print("  one instant cannot separate those two. Needs a repeat on another day.")

    print("\n--- PRICE_ZONE: pinning the band ---")
    rows = [(r[0], r[7], (r[10] - r[9]) / (r[8] - r[9])) for r in ROWS]
    for label in ("near low", "mid-range", "near high"):
        vals = [p for _, z, p in rows if z == label]
        if vals:
            print(f"  {label:<10} n={len(vals):>2}  position "
                  f"{min(vals):.1%} .. {max(vals):.1%}")
    lo_hi = max(p for _, z, p in rows if z == "near low")
    mid_lo = min(p for _, z, p in rows if z == "mid-range")
    mid_hi = max(p for _, z, p in rows if z == "mid-range")
    hi_lo = min(p for _, z, p in rows if z == "near high")
    print(f"\n  near-low / mid boundary lies in ({lo_hi:.1%}, {mid_lo:.1%})")
    print(f"  mid / near-high boundary lies in ({mid_hi:.1%}, {hi_lo:.1%})")
    print("  Neither 'breakout high' nor 'breakdown low' appears in 30 coins, so those")
    print("  two labels of the five remain unobserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
