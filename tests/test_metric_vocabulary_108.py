"""The 171-metric vocabulary served at contract 108: 156 measured (the 61.2.0 extraction) and 15 known by name only.

The 15 are the REPORT column metric enum of the saved 108 write schema (data/derived/condition_vocabulary_108.json)
minus the measured corpus: the twelve bar-geometry metrics of README "Contract history - v100" and the three swing
metrics of "v101.1". Which transforms each composes is UNMEASURED offline (it was read live per metric at 61.2.0), so
omega refuses to emit them (METRIC_UNMEASURED) while scripts/compare_vocabulary.py counts them as stored - which is
what makes battlegrid-manager's `pin_drift` stop reporting them as `VOCABULARY_MOVED metrics.liveNotStored`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.condition_vocabulary import resolve, vocabulary
from omega.contract import CONTRACT_DIR, load
from omega.generate import PRESETS, plan
from omega.types import Column, CustomSection, Report
from omega.validate import validate_column, validate_report
from scripts.compare_vocabulary import compare, live_enums, stored_enums, stored_unmeasured

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((CONTRACT_DIR / "metrics" / "_unmeasured_108.json").read_text(encoding="utf-8"))
SERVED = vocabulary()["reportColumn"]["metric"]["enum"]
V100 = {"CANDLE_DOJI", "CANDLE_PIN", "CANDLE_ENGULFING", "BAR_CONTAINMENT", "GAP", "GAP_RANGE_CLEAR", "GAP_PCT",
        "CLOSE_RUN", "CANDLE_RUN", "HL2", "HLC3", "OHLC4"}                       # README v100: "Twelve metrics"
V101_1 = {"SWING_FRACTAL_HIGH", "SWING_FRACTAL_LOW", "SWING_FRACTAL_LABEL"}    # README v101.1: "three swing-structure"
SURFACE_104_1 = Path("C:/Users/rafae/Documents/GitHub/battlegrid-manager/tests/fixtures/"
                     "2026-10-08-surface-104.1.0/tool_definitions.json")


def test_the_unmeasured_record_is_exactly_the_served_enum_minus_the_measured_corpus():
    c = load()
    assert set(RECORD["metrics"]) == set(SERVED) - set(c.metrics) == V100 | V101_1
    assert set(c.metrics) < set(SERVED) and len(c.metrics) == 156 and len(SERVED) == 171
    assert {m for m, r in RECORD["metrics"].items() if r["addedAt"] == "v100"} == V100
    assert {m for m, r in RECORD["metrics"].items() if r["addedAt"] == "v101.1"} == V101_1
    assert all(r["transformAdmissibility"] == "UNMEASURED" for r in RECORD["metrics"].values())
    schema = json.loads((ROOT / RECORD["source"]["schema"]).read_text(encoding="utf-8"))
    assert resolve(schema, RECORD["source"]["pointer"])["enum"] == SERVED


def test_the_contract_knows_them_by_name_and_never_as_measured():
    c = load()
    assert set(c.unmeasured_metrics) == V100 | V101_1
    assert not set(c.unmeasured_metrics) & set(c.metrics)


@pytest.mark.parametrize("metric", sorted(V100 | V101_1))
def test_a_column_over_an_unmeasured_metric_is_refused(metric):
    column = Column.model_validate({"metric": metric, "transformId": "value", "timeframe": {"rel": "anchor"}})
    findings = validate_column(column)
    assert [f.code for f in findings] == ["METRIC_UNMEASURED"]
    assert findings[0].severity == "error" and "get_metric_construction_hints" in findings[0].message


def test_a_report_carrying_one_does_not_validate():
    report = Report(anchor="1h", sections=[CustomSection(title="T", columns=[
        Column.model_validate({"metric": "HLC3", "transformId": "value", "timeframe": {"rel": "anchor"}})])])
    assert not validate_report(report).ok


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_no_generated_plan_emits_an_unmeasured_metric(name):
    report = plan(PRESETS[name]).report
    used = {col.metric for s in report.sections if isinstance(s, CustomSection) for col in s.columns}
    assert used and not used & set(load().unmeasured_metrics)


# --- what the manager's pin-drift check sees -------------------------------------------------------
def _surface(metrics: list[str], sections: set[str]) -> dict:
    axes = {"REPORT": {"type": "object", "properties": {"sections": {"type": "array", "items": {"anyOf": [
        {"type": "object", "properties": {"sectionKey": {"type": "string", "enum": sorted(sections)}}}]}}}}}
    return {"tools": [
        {"name": "get_metric_construction_hints",
         "inputSchema": {"type": "object", "properties": {"metric": {"type": "string", "enum": metrics}}}},
        {"name": "stage_strategy_draft", "inputSchema": {"type": "object", "properties": {"request": {
            "type": "object", "properties": {"axes": {"type": "object", "properties": axes}}}}}}]}


def test_the_served_171_compare_as_stored_and_the_15_are_named_unmeasured():
    stored = stored_enums()
    assert stored["metrics"] == set(SERVED)
    result = compare(live_enums(_surface(SERVED, stored["sectionKeys"])), stored, stored_unmeasured())
    assert result["metrics"]["liveNotStored"] == [] and result["metrics"]["storedNotLive"] == []
    assert result["metrics"]["storedUnmeasured"] == sorted(V100 | V101_1)
    # a caller that passes no `unmeasured` (battlegrid-manager's pin_drift) reads the same two lists it always did
    assert compare(live_enums(_surface(SERVED, stored["sectionKeys"])), stored)["metrics"]["storedUnmeasured"] == []


@pytest.mark.skipif(not SURFACE_104_1.exists(), reason="the battlegrid-manager checkout is not beside this repo")
def test_the_stored_104_1_surface_no_longer_reports_a_metric_as_missing():
    """battlegrid-manager pin_drift -> _moved("metrics", liveNotStored, ...) raised one VOCABULARY_MOVED warning per
    metric OMEGA had not extracted: these 15 against the 104.x surfaces. With the names stored, the list is empty."""
    surface = json.loads(SURFACE_104_1.read_text(encoding="utf-8"))
    result = compare(live_enums(surface), stored_enums(), stored_unmeasured())
    assert result["metrics"]["liveNotStored"] == []
    assert result["metrics"]["storedUnmeasured"] == sorted(V100 | V101_1)
