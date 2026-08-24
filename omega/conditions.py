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
              verdict: str | None = None, required: bool = False) -> dict:
    return {"conditionKey": key, "name": name, "definition": definition,
            "verdict": verdict, "required": required}


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


def report_headers(report: Report) -> dict[str, dict]:
    """Every header the report exposes to conditions, ambient headers included."""
    c = load()
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
                        out[o.header] = {"sectionKey": section.sectionKey,
                                         "ops": o.condition_operators,
                                         "vocab": list(o.vocabulary), "meaning": ""}
                except Exception:
                    continue
        elif isinstance(section, CustomSection):
            for column in section.columns:
                if column.metric not in c.metrics:
                    continue
                for o in outputs_for(column, c):
                    out[o.header] = {"sectionKey": section.sectionKey,
                                     "ops": o.condition_operators,
                                     "vocab": list(o.vocabulary), "meaning": ""}
    return out


def _walk(defn: dict, key: str, path: str, headers: dict, known_keys: set[str],
          out: list[ConditionFinding], depth: int = 0) -> int:
    """Validate one definition node. Returns the number of clauses beneath it."""
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
            total += _walk(member, key, f"{path}.members[{i}]", headers, known_keys, out, depth + 1)
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
        clauses = _walk(cond.get("definition") or {}, key, ".definition", headers, known, out)
        if clauses > clause_cap:
            out.append(ConditionFinding("error", key, ".definition",
                                        f"{clauses} clauses exceeds the budget of {clause_cap}"))
    return out


def _reference_edges(defn: dict, out: set[str]) -> None:
    if not isinstance(defn, dict):
        return
    if defn.get("kind") == "conditionRef":
        out.add(defn.get("conditionKey", ""))
    for member in defn.get("members") or []:
        _reference_edges(member, out)


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
