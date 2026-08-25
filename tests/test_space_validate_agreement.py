"""Every shape the enumerator produces must be one the validator accepts.

This invariant was never checked, and it was false in two ways:

  1. A `rank` atom's structural shape carried no ordering, so it defaulted to "hi".
     CLOSE_CHANGE offers only ['far', 'near'], so `enumerate_shapes()` emitted a shape
     `validate_column` refuses - "ranked column 'closeChg' does not offer the 'hi'
     ordering".
  2. Chaining `spread -> rank` narrows the legal operand set: the contract publishes
     `rankableSpreadOperands`, and for EMA5 that is ['EMA13'] alone - "Raw price-unit
     metrics never rank - rank the composition, not the level." The enumerator paired
     the chain with all 16 of spread's operands x 4 orderings, emitting 64 shapes the
     validator refuses.

Both inflated the published shape counts. The contract knew the rules and the validator
enforced them; only the enumerator disagreed.

Placeholder shapes are exempt: an unexpanded `spread` has no operand and the nearestZone
family has no `side`, so both are incomplete-by-design rather than illegal, and their
OPERAND_REQUIRED / SIDE_REQUIRED findings are expected.
"""
from __future__ import annotations

from collections import Counter

import pytest

from omega import contract as C
from omega.space import enumerate_shapes
from omega.validate import validate_column
from scripts.render_coverage import is_placeholder

# A placeholder spread CHAINED to rank also trips the rankable-operand check, because
# "no operand yet" is not in rankableSpreadOperands either. Same incompleteness, third
# code - not a third defect.
EXPECTED_PLACEHOLDER_CODES = {"OPERAND_REQUIRED", "SIDE_REQUIRED",
                              "REPORT_COLUMN_CHAIN_UNSUPPORTED"}


@pytest.fixture(scope="module")
def contract():
    return C.load()


def _errors(shape, contract):
    return [f for f in validate_column(shape.to_column(), section_timeframe=None,
                                       path="s", contract=contract)
            if f.severity == "error"]


@pytest.mark.parametrize("expand", [False, True])
def test_every_enumerated_shape_validates(expand, contract):
    offenders = []
    for shape in enumerate_shapes(expand_operands=expand, contract=contract):
        if is_placeholder(shape):
            continue
        errs = _errors(shape, contract)
        if errs:
            offenders.append(
                f"{shape.metric} x {shape.transform}"
                f"{' x ' + shape.chained if shape.chained else ''} "
                f"operand={shape.operand} ordering={shape.ordering}: "
                f"{errs[0].code} - {errs[0].message}")
    assert not offenders, (
        f"{len(offenders)} enumerated shapes are refused by omega's own validator:\n"
        + "\n".join(offenders[:8]))


@pytest.mark.parametrize("expand", [False, True])
def test_placeholders_only_fail_for_the_expected_reason(expand, contract):
    """A placeholder may fail OPERAND_REQUIRED/SIDE_REQUIRED and nothing else - otherwise
    the exemption is hiding a real defect."""
    unexpected = Counter()
    for shape in enumerate_shapes(expand_operands=expand, contract=contract):
        if not is_placeholder(shape):
            continue
        for f in _errors(shape, contract):
            if f.code not in EXPECTED_PLACEHOLDER_CODES:
                unexpected[f"{shape.metric} x {shape.transform}: {f.code}"] += 1
    assert not unexpected, dict(unexpected)


def test_close_change_rank_does_not_offer_hi(contract):
    """Bug 1's root fact, pinned so the enumerator fix stays justified."""
    assert tuple(contract.metric("CLOSE_CHANGE").rank_orderings) == ("far", "near")


def test_chained_rank_narrows_spread_operands(contract):
    """Bug 2's root fact. rankableSpreadOperands is the field the enumerator must honour."""
    spec = contract.metric("EMA5").transforms["spread"]
    assert spec.get("rankableSpreadOperands") == ["EMA13"]
    assert len(contract.metric("EMA5").spread_operands) > 1, (
        "spread offers many operands; only the rankable subset may chain to rank")
