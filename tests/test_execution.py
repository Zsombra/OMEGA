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


def test_schema_bounds_are_the_ones_the_2026_09_18_capture_declares():
    """The five bounds that moved between the 09-09 and 09-18 captures, as
    omega.preflight.changelog computed them off
    data/contract/compile_strategy_plan/schema_20260909T080307Z.json ->
    schema_20260918T083359Z.json (contract 61.0.1):
        maxStopLossAtrMultiple :: bounds {} -> {'maximum': 3}
        minAtrPct              :: bounds {'minimum': 0.01, 'maximum': 50} -> {}
        timeDecayGracePeriodMinutes :: {'minimum': 1, ...} -> {'minimum': 5, 'maximum': 1440}
        timeDecayIntervalMinutes    :: {'minimum': 1, ...} -> {'minimum': 5, 'maximum': 480}
        timeDecayTightenPct         :: {'minimum': 0.1, ...} -> {'minimum': 0.5, 'maximum': 50}
    minAtrPct is unbounded in the schema now, so it leaves SCHEMA_BOUNDS entirely (the
    catalog bound for it is a separate, still-measured surface)."""
    assert SCHEMA_BOUNDS["maxStopLossAtrMultiple"] == (None, 3)
    assert "minAtrPct" not in SCHEMA_BOUNDS
    assert SCHEMA_BOUNDS["timeDecayIntervalMinutes"] == (5, 480)
    assert SCHEMA_BOUNDS["timeDecayGracePeriodMinutes"] == (5, 1440)
    assert SCHEMA_BOUNDS["timeDecayTightenPct"] == (0.5, 50)


def test_schema_bounds_agree_with_the_committed_2026_09_18_capture():
    """Not a restatement of the constant: read the bounds straight out of the capture and
    demand SCHEMA_BOUNDS equal them, so a re-capture that moves a bound fails here."""
    import json
    from pathlib import Path

    from omega import preflight as P

    root_dir = Path(__file__).resolve().parents[1]
    definition = json.loads((root_dir / "data/contract/compile_strategy_plan"
                             / "schema_20260918T083359Z.json").read_text(encoding="utf-8"))["response"]
    arms, root = P.resolve_arms(definition)
    create = P.deref(arms["CREATE"], root)
    declared = {}
    for name in PLATFORM_EXECUTION_DEFAULTS:
        node = P.deref(create["properties"][name], root)
        if "minimum" in node or "maximum" in node:
            declared[name] = (node.get("minimum"), node.get("maximum"))
    assert SCHEMA_BOUNDS == declared


def test_the_platform_defaults_sit_inside_the_schema_bounds():
    """The 61.0.1 minima rose on three time-decay knobs; the measured defaults (60, 15, 5)
    are still legal, which is why omega can keep emitting nothing and describe them."""
    for name, value in PLATFORM_EXECUTION_DEFAULTS.items():
        if name not in SCHEMA_BOUNDS or isinstance(value, bool):
            continue
        lo, hi = SCHEMA_BOUNDS[name]
        assert lo is None or value >= lo, (name, value, lo)
        assert hi is None or value <= hi, (name, value, hi)


def test_an_open_lower_bound_still_validates_the_upper_edge():
    """maxStopLossAtrMultiple is (None, 3) in 61.0.1 - a maximum with no minimum. The open
    edge must not silence the closed one, and must not raise."""
    assert any(f.code == "EXECUTION_OUT_OF_BOUNDS" and f.severity == "error"
               for f in validate_execution({"maxStopLossAtrMultiple": 3.5}))
    assert not [f for f in validate_execution({"maxStopLossAtrMultiple": 0.5})
                if f.severity == "error"]


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
