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
# The per-condition clock was RETIRED in contract 61.0.0 (2026-09-17) and the compile
# schema refuses the key outright: conditions[] is additionalProperties:false over
# [conditionKey, name, definition, verdict, required, exit, closes]
# (data/contract/compile_strategy_plan/schema_20260918T083359Z.json, captured 2026-09-18).
# What survives is `closes`: the HOLD, how many consecutive COMPLETED strategy bars must
# read TRUE. The schema bounds it to an integer 1..5, multipleOf 1.
HOLD_MIN, HOLD_MAX = 1, 5


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
def col(header: str, section_key: str | None = None) -> dict:
    return {"sectionKey": section_key, "header": header}


def num(header: str, op: str, value: float, *, section_key: str | None = None) -> dict:
    if op not in NUMERIC_OPS:
        raise ValueError(f"{op!r} is not one of {NUMERIC_OPS}")
    return {"kind": "clause", "column": col(header, section_key), "op": op, "value": value}


def between(header: str, low: float, high: float, *, section_key: str | None = None) -> dict:
    return {"kind": "clause", "column": col(header, section_key), "op": "between",
            "low": low, "high": high}


def is_(header: str, label: str, *, section_key: str | None = None) -> dict:
    return {"kind": "clause", "column": col(header, section_key), "op": "is", "label": label}


def in_(header: str, labels: list[str], *, section_key: str | None = None) -> dict:
    return {"kind": "clause", "column": col(header, section_key), "op": "in", "labels": labels}


def ref(condition_key: str) -> dict:
    return {"kind": "conditionRef", "conditionKey": condition_key}


def group(op: str, members: list[dict], n: int | None = None) -> dict:
    if op not in GROUP_OPS:
        raise ValueError(f"{op!r} is not one of {GROUP_OPS}")
    if op == "N_OF" and n is None:
        raise ValueError("N_OF requires n")
    out: dict[str, Any] = {"kind": "group", "op": op, "members": members}
    if n is not None:
        out["n"] = n
    return out


def all_of(*members: dict) -> dict:
    return group("ALL", list(members))


def any_of(*members: dict) -> dict:
    return group("ANY", list(members))


def not_(member: dict) -> dict:
    return group("NOT", [member])


def n_of(n: int, *members: dict) -> dict:
    return group("N_OF", list(members), n=n)


def condition(key: str, name: str, definition: dict, *,
              verdict: str | None = None, required: bool = False,
              exit: bool = False, closes: int = 1) -> dict:
    """One wire-shaped condition, contract 61.0.1: exactly the seven keys the platform reads back
    (data/contract/get_strategy/43d11467-637c-42b1-b88b-8a71ed8c32c3_20260918T083500Z.json), in that
    order. `closes` is the hold: how many consecutive COMPLETED strategy bars must read TRUE (1..5).
    The per-condition clock was retired in 61.0.0 and a `clock` key is refused (vendor pack 31.2.28,
    strategy-examples § Conditions) - it is not a keyword here, so passing it raises TypeError.

    exit is REQUIRED since the schema re-read of 2026-09-04 (drift instance #5, caught offline):
    both records then in existence read back exit=false on every condition with no revision bump
    (drift5_exit_rediscovery_2026-09-04.json). 61.0.1 published what exit=true does - a settled TRUE
    reading closes positions its verdict opposes - and the read rule that goes with it, mirrored in
    validate_conditions; authoring still defaults to False."""
    if not isinstance(exit, bool):
        raise ValueError(f"exit must be a bool (required by the compile schema since "
                         f"2026-09-04), got {exit!r}")
    if not isinstance(closes, int) or isinstance(closes, bool) \
            or not HOLD_MIN <= closes <= HOLD_MAX:
        raise ValueError(f"closes must be an int {HOLD_MIN}..{HOLD_MAX}, got {closes!r}")
    return {"conditionKey": key, "name": name, "definition": definition,
            "verdict": verdict, "required": required, "exit": exit, "closes": closes}


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

    The verdict and exit read rules are NOT here: both are stated over the closure
    (what the condition reads directly plus everything reached through conditionRef,
    transitively), so they are checked once per condition against the collected
    closure rather than node by node.
    """
    closes: int = HOLD_MIN


def _holdable(spec: dict) -> bool:
    """True when a completed strategy bar changes this header's reading.

    "Above 1 it is legal only where a completed bar changes the reading: over a header
    resolved from this coin's own candle series, at offset 0, at or above the strategy
    timeframe, read Confirmed." (vendor pack 31.2.28 § Conditions)

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
        if target == key:
            out.append(ConditionFinding("error", key, path, "condition references itself"))
        elif target not in known_keys:
            out.append(ConditionFinding("error", key, path,
                                        f"references unknown condition {target!r}"))
        return 0

    if kind == "group":
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
        total = 0
        for i, member in enumerate(members):
            total += _walk(member, key, f"{path}.members[{i}]", headers, known_keys,
                           out, depth + 1, mode)
        return total

    if kind != "clause":
        out.append(ConditionFinding("error", key, path, f"unknown definition kind {kind!r}"))
        return 0

    # --- a clause: header must exist, operator must be offered, literal must fit
    header = (defn.get("column") or {}).get("header", "")
    spec = headers.get(header)
    if spec is None:
        out.append(ConditionFinding(
            "error", key, path,
            f"header {header!r} is not produced by any column in this report "
            f"(nor ambient). Add a column that emits it, or fix the name."))
        return 1

    if mode.closes > HOLD_MIN and not _holdable(spec):
        out.append(ConditionFinding(
            "error", key, path,
            f"{header!r} cannot hold {mode.closes} closes: a hold above 1 is legal only "
            f"over a header resolved from this coin's own candle series at offset 0, at "
            f"or above the strategy timeframe, read Confirmed "
            f"(CONDITION_HOLD_OPERAND_ILLEGAL, vendor pack 31.2.28, contract 61.0.1)"))

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
        # exit is REQUIRED by the compile schema (re-read 2026-09-04, drift #5);
        # the platform's migration default is false on every existing condition
        if not isinstance(cond.get("exit"), bool):
            out.append(ConditionFinding(
                "error", key, ".exit",
                f"must be a bool (required by the compile schema since 2026-09-04; "
                f"platform migration default false), got {cond.get('exit')!r}"))
        # The per-condition clock was retired in 61.0.0 and the compile schema is
        # additionalProperties:false over the seven keys, so a surviving `clock` is
        # not a stale default - it is a refused payload.
        if "clock" in cond:
            out.append(ConditionFinding(
                "error", key, ".clock",
                "clock was retired in contract 61.0.0 and is refused by the compile "
                "schema; drop the key (the hold is `closes`)"))
        # closes is REQUIRED by the compile schema: integer, minimum 1, maximum 5,
        # multipleOf 1 (schema_20260918T083359Z.json)
        closes = cond.get("closes")
        if not isinstance(closes, int) or isinstance(closes, bool) \
                or not HOLD_MIN <= closes <= HOLD_MAX:
            out.append(ConditionFinding(
                "error", key, ".closes",
                f"must be an int {HOLD_MIN}..{HOLD_MAX} (the compile schema declares "
                f"integer, minimum 1, maximum 5, multipleOf 1; "
                f"schema_20260918T083359Z.json), got {closes!r}"))
            closes = HOLD_MIN   # keep walking; clause-level hold findings suppressed
        clauses = _walk(cond.get("definition") or {}, key, ".definition", headers,
                        known, out, 0, _Mode(closes=closes))
        if clauses > clause_cap:
            out.append(ConditionFinding("error", key, ".definition",
                                        f"{clauses} clauses exceeds the budget of {clause_cap}"))
        # A hold needs a clause of the condition's OWN: conditionRef contributes an
        # answer resolved once, not one that moves with the bar.
        if closes > HOLD_MIN and clauses == 0:
            out.append(ConditionFinding(
                "error", key, ".definition",
                f"a hold of {closes} closes needs a clause of the condition's own; a "
                f"referenced condition is resolved once and contributes the same answer "
                f"to every bar (CONDITION_HOLD_ILLEGAL)"))

        # The two CLOSURE rules. "The closure is what the condition reads directly plus
        # everything reached through conditionRef, transitively: a referenced condition
        # contributes what IT reads, so moving the clause into a building block does not
        # launder it." (vendor pack 31.2.28 § Conditions)
        carrier = cond.get("verdict") in CARRIER_VERDICTS
        exits = cond.get("exit") is True
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
                        f"read); exit: true needs a closure every operand of which a "
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
