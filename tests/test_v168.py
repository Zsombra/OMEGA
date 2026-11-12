"""OMEGA v0.13.0: the re-extraction at contract 168.3.0 (build af8b2c96, 2026-11-11).

157 - 168 are not in the vendor README (its newest entry is v156), so the served schemas and hints are the source.
What 168 moved, and where each piece is pinned:

  the trade level menu (TRADE_LEVEL_POLICY.tradeLevelMenu, required)      tests/test_trade_level_menu_168.py
  the hints read over one mcporter runtime; operand sets resolved          tests/test_refresh_metric_contracts.py,
                                                                            tests/test_mcporter_transport.py
  here: the moves record, the roster read from the read schema, the three knobs, and what 168 served and v0.13.0 left
  unmeasured - the chained spread, a spread operand under an average, the SEQUENCE group - each measured at 169.4.0
  and modelled by v0.13.1 (tests/test_v169.py). The manifest moved to the 169.4.0 re-read (tests/test_v169.py).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from omega import condition_vocabulary as cv
from omega.conditions import GROUP_OPS
from omega.contract import load, stage_schema
from omega.space import enumerate_shapes
from omega.types import KNOBS, Column, Operand
from omega.validate import validate_column

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "data/contract/_manifest.json").read_text(encoding="utf-8"))
MOVES = json.loads((ROOT / "data/contract/metrics/_moves_168.json").read_text(encoding="utf-8"))
UNMEASURED = json.loads((ROOT / "data/contract/metrics/_unmeasured_108.json").read_text(encoding="utf-8"))
BUILD = "af8b2c9632fa71620e9dcc1802904ee963d305a4"
ANCHOR = {"rel": "anchor"}


def _codes(column: Column) -> list[tuple[str, str]]:
    return [(f.code, f.path) for f in validate_column(column)]


# --- the manifest ------------------------------------------------------------------------------------------------

def test_the_manifest_records_the_168_extraction_and_keeps_161_as_history():
    # since 2026-11-12 the 168.3.0 block is the `supersedes` of the 169.4.0 re-read (tests/test_v169.py), as are both
    # write surfaces
    from tests.manifest_chain import extraction as extraction_of, surface as surface_of
    extraction = extraction_of("168.3.0", MANIFEST)
    assert extraction["extractedOn"] == "2026-11-11"
    assert BUILD in extraction["contractVersionSource"]
    previous = extraction["supersedes"]
    assert (previous["servedContractVersion"], previous["extractedOn"], previous["counts"]["metrics"]) == (
        "161.0.0", "2026-11-09", 534)
    assert previous["supersedes"]["servedContractVersion"] == "146.0.1"
    surface = surface_of("168.3.0", MANIFEST)
    assert surface["buildSha"] == BUILD
    assert surface["schema"] == "data/contract/stage_strategy_draft/schema_20261111T213257Z.json"
    assert surface["supersedes"]["servedContractVersion"] == "161.0.0"


def test_the_manifest_counts_are_the_corpus():
    # the 168.3.0 block's counts, on a corpus that did not move to 169.4.0; only the space grew since (the chained
    # spread's 660 shapes, modelled 2026-11-12) - the top block's counts are pinned in tests/test_v169.py
    c = load()
    legal = sum(len(m.transforms) for m in c.metrics.values())
    from tests.manifest_chain import extraction as extraction_of
    counts = extraction_of("168.3.0", MANIFEST)["counts"]
    assert (counts["metrics"], counts["families"], counts["authorableTransforms"]) == (
        len(c.metrics), len({m.family for m in c.metrics.values()}), len(c.transforms)) == (581, 14, 30)
    assert (counts["composabilityCells"], counts["composabilityLegal"]) == (581 * 30, legal) == (17430, 4735)
    assert counts["structuralShapes"] == len(enumerate_shapes()) - 660 == 26584
    assert counts["platformSectionTemplates"] == len(c.platform_templates) == 22


def test_the_two_captures_of_the_day_hold_the_same_six_tools():
    # the menu was measured at 168.2.0 (fifteen drafts) and at 168.3.0 (fifteen): one write surface
    first = json.loads((ROOT / "data/contract/stage_strategy_draft/schema_20261111T183243Z.json").read_text(encoding="utf-8"))
    from tests.manifest_chain import surface as surface_of
    pinned = json.loads((ROOT / surface_of("168.3.0", MANIFEST)["schema"]).read_text(encoding="utf-8"))
    assert (first["contractVersion"], pinned["contractVersion"], pinned["buildSha"]) == ("168.2.0", "168.3.0", BUILD)
    # the six draft tools were the same at 169.4.0; 170 moved the trade level menu (tests/test_exit_plans_170.py)
    nineteen = json.loads((ROOT / surface_of("169.4.0", MANIFEST)["schema"]).read_text(encoding="utf-8"))
    assert all(nineteen[tool] == pinned[tool] for tool in MANIFEST["writeSurface"]["tools"])
    for tool in MANIFEST["writeSurface"]["tools"]:
        assert first[tool] == pinned[tool], tool
    assert all(all(parts.values()) for parts in pinned["managerRowAgrees"].values())


# --- the roster ----------------------------------------------------------------------------------------------------

def test_the_write_schema_names_a_metric_by_pattern_and_the_roster_is_the_read_schemas_enum():
    doc = stage_schema()
    key = doc["stage_strategy_draft"]["inputSchema"]["$defs"]["metricKey"]
    assert "enum" not in key and key["pattern"] == "^[A-Z][A-Z0-9_]*$" and (key["minLength"], key["maxLength"]) == (1, 64)
    served = cv.vocabulary()["reportColumn"]["metric"]
    assert served["enumPointer"] == "/get_strategy/outputSchema/$defs/metricKey"
    assert served["enum"] == doc["get_strategy"]["outputSchema"]["$defs"]["metricKey"]["enum"]
    assert served["count"] == 581 and set(served["enum"]) == set(load().metrics)
    assert all(__import__("re").fullmatch(key["pattern"], name) for name in served["enum"])
    assert UNMEASURED["metrics"] == {} and UNMEASURED["servedAt"] == "169.4.0"      # 168.3.0 until 2026-11-12


def test_the_moves_record_is_the_corpus_against_161():
    c = load()
    assert (MOVES["contractVersion"], MOVES["buildSha"], MOVES["hintsReadOn"]) == ("168.3.0", BUILD, "2026-11-11")
    assert MOVES["metrics"] == {"at161": 534, "at168": 581} and MOVES["retired"] == []
    added = MOVES["added"]
    assert len(added) == 47 == len(set(added)) and set(added) <= set(c.metrics)
    assert Counter(c.metrics[m].family for m in added) == Counter(MOVES["addedByFamily"]) == Counter(
        {"levels": 24, "structure": 22, "trend": 1})
    assert "EMA55" in added and c.metrics["EMA55"].family == "trend"
    # the platform split three categories out of `structure` and re-homed the metrics it already served
    assert MOVES["familiesMoved"]["byMove"] == {"structure -> channels": 14, "structure -> levels": 250,
                                                "structure -> trend": 2, "structure -> vwapProfile": 81}
    for name, (_, now) in MOVES["familiesMoved"]["metrics"].items():
        assert c.metrics[name].family == now, name
    assert MOVES["headerCodesMoved"] == [] and MOVES["nativeOutputMoved"] == {} and MOVES["platformTemplatesChanged"] == []
    assert MOVES["parametersAdded"] == {"STRUCT_ZONES": ["usedUpOnClose"]}


def test_the_new_keys_validate_and_spell_as_the_sweep_rendered_them():
    sweep = json.loads((ROOT / "data/audit/coverage_sweep_2026-11-11.json").read_text(encoding="utf-8"))
    assert (sweep["contractVersion"], sweep["versionAtEnd"], sweep["buildSha"], sweep["contractMoved"]) == (
        "168.3.0", "168.3.0", BUILD, False)
    assert (sweep["shapesRequested"], sweep["headersMinted"], sweep["refusalCount"],
            sweep["predictedButNotRenderedCount"], sweep["complete"]) == (557, 673, 0, 0, True)
    rendered = set(json.loads((ROOT / "data/contract/columns/_coverage_sweep_2026-11-11.json")
                              .read_text(encoding="utf-8"))["headers"])
    from omega.fanout import outputs_for
    c = load()
    for metric, header in (("EQH_LEVEL", "eqhLvl"), ("PRIOR_ASIA_DEMAND_AVG", "pAsiaDemAvg")):
        column = Column(metric=metric, transformId="value", timeframe=ANCHOR)
        assert _codes(column) == []
        assert [o.header for o in outputs_for(column, c)] == [header] and header in rendered


# --- the three knobs -------------------------------------------------------------------------------------------------

def test_the_three_knobs_are_served_where_the_corpus_says_and_judged_against_what_each_metric_serves():
    c = load()
    assert KNOBS[-3:] == ("supplyDemandThreshold", "supplyDemandResolution", "usedUpOnClose")
    serving = {knob: sorted(m.metric for m in c.metrics.values() if knob in (m.parameters or {})) for knob in KNOBS[-3:]}
    assert len(serving["supplyDemandThreshold"]) == len(serving["supplyDemandResolution"]) == 24
    assert all(name.startswith("PRIOR_") and ("_DEMAND_" in name or "_SUPPLY_" in name)
               for name in serving["supplyDemandThreshold"])
    assert serving["usedUpOnClose"] == ["STRUCT_ZONES", "ZONE_RESIST_HIGH", "ZONE_RESIST_LOW", "ZONE_RESIST_MID",
                                        "ZONE_SUPPORT_HIGH", "ZONE_SUPPORT_LOW", "ZONE_SUPPORT_MID"]
    served = c.metrics["PRIOR_ASIA_DEMAND_AVG"].parameters
    assert {k: (v["defaultValue"], v["minimum"], v["maximum"], v["step"]) for k, v in served.items()} == {
        "supplyDemandThreshold": (10, 0, 100, 0.5), "supplyDemandResolution": (50, 2, 500, 1)}

    def zone(**knobs):
        return Column(metric="PRIOR_ASIA_DEMAND_AVG", transformId="value", timeframe=ANCHOR, **knobs)

    assert _codes(zone(supplyDemandThreshold=10)) == []                      # the explicit default spells nothing
    assert _codes(Column(metric="ZONE_SUPPORT_LOW", transformId="value", timeframe=ANCHOR, usedUpOnClose=False)) == []
    assert ("PARAMETER_OUT_OF_RANGE", "column.supplyDemandThreshold") in _codes(zone(supplyDemandThreshold=120))
    assert ("PARAMETER_OUT_OF_RANGE", "column.supplyDemandResolution") in _codes(zone(supplyDemandResolution=50.5))
    assert _codes(Column(metric="EMA20", transformId="value", timeframe=ANCHOR, usedUpOnClose=True)) == [
        ("PARAMETER_UNDECLARED", "column.usedUpOnClose")]


@pytest.mark.parametrize("knobs, header", [
    ({"supplyDemandThreshold": 10.5}, "pAsiaDemAvg_vt10.5"),
    ({"supplyDemandResolution": 51}, "pAsiaDemAvg_res51"),
    # both off share ONE token in the served order - neither the SINGLE regime (_vt10.5_res51) nor the SET one
    ({"supplyDemandThreshold": 10.5, "supplyDemandResolution": 51}, "pAsiaDemAvg_vt10.5res51"),
    ({"supplyDemandThreshold": 10, "supplyDemandResolution": 50}, "pAsiaDemAvg"),          # explicit defaults spell nothing
])
def test_the_supply_demand_knobs_spell_as_the_168_probe_rendered_them(knobs, header):
    from omega.fanout import outputs_for
    column = Column(metric="PRIOR_ASIA_DEMAND_AVG", transformId="value", timeframe=ANCHOR, **knobs)
    assert _codes(column) == []
    assert [o.header for o in outputs_for(column, load())] == [header]
    rendered = {h for batch in "abc" for h in json.loads(
        (ROOT / f"data/contract/columns/_probe_168_knobs_2026-11-11-{batch}.json").read_text(encoding="utf-8"))["headers"]}
    assert header in rendered or not column.knobs() or all(
        v == load().metrics[column.metric].parameters[k]["defaultValue"] for k, v in column.knobs().items())


def test_the_structure_zone_flag_spells_close_and_every_168_knob_cell_is_rendered():
    from omega.fanout import KNOB_JOINED, KNOB_SINGLE, KNOB_SPELLING_RENDERED, outputs_for
    c = load()
    assert KNOB_JOINED == {"supplyDemandThreshold": "vt", "supplyDemandResolution": "res"}
    assert KNOB_SINGLE["usedUpOnClose"] == "close"
    zone = Column(metric="ZONE_RESIST_HIGH", transformId="value", timeframe=ANCHOR, usedUpOnClose=True)
    assert _codes(zone) == [] and [o.header for o in outputs_for(zone, c)] == ["zoneResHi_close"]
    count = Column(metric="STRUCT_ZONES", transformId="count", timeframe=ANCHOR, usedUpOnClose=True)
    assert [o.header for o in outputs_for(count, c)] == ["zones_close_count"]
    # the known names on the added keys spell as on the old ones
    pool = Column(metric="LIQUIDITY_POOL_ABOVE", transformId="value", timeframe=ANCHOR, equalBars=4, equalThreshold=0.2)
    assert _codes(pool) == [] and [o.header for o in outputs_for(pool, c)] == ["poolAbove_e4_atr0.2"]
    served = {name: frozenset(m.parameters) for name, m in c.metrics.items() if m.parameters}
    assert served == KNOB_SPELLING_RENDERED and sum(map(len, served.values())) == 191


# --- served and not modelled yet ---------------------------------------------------------------------------------------

def test_the_chained_spread_was_unmeasured_at_168_and_is_modelled_since_169():
    # v0.13.0 recorded `spread` as a chain outer unmeasured and refused it (TRANSFORM_UNMEASURED); v0.13.1 rendered it
    # at 169.4.0 on 2026-11-12 (tests/test_v169.py) and moved the record into history169
    c = load()
    assert UNMEASURED["chainOuters"] == {} == c.unmeasured_chain_outers
    was = UNMEASURED["history169"]["formerlyUnmeasured"]["chainOuters"]["spread"]
    assert (was["servedAt"], UNMEASURED["history169"]["measuredAt"]) == ("168.3.0", "169.4.0")
    assert cv.vocabulary()["reportColumn"]["chainedTransformId"]["count"] == 20
    inners = Counter(t for m in c.metrics.values() for t, flags in m.transforms.items()
                     if "spread" in (flags.get("chainSuccessors") or ()))
    assert inners == Counter({"aggregate": 165, "ema": 165, "rma": 165, "wma": 165})
    assert MOVES["chainOutersGained"]["aggregate->spread"] == 162          # 165 less the three added keys that serve it
    # ADX x aggregate -> spread is offered, and RSI14 is not one of its served operands (another unit)
    column = Column(metric="ADX", transformId="aggregate", timeframe=ANCHOR, window=20, chainedTransformId="spread",
                    inputs=[{"metric": "RSI14"}])
    assert _codes(column) == []                                  # RSI14 is one of its served operands (the 0-100 unit)
    column = column.model_copy(update={"inputs": [Operand(metric="CLOSE")]})
    assert _codes(column) == [("REPORT_COLUMN_OPERAND_UNSUPPORTED", "column.inputs[0]")]
    assert sum(shape.chained == "spread" for shape in enumerate_shapes()) == 660


def test_a_spread_operand_under_an_average_was_unbuildable_at_168_and_is_modelled_since_169():
    # 168 serves `inputs[]` {metric, transformId, window}; the corpus records the operand lists (served on 501 metrics).
    # v0.13.0's Operand admitted `metric` alone; v0.13.1 builds the average and omega.validate judges it
    c = load()
    assert sum(1 for name in c.metrics
               if json.loads((ROOT / f"data/contract/metrics/{name}.json").read_text(encoding="utf-8"))
               .get("spreadAverageOperands")) == 501
    assert Operand(metric="EMA20", transformId="ema", window=5).averaged
    assert not Operand(metric="EMA20").averaged
    with pytest.raises(ValidationError):
        Operand(metric="EMA20", transformId="ema", window=5, offset=1)


def test_sequence_is_served_and_since_169_a_group_omega_builds_and_judges():
    grammar = cv.vocabulary()
    assert grammar["groupOperators"] == ["ALL", "ANY", "NOT", "N_OF", "SEQUENCE"]
    assert GROUP_OPS == ("ALL", "ANY", "NOT", "N_OF", "SEQUENCE")
    assert cv.gaps()["groupOperators"] == {"schemaOnly": [], "omegaOnly": []}
    group = stage_schema()["stage_strategy_draft"]["inputSchema"]["$defs"]["conditionNode"]
    arms = group.get("anyOf") or group.get("oneOf")
    within = [arm["properties"]["within"] for arm in arms if "within" in arm.get("properties", {})]
    assert within == [{"type": "integer", "exclusiveMinimum": 0, "maximum": 9007199254740991}]


# --- semantics that moved in the served text -------------------------------------------------------------------------

def test_the_served_authoring_text_that_moved():
    catalogue = json.loads((ROOT / "data/contract/transforms/_authoring.json").read_text(encoding="utf-8"))["transforms"]
    bars = catalogue["value"]["parameters"]["bars"]["description"]
    assert bars.endswith("Left unset, a column reads Confirmed at every timeframe; Developing applies only where it "
                         "is chosen.")
    assert bars == MOVES["authoringTextMovedQuotes"]["bars"]
    assert len(MOVES["authoringTextMoved"]["parameters/bars/description changed"]) == 23
    zone = catalogue["nearestZoneDist"]
    assert "nearEdge(nearest zone)" in zone["formula"] and zone["formula"].startswith("output = 0 when low")
    assert "at least 2" in catalogue["spread"]["parameters"]["inputs"]["description"]


# --- the offline preflight still refuses a metric the platform does not serve ------------------------------------------

def _stage_body(preset: str = "trend-continuation") -> dict:
    from omega.generate import PRESETS, plan
    return {"draftVersion": 0, "axes": plan(PRESETS[preset]).axes()}


def test_the_schema_walk_refuses_an_unserved_metric_key_through_the_read_schemas_roster():
    """To 161 the stage schema enumerated the metric keys, so an unknown one failed the walk as ENUM. At 168 the schema
    names a metric by pattern: without the roster the walk would pass `NOT_A_METRIC` (found 2026-11-11 while re-pinning).
    The roster is the same capture's get_strategy output enum; a key outside it is ENUM again, a key that is not even a
    key is PATTERN, and a walk given no roster says the key was not checked."""
    from omega import preflight as P
    doc = stage_schema()
    root = doc["stage_strategy_draft"]["inputSchema"]
    roster = P.read_roster(doc)
    assert len(roster) == 581 and "PATTERN" in P.CLASSES

    def fails(body, **kw):
        return [(f.cls, f.path) for f in P.diff_schema(body, root, root, **kw) if f.verdict == "FAIL"]

    clean = _stage_body()
    assert fails(clean, roster=roster) == []
    column = "axes.REPORT.sections[0].columns[0].metric"

    unknown = _stage_body()
    unknown["axes"]["REPORT"]["sections"][0]["columns"][0]["metric"] = "NOT_A_METRIC"
    assert fails(unknown, roster=roster) == [("ENUM", column)]
    unchecked = [f for f in P.diff_schema(unknown, root, root) if f.path == column]
    assert [(f.cls, f.verdict) for f in unchecked] == [("INFO", "INFO")] and "metric-roster-unchecked" in unchecked[0].detail

    malformed = _stage_body()
    malformed["axes"]["REPORT"]["sections"][0]["columns"][0]["metric"] = "rsi 14"
    assert fails(malformed) == [("PATTERN", column)]                      # the pattern alone refuses it, roster or not
    assert fails(malformed, roster=roster) == [("ENUM", column)]

    # a level reference names a metric too: the menu's levels are checked by the same rule
    menu = _stage_body()
    side = menu["axes"]["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]["LONG"]
    side["stops"].append({"kind": "LEVEL", "bufferAtrMultiple": 0,
                          "level": {"metric": "NOT_A_LEVEL", "timeframe": ANCHOR, "bars": None, "offset": 0,
                                    "knobs": {}, "windowExtreme": None}})
    assert fails(menu, roster=roster) == [("ENUM", "axes.TRADE_LEVEL_POLICY.tradeLevelMenu.LONG.stops[3].level.metric")]


def test_a_capture_before_168_has_no_roster_and_needs_none():
    from omega import preflight as P
    old = json.loads((ROOT / "data/contract/stage_strategy_draft/schema_20261109T162100Z.json").read_text(encoding="utf-8"))
    root = old["stage_strategy_draft"]["inputSchema"]
    assert "enum" in root["$defs"]["metricKey"]                          # the 161 write schema IS the roster
    body = _stage_body()
    del body["axes"]["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]             # a 161 body carries no menu
    body["axes"]["REPORT"]["sections"][0]["columns"][0]["metric"] = "NOT_A_METRIC"
    found = [(f.cls, f.path) for f in P.diff_schema(body, root, root) if f.verdict == "FAIL"]
    assert found == [("ENUM", "axes.REPORT.sections[0].columns[0].metric")]
