"""Every generated strategy must be legal, in budget, and honestly allocated."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.contract import DERIVED_DIR, load
from omega.generate import (
    AXES, ENTRY_MIRROR, MODULE_RECIPES, PRESETS, Thesis, plan, plan_for_signals,
)
from omega.membership import signals_for
from omega.types import Column

MAP = json.loads((DERIVED_DIR / "signal_module_map.json").read_text(encoding="utf-8"))
CONTRACT = load()
PRESET_IDS = sorted(PRESETS)

# Recorded from the live connector for the squeeze-breakout preset's report.
SQUEEZE_LIVE_MEMBERSHIP = {
    "volume_surge", "volume_dry_up", "volume_obv_bull_divergence", "volume_obv_bear_divergence",
    "volatility_atr_expanding", "volatility_atr_contracting",
    "bollinger_squeeze", "bollinger_lower_touch", "bollinger_upper_touch",
    "bollinger_cci_oversold", "bollinger_cci_overbought",
    "oi_surge", "oi_divergence_bull", "oi_divergence_bear",
    "regime_trend_shift", "regime_volatility_shift", "regime_alignment", "regime_divergence",
}


@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_report_is_valid(name):
    result = plan(PRESETS[name]).validation()
    assert result.ok, result.report()


@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_is_within_budget(name):
    cost = plan(PRESETS[name]).cost()
    assert cost.ok, cost.breaches


@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_allocates_only_feedable_signals(name):
    p = plan(PRESETS[name])
    errors = [f for f in p.allocation_findings() if f.severity == "error"]
    assert not errors, [str(e) for e in errors]


@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_can_clear_its_own_gate(name):
    """A thesis whose signals all score well should route - otherwise the gate is unreachable."""
    p = plan(PRESETS[name])
    assert p.simulate(0.75).would_route


@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_separates_inert_metrics_into_their_own_section(name):
    p = plan(PRESETS[name])
    for section in p.report.sections:
        modes = {CONTRACT.metric(c.metric).timeframe_mode for c in section.columns}
        assert len(modes) == 1, f"{section.title} mixes {modes}"


def test_every_recipe_column_is_legal():
    from omega.validate import validate_column
    for module, specs in MODULE_RECIPES.items():
        for spec in specs:
            col = Column.model_validate(spec)
            errors = [f for f in validate_column(col, contract=CONTRACT) if f.severity == "error"]
            assert not errors, f"{module}: {[str(e) for e in errors]}"


def test_every_recipe_actually_feeds_its_module():
    for module, specs in MODULE_RECIPES.items():
        metrics = {s["metric"] for s in specs}
        assert module in {
            k for k, v in MAP["moduleSatisfiedBy"].items() if set(v) & metrics
        }, f"{module} recipe does not feed {module}"


def test_squeeze_breakout_matches_the_live_connector():
    """The live derive read the report as generated before 2026-10-10, REGIME as context; the
    preset dropped that context (tests/test_recipes_rung_gap.py), so the comparison keeps it."""
    from dataclasses import replace
    predicted = plan(replace(PRESETS["squeeze-breakout"], context=["REGIME"])).membership().signals_in
    assert predicted == SQUEEZE_LIVE_MEMBERSHIP
    assert len(predicted) == 18


def test_axes_carry_no_scorecard_and_no_gate_at_108():
    """v108: "signal rules, the aggregate-score gate and the required-count gate are removed"; the stage refuses
    SIGNAL_RULES and SETUP_GATES. The dense 84-row scorecard is StrategyPlan._rules(), retired (history)."""
    axes = plan(PRESETS["mean-reversion"]).axes()
    assert tuple(axes) == AXES and len(AXES) == 8
    assert "minAggregateScore" not in json.dumps(axes) and "minRequiredCount" not in json.dumps(axes)
    assert "signalId" not in json.dumps(axes)


def test_the_retired_scorecard_still_carries_the_recorded_default_params():
    """History: what the v91 SIGNAL_RULES rows carried (StrategyPlan._rules(), retired at contract 108)."""
    by_id = {r["signalId"]: r for r in plan(PRESETS["mean-reversion"])._rules()}
    assert by_id["rsi_oversold"]["params"] == {"threshold": 30}
    assert by_id["bollinger_lower_touch"]["params"] == {"pctBThreshold": 0.05}
    assert by_id["macd_bull_cross"]["params"] == {}


def test_emit_plan_keeps_cadence_as_local_metadata(tmp_path):
    """cadence/regimeTimeframe have no field on any axis (nor had they on the CREATE
    request, measured 2026-08-26, re-verified 2026-08-28) - but the anchor-derived values
    are still worth keeping. They ride on the emitted file as _-prefixed keys, which never
    go to the API. The rest of the file is a CREATE stage_strategy_draft request."""
    from omega.generate import emit_plan
    p = plan(PRESETS["mean-reversion"])
    path = emit_plan(p, "t", out_dir=tmp_path)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["_cadence"] == "INTRADAY"
    assert payload["_regimeTimeframe"] == "4h"
    assert "cadence" not in payload and "regimeTimeframe" not in payload
    assert {k for k in payload if not k.startswith("_")} == {"draftVersion", "axes"}
    assert payload["draftVersion"] == 0 and payload["axes"] == p.axes()
    assert payload["_previewRequest"] == p.preview_request()


def test_backwards_planning_reaches_requested_signals():
    p = plan_for_signals(["cvd_bull_divergence", "oi_surge"], name="T")
    assert {"cvd_bull_divergence", "oi_surge"} <= p.membership().signals_in
    assert p.validation().ok


def test_backwards_planning_reports_unreachable_signals():
    p = plan_for_signals(["cvd_bullish", "mtf_aligned_bull"], name="T")
    assert "mtf_aligned_bull" in p.thesis.description
    assert "mtf_aligned_bull" not in {r.signalId for r in p.rules}


def test_critique_flags_correlated_oscillators():
    t = Thesis(name="Osc Soup", weights={"RSI": 2, "STOCHASTIC": 2, "MFI": 2, "BOLLINGER": 2})
    text = " ".join(plan(t).critique())
    assert "correlated oscillators" in text


def test_critique_flags_an_unreachable_gate():
    t = Thesis(name="Impossible", gate=0.99, weights={"RSI": 1})
    p = plan(t)
    assert any("below the" in x for x in p.critique())
    assert not p.simulate(0.75).would_route


def test_generator_output_is_ascii_safe():
    """The user is on Windows; cp1252 consoles choke on smart punctuation."""
    for name in PRESET_IDS:
        text = plan(PRESETS[name]).render()
        text.encode("cp1252")


# --- the v91 draft axes (contract 85.0.0 split the body; 84/88 reshaped conditions) ------

@pytest.mark.parametrize("name", sorted(PRESETS))
def test_custom_sections_carry_provenance_notes(name):
    """notes is REQUIRED on a custom section (string 1-400 or null; the v91 REPORT axis
    keeps it). Plan decision 2026-08-29: emit a provenance string; null acceptance is
    unmeasured."""
    for s in plan(PRESETS[name]).axes()["REPORT"]["sections"]:
        if s["kind"] == "custom":
            assert isinstance(s["notes"], str) and 1 <= len(s["notes"]) <= 400
            assert "omega.generate" in s["notes"]


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_axes_are_the_eight_in_order_and_the_update_drops_entry_and_unnamed_dials(name):
    """A create stages all eight (contract 108). An update without execution overrides stages
    neither ENTRY nor the two dial axes (they keep the strategy's values; tests/test_first_update.py
    pins the rule) - and since SETUP_GATES is gone, nothing else forces a dial axis onto it."""
    assert PRESETS[name].execution is None      # every preset runs on the platform's dials
    p = plan(PRESETS[name])
    a = p.axes()
    assert tuple(a) == AXES == ("IDENTITY", "TIMEFRAME_PROFILE", "REPORT", "MARKET_READ", "CONDITIONS",
                                "ENTRY", "TRADE_LEVEL_POLICY", "POSITION_MANAGEMENT")
    u = p.axes_update({"TRADE_LEVEL_POLICY": {**a["TRADE_LEVEL_POLICY"], "minAtrPct": 0.8}})
    dropped = {"ENTRY", "TRADE_LEVEL_POLICY", "POSITION_MANAGEMENT"}
    assert tuple(u) == tuple(x for x in AXES if x not in dropped)


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_entry_is_on_candle_close_alone(name):
    """v85: "{ trigger: 'ON_CANDLE_CLOSE' } alone ... ON_CANDLE_CLOSE naming either dial
    is refused, which the retired compile accepted; the server stamps the seed values".
    The trigger itself is the one every stored record was migrated to at 60.0.0
    (data/contract/get_strategy/824f4343-..._20260918T084500Z.json)."""
    assert ENTRY_MIRROR == {"trigger": "ON_CANDLE_CLOSE"}
    assert plan(PRESETS[name]).axes()["ENTRY"] == {"entry": ENTRY_MIRROR}


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_conditions_axis_carries_the_six_v91_keys_as_entry_conditions(name):
    """v84 moved the hold onto each clause and group (`closes` refused), v88 replaced
    `exit` with `exitSide` (nullable, never optional). No preset declares an exit, so every
    emitted condition is an entry condition, exitSide null; tests/test_conditions.py walks
    them through the saved 91.0.0 CONDITIONS axis."""
    for c in plan(PRESETS[name]).axes()["CONDITIONS"]["conditions"]:
        assert list(c) == ["conditionKey", "name", "definition", "verdict",
                            "required", "exitSide"]
        assert c["exitSide"] is None


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_whole_axes_send_every_dial_at_the_measured_defaults(name):
    """Each axis is written WHOLE (v85) and the v91 schema REQUIRES every dial on its
    axis, so a create sends all of them: the 08-28 measured defaults (M1 owed), and the
    thirteenth POSITION_MANAGEMENT dial mirrored from every record on disk."""
    from omega.execution import (PLATFORM_EXECUTION_DEFAULTS, POSITION_MANAGEMENT_DIALS,
                                 TRADE_LEVEL_DIALS)
    a = plan(PRESETS[name]).axes()
    assert list(a["POSITION_MANAGEMENT"]) == list(POSITION_MANAGEMENT_DIALS)
    assert a["POSITION_MANAGEMENT"]["decisionInvalidationExitEnabled"] is True
    # v108: minAtrPct is required on TRADE_LEVEL_POLICY, in the 108 schema's `required` order
    assert list(a["TRADE_LEVEL_POLICY"]) == list(TRADE_LEVEL_DIALS) == [
        "minAtrPct", "minStopLossAtrMultiple", "maxStopLossAtrMultiple", "minRiskRewardRatio"]
    sent = {**a["TRADE_LEVEL_POLICY"], **a["POSITION_MANAGEMENT"]}
    assert all(sent[k] == v for k, v in PLATFORM_EXECUTION_DEFAULTS.items())


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_axes_walk_clean_against_the_v108_stage_schema(name):
    """Zero FAIL and zero UNSUPPORTED walking the whole CREATE stage request through the
    saved 108.0.0 stage_strategy_draft input schema (the manifest's writeSurface)."""
    from omega import preflight as P
    from omega.contract import stage_schema
    root = stage_schema()["stage_strategy_draft"]["inputSchema"]
    findings = P.diff_schema({"request": {"draftVersion": 0, "axes": plan(PRESETS[name]).axes()}},
                             root, root)
    assert [(f.cls, f.path) for f in findings if f.verdict == "FAIL"] == []
    assert [f for f in findings if f.cls == "UNSUPPORTED"] == []


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_the_preview_request_is_a_fields_source_that_walks_clean(name):
    """The dry run (v85): preview_strategy_report {coinSelection, source: {kind: FIELDS,
    timeframe, sections, conditions, marketReadText}}. coinSelection is an input of the
    preview only - no axis carries it."""
    from omega import preflight as P
    from omega.contract import stage_schema
    p = plan(PRESETS[name])
    body = p.preview_request()
    a = p.axes()
    assert body["coinSelection"] == p.thesis.resolved_coin_selection()
    assert body["source"] == {"kind": "FIELDS", "timeframe": a["TIMEFRAME_PROFILE"]["timeframe"],
                              "sections": a["REPORT"]["sections"],
                              "conditions": a["CONDITIONS"]["conditions"],
                              "marketReadText": a["MARKET_READ"]["marketReadText"]}
    assert "coinSelection" not in json.dumps(a)
    root = stage_schema()["preview_strategy_report"]["inputSchema"]
    findings = P.diff_schema(body, root, root)
    assert [(f.cls, f.path) for f in findings if f.verdict == "FAIL"] == []
    assert [f for f in findings if f.cls == "UNSUPPORTED"] == []


def test_wire_and_wire_update_are_gone_not_aliased():
    from omega.generate import StrategyPlan
    assert not hasattr(StrategyPlan, "wire") and not hasattr(StrategyPlan, "wire_update")


def test_render_carries_the_assumptions_that_no_longer_reach_the_platform():
    text = plan(PRESETS["trend-continuation"]).render()
    assert "assumptions:" in text and "local only" in text


# --- exits: the v88 split, generated -----------------------------------------------

EXITING = Thesis(name="Trend Continuation", tagline="t", description="d", gate=0.60,
                 weights={"MOVING_AVERAGES": 3, "TREND_STRENGTH": 2, "MACD": 2, "VOLUME": 1},
                 context=["REGIME"], exits=["CORE_UP", "UP"])


def test_a_thesis_exit_role_appends_its_close_on_rule_after_the_seven():
    conds = plan(EXITING).axes()["CONDITIONS"]["conditions"]
    assert [c["conditionKey"] for c in conds][7:] == ["CLOSE_ON_TC_CORE_UP", "CLOSE_ON_TC_UP"]
    by_key = {c["conditionKey"]: c for c in conds}
    assert by_key["CLOSE_ON_TC_UP"]["exitSide"] == "SHORT"       # UP verdict -> closes shorts
    assert by_key["CLOSE_ON_TC_CORE_UP"]["exitSide"] == "BOTH"   # null verdict -> both sides
    assert by_key["TC_UP"]["exitSide"] is None and by_key["TC_UP"]["verdict"] == "UP"
    # an exit rule never reaches the market read
    assert "CLOSE_ON" not in plan(EXITING).market_read_text


def test_the_generated_exit_rules_are_judged_by_the_exit_read_rule():
    """CLOSE_ON_TC_UP reads TC_UP's whole closure, which includes the ambient tape and the
    stablecoin pairs - not moved by a completed bar (CONDITION_EXIT_READ_ILLEGAL). The
    core's closure is the report's own candle columns, so its rule is clean."""
    errs = [f for f in plan(EXITING).condition_findings() if f.severity == "error"]
    assert {f.condition_key for f in errs} == {"CLOSE_ON_TC_UP"}
    assert all("CONDITION_EXIT_READ_ILLEGAL" in f.message for f in errs)


def test_an_unknown_exit_role_is_refused():
    from dataclasses import replace
    with pytest.raises(ValueError):
        plan(replace(EXITING, exits=["SIDEWAYS"]))
