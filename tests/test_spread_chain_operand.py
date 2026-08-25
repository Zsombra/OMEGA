"""A spread chained into a series-building transform needs a candle-backed operand.

The contract does NOT publish this rule. It was found by rendering: batch 5 of the spread
sweep was refused at ATR x spread(SPOT_CVD) -> aggregate, after 544 pairs had already
passed clean.

    [column-grammar] transform 'spread' cannot be chained into 'aggregate': 'spotCVD'
    resolves from the bundle and has no per-bar value, so the relation is a single scalar
    with no series to build

Probed on both axes before being encoded - three different timeless operands (a flow
metric, a price read, a published change) against one chain, then one operand across all
three chains, each render carrying a candle-operand control that passed. See
data/audit/spread_chain_operand.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega import contract as C
from omega.space import enumerate_shapes
from omega.types import Column
from omega.validate import SERIES_CHAINS, validate_column

AUDIT = Path(__file__).resolve().parents[1] / "data/audit/spread_chain_operand.json"


@pytest.fixture(scope="module")
def contract():
    return C.load()


def _errors(base, operand, chained, contract):
    col = Column.model_validate({
        "metric": base, "transformId": "spread", "timeframe": {"rel": "anchor"},
        "chainedTransformId": chained, "inputs": [{"metric": operand}]})
    return [f.code for f in validate_column(col, section_timeframe=None, path="s",
                                            contract=contract) if f.severity == "error"]


@pytest.mark.parametrize("base,operand", [
    ("ATR", "SPOT_CVD"),        # flow metric - the case that surfaced it
    ("CLOSE", "MARK"),          # price read - proves it is not about CVD
    ("ATR_PCT", "CHG_24H"),     # published change - a third kind
])
@pytest.mark.parametrize("chained", sorted(SERIES_CHAINS))
def test_timeless_operand_cannot_feed_a_series_chain(base, operand, chained, contract):
    assert contract.metric(operand).is_timeless
    assert "REPORT_COLUMN_CHAIN_UNSUPPORTED" in _errors(base, operand, chained, contract)


@pytest.mark.parametrize("chained", sorted(SERIES_CHAINS))
def test_candle_operand_still_feeds_a_series_chain(chained, contract):
    """The control that passed in every probe. Without it the rule could be 'spread
    never chains', which is false and would delete 770 legal shapes."""
    assert not contract.metric("RSI14").is_timeless
    assert _errors("ADX", "RSI14", chained, contract) == []


def test_rank_is_not_caught_by_this_rule(contract):
    """rank reduces to an ordinal rather than building a series, and is restricted by
    the contract's own rankableSpreadOperands instead. EMA13 is candle-backed and is the
    single rankable operand for EMA5 x spread."""
    assert _errors("EMA5", "EMA13", "rank", contract) == []


def test_the_enumerator_no_longer_produces_them(contract):
    offenders = [s for s in enumerate_shapes(expand_operands=True, contract=contract)
                 if s.transform == "spread" and s.chained in SERIES_CHAINS
                 and s.operand and contract.metric(s.operand).is_timeless]
    assert not offenders, f"{len(offenders)} refused shapes still enumerated"


def test_expanded_space_shrank_by_exactly_the_measured_count(contract):
    rec = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert rec["scope"]["enumeratedShapesRefused"] == 357
    assert rec["scope"]["expandedSpace"] == {"before": 2136, "after": 1779}
    assert len(enumerate_shapes(expand_operands=True, contract=contract)) == 1779


def test_structural_space_is_untouched(contract):
    """A structural spread shape carries no operand, so the rule cannot bite there."""
    assert len(enumerate_shapes(contract=contract)) == 488
