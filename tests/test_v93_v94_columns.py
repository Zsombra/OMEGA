"""Two column rules the builder enforces behind unchanged schemas (vendor README, pack 31.2.77):

- v93: "A custom column { transformId: "trajectory", window: 1 }, plain or as the chained
  outer of distance x trajectory, for any metric" is refused (REPORT_COLUMN_CONSTRUCTION_FAILED):
  a window of one compared a reading with itself and read `flat` everywhere.
- v94: "A value column over a timeless metric ... with offset above 0 is refused at
  construction" - a timeless metric has no earlier bar.
"""
from __future__ import annotations

import pytest

from omega import contract as C
from omega.types import Column
from omega.validate import validate_column


@pytest.fixture(scope="module")
def contract():
    return C.load()


def _errors(spec, contract):
    col = Column.model_validate(spec)
    return [f for f in validate_column(col, section_timeframe=None, path="s", contract=contract)
            if f.severity == "error"]


@pytest.mark.parametrize("spec", [
    {"metric": "RSI14", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 1},
    {"metric": "SMA20", "transformId": "distance", "chainedTransformId": "trajectory",
     "timeframe": {"rel": "anchor"}, "window": 1},
])
def test_a_trajectory_window_of_one_is_refused(spec, contract):
    codes = [f.code for f in _errors(spec, contract)]
    assert "TRAJECTORY_WINDOW_BELOW_TWO" in codes


@pytest.mark.parametrize("window", [None, 2, 4])
def test_a_trajectory_of_two_or_more_or_the_default_window_is_not(window, contract):
    spec = {"metric": "RSI14", "transformId": "trajectory", "timeframe": {"rel": "anchor"}}
    if window is not None:
        spec["window"] = window
    assert "TRAJECTORY_WINDOW_BELOW_TWO" not in [f.code for f in _errors(spec, contract)]


def test_an_offset_on_a_timeless_value_column_is_refused(contract):
    timeless = sorted(n for n in contract.metrics if contract.metric(n).is_timeless)
    assert timeless, "the contract names timeless metrics (funding, regime, prior-session levels)"
    spec = {"metric": timeless[0], "transformId": "value", "timeframe": {"rel": "anchor"}, "offset": 2}
    assert "TIMELESS_OFFSET_REFUSED" in [f.code for f in _errors(spec, contract)]


def test_an_offset_on_a_candle_value_column_is_not(contract):
    spec = {"metric": "CLOSE", "transformId": "value", "timeframe": {"rel": "anchor"}, "offset": 2}
    assert "TIMELESS_OFFSET_REFUSED" not in [f.code for f in _errors(spec, contract)]
