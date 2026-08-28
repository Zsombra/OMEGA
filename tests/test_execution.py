"""Decision 1(a), recorded 2026-08-28: omega emits NO execution parameters by default and
says exactly what the platform will therefore do - the defaults are measured, not
invented (execution_surface_ownership_2026-08-28.json + the Task 3/4 probes)."""
from dataclasses import replace

from omega.execution import (
    EXECUTION_PARAMS, PLATFORM_EXECUTION_DEFAULTS, SCHEMA_BOUNDS, validate_execution,
)
from omega.generate import PRESETS, plan


def test_the_defaults_are_the_measured_ones():
    assert len(EXECUTION_PARAMS) == 16
    assert PLATFORM_EXECUTION_DEFAULTS["minRiskRewardRatio"] == 1.5
    assert PLATFORM_EXECUTION_DEFAULTS["trailingEnabled"] is True
    assert PLATFORM_EXECUTION_DEFAULTS["breakEvenTriggerR"] == 1.08


def test_presets_emit_no_execution_parameters():
    for preset in PRESETS:
        assert not EXECUTION_PARAMS & set(plan(PRESETS[preset]).wire())


def test_an_explicit_override_reaches_the_wire():
    t = replace(PRESETS["trend-continuation"], execution={"minRiskRewardRatio": 2.0})
    w = plan(t).wire()
    assert w["minRiskRewardRatio"] == 2.0
    assert EXECUTION_PARAMS & set(w) == {"minRiskRewardRatio"}


def test_override_validation():
    assert any(f.code == "EXECUTION_UNKNOWN_PARAM"
               for f in validate_execution({"minRiskReward": 2}))       # typo'd key
    lo, hi = SCHEMA_BOUNDS["breakEvenTriggerR"]
    assert any(f.code == "EXECUTION_OUT_OF_BOUNDS" and f.severity == "error"
               for f in validate_execution({"breakEvenTriggerR": hi + 1}))
    assert not [f for f in validate_execution({"breakEvenTriggerR": 1.5})
                if f.severity == "error"]


def test_critique_states_the_effective_profile():
    text = " ".join(plan(PRESETS["trend-continuation"]).critique())
    assert "platform defaults" in text and "R:R 1.5" in text
