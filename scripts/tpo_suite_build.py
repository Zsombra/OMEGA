"""Build the TPO strategy suite S1-S7: a design record, a stage request and a preview body per strategy.

PREPARE, NEVER EXECUTE (docs/20, decision P4).
    This script makes ZERO live calls and writes NOTHING to the platform. It emits JSON files
    to out/tpo_suite/. Staging, previewing, committing and binding are separate,
    human-initiated acts, each per-instance authorised.

THREE FILES PER STRATEGY, BECAUSE ONE FILE CANNOT BE ALL OF THEM (measured 2026-09-11)
    <id>.json          the DESIGN RECORD: thesis, what it teaches, null exposure, threshold
                       provenance, predicted headers, offline validation, the v91 mappings this
                       port applied. Human-facing. NEVER sent.
    <id>.stage.json    `{draftVersion: 0, axes}` - the `request` of a CREATE stage_strategy_draft
                       (no strategyId: v85 "omit strategyId to open a NEW create draft"). The
                       eight axes (contract 108) are exactly what omega.generate.StrategyPlan.axes() returns, so
                       the manager stages them as it stages a generated plan.
    <id>.preview.json  the read-only dry run: preview_strategy_report {coinSelection, source:
                       {kind: FIELDS, timeframe, sections, conditions, marketReadText}} (v85),
                       the shape StrategyPlan.preview_request() returns.
    Until 2026-09-11 this script emitted only the first file and called it "submit-ready"; run
    through scripts/preflight.py it FAILED on every strategy (five required fields missing, ten
    undeclared keys). Offline validation is this repo's MODEL of the contract, not the server -
    which is why tests/test_tpo_suite_wire.py walks every axis against the saved schema.

PORTED 2026-10-10 FROM THE RETIRED COMPILE BODY TO THE v91 DRAFT LIFECYCLE
    The 2026-09-11 version emitted the flat compile_strategy_plan CREATE body (contract 54.1.0).
    Contract 85.0.0 retired that tool; v84 moved the hold onto every clause and group; v88 made
    `exitSide` a required key; v91 is the saved schema. Each mapping is listed on the design
    record under `v91Mappings`, per member, and in V91_MAPPINGS below. The theses - the market
    reads and the condition logic - are the 2026-09-10/11 ones, unchanged.

PORTED 2026-10-11 TO CONTRACT 108 (conditions are the only entry gate)
    v108 refuses SETUP_GATES and SIGNAL_RULES; minAtrPct moved onto TRADE_LEVEL_POLICY. The 0.99 / 0
    gate mirror (GATE_MIRROR) has no axis any more and is history. Every member's conditions are now
    its entry gate: each declares a verdict carrier, so none draws NO_ENTRY_CONDITION; the design
    record lists the gate under `entryGate`. No condition changed.

EVERY NUMBER'S PROVENANCE IS RECORDED
    Each threshold carries a basis string. There are exactly two honest categories and this file
    uses only those: MEASURED (cite the measurement) or INVENTED (say so).

WHY THE COIN LIST IS EXPLICIT AND NOT RANKED
    coinSelection is no part of a strategy since v85: it is an input of preview_strategy_report
    only. The preview is capped at previewExecutionLimits.maxResultChars (150,000 at v92), and
    the retired compile's 256 KB cap refused 36 and 16 tickers on this report shape (below).
    Eight explicit tickers carry breadth with headroom.

NOT ALL OF THESE ARE WORTH CREATING, AND THIS FILE DOES NOT DECIDE THAT
    S1 and S7 emit only NEITHER verdicts, so neither can produce a direction - and at 108 their
    NEITHER carriers are their whole entry gate, which (vendor strategy-examples: a resolved NEITHER
    admits no side) suggests they can never enter; unmeasured. S2's re-entry
    geometry (bar opened outside prior value, closed inside) was observed firing ZERO times
    across two days of probing, and S3 and S5 both lean on it. Until 108 none of the seven weighted
    a signal, so all seven were annotation-only and could not route at any gate; at 108 the
    conditions themselves gate entry. And since 56.1.0 a
    NEITHER carrier reading TRUE beside an UP or DOWN carrier resolves the coin NEITHER (see
    ordered()). Emitting a legal payload is not the same as it being worth a quota slot.

USAGE
    python scripts/tpo_suite_build.py
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omega.conditions import (  # noqa: E402
    all_of, between, condition, entry_gates, held, in_, market_read_text, num, ref, report_headers,
    validate_conditions, validate_entry_gate, validate_market_read,
)
from omega.generate import ENTRY_MIRROR, StrategyPlan, Thesis  # noqa: E402
from omega.types import Column, CustomSection, Report  # noqa: E402
from omega.validate import validate_report  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "tpo_suite")

# SECTION KEY: None, and that is load-bearing.
#
# MEASURED 2026-09-10 on a real CREATE: a caller-supplied sectionKey is REFUSED with
#   REPORT_CUSTOM_SECTION_NOT_OWNED
#   "Custom section 'custom:7b0d4a1e-...' does not belong to this strategy."
# The server mints the key at commit. The v91 REPORT axis still declares `sectionKey` optional
# on a custom section and a create draft's acceptance of one is unmeasured, so a CREATE keeps
# not sending it (omega.generate.StrategyPlan._sections drops it; SK None drops it here too).
# Every clause carries `column.sectionKey: null`, which the server resolves to the key it mints
# (verified 2026-09-10: all conditions read back carrying custom:88da7c5c-... after being
# submitted as null). An UPDATE of an existing strategy carries the live keys forward
# (StrategyPlan.axes_update, 2026-10-10); this file builds CREATEs only.
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
# The persistence leg's hold: two closes in a row. The 2026-09-11 body said `closes: 2` on the
# condition (with the CLOSE clock); v84 says `hold: {atLeast: 2, of: 2}` on the clause.
HELD_CLOSES = 2

# 36 CRYPTO tickers observed in the 2026-09-10T12:21Z ranked panel pull.
# UNIVERSE. 36 tickers is MEASURED REFUSED - on the retired compile's 256 KB report-preview cap:
#   36 tickers -> "mcp_result_bytes limit exceeded: 433118 > 256000"  REFUSED
#   16 tickers -> "281848 > 256000"                                    REFUSED
#   10 tickers ->  compiled
# Fitting those two refusals: about 7563 bytes per coin on about 160832 fixed overhead against
# a 262144 cap, so roughly 13 coins at 8 columns / 9 conditions. The v91 preview has its own
# cap (previewExecutionLimits.maxResultChars 150,000 at v92, omega.contract.load().shared);
# what it admits for this report shape is UNMEASURED. COINS_ALL is kept so the full cohort is
# not silently lost - the read-only panel logger still covers all 36 through preview.
COINS_ALL = [
    "AAVE", "AIXBT", "APT", "AVAX", "BNB", "BTC", "CAKE", "CRV", "DOGE", "ENA",
    "ETH", "FARTCOIN", "GRAM", "HYPE", "JUP", "LDO", "LINK", "LTC", "MELANIA",
    "MET", "MOODENG", "PENGU", "PEPE", "POPCAT", "PUMP", "PURR", "SHIB", "SNX",
    "SOL", "SUI", "TRUMP", "UNI", "WIF", "WLFI", "XRP", "ZEC",
]
# The eight carried into a preview: the liquid majors plus the two memes that actually
# produced ENTER decisions on the live agent (MOODENG, DOGE).
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "LINK", "DOGE", "MOODENG"]
COIN_SELECTION = {"mode": "explicit", "tickers": COINS}


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
#
# Every clause and group below reads one bar, hold {atLeast 1, of 1} - the builders' default,
# and what the 2026-09-11 body's `closes: 1` meant (v84). Only HELD holds more.

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

# The persistence leg. It reads RSI14 and not a TPO header because on 54.1.0 (2026-09-11) a
# hold above one bar was refused on every TPO header, while RSI14 was the ONE candle metric
# measured end to end (header `RSI14`, closes:2 returning closesHeld 2 / closesRequired 2).
# At v91 the hold is `hold: {atLeast: 2, of: 2}` on the clause - "2 closes in a row" (v84) -
# placed by condition(hold=) on the definition's root, which for a single clause IS the clause.
# The clock is gone (retired 61.0.0). What a 1h RSI14 `value` column admits as conditionHold
# is UNMEASURED: the 2026-10-06 M2 read has RSI14_now (trajectory) at maxWindow 192 and no
# `RSI14` row; the builder judges it (omega warns only when the header is not candle-moved).
HELD = [
    condition("RSI_HELD_UP_2C", "Momentum above the midline for two closed bars",
              num("RSI14", "gt", RSI_MID, section_key=SK),
              verdict=None, hold=held(HELD_CLOSES)),
    condition("RSI_HELD_DOWN_2C", "Momentum below the midline for two closed bars",
              num("RSI14", "lt", RSI_MID, section_key=SK),
              verdict=None, hold=held(HELD_CLOSES)),
]

# The join reads one bar: a group hold here would be "a group hold over members that hold their
# own bars", which v84 refuses - so the two-bar hold lives on RSI_HELD_*, reached by conditionRef
# (a ref carries no hold of its own), and this ALL reads the two building blocks once.
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
    """Sort conditions directional-first: UP/DOWN, then verdict-null building blocks, then
    NEITHER tags. sorted() is stable, so order within a rank is preserved.

    WHY IT WAS LOAD-BEARING. MEASURED 2026-09-10 on 54.1.0: verdict resolution was
    FIRST-TRUE-WINS in array order - the same nine conditions, differing ONLY in array order,
    returned 0 UP / 0 DOWN / 10 NEITHER in one order and 0 UP / 4 DOWN / 0 NEITHER in the
    other. A NEITHER condition placed ahead of a directional one SILENTLY masked it; that is how
    strategy 56c08ef6 revision 2 shipped emitting nothing.

    WHY IT NO LONGER IS. Contract 56.1.0 (2026-09-14; vendor pack strategy-examples SKILL.md
    "Verdicts") resolves over the DISTINCT verdicts of the carriers that read TRUE: one distinct
    verdict decides and "the first carrier in declaration order carrying it is named as the
    decider"; carriers that DISAGREE resolve NEITHER, and "declaration order never picks a side
    between them". So the order now names the decider among AGREEING carriers and nothing else.
    What it cannot fix: every LOC tag is a NEITHER CARRIER, and a re-entry (closed back inside
    value) is TRUE together with INSIDE_PRIOR_VALUE, so {UP, NEITHER} disagree and S2-S5
    resolve NEITHER whenever their directional leg fires. That is a 56.1.0 semantics change in
    the suite's design, NOT a v91 grammar mapping; it is recorded on every design record
    (`verdictResolutionNote`) and left to the author - this port changes no condition's logic.
    """
    rank = {"UP": 0, "DOWN": 0, None: 1, "NEITHER": 2}
    return sorted(conds, key=lambda c: rank.get(c.get("verdict"), 1))


VERDICT_RESOLUTION_NOTE = (
    "Contract 56.1.0 (2026-09-14) resolves a coin over the DISTINCT verdicts of the carriers that "
    "read TRUE; disagreeing carriers resolve NEITHER and declaration order never picks a side. "
    "Every LOC tag here is a NEITHER carrier and a re-entry is TRUE together with "
    "INSIDE_PRIOR_VALUE, so a directional leg firing beside it resolves NEITHER. The 2026-09-10 "
    "first-true-wins measurement that justified ordered() is superseded; ordered() now only names "
    "the decider among agreeing carriers. Unmeasured on 56.1.0+ for this suite; the author decides "
    "whether the LOC tags should carry verdict null instead. This port changed no condition.")


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
         # 2026-09-11 wording: "joined by conditionRef across clocks". The clock was retired at
         # 61.0.0; the read is the same - the two-bar hold sits on the RSI leg, reached by ref.
         thesis="Re-entry that survived two closed bars of momentum, joined by conditionRef to a two-bar hold.",
         extra=[c("RSI14", "value")], conds=ordered(LOC + REENTRY + HELD + CONFIRMED),
         teaches="The held-leg composition, and the only leg in the suite that can persist.",
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


# --- the entry axis: MIRRORED, never invented ------------------------------------
# `ENTRY` is `{trigger: "ON_CANDLE_CLOSE"}` alone - omega.generate.ENTRY_MIRROR. v85: "a union
# discriminated by trigger ... ON_CANDLE_CLOSE naming either dial is refused, which the retired
# compile accepted; the server stamps the seed values". The six-key block this file mirrored
# from 56c08ef6 rev 4 on 2026-09-11 (trigger, confirmTf, closes, bandAtrMultiple,
# levelOffsetAtrMultiple, validForBars) lost three keys at 60.0.0 and the remaining two dials
# at v85; it is in git history and on no live record's write path.
ENTRY_MIRROR_SOURCE = ("omega.generate.ENTRY_MIRROR - v85 ENTRY axis, trigger ON_CANDLE_CLOSE alone "
                       "(data/contract/stage_strategy_draft/schema_20261005T194629Z.json); the six-key "
                       "56c08ef6 rev-4 mirror of 2026-09-11 is history")

# RETIRED 2026-10-11 (contract 108 removed the aggregate-score and required-count gates; no axis carries
# them, and Thesis.gate is retired). Kept as history of what the v91 port sent on SETUP_GATES.
# Routing gate, mirrored from the 2026-09-11 reference record (56c08ef6 rev 4). No strategy here
# weights a signal (all nine TPO metrics feed zero of the 84 signal modules - 663-cell probe,
# 0 failures), so none can produce an aggregate and none can qualify a coin at ANY gate. 0.99
# states that honestly on the record instead of leaving a default we have not measured. At v91
# it is Thesis.gate -> SETUP_GATES.minAggregateScore; minRequiredCount is the count of required
# rules (none) and minAtrPct the 08-28 measured platform default, both via StrategyPlan.axes().
GATE_MIRROR = {"minAggregateScore": 0.99, "minRequiredCount": 0}

# The IDENTITY strings' local ceilings. The v91 IDENTITY axis declares NO length bound (name,
# description, tagline are plain strings); these are the retired compile's caps, kept so the
# strings stay inside what the platform is known to have accepted - a longer string's acceptance
# is unmeasured. intentSummary and assumptions went with the compile (v85: "the draft is the
# intent"); their text lives on the design record only.
CAPS = {"name": 50, "tagline": 80, "description": 500}

STANDING_ASSUMPTIONS = [
    "Contract 108 (2026-10-11): signal rules and the aggregate-score and required-count gates are "
    "removed; a strategy's entry gate is its conditions - a required condition or a verdict "
    "carrier (README 'Contract history - v108'). This strategy's verdict carriers are its entry "
    "gate, and the resolved verdict binds entry direction (since 56.1.0). Before 108: all nine TPO "
    "metrics fed zero of the 84 signal modules (663-cell probe), so it had no aggregate and could "
    "not qualify a coin at any gate.",
    "Measured: spread(M,O) = (M - O)/O in percent, positive meaning M sits above O. Proven "
    "by arithmetic on BTC 2026-09-11 (close 76845.00 vs pTpoVAL 76488.38 -> -0.46%). Every "
    "sign in the conditions is read against that convention.",
    "Measured 2026-09-10 on 54.1.0: TPO has no history by any route - offset inert, chaining "
    "refused with an empty candidate list, a hold above one bar refused on every TPO header. "
    "Every TPO column is a current read. At v91 the per-column conditionHold of the TPO "
    "headers is unmeasured (the 2026-10-06 M2 read covered the five presets' headers only).",
    VERDICT_RESOLUTION_NOTE,
    "Scope: stage request and preview body. Nothing staged, previewed, committed, bound or "
    "deployed by this file.",
]

# The v91 mappings this port applied to the 2026-09-11 compile body, one line each, every one
# from the README contract history or the saved schema (plan 2026-10-06). `common` applies to
# every member; `held` only to a member carrying HELD (S5). No member carried `exit: true`, so
# no condition gained a CLOSE_ON_ exit rule (the v88 split).
V91_MAPPINGS = {
    "common": [
        "v85: the flat compile_strategy_plan CREATE body became the ten axes of a stage_strategy_draft "
        "CREATE request {draftVersion: 0, axes} - IDENTITY {name, tagline, description}, "
        "TIMEFRAME_PROFILE {timeframe}, REPORT {sections}, MARKET_READ, CONDITIONS, ENTRY, "
        "SETUP_GATES, TRADE_LEVEL_POLICY, POSITION_MANAGEMENT, SIGNAL_RULES - each written WHOLE, "
        "built by omega.generate.StrategyPlan.axes().",
        "v85: operation, intentSummary and assumptions are gone ('the draft is the intent'); their "
        "text stays on this design record and is never sent.",
        "v85: coinSelection is no part of a strategy; it moved to the preview_strategy_report body "
        "(<id>.preview.json), whose source is {kind: FIELDS, timeframe, sections, conditions, "
        "marketReadText}.",
        "v84: `closes: 1` on every condition became `hold: {atLeast: 1, of: 1}` on every clause and "
        "every group (one read); a conditionRef carries no hold.",
        "v88: `exit: false` on every condition became `exitSide: null` (an entry condition); no "
        "condition carried exit: true, so no CLOSE_ON_<key> exit rule arises.",
        "61.0.0 / v84: `clock` is gone from every condition (retired at 61.0.0, refused as an unknown "
        "key); nothing replaces it on a one-read condition.",
        "60.0.0 / v85: the six-key entry mirror became ENTRY {entry: {trigger: ON_CANDLE_CLOSE}} alone "
        "(omega.generate.ENTRY_MIRROR); naming a dial on that trigger is refused.",
        "v85 whole axes: TRADE_LEVEL_POLICY and POSITION_MANAGEMENT carry omega's measured 08-28 "
        "defaults - the compile body sent none of these (Decision 1a); the axes require them.",
        "v108: SETUP_GATES and SIGNAL_RULES are refused as unrecognized keys, so the eight axes carry "
        "neither the 0.99 / 0 gate mirror nor the 84 allocation-0 rows the v91 port sent; minAtrPct "
        "(0.5, the 08-28 default) is required on TRADE_LEVEL_POLICY. The conditions are the entry gate.",
        "MARKET_READ is a required axis: marketReadText is composed by omega.conditions.market_read_text "
        "over every condition (the compile body sent none). Advisory text; it changes no condition.",
    ],
    "held": [
        "v84: `clock: CLOSE, closes: 2` on RSI_HELD_UP_2C / RSI_HELD_DOWN_2C became "
        "`hold: {atLeast: 2, of: 2}` ('2 closes in a row') on the RSI14 clause - the condition's "
        "hold on its definition's root, which for a single clause is the clause; the clock is gone.",
        "v84: REENTRY_CONFIRMED_* keep `hold: {1, 1}` on their ALL group - a group hold over "
        "members that hold their own bars is refused, so the two-bar hold lives on the referenced "
        "RSI leg and the join reads once. Thesis wording 'across clocks' -> 'to a two-bar hold'.",
    ],
}


def _cap(text: str, key: str) -> str:
    """Cut to the cap on a word boundary (a mid-word cut is what the 2026-09-11 tagline shipped)."""
    cap = CAPS[key]
    if len(text) <= cap:
        return text
    cut = text[:cap]
    return cut[:cut.rfind(" ")].rstrip(" ,;") if " " in cut else cut


def _carries_hold_above_one(conds: list[dict]) -> bool:
    def walk(d):
        if not isinstance(d, dict):
            return False
        h = d.get("hold")
        if isinstance(h, dict) and (h.get("atLeast"), h.get("of")) != (1, 1):
            return True
        return any(walk(m) for m in d.get("members") or [])
    return any(walk(x.get("definition")) for x in conds)


def thesis_for(s: dict) -> Thesis:
    """The omega Thesis that carries one suite member's identity, anchor and universe into
    StrategyPlan.axes() / preview_request(). weights is empty on purpose: no module recipe adds
    a column - the report is the SPINE plus the member's extras, built in build() - and the
    conditions are the member's own (contract 108: no gate, no signal rules)."""
    return Thesis(
        name=_cap("OMEGA-TEST: " + s["name"], "name"),
        tagline=_cap(s["thesis"], "tagline"),
        description=_cap(s["thesis"] + " " + s["teaches"], "description"),
        anchor=ANCHOR,
        coin_selection=dict(COIN_SELECTION),
    )


@dataclass
class Built:
    spec: dict
    section: CustomSection
    plan: StrategyPlan
    design: dict
    axes: dict
    preview: dict
    report_errors: list
    condition_errors: list
    warnings: list

    @property
    def errors(self) -> int:
        return len(self.report_errors) + len(self.condition_errors)


def build() -> list[Built]:
    """Validate every suite entry offline and return one Built per member. Pure: no files, no
    network. main() does the writing."""
    out: list[Built] = []
    for s in SUITE:
        section = CustomSection(
            title=("TPO " + s["name"])[:60], sectionKey=SK, benchmarkTicker=None,
            notes=(s["thesis"])[:400], columns=SPINE + s["extra"],
        )
        report = Report(anchor=ANCHOR, sections=[section])
        text = market_read_text(
            "%s. %s The conditions below are this strategy's entry gate (contract 108)." % (s["name"], s["thesis"]),
            s["conds"])
        plan = StrategyPlan(thesis=thesis_for(s), report=report, rules=[],
                            conditions=s["conds"], market_read_text=text)
        vr = validate_report(report)
        rep_errs = [f for f in vr.findings if f.severity == "error"]
        cf = (validate_conditions(report, s["conds"]) + validate_market_read(text, s["conds"], report)
              + validate_entry_gate(s["conds"]))
        gate = entry_gates(s["conds"])
        gate_verdicts = {c["verdict"] for c in s["conds"] if c["conditionKey"] in gate}
        gate_note = ("every entry gate is a NEITHER carrier: the platform counts a NEITHER verdict as "
                     "carrying one (no NO_ENTRY_CONDITION), but a resolved NEITHER admits no side (vendor "
                     "strategy-examples skill), so whether this member can ever enter is unmeasured"
                     if gate_verdicts == {"NEITHER"} else
                     "verdict carriers: %s; a required condition: %s" % (
                         ", ".join(sorted(v for v in gate_verdicts if v)) or "none",
                         "yes" if any(c["required"] for c in s["conds"] if c["conditionKey"] in gate) else "no"))
        cond_errs = [f for f in cf if f.severity == "error"]
        warns = [f for f in cf if f.severity == "warning"]
        mappings = list(V91_MAPPINGS["common"])
        if _carries_hold_above_one(s["conds"]):
            mappings += V91_MAPPINGS["held"]
        design = {
            "_what": "DESIGN RECORD for a TPO strategy - human-facing provenance. NOT a request body: "
                     "the CREATE stage request is the sibling <id>.stage.json and the read-only preview "
                     "body <id>.preview.json. NOT staged, NOT previewed, NOT committed, NOT bound.",
            "_provenance": "scripts/tpo_suite_build.py; designed on contract 54.1.0 (measured 2026-09-10/11), "
                           "ported 2026-10-10 to the 91.0.0 draft lifecycle "
                           "(data/contract/stage_strategy_draft/schema_20261005T194629Z.json) and "
                           "2026-10-11 to contract 108.0.0 "
                           "(data/contract/stage_strategy_draft/schema_20261010T215326Z.json)",
            "id": s["id"], "name": s["name"], "thesis": s["thesis"],
            "teaches": s["teaches"], "nullExposure": s["null"],
            "anchor": ANCHOR,
            "coinSelection": dict(COIN_SELECTION),
            "sections": report.wire(),
            "conditions": s["conds"],
            "marketReadText": text,
            "predictedHeaders": sorted(report_headers(report).keys()),
            "thresholds": {
                "BIN": {"value": BIN, "basis": "MEASURED - vendor bins price at 5 bps"},
                "WIDTH_P25": {"value": WIDTH_P25,
                              "basis": "MEASURED - p25 of 36 CRYPTO coins at 2026-09-10T12:21Z. "
                                       "ONE SNAPSHOT, not a calibration."},
                "RSI_MID": {"value": RSI_MID, "basis": "INVENTED"},
                "HELD_CLOSES": {"value": HELD_CLOSES,
                                "basis": "the 2026-09-11 design's closes: 2, now hold {2, 2} (v84); "
                                         "the 1h RSI14 conditionHold ceiling is unmeasured"},
            },
            "entryMirror": {"values": dict(ENTRY_MIRROR), "source": ENTRY_MIRROR_SOURCE},
            "entryGate": {"conditions": gate, "note": gate_note},
            "assumptions": [("Null exposure: " + s["null"]),
                            ("What this strategy is meant to teach: " + s["teaches"])] + STANDING_ASSUMPTIONS,
            "v91Mappings": mappings,
            "verdictResolutionNote": VERDICT_RESOLUTION_NOTE,
            "validation": {"reportErrors": [str(f) for f in rep_errs],
                           "conditionErrors": [str(f) for f in cond_errs],
                           "warnings": [str(f) for f in warns]},
        }
        out.append(Built(spec=s, section=section, plan=plan, design=design,
                         axes=plan.axes(), preview=plan.preview_request(),
                         report_errors=rep_errs, condition_errors=cond_errs, warnings=warns))
    return out


def stage_request(b: Built) -> dict:
    """The `request` of a CREATE stage_strategy_draft: no strategyId, draftVersion 0, the eight
    axes whole (contract 108). A stage is a WRITE into the player's draft; writing this file is not making it."""
    return {"draftVersion": 0, "axes": b.axes}


def main():
    os.makedirs(OUT, exist_ok=True)
    total_err = 0
    print("%-4s %-22s %5s %5s %6s  %s" % ("id", "name", "cols", "conds", "errors", "status"))
    print("-" * 78)
    manifest = []
    for b in build():
        s = b.spec
        total_err += b.errors
        status = "OK" if b.errors == 0 else "BLOCKED"
        print("%-4s %-22s %5d %5d %6d  %s" % (
            s["id"], s["name"], len(b.section.columns), len(s["conds"]), b.errors, status))
        for f in b.report_errors:
            print("      [report error] %s" % (f,))
        for f in b.condition_errors:
            print("      %s" % (f,))
        for f in b.warnings:
            print("      %s" % (f,))

        with open(os.path.join(OUT, s["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(b.design, f, indent=1)
        with open(os.path.join(OUT, s["id"] + ".stage.json"), "w", encoding="utf-8") as f:
            json.dump(stage_request(b), f, indent=1)
        with open(os.path.join(OUT, s["id"] + ".preview.json"), "w", encoding="utf-8") as f:
            json.dump(b.preview, f, indent=1)
        manifest.append({"id": s["id"], "name": s["name"], "design": s["id"] + ".json",
                         "stage": s["id"] + ".stage.json", "preview": s["id"] + ".preview.json",
                         "columns": len(b.section.columns), "conditions": len(s["conds"]),
                         "errors": b.errors})

    with open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"suite": manifest, "anchor": ANCHOR, "sectionKey": SK,
                   "coinSelection": COIN_SELECTION,
                   "entryMirror": dict(ENTRY_MIRROR), "entryMirrorSource": ENTRY_MIRROR_SOURCE,
                   "contract": "108.0.0 (schema_20261010T215326Z.json)",
                   "totalErrors": total_err}, f, indent=1)

    print("-" * 78)
    print("payloads -> %s  (<id>.json = design record, <id>.stage.json = CREATE stage request, "
          "<id>.preview.json = preview body)" % OUT)
    print("total errors: %d" % total_err)
    if total_err:
        print("BLOCKED - payloads with errors are written but must not be staged or previewed.")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
