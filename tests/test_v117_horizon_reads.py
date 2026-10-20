"""Contract v117: decided changes read at their horizon bar.

README v117, "Rejected input": "A verdict carrier or hold that reads a change over a horizon above the strategy
timeframe is refused. That is `chg4h` and `chg24h` on a `1h` strategy, and `oiRegime` (the `1h` change) below `1h`.
Such a change is a developing read whatever its selector." Refused `CONDITION_VERDICT_READ_ILLEGAL` or
`CONDITION_HOLD_ILLEGAL`. Until v0.8.3 OMEGA marked a column Developing only for `bars: "all"` above the anchor, so a
carrier on chg24h at a 1h anchor passed offline and was refused at stage.
"""
from __future__ import annotations

import pytest

from omega.conditions import (CHANGE_HORIZON, all_of, condition, num, ref, report_headers,
                              validate_conditions)
from omega.fanout import outputs_for
from omega.types import Column, CustomSection, RelTimeframe, Report

CHANGES = ["CHG_5M", "CHG_15M", "CHG_1H", "CHG_4H", "CHG_24H", "OI_PX_REGIME"]


def _col(metric: str) -> Column:
    return Column(metric=metric, transformId="value", timeframe=RelTimeframe(rel="anchor"))


def _report(anchor: str) -> Report:
    return Report(anchor=anchor, sections=[CustomSection(kind="custom", title="changes", benchmarkTicker=None,
                                                         columns=[_col(m) for m in CHANGES])])


def H(metric: str) -> str:
    """The header the builder emits - never typed (chg4h, oiRegime, ...)."""
    [o] = outputs_for(_col(metric))
    return o.header


def _clause(metric: str, hold=(1, 1)) -> dict:
    if metric == "OI_PX_REGIME":
        from omega.conditions import is_
        return is_(H(metric), "new longs", hold=hold)
    return num(H(metric), "gt", 0, hold=hold)


def _errors(report, conds, code):
    return [f for f in validate_conditions(report, conds) if f.severity == "error" and code in f.message]


def test_the_horizons_are_the_metrics_own():
    assert CHANGE_HORIZON == {"CHG_5M": "5m", "CHG_15M": "15m", "CHG_1H": "1h", "CHG_4H": "4h",
                              "CHG_24H": "1d", "OI_PX_REGIME": "1h"}


@pytest.mark.parametrize("metric,anchor,refused", [
    ("CHG_4H", "1h", True), ("CHG_24H", "1h", True),               # the README's own examples
    ("CHG_1H", "1h", False), ("CHG_15M", "1h", False), ("CHG_5M", "1h", False),
    ("OI_PX_REGIME", "15m", True), ("OI_PX_REGIME", "5m", True),   # "oiRegime (the 1h change) below 1h"
    ("OI_PX_REGIME", "1h", False), ("OI_PX_REGIME", "4h", False),
    ("CHG_24H", "4h", True), ("CHG_4H", "4h", False), ("CHG_15M", "5m", True), ("CHG_5M", "5m", False),
])
def test_a_verdict_carrier_reading_a_horizon_above_the_anchor_is_refused(metric, anchor, refused):
    report = _report(anchor)
    conds = [condition("C_UP", "carrier", _clause(metric), verdict="UP")]
    errors = _errors(report, conds, "CONDITION_VERDICT_READ_ILLEGAL")
    assert bool(errors) is refused
    assert bool(report_headers(report)[H(metric)]["horizon_above"]) is refused
    if refused:
        msg = errors[0].message
        assert "v117" in msg and H(metric) in msg and "'C_UP'" in msg
        assert "at or below the strategy timeframe" in msg          # the remedy the platform names


def test_the_selector_does_not_rescue_it():
    """"whatever its selector": a Confirmed (closed) column is refused the same."""
    report = Report(anchor="1h", sections=[CustomSection(kind="custom", title="c", benchmarkTicker=None, columns=[
        Column(metric="CHG_4H", transformId="value", timeframe=RelTimeframe(rel="anchor"), bars="closed")])])
    conds = [condition("C_UP", "carrier", num(H("CHG_4H"), "gt", 0), verdict="UP")]
    assert _errors(report, conds, "CONDITION_VERDICT_READ_ILLEGAL")


def test_a_building_block_does_not_launder_it():
    """The carrier rule is over the closure: a conditionRef to a block that reads chg24h is still refused."""
    report = _report("1h")
    conds = [condition("BLOCK", "block", _clause("CHG_24H"), verdict=None),
             condition("C_UP", "carrier", all_of(ref("BLOCK"), _clause("CHG_1H")), verdict="UP")]
    errors = _errors(report, conds, "CONDITION_VERDICT_READ_ILLEGAL")
    assert len(errors) == 1 and errors[0].condition_key == "C_UP" and "(in BLOCK)" in errors[0].path


def test_a_non_carrier_read_at_one_bar_is_legal():
    """The rule names verdict carriers and holds; a building block read once is neither."""
    report = _report("1h")
    conds = [condition("BLOCK", "block", _clause("CHG_24H"), verdict=None)]
    assert not [f for f in validate_conditions(report, conds) if f.severity == "error"]


@pytest.mark.parametrize("hold_on", ["clause", "group"])
def test_a_hold_over_a_horizon_above_the_anchor_is_an_error(hold_on):
    """Before v117 OMEGA only warned on this hold; the README names the refusal, so it is an error now."""
    report = _report("1h")
    if hold_on == "clause":
        defn = _clause("CHG_4H", hold=(2, 3))
    else:
        defn = all_of(_clause("CHG_4H"), _clause("CHG_1H"), hold=(2, 3))
    conds = [condition("BLOCK", "block", defn, verdict=None)]
    errors = _errors(report, conds, "CONDITION_HOLD_ILLEGAL")
    assert errors and "v117" in errors[0].message and "over 3 bars" in errors[0].message


def test_a_hold_over_a_horizon_at_the_anchor_is_not_a_v117_error():
    report = _report("1h")
    conds = [condition("BLOCK", "block", _clause("CHG_1H", hold=(2, 3)), verdict=None)]
    assert not [f for f in validate_conditions(report, conds) if "v117" in f.message]


def test_no_preset_reads_a_horizon_above_its_anchor():
    from omega.generate import PRESETS, plan
    for name, thesis in PRESETS.items():
        p = plan(thesis)
        assert not [f for f in p.condition_findings() if "v117" in f.message], name
