"""The metric-declared absolute anchor, and exactly how far the measurement goes.

PDH, PDL and the seven pivots published `anchor: "1d"` from contract 54.1.0 through
56.1.0. Probed live 2026-09-09 on PIVOT_P with get_strategy_column_contract: relative
references and {abs: "1d"} are ACCEPTED, {abs: "4h"} is REFUSED. So the anchor bound
PINNED references only. Record: data/audit/metric_anchor_rule_2026-09-09.json.

CONTRACT 61.2.0: those same nine metrics went timeframeMode candle -> timeless, and the
`anchor` field disappeared from all nine metric records along with it - re-derived from
the corpus: zero metrics in data/contract/metrics/*.json now carry an `anchor` key.
`omega/validate.py`'s metric-anchor rule is gated on `m.anchor and not m.is_timeless`,
which is therefore false for every metric in the current corpus - the
METRIC_ANCHOR_MISMATCH / METRIC_ANCHOR_RELATIVE_UNVERIFIED code paths are unreachable
dead code now (reported, not silently removed - see the task report). The nine metrics
are governed instead by the general timeless-column-timeframe rule (see
tests/test_timeless_timeframe.py): only {"rel": "anchor"} passes; every absolute
timeframe (including the former anchor "1d") and every other relative reference is
refused with REPORT_COLUMN_CONSTRUCTION_FAILED. The tests below are re-derived to state
that, rather than being left asserting a rule that no longer has any live subject.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.contract import load
from omega.types import Column
from omega.validate import validate_column

AUDIT = Path(__file__).resolve().parents[1] / "data/audit/metric_anchor_rule_2026-09-09.json"

# The nine metrics that declared a metric-level anchor at 54.1.0. Kept as a named
# constant for the tests below even though NONE of them declare an anchor any more -
# they are the real, still-existing subject of "what happened to the anchor rule".
FORMER_ANCHOR_METRICS = ["PDH", "PDL", "PIVOT_P", "PIVOT_R1", "PIVOT_R2", "PIVOT_R3",
                         "PIVOT_S1", "PIVOT_S2", "PIVOT_S3"]


@pytest.fixture(scope="module")
def contract():
    return load()


def _codes(metric, timeframe, contract):
    col = Column.model_validate({"metric": metric, "transformId": "value",
                                 "timeframe": timeframe})
    return [(f.severity, f.code) for f in
            validate_column(col, path="c", contract=contract)]


def test_the_anchored_metrics_are_exactly_the_ones_declaring_an_anchor(contract):
    """Re-derived from the corpus: zero metrics declare `anchor` at 61.2.0. PDH, PDL and
    the seven pivots lost it when they moved from candle to timeless timeframeMode -
    the same nine metrics FORMER_ANCHOR_METRICS names, not a different set."""
    declared = sorted(n for n in contract.metrics if contract.metric(n).anchor)
    assert declared == []
    assert {contract.metric(n).anchor for n in declared} == set()
    assert all(contract.metric(n).is_timeless for n in FORMER_ANCHOR_METRICS)


@pytest.mark.parametrize("metric", FORMER_ANCHOR_METRICS)
def test_a_mismatched_absolute_timeframe_is_an_error(metric, contract):
    """At 54.1.0 {abs: "4h"} against an anchor of "1d" failed METRIC_ANCHOR_MISMATCH.
    That code is unreachable now (m.anchor is None). The column still errors, but under
    the general timeless-column-timeframe rule instead, because these nine are timeless
    at 61.2.0: an absolute timeframe is not the literal {"rel": "anchor"} reference."""
    codes = _codes(metric, {"abs": "4h"}, contract)
    assert ("error", "METRIC_ANCHOR_MISMATCH") not in codes
    assert ("error", "REPORT_COLUMN_CONSTRUCTION_FAILED") in codes


@pytest.mark.parametrize("metric", FORMER_ANCHOR_METRICS)
def test_the_declared_anchor_is_clean(metric, contract):
    """At 54.1.0 {abs: "1d"} - the declared anchor - was clean (no error). At 61.2.0 the
    metric is timeless, and an absolute timeframe is refused even when it equals the
    former anchor value - the same syntactic trap test_timeless_timeframe.py's
    `abs: "1h"` probe already established for REGIME_MOM. Only the literal
    {"rel": "anchor"} reference is clean now."""
    codes = _codes(metric, {"abs": "1d"}, contract)
    assert [c for s, c in codes if s == "error"] == ["REPORT_COLUMN_CONSTRUCTION_FAILED"]
    clean = _codes(metric, {"rel": "anchor"}, contract)
    assert not [c for s, c in clean if s == "error"], clean


def test_a_relative_reference_warns_but_does_not_error(contract):
    """At 54.1.0 PIVOT_P (candle, anchor "1d") accepted {"rel": "lower"|"regime"} with a
    METRIC_ANCHOR_RELATIVE_UNVERIFIED warning and no error. At 61.2.0 PIVOT_P is
    timeless and anchor-less: the general timeless rule now REFUSES both outright, and
    the warning code is unreachable for this metric (m.anchor is None). Only
    {"rel": "anchor"} is accepted, matching every other timeless metric."""
    for tf in ({"rel": "lower"}, {"rel": "regime"}):
        codes = _codes("PIVOT_P", tf, contract)
        assert ("error", "REPORT_COLUMN_CONSTRUCTION_FAILED") in codes, (tf, codes)
        assert ("warning", "METRIC_ANCHOR_RELATIVE_UNVERIFIED") not in codes, (tf, codes)
    assert _codes("PIVOT_P", {"rel": "anchor"}, contract) == []


def test_the_rule_matches_the_recorded_probe():
    """Unchanged: this is a record of what the live platform did on 2026-09-09, when
    PIVOT_P was still a candle metric declaring anchor "1d". History, not re-derived."""
    rec = json.loads(AUDIT.read_text(encoding="utf-8"))
    by_tf = {json.dumps(r["timeframe"], sort_keys=True): r["verdict"] for r in rec["results"]}
    assert by_tf[json.dumps({"abs": "4h"}, sort_keys=True)] == "REFUSED"
    assert by_tf[json.dumps({"abs": "1d"}, sort_keys=True)] == "ACCEPTED"
    assert by_tf[json.dumps({"rel": "anchor"}, sort_keys=True)] == "ACCEPTED"
    assert "STRICTER" in rec["_discrepancy"]
