"""A timeframe-inert metric accepts only the literal {"rel": "anchor"} column timeframe.

omega enforced the timeless rule at section level only (a section carrying a `timeframe`
override). The column's own timeframe went unchecked, so omega accepted three shapes the
platform refuses. All four probes ran live against REGIME_MOM at a 1h anchor - see
data/audit/timeless_column_timeframe.json.

The abs-equal-to-anchor case is the one that fixes the rule's shape: {"abs": "1h"} under a
1h anchor resolves to the very same timeframe and is STILL refused. The constraint is
syntactic. A validator inferred from the 'regime' message alone would pass it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega import contract as C
from omega.types import Column
from omega.validate import validate_column

AUDIT = Path(__file__).resolve().parents[1] / "data/audit/timeless_column_timeframe.json"


@pytest.fixture(scope="module")
def contract():
    return C.load()


def _findings(metric, timeframe, contract, section_timeframe=None):
    col = Column.model_validate(
        {"metric": metric, "transformId": "value", "timeframe": timeframe})
    return validate_column(col, section_timeframe=section_timeframe,
                           path="s.columns[0]", contract=contract)


@pytest.mark.parametrize("timeframe", [
    {"rel": "lower"},
    {"rel": "regime"},
    {"abs": "4h"},
    {"abs": "1h"},            # equals the anchor and is still refused
])
def test_timeless_metric_rejects_non_anchor_column_timeframe(timeframe, contract):
    codes = [f.code for f in _findings("REGIME_MOM", timeframe, contract)]
    assert "REPORT_COLUMN_CONSTRUCTION_FAILED" in codes, (
        f"omega accepted timeframe={timeframe} on a timeless metric; "
        f"the platform refuses it")


def test_timeless_metric_accepts_the_anchor_reference(contract):
    assert _findings("REGIME_MOM", {"rel": "anchor"}, contract) == []


def test_candle_metric_still_accepts_every_relative_timeframe(contract):
    """The new check must not leak onto candle-grid metrics."""
    assert not contract.metric("RSI14").is_timeless
    for rel in ("anchor", "lower", "regime"):
        assert _findings("RSI14", {"rel": rel}, contract) == [], rel


def test_every_timeless_metric_is_covered(contract):
    """Not just REGIME_MOM - the rule is a property of timeframeMode."""
    timeless = [n for n in contract.metrics if contract.metric(n).is_timeless]
    assert len(timeless) == 40
    for name in timeless:
        codes = [f.code for f in _findings(name, {"rel": "regime"}, contract)]
        assert "REPORT_COLUMN_CONSTRUCTION_FAILED" in codes, name


def test_audit_record_matches_the_contract(contract):
    """The recorded metric list is regenerated from the contract, not hand-kept."""
    rec = json.loads(AUDIT.read_text(encoding="utf-8"))
    timeless = sorted(n for n in contract.metrics if contract.metric(n).is_timeless)
    assert rec["affectedMetrics"]["metrics"] == timeless
    assert rec["affectedMetrics"]["count"] == len(timeless)
    # the deciding probe must stay in the record - it is what makes the rule syntactic
    abs_anchor = [p for p in rec["probes"] if p["timeframe"].get("abs") == "1h"]
    assert abs_anchor and abs_anchor[0]["result"] == "REJECTED"
