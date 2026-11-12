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

The default menu (`default_menu`) is the ATR / R part of the platform's migration default, read 2026-11-11 from three
live strategies (Dunkirk, VWAP Reject 4h, TPO Prior Session Levels LONG): stops ATR 1 / 1.5 / 2 whatever the strategy's
own stop range is (VWAP Reject 4h: maxStopLossAtrMultiple 1.8, ATR 2 in its menu), targets R 1.5 / 2 / 3 from the
strategy's minRiskRewardRatio up (2 -> R 2 / 3). Its band LEVEL entries are left out: they stage only on a report
that reads the bands.
"""
from __future__ import annotations

import copy
import json
from functools import lru_cache

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


@lru_cache(maxsize=1)
def _root() -> dict:
    return stage_schema()[STAGE]["inputSchema"]


def _axis(name: str) -> dict:
    return _root()["properties"]["axes"]["properties"][name]


def menu_required() -> bool:
    """Does the pinned write schema require a menu on TRADE_LEVEL_POLICY? (True from the 168 capture on; a capture
    before it has no such property, and an axis carrying one would be refused as an unrecognized key.)"""
    return "tradeLevelMenu" in _axis("TRADE_LEVEL_POLICY").get("required", [])


def list_bounds(kind: str) -> tuple[int, int]:
    """`stops` | `targets` -> (minItems, maxItems), read from the write schema."""
    node = _root()["$defs"]["directionTradeLevelMenu"]["properties"][kind]
    return node["minItems"], node["maxItems"]


def level_knobs() -> tuple[str, ...]:
    """The knob names a level reference carries under `knobs` (the write schema's conditionLevelRef)."""
    return tuple(_root()["$defs"]["conditionLevelRef"]["properties"]["knobs"]["properties"])


def level_ref(metric: str, timeframe: dict | None = None, *, knobs: dict | None = None, offset: int = 0) -> dict:
    """A level reference with all six required keys: `metric` read at `timeframe` (default the strategy's anchor)."""
    return {"metric": metric, "timeframe": dict(timeframe or {"rel": "anchor"}), "bars": None, "offset": offset,
            "knobs": dict(knobs or {}), "windowExtreme": None}


def default_menu(min_rr) -> dict:
    """The menu a plan stages when its thesis names none (see the module docstring for where it was read). A
    minRiskRewardRatio that is not a number is not this function's to judge (the axis walk refuses the dial): the
    three targets are kept."""
    usable = isinstance(min_rr, (int, float)) and not isinstance(min_rr, bool) and min_rr == min_rr
    targets = ([m for m in DEFAULT_R_TARGETS if m >= min_rr] or [min_rr]) if usable else list(DEFAULT_R_TARGETS)
    side = {"stops": [{"kind": "ATR", "atrMultiple": m} for m in DEFAULT_ATR_STOPS],
            "targets": [{"kind": "R_MULTIPLE", "multiple": m} for m in targets]}
    return {s: copy.deepcopy(side) for s in SIDES}


# --- the write schema's shape ------------------------------------------------------------------------------------
def _shape(value, node: dict, prefix: str, code: str) -> list[Finding]:
    """Every FAIL of walking `value` against the write schema's `node`, as findings under `prefix`. The walk checks a
    metric key against the served roster too (omega.preflight.read_roster), so a key the platform does not serve is
    refused here."""
    out: list[Finding] = []
    for f in P.diff_schema(value, node, _root(), roster=P.read_roster(stage_schema())):
        if f.verdict != "FAIL":
            continue
        path = prefix + (f.path if f.path.startswith("[") or not f.path else "." + f.path)
        unknown_metric = f.cls in ("ENUM", "PATTERN") and f.path.endswith(".metric")
        out.append(Finding("error", "TRADE_MENU_LEVEL_UNKNOWN_METRIC" if unknown_metric else code, path,
                           f"{f.detail} [{f.cls}: the write schema of {stage_schema()['contractVersion']}]"))
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
                if operand.get("transformId") or knobs or offset:
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


def validate_menu(menu, *, dials: dict, sections: list[dict], anchor: str) -> list[Finding]:
    """Every finding on a trade level menu staged with `dials` (the TRADE_LEVEL_POLICY dials: minRiskRewardRatio and
    the stop range) beside the REPORT `sections` (wire form) of a strategy anchored at `anchor`. A menu the write
    schema refuses gets its shape findings and nothing else: the rules are judged on a well-formed menu only."""
    root = "tradeLevelMenu"
    shape = _shape(menu, _axis("TRADE_LEVEL_POLICY")["properties"]["tradeLevelMenu"], root, "TRADE_MENU_SHAPE")
    if shape:
        return shape
    out: list[Finding] = []
    readings = report_readings(sections, anchor)
    min_rr = dials.get("minRiskRewardRatio")
    lo, hi = dials.get("minStopLossAtrMultiple"), dials.get("maxStopLossAtrMultiple")
    for side in SIDES:
        seen: dict[str, dict[tuple, str]] = {"stops": {}, "targets": {}}
        for kind, role in (("stops", "stop"), ("targets", "target")):
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
                out.append(Finding("error", "TRADE_MENU_LEVEL_BOTH_SIDES", f"{path}.level",
                                   f"the {side} target {identity[0]} is also a {side} stop option "
                                   f"({seen['stops'][identity]}): the stage refuses it (\"one level cannot be both the "
                                   f"loss side and the profit side of a trade\", probe V8)"))
    return out
