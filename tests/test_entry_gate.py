"""Contract 108: conditions are the only entry gate (2026-10-11).

The platform: "A strategy's deterministic entry gate is its conditions: a required condition, or a condition that
carries a verdict. A strategy that declares neither never trades, and its draft says so with the warning
NO_ENTRY_CONDITION" (README "Contract history - v108"). The served stage description narrows it to ENTRY conditions:
"the only deterministic entry gate - with no required and no verdict-carrying entry condition the strategy never
routes, and the draft warns NO_ENTRY_CONDITION" (data/contract/stage_strategy_draft/schema_20261010T215326Z.json,
stage_strategy_draft.description). The draft warns; OMEGA refuses: a strategy that can never trade is not a plan,
so the same finding is an ERROR here (omega.conditions.validate_entry_gate, omega.authoring.validate_thesis)."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from omega.authoring import validate_thesis
from omega.conditions import (NO_ENTRY_CONDITION, close_on, condition, entry_gates, exit_rule, num, ref,
                              validate_entry_gate)
from omega.generate import PRESETS, Thesis, plan

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = json.loads((ROOT / "data/contract/stage_strategy_draft/schema_20261010T215326Z.json")
                     .read_text(encoding="utf-8"))

BLOCK = condition("BLOCK", "a building block", num("RSI14_now", "gt", 50))           # verdict null, not required


def test_the_finding_is_the_platforms_own_warning_code():
    warnings = CAPTURE["get_strategy_draft"]["outputSchema"]["properties"]["diagnostics"]["properties"]["warnings"]
    assert warnings["items"]["properties"]["code"]["enum"] == [NO_ENTRY_CONDITION] == ["NO_ENTRY_CONDITION"]


def test_no_conditions_at_all_is_no_entry_condition():
    [f] = validate_entry_gate([])
    assert f.severity == "error" and NO_ENTRY_CONDITION in f.message
    assert entry_gates([]) == []


def test_building_blocks_alone_are_no_entry_condition():
    [f] = validate_entry_gate([BLOCK, condition("B2", "n", ref("BLOCK"))])
    assert f.severity == "error" and f.message.startswith(NO_ENTRY_CONDITION)


@pytest.mark.parametrize("verdict", ["UP", "DOWN", "NEITHER"])
def test_a_verdict_carrying_entry_condition_is_a_gate(verdict):
    """The schema's verdict enum is UP | DOWN | NEITHER or null; "carries a verdict" is any non-null one. NEITHER
    counts as carrying one (it admits no side when it resolves - the vendor's strategy-examples skill - but it IS
    a verdict); whether the platform's check agrees for a NEITHER-only strategy is unmeasured."""
    gate = condition("GATE", "n", ref("BLOCK"), verdict=verdict)
    assert validate_entry_gate([BLOCK, gate]) == []
    assert entry_gates([BLOCK, gate]) == ["GATE"]


def test_a_required_entry_condition_is_a_gate():
    veto = condition("VETO", "n", num("RSI14_now", "lt", 90), required=True)
    assert validate_entry_gate([veto]) == [] and entry_gates([veto]) == ["VETO"]


def test_an_exit_rule_is_never_an_entry_gate():
    """An exit rule is not an entry condition; even a malformed one carrying a verdict or required (refused on its
    own by validate_conditions) does not open the entry gate."""
    rule = exit_rule("XR", "n", num("RSI14_now", "gt", 70), "SHORT")
    assert validate_entry_gate([BLOCK, rule]) != []
    bad = dict(rule, verdict="UP", required=True)
    assert entry_gates([BLOCK, bad]) == []
    up = condition("UPC", "n", ref("BLOCK"), verdict="UP")
    assert entry_gates([BLOCK, up, close_on(up)]) == ["UPC"]


# --- the five presets ---------------------------------------------------------------------

# Every preset weights at least two directional modules, so _build_conditions emits its two verdict carriers
# {P}_UP and {P}_DOWN (prefix = the initials of the first two words of the thesis name). Nothing had to change.
PRESET_GATES = {
    "mean-reversion": ["MR_UP", "MR_DOWN"],
    "trend-continuation": ["TC_UP", "TC_DOWN"],
    "squeeze-breakout": ["SB_UP", "SB_DOWN"],
    "flow-divergence": ["SA_UP", "SA_DOWN"],
    "structure-reversal": ["SR_UP", "SR_DOWN"],
}


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_every_preset_has_an_entry_gate_of_two_verdict_carriers(name):
    p = plan(PRESETS[name])
    conds = p.axes()["CONDITIONS"]["conditions"]
    assert entry_gates(conds) == PRESET_GATES[name]
    by_key = {c["conditionKey"]: c for c in conds}
    assert [by_key[k]["verdict"] for k in PRESET_GATES[name]] == ["UP", "DOWN"]
    assert not any(c["required"] for c in conds)          # no preset declares a required veto
    assert validate_entry_gate(conds) == []
    assert not [f for f in p.condition_findings() if NO_ENTRY_CONDITION in f.message]
    assert NO_ENTRY_CONDITION not in {f.code for f in validate_thesis(PRESETS[name])}


def test_a_thesis_with_fewer_than_two_directional_modules_is_refused_with_no_entry_condition():
    """_build_conditions emits nothing below two directional modules: such a strategy could never trade at 108."""
    t = Thesis(name="One Way", weights={"RSI": 2, "VOLATILITY": 1})
    p = plan(t)
    assert p.conditions == []
    codes = {f.code for f in validate_thesis(t)}
    assert {"THESIS_TOO_FEW_DIRECTIONAL", NO_ENTRY_CONDITION} <= codes
    assert [f for f in validate_thesis(t) if f.code == NO_ENTRY_CONDITION][0].severity == "error"
    assert any(NO_ENTRY_CONDITION in f.message and f.severity == "error" for f in p.condition_findings())
    assert any(NO_ENTRY_CONDITION in line for line in p.critique())


def test_the_brief_and_the_render_name_the_entry_gate():
    from omega.authoring import brief
    p = plan(PRESETS["trend-continuation"])
    assert "entry gate: TC_UP, TC_DOWN" in brief(p)
    assert "entry gate: TC_UP, TC_DOWN" in p.render()
    lonely = plan(Thesis(name="One Way", weights={"RSI": 2}))
    assert "entry gate: NONE (NO_ENTRY_CONDITION)" in brief(lonely)


def test_an_exit_role_does_not_change_the_gate():
    t = replace(PRESETS["trend-continuation"], exits=["UP", "CORE_DOWN"])
    assert entry_gates(plan(t).axes()["CONDITIONS"]["conditions"]) == ["TC_UP", "TC_DOWN"]
