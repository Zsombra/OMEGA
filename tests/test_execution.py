"""Decision 1(a), recorded 2026-08-28: omega emitted NO execution parameters by default and
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


def _dials(axes: dict) -> dict:
    # contract 108: minAtrPct rides on TRADE_LEVEL_POLICY; SETUP_GATES is refused
    return {**axes["TRADE_LEVEL_POLICY"], **axes["POSITION_MANAGEMENT"]}


def test_presets_send_every_dial_at_the_measured_defaults():
    """Decision 1(a) emitted NO execution parameter on the compile. Since v85 every axis
    is staged WHOLE and the v91 schema requires each dial on its axis, so a create sends
    all 16 - at the measured defaults, until M1 reads a create draft's seeds."""
    for preset in PRESETS:
        dials = _dials(plan(PRESETS[preset]).axes())
        assert EXECUTION_PARAMS <= set(dials)
        assert {k: dials[k] for k in EXECUTION_PARAMS} == PLATFORM_EXECUTION_DEFAULTS


def test_an_explicit_override_reaches_its_axis():
    t = replace(PRESETS["trend-continuation"], execution={"minRiskRewardRatio": 2.0})
    a = plan(t).axes()
    assert a["TRADE_LEVEL_POLICY"]["minRiskRewardRatio"] == 2.0
    moved = {k for k, v in _dials(a).items()
             if k in PLATFORM_EXECUTION_DEFAULTS and v != PLATFORM_EXECUTION_DEFAULTS[k]}
    assert moved == {"minRiskRewardRatio"}


def test_every_dial_has_exactly_one_axis():
    from omega.execution import (POSITION_MANAGEMENT_DIALS, POSITION_MANAGEMENT_MIRROR,
                                 SETUP_GATE_DIALS, TRADE_LEVEL_DIALS)
    placed = list(TRADE_LEVEL_DIALS) + list(POSITION_MANAGEMENT_DIALS)
    assert len(placed) == len(set(placed))
    assert set(placed) == EXECUTION_PARAMS | set(POSITION_MANAGEMENT_MIRROR)
    # the retired v91 SETUP_GATES dial is TRADE_LEVEL_POLICY's at 108 (README "Contract history - v108")
    assert set(SETUP_GATE_DIALS) <= set(TRADE_LEVEL_DIALS) and TRADE_LEVEL_DIALS[0] == "minAtrPct"


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
    assert any(f.code == "EXECUTION_OUT_OF_BOUNDS"
               for f in validate_execution({"maxStopLossAtrMultiple": 3.5}))
    assert not [f for f in validate_execution({"maxStopLossAtrMultiple": 0.5})
                if f.code == "EXECUTION_OUT_OF_BOUNDS"]


def test_the_retired_schema_bounds_warn_and_never_gate():
    """Plan 2026-10-06: SCHEMA_BOUNDS "becomes a record of a retired schema, never a gate".
    The v91 and v108 axis schemas declare no bound on any dial, and since v89 a create is judged at
    the operator bounds configured now, in the draft's diagnostics and at commit."""
    from omega.contract import stage_schema
    axes = stage_schema()["stage_strategy_draft"]["inputSchema"]["properties"]["axes"]["properties"]
    for axis in ("TRADE_LEVEL_POLICY", "POSITION_MANAGEMENT"):
        for name, node in axes[axis]["properties"].items():
            assert not {"minimum", "maximum", "multipleOf"} & set(node), (axis, name)
    lo, hi = SCHEMA_BOUNDS["breakEvenTriggerR"]
    found = [f for f in validate_execution({"breakEvenTriggerR": hi + 1})
             if f.code == "EXECUTION_OUT_OF_BOUNDS"]
    assert found and all(f.severity == "warning" for f in found)


def test_override_validation():
    assert any(f.code == "EXECUTION_UNKNOWN_PARAM" and f.severity == "error"
               for f in validate_execution({"minRiskReward": 2}))       # typo'd key
    assert not [f for f in validate_execution({"breakEvenTriggerR": 1.5})
                if f.severity == "error"]


def test_critique_states_the_effective_profile():
    text = " ".join(plan(PRESETS["trend-continuation"]).critique())
    assert "platform defaults" in text and "R:R 1.5" in text
