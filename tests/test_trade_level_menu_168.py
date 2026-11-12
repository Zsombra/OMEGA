"""Contract 168: the trade level menu (omega/trade_levels.py), replayed against the platform's own answers.

data/audit/trade_level_menu_168_2026-11-11.json holds thirty create drafts (fifteen at 168.2.0, fifteen at 168.3.0),
each staged, read back and discarded. Every probe is replayed here offline: where the stage answered clean, omega finds
no error; where it answered an error, omega raises one on the SAME field.

Since contract 170 (2026-11-12) the menu's profit side is `exitPlans`, not `targets`: the probes replay against the
168.3.0 capture they were measured on (SCHEMA_168, `schema=`), and the plans omega generates - which follow the pinned
write schema - are judged in the 170 form (tests/test_exit_plans_170.py has the exit plan's own probes).
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from omega import trade_levels as tl
from omega.generate import AXES, PRESETS, Thesis, plan

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_168 = json.loads((ROOT / "data/contract/stage_strategy_draft/schema_20261111T213257Z.json").read_text(encoding="utf-8"))
RECORD = json.loads((ROOT / tl.PROBES).read_text(encoding="utf-8"))
BASE = RECORD["basePlan"]
PROBES = RECORD["probes"]
ANCHOR = {"rel": "anchor"}


def _sections(probe: dict) -> list[dict]:
    sections = copy.deepcopy(BASE["reportSections"])
    if probe["sent"].get("addedColumn"):
        sections[0]["columns"].append(probe["sent"]["addedColumn"])
    return sections


def _offline(probe: dict) -> list:
    found = tl.validate_menu(probe["sent"]["menu"], dials=BASE["dials"], sections=_sections(probe), anchor=BASE["anchor"],
                             schema=SCHEMA_168)
    entry = probe["sent"]["entry"]["entry"]
    return found + tl.validate_entry_levels(entry, sections=_sections(probe), anchor=BASE["anchor"])


def _platform_fields(probe: dict) -> list[str]:
    answer = probe["answer"]
    if not answer["staged"]:                    # refused at input: the issue paths, as the menu's own field path
        return [".".join(str(p) for p in issue["path"][2:]) for issue in answer["refusal"]["issues"]]
    return [e["field"] for e in answer["errors"]]


def _stop_on(ref) -> dict:
    side = {"stops": [{"kind": "LEVEL", "level": ref, "bufferAtrMultiple": 0}],
            "targets": [{"kind": "R_MULTIPLE", "multiple": 2}]}
    return {"LONG": side, "SHORT": copy.deepcopy(side)}


def _codes(menu, sections=None) -> set[str]:
    found = tl.validate_menu(menu, dials=BASE["dials"], sections=sections or BASE["reportSections"], anchor=BASE["anchor"],
                             schema=SCHEMA_168)
    return {f.code for f in found}


def test_the_record_is_thirty_drafts_none_committed_and_every_staged_one_discarded():
    assert RECORD["counts"] == {"probes": 30, "staged": 29, "refusedAtInput": 1, "stagedWithErrors": 10, "discarded": 29}
    assert [m["contractVersion"] for m in RECORD["measuredAt"]] == ["168.2.0", "168.3.0"]
    assert sum(p["contractVersion"] == "168.3.0" for p in PROBES.values()) == 15
    for name, probe in PROBES.items():
        if probe["answer"]["staged"]:
            assert probe["keptAsSent"] is True, name          # the draft stored the menu exactly as sent
            assert probe["discarded"] is True and probe["draftAfterDiscard"] is None, name


@pytest.mark.parametrize("name", sorted(PROBES))
def test_every_probe_replays_offline_as_the_stage_answered(name):
    probe = PROBES[name]
    errors = [f for f in _offline(probe) if f.severity == "error"]
    expected = _platform_fields(probe)
    if not expected:
        assert errors == [], (name, [(f.code, f.path) for f in errors])
        return
    paths = {f.path for f in errors}
    for field in expected:
        assert field in paths, (name, field, sorted(paths))


def test_each_rule_has_its_own_code():
    def codes(name):
        return sorted({f.code for f in _offline(PROBES[name]) if f.severity == "error"})

    assert codes("V3.atr5.r1.outside_dials") == ["TRADE_MENU_TARGET_BELOW_MIN_RR"]
    assert codes("V5.nine_stops") == ["TRADE_MENU_SHAPE"]
    assert codes("V8.level.buffer") == ["TRADE_MENU_LEVEL_BOTH_SIDES"]
    # a non-price reading: ADX through `trajectory` (L1) and, isolating it, through `value` (M2)
    assert codes("L1.level.adx.non_price") == codes("M2.non_price_via_value") == ["TRADE_MENU_LEVEL_NOT_PRICE"]
    for name in ("tc_default_menu", "V10.level.sma200.other_timeframe", "L3a.level.bb_lower.column_knob_level_plain",
                 "L4.level.sma200.offset_1", "E2.on_retest.unyielded_level", "M9.level_bars_all"):
        assert codes(name) == ["TRADE_MENU_LEVEL_NOT_YIELDED"], name


def test_the_measured_envelope_of_a_yielded_level():
    """What the nine envelope probes settled, read back from omega.trade_levels.report_readings."""
    def yields(name):
        return tl.report_readings(_sections(PROBES[name]), BASE["anchor"])[0]

    assert ("SMA50", "1h", (), 0) in yields("M1.price_via_trajectory")          # any transform
    assert ("EMA5", "1h", (), 0) in yields("M6.spread_base")                    # a spread's base ...
    assert ("EMA13", "1h", (), 0) in yields("V2.level.ema13.operand_only")      # ... and its plain operand
    assert ("SMA50", "1h", (), 1) in yields("M3.offset_like_for_like")          # the offset is part of the reading
    assert ("SMA50", "4h", (), 0) in yields("M4.abs_4h_like_for_like")
    assert ("SMA50", "rel:lower", (), 0) in yields("M8.rel_lower_like_for_like")
    assert ("SMA50", "1h", (), 0) in yields("M7.column_abs_anchor_level_rel")   # {abs: 1h} at a 1h anchor IS the anchor
    assert ("BB_LOWER", "1h", (("period", 10),), 0) in yields("L3b.level.bb_lower.column_knob_level_knob")
    developing = tl.report_readings(_sections(PROBES["M5.column_bars_all"]), BASE["anchor"])[1]
    assert developing == {("SMA50", "1h", (), 0)}


def test_an_atr_stop_outside_the_stop_range_is_a_warning_because_the_stage_accepts_it():
    found = _offline(PROBES["V9.atr5.atr0_5.outside_stop_range"])
    assert [f for f in found if f.severity == "error"] == []
    assert sorted((f.code, f.path) for f in found) == sorted(
        ("TRADE_MENU_STOP_OUTSIDE_RANGE", f"tradeLevelMenu.{side}.stops[{i}].atrMultiple")
        for side in tl.SIDES for i in (0, 1))


def test_what_was_not_measured_is_refused_not_guessed():
    extreme = {**tl.level_ref("SMA200"), "windowExtreme": {"transformId": "rollingMax", "window": 5}}
    assert _codes(_stop_on(extreme)) == {"TRADE_MENU_LEVEL_UNMEASURED"}
    # a level asking bars "all": refused where no column reads Developing (M9), unmeasured where one does
    asking_all = {**tl.level_ref("SMA50"), "bars": "all"}
    assert _codes(_stop_on(asking_all)) == {"TRADE_MENU_LEVEL_NOT_YIELDED"}
    developing = copy.deepcopy(BASE["reportSections"])
    developing[0]["columns"].append({"metric": "SMA50", "transformId": "value", "timeframe": ANCHOR, "bars": "all"})
    assert _codes(_stop_on(asking_all), developing) == {"TRADE_MENU_LEVEL_UNMEASURED"}
    # a metric the report holds only in a market / reference section, or only as the operand of a spread with an offset
    market = copy.deepcopy(BASE["reportSections"])
    market[1]["columns"].append({"metric": "SMA50", "transformId": "value", "timeframe": ANCHOR})
    assert market[1]["marketScope"] is not None
    assert _codes(_stop_on(tl.level_ref("SMA50")), market) == {"TRADE_MENU_LEVEL_UNMEASURED"}
    shifted = copy.deepcopy(BASE["reportSections"])
    shifted[0]["columns"].append({"metric": "CLOSE", "transformId": "spread", "timeframe": ANCHOR, "offset": 1,
                                  "inputs": [{"metric": "SMA50"}]})
    assert _codes(_stop_on(tl.level_ref("SMA50")), shifted) == {"TRADE_MENU_LEVEL_UNMEASURED"}
    # {rel: lower} against the same rung spelled absolutely: only the anchor's equivalence was measured
    lower = copy.deepcopy(BASE["reportSections"])
    lower[0]["columns"].append({"metric": "SMA50", "transformId": "value", "timeframe": {"abs": "15m"}})
    assert _codes(_stop_on({**tl.level_ref("SMA50"), "timeframe": {"rel": "lower"}}), lower) == {
        "TRADE_MENU_LEVEL_NOT_YIELDED"}


@pytest.mark.parametrize("ref, where", [
    ({k: v for k, v in tl.level_ref("SMA200").items() if k != "windowExtreme"}, "level.windowExtreme"),
    ({**tl.level_ref("SMA200"), "timeframe": "1h"}, "level.timeframe"),
    ({**tl.level_ref("SMA200"), "timeframe": {"rel": "anchor", "abs": "4h"}}, "level.timeframe"),
    ({**tl.level_ref("SMA200"), "offset": None}, "level.offset"),
    ({**tl.level_ref("SMA200"), "offset": False}, "level.offset"),
    ({**tl.level_ref("SMA200"), "knobs": {"period": True}}, "level.knobs.period"),
    ({**tl.level_ref("SMA200"), "knobs": {"notAKnob": 3}}, "level.knobs"),
    ({**tl.level_ref("SMA200"), "metric": ["SMA200"]}, "level.metric"),
    ({**tl.level_ref("SMA200"), "extra": 1}, "level"),
])
def test_a_level_the_write_schema_refuses_is_a_shape_finding_never_a_crash(ref, where):
    """Review 2026-11-12: each of these was accepted, or raised, before the menu was walked against the write schema."""
    found = tl.validate_menu(_stop_on(ref), dials=BASE["dials"], sections=BASE["reportSections"], anchor=BASE["anchor"],
                             schema=SCHEMA_168)
    assert found and {f.code for f in found} <= {"TRADE_MENU_SHAPE", "TRADE_MENU_LEVEL_UNKNOWN_METRIC"}
    assert any(where in f.path for f in found), [(f.code, f.path) for f in found]


@pytest.mark.parametrize("menu", [
    None, [], "menu", {"LONG": {}}, {"LONG": [], "SHORT": []},
    {"LONG": {"stops": [{"kind": ["ATR"], "atrMultiple": 1}], "targets": [{"kind": "R_MULTIPLE", "multiple": 2}]},
     "SHORT": {"stops": [{"kind": "ATR", "atrMultiple": 1}], "targets": [{"kind": "R_MULTIPLE", "multiple": 2}]}},
    {"LONG": {"stops": [{"kind": "ATR", "atrMultiple": True}], "targets": [{"kind": "R_MULTIPLE", "multiple": 2}]},
     "SHORT": {"stops": [{"kind": "ATR", "atrMultiple": 1}], "targets": [{"kind": "R_MULTIPLE", "multiple": 2}]}},
    {"LONG": {"stops": [{"kind": "LEVEL", "level": tl.level_ref("SMA200"), "bufferAtrMultiple": math.nan}],
              "targets": [{"kind": "R_MULTIPLE", "multiple": 2}]},
     "SHORT": {"stops": [{"kind": "ATR", "atrMultiple": 1}], "targets": [{"kind": "R_MULTIPLE", "multiple": 2}]}},
])
def test_a_malformed_menu_is_a_shape_finding_never_a_crash(menu):
    found = tl.validate_menu(menu, dials=BASE["dials"], sections=BASE["reportSections"], anchor=BASE["anchor"],
                             schema=SCHEMA_168)
    assert found and {f.code for f in found} == {"TRADE_MENU_SHAPE"} and all(f.severity == "error" for f in found)


def test_an_unserved_or_malformed_level_metric_is_its_own_code():
    assert _codes(_stop_on(tl.level_ref("NOT_A_METRIC"))) == {"TRADE_MENU_LEVEL_UNKNOWN_METRIC"}
    assert _codes(_stop_on(tl.level_ref("sma 200"))) == {"TRADE_MENU_LEVEL_UNKNOWN_METRIC"}


def test_the_default_menu_is_the_atr_and_r_part_of_the_platforms_migration_default():
    # read 2026-11-11 from three live strategies: ATR 1 / 1.5 / 2 whatever the stop range, R from the minimum up
    assert tl.default_menu(1.5, SCHEMA_168)["LONG"] == {
        "stops": [{"kind": "ATR", "atrMultiple": m} for m in (1, 1.5, 2)],
        "targets": [{"kind": "R_MULTIPLE", "multiple": m} for m in (1.5, 2, 3)]}
    assert [t["multiple"] for t in tl.default_menu(2, SCHEMA_168)["SHORT"]["targets"]] == [2, 3]   # VWAP Reject 4h, TPO LONG
    assert [t["multiple"] for t in tl.default_menu(2.5, SCHEMA_168)["LONG"]["targets"]] == [3]
    assert [t["multiple"] for t in tl.default_menu(3, SCHEMA_168)["LONG"]["targets"]] == [3]
    menu = tl.default_menu(1.5, SCHEMA_168)
    assert menu["LONG"] == menu["SHORT"] and menu["LONG"] is not menu["SHORT"]
    assert PROBES["tc_atr_r_menu"]["sent"]["menu"] == menu          # exactly the menu the stage accepted clean
    # a dial that is not a number is the axis walk's to refuse: the menu builder does not raise on it
    for bad in ("2", None, True, math.nan):
        assert [t["multiple"] for t in tl.default_menu(bad, SCHEMA_168)["LONG"]["targets"]] == [1.5, 2, 3]


def test_the_schema_bounds_are_read_from_the_pinned_write_surface():
    assert tl.menu_required(SCHEMA_168) is True and tl.menu_form(SCHEMA_168) == "targets"
    assert tl.list_bounds("stops", SCHEMA_168) == (1, 8) and tl.list_bounds("targets", SCHEMA_168) == (1, 8)
    assert len(tl.level_knobs(SCHEMA_168)) == 26 and {"period", "stdDev", "usedUpOnClose"} <= set(tl.level_knobs(SCHEMA_168))
    side = {"stops": [{"kind": "ATR", "atrMultiple": 6}], "targets": [{"kind": "R_MULTIPLE", "multiple": 11}]}
    found = tl.validate_menu({"LONG": side, "SHORT": copy.deepcopy(side)}, dials=BASE["dials"],
                             sections=BASE["reportSections"], anchor=BASE["anchor"], schema=SCHEMA_168)
    assert {(f.code, f.path.rsplit(".", 1)[-1]) for f in found if f.severity == "error"} == {
        ("TRADE_MENU_SHAPE", "atrMultiple"), ("TRADE_MENU_SHAPE", "multiple")}


def test_an_entry_is_judged_by_the_write_schema_and_its_levels_by_the_menus_rule():
    sections, anchor = BASE["reportSections"], BASE["anchor"]

    def entry_codes(entry):
        return [(f.code, f.path) for f in tl.validate_entry_levels(entry, sections=sections, anchor=anchor)]

    assert entry_codes({"trigger": "ON_CANDLE_CLOSE"}) == []
    levelled = {"trigger": "ON_RETEST", "levelOffsetAtrMultiple": 0.1, "validForBars": 4,
                "levels": {"LONG": tl.level_ref("SMA200"), "SHORT": tl.level_ref("SMA200")}}
    assert entry_codes(levelled) == []
    # review 2026-11-12: an unknown or missing trigger carrying `levels` returned no finding at all
    for entry in ({"trigger": "AT_MARKET", "levels": levelled["levels"]}, {"levels": levelled["levels"]},
                  {"trigger": "ON_CANDLE_CLOSE", "levels": levelled["levels"]},
                  {k: v for k, v in levelled.items() if k != "levels"}, "ON_RETEST", None):
        found = entry_codes(entry)
        assert found and {code for code, _ in found} == {"ENTRY_LEVELS_SHAPE"}, entry
    one_sided = {**levelled, "levels": {"LONG": tl.level_ref("SMA200")}}
    assert {code for code, _ in entry_codes(one_sided)} == {"ENTRY_LEVELS_SHAPE"}


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_every_preset_stages_the_default_menu_with_no_finding(preset):
    p = plan(PRESETS[preset])
    policy = p.axes()["TRADE_LEVEL_POLICY"]
    assert list(policy) == ["minAtrPct", "minStopLossAtrMultiple", "maxStopLossAtrMultiple", "minRiskRewardRatio",
                            "tradeLevelMenu"]
    assert policy["tradeLevelMenu"] == tl.default_menu(policy["minRiskRewardRatio"])
    assert p.menu_findings() == []
    assert any(line.startswith("trade level menu: default") for line in p.critique())


def test_a_thesis_minimum_moves_the_default_targets_and_a_thesis_menu_wins():
    base = PRESETS["trend-continuation"]
    raised = plan(Thesis(**{**base.__dict__, "execution": {"minRiskRewardRatio": 2}}))
    # the plan follows the pinned write schema: since contract 170 each R target is a one-leg exit plan
    plans = raised.axes()["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]["LONG"]["exitPlans"]
    assert [p["targets"][0]["method"]["multiple"] for p in plans] == [2, 3]
    own = tl.default_menu(1.5)
    own["LONG"]["stops"].append({"kind": "LEVEL", "level": tl.level_ref("SMA200"), "bufferAtrMultiple": 0.5})
    named = plan(Thesis(**{**base.__dict__, "trade_level_menu": own}))
    assert named.axes()["TRADE_LEVEL_POLICY"]["tradeLevelMenu"] == own
    assert named.menu_findings() == []                    # the preset's report reads SMA200 (distance): probe V1
    below = tl.default_menu(1.5)
    refused = plan(Thesis(**{**base.__dict__, "execution": {"minRiskRewardRatio": 2}, "trade_level_menu": below}))
    assert {f.code for f in refused.menu_findings()} == {"TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"}     # 170: what a plan pays
    assert any(line.startswith("trade level menu error") for line in refused.critique())
    # a menu that is not a menu: findings and a critique line, never an exception (review 2026-11-12)
    broken = plan(Thesis(**{**base.__dict__, "trade_level_menu": ["not", "a", "menu"]}))
    assert {f.code for f in broken.menu_findings()} == {"TRADE_MENU_SHAPE"}
    assert any(line.startswith("trade level menu error") for line in broken.critique())


def test_an_update_carries_the_live_menu_and_never_invents_one():
    base = PRESETS["trend-continuation"]
    # the platform's migration default, bands included, as 170 holds it (each target a one-leg exit plan)
    live_menu = tl.migrate_menu(PROBES["tc_default_menu"]["sent"]["menu"])
    current = {"TRADE_LEVEL_POLICY": {**BASE["dials"], "tradeLevelMenu": live_menu}}

    untouched = plan(base)
    assert "TRADE_LEVEL_POLICY" not in untouched.axes_update(current)          # no dial and no menu named: not staged
    # the axis is not staged, but REPORT is, and the live menu names bands the new report does not read. v0.14.1 warned
    # (every probe was a create); measured 2026-11-12 at 171.0.0, the stage re-judges the menu it is not sent - REPORT
    # staged alone without the Bollinger columns drew the level refusal on the COMMITTED menu (tests/
    # test_update_rules_171.py, probe A3) - so it is an error
    would = untouched.update_menu_findings(current)
    assert would and {(f.severity, f.code) for f in would} == {("error", "TRADE_MENU_LEVEL_NOT_YIELDED")}
    assert all("A3" in f.message for f in would)
    # no live menu read: e52f745 passed it ([]) while the stage judges the menu omega never saw - refused, failing
    # closed (v0.14.2 review, 2026-11-12; tests/test_update_rules_171.py, a partial `current`)
    unread = untouched.update_menu_findings({"TRADE_LEVEL_POLICY": dict(BASE["dials"])})
    assert [(f.severity, f.code, f.path) for f in unread] == [
        ("error", "TRADE_MENU_LIVE_UNKNOWN", "TRADE_LEVEL_POLICY.tradeLevelMenu")]

    dial = plan(Thesis(**{**base.__dict__, "execution": {"minAtrPct": 0.4}}))
    staged = dial.axes_update(current)["TRADE_LEVEL_POLICY"]
    assert staged["minAtrPct"] == 0.4 and staged["tradeLevelMenu"] == live_menu          # carried verbatim
    assert staged["tradeLevelMenu"] is not live_menu
    # the migrated menu names bands this report does not read: the stage refuses the axis, and omega says so first
    found = dial.update_menu_findings(current)
    assert {(f.severity, f.code) for f in found} == {("error", "TRADE_MENU_LEVEL_NOT_YIELDED")}
    with pytest.raises(ValueError, match="never invents a live strategy's menu"):
        dial.axes_update({"TRADE_LEVEL_POLICY": dict(BASE["dials"])})

    own = tl.default_menu(1.5)
    named = plan(Thesis(**{**base.__dict__, "trade_level_menu": own}))
    update = named.axes_update(current)
    staged = update["TRADE_LEVEL_POLICY"]
    assert staged["tradeLevelMenu"] == own and {k: staged[k] for k in BASE["dials"]} == BASE["dials"]
    assert named.update_menu_findings(current) == []
    # a menu-only update keeps the axes in the published order (TRADE_LEVEL_POLICY before POSITION_MANAGEMENT)
    both = plan(Thesis(**{**base.__dict__, "trade_level_menu": own, "execution": {"trailingTriggerR": 1.5}}))
    full = {**current, "POSITION_MANAGEMENT": plan(base).axes()["POSITION_MANAGEMENT"]}
    assert list(both.axes_update(full)) == [a for a in AXES if a != "ENTRY"]
