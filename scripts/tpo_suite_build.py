"""Build the TPO strategy suite S1-S7: a design record AND a wire body per strategy.

PREPARE, NEVER EXECUTE (docs/20, decision P4).
    This script makes ZERO live calls and writes NOTHING to the platform. It emits
    JSON files to out/tpo_suite/. Compiling, applying and binding are separate,
    human-initiated acts, each per-instance authorised.

TWO FILES PER STRATEGY, BECAUSE ONE FILE CANNOT BE BOTH (measured 2026-09-11)
    <id>.json       the DESIGN RECORD: thesis, what it teaches, null exposure, threshold
                    provenance, predicted headers, offline validation. Human-facing.
    <id>.wire.json  the exact compile_strategy_plan CREATE request body and nothing
                    else. This is what the preflight diffs and what a compile is sent.
    Until 2026-09-11 this script emitted only the first file and called it
    "submit-ready". Run through scripts/preflight.py against a fresh schema capture it
    FAILED on every strategy: five required wire fields missing (operation,
    intentSummary, assumptions, timeframe, entry) and ten undeclared annotation keys.
    It had passed omega's offline validation with zero errors, which is the trap named
    at SK below - offline validation is this repo's MODEL of the contract, not the
    server. The assumption that the payloads were compile-ready had never been RUN.

EVERY NUMBER'S PROVENANCE IS RECORDED
    Each condition carries a thresholdBasis string. There are exactly two honest
    categories and this file uses only those: MEASURED (cite the measurement) or
    INVENTED (say so). Nothing is dressed up.

WHY THE COIN LIST IS EXPLICIT AND NOT RANKED
    preview_strategy_report accepts ranked limit 50 - the panel logger uses it. The
    COMPILE path does not: the measured BG-14 ceiling is ranked limit 4 (README,
    2026-08-28), so a realistic ranked universe cannot compile. Explicit lists are the
    only way to carry breadth into a saved strategy. The schema cap is 50 but the 256 KB
    report-preview cap binds far earlier - see COINS below. We carry 8.

NOT ALL OF THESE ARE WORTH CREATING, AND THIS FILE DOES NOT DECIDE THAT
    S1 and S7 emit only NEITHER verdicts, so neither can produce a direction. S2's
    re-entry geometry (bar opened outside prior value, closed inside) has been observed
    firing ZERO times across two days of probing, and S3 and S5 both lean on it. None of
    the seven carries a rules array, so all seven are annotation-only and cannot route at
    any gate. Emitting a legal payload is not the same as it being worth a quota slot.

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

# SECTION KEY: None, and that is load-bearing.
#
# MEASURED 2026-09-10 on a real CREATE: a caller-supplied sectionKey is REFUSED with
#   REPORT_CUSTOM_SECTION_NOT_OWNED
#   "Custom section 'custom:7b0d4a1e-...' does not belong to this strategy."
#   rule: omit sectionKey on a new custom section - the server derives it from the section
# which is coherent - on a CREATE the section does not exist yet, so it cannot be owned.
# It IS accepted on UPDATE, where the section exists (also measured, same day).
#
# Setting SK to None fixes both halves at once: CustomSection.wire() drops sectionKey via
# exclude_none, and every condition clause carries sectionKey null, which the server
# resolves to the key it mints (verified - all conditions read back carrying
# custom:88da7c5c-... after being submitted as null).
#
# An earlier version of this file hardcoded custom:7b0d4a1e-... Every payload it emitted
# would have been refused on submission. They all passed omega offline validation with
# zero errors, which is exactly the trap: offline validation is this repo's MODEL of the
# contract, not the server.
SK = None

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
# UNIVERSE. 36 tickers is MEASURED REFUSED.
#
# The 256 KB compile report-preview cap binds on coins x columns x conditions, not on
# ranked mode alone as the README records. Measured on one identical payload:
#   36 tickers -> "mcp_result_bytes limit exceeded: 433118 > 256000"  REFUSED
#   16 tickers -> "281848 > 256000"                                    REFUSED
#   10 tickers ->  compiled
# Fitting those two refusals: about 7563 bytes per coin on about 160832 fixed overhead,
# against a 262144 cap. So the ceiling is roughly (262144 - 160832) / 7563 = 13 coins at
# 8 columns / 9 conditions, and fewer as the column x condition grid grows.
#
# COINS_ALL is kept so the full cohort is not silently lost - the read-only panel logger
# still covers all 36 through preview, which is NOT subject to this cap.
COINS_ALL = [
    "AAVE", "AIXBT", "APT", "AVAX", "BNB", "BTC", "CAKE", "CRV", "DOGE", "ENA",
    "ETH", "FARTCOIN", "GRAM", "HYPE", "JUP", "LDO", "LINK", "LTC", "MELANIA",
    "MET", "MOODENG", "PENGU", "PEPE", "POPCAT", "PUMP", "PURR", "SHIB", "SNX",
    "SOL", "SUI", "TRUMP", "UNI", "WIF", "WLFI", "XRP", "ZEC",
]
# The eight carried into a compile: the liquid majors plus the two memes that actually
# produced ENTER decisions on the live agent (MOODENG, DOGE). Eight leaves headroom even
# at 9 columns.
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "LINK", "DOGE", "MOODENG"]


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

def ordered(conds):
    """Sort conditions so a directional verdict can never be masked.

    MEASURED 2026-09-10: verdict resolution is FIRST-TRUE-WINS in array order. The same
    nine conditions, same thresholds, same columns, differing ONLY in array order returned
    0 UP / 0 DOWN / 10 NEITHER in one order and 0 UP / 4 DOWN / 0 NEITHER in the other,
    with decidedBy naming the directional condition. A NEITHER condition placed ahead of a
    directional one SILENTLY MASKS it, and the rendered conditions table still shows every
    row's TRUE/FALSE correctly, so the masking is invisible unless you read the Verdict
    column. That is how strategy 56c08ef6 revision 2 shipped emitting nothing.

    UP/DOWN first, then verdict-null building blocks, then NEITHER tags last. Whether a
    verdict-null condition can also mask is UNMEASURED, so it sits in the middle rather
    than being assumed harmless. sorted() is stable, so order within a rank is preserved.
    """
    rank = {"UP": 0, "DOWN": 0, None: 1, "NEITHER": 2}
    return sorted(conds, key=lambda c: rank.get(c.get("verdict"), 1))


SUITE = [
    dict(id="S1", name="Value Location",
         thesis="Where the close sits against the previous completed UTC session's value area. No direction claimed.",
         extra=[], conds=ordered(LOC),
         teaches="The spine renders, the signs are right, and a TPO condition reaches only the report.",
         null="ZERO - every column pairs a prior-session base with a candle operand."),
    dict(id="S2", name="Value Re-Entry",
         thesis="Price that was outside prior value at the bar's open and is back inside at its close.",
         extra=[], conds=ordered(LOC + REENTRY),
         teaches="Whether the re-entry geometry ever fires at all. It has never been observed TRUE.",
         null="ZERO."),
    dict(id="S3", name="Rotation Target",
         thesis="Re-entry, plus whether the prior POC is still ahead of price or already behind it.",
         extra=[], conds=ordered(LOC + REENTRY + TARGET),
         teaches="Separates a setup from a completed rotation.",
         null="ZERO."),
    dict(id="S4", name="Width Regime",
         thesis="Stand down when the prior value area is too narrow for the rotation to pay.",
         extra=[], conds=ordered(LOC + REENTRY + TARGET + [WIDE]),
         teaches="The only never-null TPO regime read available.",
         null="ZERO."),
    dict(id="S5", name="Confirmed Re-Entry",
         thesis="Re-entry that survived two closed bars of momentum, joined by conditionRef across clocks.",
         extra=[c("RSI14", "value")], conds=ordered(LOC + REENTRY + HELD + CONFIRMED),
         teaches="The split-clock composition, and the only leg in the suite that can persist.",
         null="RSI14 warm-up only - null until 14 anchor bars exist."),
    dict(id="S6", name="POC Cross-Recross",
         thesis="One bar that crossed the prior POC and closed back on its original side.",
         extra=[c("PRIOR_TPO_POC", "spread", "OPEN"),
                c("PRIOR_TPO_POC", "spread", "LOW"),
                c("PRIOR_TPO_POC", "spread", "HIGH")],
         conds=ordered(LOC + POC_DEFENCE),
         teaches="The nearest lawful reading of 'the POC acted as support'. It cannot distinguish a defence from a failed breakout.",
         null="ZERO."),
    dict(id="S7", name="Developing Value",
         thesis="Today's developing POC and profile skew against the previous completed session.",
         extra=[c("TPO_POC", "spread", "PRIOR_TPO_POC"),
                c("TPO_VAH", "spread", "TPO_VAL"),
                c("TPO_SHAPE", "value")],
         conds=ordered(LOC + DEVELOPING),
         teaches="Whether developing-vs-prior carries information beyond time-of-day.",
         null="SEVERE - all three added columns are null 00:00-01:00 UTC, and the developing area is "
              "structurally narrow all morning (measured 40-48% of prior width at the 12:00 midpoint). "
              "A silent FALSE both ways. Every condition here is verdict NEITHER so it cannot flip a direction."),
]


# --- the entry block: MIRRORED from a record, never invented ---------------------
# `entry` is REQUIRED on CREATE. omega/preflight.py MIRROR_ENTRY_FIELDS warns when a
# hardcoded value differs from the reference record, and the recipe's rule for a
# missing field is "mirror the record's value, never invent". These six are read back
# VERBATIM from 56c08ef6 (rev 4) and 3d720de3 (rev 2) on 2026-09-11 - identical on both.
# confirmTf is the thesis anchor by design (Step 0 amendment, 2026-08-30).
# NOTE omega/generate.py still hardcodes trigger AT_SIGNAL / bandAtrMultiple 1, mirrored
# from 6a8bca67 in August. Both records bound to TPO strategies now carry the values
# below; that is a live mirror drift in generate.py, recorded here rather than fixed
# here because generate.py's mirror has its own tests and its own reference record.
ENTRY_MIRROR = {"trigger": "ON_CANDLE_CLOSE", "confirmTf": ANCHOR, "closes": 1,
                "bandAtrMultiple": 0.5, "levelOffsetAtrMultiple": 0, "validForBars": 4}
ENTRY_MIRROR_SOURCE = "get_strategy 56c08ef6-480b-4293-8136-81beed2161cf rev 4, 2026-09-11T06:39:51Z"

# Routing gate, mirrored from the same record. No strategy here carries a rules array
# (all nine TPO metrics feed zero of the 84 signal modules - 663-cell probe, 0 failures),
# so none can produce an aggregate and none can qualify a coin at ANY gate. 0.99 states
# that honestly on the record instead of leaving a platform default we have not measured.
GATE_MIRROR = {"minAggregateScore": 0.99, "minRequiredCount": 0}

# The CREATE arm's string caps, read from the live compile schema (byte-identical to the
# 2026-09-09 capture, sha256 bb5961fd..., re-verified 2026-09-11). Enforced here so a
# too-long field fails offline instead of at the server.
CAPS = {"name": 50, "tagline": 80, "description": 500, "intentSummary": 2000,
        "assumption": 500, "assumptions": 20}

STANDING_ASSUMPTIONS = [
    "Measured: all nine TPO metrics feed zero of the 84 signal modules (663-cell probe, "
    "zero failures). This strategy carries no rules array, so it has no aggregate and "
    "cannot qualify a coin at any gate. Its conditions are advisory and reach an agent "
    "only as prompt context.",
    "Measured: spread(M,O) = (M - O)/O in percent, positive meaning M sits above O. Proven "
    "by arithmetic on BTC 2026-09-11 (close 76845.00 vs pTpoVAL 76488.38 -> -0.46%). Every "
    "sign in the conditions is read against that convention.",
    "Measured: TPO has no history by any route - offset inert, chaining refused with an "
    "empty candidate list, CLOSE clock refused. Every column is a current read.",
    "Measured: verdicts resolve first-true-wins in array order. Conditions are sorted "
    "directional-first (ordered()) so a NEITHER cannot shadow an UP or DOWN.",
    "Scope: dry-run body. Compile only; nothing applied, bound or deployed by this file.",
]


def _cap(text: str, key: str) -> str:
    return text[:CAPS[key]]


def wire(s: dict, report: Report) -> dict:
    """The exact compile_strategy_plan CREATE request body for one suite entry - the
    shape omega.generate.StrategyPlan.wire() proved live on 2026-08-28, minus the rules
    array (annotation-only by construction), with entry and gate MIRRORED from the
    reference record rather than invented. Every key here is declared by the CREATE arm;
    nothing else is emitted, because the arm is additionalProperties:false."""
    # Measured 2026-08-28 and again 2026-09-10: CREATE refuses ANY client-supplied custom
    # sectionKey (REPORT_CUSTOM_SECTION_NOT_OWNED). The server mints it. SK is None so
    # CustomSection.wire() already drops it; the filter makes that explicit and durable.
    sections = [{k: v for k, v in sec.items() if not (sec.get("kind") == "custom" and k == "sectionKey")}
                for sec in report.wire()]
    thresholds = [
        "Threshold BIN %s%%: MEASURED - the vendor bins price at 5 bps, so anything finer "
        "measures quantisation rather than structure." % BIN,
        "Threshold WIDTH_P25 %s%%: MEASURED as the p25 of prior value-area width across 36 "
        "CRYPTO coins at 2026-09-10T12:21Z. ONE SNAPSHOT, not a calibration." % WIDTH_P25,
        "Threshold RSI_MID %s: INVENTED. No measurement supports it." % RSI_MID,
    ]
    assumptions = ([("Null exposure: " + s["null"])[:CAPS["assumption"]],
                    ("What this strategy is meant to teach: " + s["teaches"])[:CAPS["assumption"]]]
                   + thresholds + STANDING_ASSUMPTIONS)[:CAPS["assumptions"]]
    for a in assumptions:
        assert len(a) <= CAPS["assumption"], "assumption over cap: %r" % a[:60]
    return {
        "operation": "CREATE",
        "intentSummary": _cap("%s. %s Teaches: %s Built by scripts/tpo_suite_build.py; "
                              "compile dry-run only, nothing applied."
                              % (s["name"], s["thesis"], s["teaches"]), "intentSummary"),
        "assumptions": assumptions,
        "coinSelection": {"mode": "explicit", "tickers": COINS},
        "name": _cap("OMEGA-TEST: " + s["name"], "name"),
        "tagline": _cap(s["thesis"], "tagline"),
        "description": _cap(s["thesis"] + " " + s["teaches"], "description"),
        "timeframe": ANCHOR,
        "sections": sections,
        "conditions": s["conds"],
        "entry": dict(ENTRY_MIRROR),
        **GATE_MIRROR,
    }


def build():
    """Validate every suite entry offline and return (design_record, wire_body, nerr)
    triples. Pure: no files, no network. main() does the writing."""
    out = []
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
        design = {
            "_what": "DESIGN RECORD for a TPO strategy - human-facing provenance. NOT a wire "
                     "body: the compile request is the sibling <id>.wire.json. NOT compiled, "
                     "NOT applied, NOT bound.",
            "_provenance": "scripts/tpo_suite_build.py, contract 54.1.0, measured 2026-09-10/11",
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
            "entryMirror": {"values": ENTRY_MIRROR, "source": ENTRY_MIRROR_SOURCE},
            "validation": {"reportErrors": [str(f) for f in rep_errs],
                           "conditionErrors": [str(f) for f in cond_errs],
                           "warnings": [str(f) for f in warns]},
        }
        out.append((s, section, design, wire(s, report), rep_errs, cond_errs, warns))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    total_err = 0
    print("%-4s %-22s %5s %5s %6s  %s" % ("id", "name", "cols", "conds", "errors", "status"))
    print("-" * 78)
    manifest = []
    for s, section, design, body, rep_errs, cond_errs, warns in build():
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

        with open(os.path.join(OUT, s["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(design, f, indent=1)
        with open(os.path.join(OUT, s["id"] + ".wire.json"), "w", encoding="utf-8") as f:
            json.dump(body, f, indent=1)
        manifest.append({"id": s["id"], "name": s["name"], "design": s["id"] + ".json",
                         "wire": s["id"] + ".wire.json",
                         "columns": len(section.columns), "conditions": len(s["conds"]),
                         "errors": nerr})

    with open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"suite": manifest, "anchor": ANCHOR, "sectionKey": SK,
                   "coins": COINS, "entryMirror": ENTRY_MIRROR, "entryMirrorSource": ENTRY_MIRROR_SOURCE,
                   "totalErrors": total_err}, f, indent=1)

    print("-" * 78)
    print("payloads -> %s  (<id>.json = design record, <id>.wire.json = compile body)" % OUT)
    print("total errors: %d" % total_err)
    if total_err:
        print("BLOCKED - payloads with errors are written but must not be compiled.")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
