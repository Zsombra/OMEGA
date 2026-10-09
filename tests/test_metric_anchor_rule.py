"""The metric-anchor rule: measured at 54.1.0, unreachable at 61.2.0, kept and covered.

At contract 54.1.0 the platform declared an absolute anchor on nine metrics - PDH, PDL and
the seven pivots, all "1d". Measured live 2026-09-09 on PIVOT_P: relative references and
{abs: "1d"} are accepted, {abs: "4h"} is refused ("metric 'pivotP' is anchored to '1d' - it
accepts only that absolute timeframe reference"). `validate_column` enforces that rule
(`omega/validate.py`, METRIC_ANCHOR_MISMATCH / METRIC_ANCHOR_RELATIVE_UNVERIFIED).

By the 61.2.0 re-extraction those nine went TIMELESS and lost their declared anchor, so no
catalogued metric satisfies the block's condition any more - `m.anchor and not m.is_timeless`
is false for all 156. The 09-20 session record flagged the block as dead code.

It is kept rather than deleted, because it encodes a measured platform rule that has been
live before and can return; deleting it would mean re-discovering it from a refusal. What
this file adds is the two things dead code otherwise lacks:

1. the dead-ness is ASSERTED, so if the platform ever re-declares an anchor the invariant
   test fails loudly and a human re-verifies the branch against the live contract, instead
   of the rule silently starting to fire again;
2. the branch is EXERCISED against a synthetic anchored metric, so it is covered and correct
   on the day it goes live again, rather than untested for however long it stays unreachable.
"""
import dataclasses

import pytest

from omega.contract import load
from omega.types import Column
from omega.validate import validate_column

ANCHORED = "PIVOT_P"          # anchored to "1d" at 54.1.0; timeless since 61.x
ANCHOR = "1d"


@pytest.fixture(scope="module")
def contract():
    return load()


# --- the invariant: this is WHY the block is unreachable today ------------------------------

def test_no_catalogued_metric_declares_an_anchor_while_not_timeless(contract):
    """The block's exact condition, over the whole live catalogue.

    If this fails, the platform has re-declared an anchor. That is not a bug in this test:
    re-verify METRIC_ANCHOR_MISMATCH against the live contract (the 09-09 probe in
    data/audit/metric_anchor_rule_2026-09-09.json is the shape to repeat) and then update
    this test to name the metrics that carry one."""
    live = [m.metric for m in (contract.metric(n) for n in contract.metrics)
            if m.anchor and not m.is_timeless]
    assert live == [], (
        f"{len(live)} metric(s) now declare an anchor while not timeless: {live}. "
        "The METRIC_ANCHOR_MISMATCH branch in omega/validate.py is live again - re-verify it.")


def test_the_nine_metrics_that_once_carried_an_anchor_are_now_timeless_and_carry_none(contract):
    """PDH, PDL and the seven pivots: the exact set that was anchored to "1d" at 54.1.0."""
    once_anchored = ["PDH", "PDL", "PIVOT_P", "PIVOT_R1", "PIVOT_R2", "PIVOT_R3",
                     "PIVOT_S1", "PIVOT_S2", "PIVOT_S3"]
    for name in once_anchored:
        m = contract.metric(name)
        assert m.anchor is None, f"{name} declares anchor {m.anchor!r} again"
        assert m.is_timeless, f"{name} is no longer timeless"


# --- the branch itself, exercised against a synthetic anchored metric -----------------------

def _anchored(contract, name=ANCHORED, anchor=ANCHOR):
    """The catalogued metric as it WAS at 54.1.0: same record, anchor restored, not timeless."""
    m = contract.metric(name)
    return dataclasses.replace(m, anchor=anchor, timeframe_mode="anchored")


def _contract_with(contract, metric):
    """`contract` with one metric record swapped. Contract is a frozen dataclass, so this
    replaces the metrics mapping rather than mutating it - no monkeypatching of a frozen
    instance, and every other rule in validate_column still runs against the real catalogue."""
    return dataclasses.replace(contract, metrics={**contract.metrics, metric.metric: metric})


def _codes(contract, metric, timeframe):
    col = Column(metric=metric.metric, transformId="value", timeframe=timeframe)
    return [f.code for f in validate_column(col, contract=_contract_with(contract, metric))]


def test_an_absolute_timeframe_other_than_the_anchor_is_an_error(contract):
    assert "METRIC_ANCHOR_MISMATCH" in _codes(contract, _anchored(contract), {"abs": "4h"})


def test_the_anchor_itself_is_accepted(contract):
    codes = _codes(contract, _anchored(contract), {"abs": ANCHOR})
    assert "METRIC_ANCHOR_MISMATCH" not in codes
    assert "METRIC_ANCHOR_RELATIVE_UNVERIFIED" not in codes


def test_a_relative_reference_warns_that_the_save_path_is_unmeasured(contract):
    m = _anchored(contract)
    col = Column(metric=m.metric, transformId="value", timeframe={"rel": "anchor"})
    findings = validate_column(col, contract=_contract_with(contract, m))
    warning = [f for f in findings if f.code == "METRIC_ANCHOR_RELATIVE_UNVERIFIED"]
    assert len(warning) == 1
    assert warning[0].severity == "warning", "the save path is unmeasured, so not an error"


def test_a_timeless_metric_with_an_anchor_does_not_reach_the_rule(contract):
    """`not m.is_timeless` is load-bearing: the 61.x metrics are timeless, and a timeless
    metric's timeframe is governed by the literal {"rel": "anchor"} rule instead."""
    m = dataclasses.replace(contract.metric(ANCHORED), anchor=ANCHOR, timeframe_mode="timeless")
    assert "METRIC_ANCHOR_MISMATCH" not in _codes(contract, m, {"abs": "4h"})
