"""Every generated strategy must be legal, in budget, and honestly allocated."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.contract import DERIVED_DIR, load
from omega.generate import (
    MODULE_RECIPES, PRESETS, Thesis, plan, plan_for_signals,
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
    predicted = plan(PRESETS["squeeze-breakout"]).membership().signals_in
    assert predicted == SQUEEZE_LIVE_MEMBERSHIP
    assert len(predicted) == 18


def test_wire_payload_has_the_dense_84_entry_scorecard():
    payload = plan(PRESETS["mean-reversion"]).wire()
    rules = payload["rules"]
    assert len(rules) == 84
    assert len({r["signalId"] for r in rules}) == 84
    assert payload["minAggregateScore"] == PRESETS["mean-reversion"].gate
    # unallocated signals must be present at zero, matching real strategies
    zeros = [r for r in rules if r["allocation"] == 0]
    assert zeros and all(r["required"] is False for r in zeros)


def test_wire_params_match_recorded_defaults():
    payload = plan(PRESETS["mean-reversion"]).wire()
    by_id = {r["signalId"]: r for r in payload["rules"]}
    assert by_id["rsi_oversold"]["params"] == {"threshold": 30}
    assert by_id["bollinger_lower_touch"]["params"] == {"pctBThreshold": 0.05}
    assert by_id["macd_bull_cross"]["params"] == {}


def test_emit_plan_keeps_cadence_as_local_metadata(tmp_path):
    """cadence/regimeTimeframe have no CREATE-request field (measured 2026-08-26,
    re-verified 2026-08-28), so wire() no longer carries them - but the anchor-derived
    values are still worth keeping. They ride on the emitted file as _-prefixed keys,
    which never go to the API."""
    from omega.generate import emit_plan
    path = emit_plan(plan(PRESETS["mean-reversion"]), "t", out_dir=tmp_path)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["_cadence"] == "INTRADAY"
    assert payload["_regimeTimeframe"] == "4h"
    assert "cadence" not in payload and "regimeTimeframe" not in payload


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


# --- the condition-clock migration surface (schema published 2026-08-30) ------

@pytest.mark.parametrize("name", sorted(PRESETS))
def test_custom_sections_carry_provenance_notes(name):
    """sections[].notes is REQUIRED by the compile schema (string 1-400 or null).
    Plan decision 2026-08-29: emit a provenance string; null acceptance is
    unmeasured."""
    for s in plan(PRESETS[name]).wire()["sections"]:
        if s["kind"] == "custom":
            assert isinstance(s["notes"], str) and 1 <= len(s["notes"]) <= 400
            assert "omega.generate" in s["notes"]


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_wire_emits_the_platform_migration_entry(name):
    """entry is REQUIRED on CREATE since 2026-08-30. Values mirror the platform's
    own migration of existing records (6a8bca67 read-back: AT_SIGNAL, confirmTf =
    the anchor timeframe, closes 1, bandAtrMultiple 1; drift instance #4 later
    the same day added levelSource/levelOffsetAtrMultiple/validForBars, mirrored
    from the same record's silent re-migration) - semantics unmeasured, so
    nothing else may be emitted. The 7-field form compiled viable and
    round-tripped verbatim (b9438519, deep_tail_fade_create_2026-08-30.json)."""
    p = plan(PRESETS[name])
    assert p.wire()["entry"] == {"trigger": "AT_SIGNAL",
                                 "confirmTf": p.thesis.anchor,
                                 "closes": 1, "bandAtrMultiple": 1,
                                 "levelSource": "SWING_HIGH",
                                 "levelOffsetAtrMultiple": 0, "validForBars": 4}


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_wire_conditions_all_carry_clock_and_closes(name):
    for c in plan(PRESETS[name]).wire()["conditions"]:
        assert c["clock"] in ("LIVE", "CLOSE")
        assert c["closes"] == 1


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_wire_conditions_all_carry_exit_false(name):
    """Drift instance #5 (2026-09-04, caught offline): conditions[].exit is REQUIRED
    by the published compile schema; both existing records read back exit=false on
    every condition (drift5_exit_rediscovery_2026-09-04.json). Mirrored, not
    interpreted: exit=true semantics are unmeasured."""
    for c in plan(PRESETS[name]).wire()["conditions"]:
        assert c["exit"] is False


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_wire_does_not_emit_decisionInvalidationExitEnabled(name):
    """The same schema declares an OPTIONAL top-level decisionInvalidationExitEnabled;
    existing records read back true, but what a CREATE that omits it receives is
    unmeasured, so emitting a value would be inference. Left out on purpose."""
    assert "decisionInvalidationExitEnabled" not in plan(PRESETS[name]).wire()
