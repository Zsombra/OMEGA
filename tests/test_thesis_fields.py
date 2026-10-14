"""What a Thesis is at contract 108 (2026-10-11).

v108 removed "signal rules, the aggregate-score gate and the required-count gate" (README "Contract history -
v108"). `Thesis.gate` was SETUP_GATES.minAggregateScore and `Thesis.required` named the signal ids counted into
minRequiredCount; neither has a platform meaning any more and nothing in OMEGA reads them, so both are retired -
removed from the dataclass, not aliased. A caller passing either gets a TypeError rather than a silently ignored
value. battlegrid-manager pins the field list (manager/authoring/pipeline.py THESIS_KEYS) and must follow."""
from __future__ import annotations

from dataclasses import fields

import pytest

from omega.generate import PRESETS, Thesis, plan


def _names() -> list[str]:
    return [f.name for f in fields(Thesis)]


# The field list at contract 108, in order (battlegrid-manager's THESIS_KEYS must equal it).
THESIS_FIELDS_108 = ("name", "tagline", "description", "anchor", "weights", "stance", "context",
                     "coin_selection", "execution", "exits")


def test_the_field_list_at_108_is_exactly_this():
    assert tuple(_names()) == THESIS_FIELDS_108


def test_show_scoring_data_is_retired_with_the_scoring_data_columns():
    """It added a column per (metric, rung) a weighted SIGNAL scored on; with no signals at 108 those columns fed
    nothing. plan() now gives what show_scoring_data=False gave; plan_pre_108 keeps the widened report."""
    from omega.generate import plan_pre_108
    assert "show_scoring_data" not in _names()
    with pytest.raises(TypeError):
        Thesis(name="x", show_scoring_data=False)
    for name, t in PRESETS.items():
        assert plan(t).report == plan_pre_108(t, show_scoring_data=False).report, name


@pytest.mark.parametrize("retired", ["gate", "required"])
def test_the_gate_and_the_required_signal_ids_are_retired(retired):
    assert retired not in _names()
    with pytest.raises(TypeError):
        Thesis(name="x", **{retired: 0.6 if retired == "gate" else ["rsi_oversold"]})


def test_weights_stay_and_still_choose_the_report_modules():
    """`weights` keeps its role: its keys choose which modules' recipe columns the REPORT shows (and which modules'
    readings the condition checklist reads). The tier number had one platform meaning - the signal allocation - and
    has none at 108; it is still validated 0..3 so existing theses stay legal."""
    assert "weights" in _names()
    t = PRESETS["trend-continuation"]
    metrics = {c.metric for s in plan(t).report.sections for c in s.columns}
    assert {"MA_ALIGN", "ADX", "MACD_HIST", "OBV"} <= metrics      # MACD_HIST since contract 110 (MACD retired)
    assert {"MACD_HIST", "OBV"}.isdisjoint({c.metric for s in plan(Thesis(
        name="Trend Continuation", weights={"MOVING_AVERAGES": 3, "TREND_STRENGTH": 2})).report.sections
        for c in s.columns})


def test_no_preset_sets_a_retired_field():
    for name, t in PRESETS.items():
        assert not hasattr(t, "gate") and not hasattr(t, "required"), name
