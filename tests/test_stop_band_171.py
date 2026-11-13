"""OMEGA v0.14.3 (2026-11-13): a trade level menu ATR stop outside the strategy's own stop range, replayed offline.

data/audit/stop_band_171_2026-11-12.json holds three sources:

  storedAt168_4  preview_strategy_trade_levels on BTC at 168.4.0 (2026-11-12 00:56Z) on three committed strategies:
                 ATR 2 against maxStopLossAtrMultiple 1.8 (VWAP Reject 4h, TPO Prior Session Levels LONG) reads verdict
                 ABOVE_CEILING, responsibleBound MAX_STOP_LOSS_ATR_MULTIPLE, and makes no setup and no refused pair;
                 ATR 2 at a maximum of 2 (Dunkirk) and ATR 1 at a minimum of 1 survive.
  stage168_2     probe V9 (168.2.0): ATR 5 and ATR 0.5 against the range 1 - 2 staged clean.
  B1             one CREATE draft at 171.0.0 (2026-11-12 23:55Z): the range 0.8 - 1.8 and ATR stops 0.5 / 0.8 / 1 /
                 1.5 / 1.8 / 2 staged clean; at the decision 0.5 read BELOW_FLOOR / MIN_STOP_LOSS_ATR_MULTIPLE and 2
                 ABOVE_CEILING / MAX_STOP_LOSS_ATR_MULTIPLE, both in no setup and no refused pair, and the stops on the
                 two bounds survived. Discarded and read null; nothing committed.

So the stage never judges the range, and a decision DROPS an ATR stop outside it - not an error, not clamped to the
bound. An ATR stop's distance in ATR is its multiple, so it is dropped on every coin at every decision.
omega.trade_levels.default_menu offers only the default ATR stops inside the thesis's range (the range's own bounds
when none of them is), and validate_menu warns on a menu stop outside it, as the stage accepts it. Nothing here calls
the platform.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from omega import trade_levels as tl
from omega.execution import ENFORCED_STEPS, off_step, validate_execution
from omega.generate import PRESETS, Thesis, plan

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / tl.STOP_BAND_PROBES).read_text(encoding="utf-8"))
B1 = RECORD["probes"]["B1.range_0_8_1_8"]
SENT = B1["sent"]["axes"]
DIALS = {k: v for k, v in SENT["TRADE_LEVEL_POLICY"].items() if k != "tradeLevelMenu"}
VERSION = ("171.0.0", "588e449aa4cb93b3d805c360ce1e6c55f0037951")
DROPPED = {"BELOW_FLOOR": "MIN_STOP_LOSS_ATR_MULTIPLE", "ABOVE_CEILING": "MAX_STOP_LOSS_ATR_MULTIPLE"}
READ_TOOLS = {"get_strategy_draft", "list_strategy_drafts", "preview_strategy_trade_levels"}
DRAFT_WRITES = {"stage_strategy_draft", "discard_strategy_draft"}


def _previews():
    """Every stored decision: (where, direction, its answer digest) - B1 at 171.0.0 and the three 168.4.0 reads."""
    for direction, d in B1["preview"]["directions"].items():
        yield "B1", direction, d
    for name, stored in RECORD["storedAt168_4"]["previews"].items():
        for direction, d in stored["directions"].items():
            yield name, direction, d


def _atr_stops(menu_side: dict) -> list:
    return [s["atrMultiple"] for s in menu_side["stops"] if s["kind"] == "ATR"]


def _findings(menu, dials=None):
    return tl.validate_menu(menu, dials=dials or DIALS, sections=SENT["REPORT"]["sections"],
                            anchor=SENT["TIMEFRAME_PROFILE"]["timeframe"],
                            trailing_enabled=SENT["POSITION_MANAGEMENT"]["trailingEnabled"])


# --- the record --------------------------------------------------------------------------------------------------------
def test_the_record_is_complete_and_nothing_was_committed():
    reads = RECORD["measuredAt"]["versionReads"]
    assert [r["tag"] for r in reads] == ["before", "after"]
    assert all((r["contractVersion"], r["buildSha"]) == VERSION for r in reads)
    calls = RECORD["calls"]
    assert calls["total"] == len(calls["lines"]) == sum(calls["byTool"].values()) == 7
    assert set(calls["byTool"]) <= READ_TOOLS | DRAFT_WRITES, "only reads, one stage and its discard"
    assert RECORD["counts"]["committed"] == calls["byTool"].get("commit_strategy_draft", 0) == 0
    assert RECORD["counts"] == {"stages": 1, "staged": 1, "discarded": 1, "committed": 0, "tradeLevelPreviews": 1}
    assert [c["tool"] for c in calls["lines"]] == ["stage_strategy_draft", "get_strategy_draft",
                                                   "preview_strategy_trade_levels", "get_strategy_draft",
                                                   "discard_strategy_draft", "get_strategy_draft",
                                                   "list_strategy_drafts"]
    assert B1["sentAt"] == calls["lines"][B1["callLine"]]["at"]
    assert B1["discard"]["answer"] == {"strategyId": B1["answer"]["strategyId"], "discarded": True}
    assert B1["draftAfterDiscard"] is None and B1["draftVersionAfterDiscard"] == 0
    listed = RECORD["listStrategyDraftsAtEnd"]["answer"]["drafts"]
    assert B1["answer"]["strategyId"] not in {d["strategyId"] for d in listed}
    assert B1["readBack"]["impact"]["operation"] == "CREATE" and B1["readBack"]["impact"]["boundAgentCount"] == 0
    # the three 168.4.0 reads are previews of COMMITTED strategies (read-only), each named by its file's sha256
    for stored in RECORD["storedAt168_4"]["previews"].values():
        assert stored["source"]["kind"] == "COMMITTED" and len(stored["sha256"]) == 64


def test_b1_was_read_back_as_sent_and_previewed_on_its_draft():
    assert B1["readBack"]["comparedWithSent"]["canonicalEqual"] is True
    assert B1["readBack"]["content"]["TRADE_LEVEL_POLICY"] == SENT["TRADE_LEVEL_POLICY"]
    assert B1["preview"]["args"]["source"] == {"kind": "DRAFT", "strategyId": B1["answer"]["strategyId"],
                                               "draftVersion": B1["readBack"]["draftVersion"]}
    for d in B1["preview"]["directions"].values():
        assert d["band"] == {"minStopLossAtrMultiple": 0.8, "maxStopLossAtrMultiple": 1.8}
        assert d["stage"] == "OK" and d["rejectedPairCount"] == 0      # every plan pays >= 1.5: only stops are dropped


# --- what the platform does --------------------------------------------------------------------------------------------
def test_the_stage_accepts_a_stop_outside_the_range():
    assert B1["answer"]["staged"] and B1["answer"]["errors"] == [] and B1["answer"]["warnings"] == []
    assert B1["readBack"]["diagnostics"] == {"errors": [], "warnings": []}
    v9 = RECORD["stage168_2"]
    assert v9["answer"] == {"staged": True, "errors": [], "warnings": []} and v9["contractVersion"] == "168.2.0"
    assert [s["atrMultiple"] for s in v9["sent"]["LONG"]["stops"]] == [5, 0.5]       # both outside 1 - 2


def test_a_decision_drops_every_atr_stop_outside_the_range_and_keeps_both_bounds():
    seen = {"BELOW_FLOOR": 0, "ABOVE_CEILING": 0, "SURVIVED": 0}
    for where, direction, d in _previews():
        lo, hi = d["band"]["minStopLossAtrMultiple"], d["band"]["maxStopLossAtrMultiple"]
        made = {json.dumps(s, sort_keys=True) for stops in d["setupStops"] + d["rejectedPairStops"] for s in
                (stops if isinstance(stops, list) else [stops])}
        for c in d["stopCandidates"]:
            if c["method"]["kind"] != "ATR":
                continue
            m = c["method"]["atrMultiple"]
            verdict = tl.outside_stop_range(m, lo, hi)
            assert c["verdict"] == (verdict or "SURVIVED"), (where, direction, m)
            seen[c["verdict"]] += 1
            if verdict:
                assert c["responsibleBound"] == DROPPED[verdict], (where, direction, m)
                # dropped before pairing: in no setup and no refused pair
                assert json.dumps(c["method"], sort_keys=True) not in made, (where, direction, m)
            else:
                assert json.dumps(c["method"], sort_keys=True) in made, (where, direction, m)
    # B1 dropped 0.5 and 2 per side, 168.4.0 dropped ATR 2 on both sides of two strategies; on a bound it survives
    assert seen == {"BELOW_FLOOR": 2, "ABOVE_CEILING": 6, "SURVIVED": 22}
    b1 = B1["preview"]["directions"]["LONG"]
    on_bounds = {c["method"]["atrMultiple"]: c["verdict"] for c in b1["stopCandidates"]}
    assert on_bounds[0.8] == on_bounds[1.8] == "SURVIVED"       # inclusive: neither bound is a whole number
    assert b1["counters"]["stopsRemovedByFloor"] == b1["counters"]["stopsRemovedByCeiling"] == 1


def test_the_threshold_a_stop_is_refused_by_is_the_range_times_the_atr():
    for where, direction, d in _previews():
        atr_pct = d["snapshot"]["atrPct"]
        for c in d["stopCandidates"]:
            if c["verdict"] in DROPPED:
                bound = d["band"]["minStopLossAtrMultiple" if c["verdict"] == "BELOW_FLOOR"
                                  else "maxStopLossAtrMultiple"]
                assert math.isclose(c["rejectedByThresholdPct"], bound * atr_pct, rel_tol=1e-9), (where, direction)
        assert math.isclose(d["hardStopDistancePct"], d["band"]["maxStopLossAtrMultiple"] * atr_pct, rel_tol=1e-9)


def test_a_level_stop_is_dropped_by_its_distance_at_the_decision_which_omega_cannot_read_offline():
    """BB_UPPER at 1.85 ATR and DONCHIAN_UPPER at 2.2 ATR against 1.8 (168.4.0, SHORT): the same ceiling, read on the
    level's distance at that bar. omega judges an ATR stop only: a level's distance is per coin and per bar."""
    dropped_levels = [(name, c["method"]["level"]["metric"], c["distanceAtrMultiple"])
                      for name, direction, d in _previews() for c in d["stopCandidates"]
                      if c["method"]["kind"] == "LEVEL" and c["verdict"] == "ABOVE_CEILING"]
    assert dropped_levels and all(dist > 1.8 for _, _, dist in dropped_levels)
    level_side = {"stops": [{"kind": "LEVEL", "level": tl.level_ref("SMA200"), "bufferAtrMultiple": 0}],
                  "exitPlans": tl.default_menu(1.5)["LONG"]["exitPlans"]}
    found = _findings({"LONG": level_side, "SHORT": copy.deepcopy(level_side)})
    assert not [f for f in found if f.code == "TRADE_MENU_STOP_OUTSIDE_RANGE"]


# --- what omega does -----------------------------------------------------------------------------------------------------
def test_validate_menu_warns_exactly_the_stops_a_decision_drops():
    menu = SENT["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]
    found = _findings(menu)
    assert [f for f in found if f.severity == "error"] == [], "the stage accepted this menu clean"
    warned = sorted((f.code, f.path) for f in found)
    assert warned == sorted(("TRADE_MENU_STOP_OUTSIDE_RANGE", f"tradeLevelMenu.{side}.stops[{i}].atrMultiple")
                            for side in tl.SIDES for i in (0, 5))           # ATR 0.5 and ATR 2
    by_path = {f.path: f.message for f in found}
    assert "BELOW_FLOOR" in by_path["tradeLevelMenu.LONG.stops[0].atrMultiple"]
    assert "ABOVE_CEILING" in by_path["tradeLevelMenu.LONG.stops[5].atrMultiple"]
    for message in by_path.values():
        assert "drops it" in message and "not measured" not in message
    # the three 168.4.0 strategies: their ATR stops against their own ranges warn exactly where the decision dropped
    for name, stored in RECORD["storedAt168_4"]["previews"].items():
        for direction, d in stored["directions"].items():
            lo, hi = d["band"]["minStopLossAtrMultiple"], d["band"]["maxStopLossAtrMultiple"]
            stops = [c["method"] for c in d["stopCandidates"] if c["method"]["kind"] == "ATR"]
            side = {"stops": stops, "exitPlans": tl.default_menu(2)["LONG"]["exitPlans"]}
            got = _findings({"LONG": side, "SHORT": copy.deepcopy(side)},
                            dials={**DIALS, "minStopLossAtrMultiple": lo, "maxStopLossAtrMultiple": hi,
                                   "minRiskRewardRatio": 2})
            warned = {f.path for f in got if f.code == "TRADE_MENU_STOP_OUTSIDE_RANGE" and ".LONG." in f.path}
            dropped = {f"tradeLevelMenu.LONG.stops[{i}].atrMultiple" for i, c in
                       enumerate(c for c in d["stopCandidates"] if c["method"]["kind"] == "ATR")
                       if c["verdict"] in DROPPED}
            assert warned == dropped, (name, direction)


def test_the_default_menu_offers_only_stops_the_decision_keeps():
    # B1's range (TPO Prior Session Levels LONG's): ATR 2 is dropped, 1 and 1.5 survive
    menu = tl.default_menu(1.5, stop_range=(0.8, 1.8))
    assert _atr_stops(menu["LONG"]) == _atr_stops(menu["SHORT"]) == [1, 1.5]
    survived = {c["method"]["atrMultiple"] for c in B1["preview"]["directions"]["LONG"]["stopCandidates"]
                if c["verdict"] == "SURVIVED"}
    assert set(_atr_stops(menu["LONG"])) <= survived
    assert not [f for f in _findings(menu) if f.code == "TRADE_MENU_STOP_OUTSIDE_RANGE"]
    # each stored strategy's range keeps exactly the default stops its decision kept
    for name, stored in RECORD["storedAt168_4"]["previews"].items():
        d = stored["directions"]["LONG"]
        lo, hi = d["band"]["minStopLossAtrMultiple"], d["band"]["maxStopLossAtrMultiple"]
        kept = [c["method"]["atrMultiple"] for c in d["stopCandidates"]
                if c["method"]["kind"] == "ATR" and c["verdict"] == "SURVIVED"]
        assert sorted(_atr_stops(tl.default_menu(2, stop_range=(lo, hi))["LONG"])) == sorted(kept), name
    # the exit plans are untouched by the range
    assert menu["LONG"]["exitPlans"] == tl.default_menu(1.5)["LONG"]["exitPlans"]


def test_the_default_menu_falls_back_to_the_ranges_own_bounds_when_no_default_stop_is_inside():
    """A bound survives the decision (B1: 0.8 and 1.8). A bound above the write schema's ATR maximum is not
    stageable, so it is not offered; with no stageable bound the three defaults stay (and validate_menu warns)."""
    assert tl.atr_stop_bounds() == (0, 5)
    for stop_range, stops in (((2.5, 4), [2.5, 4]), ((1.2, 1.2), [1.2]), ((1.6, 1.9), [1.6, 1.9]),
                              ((0.3, 0.6), [0.3, 0.6]), ((2.5, 6), [2.5]), ((2, 3), [2]), ((1, 1.5), [1, 1.5]),
                              ((6, 8), [1, 1.5, 2]), ((-1, 0), [1, 1.5, 2])):
        menu = tl.default_menu(1.5, stop_range=stop_range)
        assert _atr_stops(menu["LONG"]) == _atr_stops(menu["SHORT"]) == stops, stop_range
    found = _findings(tl.default_menu(1.5, stop_range=(6, 8)),
                      dials={**DIALS, "minStopLossAtrMultiple": 6, "maxStopLossAtrMultiple": 8})
    assert {f.code for f in found} == {"TRADE_MENU_STOP_OUTSIDE_RANGE"} and len(found) == 6


def test_a_range_the_builder_cannot_read_keeps_the_three_defaults():
    """The dials are the axis walk's to judge (as default_menu leaves a minRiskRewardRatio that is not a number)."""
    assert _atr_stops(tl.default_menu(1.5)["LONG"]) == [1, 1.5, 2]          # no range given: as before v0.14.3
    for stop_range in (None, ("1", 2), (True, 2), (math.nan, 2), (1, math.inf), (None, 2), (2, 1)):
        assert _atr_stops(tl.default_menu(1.5, stop_range=stop_range)["LONG"]) == [1, 1.5, 2], stop_range
    assert tl.outside_stop_range(1, math.nan, 2) is None and tl.outside_stop_range(math.nan, 1, 2) is None
    assert tl.outside_stop_range(True, 0, 2) is None
    # inclusive and exact on the bounds the thesis wrote
    assert tl.outside_stop_range(0.8, 0.8, 1.8) is None and tl.outside_stop_range(1.8, 0.8, 1.8) is None
    assert tl.outside_stop_range(0.5, 0.8, 1.8) == "BELOW_FLOOR" and tl.outside_stop_range(2, 0.8, 1.8) == "ABOVE_CEILING"


def test_a_plan_stages_the_stops_its_range_keeps():
    base = PRESETS["trend-continuation"]
    narrow = plan(Thesis(**{**base.__dict__, "execution": {"minStopLossAtrMultiple": 0.8,
                                                           "maxStopLossAtrMultiple": 1.8}}))
    policy = narrow.axes()["TRADE_LEVEL_POLICY"]
    assert (policy["minStopLossAtrMultiple"], policy["maxStopLossAtrMultiple"]) == (0.8, 1.8)
    assert _atr_stops(policy["tradeLevelMenu"]["LONG"]) == _atr_stops(policy["tradeLevelMenu"]["SHORT"]) == [1, 1.5]
    assert narrow.menu_findings() == []
    assert narrow.trade_level_menu() == tl.default_menu(1.5, stop_range=(0.8, 1.8))
    # the platform's default range keeps all three: every preset's menu is as before
    assert _atr_stops(plan(base).axes()["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]["LONG"]) == [1, 1.5, 2]
    # a thesis's own menu is staged as written, and its stops outside the range are warned, not dropped
    own = plan(Thesis(**{**base.__dict__, "execution": {"maxStopLossAtrMultiple": 1.8},
                         "trade_level_menu": tl.default_menu(1.5)}))
    assert _atr_stops(own.axes()["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]["LONG"]) == [1, 1.5, 2]
    assert sorted((f.severity, f.code, f.path) for f in own.menu_findings()) == sorted(
        ("warning", "TRADE_MENU_STOP_OUTSIDE_RANGE", f"tradeLevelMenu.{side}.stops[2].atrMultiple")
        for side in tl.SIDES)


def test_an_update_narrowing_the_range_warns_on_the_live_stops_it_carries():
    """An UPDATE naming a range dial restages TRADE_LEVEL_POLICY whole with the live menu carried verbatim: the live
    ATR 2 under a new maximum of 1.8 is a dead option at every decision, and is warned - the stage accepts it."""
    base = PRESETS["trend-continuation"]
    p = plan(Thesis(**{**base.__dict__, "execution": {"maxStopLossAtrMultiple": 1.8}}))
    live = {**{k: v for k, v in DIALS.items()}, "minStopLossAtrMultiple": 1, "maxStopLossAtrMultiple": 2,
            "tradeLevelMenu": tl.default_menu(1.5)}
    current = {"TRADE_LEVEL_POLICY": live, "POSITION_MANAGEMENT": copy.deepcopy(SENT["POSITION_MANAGEMENT"]),
               "REPORT": copy.deepcopy(SENT["REPORT"])}
    axes = p.axes_update(current)
    assert axes["TRADE_LEVEL_POLICY"]["tradeLevelMenu"] == live["tradeLevelMenu"]      # carried, never rewritten
    found = p.update_menu_findings(current)
    assert [f for f in found if f.severity == "error"] == []
    assert sorted((f.code, f.path) for f in found) == sorted(
        ("TRADE_MENU_STOP_OUTSIDE_RANGE", f"tradeLevelMenu.{side}.stops[2].atrMultiple") for side in tl.SIDES)


def test_the_range_dials_take_no_quarter_step():
    """B1 staged minStopLossAtrMultiple 0.8 and maxStopLossAtrMultiple 1.8 with no draft error: the 0.25 step the
    stage enforces on minRiskRewardRatio (W2) is not enforced on the two range dials."""
    assert "minStopLossAtrMultiple" not in ENFORCED_STEPS and "maxStopLossAtrMultiple" not in ENFORCED_STEPS
    assert not off_step("minStopLossAtrMultiple", 0.8) and not off_step("maxStopLossAtrMultiple", 1.8)
    assert not [f for f in validate_execution({"minStopLossAtrMultiple": 0.8, "maxStopLossAtrMultiple": 1.8})
                if f.code == "EXECUTION_OFF_STEP"]


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_every_preset_keeps_its_default_menu(preset):
    p = plan(PRESETS[preset])
    policy = p.axes()["TRADE_LEVEL_POLICY"]
    rng = (policy["minStopLossAtrMultiple"], policy["maxStopLossAtrMultiple"])
    assert policy["tradeLevelMenu"] == tl.default_menu(policy["minRiskRewardRatio"], stop_range=rng)
    assert not [f for f in p.menu_findings() if f.code == "TRADE_MENU_STOP_OUTSIDE_RANGE"]
