"""Build the TPO strategy suite S1-S7 as validated, submit-ready payloads.

PREPARE, NEVER EXECUTE (docs/20, decision P4).
    This script makes ZERO live calls and writes NOTHING to the platform. It emits
    JSON payloads to out/tpo_suite/. Compiling, applying and binding are separate,
    human-initiated acts, each per-instance authorised.

EVERY NUMBER'S PROVENANCE IS RECORDED
    Each condition carries a thresholdBasis string. There are exactly two honest
    categories and this file uses only those: MEASURED (cite the measurement) or
    INVENTED (say so). Nothing is dressed up.

WHY THE COIN LIST IS EXPLICIT AND NOT RANKED
    preview_strategy_report accepts ranked limit 50 - the panel logger uses it. The
    COMPILE path does not: the measured BG-14 ceiling is ranked limit 4 (README,
    2026-08-28), so a realistic ranked universe cannot compile. Explicit lists are the
    only way to carry breadth into a saved strategy. Schema cap is 50; we carry 36.

USAGE
    python scripts/tpo_suite_build.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omega.conditions import (  # noqa: E402
    all_of, between, condition, in_, num, ref, report_headers, validate_conditions,
)
from omega.types import Column, CustomSection, Report  # noqa: E402
from omega.validate import validate_report  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "tpo_suite")

# One fixed section key so conditions can address headers without a compile-first
# round trip. The server accepts a caller-supplied custom:<uuid> (docs/09).
SK = "custom:7b0d4a1e-9c3f-4a52-8e61-2f5c8d0a4b77"

ANCHOR = "1h"

# --- thresholds, with provenance ------------------------------------------------
# The 5-bps bin floor. The vendor bins price at 5 bps, so anything finer measures
# quantisation rather than structure. MEASURED (vendor text, 2026-09-10).
BIN = 0.05
# Prior value-area width gate. MEASURED as the p25 of 36 CRYPTO coins at
# 2026-09-10T12:21Z (min 1.01, p25 2.06, median 3.19, p75 5.07, max 8.78).
# This is ONE SNAPSHOT, not a calibration - it is a starting point that at least
# excludes something, unlike the 1.00 first drafted, which excluded 0 of 36.
WIDTH_P25 = 2.06
# RSI midline for the persistence leg. INVENTED.
RSI_MID = 50.0

# 36 CRYPTO tickers observed in the 2026-09-10T12:21Z ranked panel pull.
COINS = [
    "AAVE", "AIXBT", "APT", "AVAX", "BNB", "BTC", "CAKE", "CRV", "DOGE", "ENA",
    "ETH", "FARTCOIN", "GRAM", "HYPE", "JUP", "LDO", "LINK", "LTC", "MELANIA",
    "MET", "MOODENG", "PENGU", "PEPE", "POPCAT", "PUMP", "PURR", "SHIB", "SNX",
    "SOL", "SUI", "TRUMP", "UNI", "WIF", "WLFI", "XRP", "ZEC",
]


def c(metric, transform, operand=None, **kw):
    col = {"metric": metric, "transformId": transform, "timeframe": {"rel": "anchor"}}
    if operand:
        col["inputs"] = [{"metric": operand}]
    col.update(kw)
    return Column(**col)


# --- the spine: six columns, every one never-null -------------------------------
# Each pairs a PRIOR_TPO base (refreshes 00:00 UTC, never null) with a candle
# operand (never null), or two prior legs. Nothing here goes dark at any hour.
SPINE = [
    c("PRIOR_TPO_VAH", "spread", "CLOSE"),        # pTpoVAH_close_spread
    c("PRIOR_TPO_VAL", "spread", "CLOSE"),        # pTpoVAL_close_spread
    c("PRIOR_TPO_VAH", "spread", "OPEN"),         # pTpoVAH_open_spread   <- origin
    c("PRIOR_TPO_VAL", "spread", "OPEN"),         # pTpoVAL_open_spread   <- origin
    c("PRIOR_TPO_POC", "spread", "CLOSE"),        # pTpoPOC_close_spread  <- target
    c("PRIOR_TPO_VAH", "spread", "PRIOR_TPO_VAL"),  # pTpoVAH_pTpoVAL_spread <- room
]

# Sign convention, stated once so every clause below can be checked against it:
#   spread = (base - operand) / operand * 100
#   POSITIVE  =>  the BASE LEVEL sits ABOVE the operand.
# So pTpoVAL_close_spread > 0 means the close is BELOW prior VAL.

LOC = [
    condition("ABOVE_PRIOR_VALUE", "Close above the prior value area",
              num("pTpoVAH_close_spread", "lte", -BIN, section_key=SK),
              verdict="NEITHER"),
    condition("INSIDE_PRIOR_VALUE", "Close inside the prior value area",
              all_of(num("pTpoVAH_close_spread", "gte", BIN, section_key=SK),
                     num("pTpoVAL_close_spread", "lte", -BIN, section_key=SK)),
              verdict="NEITHER"),
    condition("BELOW_PRIOR_VALUE", "Close below the prior value area",
              num("pTpoVAL_close_spread", "gte", BIN, section_key=SK),
              verdict="NEITHER"),
]

REENTRY = [
    condition("VALUE_REENTRY_UP", "Opened below prior value, closed back inside",
              all_of(num("pTpoVAL_open_spread", "gte", BIN, section_key=SK),
                     num("pTpoVAL_close_spread", "lte", -BIN, section_key=SK)),
              verdict="UP"),
    condition("VALUE_REENTRY_DOWN", "Opened above prior value, closed back inside",
              all_of(num("pTpoVAH_open_spread", "lte", -BIN, section_key=SK),
                     num("pTpoVAH_close_spread", "gte", BIN, section_key=SK)),
              verdict="DOWN"),
]

TARGET = [
    condition("POC_AHEAD_UP", "Prior POC still above the close - rotation has room",
              num("pTpoPOC_close_spread", "gte", BIN, section_key=SK), verdict=None),
    condition("POC_AHEAD_DOWN", "Prior POC still below the close - rotation has room",
              num("pTpoPOC_close_spread", "lte", -BIN, section_key=SK), verdict=None),
    condition("POC_REACHED", "Close is at the prior point of control",
              between("pTpoPOC_close_spread", -BIN, BIN, section_key=SK),
              verdict="NEITHER"),
]

WIDE = condition("WIDE_ENOUGH", "Prior value area wide enough to be worth rotating",
                 num("pTpoVAH_pTpoVAL_spread", "gte", WIDTH_P25, section_key=SK),
                 verdict=None)

# The persistence leg. TPO cannot carry it: closes>1 needs the CLOSE clock and the
# CLOSE clock is refused on every TPO header. RSI14 is used because it is the ONE
# candle metric measured end to end this session - header `RSI14`,
# closeClockReadable true, and closes:2 returning closeClock {closesHeld:2,
# closesRequired:2, nextCloseAt}. An earlier draft named close_EMA21_spread, a
# header nobody had rendered; that is exactly the assumption this file exists to
# avoid.
HELD = [
    condition("RSI_HELD_UP_2C", "Momentum above the midline for two closed bars",
              num("RSI14", "gt", RSI_MID, section_key=SK),
              verdict=None, clock="CLOSE", closes=2),
    condition("RSI_HELD_DOWN_2C", "Momentum below the midline for two closed bars",
              num("RSI14", "lt", RSI_MID, section_key=SK),
              verdict=None, clock="CLOSE", closes=2),
]

CONFIRMED = [
    condition("REENTRY_CONFIRMED_UP", "Re-entered value and momentum held two closes",
              all_of(ref("VALUE_REENTRY_UP"), ref("RSI_HELD_UP_2C")), verdict="UP"),
    condition("REENTRY_CONFIRMED_DOWN", "Re-entered value and momentum held two closes",
              all_of(ref("VALUE_REENTRY_DOWN"), ref("RSI_HELD_DOWN_2C")), verdict="DOWN"),
]

# S6: the nearest lawful expression of "did the POC act as support". It establishes
# that the level was crossed and recrossed INSIDE ONE BAR and nothing more - OHLC
# carries no intrabar sequence, so a defence and a failed breakout are
# indistinguishable here. Named honestly for that reason.
POC_DEFENCE = [
    condition("POC_CROSSED_RECROSSED_UP", "One bar: opened above the POC, traded below it, closed back above",
              all_of(num("pTpoPOC_open_spread", "lte", -BIN, section_key=SK),
                     num("pTpoPOC_low_spread", "gte", BIN, section_key=SK),
                     num("pTpoPOC_close_spread", "lte", -BIN, section_key=SK)),
              verdict="UP"),
    condition("POC_CROSSED_RECROSSED_DOWN", "One bar: opened below the POC, traded above it, closed back below",
              all_of(num("pTpoPOC_open_spread", "gte", BIN, section_key=SK),
                     num("pTpoPOC_high_spread", "lte", -BIN, section_key=SK),
                     num("pTpoPOC_close_spread", "gte", BIN, section_key=SK)),
              verdict="DOWN"),
]

DEVELOPING = [
    condition("VALUE_MIGRATING_UP", "Developing POC above the prior POC",
              num("tpoPOC_pTpoPOC_spread", "gte", BIN, section_key=SK), verdict="NEITHER"),
    condition("VALUE_MIGRATING_DOWN", "Developing POC below the prior POC",
              num("tpoPOC_pTpoPOC_spread", "lte", -BIN, section_key=SK), verdict="NEITHER"),
    condition("SHAPE_P", "Developing POC skewed to the top of value",
              in_("tpoShape", ["p-shape"], section_key=SK), verdict="NEITHER"),
    condition("SHAPE_B", "Developing POC skewed to the bottom of value",
              in_("tpoShape", ["b-shape"], section_key=SK), verdict="NEITHER"),
]

SUITE = [
    dict(id="S1", name="Value Location",
         thesis="Where the close sits against the previous completed UTC session's value area. No direction claimed.",
         extra=[], conds=LOC,
         teaches="The spine renders, the signs are right, and a TPO condition reaches only the report.",
         null="ZERO - every column pairs a prior-session base with a candle operand."),
    dict(id="S2", name="Value Re-Entry",
         thesis="Price that was outside prior value at the bar's open and is back inside at its close.",
         extra=[], conds=LOC + REENTRY,
         teaches="Whether the re-entry geometry ever fires at all. It has never been observed TRUE.",
         null="ZERO."),
    dict(id="S3", name="Rotation Target",
         thesis="Re-entry, plus whether the prior POC is still ahead of price or already behind it.",
         extra=[], conds=LOC + REENTRY + TARGET,
         teaches="Separates a setup from a completed rotation.",
         null="ZERO."),
    dict(id="S4", name="Width Regime",
         thesis="Stand down when the prior value area is too narrow for the rotation to pay.",
         extra=[], conds=LOC + REENTRY + TARGET + [WIDE],
         teaches="The only never-null TPO regime read available.",
         null="ZERO."),
    dict(id="S5", name="Confirmed Re-Entry",
         thesis="Re-entry that survived two closed bars of momentum, joined by conditionRef across clocks.",
         extra=[c("RSI14", "value")], conds=LOC + REENTRY + HELD + CONFIRMED,
         teaches="The split-clock composition, and the only leg in the suite that can persist.",
         null="RSI14 warm-up only - null until 14 anchor bars exist."),
    dict(id="S6", name="POC Cross-Recross",
         thesis="One bar that crossed the prior POC and closed back on its original side.",
         extra=[c("PRIOR_TPO_POC", "spread", "OPEN"),
                c("PRIOR_TPO_POC", "spread", "LOW"),
                c("PRIOR_TPO_POC", "spread", "HIGH")],
         conds=LOC + POC_DEFENCE,
         teaches="The nearest lawful reading of 'the POC acted as support'. It cannot distinguish a defence from a failed breakout.",
         null="ZERO."),
    dict(id="S7", name="Developing Value",
         thesis="Today's developing POC and profile skew against the previous completed session.",
         extra=[c("TPO_POC", "spread", "PRIOR_TPO_POC"),
                c("TPO_VAH", "spread", "TPO_VAL"),
                c("TPO_SHAPE", "value")],
         conds=LOC + DEVELOPING,
         teaches="Whether developing-vs-prior carries information beyond time-of-day.",
         null="SEVERE - all three added columns are null 00:00-01:00 UTC, and the developing area is "
              "structurally narrow all morning (measured 40-48% of prior width at the 12:00 midpoint). "
              "A silent FALSE both ways. Every condition here is verdict NEITHER so it cannot flip a direction."),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    total_err = 0
    print("%-4s %-22s %5s %5s %6s  %s" % ("id", "name", "cols", "conds", "errors", "status"))
    print("-" * 78)
    manifest = []
    for s in SUITE:
        section = CustomSection(
            title=("TPO " + s["name"])[:60], sectionKey=SK, benchmarkTicker=None,
            notes=(s["thesis"])[:400], columns=SPINE + s["extra"],
        )
        report = Report(anchor=ANCHOR, sections=[section])

        vr = validate_report(report)
        rep_errs = [f for f in vr.findings if f.severity == "error"]
        cf = validate_conditions(report, s["conds"])
        cond_errs = [f for f in cf if f.severity == "error"]
        warns = [f for f in cf if f.severity == "warning"]
        nerr = len(rep_errs) + len(cond_errs)
        total_err += nerr

        status = "OK" if nerr == 0 else "BLOCKED"
        print("%-4s %-22s %5d %5d %6d  %s" % (
            s["id"], s["name"], len(section.columns), len(s["conds"]), nerr, status))
        for f in rep_errs:
            print("      [report error] %s" % (f,))
        for f in cond_errs:
            print("      %s" % (f,))
        for f in warns:
            print("      %s" % (f,))

        payload = {
            "_what": "Submit-ready TPO strategy payload. NOT compiled, NOT applied, NOT bound.",
            "_provenance": "scripts/tpo_suite_build.py, contract 54.1.0, measured 2026-09-10",
            "id": s["id"], "name": s["name"], "thesis": s["thesis"],
            "teaches": s["teaches"], "nullExposure": s["null"],
            "anchor": ANCHOR,
            "coinSelection": {"mode": "explicit", "tickers": COINS},
            "sections": report.wire(),
            "conditions": s["conds"],
            "predictedHeaders": sorted(report_headers(report).keys()),
            "thresholds": {
                "BIN": {"value": BIN, "basis": "MEASURED - vendor bins price at 5 bps"},
                "WIDTH_P25": {"value": WIDTH_P25,
                              "basis": "MEASURED - p25 of 36 CRYPTO coins at 2026-09-10T12:21Z. "
                                       "ONE SNAPSHOT, not a calibration."},
                "RSI_MID": {"value": RSI_MID, "basis": "INVENTED"},
            },
            "validation": {"reportErrors": [str(f) for f in rep_errs],
                           "conditionErrors": [str(f) for f in cond_errs],
                           "warnings": [str(f) for f in warns]},
        }
        path = os.path.join(OUT, s["id"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1)
        manifest.append({"id": s["id"], "name": s["name"], "file": s["id"] + ".json",
                         "columns": len(section.columns), "conditions": len(s["conds"]),
                         "errors": nerr})

    with open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"suite": manifest, "anchor": ANCHOR, "sectionKey": SK,
                   "coins": COINS, "totalErrors": total_err}, f, indent=1)

    print("-" * 78)
    print("payloads -> %s" % OUT)
    print("total errors: %d" % total_err)
    if total_err:
        print("BLOCKED - payloads with errors are written but must not be compiled.")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
