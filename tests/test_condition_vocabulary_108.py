"""The condition vocabulary at contract 108, re-derived from the saved write schema on every run.

Source: data/contract/stage_strategy_draft/schema_20261010T215326Z.json (the manifest's `writeSurface.schema`;
contract 108.0.0, build 1076c4e7, copied from battlegrid-manager tests/fixtures/2026-10-11-surface-108.0.0/
manager_schemas_108.0.0.json). Every fact asserted below is read from that file through the pointer the inventory
records; the README changelog (v98, v100, v101.1) is quoted only where it names the same thing.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from omega import condition_vocabulary as CV

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "data/contract/stage_strategy_draft/schema_20261010T215326Z.json"
DOC = json.loads(SCHEMA.read_text(encoding="utf-8"))
V = CV.vocabulary()
G = V["grammar"]
HINTS_104_1 = Path("C:/Users/rafae/Documents/GitHub/battlegrid-manager/tests/fixtures/"
                   "2026-10-08-surface-104.1.0/tool_definitions.json")

# v98: "a condition clause accepts six operators that compare a column with its own previous completed bar"
PRIOR_BAR = ["crossesAbove", "crossesBelow", "increased", "decreased", "enters", "exits"]
# v100 (12 metrics) + v101.1 (3 swing-structure metrics); the manager's pin-drift reports them against 104.x
ADDED_SINCE_61_2 = ["BAR_CONTAINMENT", "CANDLE_DOJI", "CANDLE_ENGULFING", "CANDLE_PIN", "CANDLE_RUN", "CLOSE_RUN",
                    "GAP", "GAP_PCT", "GAP_RANGE_CLEAR", "HL2", "HLC3", "OHLC4", "SWING_FRACTAL_HIGH",
                    "SWING_FRACTAL_LABEL", "SWING_FRACTAL_LOW"]


def _arm(op: str) -> dict:
    return G["clauseArms"][G["operators"][op]["arm"]]


def test_the_stored_inventory_is_the_schemas_derivation():
    assert CV.render(CV.derive_from_disk()) == CV.OUT.read_text(encoding="utf-8"), \
        "run `python scripts/derive_condition_vocabulary.py` and review the diff"


def test_the_inventory_names_its_source_by_path_and_hash():
    assert CV.schema_path() == SCHEMA
    assert V["source"] == {"schema": "data/contract/stage_strategy_draft/schema_20261010T215326Z.json",
                           "sha256": CV.sha256(SCHEMA), "contractVersion": "108.0.0",
                           "buildSha": "1076c4e78456424dd92242eeb30701099c6b9146",
                           "observedAt": DOC["observedAt"]}


def test_every_pointer_resolves_to_what_the_inventory_says_is_there():
    for arm in G["clauseArms"]:
        node = CV.resolve(DOC, arm["pointer"])
        assert node["properties"]["kind"]["const"] == "clause"
        op = CV.resolve(DOC, arm["opPointer"])
        assert (op.get("enum") or [op.get("const")]) == arm["ops"]
        for name, operand in arm["operands"].items():
            assert operand["pointer"].endswith(f"/properties/{name}")
            CV.resolve(DOC, operand["pointer"])
    assert CV.resolve(DOC, G["column"]["pointer"]) == G["column"]["schema"]
    assert CV.resolve(DOC, G["hold"]["pointer"]) == G["hold"]["schema"]
    assert CV.resolve(DOC, G["group"]["opPointer"])["enum"] == G["group"]["ops"]
    assert CV.resolve(DOC, G["group"]["holdPointer"]) == G["hold"]["schema"]
    assert G["group"]["members"]["itemsRef"] == G["definitionPointer"]          # members are definitions again
    assert CV.resolve(DOC, G["conditionRef"]["pointer"])["properties"]["kind"]["const"] == "conditionRef"
    for key in ("metric", "transformId", "chainedTransformId"):
        entry = V["reportColumn"][key]
        assert CV.resolve(DOC, entry["pointer"])["enum"] == entry["enum"]
    served = V["servedPerHeader"]
    assert CV.resolve(DOC, served["conditionOperators"]["pointer"])["enum"] == served["conditionOperators"]["enum"]
    assert CV.resolve(DOC, served["conditionHold"]["refusal"]["pointer"])["enum"] == \
        served["conditionHold"]["refusal"]["enum"]


# --- the operator inventory -----------------------------------------------------------------------
def test_thirteen_clause_operators_in_five_arms():
    # v98: "The authoring contract digest gains domains.conditionOperator, the thirteen operator names."
    assert V["clauseOperators"] == ["lt", "lte", "gte", "gt", "crossesAbove", "crossesBelow", "between",
                                    "is", "enters", "exits", "in", "increased", "decreased"]
    assert [arm["ops"] for arm in G["clauseArms"]] == [
        ["lt", "lte", "gte", "gt", "crossesAbove", "crossesBelow"], ["between"], ["is", "enters", "exits"],
        ["in"], ["increased", "decreased"]]
    assert all(arm["additionalProperties"] is False for arm in G["clauseArms"])
    assert set(PRIOR_BAR) < set(V["clauseOperators"])


def test_a_crossing_compares_the_column_with_one_number_value():
    # v98: "crossesAbove / crossesBelow with a number value" - the same arm as lt/lte/gte/gt; no second column
    for op in ("crossesAbove", "crossesBelow"):
        arm = _arm(op)
        assert arm["operands"] == {"value": {"pointer": arm["pointer"] + "/properties/value",
                                             "schema": {"type": "number"}}}
        assert arm["required"] == ["kind", "column", "op", "value", "hold"]
        assert G["operators"][op]["sharesArmWith"] == [o for o in arm["ops"] if o != op]


def test_enters_and_exits_take_one_label_never_a_range_or_a_set():
    # v98: "enters / exits with one label"
    for op in ("enters", "exits"):
        arm = _arm(op)
        assert set(arm["operands"]) == {"label"}
        assert arm["operands"]["label"]["schema"] == {"maxLength": 80, "minLength": 1, "type": "string"}
        assert arm["required"] == ["kind", "column", "op", "label", "hold"]
        assert G["operators"][op]["sharesArmWith"] == [o for o in ("is", "enters", "exits") if o != op]


def test_increased_and_decreased_take_no_operand_and_no_lookback():
    # v98: "increased / decreased with no literal ... A value beside them is refused" (additionalProperties:false)
    for op in ("increased", "decreased"):
        arm = _arm(op)
        assert arm["operands"] == {}
        assert arm["required"] == ["kind", "column", "op", "hold"]
        assert arm["additionalProperties"] is False


def test_the_older_arms_are_unchanged_since_91():
    assert _arm("between")["operands"] == {
        "high": {"pointer": _arm("between")["pointer"] + "/properties/high", "schema": {"type": "number"}},
        "low": {"pointer": _arm("between")["pointer"] + "/properties/low", "schema": {"type": "number"}}}
    labels = _arm("in")["operands"]["labels"]["schema"]
    assert labels == {"items": {"maxLength": 80, "minLength": 1, "type": "string"},
                      "maxItems": 32, "minItems": 1, "type": "array"}


def test_every_clause_and_group_carries_the_same_hold_and_a_ref_carries_none():
    assert G["hold"]["schema"] == {"additionalProperties": False,
                                   "properties": {"atLeast": {"minimum": 1, "type": "integer"},
                                                  "of": {"minimum": 1, "type": "integer"}},
                                   "required": ["atLeast", "of"], "type": "object"}
    assert all("hold" in arm["required"] for arm in G["clauseArms"])
    assert "hold" in G["group"]["required"]
    assert G["conditionRef"]["required"] == ["kind", "conditionKey"]
    assert set(G["conditionRef"]["fields"]) == {"kind", "conditionKey"}
    assert G["conditionRef"]["additionalProperties"] is False


def test_groups_conditions_and_the_conditions_array():
    assert G["group"]["ops"] == ["ALL", "ANY", "NOT", "N_OF"]
    assert (G["group"]["members"]["minItems"], G["group"]["members"]["maxItems"]) == (1, 64)
    assert G["group"]["n"]["schema"] == {"exclusiveMinimum": 0, "maximum": 64, "type": "integer"}
    assert G["condition"]["required"] == ["conditionKey", "name", "definition", "verdict", "required", "exitSide"]
    assert G["condition"]["additionalProperties"] is False
    # v103: "The fixed 64 maximums leave strategy authoring: ... the conditions arrays" - budgets judge them
    assert V["conditionsArray"]["bounds"] == {}


def test_the_preview_takes_the_same_grammar_as_the_stage():
    assert V["previewConditions"]["sameGrammarAsStage"] is True
    assert V["previewConditions"]["pointer"].startswith("/preview_strategy_report/inputSchema/properties/source/")


def test_what_is_served_per_header_names_the_same_thirteen_operators():
    served = V["servedPerHeader"]
    assert sorted(served["conditionOperators"]["enum"]) == sorted(V["clauseOperators"])
    assert served["conditionHold"]["required"] == ["timeframe", "maxWindow", "maxAtLeast", "refusal"]
    assert served["conditionHold"]["refusal"]["enum"] == [
        "NOT_REWINDABLE", "DEVELOPING", "OFFSET", "BAR_STATE", "HISTORY", "MEMBER_HOLDS_WINDOW",
        "MEMBER_IS_REFERENCE", "NESTED_HELD_GROUP"]


# --- the column enums -----------------------------------------------------------------------------
def test_the_column_metric_enum_is_171_and_the_transform_enum_17():
    col = V["reportColumn"]
    assert col["metric"]["count"] == 171 == len(set(col["metric"]["enum"]))
    assert col["transformId"]["enum"] == [
        "value", "trajectory", "classifyZone", "classifyState", "distance", "spread", "crossDetect", "aggregate",
        "efficiency", "maxShare", "rank", "count", "nearestZoneType", "nearestZoneRange", "nearestZoneDist",
        "nearestZoneAge", "levelInteraction"]
    assert col["chainedTransformId"]["enum"] == ["trajectory", "aggregate", "efficiency", "maxShare", "rank"]
    assert "buffer" in col["fields"]       # v100: "buffer, a column knob declared by levelInteraction only"


@pytest.mark.skipif(not HINTS_104_1.exists(), reason="the battlegrid-manager checkout is not beside this repo")
def test_the_108_stage_metric_enum_is_the_104_1_hints_enum():
    surface = json.loads(HINTS_104_1.read_text(encoding="utf-8"))
    hints = {t["name"]: t for t in surface["tools"]}["get_metric_construction_hints"]
    assert surface["contractVersion"] == "104.1.0"
    assert hints["inputSchema"]["properties"]["metric"]["enum"] == V["reportColumn"]["metric"]["enum"]


# --- a schema swap shows up as a diff -------------------------------------------------------------
def test_a_moved_schema_derives_a_different_inventory():
    moved = copy.deepcopy(DOC)
    arm = CV.resolve(moved, _arm("increased")["pointer"])
    arm["properties"]["op"]["enum"].append("unchanged")
    out = CV.derive(moved, source="x", source_sha256="y")
    assert "unchanged" in out["clauseOperators"]
    assert out["previewConditions"]["sameGrammarAsStage"] is False      # the preview did not move with it


# --- what omega models against it -----------------------------------------------------------------
def test_the_gaps_between_the_schema_and_omega():
    gaps = CV.gaps()
    # closed 2026-10-11: the six v98 operators have builders and validate_conditions checks their arms
    # (tests/test_conditions_prior_bar.py); before, schemaOnly was exactly PRIOR_BAR
    assert gaps["clauseOperators"] == {"schemaOnly": [], "omegaOnly": []}
    assert gaps["groupOperators"] == {"schemaOnly": [], "omegaOnly": []}
    assert gaps["metrics"] == {"schemaOnly": ADDED_SINCE_61_2, "omegaOnly": []}
    # v100: "the bandTouch transform is retired and levelInteraction takes its place"; classifyState is served in
    # the enum and was platform-privileged at the 61.2.0 extraction (data/derived/platform_privileged.json)
    assert gaps["transforms"] == {"schemaOnly": ["classifyState", "levelInteraction"], "omegaOnly": ["bandTouch"]}
    assert gaps["columnFields"] == {"schemaOnly": ["buffer"], "omegaOnly": []}
