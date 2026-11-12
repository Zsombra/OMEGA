"""Contract 171: the exit plan's runner (omega/trade_levels.py), replayed against the platform's answers.

data/audit/exit_plan_runner_171_2026-11-12.json holds 14 create stages at 171.0.0 / 588e449a (2026-11-12 14:52 -
14:58Z): 10 drafts staged, read back, previewed with preview_strategy_trade_levels on the DRAFT and discarded, none
committed, and 4 refused at input. Every probe is replayed offline on the dials and the trailingEnabled it staged:
where the stage answered clean, omega finds no error; where it answered an error or refused the input, omega raises
one on the SAME field. What a plan pays is checked against the number the stage's refusal names and the risk-reward
every rendered preview reads beside each stop.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from omega import trade_levels as tl
from omega.execution import validate_execution
from omega.generate import PRESETS, Thesis, plan

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / tl.RUNNER_PROBES).read_text(encoding="utf-8"))
PROBES = RECORD["probes"]
BASE = json.loads((ROOT / tl.EXIT_PLAN_PROBES).read_text(encoding="utf-8"))["basePlan"]


def _legs(name: str) -> list[dict]:
    return PROBES[name]["sent"]["menu"]["LONG"]["exitPlans"][0]["targets"]


def _offline(probe: dict) -> list:
    sent = probe["sent"]
    found = tl.validate_menu(sent["menu"], dials=sent["dials"], sections=BASE["reportSections"],
                             anchor=BASE["anchor"], trailing_enabled=sent["trailingEnabled"])
    # the dial the stage names (W2) is judged where omega judges a dial: omega.execution.validate_execution
    return found + validate_execution({"minRiskRewardRatio": sent["dials"]["minRiskRewardRatio"]})


def _platform_fields(probe: dict) -> list[str]:
    answer = probe["answer"]
    if not answer["staged"]:                    # refused at input: the issue paths, as the menu's own field path
        return [".".join(str(p) for p in issue["path"][2:]) for issue in answer["refusal"]["issues"]]
    return [e["field"] for e in answer["errors"]]


def _field(path: str) -> str:
    """omega names a list position `[i]` and a dial `execution.<dial>`; the platform's input issues name a position
    `.i` and a draft error names the dial bare - one spelling for comparing."""
    return path.replace("[", ".").replace("]", "").removeprefix("execution.")


def test_the_record_is_fourteen_stages_none_committed_every_draft_discarded_and_read_null():
    assert RECORD["counts"] == {"stages": 14, "staged": 10, "refusedAtInput": 4, "discarded": 10, "committed": 0,
                                "previews": 10, "previewsRendered": 5, "previewsRefused": 5}
    run = RECORD["measuredAt"][0]
    assert run["contractVersion"] == run["versionAtEnd"] == "171.0.0"
    assert run["buildSha"] == run["buildShaAtEnd"] and run["buildSha"].startswith("588e449a")
    for name, probe in PROBES.items():
        if probe["answer"]["staged"]:
            assert probe["discarded"] is True and probe["draftAfterDiscard"] is None, name
            assert probe["keptAsSent"] is True and probe["keptTrailingEnabled"] is probe["sent"]["trailingEnabled"]


@pytest.mark.parametrize("name", sorted(PROBES))
def test_every_probe_replays_offline_as_the_stage_answered(name):
    probe = PROBES[name]
    found = _offline(probe)
    errors = sorted({_field(f.path) for f in found if f.severity == "error"})
    platform = sorted({_field(f) for f in _platform_fields(probe)})
    if not platform:
        assert errors == [], (name, [str(f) for f in found])
        return
    # the platform names LONG and SHORT on input issues and LONG alone on a draft's errors; omega names both sides
    assert set(platform) <= set(errors), (name, platform, errors)
    assert {e.replace("SHORT", "LONG") for e in errors} == {p.replace("SHORT", "LONG") for p in platform}, name


@pytest.mark.parametrize("name, code", [
    ("T1.runner_trailing_off", "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING"),
    ("T2.trail_objective_trailing_off", "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING"),
    ("W1.r1_30_r3_30_min_2_5", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"),
    ("W2.r1_30_r3_30_min_2_2", "EXECUTION_OFF_STEP"),
    ("O1.trail_objective_min_2", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"),
    ("O2.zero_after_full_plan", "TRADE_MENU_EXIT_PLAN_ZERO_WITHOUT_RUNNER"),
    ("O3.zero_in_the_middle", "TRADE_MENU_EXIT_PLAN_ZERO_NOT_LAST"),
    ("S1.runner_3pct", "TRADE_MENU_EXIT_PLAN_RUNNER_UNDER_5"),
    ("S2.closing_target_3pct", "TRADE_MENU_EXIT_PLAN_LEG_UNDER_5"),
])
def test_each_rule_has_its_own_code(name, code):
    assert {f.code for f in _offline(PROBES[name]) if f.severity == "error"} == {code}


def test_trailing_off_alone_is_not_refused_and_a_runner_with_trailing_unknown_is_warned():
    assert [f for f in _offline(PROBES["T3.full_plans_trailing_off"]) if f.severity == "error"] == []
    runner = PROBES["T1.runner_trailing_off"]["sent"]

    def found(trailing):
        return tl.validate_menu(runner["menu"], dials=runner["dials"], sections=BASE["reportSections"],
                                anchor=BASE["anchor"], trailing_enabled=trailing)

    assert found(True) == []                 # T4: the same runner with Trailing on stages clean
    # a caller that does not say: the rule cannot be judged, so it warns instead of failing open (review 2026-11-12)
    unknown = found(None)
    assert {(f.severity, f.code, f.path) for f in unknown} == {
        ("warning", "TRADE_MENU_EXIT_PLAN_RUNNER_TRAILING_UNKNOWN", f"tradeLevelMenu.{side}.exitPlans[0]")
        for side in tl.SIDES}
    # no runner, no warning: the default menu's plans close 100%
    assert tl.validate_menu(tl.default_menu(1.5), dials=runner["dials"], sections=BASE["reportSections"],
                            anchor=BASE["anchor"], trailing_enabled=None) == []


def test_an_update_with_trailing_unknown_under_a_staged_runner_is_warned():
    # neither the update nor `current` carries trailingEnabled: the restaged runner is warned, not passed
    base = PRESETS["trend-continuation"]
    named = plan(Thesis(**{**base.__dict__, "trade_level_menu": _runner_menu()}))
    current = {"TRADE_LEVEL_POLICY": dict(BASE["dials"])}
    assert "POSITION_MANAGEMENT" not in named.axes_update(current)
    assert {(f.severity, f.code) for f in named.update_menu_findings(current)} == {
        ("warning", "TRADE_MENU_EXIT_PLAN_RUNNER_TRAILING_UNKNOWN")}


def _r_plan(*legs) -> dict:
    side = {"stops": [{"kind": "ATR", "atrMultiple": 1}],
            "exitPlans": [{"targets": [{"method": {"kind": "R_MULTIPLE", "multiple": m}, "closePct": c}
                                       for m, c in legs]}]}
    return {s: copy.deepcopy(side) for s in tl.SIDES}


@pytest.mark.parametrize("at, below, minimum", [
    # binary floats paid these 0.9999999999999999 and 1.2499999999999998 and refused them (review 2026-11-12)
    (((0.6, 50), (1.4, 28)), ((0.6, 51), (1.4, 27)), 1),
    (((0.6, 50), (1.9, 9)), ((0.6, 51), (1.9, 8)), 1.25),
])
def test_a_plan_paying_exactly_the_minimum_is_not_refused_and_one_tick_below_is(at, below, minimum):
    dials = {**BASE["dials"], "minRiskRewardRatio": minimum}

    def codes(menu, dials=dials):
        return {f.code for f in tl.validate_menu(menu, dials=dials, sections=BASE["reportSections"],
                                                 anchor=BASE["anchor"], trailing_enabled=True)}

    legs = _r_plan(*at)["LONG"]["exitPlans"][0]["targets"]
    assert tl.plan_pays_exact(legs) == tl._exact(minimum) and tl.plan_pays(legs) == minimum
    assert codes(_r_plan(*at)) == set()
    # one closePct tick (the integer step) moved from the far leg to the near one: below the minimum, refused
    assert tl.plan_pays_exact(_r_plan(*below)["LONG"]["exitPlans"][0]["targets"]) < tl._exact(minimum)
    assert codes(_r_plan(*below)) == {"TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"}
    # and the exact plan against a minimum one float tick above it is refused too
    assert codes(_r_plan(*at), {**dials, "minRiskRewardRatio": math.nextafter(minimum, 2)}) == {
        "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"}


def test_an_update_carrying_a_live_minimum_off_its_step_is_refused():
    # v0.14.1 warned here (every probe was a CREATE). Measured 2026-11-12 at 171.0.0 (tests/test_update_rules_171.py):
    # an UPDATE restaging an off-step minimum is a draft error on the dial, named (C1) or carried as the draft holds it
    # (C2) - both SENT the value in a restaged TRADE_LEVEL_POLICY; one carried from the committed strategy, or held in
    # an axis the update does not stage, is unmeasured and refused too, failing closed
    base = PRESETS["trend-continuation"]
    current = plan(base).axes()
    current["TRADE_LEVEL_POLICY"]["minRiskRewardRatio"] = 1.6          # a live value off the 0.25 step
    current["TRADE_LEVEL_POLICY"]["tradeLevelMenu"] = tl.default_menu(1.5)
    carried = plan(Thesis(**{**base.__dict__, "execution": {"minAtrPct": 0.4}}))
    staged = carried.axes_update(current)["TRADE_LEVEL_POLICY"]
    assert staged["minRiskRewardRatio"] == 1.6                              # carried as read
    found = carried.update_menu_findings(current)
    assert [(f.severity, f.code, f.path) for f in found if f.code == "EXECUTION_CARRIED_OFF_STEP"] == [
        ("error", "EXECUTION_CARRIED_OFF_STEP", "TRADE_LEVEL_POLICY.minRiskRewardRatio")]
    assert all("C1" in f.message and "C2" in f.message for f in found if f.code == "EXECUTION_CARRIED_OFF_STEP")
    # named on its step by the thesis: nothing carried, nothing refused
    fixed = plan(Thesis(**{**base.__dict__, "execution": {"minAtrPct": 0.4, "minRiskRewardRatio": 1.5}}))
    assert [f for f in fixed.update_menu_findings(current) if f.code == "EXECUTION_CARRIED_OFF_STEP"] == []
    # a live value on its step: nothing to refuse
    current["TRADE_LEVEL_POLICY"]["minRiskRewardRatio"] = 1.5
    assert [f for f in carried.update_menu_findings(current) if f.code == "EXECUTION_CARRIED_OFF_STEP"] == []
    # the axis not restaged: the strategy still holds the value. A2 and A3 measured a rule tying two axes re-judged when
    # ONE of them is staged; no probe left TRADE_LEVEL_POLICY unsent with an off-step value in it - so this is
    # unmeasured, refused on the axis that holds it, failing closed, and labelled so (v0.14.1 passed it)
    current["TRADE_LEVEL_POLICY"]["minRiskRewardRatio"] = 1.6
    held = [f for f in plan(base).update_menu_findings(current) if f.code == "EXECUTION_CARRIED_OFF_STEP"]
    assert [(f.severity, f.path) for f in held] == [("error", "TRADE_LEVEL_POLICY.minRiskRewardRatio")]
    assert all(s in held[0].message for s in ("does not stage", "unmeasured", "failing closed"))
    assert "the stage refuses it" not in held[0].message          # not claimed as the stage's measured answer


def test_what_a_plan_pays_is_the_number_the_stage_names():
    for name, pays in (("W1.r1_30_r3_30_min_2_5", 2.4), ("O1.trail_objective_min_2", 1.5)):
        assert round(tl.plan_pays(_legs(name)), 6) == pays
        assert f"pays {pays}R" in PROBES[name]["answer"]["errors"][0]["message"]


@pytest.mark.parametrize("name", ["T3.full_plans_trailing_off", "T4.runner_trailing_on", "W2b.r1_30_r3_30_min_2_25",
                                  "W3.r1_50_r2_2_20_min_1_5", "O4.trail_objective_min_1_5"])
def test_what_a_plan_pays_is_the_risk_reward_every_preview_reads(name):
    preview = PROBES[name]["preview"]
    assert set(preview["directions"]) == {"LONG", "SHORT"}
    for side, direction in preview["directions"].items():
        assert direction["setups"] and direction["rejectedPairs"] == []
        for setup in direction["setups"]:
            assert round(tl.plan_pays(setup["exitPlans"][0]["targets"]), 6) == setup["riskRewardRatio"], (name, side)


def test_where_v0_14_0_parted_from_the_stage():
    # a runner after two different R legs: v0.14.0's mean over the closed share is below what the stage judges
    for name, old, new in (("T4.runner_trailing_on", 2.0625, 2.25), ("W1.r1_30_r3_30_min_2_5", 2.0, 2.4),
                           ("W2b.r1_30_r3_30_min_2_25", 2.0, 2.4), ("O1.trail_objective_min_2", 1.285714, 1.5)):
        assert round(tl.plan_pays_v0_14_0(_legs(name)), 6) == old and round(tl.plan_pays(_legs(name)), 6) == new
    # W2b and W3 straddle: v0.14.0 would have refused both, the stage staged both clean
    for name in ("W2b.r1_30_r3_30_min_2_25", "W3.r1_50_r2_2_20_min_1_5"):
        minimum = PROBES[name]["sent"]["dials"]["minRiskRewardRatio"]
        assert tl.plan_pays_v0_14_0(_legs(name)) < minimum <= tl.plan_pays(_legs(name))
        assert PROBES[name]["answer"]["errors"] == []
    # no v0.14.0 probe could tell the two apart: they differ only on X3 (2.25 vs 2.0625), both above its 1.5 minimum
    old = json.loads((ROOT / tl.EXIT_PLAN_PROBES).read_text(encoding="utf-8"))["probes"]
    differ = set()
    for name, probe in old.items():
        for plan_ in probe["sent"]["menu"]["LONG"]["exitPlans"]:
            a, b = tl.plan_pays(plan_["targets"]), tl.plan_pays_v0_14_0(plan_["targets"])
            if a is not None and round(a, 9) != round(b, 9):
                differ.add(name)
                assert a >= 1.5 and b >= 1.5, name
    assert differ == {"X3.two_legs_sum_80"}


def test_a_trail_objective_earns_nothing_and_sets_the_runners_trail():
    # O4 pays 1.5 (the runner at 2R), not 2.7 (at the 6R objective); the preview's trail reads 2.7R beside every stop
    assert tl.plan_pays(_legs("O4.trail_objective_min_1_5")) == 1.5
    for direction in PROBES["O4.trail_objective_min_1_5"]["preview"]["directions"].values():
        assert {s["runnerTrail"]["rMultiple"] for s in direction["setups"]} == {2.7}
    for direction in PROBES["T3.full_plans_trailing_off"]["preview"]["directions"].values():
        assert {s["runnerTrail"] is None for s in direction["setups"]} == {True}       # no runner, no trail


def test_the_refused_previews_name_the_draft_error():
    for name in ("T1.runner_trailing_off", "T2.trail_objective_trailing_off", "W1.r1_30_r3_30_min_2_5",
                 "W2.r1_30_r3_30_min_2_2", "O1.trail_objective_min_2"):
        refused = PROBES[name]["preview"]["refused"]
        assert refused["field"] == PROBES[name]["answer"]["errors"][0]["field"], name


def _runner_menu() -> dict:
    return copy.deepcopy(PROBES["T4.runner_trailing_on"]["sent"]["menu"])


def test_a_plan_reads_trailing_from_its_own_position_management():
    base = PRESETS["trend-continuation"]
    on = plan(Thesis(**{**base.__dict__, "trade_level_menu": _runner_menu()}))
    assert on.axes()["POSITION_MANAGEMENT"]["trailingEnabled"] is True and on.menu_findings() == []
    off = plan(Thesis(**{**base.__dict__, "trade_level_menu": _runner_menu(), "execution": {"trailingEnabled": False}}))
    assert off.axes()["POSITION_MANAGEMENT"]["trailingEnabled"] is False
    assert {f.code for f in off.menu_findings()} == {"TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING"}
    # the default menu (every plan closes 100%) stages with Trailing off: probe T3
    plain = plan(Thesis(**{**base.__dict__, "execution": {"trailingEnabled": False}}))
    assert plain.menu_findings() == []


def test_an_update_that_switches_trailing_off_under_a_live_runner_is_refused():
    # v0.14.1 warned here (every probe was a create). Measured 2026-11-12 at 171.0.0 (tests/test_update_rules_171.py,
    # A2): POSITION_MANAGEMENT staged alone with Trailing off draws the runner's draft error on the menu the strategy holds
    base = PRESETS["trend-continuation"]
    p = plan(Thesis(**{**base.__dict__, "execution": {"trailingEnabled": False}}))
    current = plan(base).axes()
    current["TRADE_LEVEL_POLICY"]["tradeLevelMenu"] = _runner_menu()
    found = p.update_menu_findings(current)
    assert found and {(f.severity, f.code) for f in found} == {
        ("error", "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING")}
    assert all("A2" in f.message for f in found)
    # a TRADE_LEVEL_POLICY update beside the live Trailing off is judged as the create was: an error
    current["POSITION_MANAGEMENT"]["trailingEnabled"] = False
    named = plan(Thesis(**{**base.__dict__, "trade_level_menu": _runner_menu()}))
    assert {(f.severity, f.code) for f in named.update_menu_findings(current)} == {
        ("error", "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING")}


def test_the_off_step_minimum_is_an_execution_error_and_on_step_values_are_not():
    assert {f.code for f in validate_execution({"minRiskRewardRatio": 2.2})} == {"EXECUTION_OFF_STEP"}
    for v in (0.5, 1.5, 2.25, 2.5, 3):
        assert validate_execution({"minRiskRewardRatio": v}) == []
