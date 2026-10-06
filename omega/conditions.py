"""Author strategy conditions, and type-check them offline against the report.

A condition is a deterministic read of report columns, resolved server-side at
prompt-build time. The platform is explicit about what they are NOT:

    "They are advisory: they may make you more selective, never less - they do
     not gate, score, or qualify anything."

The gate is `minAggregateScore` over the signal scorecard. Conditions shape what the
agent reads: a `conditionKey` interpolates into `marketReadText`, so the agent sees a
named verdict instead of re-deriving four filters.

The value here is the cross-check: a clause names a header, an operator and a literal,
and all three must agree with what the column actually compiles to. `validate_conditions`
catches `op:"is"` on a numeric header, a label outside the vocabulary, and a header that
no column in the report produces - offline, before a round-trip.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from .contract import DERIVED_DIR, load
from .fanout import outputs_for
from .types import CustomSection, PlatformSection, Report

CONDITION_KEY = re.compile(r"^[A-Z][A-Z0-9_]{1,39}$")
GROUP_OPS = ("ALL", "ANY", "NOT", "N_OF")
NUMERIC_OPS = ("lt", "lte", "gte", "gt")
VERDICTS = ("UP", "DOWN", "NEITHER", None)
CARRIER_VERDICTS = ("UP", "DOWN", "NEITHER")
# Contract 91.0.0 (data/contract/stage_strategy_draft/schema_20261005T194629Z.json, the
# CONDITIONS axis): a condition is additionalProperties:false over exactly these six keys,
# all required. v84 removed `closes` (the hold moved onto each clause and group), v88
# removed `exit` (an exit rule is its own condition and names the side it closes), and
# 61.0.0 had already retired `clock`. Each of the three is now refused as an unknown key.
CONDITION_FIELDS = ("conditionKey", "name", "definition", "verdict", "required", "exitSide")
RETIRED_CONDITION_FIELDS = {
    "clock": "clock was retired in contract 61.0.0 and is refused as an unknown key",
    "closes": ("closes was removed at contract 84.0.0 and is refused as an unknown key; "
               "the hold is `hold: {atLeast, of}` on each clause and group"),
    "exit": ("exit was removed at contract 88.0.0 and is refused as an unknown key; an exit "
             "rule is its own condition with exitSide LONG|SHORT|BOTH (see close_on)"),
}
# v88: "Every condition requires exitSide: LONG, SHORT or BOTH for an exit rule, null for
# an entry condition. It is nullable, never optional."
EXIT_SIDES = ("LONG", "SHORT", "BOTH")
# v88, the platform's own migration of a stored `exit: true` condition: "its strategy
# gains an exit rule CLOSE_ON_<conditionKey>, a conditionRef to it closing the side its
# verdict opposed (UP -> SHORT, DOWN -> LONG, NEITHER -> BOTH)", and "both sides for a
# NEITHER or null verdict" (README "Contract history - v88").
EXIT_RULE_PREFIX = "CLOSE_ON_"
SIDE_CLOSED_BY_VERDICT = {"UP": "SHORT", "DOWN": "LONG", "NEITHER": "BOTH", None: "BOTH"}
# v84: "Every clause and every group requires hold: {atLeast, of}, whole numbers of at
# least 1. {atLeast: 1, of: 1} is one read (what every v83 condition did), {n, n} is
# 'n closes in a row', {1, n} is 'within n closes', and anything else is 'at least m of n
# closes'." The 1..5 ceiling of the retired compile schema (HOLD_MIN/HOLD_MAX) is gone:
# each column admits up to conditionHold.maxWindow / maxAtLeast, served by
# preview_strategy_report and list_strategy_vocabulary at v84+. No v84+ vocabulary read is
# on disk, so omega checks only the schema (>= 1) and the builder's atLeast <= of; the
# builder judges the window (plan 2026-10-06, measurement M2).
HOLD_ONE = (1, 1)
HOLD_KEYS = ("atLeast", "of")


OBSERVED_VOCAB = DERIVED_DIR.parent / "contract" / "columns" / "_observed_vocabulary.json"


@lru_cache(maxsize=1)
def observed_vocabulary() -> dict[str, dict]:
    """What categorical headers were MEASURED to emit, per header.

    The platform publishes a `conditionVocabulary` per categorical header, and for
    two `classifyZone` columns that published set is disjoint from reality:
    `ADX_zone` emits trending / developing / weak, `MFI14_zone` emits bearish /
    bullish, and neither ever emits the overbought / oversold / neutral it declares.

    A condition written from the declared set is permanently FALSE - not an error,
    not UNRESOLVED. So the declared set alone cannot be the legality test. This is
    the measured counterpart, used only to WIDEN what is legal.
    """
    try:
        import json as _json
        return _json.loads(OBSERVED_VOCAB.read_text(encoding="utf-8"))["headers"]
    except (OSError, KeyError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _surface() -> dict:
    return json.loads((DERIVED_DIR / "condition_surface.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def ambient_headers() -> dict[str, dict]:
    """Headers available to conditions without adding any column.

    session-field, market-breadth and reference-pairs are provided by the platform.
    They cost nothing against the report budget - which is why the includeMarketBreadth
    and includeReferencePairs templates ship with zero columns.
    """
    out: dict[str, dict] = {}
    for section_key, section in _surface()["ambientSections"].items():
        if section_key.startswith("_"):
            continue
        for o in section["outputs"]:
            out[o["header"]] = {
                "sectionKey": section_key,
                "ops": o["ops"],
                "vocab": o.get("vocab", []),
                "meaning": o["meaning"],
                # ambient values do not come from the coin's own candle series, so a
                # completed bar does not move them: no hold above 1 and no exit role
                # (CONDITION_HOLD_OPERAND_ILLEGAL / CONDITION_EXIT_READ_ILLEGAL,
                # vendor pack 31.2.28 § Conditions). They are not read off a column
                # omega can inspect either, so the three timeframe flags are False.
                "moved": False,
                "candle": False,
                "above_anchor": False,
                "below_anchor": False,
                "developing": False,
            }
    return out


# --- builders -------------------------------------------------------------
def _is_count(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 1


def hold_of(hold: tuple[int, int]) -> dict:
    """`(atLeast, of)` -> the v84 wire object `{"atLeast": m, "of": n}`.

    The schema publishes both as integers >= 1; "atLeast above of" is a builder refusal
    (v84: "a typed remediation error"), refused here too rather than shipped. No ceiling:
    the window a header admits is served per column (conditionHold.maxWindow) and judged
    by the builder."""
    try:
        at_least, of = hold
    except (TypeError, ValueError):
        raise ValueError(f"hold must be a pair (atLeast, of), got {hold!r}") from None
    if not _is_count(at_least) or not _is_count(of):
        raise ValueError(f"hold atLeast and of must be integers >= 1 (schema), got {hold!r}")
    if at_least > of:
        raise ValueError(f"hold atLeast {at_least} is above of {of} (v84: refused by the builder)")
    return {"atLeast": at_least, "of": of}


def held(n: int) -> tuple[int, int]:
    """`(n, n)`: "n closes in a row" (v84). held(1) is one read, the pre-v84 `closes: 1`."""
    return (n, n)


def col(header: str, section_key: str | None = None) -> dict:
    return {"sectionKey": section_key, "header": header}


# Every clause and group builder emits its own `hold`, defaulting to one read. The keys
# follow the schema's `required` order for each arm (kind, column, op, <operand>, hold).
def num(header: str, op: str, value: float, *, section_key: str | None = None,
        hold: tuple[int, int] = HOLD_ONE) -> dict:
    if op not in NUMERIC_OPS:
        raise ValueError(f"{op!r} is not one of {NUMERIC_OPS}")
    return {"kind": "clause", "column": col(header, section_key), "op": op, "value": value,
            "hold": hold_of(hold)}


def between(header: str, low: float, high: float, *, section_key: str | None = None,
            hold: tuple[int, int] = HOLD_ONE) -> dict:
    return {"kind": "clause", "column": col(header, section_key), "op": "between",
            "low": low, "high": high, "hold": hold_of(hold)}


def is_(header: str, label: str, *, section_key: str | None = None,
        hold: tuple[int, int] = HOLD_ONE) -> dict:
    return {"kind": "clause", "column": col(header, section_key), "op": "is", "label": label,
            "hold": hold_of(hold)}


def in_(header: str, labels: list[str], *, section_key: str | None = None,
        hold: tuple[int, int] = HOLD_ONE) -> dict:
    return {"kind": "clause", "column": col(header, section_key), "op": "in", "labels": labels,
            "hold": hold_of(hold)}


def ref(condition_key: str) -> dict:
    """A conditionRef carries no hold: the schema's ref arm is additionalProperties:false
    over exactly kind and conditionKey (v91 CONDITIONS axis)."""
    return {"kind": "conditionRef", "conditionKey": condition_key}


def group(op: str, members: list[dict], n: int | None = None, *,
          hold: tuple[int, int] = HOLD_ONE) -> dict:
    if op not in GROUP_OPS:
        raise ValueError(f"{op!r} is not one of {GROUP_OPS}")
    if op == "N_OF" and n is None:
        raise ValueError("N_OF requires n")
    out: dict[str, Any] = {"kind": "group", "op": op, "hold": hold_of(hold), "members": members}
    if n is not None:
        out["n"] = n
    return out


def all_of(*members: dict, hold: tuple[int, int] = HOLD_ONE) -> dict:
    return group("ALL", list(members), hold=hold)


def any_of(*members: dict, hold: tuple[int, int] = HOLD_ONE) -> dict:
    return group("ANY", list(members), hold=hold)


def not_(member: dict, *, hold: tuple[int, int] = HOLD_ONE) -> dict:
    return group("NOT", [member], hold=hold)


def n_of(n: int, *members: dict, hold: tuple[int, int] = HOLD_ONE) -> dict:
    return group("N_OF", list(members), n=n, hold=hold)


def _nested_holds(defn: dict) -> list[dict]:
    """The `hold` of every clause and group strictly below `defn` (refs carry none)."""
    out: list[dict] = []
    for member in (defn.get("members") or []) if isinstance(defn, dict) else []:
        if isinstance(member, dict) and member.get("kind") in ("clause", "group"):
            out.append(member.get("hold"))
            out.extend(_nested_holds(member))
    return out


def condition(key: str, name: str, definition: dict, *,
              verdict: str | None = None, required: bool = False,
              exit_side: str | None = None, hold: tuple[int, int] | None = None) -> dict:
    """One condition in the v91 shape: exactly the six keys the CONDITIONS axis declares, in
    its `required` order (conditionKey, name, definition, verdict, required, exitSide).

    `exit_side` is v88's `exitSide`: None for an entry condition, LONG / SHORT / BOTH for
    an exit rule (prefer exit_rule() or close_on() for those). The retired `exit`,
    `closes` and `clock` are not keywords here, so passing any of them raises TypeError.

    `hold`, when given, is the CONDITION's hold and omega places it on the definition's
    root node (plan 2026-10-06 § Conditions); every nested clause and group must then read
    one bar, because the builder refuses "a group hold over members that hold their own
    bars" (v84). A root conditionRef cannot carry a hold, so a hold over one is refused -
    wrap the reference in a group if a held reading of it is what you mean."""
    if exit_side is not None and exit_side not in EXIT_SIDES:
        raise ValueError(f"exit_side must be one of {EXIT_SIDES} or None (v88), got {exit_side!r}")
    if hold is not None:
        if definition.get("kind") == "conditionRef":
            raise ValueError(f"{key}: a conditionRef carries no hold (v84); the hold goes on a "
                             f"clause or group")
        if any(h != hold_of(HOLD_ONE) for h in _nested_holds(definition)):
            raise ValueError(f"{key}: the condition's hold goes on the root node; every nested "
                             f"clause and group must read {hold_of(HOLD_ONE)}")
        definition = {**definition, "hold": hold_of(hold)}
    return {"conditionKey": key, "name": name, "definition": definition,
            "verdict": verdict, "required": required, "exitSide": exit_side}


def exit_rule(key: str, name: str, definition: dict, side: str) -> dict:
    """A v88 exit rule: it closes exactly `side` when it settles TRUE on a completed bar,
    and "carries verdict: null and required: false" (CONDITION_EXIT_RULE_CARRIES_VERDICT,
    CONDITION_EXIT_RULE_REQUIRED). While it reads TRUE that side is not offered for entry."""
    if side not in EXIT_SIDES:
        raise ValueError(f"an exit rule names the side it closes, one of {EXIT_SIDES}; got {side!r}")
    return condition(key, name, definition, verdict=None, required=False, exit_side=side)


def close_on(cond: dict, *, name: str | None = None) -> dict:
    """The exit rule v88 split a stored `exit: true` condition into, for `cond`.

    The split is TWO conditions: `cond` itself stays an entry condition (it keeps its
    verdict, exitSide null) and this function returns the second, `CLOSE_ON_<key>` - a
    conditionRef to `cond`, verdict null, required false, closing the side its verdict
    opposes (UP -> SHORT, DOWN -> LONG, NEITHER or null -> BOTH). The key must still match
    ^[A-Z][A-Z0-9_]{1,39}$, so a source key longer than 31 characters is an error, never
    truncated. The platform's migrated name is not published; omega names the rule
    "Close on <key>" (at most 49 characters, inside the 80 cap) unless `name` is given."""
    if cond.get("exitSide") is not None:
        raise ValueError(f"{cond.get('conditionKey')!r} is already an exit rule "
                         f"(exitSide {cond.get('exitSide')!r}); only an entry condition is split")
    source = cond["conditionKey"]
    key = f"{EXIT_RULE_PREFIX}{source}"
    if not CONDITION_KEY.match(key):
        raise ValueError(f"{key!r} does not match ^[A-Z][A-Z0-9_]{{1,39}}$ ({len(key)} characters): "
                         f"the source key {source!r} is too long for the {EXIT_RULE_PREFIX!r} prefix")
    verdict = cond.get("verdict")
    if verdict not in SIDE_CLOSED_BY_VERDICT:
        raise ValueError(f"{source}: verdict {verdict!r} is not one of {VERDICTS}")
    return exit_rule(key, name or f"Close on {source}", ref(source), SIDE_CLOSED_BY_VERDICT[verdict])


# --- ambient clause library -----------------------------------------------
# Clauses over the three platform-provided sections. They reference data the report
# already carries, so they cost NOTHING against the column or token budget - the
# cheapest context a strategy can buy.

def tape_bullish(threshold: float = 10.0) -> dict:
    """Net breadth positive: more of the field closed up than down."""
    return num("mktBreadth_all", "gt", threshold)


def tape_bearish(threshold: float = -10.0) -> dict:
    """Net breadth negative - a broadly red field."""
    return num("mktBreadth_all", "lt", threshold)


def crowd_leaning_up(threshold: float = 60.0) -> dict:
    """The session's players are mostly picking up. Confirmation for a trend thesis,
    a fade target for a contrarian one."""
    return num("fieldUpBias_session", "gt", threshold)


def crowd_leaning_down(threshold: float = 40.0) -> dict:
    return num("fieldUpBias_session", "lt", threshold)


def crowd_concentrated(threshold: float = 40.0) -> dict:
    """Captain picks piling onto one coin - a crowding read."""
    return num("captConc_session", "gt", threshold)


def stables_at_par(tolerance: float = 0.5) -> dict:
    """Both stablecoin pairs near par. Use as a risk-off veto: a depeg is the market
    telling you something the indicators have not priced yet."""
    return all_of(between("usdtUsdDev_market", -tolerance, tolerance),
                  between("usdcUsdtDev_market", -tolerance, tolerance))


AMBIENT_CLAUSES = {
    "tape_bullish": tape_bullish,
    "tape_bearish": tape_bearish,
    "crowd_leaning_up": crowd_leaning_up,
    "crowd_leaning_down": crowd_leaning_down,
    "crowd_concentrated": crowd_concentrated,
    "stables_at_par": stables_at_par,
}


# --- validation -----------------------------------------------------------
@dataclass(frozen=True)
class ConditionFinding:
    severity: Literal["error", "warning"]
    condition_key: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.condition_key}{self.path}: {self.message}"


def _anchor_side(column, anchor: str, order: list[str]) -> tuple[bool, bool]:
    """(above_anchor, below_anchor) for one column's timeframe reference.

    `rel` is resolved by name: regime is the higher frame, lower the retained lower
    series, anchor the strategy timeframe itself. An `abs` reference is placed by its
    index in `absoluteTimeframes` (data/contract/vocabulary/_shared.json, 13 values)
    against the report anchor's index. An abs reference EQUAL to the anchor is neither
    above nor below - "at or above the strategy timeframe" admits it.
    """
    tf = column.timeframe
    rel = getattr(tf, "rel", None)
    if rel is not None:
        return rel == "regime", rel == "lower"
    abs_tf = getattr(tf, "abs", None)
    if abs_tf not in order or anchor not in order:
        return False, False
    here, there = order.index(abs_tf), order.index(anchor)
    return here > there, here < there


def report_headers(report: Report) -> dict[str, dict]:
    """Every header the report exposes to conditions, ambient headers included.

    Each entry carries five booleans the 61.0.1 read rules turn on:
      moved         a completed bar MOVES the header: it resolves from this coin's own
                    candle series (a non-timeless metric on a custom section), at any
                    offset. This is the exit rule's operand test - the vendor's exit
                    sentence rules out "a frame-inert operand" and a developing read,
                    and says nothing about offset.
      candle        `moved` AND the column reads offset 0 - the hold rule's operand
                    test, which does name the offset ("at offset 0", and "a non-zero
                    offset" is in its refusal list).
      above_anchor  its column reads a timeframe above the report anchor
      below_anchor  ... below it (the retained lower series)
      developing    above_anchor and bars="all" - the higher-timeframe bar still in
                    progress at the strategy close, which REPAINTS until it completes.
                    Left unset, bars above the anchor default to Confirmed, so an unset
                    column is never developing (vendor pack 31.2.28 § Conditions).
    """
    c = load()
    order = list(c.shared["absoluteTimeframes"])
    out = dict(ambient_headers())
    for section in report.sections:
        if isinstance(section, PlatformSection):
            tmpl = c.platform_templates.get(section.sectionKey)
            if not tmpl:
                continue
            # platform columns may use privileged transforms; predict what we can
            from .types import Column
            for spec in tmpl["columns"]:
                try:
                    for o in outputs_for(Column.model_validate(spec), c):
                        # conservative: the published hold rule names "a header
                        # resolved from this coin's own candle series"; only
                        # custom-candle-section headers are treated as eligible
                        # offline, platform-section headers are not, and their
                        # timeframe placement is not omega's to assert either
                        out[o.header] = {"sectionKey": section.sectionKey,
                                         "ops": o.condition_operators,
                                         "vocab": list(o.vocabulary), "meaning": "",
                                         "moved": False, "candle": False,
                                         "above_anchor": False,
                                         "below_anchor": False, "developing": False}
                except Exception:
                    continue
        elif isinstance(section, CustomSection):
            for column in section.columns:
                if column.metric not in c.metrics:
                    continue
                moved = not c.metric(column.metric).is_timeless
                candle = moved and (column.offset or 0) == 0
                above, below = _anchor_side(column, report.anchor, order)
                developing = above and column.bars == "all"
                for o in outputs_for(column, c):
                    out[o.header] = {"sectionKey": section.sectionKey,
                                     "ops": o.condition_operators,
                                     "vocab": list(o.vocabulary), "meaning": "",
                                     "moved": moved, "candle": candle,
                                     "above_anchor": above,
                                     "below_anchor": below, "developing": developing}
    return out


@dataclass(frozen=True)
class _Mode:
    """What the current condition needs checked at each of its OWN clauses.

    `window` is the widest `of` on this node's path from the definition root: a clause
    under a group that holds 3 bars is read on 3 bars even at its own {1,1}.

    The verdict and exit read rules are NOT here: both are stated over the closure
    (what the condition reads directly plus everything reached through conditionRef,
    transitively), so they are checked once per condition against the collected
    closure rather than node by node.
    """
    window: int = 1


def _holdable(spec: dict) -> bool:
    """True when a completed strategy bar changes this header's reading.

    "Above 1 it is legal only where a completed bar changes the reading: over a header
    resolved from this coin's own candle series, at offset 0, at or above the strategy
    timeframe, read Confirmed." (vendor pack 31.2.28 § Conditions)

    That sentence is the 61.0.1 rule. Since v84 each column serves its own
    `conditionHold {timeframe, maxWindow, maxAtLeast, refusal}` (refusals NOT_REWINDABLE,
    DEVELOPING, OFFSET, BAR_STATE, HISTORY) and the builder judges the window, so this
    offline test now only WARNS (plan 2026-10-06: kept "as a warning ... never as an
    error") until a v84+ vocabulary read is on disk (measurement M2).

    `candle` already carries the "at offset 0" clause of that sentence, which is why the
    exit rule reads `moved` instead: its own sentence never mentions offset.

    Four cells of this test are UNMEASURED and may be LOOSER here than on the platform -
    they are enumerated, as unmeasured, in docs/09-conditions.md § "Where the offline
    check may be looser". None of them is encoded as a rule: the extraction that would
    ground them is the not-resolved item of data/contract/_drift_2026-09-18.json.
    """
    return (bool(spec.get("candle"))
            and not spec.get("below_anchor")
            and not spec.get("developing"))


def _check_hold(defn: dict, key: str, path: str, out: list[ConditionFinding]) -> dict | None:
    """The node's `hold` if it is schema-shaped, else None after reporting why.

    v84: "Every clause and every group requires hold: {atLeast, of}, whole numbers of at
    least 1 ... A clause or group without hold is refused." The schema object is
    additionalProperties:false over the two keys. atLeast above `of` is the builder's
    refusal, mirrored as an error."""
    h = defn.get("hold")
    where = f"{path}.hold"
    if h is None:
        out.append(ConditionFinding(
            "error", key, where,
            "every clause and group requires hold {atLeast, of} since contract 84.0.0 "
            "({atLeast: 1, of: 1} is one read)"))
        return None
    if not isinstance(h, dict) or set(h) != set(HOLD_KEYS) \
            or not all(_is_count(h[k]) for k in HOLD_KEYS):
        out.append(ConditionFinding(
            "error", key, where,
            f"must be exactly {{atLeast, of}}, both integers >= 1 (v91 schema), got {h!r}"))
        return None
    if h["atLeast"] > h["of"]:
        out.append(ConditionFinding(
            "error", key, where,
            f"atLeast {h['atLeast']} is above of {h['of']} - refused by the builder (v84)"))
        return None
    return h


def _is_one_read(h: dict | None) -> bool:
    return h is None or (h.get("atLeast"), h.get("of")) == HOLD_ONE


def _walk(defn: dict, key: str, path: str, headers: dict, known_keys: set[str],
          out: list[ConditionFinding], depth: int = 0,
          mode: _Mode | None = None) -> int:
    """Validate one definition node. Returns the number of clauses beneath it.

    conditionRef is an edge, not a descent: the target's own clauses are validated
    when that condition's turn comes, and closure rules are handled separately.
    """
    mode = mode or _Mode()
    kind = defn.get("kind")

    if kind == "conditionRef":
        target = defn.get("conditionKey", "")
        if "hold" in defn:
            out.append(ConditionFinding(
                "error", key, f"{path}.hold",
                "a conditionRef carries no hold: the schema's ref arm is "
                "additionalProperties:false over kind and conditionKey (v84/v91)"))
        if target == key:
            out.append(ConditionFinding("error", key, path, "condition references itself"))
        elif target not in known_keys:
            out.append(ConditionFinding("error", key, path,
                                        f"references unknown condition {target!r}"))
        return 0

    if kind == "group":
        h = _check_hold(defn, key, path, out)
        op, members = defn.get("op"), defn.get("members") or []
        if op not in GROUP_OPS:
            out.append(ConditionFinding("error", key, path, f"group op {op!r} not in {GROUP_OPS}"))
        if not members:
            out.append(ConditionFinding("error", key, path, "group has no members"))
        if op == "NOT" and len(members) != 1:
            out.append(ConditionFinding("error", key, path,
                                        f"NOT takes exactly one member, got {len(members)}"))
        if op == "N_OF":
            n = defn.get("n")
            if n is None:
                out.append(ConditionFinding("error", key, path, "N_OF requires n"))
            elif n > len(members):
                out.append(ConditionFinding("error", key, path,
                                            f"N_OF n={n} exceeds {len(members)} members - can never be true"))
            elif n == len(members):
                out.append(ConditionFinding("warning", key, path,
                                            f"N_OF n={n} equals member count; ALL says this more plainly"))
        if not _is_one_read(h):
            # v84: "a group hold over members that hold their own bars is a typed
            # remediation error" - a group above {1,1} needs its members at {1,1}.
            for i, member in enumerate(members):
                if isinstance(member, dict) and member.get("kind") in ("clause", "group") \
                        and not _is_one_read(member.get("hold")):
                    out.append(ConditionFinding(
                        "error", key, f"{path}.members[{i}].hold",
                        f"a group holding {h} over a member that holds its own bars "
                        f"({member.get('hold')}) is refused by the builder (v84); hold the "
                        f"members at {{1,1}} or drop the group hold"))
        inner = _Mode(window=max(mode.window, h["of"] if h else 1))
        total = 0
        for i, member in enumerate(members):
            total += _walk(member, key, f"{path}.members[{i}]", headers, known_keys,
                           out, depth + 1, inner)
        if not _is_one_read(h) and total == 0:
            # The 61.0.1 CONDITION_HOLD_ILLEGAL sentence: a referenced condition "is
            # resolved once and contributes the same answer to every bar". Pre-v84
            # evidence; a v84+ group hold over refs alone is unmeasured, so a warning.
            out.append(ConditionFinding(
                "warning", key, f"{path}.hold",
                f"a group hold of {h} over conditionRefs alone: at 61.0.1 a referenced "
                f"condition contributed the same answer to every bar "
                f"(CONDITION_HOLD_ILLEGAL); unmeasured at v84+, the builder judges it"))
        return total

    if kind != "clause":
        out.append(ConditionFinding("error", key, path, f"unknown definition kind {kind!r}"))
        return 0

    # --- a clause: hold, header must exist, operator must be offered, literal must fit
    h = _check_hold(defn, key, path, out)
    window = max(mode.window, h["of"] if h else 1)
    header = (defn.get("column") or {}).get("header", "")
    spec = headers.get(header)
    if spec is None:
        out.append(ConditionFinding(
            "error", key, path,
            f"header {header!r} is not produced by any column in this report "
            f"(nor ambient). Add a column that emits it, or fix the name."))
        return 1

    if window > 1 and not _holdable(spec):
        out.append(ConditionFinding(
            "warning", key, path,
            f"{header!r} is read over {window} bars: at 61.0.1 a hold above 1 was legal "
            f"only over a header resolved from this coin's own candle series at offset 0, "
            f"at or above the strategy timeframe, read Confirmed "
            f"(CONDITION_HOLD_OPERAND_ILLEGAL, vendor pack 31.2.28). Since v84 the column's "
            f"conditionHold decides and the builder judges it; no v84+ read is on disk"))

    declared = (defn.get("column") or {}).get("sectionKey")
    if declared is not None and spec["sectionKey"] is not None and declared != spec["sectionKey"]:
        out.append(ConditionFinding(
            "error", key, path,
            f"header {header!r} lives in {spec['sectionKey']!r}, not {declared!r}"))

    op = defn.get("op")
    allowed = spec["ops"]
    if not allowed:
        out.append(ConditionFinding("error", key, path,
                                    f"{header!r} offers no condition operators at all"))
    elif op not in allowed:
        out.append(ConditionFinding(
            "error", key, path,
            f"{header!r} does not accept {op!r}. Allowed: {allowed}"))

    vocab = spec["vocab"]
    measured = observed_vocabulary().get(header, {})
    observed = measured.get("observed") or []
    # A header whose declared vocabulary is DISJOINT from what it emits cannot be
    # used in a condition at all. The platform rejects the labels it emits
    # (CONDITION_LITERAL_UNSUPPORTED) and evaluates the labels it accepts as FALSE
    # forever. There is no third option, so omega refuses the whole clause rather
    # than emitting one that is dead on arrival. Measured live 2026-08-24.
    disjoint = bool(observed) and measured.get("observedInDeclared") == 0

    def _trap(_labels: list[str]) -> None:
        if not disjoint:
            return
        out.append(ConditionFinding(
            "error", key, path,
            f"{header!r} cannot carry a condition. It declares {list(vocab)} and was "
            f"observed to emit only {observed} ({measured['samples']} samples). The "
            f"platform refuses the labels it emits (CONDITION_LITERAL_UNSUPPORTED) and "
            f"reads the labels it accepts as FALSE forever. Threshold the numeric "
            f"column instead: {measured['numericReplacement']}. Cookbook trap 13."))

    if op == "is":
        label = defn.get("label")
        if vocab and label not in vocab:
            out.append(ConditionFinding("error", key, path,
                                        f"{label!r} is not in {header!r} vocabulary {vocab}"))
        else:
            _trap([label])
    elif op == "in":
        labels = defn.get("labels") or []
        bad = [x for x in labels if vocab and x not in vocab]
        if bad:
            out.append(ConditionFinding("error", key, path,
                                        f"{bad} not in {header!r} vocabulary {vocab}"))
        else:
            _trap(labels)
    elif op == "between":
        low, high = defn.get("low"), defn.get("high")
        if low is not None and high is not None and low >= high:
            out.append(ConditionFinding("error", key, path,
                                        f"between low={low} is not below high={high}"))
    return 1


def validate_conditions(report: Report, conditions: list[dict]) -> list[ConditionFinding]:
    """Type-check conditions against the headers the report actually produces."""
    c = load()
    headers = report_headers(report)
    keys = [x.get("conditionKey", "") for x in conditions]
    known = set(keys)
    out: list[ConditionFinding] = []

    limit = c.budgets["strategyConditions"]
    if len(conditions) > limit:
        out.append(ConditionFinding("error", "<report>", "",
                                    f"{len(conditions)} conditions exceeds the budget of {limit}"))
    for k in {x for x in keys if keys.count(x) > 1}:
        out.append(ConditionFinding("error", k, "", "duplicate conditionKey"))

    for cycle in _find_reference_cycles(conditions):
        out.append(ConditionFinding(
            "error", cycle[0], ".definition",
            f"conditionRef cycle: {' -> '.join(cycle)} -> {cycle[0]}"))

    defn_by_key = {x.get("conditionKey", ""): (x.get("definition") or {})
                   for x in conditions}
    # v88: "an entry condition cannot reference an exit rule" - the set it may not name
    exit_keys = {x.get("conditionKey", "") for x in conditions
                 if x.get("exitSide") in EXIT_SIDES}

    clause_cap = c.budgets["conditionClauses"]
    for cond in conditions:
        key = cond.get("conditionKey", "")
        if not CONDITION_KEY.match(key):
            out.append(ConditionFinding("error", key, ".conditionKey",
                                        "must match ^[A-Z][A-Z0-9_]{1,39}$"))
        name = cond.get("name") or ""
        if not 1 <= len(name) <= 80:
            out.append(ConditionFinding("error", key, ".name", "must be 1-80 characters"))
        if cond.get("verdict") not in VERDICTS:
            out.append(ConditionFinding("error", key, ".verdict",
                                        f"must be one of {VERDICTS}"))
        # The v91 CONDITIONS axis is additionalProperties:false over the six keys. The
        # three retired keys get the reason they went; anything else is just undeclared.
        for k in cond:
            if k in RETIRED_CONDITION_FIELDS:
                out.append(ConditionFinding("error", key, f".{k}", RETIRED_CONDITION_FIELDS[k]))
            elif k not in CONDITION_FIELDS:
                out.append(ConditionFinding(
                    "error", key, f".{k}",
                    f"not declared by the v91 CONDITIONS axis (additionalProperties:false "
                    f"over {list(CONDITION_FIELDS)})"))
        # v88: exitSide is "nullable, never optional; a condition without it is refused"
        side = cond.get("exitSide")
        if "exitSide" not in cond:
            out.append(ConditionFinding(
                "error", key, ".exitSide",
                "required since contract 88.0.0: null for an entry condition, LONG / SHORT / "
                "BOTH for an exit rule (nullable, never optional)"))
        elif side is not None and side not in EXIT_SIDES:
            out.append(ConditionFinding("error", key, ".exitSide",
                                        f"must be one of {EXIT_SIDES} or null, got {side!r}"))
        is_exit = side in EXIT_SIDES
        # The three typed builder refusals v88 added (README "Contract history - v88").
        if is_exit and cond.get("verdict") is not None:
            out.append(ConditionFinding(
                "error", key, ".verdict",
                f"an exit rule carries verdict: null, got {cond.get('verdict')!r} "
                f"(CONDITION_EXIT_RULE_CARRIES_VERDICT)"))
        if is_exit and cond.get("required") is not False:
            out.append(ConditionFinding(
                "error", key, ".required",
                f"an exit rule carries required: false, got {cond.get('required')!r} "
                f"(CONDITION_EXIT_RULE_REQUIRED)"))
        if not is_exit:
            named: set[str] = set()
            _reference_edges(cond.get("definition") or {}, named)
            for target in sorted(named & exit_keys):
                out.append(ConditionFinding(
                    "error", key, ".definition",
                    f"an entry condition cannot reference the exit rule {target!r} "
                    f"(CONDITION_ENTRY_REFERENCES_EXIT_RULE); an exit rule may reference "
                    f"anything, not the other way round"))
        clauses = _walk(cond.get("definition") or {}, key, ".definition", headers,
                        known, out, 0, _Mode())
        if clauses > clause_cap:
            out.append(ConditionFinding("error", key, ".definition",
                                        f"{clauses} clauses exceeds the budget of {clause_cap}"))

        # The two CLOSURE rules. "The closure is what the condition reads directly plus
        # everything reached through conditionRef, transitively: a referenced condition
        # contributes what IT reads, so moving the clause into a building block does not
        # launder it." (vendor pack 31.2.28 § Conditions). Since v88 the exit role is the
        # exit rule's: a CLOSE_ON_<key> rule reads its source's whole closure.
        carrier = cond.get("verdict") in CARRIER_VERDICTS
        exits = is_exit
        if carrier or exits:
            for owner, cpath, header in _closure_clauses(key, defn_by_key):
                spec = headers.get(header)
                if spec is None:
                    continue            # unknown header: already reported at its clause
                where = cpath if owner == key else f"{cpath} (in {owner})"
                if carrier and spec.get("developing"):
                    out.append(ConditionFinding(
                        "error", key, where,
                        f"{header!r} reads a Developing higher-timeframe bar; a verdict "
                        f"carrier may not read one, at any depth "
                        f"(CONDITION_VERDICT_READ_ILLEGAL)"))
                # `moved`, not `candle`: the exit sentence rules out "a developing read"
                # and "a frame-inert operand" and never mentions offset, so an offset
                # column - which a completed bar still moves, one bar later - is legal
                # here while the hold rule ("at offset 0") refuses it.
                if exits and (not spec.get("moved") or spec.get("developing")):
                    out.append(ConditionFinding(
                        "error", key, where,
                        f"{header!r} is not moved by a completed bar (or is a developing "
                        f"read); an exit rule needs a closure every operand of which a "
                        f"completed bar moves (CONDITION_EXIT_READ_ILLEGAL)"))
    return out


def _reference_edges(defn: dict, out: set[str]) -> None:
    if not isinstance(defn, dict):
        return
    if defn.get("kind") == "conditionRef":
        out.add(defn.get("conditionKey", ""))
    for member in defn.get("members") or []:
        _reference_edges(member, out)


def _own_clauses(defn: dict, path: str = ".definition") -> list[tuple[str, str]]:
    """(path, header) for every clause this definition holds itself.

    conditionRef is not followed: what a reference contributes belongs to the
    condition it names, which _closure_clauses collects separately.
    """
    if not isinstance(defn, dict):
        return []
    if defn.get("kind") == "clause":
        return [(path, ((defn.get("column") or {}).get("header", "")))]
    out: list[tuple[str, str]] = []
    for i, member in enumerate(defn.get("members") or []):
        out.extend(_own_clauses(member, f"{path}.members[{i}]"))
    return out


def _closure_clauses(key: str, defn_by_key: dict[str, dict]) -> list[tuple[str, str, str]]:
    """(owner key, clause path, header) for the whole closure of one condition.

    The closure is the condition's own clauses plus everything reached through
    conditionRef, transitively. Breadth-first from `key`, each condition visited once -
    which also makes this terminate on a reference cycle (reported separately by
    _find_reference_cycles).
    """
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    queue = [key]
    while queue:
        cur = queue.pop(0)
        if cur in seen or cur not in defn_by_key:
            continue
        seen.add(cur)
        defn = defn_by_key[cur]
        out.extend((cur, path, header) for path, header in _own_clauses(defn))
        edges: set[str] = set()
        _reference_edges(defn, edges)
        queue.extend(sorted(edges))
    return out


def _find_reference_cycles(conditions: list[dict]) -> list[list[str]]:
    """Detect conditionRef cycles. A cycle can never resolve, so it is an error."""
    graph: dict[str, set[str]] = {}
    for cond in conditions:
        edges: set[str] = set()
        _reference_edges(cond.get("definition") or {}, edges)
        graph[cond.get("conditionKey", "")] = edges

    cycles: list[list[str]] = []
    seen_cycles: set[frozenset[str]] = set()
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {k: WHITE for k in graph}

    def visit(node: str, stack: list[str]) -> None:
        colour[node] = GREY
        stack.append(node)
        for nxt in graph.get(node, ()):
            if nxt not in colour:
                continue                      # dangling ref, reported elsewhere
            if colour[nxt] == GREY:
                cycle = stack[stack.index(nxt):]
                if len(cycle) > 1 and frozenset(cycle) not in seen_cycles:
                    seen_cycles.add(frozenset(cycle))
                    cycles.append(cycle)
            elif colour[nxt] == WHITE:
                visit(nxt, stack)
        stack.pop()
        colour[node] = BLACK

    for node in list(graph):
        if colour[node] == WHITE:
            visit(node, [])
    return cycles


def validate_market_read(text: str, conditions: list[dict], report: Report) -> list[ConditionFinding]:
    """Check every {TOKEN} in marketReadText resolves to a condition key or a header."""
    out: list[ConditionFinding] = []
    if len(text) > 2000:
        out.append(ConditionFinding("error", "<marketReadText>", "",
                                    f"{len(text)} characters exceeds the 2000 cap"))
    keys = {c.get("conditionKey") for c in conditions}
    headers = report_headers(report)
    for token in re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", text):
        if token not in keys and token not in headers:
            out.append(ConditionFinding(
                "error", "<marketReadText>", f".{{{token}}}",
                f"{token!r} is neither a conditionKey nor a header in this report"))
    return out


def market_read_text(intro: str, conditions: list[dict], *, closing: str = "") -> str:
    """Compose marketReadText that references each condition by key.

    The agent should read the named verdict, not re-derive the filters - which is how
    EL_ALAMEIN is written: "{CONFLUENCE_UP} and {CONFLUENCE_DOWN} report whether the
    four-filter checklist is satisfied on each side. Read that answer rather than
    re-counting the filters."
    """
    lines = [intro.strip(), ""]
    for cond in conditions:
        verdict = cond.get("verdict")
        side = f" ({verdict})" if verdict in ("UP", "DOWN") else ""
        lines.append(f"- {{{cond['conditionKey']}}}{side} - {cond['name']}.")
    lines.append("")
    lines.append(closing.strip() or
                 "Read these verdicts rather than re-deriving them from the columns.")
    return "\n".join(x for x in lines if x is not None).strip()
