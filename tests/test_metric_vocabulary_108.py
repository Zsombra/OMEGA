"""The 171-metric vocabulary served at contract 108 - all of it MEASURED since 2026-10-13.

History: from 2026-10-11 the 15 metrics added at v100 / v101.1 were known by name only (the 108 column enum minus the
61.2.0 corpus) and refused (METRIC_UNMEASURED). On 2026-10-13 `get_metric_construction_hints` was read for all 171 at
contract 108.4.0 (docs/plans/2026-10-13-omega-reextraction-108-4.md); the corpus now holds every served metric,
data/contract/metrics/_unmeasured_108.json is empty and names what it used to hold, and the 2026-10-13 render sweep
rendered every shape over them live.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.condition_vocabulary import vocabulary
from omega.contract import CONTRACT_DIR, load
from omega.generate import PRESETS, plan
from omega.types import Column, CustomSection, Report
from omega.validate import validate_column, validate_report
from scripts.compare_vocabulary import compare, live_enums, stored_enums, stored_unmeasured

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((CONTRACT_DIR / "metrics" / "_unmeasured_108.json").read_text(encoding="utf-8"))
SERVED = vocabulary()["reportColumn"]["metric"]["enum"]
PATTERNS_GAPS_RUNS = {"CANDLE_DOJI", "CANDLE_PIN", "CANDLE_ENGULFING", "BAR_CONTAINMENT", "GAP", "GAP_RANGE_CLEAR",
                      "GAP_PCT", "CLOSE_RUN", "CANDLE_RUN"}
PRICE_SOURCES = {"HL2", "HLC3", "OHLC4"}
V100 = PATTERNS_GAPS_RUNS | PRICE_SOURCES                                        # README v100: "Twelve metrics"
V101_1 = {"SWING_FRACTAL_HIGH", "SWING_FRACTAL_LOW", "SWING_FRACTAL_LABEL"}    # README v101.1: "three swing-structure"
SURFACE_104_1 = Path("C:/Users/rafae/Documents/GitHub/battlegrid-manager/tests/fixtures/"
                     "2026-10-08-surface-104.1.0/tool_definitions.json")


def test_the_corpus_plus_the_unmeasured_record_is_the_whole_served_enum():
    """EMPTY from 2026-10-13 to 2026-10-31 (the 15 served at 108 were measured). Since 2026-11-01 the record names the
    24 keys contract 146.0.0 added (tests/test_v146.py): served, known by name only, not in the corpus."""
    c = load()
    # 326 at 146.0.0 (24 unmeasured 2026-11-01 .. 11-02, measured at 146.0.1 on 2026-11-02: _moves_146.json); 302 at
    # 144.0.0 (_moves_144.json); 171 at 108; 177 at 110 (_moves_110.json); 183 at 110.8 (_moves_110_8.json); 226 at
    # 135.2 (_moves_135.json)
    # 532 since the 148.1.0 capture (2026-11-05): the 206 keys v146.5 / .8 / .10 / .11 added, listed by name - the
    # re-extraction at 148.1.0 stopped at its hint step before reaching any of them (RECORD["why"])
    # 532 in the corpus since the refresh at 149.1.0, 2026-11-07 (_moves_149.json); the 206 under history148
    # 534 since 161.0.0 (2026-11-09, _moves_161.json): BB_TOUCH retired, VWMA20 and the two DONCHIAN_BROKEN_*_PRIOR added
    # 2026-11-11, contract 168.3.0 (extraction 20261111): 581 - the 47 keys of _moves_168.json added, none retired, all
    # 47 measured the same day (581 hints), so the record's `metrics` stays empty. SERVED is no longer the stage
    # schema's enum: since 168 that schema names a metric by pattern and the roster is the same capture's read schema
    # (get_strategy outputSchema $defs/metricKey), which omega.condition_vocabulary carries as reportColumn.metric.enum
    moves_168 = json.loads((CONTRACT_DIR / "metrics" / "_moves_168.json").read_text(encoding="utf-8"))
    assert (len(moves_168["added"]), moves_168["retired"]) == (47, []) and set(moves_168["added"]) <= set(SERVED)
    metric = vocabulary()["reportColumn"]["metric"]
    assert metric["pattern"] == "^[A-Z][A-Z0-9_]*$" and metric["enumPointer"] == "/get_strategy/outputSchema/$defs/metricKey"
    assert metric["count"] == len(SERVED) == len(set(SERVED))
    assert set(c.metrics) | set(c.unmeasured_metrics) == set(SERVED) and len(SERVED) == 534 + len(moves_168["added"]) == 581
    assert len(c.metrics) == 581 and RECORD["metrics"] == {} and c.unmeasured_metrics == {}
    assert len(RECORD["history148"]["formerlyUnmeasured"]) == 206
    assert set(RECORD["formerlyUnmeasured"]) == V100 | V101_1 and RECORD["measuredOn"] == "2026-10-13"
    assert len(RECORD["history146"]["formerlyUnmeasured"]) == 24 and RECORD["history146"]["measuredOn"] == "2026-11-02"
    # listed 2026-11-05 at 148.1.0; the record's servedAt follows the served contract (149.1.0 when it was emptied)
    # 2026-11-11, contract 168.3.0: the record was listed again that day - no metric, one chain outer: `spread`, which
    # 168 serves after aggregate / ema / rma / wma and no probe has rendered (tests/test_v148_surface.py,
    # tests/test_v149_surface.py) - so servedAt is 168.3.0 and listedOn 2026-11-11
    assert RECORD["servedAt"] == "168.3.0" and RECORD["listedOn"] == "2026-11-11"
    assert set(RECORD["chainOuters"]) == {"spread"} and RECORD["chainOuters"]["spread"]["servedAt"] == "168.3.0"
    assert RECORD["transformParameters"] == {}
    assert RECORD["history148"]["servedAt"] == "148.1.0"


def test_the_v100_metrics_are_what_the_changelog_says():
    """README v100: "The patterns, gaps and runs compose `value` only, and none of the twelve is ranked"; the price
    sources are "price facts that take every transform a close takes"."""
    c = load()
    for m in PATTERNS_GAPS_RUNS:
        assert set(c.metrics[m].transforms) == {"value"}, m
    for m in V100:
        assert "rank" not in c.metrics[m].transforms, m
    for m in PRICE_SOURCES:
        # 161.0.0 (2026-11-09): the platform removed `distance` from CLOSE (and LAST, DONCHIAN_UPPER/LOWER) but not from
        # the three derived price sources, so they take every transform a close takes, plus distance
        assert set(c.metrics[m].transforms) == set(c.metrics["CLOSE"].transforms) | {"distance"}, m


@pytest.mark.parametrize("metric", sorted(V100 | V101_1))
def test_a_value_column_over_each_now_validates(metric):
    column = Column.model_validate({"metric": metric, "transformId": "value", "timeframe": {"rel": "anchor"}})
    assert [f for f in validate_column(column) if f.severity == "error"] == []


def test_the_changelogs_own_example_validates():
    """README v100: "`HLC3 x aggregate(20)` is the 20-bar SMA of typical price"."""
    report = Report(anchor="1h", sections=[CustomSection(title="T", columns=[
        Column.model_validate({"metric": "HLC3", "transformId": "aggregate", "timeframe": {"rel": "anchor"},
                               "window": 20})])])
    assert validate_report(report).ok


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_every_generated_plan_uses_only_measured_metrics(name):
    report = plan(PRESETS[name]).report
    used = {col.metric for s in report.sections if isinstance(s, CustomSection) for col in s.columns}
    assert used and used <= set(load().metrics)


# --- what the manager's pin-drift check sees -------------------------------------------------------
def _surface(metrics: list[str], sections: set[str]) -> dict:
    axes = {"REPORT": {"type": "object", "properties": {"sections": {"type": "array", "items": {"anyOf": [
        {"type": "object", "properties": {"sectionKey": {"type": "string", "enum": sorted(sections)}}}]}}}}}
    return {"tools": [
        {"name": "get_metric_construction_hints",
         "inputSchema": {"type": "object", "properties": {"metric": {"type": "string", "enum": metrics}}}},
        {"name": "stage_strategy_draft", "inputSchema": {"type": "object", "properties": {"request": {
            "type": "object", "properties": {"axes": {"type": "object", "properties": axes}}}}}}]}


def test_the_served_enum_compares_as_stored_and_the_146_additions_are_unmeasured():
    stored = stored_enums()
    assert stored["metrics"] == set(SERVED)
    result = compare(live_enums(_surface(SERVED, stored["sectionKeys"])), stored, stored_unmeasured())
    assert result["metrics"]["liveNotStored"] == [] and result["metrics"]["storedNotLive"] == []
    assert result["metrics"]["storedUnmeasured"] == sorted(load().unmeasured_metrics)      # [] from 2026-10-13 to 10-31


@pytest.mark.skipif(not SURFACE_104_1.exists(), reason="the battlegrid-manager checkout is not beside this repo")
def test_the_stored_104_1_surface_reports_nothing_missing_and_nothing_unmeasured():
    surface = json.loads(SURFACE_104_1.read_text(encoding="utf-8"))
    result = compare(live_enums(surface), stored_enums(), stored_unmeasured())
    # History since contract 110: the 104.1.0 surface still lists exactly the three keys v110 retired, and nothing else
    # is missing (data/contract/metrics/_moves_110.json).
    # ... plus STOCH_RSI14 (v137) and BB_WIDTH (v138), which the 104.1.0 surface still lists and the 144.0.0 corpus no
    # longer stores (_moves_144.json, 2026-10-30)
    root = Path(__file__).resolve().parents[1]
    retired = {**json.loads((root / "data/contract/metrics/_moves_110.json").read_text(encoding="utf-8"))["retired"],
               **json.loads((root / "data/contract/metrics/_moves_144.json").read_text(encoding="utf-8"))["retired"]}
    # ... plus BB_TOUCH (retired at 161.0.0, 2026-11-09 - _moves_161.json), which the 104.1.0 surface also still lists
    retired = {**retired, **json.loads((root / "data/contract/metrics/_moves_161.json").read_text(encoding="utf-8"))["retired"]}
    assert result["metrics"]["liveNotStored"] == sorted(retired) and result["metrics"]["storedUnmeasured"] == []
