"""The trade level menu (contract 168): the stops and targets a strategy offers its model, per direction.

Since contract 168 (first served 168.2.0, 2026-11-11T16:32Z) the AUTHOR defines the trade levels:
`stage_strategy_draft` requires `TRADE_LEVEL_POLICY.tradeLevelMenu` = {LONG, SHORT}, each
{stops: 1 - 8 of ATR | LEVEL | PERCENT, targets: 1 - 8 of R_MULTIPLE | LEVEL}
(`$defs/directionTradeLevelMenu` of the pinned write schema; a `level` is a `$defs/conditionLevelRef`
{metric, timeframe, bars, offset, knobs, windowExtreme}, all six required).

The SHAPE of a menu is the write schema's, and is judged by walking the menu against it (omega.preflight): nothing
about shape is re-typed here. The RULES are not in the schema or the tool description. Each was MEASURED on thirty
create drafts, staged, read back and discarded, none committed (fifteen at 168.2.0, fifteen at 168.3.0):
data/audit/trade_level_menu_168_2026-11-11.json. The probe that measured a rule is named beside it.

  * ATR stops and R-multiple targets stage cleanly on any report (tc_atr_r_menu).
  * An R target below the strategy's minRiskRewardRatio is refused (V3: "every pair it makes would be refused").
  * A LEVEL must be "a level this strategy's report yields": a PRICE metric (M2: ADX read through `value` is refused;
    L1) that a per-coin custom section holds as a READING - the same metric at the same timeframe, knobs and offset.
      - The transform does not matter: `distance` (V1), `value` (V6), `trajectory` (M1); a spread yields its base
        metric (M6) and its plain operand (V2).
      - Timeframe: {abs: <anchor>} and {rel: anchor} are one reading, both ways (L2, M7); another timeframe matches
        like for like ({abs: 4h} M4, {rel: lower} M8) and nothing else (V10).
      - Knobs must be equal (L3a refused, L3b accepted). Offset must be equal (L4 refused, M3 accepted).
      - The level's `bars`: unset and "closed" are one (L5), and match a column whatever ITS bars are (M5: a
        Developing column). A level asking "all" against a column that does not is refused (M9).
    The platform's own migration default - the Donchian and Bollinger bands - is refused on a report that reads
    neither (tc_default_menu).
  * One level cannot be a stop and a target of the same direction (V8); across directions it can (V6).
  * More than eight entries in a list is refused at input (V5: the schema's maxItems).
  * NOT judged at stage: an ATR stop outside minStopLossAtrMultiple - maxStopLossAtrMultiple (V9), a repeated entry
    (V7). A PERCENT stop is accepted (V4), a LEVEL stop's bufferAtrMultiple too (V11). What a decision does with an
    ATR stop outside the stop range is unmeasured: a warning here, not an error.
  * A level-triggered entry's `levels` follow the same rule (E1 accepted, E2 refused).

Not measured, and refused here rather than guessed (TRADE_MENU_LEVEL_UNMEASURED): a `windowExtreme`; a level asking
bars "all" where a column also reads "all"; a metric the report holds only in a market, reference or platform section,
only as the operand of a spread whose column carries a knob or an offset, or only as an operand under an average
({metric, transformId, window}, new at 168). A {rel: lower | regime} level against the column at the same rung
spelled {abs: ...} is refused as not yielded (their equivalence is unmeasured; only the anchor's is).

Every probe was a CREATE. Whether a stage that omits TRADE_LEVEL_POLICY re-judges the strategy's live menu against a
restaged REPORT is unmeasured (StrategyPlan.update_menu_findings warns).

**Contract 170.0.0 (2026-11-12, undocumented): exit plans replace the targets.** Per direction `targets` became
`exitPlans`: 1 - 8 plans, each {targets: 1 - 4 legs {method: R_MULTIPLE {multiple} | LEVEL {level}, closePct: an
integer 0 - 100}} - a position can scale out. The platform migrated every stored strategy one to one: each old target
became a plan of ONE leg closing 100% (read 2026-11-12 08:55Z on all 16 account strategies). The rules, measured on 32
create stages at 170.0.0 (09:02 - 09:11Z): 26 drafts staged, read back and discarded, none committed, and 6 refused
at input (EXIT_PLAN_PROBES; the probe names below):

  * Refused at input (no draft): a plan whose legs close more than 100% together ("The close percentages of an exit
    plan sum to at most 100": X4 60 + 60, X5 50 + 100), a first leg closing 0% ("An exit plan's first target closes a
    share", X7), more than 4 legs (X13), more than 8 plans (X14), a closePct above 100 (X16).
  * Accepted: legs closing less than 100% together - the rest of the position runs (X3 50 + 30, X6 one leg of 50%); a
    later leg closing 0% (Y8); a level leg (X15, Y10); repeated plans (X17); plans of different shapes (X18).
  * Refused at stage as a draft error: an R leg not farther than the R leg IMMEDIATELY before it ("A LONG exit plan's
    targets run away from entry: 1.5R follows 3R. List each target farther than the one before it": X8, X9 equal, X11,
    Z4); a level leg between two R legs breaks the comparison (Z3 accepted 1.5R, level, 1.2R).
  * The minimum risk-reward is judged on what the PLAN pays: the closePct-weighted mean of its legs' R over the share
    it closes, at or above minRiskRewardRatio ("The LONG exit plan pays 1.3R, below this strategy's minimum
    risk-reward of 1.5": Y2 1R 50 + 1.6R 50, Y3, Y7; 1.4R Y4 1R 80 + 3R 20; 1R Y1, and Y6 one leg of 1R closing 50%;
    accepted X10 1R 50 + 3R 50 = 2R, Y5 = 1.8R, Y8 1.5R exactly). A plan out of order is judged on its order alone
    (X11 pays 1.35R and only the order was refused). A plan with a level leg is not judged at stage
    (Z1 1R 50 + a level accepted): its R is known only at a decision, which refuses a pair TARGETS_OUT_OF_ORDER /
    RISK_REWARD_TOO_LOW (the 170 gate-block reasons) - a warning here.
  * A level leg follows the target level rules above, and one level cannot be a stop and a leg of the same direction
    (Y9, as V8).

**Contract 171.0.0 (2026-11-12): the runner.** What a plan does not close is its RUNNER. The vendor skill pack 32.0.94
states the rules; each below was measured on 14 create stages at 171.0.0 / 588e449a (14:52 - 14:58Z): 10 drafts
staged, read back, previewed (preview_strategy_trade_levels on the DRAFT, BTC) and discarded, none committed, and 4
refused at input (RUNNER_PROBES; the probe names below):

  * A plan that leaves a runner is refused while POSITION_MANAGEMENT.trailingEnabled is false, as a draft error on the
    plan ("The LONG exit plan leaves a runner, and Trailing is off: nothing would exit it. Turn Trailing on, or close
    100% across the plan's targets.": T1 2R 50%, T2 1.5R 50% + 3R 0%). Trailing off under plans that close 100% stages
    clean (T3); the same runner with Trailing on too (T4). An UPDATE that only switches Trailing off is unmeasured.
  * What a plan pays is SHARE-WEIGHTED over the whole position: each share at its leg's R, the runner at the R of the
    last leg that closes a share (plan_pays). v0.14.0 divided by the share the plan closes, which agrees only when the
    plan closes 100% or closes at one R: W1 1R 30% + 3R 30% "pays 2.4R" (v0.14.0 2.0) below 2.5; W2b the same plan at
    2.25 stages clean, and W3 1R 50% + 2.2R 20% at 1.5 (v0.14.0 1.343) too; the previews read riskRewardRatio 2.25
    (T4), 2.4 (W2b) and 1.6 (W3) beside every stop. No v0.14.0 probe told the two apart: they differ only on X3 (the
    T4 plan: 2.25 vs 2.0625), both above its 1.5 minimum.
  * A last leg closing 0% is the TRAIL OBJECTIVE: it earns nothing - O1 1R 50% + 2R 20% + 6R 0% "pays 1.5R" (the
    runner at 2R; at 6R it would pay 2.7) below 2; O4 the same plan at 1.5 stages clean - and the preview's runner trail
    reads 2.7R beside every stop. Each trail read the plan's farthest target x 0.45 (the base plan's
    trailingGivebackPct 45: O4 2.7 = 6 x 0.45; T4, W2b 1.35 = 3 x 0.45; W3 0.99 = 2.2 x 0.45 at stops ATR 1.5 and 2)
    except W3 at stop ATR 1, which read runnerTrail {atrMultiple 1, rMultiple 1} - 1.0R, apparently a one-ATR floor.
    How the trail is sized is recorded, not modelled: one giveback was sent.
  * Refused at input (no draft): a 0% leg after legs closing 100% ("A target closing 0% needs a runner to govern; this
    plan closes everything before it", O2), a 0% leg that is not the last ("Only the last target of an exit plan may
    close 0%", O3; a 0% FIRST leg answers X7's message alone), a runner of 1 - 4% ("A runner holds 0% or at least 5% of
    the position; this plan leaves 3%", S1: measured at 3% only), a leg closing 1 - 4% ("A target closes at least 5%",
    S2: measured on a first leg only). Both extensions come from the message text and fail closed; a non-first 3% leg
    and a 1% runner are to be probed.
  * minRiskRewardRatio is refused off its 0.25 step as a draft error on the dial ("minRiskRewardRatio must be a
    multiple of 0.25", W2 at 2.2; omega.execution.validate_execution). An UPDATE restaging TRADE_LEVEL_POLICY carries
    the live minRiskRewardRatio as read: one off the step is a warning (EXECUTION_CARRIED_OFF_STEP,
    StrategyPlan.update_menu_findings), as the stage's answer on an UPDATE is unmeasured.
  * Raising minRiskRewardRatio above an all-R plan's pay is, on a CREATE, the plan below the minimum (W1, O1). The
    UPDATE that raises the dial alone is unmeasured (StrategyPlan.update_menu_findings judges the staged axis whole).

The default menu (`default_menu`) is the ATR / R part of the platform's migration default, read 2026-11-11 from three
live strategies (Dunkirk, VWAP Reject 4h, TPO Prior Session Levels LONG): stops ATR 1 / 1.5 / 2 whatever the strategy's
own stop range is (VWAP Reject 4h: maxStopLossAtrMultiple 1.8, ATR 2 in its menu), targets R 1.5 / 2 / 3 from the
strategy's minRiskRewardRatio up (2 -> R 2 / 3). Its band LEVEL entries are left out: they stage only on a report
that reads the bands.
"""
from __future__ import annotations

import copy
import json
import math
from fractions import Fraction

from . import preflight as P
from .contract import load, stage_schema
from .validate import Finding

SIDES = ("LONG", "SHORT")
STAGE = "stage_strategy_draft"
DEFAULT_ATR_STOPS = (1, 1.5, 2)
DEFAULT_R_TARGETS = (1.5, 2, 3)
LEVEL_REF_KEYS = ("metric", "timeframe", "bars", "offset", "knobs", "windowExtreme")
LEVEL_TRIGGERS = ("STOP_THROUGH_LEVEL", "ON_RETEST")
PROBES = "data/audit/trade_level_menu_168_2026-11-11.json"
EXIT_PLAN_PROBES = "data/audit/exit_plans_170_2026-11-12.json"
RUNNER_PROBES = "data/audit/exit_plan_runner_171_2026-11-12.json"
EXIT_PLAN_FULL = 100          # a plan's legs close at most 100% of the position together
EXIT_PLAN_SHARE_MIN = 5       # a closing leg closes, and a runner holds, at least 5% (probes S1, S2)


def _doc(schema: dict | None) -> dict:
    """The stage-schema capture judged against: the pinned one (omega.contract.stage_schema) unless a caller names
    another - the 168 probes replay against the 168.3.0 capture, which served `targets`."""
    return stage_schema() if schema is None else schema


def _root(schema: dict | None = None) -> dict:
    return _doc(schema)[STAGE]["inputSchema"]


def _axis(name: str, schema: dict | None = None) -> dict:
    return _root(schema)["properties"]["axes"]["properties"][name]


def menu_required(schema: dict | None = None) -> bool:
    """Does the write schema require a menu on TRADE_LEVEL_POLICY? (True from the 168 capture on; a capture
    before it has no such property, and an axis carrying one would be refused as an unrecognized key.)"""
    return "tradeLevelMenu" in _axis("TRADE_LEVEL_POLICY", schema).get("required", [])


def menu_form(schema: dict | None = None) -> str:
    """How a direction names its profit side in the write schema: `exitPlans` since contract 170, `targets` at 168."""
    return "exitPlans" if "exitPlans" in _root(schema)["$defs"]["directionTradeLevelMenu"]["properties"] else "targets"


def list_bounds(kind: str, schema: dict | None = None) -> tuple[int, int]:
    """`stops` | `targets` (168) | `exitPlans` (170) | `legs` (170: the targets of one exit plan) -> (minItems,
    maxItems), read from the write schema."""
    node = (_root(schema)["$defs"]["exitPlan"]["properties"]["targets"] if kind == "legs" else
            _root(schema)["$defs"]["directionTradeLevelMenu"]["properties"][kind])
    return node["minItems"], node["maxItems"]


def level_knobs(schema: dict | None = None) -> tuple[str, ...]:
    """The knob names a level reference carries under `knobs` (the write schema's conditionLevelRef)."""
    return tuple(_root(schema)["$defs"]["conditionLevelRef"]["properties"]["knobs"]["properties"])


def level_ref(metric: str, timeframe: dict | None = None, *, knobs: dict | None = None, offset: int = 0) -> dict:
    """A level reference with all six required keys: `metric` read at `timeframe` (default the strategy's anchor)."""
    return {"metric": metric, "timeframe": dict(timeframe or {"rel": "anchor"}), "bars": None, "offset": offset,
            "knobs": dict(knobs or {}), "windowExtreme": None}


def default_menu(min_rr, schema: dict | None = None) -> dict:
    """The menu a plan stages when its thesis names none (see the module docstring for where it was read). A
    minRiskRewardRatio that is not a number is not this function's to judge (the axis walk refuses the dial): the
    three targets are kept. Since contract 170 each R target is an exit plan of one leg closing 100% - the shape the
    platform migrated every stored target to."""
    usable = isinstance(min_rr, (int, float)) and not isinstance(min_rr, bool) and min_rr == min_rr
    targets = ([m for m in DEFAULT_R_TARGETS if m >= min_rr] or [min_rr]) if usable else list(DEFAULT_R_TARGETS)
    side = {"stops": [{"kind": "ATR", "atrMultiple": m} for m in DEFAULT_ATR_STOPS],
            "targets": [{"kind": "R_MULTIPLE", "multiple": m} for m in targets]}
    if menu_form(schema) == "exitPlans":
        side = migrate_side(side)
    return {s: copy.deepcopy(side) for s in SIDES}


def migrate_side(side: dict) -> dict:
    """One direction of a 168 menu ({stops, targets}) as contract 170 holds it ({stops, exitPlans}): each target an
    exit plan of ONE leg closing 100% - the platform's own migration, read on all 16 account strategies at 170.0.0
    (2026-11-12). Anything else in `side` is kept as it is."""
    out = {k: copy.deepcopy(v) for k, v in side.items() if k != "targets"}
    out["exitPlans"] = [{"targets": [{"method": copy.deepcopy(t), "closePct": EXIT_PLAN_FULL}]}
                        for t in side.get("targets") or []]
    return out


def migrate_menu(menu: dict) -> dict:
    """A whole 168 menu in the 170 form (migrate_side per direction); a menu already in it, or not a menu, as it is.
    Only a menu whose every direction names `targets` and no `exitPlans` is migrated: one carrying both, or one side in
    each form, is left as written, and the write schema's walk refuses it (review 2026-11-12: migrating a side with
    both silently replaced its exit plans)."""
    if not isinstance(menu, dict) or not all(isinstance(menu.get(s), dict) and "targets" in menu[s]
                                             and "exitPlans" not in menu[s] for s in SIDES):
        return menu
    return {**menu, **{s: migrate_side(menu[s]) for s in SIDES}}


# --- the write schema's shape ------------------------------------------------------------------------------------
def _shape(value, node: dict, prefix: str, code: str, schema: dict | None = None) -> list[Finding]:
    """Every FAIL of walking `value` against the write schema's `node`, as findings under `prefix`. The walk checks a
    metric key against the served roster too (omega.preflight.read_roster), so a key the platform does not serve is
    refused here."""
    out: list[Finding] = []
    for f in P.diff_schema(value, node, _root(schema), roster=P.read_roster(_doc(schema))):
        if f.verdict != "FAIL":
            continue
        path = prefix + (f.path if f.path.startswith("[") or not f.path else "." + f.path)
        unknown_metric = f.cls in ("ENUM", "PATTERN") and f.path.endswith(".metric")
        out.append(Finding("error", "TRADE_MENU_LEVEL_UNKNOWN_METRIC" if unknown_metric else code, path,
                           f"{f.detail} [{f.cls}: the write schema of {_doc(schema)['contractVersion']}]"))
    return out


# --- level identity ----------------------------------------------------------------------------------------------
def _timeframe(ref: dict, anchor: str) -> str:
    """A timeframe reference as far as its equivalences were measured: {rel: anchor} and {abs: <anchor>} are one
    reading (L2, M7); every other reference is itself ({abs: 4h} M4, {rel: lower} M8)."""
    if ref.get("rel") == "anchor":
        return anchor
    return ref["abs"] if "abs" in ref else f"rel:{ref.get('rel')}"


def _identity(metric: str, timeframe: dict, knobs: dict, offset: int, anchor: str) -> tuple:
    return (metric, _timeframe(timeframe, anchor), tuple(sorted(knobs.items())), offset)


def report_readings(sections: list[dict], anchor: str) -> tuple[set[tuple], set[tuple], set[str]]:
    """What a staged REPORT holds, read as the menu's level rule reads it -> (yields, developing, unmeasured):

    `yields`      the identities (metric, timeframe, knobs, offset) a per-coin custom section holds: each column's own
                  metric through ANY transform (V1, V6, M1; a spread's base M6), and the plain operand of a spread
                  whose column carries no knob and no offset (V2);
    `developing`  those of them whose column reads bars "all";
    `unmeasured`  metric names the report holds only where no probe looked: in a market, reference or platform
                  section, as the operand of a spread with a knob or an offset, or as an operand under an average.
    Whether a reading is a PRICE is judged by the caller against the corpus."""
    knob_names = set(level_knobs())
    yields: set[tuple] = set()
    developing: set[tuple] = set()
    unmeasured: set[str] = set()
    for section in sections:
        columns = section.get("columns") or []
        per_coin = (section.get("kind", "custom") == "custom" and section.get("marketScope") is None
                    and section.get("benchmarkTicker") is None)
        for column in columns:
            operands = [o for o in (column.get("inputs") or []) if isinstance(o, dict) and o.get("metric")]
            if not per_coin:
                unmeasured.update([column["metric"], *(o["metric"] for o in operands)])
                continue
            knobs = {k: column[k] for k in knob_names if column.get(k) is not None}
            offset = column.get("offset") or 0
            identity = _identity(column["metric"], column["timeframe"], knobs, offset, anchor)
            yields.add(identity)
            if column.get("bars") == "all":
                developing.add(identity)
            for operand in operands:
                # a chained spread's operand (<metric> x ema -> spread, contract 168) is unmeasured as a level too
                if (operand.get("transformId") or operand.get("window") or knobs or offset
                        or column.get("transformId") != "spread"):
                    unmeasured.add(operand["metric"])
                else:
                    operand_identity = _identity(operand["metric"], column["timeframe"], {}, 0, anchor)
                    yields.add(operand_identity)
                    if column.get("bars") == "all":
                        developing.add(operand_identity)
    return yields, developing, unmeasured


def _level_findings(ref: dict, path: str, side: str, role: str, readings: tuple, anchor: str) -> tuple[list[Finding], tuple | None]:
    """The findings on one WELL-FORMED level reference (the schema walk ran first) and its identity."""
    yields, developing, unmeasured = readings
    metric = ref["metric"]
    known = load().metrics.get(metric)
    if known is None:
        return [Finding("error", "TRADE_MENU_LEVEL_UNKNOWN_METRIC", f"{path}.metric",
                        f"{metric!r} is not a metric of the corpus")], None
    identity = _identity(metric, ref["timeframe"], ref["knobs"], ref["offset"], anchor)
    if ref["windowExtreme"] is not None:
        return [Finding("error", "TRADE_MENU_LEVEL_UNMEASURED", path,
                        f"a windowExtreme on a menu level was not measured ({PROBES} staged none); omega does not "
                        f"guess whether the report yields it")], None
    if known.native_output.get("unit") != "price":
        return [Finding("error", "TRADE_MENU_LEVEL_NOT_PRICE", path,
                        f"{metric} reads {known.native_output.get('unit')!r}, not a price: the stage refuses it as "
                        f"\"not a level this strategy's report yields. Choose one of the report's price levels\" "
                        f"(measured on ADX read through `value`, probe M2)")], identity
    described = (f"the {side} {role} level {metric} at {json.dumps(ref['timeframe'])}"
                 f"{', knobs ' + json.dumps(ref['knobs']) if ref['knobs'] else ''}"
                 f"{', offset ' + str(ref['offset']) if ref['offset'] else ''}")
    refused = (f"the stage refuses it (\"A {side} {role} level is not a level this strategy's report yields ... add a "
               f"column that reads it\")")
    if ref["bars"] == "all":
        if identity in developing:
            return [Finding("error", "TRADE_MENU_LEVEL_UNMEASURED", path,
                            f"{described} asks bars 'all' where a column also reads 'all': that pairing was not "
                            f"measured ({PROBES}); omega does not guess")], identity
        return [Finding("error", "TRADE_MENU_LEVEL_NOT_YIELDED", path,
                        f"{described} asks bars 'all' and no column reads it Developing: {refused} (probe M9)")], identity
    if identity in yields:
        return [], identity
    if metric in unmeasured:
        return [Finding("error", "TRADE_MENU_LEVEL_UNMEASURED", path,
                        f"{described}: this plan's report holds {metric} only where no probe measured a level - in a "
                        f"market, reference or platform section, or as the operand of a spread with a knob, an offset "
                        f"or an average ({PROBES}); omega does not guess whether it yields the level")], identity
    return [Finding("error", "TRADE_MENU_LEVEL_NOT_YIELDED", path,
                    f"{described} is not a reading this plan's per-coin custom sections hold: {refused}. A column (any "
                    f"transform), a spread's base or its plain operand must read the same metric at the same "
                    f"timeframe, knobs and offset (probes tc_default_menu, V10, L3a, L4)")], identity


def validate_entry_levels(entry: dict, *, sections: list[dict], anchor: str) -> list[Finding]:
    """An ENTRY axis's `entry`, judged as the stage judges it: its shape by the write schema (a level trigger requires
    `levels`, a close trigger takes none), and each level by the menu's level rule - a level the report reads stages
    (probe E1), one it does not is refused on `entry.levels.<side>` (probe E2). omega's own plans stage
    ON_CANDLE_CLOSE only (generate.ENTRY_MIRROR); this judges an entry a caller brings."""
    node = _axis("ENTRY")["properties"]["entry"]
    shape = _shape(entry, node, "entry", "ENTRY_LEVELS_SHAPE")
    if shape or not isinstance(entry, dict) or entry.get("trigger") not in LEVEL_TRIGGERS:
        return shape
    readings = report_readings(sections, anchor)
    out: list[Finding] = []
    for side in SIDES:
        out += _level_findings(entry["levels"][side], f"entry.levels.{side}", side, "entry", readings, anchor)[0]
    return out


# --- validation --------------------------------------------------------------------------------------------------
def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_menu(menu, *, dials: dict, sections: list[dict], anchor: str, schema: dict | None = None,
                  trailing_enabled: bool | None = None) -> list[Finding]:
    """Every finding on a trade level menu staged with `dials` (the TRADE_LEVEL_POLICY dials: minRiskRewardRatio and
    the stop range) beside the REPORT `sections` (wire form) of a strategy anchored at `anchor`, judged against the
    pinned write schema (or `schema`, a stage-schema capture). `trailing_enabled` is the POSITION_MANAGEMENT
    trailingEnabled the menu stages beside: False refuses a plan that leaves a runner (probes T1, T2); None (not
    known to the caller) cannot judge the rule and warns on each such plan
    (TRADE_MENU_EXIT_PLAN_RUNNER_TRAILING_UNKNOWN) instead of passing it. A menu the write schema refuses gets its
    shape findings and nothing else: the rules are judged on a well-formed menu only."""
    root = "tradeLevelMenu"
    shape = _shape(menu, _axis("TRADE_LEVEL_POLICY", schema)["properties"]["tradeLevelMenu"], root, "TRADE_MENU_SHAPE",
                   schema)
    if shape:
        return shape
    out: list[Finding] = []
    readings = report_readings(sections, anchor)
    min_rr = dials.get("minRiskRewardRatio")
    lo, hi = dials.get("minStopLossAtrMultiple"), dials.get("maxStopLossAtrMultiple")
    exit_plans = menu_form(schema) == "exitPlans"
    for side in SIDES:
        seen: dict[str, dict[tuple, str]] = {"stops": {}, "targets": {}}
        if exit_plans:
            out += _exit_plan_findings(menu[side]["exitPlans"], side, min_rr, readings, anchor, seen["targets"],
                                       trailing_enabled)
        for kind, role in (("stops", "stop"),) if exit_plans else (("stops", "stop"), ("targets", "target")):
            for i, entry in enumerate(menu[side][kind]):
                path = f"{root}.{side}.{kind}[{i}]"
                if entry["kind"] == "R_MULTIPLE" and _number(min_rr) and entry["multiple"] < min_rr:
                    out.append(Finding("error", "TRADE_MENU_TARGET_BELOW_MIN_RR", f"{path}.multiple",
                                       f"the {side} {entry['multiple']}R target is below this strategy's minimum "
                                       f"risk-reward of {min_rr}: the stage refuses it (\"every pair it makes would be "
                                       f"refused. Remove it or lower the minimum\", probe V3)"))
                if entry["kind"] == "ATR" and _number(lo) and _number(hi) and not lo <= entry["atrMultiple"] <= hi:
                    out.append(Finding("warning", "TRADE_MENU_STOP_OUTSIDE_RANGE", f"{path}.atrMultiple",
                                       f"the {side} ATR {entry['atrMultiple']} stop is outside this strategy's stop "
                                       f"range {lo} - {hi}xATR. The stage accepts it (probe V9; the platform's own "
                                       f"migration default does the same); what a decision does with it is not "
                                       f"measured"))
                if entry["kind"] == "LEVEL":
                    findings, identity = _level_findings(entry["level"], f"{path}.level", side, role, readings, anchor)
                    out += findings
                    if identity is not None:
                        seen[kind].setdefault(identity, path)
        for identity, path in seen["targets"].items():
            if identity in seen["stops"]:
                out.append(Finding("error", "TRADE_MENU_LEVEL_BOTH_SIDES", path if exit_plans else f"{path}.level",
                                   f"the {side} target {identity[0]} is also a {side} stop option "
                                   f"({seen['stops'][identity]}): the stage refuses it (\"one level cannot be both the "
                                   f"loss side and the profit side of a trade\", probe V8; Y9 for an exit plan's leg)"))
    return out


def _exact(value) -> Fraction:
    """A number as the decimal it was written as: Fraction(str(x)), so 0.6 is 3/5, not the float nearest it."""
    return Fraction(str(value))


def plan_pays_exact(legs: list[dict]) -> Fraction | None:
    """plan_pays, computed exactly: each multiple and closePct read as the decimal it was written as, so a plan paying
    exactly the minimum compares equal to it. In binary floats 0.6R 50% + 1.4R 28% pays 0.9999999999999999 and
    0.6R 50% + 1.9R 9% pays 1.2499999999999998; exactly they pay 1 and 1.25 (review 2026-11-12, finding 1)."""
    closing = [leg for leg in legs if leg["closePct"] > 0]
    closed = sum(leg["closePct"] for leg in closing)
    if not closing or closed > EXIT_PLAN_FULL or any(leg["method"]["kind"] != "R_MULTIPLE" for leg in legs):
        return None
    runner = EXIT_PLAN_FULL - _exact(closed)
    return (sum(_exact(leg["method"]["multiple"]) * _exact(leg["closePct"]) for leg in closing)
            + runner * _exact(closing[-1]["method"]["multiple"])) / EXIT_PLAN_FULL


def plan_pays(legs: list[dict]) -> float | None:
    """What an exit plan pays, as the stage judges it against minRiskRewardRatio: share-weighted over the whole
    position - each leg's closePct at its R, the runner (what the plan does not close) at the R of the LAST leg that
    closes a share; a last leg closing 0% (the trail objective) earns nothing. Measured at 171.0.0 (RUNNER_PROBES W1
    "pays 2.4R", O1 "pays 1.5R", the previews of T4 / W2b / W3 / O4); on a plan closing 100% it is v0.14.0's
    closePct-weighted mean (EXIT_PLAN_PROBES Y1 - Y8). None for a plan with a level leg (its R is known only at a
    decision), one that closes nothing, or one closing more than 100% (refused at input, X4, X5). A float, for
    display: the rule compares plan_pays_exact."""
    exact = plan_pays_exact(legs)
    return None if exact is None else float(exact)


def plan_pays_v0_14_0(legs: list[dict]) -> float | None:
    """v0.14.0's reading, kept to show where it parted from the stage: the closePct-weighted mean over the share the
    plan closes. It agrees with plan_pays on every plan closing 100% and parts on a runner after two different R legs
    (W1: 2.0 here, the stage "pays 2.4R"). Nothing judges by it."""
    closed = sum(leg["closePct"] for leg in legs)
    if closed <= 0 or any(leg["method"]["kind"] != "R_MULTIPLE" for leg in legs):
        return None
    return sum(leg["method"]["multiple"] * leg["closePct"] for leg in legs) / closed


def _exit_plan_findings(plans: list[dict], side: str, min_rr, readings: tuple, anchor: str,
                        seen_targets: dict, trailing_enabled: bool | None = None) -> list[Finding]:
    """The findings on one direction's WELL-FORMED exit plans (contracts 170 and 171; the module docstring names the
    probes)."""
    out: list[Finding] = []
    for p, plan in enumerate(plans):
        ppath = f"tradeLevelMenu.{side}.exitPlans[{p}]"
        legs = plan["targets"]
        closed = sum(leg["closePct"] for leg in legs)
        runner = EXIT_PLAN_FULL - closed
        if closed > EXIT_PLAN_FULL:
            out.append(Finding("error", "TRADE_MENU_EXIT_PLAN_OVER_100", f"{ppath}.targets",
                               f"the {side} exit plan's legs close {closed}% together: the stage refuses it at input "
                               f"(\"The close percentages of an exit plan sum to at most 100\", probes X4, X5)"))
        # RUNNER_UNDER_5 and LEG_UNDER_5 below each extend ONE measurement by the platform's own message text, and fail
        # closed: S1 sent only a 3% runner ("A runner holds 0% or at least 5% of the position"), so a 1, 2 or 4% runner
        # is refused on the sentence; S2 sent a 3% leg only as the FIRST leg ("A target closes at least 5%"), so a later
        # leg of 1 - 4% is refused on the sentence too. Probe both at the next platform probe: a 3% leg that is not the
        # first, and a 1% runner.
        elif 0 < runner < EXIT_PLAN_SHARE_MIN:
            out.append(Finding("error", "TRADE_MENU_EXIT_PLAN_RUNNER_UNDER_5", f"{ppath}.targets",
                               f"the {side} exit plan leaves a {runner}% runner: the stage refuses it at input (\"A "
                               f"runner holds 0% or at least 5% of the position\", probe S1)"))
        if legs[0]["closePct"] == 0:
            out.append(Finding("error", "TRADE_MENU_EXIT_PLAN_FIRST_LEG_EMPTY", f"{ppath}.targets[0].closePct",
                               f"the {side} exit plan's first leg closes 0%: the stage refuses it at input (\"An exit "
                               f"plan's first target closes a share\", probe X7)"))
        for i, leg in enumerate(legs):
            lpath = f"{ppath}.targets[{i}].closePct"
            if 0 < leg["closePct"] < EXIT_PLAN_SHARE_MIN:
                out.append(Finding("error", "TRADE_MENU_EXIT_PLAN_LEG_UNDER_5", lpath,
                                   f"the {side} exit plan's leg {i} closes {leg['closePct']}%: the stage refuses it at "
                                   f"input (\"A target closes at least 5%\", probe S2)"))
            if i and leg["closePct"] == 0 and i < len(legs) - 1:
                out.append(Finding("error", "TRADE_MENU_EXIT_PLAN_ZERO_NOT_LAST", lpath,
                                   f"the {side} exit plan's leg {i} closes 0% and is not the last: the stage refuses "
                                   f"it at input (\"Only the last target of an exit plan may close 0%\", probe O3)"))
            if (i and leg["closePct"] == 0 and i == len(legs) - 1
                    and sum(x["closePct"] for x in legs[:i]) >= EXIT_PLAN_FULL):
                out.append(Finding("error", "TRADE_MENU_EXIT_PLAN_ZERO_WITHOUT_RUNNER", lpath,
                                   f"the {side} exit plan's last leg closes 0% after legs closing everything: the stage "
                                   f"refuses it at input (\"A target closing 0% needs a runner to govern\", probe O2)"))
        if trailing_enabled is False and runner > 0:
            out.append(Finding("error", "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING", ppath,
                               f"the {side} exit plan closes {closed}% and leaves a {runner}% runner while "
                               f"POSITION_MANAGEMENT.trailingEnabled is false: the stage refuses it (\"nothing would "
                               f"exit it. Turn Trailing on, or close 100% across the plan's targets\", probes T1, T2)"))
        elif trailing_enabled is None and runner > 0:
            # the rule cannot be judged without Trailing: say so rather than pass the plan silently (review 2026-11-12)
            out.append(Finding("warning", "TRADE_MENU_EXIT_PLAN_RUNNER_TRAILING_UNKNOWN", ppath,
                               f"the {side} exit plan closes {closed}% and leaves a {runner}% runner, and "
                               f"POSITION_MANAGEMENT.trailingEnabled is not known here: the stage refuses a runner "
                               f"while Trailing is off (probes T1, T2). Pass the trailingEnabled the plan stages beside"))
        out_of_order = False
        for i, leg in enumerate(legs):
            method, lpath = leg["method"], f"{ppath}.targets[{i}]"
            if method["kind"] == "LEVEL":
                findings, identity = _level_findings(method["level"], f"{lpath}.method.level", side, "target",
                                                     readings, anchor)
                out += findings
                if identity is not None:
                    seen_targets.setdefault(identity, f"{lpath}.method.level")
            before = legs[i - 1]["method"] if i else None
            if (before is not None and method["kind"] == before["kind"] == "R_MULTIPLE"
                    and method["multiple"] <= before["multiple"]):
                out_of_order = True
                out.append(Finding("error", "TRADE_MENU_EXIT_PLAN_OUT_OF_ORDER", lpath,
                                   f"the {side} exit plan's targets run away from entry: {method['multiple']}R follows "
                                   f"{before['multiple']}R; the stage refuses it (\"List each target farther than the "
                                   f"one before it\", probes X8, X9, X11, Z4)"))
        # a plan out of order is judged on its order alone: X11 (1.5R then 1.2R) pays 1.35R, below the minimum, and the
        # stage named only the order
        pays = None if out_of_order else plan_pays_exact(legs)
        if pays is not None and _number(min_rr) and math.isfinite(min_rr) and pays < _exact(min_rr):
            out.append(Finding("error", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR", ppath,
                               f"the {side} exit plan pays {round(float(pays), 4)}R (each share at its leg's R, a "
                               f"runner at the last leg that closes a share), below this strategy's minimum "
                               f"risk-reward of {min_rr}: the stage refuses it (\"every pair it makes would be "
                               f"refused\", probes Y1 - Y7, W1, O1)"))
        if len(legs) > 1 and any(leg["method"]["kind"] == "LEVEL" for leg in legs):
            out.append(Finding("warning", "TRADE_MENU_EXIT_PLAN_JUDGED_PER_DECISION", ppath,
                               f"the {side} exit plan mixes a level leg with others: the stage judges neither what it "
                               f"pays nor the order across the level (probes Z1 - Z3); a decision does, refusing a pair "
                               f"TARGETS_OUT_OF_ORDER or RISK_REWARD_TOO_LOW"))
    return out
