"""Contract 170: the trade level menu's exit plans (omega/trade_levels.py), replayed against the platform's answers.

data/audit/exit_plans_170_2026-11-12.json holds 32 create stages at 170.0.0 (2026-11-12 09:02 - 09:11Z): 26 drafts
staged, read back and discarded, none committed, and 6 refused at input. Every probe is replayed offline against the
pinned write schema: where the stage answered clean, omega finds no error; where it answered an error or refused the
input, omega raises one on the SAME field. Four of them were staged again at 171.0.0 (whose six draft tools are
byte-identical to 170's) and answered the same (exit_plans_171 in the record's `confirmedAt`).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from omega import trade_levels as tl
from omega.generate import PRESETS, Thesis, plan

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / tl.EXIT_PLAN_PROBES).read_text(encoding="utf-8"))
BASE = RECORD["basePlan"]
PROBES = RECORD["probes"]


def _offline(menu) -> list:
    return tl.validate_menu(menu, dials=BASE["dials"], sections=BASE["reportSections"], anchor=BASE["anchor"])


def _platform_fields(probe: dict) -> list[str]:
    answer = probe["answer"]
    if not answer["staged"]:                    # refused at input: the issue paths, as the menu's own field path
        return [".".join(str(p) for p in issue["path"][2:]) for issue in answer["refusal"]["issues"]]
    return [e["field"] for e in answer["errors"]]


def _field(path: str) -> str:
    """omega names a list position `[i]`; the platform's input issues name it `.i` - one spelling for comparing."""
    return path.replace("[", ".").replace("]", "")


def test_the_record_is_thirty_two_stages_none_committed_and_every_staged_one_discarded():
    assert RECORD["counts"] == {"stages": 32, "staged": 26, "refusedAtInput": 6, "discarded": 26, "committed": 0}
    assert RECORD["measuredAt"][0]["contractVersion"] == RECORD["measuredAt"][0]["versionAtEnd"] == "170.0.0"
    for name, probe in PROBES.items():
        if probe["answer"]["staged"]:
            assert probe["discarded"] is True and probe["draftAfterDiscard"] is None and probe["keptAsSent"], name


def test_the_pinned_schema_names_exit_plans():
    assert tl.menu_form() == "exitPlans" and tl.menu_required() is True
    assert tl.list_bounds("stops") == (1, 8) and tl.list_bounds("exitPlans") == (1, 8) and tl.list_bounds("legs") == (1, 4)


@pytest.mark.parametrize("name", sorted(PROBES))
def test_every_probe_replays_offline_as_the_stage_answered(name):
    probe = PROBES[name]
    found = _offline(probe["sent"]["menu"])
    errors = sorted({_field(f.path) for f in found if f.severity == "error"})
    platform = sorted({_field(f) for f in _platform_fields(probe)})
    if not platform:
        assert errors == [], (name, [str(f) for f in found])
        return
    # the platform names LONG and SHORT on input issues and LONG alone on a draft's errors; omega names both sides
    assert set(platform) <= set(errors), (name, platform, errors)
    assert {e.replace("SHORT", "LONG") for e in errors} == {p.replace("SHORT", "LONG") for p in platform}, name


@pytest.mark.parametrize("name, code", [
    ("X4.two_legs_sum_120", "TRADE_MENU_EXIT_PLAN_OVER_100"),
    ("X5.partial_then_100", "TRADE_MENU_EXIT_PLAN_OVER_100"),
    ("X7.leg_zero_then_100", "TRADE_MENU_EXIT_PLAN_FIRST_LEG_EMPTY"),
    ("X8.legs_out_of_order", "TRADE_MENU_EXIT_PLAN_OUT_OF_ORDER"),
    ("X9.equal_legs", "TRADE_MENU_EXIT_PLAN_OUT_OF_ORDER"),
    ("Z4.adjacent_r_out_of_order_then_level", "TRADE_MENU_EXIT_PLAN_OUT_OF_ORDER"),
    ("Y1.one_leg_r1", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"),
    ("Y4.r1_80_r3_20", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"),
    ("Y6.r1_50_alone", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"),
    ("Y9.level_stop_and_leg", "TRADE_MENU_LEVEL_BOTH_SIDES"),
    ("X13.five_legs", "TRADE_MENU_SHAPE"),
    ("X14.nine_plans", "TRADE_MENU_SHAPE"),
    ("X16.close_pct_101", "TRADE_MENU_SHAPE"),
])
def test_each_rule_has_its_own_code(name, code):
    assert code in {f.code for f in _offline(PROBES[name]["sent"]["menu"]) if f.severity == "error"}


def test_what_a_plan_pays_is_the_weighted_mean_the_stage_states():
    for name, pays in (("Y1.one_leg_r1", 1), ("Y2.r1_50_r1_6_50", 1.3), ("Y3.r1_2_50_r1_4_50", 1.3),
                       ("Y4.r1_80_r3_20", 1.4), ("Y6.r1_50_alone", 1), ("Y7.r1_70_r2_30", 1.3)):
        legs = PROBES[name]["sent"]["menu"]["LONG"]["exitPlans"][0]["targets"]
        assert round(tl.plan_pays(legs), 6) == pays
        assert f"pays {pays}R" in PROBES[name]["answer"]["errors"][0]["message"]
    for name, pays in (("X10.first_leg_below_min_rr", 2), ("Y5.r1_60_r3_40", 1.8), ("Y8.later_leg_zero", 1.5)):
        assert round(tl.plan_pays(PROBES[name]["sent"]["menu"]["LONG"]["exitPlans"][0]["targets"]), 6) == pays
    assert tl.plan_pays(PROBES["Z1.r1_then_level"]["sent"]["menu"]["LONG"]["exitPlans"][0]["targets"]) is None


def test_a_plan_with_a_level_leg_is_judged_per_decision_a_warning():
    for name in ("X15.r_then_level", "Y10.level_leg_first", "Z1.r1_then_level", "Z2.r2_then_level",
                 "Z3.order_across_level"):
        found = _offline(PROBES[name]["sent"]["menu"])
        assert not [f for f in found if f.severity == "error"], name
        assert {f.code for f in found if f.severity == "warning"} == {"TRADE_MENU_EXIT_PLAN_JUDGED_PER_DECISION"}, name


def test_the_default_menu_is_the_platforms_migration_shape():
    menu = tl.default_menu(1.5)
    assert menu["LONG"] == {
        "stops": [{"kind": "ATR", "atrMultiple": m} for m in (1, 1.5, 2)],
        "exitPlans": [{"targets": [{"method": {"kind": "R_MULTIPLE", "multiple": m}, "closePct": 100}]}
                      for m in (1.5, 2, 3)]}
    assert menu == PROBES["X1.single_legs_100"]["sent"]["menu"]          # exactly what the stage accepted clean
    assert [p["targets"][0]["method"]["multiple"] for p in tl.default_menu(2)["SHORT"]["exitPlans"]] == [2, 3]
    assert _offline(menu) == []


def test_a_168_menu_migrates_as_the_platform_migrated_every_stored_one():
    targets = [{"kind": "R_MULTIPLE", "multiple": 1.5}, {"kind": "LEVEL", "level": tl.level_ref("SMA200")}]
    old = {s: {"stops": [{"kind": "ATR", "atrMultiple": 1}], "targets": copy.deepcopy(targets)} for s in tl.SIDES}
    new = tl.migrate_menu(old)
    assert new["LONG"] == {"stops": [{"kind": "ATR", "atrMultiple": 1}],
                           "exitPlans": [{"targets": [{"method": t, "closePct": 100}]} for t in targets]}
    assert tl.migrate_menu(new) == new and tl.migrate_menu(["not a menu"]) == ["not a menu"]
    # a thesis still naming 168's targets stages in the 170 form, on a CREATE and on an UPDATE
    base = PRESETS["trend-continuation"]
    named = plan(Thesis(**{**base.__dict__, "trade_level_menu": old}))
    assert named.axes()["TRADE_LEVEL_POLICY"]["tradeLevelMenu"] == new and named.menu_findings() == []
    current = {"TRADE_LEVEL_POLICY": {**BASE["dials"], "tradeLevelMenu": tl.default_menu(1.5)}}
    assert named.axes_update(current)["TRADE_LEVEL_POLICY"]["tradeLevelMenu"] == new


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_every_preset_stages_exit_plans_with_no_finding(preset):
    p = plan(PRESETS[preset])
    policy = p.axes()["TRADE_LEVEL_POLICY"]
    assert all("exitPlans" in policy["tradeLevelMenu"][s] and "targets" not in policy["tradeLevelMenu"][s]
               for s in tl.SIDES)
    assert p.menu_findings() == []
    assert any("exit plan(s)" in line for line in p.render().splitlines())


def test_a_side_in_both_forms_is_not_migrated_and_the_shape_walk_refuses_it():
    # review 2026-11-12: a side carrying `targets` AND `exitPlans` was migrated, silently replacing its exit plans
    plans = [{"targets": [{"method": {"kind": "R_MULTIPLE", "multiple": 1.5}, "closePct": 50},
                          {"method": {"kind": "R_MULTIPLE", "multiple": 3}, "closePct": 50}]}]
    side = {"stops": [{"kind": "ATR", "atrMultiple": 1}], "targets": [{"kind": "R_MULTIPLE", "multiple": 1.5}],
            "exitPlans": plans}
    both = {s: copy.deepcopy(side) for s in tl.SIDES}
    assert tl.migrate_menu(both) == both
    assert {f.code for f in _offline(both) if f.severity == "error"} == {"TRADE_MENU_SHAPE"}
    # one side in each form: left as written, refused the same way
    half = {"LONG": copy.deepcopy(side) | {"targets": None}, "SHORT": {"stops": side["stops"], "targets": side["targets"]}}
    del half["LONG"]["targets"]
    assert tl.migrate_menu(half) == half
    assert "TRADE_MENU_SHAPE" in {f.code for f in _offline(half) if f.severity == "error"}


def test_a_one_leg_level_plan_is_the_migration_shape_and_carries_no_warning():
    # every live strategy holds its band targets as one-leg LEVEL plans (the platform's migration); at 168 a LEVEL target
    # carried no warning either, so this one does not (review 2026-11-12, finding 2: kept, recorded)
    menu = tl.default_menu(1.5)
    for s in tl.SIDES:
        menu[s]["exitPlans"].append({"targets": [{"method": {"kind": "LEVEL", "level": tl.level_ref("SMA200")},
                                                  "closePct": 100}]})
    assert _offline(menu) == []
