"""The six prior-bar clause operators of contract 98 (crossesAbove, crossesBelow, increased, decreased, enters,
exits): omega's builders, and validate_conditions against the 108 CONDITIONS axis.

Two sources, kept apart:
- the SCHEMA (data/contract/stage_strategy_draft/schema_20261010T215326Z.json, inventoried in
  data/derived/condition_vocabulary_108.json): what a clause may carry. validate_conditions ERRS exactly where the
  schema refuses, and every positive and negative body here is also walked by omega.preflight against the saved
  schema, so the two must agree;
- DESCRIPTIONS (README "Contract history - v98", vendor strategy-examples skill exported at 105.0.0): which header
  kind admits which operator, the edge-hold rule, the one-bar-history refusal. Those are WARNINGS that quote their
  source, never errors - the platform serves the admitted operators per header (`conditionOperators`), which
  omega cannot read offline.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega import preflight as P
from omega.conditions import (
    EDGE_OPS, MODELLED_CLAUSE_OPS, PRIOR_BAR_OPS, all_of, any_of, condition, crosses_above, crosses_below,
    decreased, enters, exits, held, increased, num, validate_conditions,
)
from omega.condition_vocabulary import vocabulary
from omega.types import Column, CustomSection, Report

ROOT = Path(__file__).resolve().parents[1]
DOC = json.loads((ROOT / "data/contract/stage_strategy_draft/schema_20261010T215326Z.json")
                 .read_text(encoding="utf-8"))
AXES, SCHEMA_ROOT = P.resolve_axes(DOC)
SECTION_KEY = "custom:18c11ae8-bb26-5025-a01c-957043d42445"


def _report(*specs) -> Report:
    return Report(anchor="1h", sections=[CustomSection(
        title="T", sectionKey=SECTION_KEY, benchmarkTicker=None,
        columns=[Column.model_validate(s) for s in specs])])


# RSI14_now (numeric, candle), RSI14_trend (direction), RSI14_zone (classification), RSI14_rank_hi (rank),
# chg24h-style timeless numeric, EMA_CROSS (event), CAPTAIN_CONF (boolean)
REPORT = _report(
    {"metric": "RSI14", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4},
    {"metric": "RSI14", "transformId": "classifyZone", "timeframe": {"rel": "anchor"}},
    {"metric": "RSI14", "transformId": "rank", "timeframe": {"rel": "anchor"}},
    {"metric": "CHG_24H", "transformId": "value", "timeframe": {"rel": "anchor"}},
    {"metric": "EMA_CROSS", "transformId": "value", "timeframe": {"rel": "anchor"}},
)


def _header(kind: str) -> str:
    from omega.conditions import report_headers
    found = [h for h, s in report_headers(REPORT).items() if s.get("kind") == kind]
    assert found, kind
    return found[0]


def _walk(definition: dict) -> list:
    """The preflight walk of one condition carrying `definition`, against the saved 108 CONDITIONS axis."""
    body = {"CONDITIONS": {"conditions": [condition("KEY", "n", definition, verdict="UP")]}}
    return [f for f in P.diff_axes(body, AXES, SCHEMA_ROOT) if f.verdict == "FAIL" or f.cls == "UNSUPPORTED"]


def _findings(definition: dict, report: Report = REPORT):
    found = validate_conditions(report, [condition("KEY", "n", definition, verdict="UP")])
    return ([f for f in found if f.severity == "error"], [f for f in found if f.severity == "warning"])


# --- the model now covers the schema --------------------------------------------------------------
def test_omega_models_every_operator_the_schema_declares():
    assert sorted(MODELLED_CLAUSE_OPS) == sorted(vocabulary()["clauseOperators"])
    assert set(PRIOR_BAR_OPS) == {"crossesAbove", "crossesBelow", "increased", "decreased", "enters", "exits"}
    assert set(EDGE_OPS) == {"crossesAbove", "crossesBelow", "enters", "exits"}


# --- builders ---------------------------------------------------------------------------------------
def test_builders_emit_the_arm_shape_in_the_schemas_required_order():
    col = {"sectionKey": None, "header": "RSI14_now"}
    one = {"atLeast": 1, "of": 1}
    assert crosses_above("RSI14_now", 50) == {"kind": "clause", "column": col, "op": "crossesAbove",
                                               "value": 50, "hold": one}
    assert crosses_below("RSI14_now", 50) == {"kind": "clause", "column": col, "op": "crossesBelow",
                                               "value": 50, "hold": one}
    assert increased("RSI14_now") == {"kind": "clause", "column": col, "op": "increased", "hold": one}
    assert decreased("RSI14_now") == {"kind": "clause", "column": col, "op": "decreased", "hold": one}
    zone = {"sectionKey": SECTION_KEY, "header": "RSI14_zone"}
    assert enters("RSI14_zone", "overbought", section_key=SECTION_KEY) == {
        "kind": "clause", "column": zone, "op": "enters", "label": "overbought", "hold": one}
    assert exits("RSI14_zone", "overbought", section_key=SECTION_KEY) == {
        "kind": "clause", "column": zone, "op": "exits", "label": "overbought", "hold": one}
    for clause in (crosses_above("RSI14_now", 50), increased("RSI14_now"), enters("RSI14_zone", "oversold")):
        arm = vocabulary()["grammar"]["clauseArms"][vocabulary()["grammar"]["operators"][clause["op"]]["arm"]]
        assert list(clause) == arm["required"]


def test_an_edge_is_held_within_n_closes_only():
    # v98: "crossesAbove, crossesBelow, enters and exits are edges: a hold with atLeast above 1 is refused
    # (CONDITION_HOLD_ILLEGAL) - hold them 'within n closes'."
    assert crosses_above("RSI14_now", 50, hold=(1, 3))["hold"] == {"atLeast": 1, "of": 3}
    assert enters("RSI14_zone", "oversold", hold=(1, 2))["hold"] == {"atLeast": 1, "of": 2}
    for build in (lambda h: crosses_above("RSI14_now", 50, hold=h), lambda h: crosses_below("RSI14_now", 50, hold=h),
                  lambda h: enters("RSI14_zone", "oversold", hold=h), lambda h: exits("RSI14_zone", "oversold", hold=h)):
        with pytest.raises(ValueError, match="CONDITION_HOLD_ILLEGAL"):
            build(held(3))
        with pytest.raises(ValueError, match="CONDITION_HOLD_ILLEGAL"):
            build((2, 3))


def test_a_change_is_no_edge_and_may_be_held_in_a_row():
    # vendor strategy-examples: "increased and decreased are no edge: '3 closes in a row' of increased is three
    # rising closes."
    assert increased("RSI14_now", hold=held(3))["hold"] == {"atLeast": 3, "of": 3}
    assert decreased("RSI14_now", hold=(2, 4))["hold"] == {"atLeast": 2, "of": 4}


def test_an_all_group_over_an_edge_is_held_within_only():
    # vendor strategy-examples: "A group whose members must all read TRUE together (ALL) over an edge admits
    # 'within' only too."
    edge = crosses_above("RSI14_now", 50)
    with pytest.raises(ValueError, match="within"):
        all_of(edge, num("RSI14_now", "gt", 40), hold=held(2))
    with pytest.raises(ValueError, match="within"):
        condition("K", "n", all_of(edge, num("RSI14_now", "gt", 40)), hold=held(2))
    with pytest.raises(ValueError, match="CONDITION_HOLD_ILLEGAL"):
        condition("K", "n", edge, hold=held(2))
    assert all_of(edge, num("RSI14_now", "gt", 40), hold=(1, 3))["hold"] == {"atLeast": 1, "of": 3}
    assert any_of(edge, increased("RSI14_now"), hold=held(2))["op"] == "ANY"     # only ALL is stated


@pytest.mark.parametrize("build", [
    lambda: crosses_above("RSI14_now", True), lambda: crosses_above("RSI14_now", "50"),
    lambda: crosses_below("RSI14_now", None), lambda: enters("RSI14_zone", ""),
    lambda: exits("RSI14_zone", "x" * 81), lambda: enters("RSI14_zone", ["oversold"]),
])
def test_builders_refuse_an_operand_the_schema_refuses(build):
    with pytest.raises(ValueError):
        build()


# --- positive bodies: the schema walk and the validator both pass ----------------------------------
POSITIVE = {
    "crossesAbove": lambda: crosses_above("RSI14_now", 50),
    "crossesBelow within 3": lambda: crosses_below("RSI14_now", 50.5, hold=(1, 3)),
    "increased 3 in a row": lambda: increased("RSI14_now", hold=held(3)),
    "decreased": lambda: decreased("RSI14_now"),
    "enters": lambda: enters("RSI14_zone", "overbought"),
    "exits within 2": lambda: exits("RSI14_zone", "oversold", hold=(1, 2)),
    "ANY over edges": lambda: any_of(crosses_above("RSI14_now", 50), enters("RSI14_trend", "rising")),
}


@pytest.mark.parametrize("name", sorted(POSITIVE))
def test_a_positive_body_walks_the_schema_and_validates_clean(name):
    definition = POSITIVE[name]()
    assert _walk(definition) == []
    errors, warnings = _findings(definition)
    assert errors == [] and warnings == [], [str(f) for f in errors + warnings]


# --- negative bodies: the schema refuses, so the validator errs ----------------------------------
def _clause(op: str, **operands) -> dict:
    return {"kind": "clause", "column": {"sectionKey": None, "header": "RSI14_now"}, "op": op, **operands,
            "hold": {"atLeast": 1, "of": 1}}


NEGATIVE = {
    "increased with a value": (_clause("increased", value=50), "value"),        # v98: "A value beside them is refused"
    "decreased with a label": (_clause("decreased", label="x"), "label"),
    "crossesAbove without a value": (_clause("crossesAbove"), "value"),
    "crossesAbove with a string": (_clause("crossesAbove", value="50"), "value"),
    "crossesBelow with a boolean": (_clause("crossesBelow", value=True), "value"),
    "crossesAbove with low/high": (_clause("crossesAbove", low=1, high=2), "low"),
    "enters with a label set": (_clause("enters", labels=["overbought"]), "label"),
    "enters with an empty label": (_clause("enters", label=""), "label"),
    "exits with a long label": (_clause("exits", label="x" * 81), "label"),
    "exits with a value": (_clause("exits", label="oversold", value=1), "value"),
    "an operator the schema lacks": (_clause("crosses", value=50), "op"),
    "in with an empty set": (_clause("in", labels=[]), "labels"),
}


@pytest.mark.parametrize("name", sorted(NEGATIVE))
def test_a_negative_body_fails_the_schema_walk_and_the_validator(name):
    definition, field = NEGATIVE[name]
    assert _walk(definition), f"the saved schema accepts {name!r}"
    errors, _ = _findings(definition)
    assert errors, f"validate_conditions accepts {name!r}, which the schema refuses"
    assert any(f".{field}" in f.path or field in f.message for f in errors), [str(f) for f in errors]


# --- description rules: warnings with their quoted source, never errors ----------------------------
def test_a_header_kind_that_does_not_take_the_operator_is_refused():
    """v98: "Numeric headers take the crossings and changes; classification, direction and boolean headers take the
    transitions; event and rank headers take none of them." A warning quoting that sentence until (measured 2026-10-13 at 108.4.0, data/contract/columns/operators_108_4_2026-10-13/), when the
    served conditionOperators matched it for every kind and each mismatch probed was refused
    CONDITION_OPERATOR_UNSUPPORTED (crossesAbove on RSI14_zone, enters on EMA5_13, increased on RSI14_rank_hi)."""
    cases = [crosses_above(_header("classification"), 1), increased(_header("direction")),
             enters("RSI14_now", "x"), crosses_above(_header("rank"), 3), enters(_header("event"), "Bullish")]
    for definition in cases:
        assert _walk(definition) == []                       # the schema accepts every one of them
        errors, _ = _findings(definition)
        assert any("CONDITION_OPERATOR_UNSUPPORTED" in e.message for e in errors), [str(e) for e in errors]


def test_a_timeless_custom_header_is_refused_and_an_ambient_one_stays_a_warning():
    """vendor strategy-examples: "a header whose conditionHold.maxWindow is 1 is served none of the six". (measured 2026-10-13 at 108.4.0, data/contract/columns/operators_108_4_2026-10-13/):
    chg24h (a timeless custom column) is served maxWindow 1 / NOT_REWINDABLE and `increased` on it was refused. An
    ambient header's kind and history omega cannot see, so mktBreadth_all stays a warning (unmeasured)."""
    assert _walk(increased("chg24h")) == []
    errors, _ = _findings(increased("chg24h"))
    assert any("NOT_REWINDABLE" in e.message and "CONDITION_OPERATOR_UNSUPPORTED" in e.message for e in errors)
    errors, warnings = _findings(crosses_above("mktBreadth_all", 0))
    assert errors == [] and any("maxWindow" in w.message for w in warnings), [str(w) for w in warnings]


def test_an_edge_held_in_a_row_passes_the_schema_and_is_refused():
    """A warning quoting README v98 and the vendor until (measured 2026-10-13 at 108.4.0, data/contract/columns/operators_108_4_2026-10-13/): both were refused CONDITION_HOLD_ILLEGAL."""
    clause = _clause("crossesAbove", value=50)
    clause["hold"] = {"atLeast": 2, "of": 2}
    assert _walk(clause) == []                               # the schema only says atLeast >= 1
    errors, _ = _findings(clause)
    assert any("CONDITION_HOLD_ILLEGAL" in e.message for e in errors)
    group = {"kind": "group", "op": "ALL", "hold": {"atLeast": 2, "of": 3},
             "members": [_clause("crossesAbove", value=50), _clause("gt", value=40)]}
    assert _walk(group) == []
    errors, _ = _findings(group)
    assert any("CONDITION_HOLD_ILLEGAL" in e.message and "within" in e.message for e in errors)


def test_a_transition_label_outside_the_vocabulary_is_a_warning():
    definition = enters("RSI14_zone", "rising")
    assert _walk(definition) == []
    errors, warnings = _findings(definition)
    assert errors == []
    assert any("vocabulary" in w.message for w in warnings)


def test_the_older_operators_keep_their_errors():
    errors, _ = _findings(num("RSI14_zone", "gt", 1))
    assert any("does not accept 'gt'" in f.message for f in errors)


# --- the presets (step 4 of plan 2026-10-11-omega-condition-vocabulary-108) -------------------------
def test_no_preset_changed_because_no_preset_description_asks_for_a_prior_bar_read():
    """A new operator goes into a preset only where the preset's own description asks for it. None does: the five
    describe states ("Full MA alignment ...", "Oscillator extreme plus band breach ...", "Volatility contraction
    into expansion ...", "Spot CVD outpacing perp flow ...", "Price arriving at a structural zone ..."), not a
    cross, a flip or a change on the bar before. So every generated condition still reads with the 91 operators."""
    from omega.generate import PRESETS, _clauses_of, plan
    for name, thesis in PRESETS.items():
        assert not any(w in thesis.description.lower() for w in ("cross", "flip", "enters", "turns")), name
        ops = {c.get("op") for cond in plan(thesis).conditions for c in _clauses_of(cond["definition"])}
        assert ops and not ops & set(PRIOR_BAR_OPS), (name, ops)
