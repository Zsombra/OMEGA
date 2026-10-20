"""The header token at contract 109: <code>[_ltf|_htf|_<abs>][_dev][_o<N>], then the transform's suffix.

Measured 2026-10-13 with two read-only previews (data/contract/columns/header_tokens_2026-10-13.json, 42 headers over 24
columns in every transform). The vendor pack 31.2.98 states the same rule (strategy-examples: "The code carries its
tokens in this order: `<code>[_<tf>][_dev][_o<N>]`, then the transform's suffix"). Until this date omega.fanout dropped
a pinned timeframe, an offset and a stored Developing selector from the header, so a condition naming
`RSI14_1d`, `RSI7_o1` or `ADX_dev_t2` was typed against a header omega said did not exist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.fanout import outputs_for
from omega.types import Column
from tests.moves_123 import header_at_123

ROOT = Path(__file__).resolve().parents[1]
REC = json.loads((ROOT / "data/contract/columns/header_tokens_2026-10-13.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", REC["cases"], ids=[f"probe{i + 1}" for i in range(len(REC["cases"]))])
def test_every_measured_header_is_predicted_exactly(case):
    columns = case["request"]["source"]["sections"][0]["columns"]
    predicted = [o.header for c in columns for o in outputs_for(Column.model_validate(c))]
    # measured before v123: the same columns render under today's codes (`ADX_dev_t2` -> `ADX14_dev_t2`)
    assert predicted == [header_at_123(h) for h in case["headers"]]


def test_the_token_order_on_one_column():
    col = Column.model_validate({"metric": "RSI2", "transformId": "value", "timeframe": {"abs": "1d"}, "offset": 1})
    assert [o.header for o in outputs_for(col)] == ["RSI2_1d_o1"]
    dev = Column.model_validate({"metric": "ADX", "transformId": "trajectory", "timeframe": {"rel": "anchor"},
                                 "window": 3, "bars": "all"})
    assert [o.header for o in outputs_for(dev)][-1] == "ADX14_dev_trend"            # v123: the code is ADX14
    closed = dev.model_copy(update={"bars": "closed"})               # Confirmed adds no token
    assert [o.header for o in outputs_for(closed)][-1] == "ADX14_trend"
