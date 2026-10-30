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
# The schema the manifest names: the 144.0.0 capture since 2026-10-30 (the 135.2.0 one of 2026-10-26, the 110.13.0 one
# of 2026-10-16, the 110.8.0 one of 2026-10-15, the 110.2.0 one of 2026-10-14 and the 108.0.0 one are kept below as
# history).
SCHEMA = ROOT / "data/contract/stage_strategy_draft/schema_20261029T152942Z.json"
SCHEMA_135 = ROOT / "data/contract/stage_strategy_draft/schema_20261026T062718Z.json"
SCHEMA_110_13 = ROOT / "data/contract/stage_strategy_draft/schema_20261016T031811Z.json"
SCHEMA_110_8 = ROOT / "data/contract/stage_strategy_draft/schema_20261015T015244Z.json"
SCHEMA_110_2 = ROOT / "data/contract/stage_strategy_draft/schema_20261013T200621Z.json"
SCHEMA_108 = ROOT / "data/contract/stage_strategy_draft/schema_20261010T215326Z.json"
MOVES_110 = json.loads((ROOT / "data/contract/metrics/_moves_110.json").read_text(encoding="utf-8"))
MOVES_110_8 = json.loads((ROOT / "data/contract/metrics/_moves_110_8.json").read_text(encoding="utf-8"))
MOVES_135 = json.loads((ROOT / "data/contract/metrics/_moves_135.json").read_text(encoding="utf-8"))
MOVES_144 = json.loads((ROOT / "data/contract/metrics/_moves_144.json").read_text(encoding="utf-8"))
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


def _in(doc: dict, ptr: str) -> str:
    """The inventory's pointer (rooted at the flat v111 input) re-rooted in `doc`: a capture from before v111 holds
    the stage's arguments under its `request` envelope (README v111: "A refusal's path into the payload loses its
    leading `request`" - the schema's own paths moved the same way)."""
    head = "/stage_strategy_draft/inputSchema"
    if "request" in doc["stage_strategy_draft"]["inputSchema"].get("properties", {}) and ptr.startswith(head + "/"):
        return head + "/properties/request" + ptr[len(head):]
    return ptr


def _enum_in(path: Path, key: str = "metric") -> list[str]:
    """`key`'s column enum in the capture at `path`, from that capture's OWN derivation: since v115.1 a discriminated
    union is `oneOf`, so today's pointers do not re-root into a capture from before it."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    return CV.derive(doc, source=path.name, source_sha256="")["reportColumn"][key]["enum"]


def _arm(op: str) -> dict:
    return G["clauseArms"][G["operators"][op]["arm"]]


def test_the_stored_inventory_is_the_schemas_derivation():
    assert CV.render(CV.derive_from_disk()) == CV.OUT.read_text(encoding="utf-8"), \
        "run `python scripts/derive_condition_vocabulary.py` and review the diff"


def test_the_inventory_names_its_source_by_path_and_hash():
    assert CV.schema_path() == SCHEMA
    assert V["source"] == {"schema": "data/contract/stage_strategy_draft/schema_20261029T152942Z.json",
                           "sha256": CV.sha256(SCHEMA), "contractVersion": "144.0.0",
                           "buildSha": "beb6b930bcf01c914c01d528aa88dc05c32d1d76",
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
    # members are definitions again: since v116 both name the shared shape, #/$defs/conditionNode
    assert CV.resolve(DOC, G["definitionPointer"]) == {"$ref": "#/$defs/conditionNode"}
    assert G["group"]["members"]["itemsRef"] == "/stage_strategy_draft/inputSchema/$defs/conditionNode"
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
    # v115.1: an integer publishes the safe-integer maximum (9,007,199,254,740,991) - acceptance did not move
    assert G["hold"]["schema"] == {"additionalProperties": False,
                                   "properties": {"atLeast": {"maximum": 9007199254740991, "minimum": 1,
                                                              "type": "integer"},
                                                  "of": {"maximum": 9007199254740991, "minimum": 1,
                                                         "type": "integer"}},
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
    """171 at 108; 177 since 110 (MACD, PPO, KC_MID retired, nine added - data/contract/metrics/_moves_110.json); 183
    since 110.8 (six added, none retired - _moves_110_8.json); 226 since 135 (43 added, none retired - _moves_135.json:
    seven at v123, PERP_SPOT_GAP at v134, 35 at v135.1) and the six v135 statistics in both transform enums; 302 since
    144 (78 added, STOCH_RSI14 and BB_WIDTH retired - _moves_144.json) and v142.3's relativeTo in the transform enum."""
    col = V["reportColumn"]
    assert col["metric"]["count"] == 302 == len(set(col["metric"]["enum"]))
    assert col["metric"]["pointer"] == "/stage_strategy_draft/inputSchema/$defs/metricKey"   # v137.2: named once
    assert set(MOVES_144["retired"]).isdisjoint(col["metric"]["enum"]) and set(MOVES_144["added"]) <= set(col["metric"]["enum"])
    stats = ["zscore", "stddev", "linregSlope", "pctl", "rollingMin", "rollingMax"]
    assert col["transformId"]["enum"] == [
        "value", "trajectory", "classifyZone", "classifyState", "distance", "spread", "relativeTo", "crossDetect", "aggregate",
        "efficiency", "maxShare", *stats, "rank", "count", "nearestZoneType", "nearestZoneRange", "nearestZoneDist",
        "nearestZoneAge", "levelInteraction"]
    assert col["chainedTransformId"]["enum"] == ["trajectory", "aggregate", "efficiency", "maxShare", *stats, "rank"]
    assert "buffer" in col["fields"]       # v100: "buffer, a column knob declared by levelInteraction only"
    assert "instrument" in col["fields"] and "scope" in col["fields"]      # v142.3 relativeTo's coin; v136 rank's scope


@pytest.mark.skipif(not HINTS_104_1.exists(), reason="the battlegrid-manager checkout is not beside this repo")
def test_the_108_stage_metric_enum_is_the_104_1_hints_enum():
    surface = json.loads(HINTS_104_1.read_text(encoding="utf-8"))
    hints = {t["name"]: t for t in surface["tools"]}["get_metric_construction_hints"]
    assert surface["contractVersion"] == "104.1.0"
    # History: the 108.0.0 stage schema's enum (kept on disk) against the 104.1.0 hints enum.
    assert hints["inputSchema"]["properties"]["metric"]["enum"] == _enum_108()


def _enum_108() -> list[str]:
    return _enum_in(SCHEMA_108)


def test_the_110_enum_is_the_108_enum_moved_exactly_as_v110_says():
    old, new = _enum_108(), _enum_in(SCHEMA_110_13)
    assert set(old) - set(new) == set(MOVES_110["retired"])
    assert set(new) - set(old) == set(MOVES_110["added"]) | set(MOVES_110_8["added"])
    assert [m for m in old if m in new] == [m for m in new if m in old]      # the survivors keep their platform order


def test_the_110_8_enum_is_the_110_2_enum_plus_the_six():
    old, new = _enum_in(SCHEMA_110_2), _enum_in(SCHEMA_110_8)
    assert MOVES_110_8["retired"] == {} and set(old) <= set(new)
    assert set(new) - set(old) == set(MOVES_110_8["added"])
    assert [m for m in new if m in old] == old                                 # the 177 keep their platform order


def test_v111_moved_no_column_enum_only_the_envelope():
    """110.13.0 (v111): the stage's arguments left the `request` envelope; every column enum is the 110.8.0 one, and
    the eight axes are byte-identical once the 110.8.0 local $refs are re-rooted (measured 2026-10-16)."""
    for key in ("metric", "transformId", "chainedTransformId"):
        assert _enum_in(SCHEMA_110_8, key) == _enum_in(SCHEMA_110_13, key), key
    old = json.loads(SCHEMA_110_8.read_text(encoding="utf-8"))["stage_strategy_draft"]["inputSchema"]
    new = json.loads(SCHEMA_110_13.read_text(encoding="utf-8"))["stage_strategy_draft"]["inputSchema"]
    assert set(old["properties"]) == {"request"} and old["required"] == ["request"]
    assert set(new["properties"]) == {"strategyId", "draftVersion", "axes"} and new["required"] == ["draftVersion", "axes"]
    flat = json.dumps(old["properties"]["request"], sort_keys=True).replace("#/properties/request/", "#/")
    assert json.loads(flat) == new


def test_the_135_enum_is_the_110_13_enum_plus_the_43():
    old, new = _enum_in(SCHEMA_110_13), _enum_in(SCHEMA_135)
    assert MOVES_135["retired"] == {} and set(old) <= set(new)
    assert set(new) - set(old) == set(MOVES_135["added"]) and len(MOVES_135["added"]) == 43
    assert [m for m in new if m in old] == old                                 # the 183 keep their platform order


def test_the_144_enum_is_the_135_enum_minus_the_two_plus_the_78():
    """v137 retired STOCH_RSI14, v138 BB_WIDTH; 78 keys arrived (v136.1, v137, v137.2, v137.3, v138, two undocumented) -
    _moves_144.json. The kept 224 keep their platform order; the enum is read at $defs/metricKey (v137.2)."""
    old, new = _enum_in(SCHEMA_135), V["reportColumn"]["metric"]["enum"]
    assert set(old) - set(new) == set(MOVES_144["retired"]) == {"STOCH_RSI14", "BB_WIDTH"}
    assert set(new) - set(old) == set(MOVES_144["added"]) and len(MOVES_144["added"]) == 78
    assert [m for m in new if m in old] == [m for m in old if m in new]
    assert set(MOVES_144["retiredBetweenExtractions"]).isdisjoint(old) and set(MOVES_144["retiredBetweenExtractions"]).isdisjoint(new)


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
    # known by name since 2026-10-11 (data/contract/metrics/_unmeasured_108.json); before, schemaOnly was these 15
    assert gaps["metrics"] == {"schemaOnly": [], "omegaOnly": []}
    # measured in the re-extraction at 108.4.0, 2026-10-13 (docs/plans/2026-10-13-omega-reextraction-108-4.md); before, these 15 (ADDED_SINCE_61_2)
    assert gaps["metricsUnmeasured"] == []
    # v100: "the bandTouch transform is retired and levelInteraction takes its place"; classifyState is served in
    # the enum and was platform-privileged at the 61.2.0 extraction (data/derived/platform_privileged.json)
    # The extraction's catalogue still lists bandTouch; since 2026-10-12 omega.contract derives it as RETIRED from this
    # very gap (and levelInteraction as UNMEASURED) and neither is enumerated or validated as legal
    # (tests/test_report_surface_108.py).
    # levelInteraction extracted 2026-10-13 (43 metrics); classifyState stays platform-privileged
    assert gaps["transforms"] == {"schemaOnly": ["classifyState"], "omegaOnly": ["bandTouch"]}
    # closed 2026-10-12: Column.buffer with the schema's 0-500; before, schemaOnly was ["buffer"]
    assert gaps["columnFields"] == {"schemaOnly": [], "omegaOnly": []}
    # the section anchor override left at 48.0.0; kept on the model for old records, refused by validate_section
    assert gaps["sectionFields"] == {"schemaOnly": [], "omegaOnly": ["timeframe"]}
