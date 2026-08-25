"""BG-13: offset is silently ignored by candle-backed categorical metrics.

Found while chasing the unobserved labels. I had written that they "need market
conditions, not effort" and that "more anchors will not produce them" - the anchor half
measured, the rest asserted. The platform's own error message on a refused timeframe
named the parameter I had not tried:

    "allowedDomain": { "candidates": ["offset"] }

offset walks backwards through bars, which reaches past market states without waiting for
another day. It works - for numeric metrics. For categorical ones it is accepted, spends
columnLookback budget, and returns the value for NOW.

The proof is arithmetic rather than a coincidence of stable labels. AMD at offset 8:
close $460.95 between swingLo $451.62 and swingHi $477.94 - 35% of range - and PRICE_ZONE
answers "near high". All three inputs moved under offset in the same render; only the
classification did not.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega import contract as C
from omega.types import Column
from omega.validate import validate_column

AUDIT = Path(__file__).resolve().parents[1] / "data/audit/offset_ignored.json"


@pytest.fixture(scope="module")
def contract():
    return C.load()


def _findings(metric, offset, contract):
    col = Column.model_validate({"metric": metric, "transformId": "value",
                                 "timeframe": {"rel": "anchor"}, "offset": offset})
    return validate_column(col, section_timeframe=None, path="s", contract=contract)


@pytest.mark.parametrize("metric", ["MA_ALIGN", "BB_TOUCH", "EMA_CROSS", "PRICE_ZONE"])
def test_offset_on_a_candle_categorical_metric_warns(metric, contract):
    codes = [f.code for f in _findings(metric, 8, contract)]
    assert "OFFSET_IGNORED" in codes, f"{metric} accepts a no-op offset without warning"


@pytest.mark.parametrize("metric", ["CLOSE", "ADX", "SWING_HIGH", "STOCH_K", "MFI14"])
def test_offset_on_a_numeric_metric_is_fine(metric, contract):
    """These genuinely honour offset - measured. Warning on them would be noise."""
    assert not contract.metric(metric).vocab
    codes = [f.code for f in _findings(metric, 8, contract)]
    assert "OFFSET_IGNORED" not in codes


def test_no_warning_without_an_offset(contract):
    codes = [f.code for f in _findings("PRICE_ZONE", 0, contract)]
    assert "OFFSET_IGNORED" not in codes


def test_the_warning_does_not_block(contract):
    """It is a warning, not an error - the column DOES render, it just lies about when."""
    errors = [f for f in _findings("PRICE_ZONE", 8, contract) if f.severity == "error"]
    assert not errors


def test_the_affected_set_is_exactly_the_candle_categoricals(contract):
    affected = sorted(n for n in contract.metrics
                      if contract.metric(n).timeframe_mode == "candle"
                      and contract.metric(n).vocab)
    assert affected == ["BAR_FORMING", "BB_TOUCH", "EMA_CROSS", "MA_ALIGN", "PRICE_ZONE"]
    rec = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert rec["scope"]["candleCategoricalMetrics"] == affected
    assert rec["scope"]["untested"] == ["BAR_FORMING"], (
        "BAR_FORMING was never rendered at an offset; it must stay listed as untested "
        "rather than quietly folded into the measured set")


def test_the_proof_is_arithmetic_not_coincidence():
    """Identical values alone would not prove anything - the label could just be stable.
    What proves it is that PRICE_ZONE's own inputs moved and the classification did not."""
    rec = json.loads(AUDIT.read_text(encoding="utf-8"))["theProof"]
    for coin in ("AMD", "EWY"):
        o0, o8 = rec[coin]["offset0"], rec[coin]["offset8"]
        assert o0["close"] != o8["close"], f"{coin}: close must move under offset"
        assert o0["zone"] == o8["zone"], f"{coin}: zone must NOT move - that is the bug"
        pos = (o8["close"] - o8["swingLo"]) / (o8["swingHi"] - o8["swingLo"])
        assert pos < 0.5, (
            f"{coin}: at offset 8 the close sits at {pos:.0%} of range, so 'near high' "
            f"cannot be the honest answer")
