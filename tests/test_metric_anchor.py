"""The metric-declared absolute anchor, and exactly how far the measurement goes.

PDH, PDL and the seven pivots publish `anchor: "1d"` from contract 54.1.0. Probed live
2026-09-09 on PIVOT_P with get_strategy_column_contract: relative references and
{abs: "1d"} are ACCEPTED, {abs: "4h"} is REFUSED. So the anchor binds PINNED references
only. Record: data/audit/metric_anchor_rule_2026-09-09.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.contract import load
from omega.types import Column
from omega.validate import validate_column

AUDIT = Path(__file__).resolve().parents[1] / "data/audit/metric_anchor_rule_2026-09-09.json"
ANCHORED = ["PDH", "PDL", "PIVOT_P", "PIVOT_R1", "PIVOT_R2", "PIVOT_R3",
            "PIVOT_S1", "PIVOT_S2", "PIVOT_S3"]


@pytest.fixture(scope="module")
def contract():
    return load()


def _codes(metric, timeframe, contract):
    col = Column.model_validate({"metric": metric, "transformId": "value",
                                 "timeframe": timeframe})
    return [(f.severity, f.code) for f in
            validate_column(col, section_timeframe=None, path="c", contract=contract)]


def test_the_anchored_metrics_are_exactly_the_ones_declaring_an_anchor(contract):
    declared = sorted(n for n in contract.metrics if contract.metric(n).anchor)
    assert declared == sorted(ANCHORED)
    assert {contract.metric(n).anchor for n in declared} == {"1d"}


@pytest.mark.parametrize("metric", ANCHORED)
def test_a_mismatched_absolute_timeframe_is_an_error(metric, contract):
    assert ("error", "METRIC_ANCHOR_MISMATCH") in _codes(metric, {"abs": "4h"}, contract)


@pytest.mark.parametrize("metric", ANCHORED)
def test_the_declared_anchor_is_clean(metric, contract):
    codes = _codes(metric, {"abs": "1d"}, contract)
    assert not [c for s, c in codes if s == "error"], codes


def test_a_relative_reference_warns_but_does_not_error(contract):
    """The column contract ACCEPTS a relative reference - measured. The vendor's authoring
    skill claims the SAVE path accepts only {abs: <anchor>}, which is stricter and was not
    probed, because probing it needs a compile that parks a plan server-side. omega refuses
    to turn an unverified vendor claim into an error, and refuses to stay silent about it."""
    for tf in ({"rel": "anchor"}, {"rel": "lower"}, {"rel": "regime"}):
        codes = _codes("PIVOT_P", tf, contract)
        assert not [c for s, c in codes if s == "error"], (tf, codes)
        assert ("warning", "METRIC_ANCHOR_RELATIVE_UNVERIFIED") in codes, (tf, codes)


def test_the_rule_matches_the_recorded_probe():
    rec = json.loads(AUDIT.read_text(encoding="utf-8"))
    by_tf = {json.dumps(r["timeframe"], sort_keys=True): r["verdict"] for r in rec["results"]}
    assert by_tf[json.dumps({"abs": "4h"}, sort_keys=True)] == "REFUSED"
    assert by_tf[json.dumps({"abs": "1d"}, sort_keys=True)] == "ACCEPTED"
    assert by_tf[json.dumps({"rel": "anchor"}, sort_keys=True)] == "ACCEPTED"
    assert "STRICTER" in rec["_discrepancy"]
