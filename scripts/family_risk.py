"""Two questions the census never asked about its own 46 buildable families.

1. WHICH FAMILIES BREAK OFF-CRYPTO?
   Measured 2026-08-25 across STOCKS, TRADFI, INDICES and COMMODITIES: those tickers
   are perps and carry funding, open interest, price, volume and structure zones. What
   they do NOT carry is the CVD family. Those columns render as an em-dash - and a null
   reads FALSE, never UNRESOLVED (cookbook trap 11). So a family built on CVD does not
   error on a stock, it silently gates FALSE.

2. WHICH FAMILIES CANNOT BE GATED?
   A column can render and still be unreferenceable. `nearestZoneRange` comes back with
   conditionOperators: [] - no operator at all. Categorical outputs carry only is/in, so
   they can be matched against a label but never thresholded. A family whose only output
   is categorical cannot express "more than X".

    python -m scripts.family_risk
"""
from __future__ import annotations

import json

from omega.contract import DERIVED_DIR

FAM = json.loads((DERIVED_DIR / "indicator_families.json").read_text(encoding="utf-8"))

# Measured null on STOCKS / TRADFI / INDICES / COMMODITIES, 2026-08-25.
#
# The rule is not "order flow is crypto-only" - it is sharper. EVERY metric the platform
# describes as accumulated since the daily 00:00-UTC anchor comes back null off-crypto,
# and every per-bar metric renders fine:
#
#   CVD      "cumulative volume delta accumulated since the daily 00:00-UTC anchor"  NULL
#   SPOT_CVD "listed venues summed, daily-anchored; crypto-only"                     NULL
#   OBV      "running signed volume sum since the daily 00:00-UTC anchor"            NULL
#   VWAP     "volume-weighted average price accumulated since the daily anchor"      NULL
#
#   BUY_VOLUME / SELL_VOLUME / BUY_TRADES / SELL_TRADES / BUY_PRESSURE   all RENDER
#   VOLUME / RVOL / SWING_HIGH / REGIME_* / STRUCT_ZONES / funding / OI  all RENDER
#
# An earlier draft guessed BUY_VOLUME and SELL_VOLUME were crypto-only because
# BUY_PRESSURE had been measured and they had not. The guess was wrong - they render.
# The daily-anchor pattern only became visible after testing them directly.
DAILY_ANCHORED = {"CVD", "SPOT_CVD", "OBV", "VWAP"}
VENUE_SPOT = {"SPOT_CLOSE_CB", "SPOT_CLOSE_BN"}
CRYPTO_ONLY = DAILY_ANCHORED | VENUE_SPOT | {
    "PERP_SPOT_FLOW", "PERP_SPOT_STRENGTH", "PERP_SPOT_CONFIRMS"}

NO_OPERATORS = {"nearestZoneRange"}
CATEGORICAL = {"classifyZone", "crossDetect", "bandTouch", "nearestZoneType"}
CATEGORICAL_METRICS = {"FUNDING_LABEL", "MA_ALIGN", "EMA_CROSS", "PRICE_ZONE",
                       "REGIME_TREND", "REGIME_VOL", "REGIME_MOM", "OI_PX_REGIME",
                       "PERP_SPOT_FLOW", "PERP_SPOT_STRENGTH", "PERP_SPOT_CONFIRMS",
                       "BB_TOUCH", "CROWD_PICK", "CROWD_PICK_LIVE"}


def gateability(spec: dict) -> str:
    """numeric | label-only | none - what a condition can do with this column."""
    t = spec.get("chainedTransformId") or spec["transformId"]
    if t in NO_OPERATORS:
        return "none"
    if t == "trajectory":
        return "numeric"          # slots are numeric even when _trend is categorical
    if t in CATEGORICAL:
        return "label-only"
    if t == "value" and spec["metric"] in CATEGORICAL_METRICS:
        return "label-only"
    return "numeric"


def main() -> int:
    off_crypto, ungateable, label_only = [], [], []
    for f in FAM["buildable"]:
        metrics = set()
        for s in f["columns"]:
            metrics.add(s["metric"])
            metrics |= {i["metric"] for i in s.get("inputs", [])}
        hit = metrics & CRYPTO_ONLY
        if hit:
            off_crypto.append((f["id"], sorted(hit)))

        gates = {gateability(s) for s in f["columns"]}
        if gates == {"none"}:
            ungateable.append(f["id"])
        elif "numeric" not in gates:
            label_only.append(f["id"])

    n = len(FAM["buildable"])
    print(f"BUILDABLE FAMILIES: {n}\n")

    print(f"1. BREAK OFF-CRYPTO - render null on STOCKS / TRADFI / INDICES / COMMODITIES")
    print(f"   {len(off_crypto)} of {n} families\n")
    for fid, hit in off_crypto:
        print(f"   {fid:<24} via {', '.join(hit)}")
    print("\n   These do not error. They render an em-dash, and a null reads FALSE.")
    print("   A strategy mixing crypto and non-crypto tickers gates these silently wrong.")
    print("\n   The pattern: every DAILY-ANCHORED accumulator is null off-crypto")
    print(f"   ({', '.join(sorted(DAILY_ANCHORED))}), plus the venue spot closes")
    print(f"   ({', '.join(sorted(VENUE_SPOT))}) and the perp-spot state metrics.")
    print("   Every per-bar metric renders - including BUY_VOLUME and SELL_VOLUME.")

    print(f"\n2. GATEABILITY")
    print(f"   ungateable (no operator at all) : {len(ungateable)}  {ungateable}")
    print(f"   label-only (is/in, no threshold): {len(label_only)}  {label_only}")
    print(f"   numeric-gateable                : {n - len(ungateable) - len(label_only)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
