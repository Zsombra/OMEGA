"""OMEGA v0.18.0 at contract 185.2.0: the trade bracket replaces the trade level menu.

`stage_strategy_draft` requires TRADE_LEVEL_POLICY.tradeBracket = {LONG, SHORT}, each {stop, exitPlan} - ONE stop and
ONE exit plan per direction; `tradeLevelMenu` is no property of the axis any more (omega/trade_levels.py, the 185
section). The live input schema is tests/fixtures/contract_185/stage_strategy_draft_185_2_0.json, copied verbatim from
battlegrid-manager's contract-watch row; the platform's default bracket was measured on one create draft
(data/audit/default_bracket_185_2026-11-27.json).
"""
from __future__ import annotations

import copy
import inspect
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

import omega.generate as G
import omega.trade_levels as tl
from omega import preflight as P
from omega.contract import stage_schema
from omega.generate import PRESETS, BracketUnknown, Thesis, plan

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/contract_185/stage_strategy_draft_185_2_0.json").read_text(encoding="utf-8"))
LIVE = FIXTURE["inputSchema"]
DEFAULTS = json.loads((ROOT / tl.DEFAULT_PROBES).read_text(encoding="utf-8"))
SIDES = ("LONG", "SHORT")


def _bracket(stop: dict, *legs: tuple) -> dict:
    """The same {stop, exitPlan} on both sides; each leg (R multiple | a level dict, closePct)."""
    targets = [{"method": ({"kind": "R_MULTIPLE", "multiple": r} if not isinstance(r, dict) else
                           {"kind": "LEVEL", "level": r}), "closePct": pct} for r, pct in legs]
    return {s: {"stop": copy.deepcopy(stop), "exitPlan": {"targets": copy.deepcopy(targets)}} for s in SIDES}


def _atr(m) -> dict:
    return {"kind": "ATR", "atrMultiple": m}


DIALS = {"minAtrPct": 0.5, "minStopLossAtrMultiple": 1, "maxStopLossAtrMultiple": 2, "minRiskRewardRatio": 1.5}
BASE = PRESETS["trend-continuation"]
SECTIONS = plan(BASE)._sections()


def _judge(bracket, dials=None, trailing=True, sections=None):
    return tl.validate_bracket(bracket, dials=dials or DIALS, sections=SECTIONS if sections is None else sections,
                               anchor=BASE.anchor, trailing_enabled=trailing)


def _codes(findings) -> set:
    return {(f.severity, f.code) for f in findings}


def _tlp_valid(policy: dict) -> list[str]:
    """Every error of TRADE_LEVEL_POLICY against the LIVE 185.2.0 axis schema: jsonschema when installed, and always
    OMEGA's own walk of the same schema (omega.preflight.diff_schema)."""
    node = LIVE["properties"]["axes"]["properties"]["TRADE_LEVEL_POLICY"]
    errors = [f"{f.cls} {f.path}" for f in P.diff_schema(policy, node, LIVE) if f.verdict == "FAIL"]
    try:
        import jsonschema
    except ImportError:                                     # the structural walk alone
        return errors
    validator = jsonschema.Draft202012Validator({"$defs": LIVE["$defs"], **node})
    return errors + [e.message for e in validator.iter_errors(policy)]


# --- the pinned write surface ----------------------------------------------------------------------------------------
def test_the_pinned_capture_is_185_2_0_and_its_stage_schema_is_the_live_one():
    doc = stage_schema()
    assert (doc["contractVersion"], doc["buildSha"]) == ("185.2.0", "ede1fce51a498a371a21bad2511ac00036893356")
    assert (FIXTURE["contractVersion"], FIXTURE["buildSha"]) == (doc["contractVersion"], doc["buildSha"])
    assert doc["stage_strategy_draft"]["inputSchema"] == LIVE
    axis = LIVE["properties"]["axes"]["properties"]["TRADE_LEVEL_POLICY"]
    assert axis["required"] == ["minAtrPct", "minStopLossAtrMultiple", "maxStopLossAtrMultiple", "minRiskRewardRatio",
                                "tradeBracket"]
    assert "tradeLevelMenu" not in axis["properties"] and axis["additionalProperties"] is False
    assert tl.bracket_required() and not tl.menu_required()
    side = LIVE["$defs"]["directionTradeBracket"]
    assert side["required"] == ["stop", "exitPlan"] and side["additionalProperties"] is False
    assert tl.atr_stop_bounds() == (0, 5)
    # get_strategy and commit_strategy_draft serve the bracket in the menu's place
    for tool in ("get_strategy", "commit_strategy_draft"):
        strategy = doc[tool]["outputSchema"]["properties"]["strategy"]
        assert "tradeBracket" in strategy["required"] and "tradeLevelMenu" not in strategy["properties"]
    manifest = json.loads((ROOT / "data/contract/_manifest.json").read_text(encoding="utf-8"))
    ws = manifest["writeSurface"]
    assert (ws["servedContractVersion"], ws["supersedes"]["servedContractVersion"]) == ("185.2.0", "184.3.2")
    assert tl.MENU_SCHEMA == ws["supersedes"]["schema"] and tl.menu_schema()["contractVersion"] == "184.3.2"
    assert 'version = "0.18.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_every_emitted_body_validates_against_the_live_schema_and_names_no_menu(preset):
    p = plan(PRESETS[preset])
    body = {"draftVersion": 0, "axes": p.axes()}
    policy = body["axes"]["TRADE_LEVEL_POLICY"]
    from omega.execution import TRADE_LEVEL_DIALS
    assert list(policy) == [*TRADE_LEVEL_DIALS, "tradeBracket"]
    assert _tlp_valid(policy) == []
    assert [f for f in P.diff_schema(body, LIVE, LIVE, roster=P.read_roster(stage_schema())) if f.verdict == "FAIL"] == []
    assert "tradeLevelMenu" not in json.dumps(body)
    assert p.bracket_findings() == [] and p.menu_findings() == []           # the v0.18.0 alias
    # an UPDATE naming a trade-level dial carries the live bracket: no menu either
    live = {"TRADE_LEVEL_POLICY": dict(policy), "POSITION_MANAGEMENT": body["axes"]["POSITION_MANAGEMENT"]}
    up = plan(replace(PRESETS[preset], execution={"minAtrPct": 0.6})).axes_update(live)
    assert "tradeLevelMenu" not in json.dumps(up) and _tlp_valid(up["TRADE_LEVEL_POLICY"]) == []


# --- the default bracket ---------------------------------------------------------------------------------------------
def test_the_default_bracket_is_the_platforms_own_at_the_platforms_dials():
    measured = DEFAULTS["defaultBracket"]
    dials = {k: v for k, v in DEFAULTS["defaultDials"].items() if not k.startswith("_") and v is not None}
    assert dials == tl.PLATFORM_BRACKET_DIALS
    built = tl.default_bracket(dials["minRiskRewardRatio"],
                               stop_range=(dials["minStopLossAtrMultiple"], dials["maxStopLossAtrMultiple"]))
    assert built == measured
    assert tl.default_bracket_basis(1.5, (1, 2)) == {"stop": "platform", "exitPlan": "platform"}
    # every preset runs at those dials, so each stages exactly the platform's default
    for preset in PRESETS.values():
        assert plan(preset).axes()["TRADE_LEVEL_POLICY"]["tradeBracket"] == measured
    # VWAP Reject 4h's band (1 - 1.8, minimum 2): the platform's bracket fits, and is what its conversion wrote
    assert tl.default_bracket(2, stop_range=(1, 1.8)) == measured


@pytest.mark.parametrize("lo, hi, rr", [(1, 2, 1.5), (1, 1.8, 2), (0.8, 1.8, 1.5), (0.5, 1.2, 2), (1.6, 2.4, 1.5),
                                        (2, 3, 3.5), (1.21, 1.24, 1.5), (1.2, 1.2, 1), (0.3, 0.35, 0.5),
                                        (3, 5, 2.25), (1, 2, 4), (1, 2, 3)])
def test_the_default_bracket_sits_inside_the_band_and_pays_at_least_the_minimum(lo, hi, rr):
    dials = {**DIALS, "minStopLossAtrMultiple": lo, "maxStopLossAtrMultiple": hi, "minRiskRewardRatio": rr}
    bracket = tl.default_bracket(rr, stop_range=(lo, hi))
    for side in SIDES:
        stop = bracket[side]["stop"]
        assert stop["kind"] == "ATR" and tl.outside_stop_range(stop["atrMultiple"], lo, hi) is None
        legs = bracket[side]["exitPlan"]["targets"]
        assert len(legs) == 1 and legs[0]["closePct"] == 100
        assert tl.stated_rr(tl.plan_pays_double(legs)) >= tl._exact(rr)
    assert _judge(bracket, dials) == []
    assert _tlp_valid({**dials, "tradeBracket": bracket}) == []
    basis = tl.default_bracket_basis(rr, (lo, hi))
    assert basis["stop"] == ("platform" if lo <= 1.5 <= hi else "fallback")
    assert basis["exitPlan"] == ("platform" if rr <= 3 else "minimum")


def test_the_fallback_stop_is_the_step_nearest_the_middle_else_a_bound():
    assert tl.default_bracket_stop((0.5, 1.2)) == 0.8           # 0.85 is a tie: the lower step
    assert tl.default_bracket_stop((1.6, 2.4)) == 2
    assert tl.default_bracket_stop((1.21, 1.24)) == 1.21        # no 0.1 step strictly inside: the lower bound
    assert tl.default_bracket_stop((1.2, 1.2)) == 1.2
    assert tl.default_bracket_stop((6, 8)) == 1.5               # nothing stageable in the band: unjudged
    assert tl.default_bracket_basis(1.5, (6, 8))["stop"] == "unjudged"
    assert _codes(_judge(tl.default_bracket(1.5, stop_range=(6, 8)),
                         {**DIALS, "minStopLossAtrMultiple": 6, "maxStopLossAtrMultiple": 8})) == {
        ("error", "TRADE_BRACKET_STOP_OUTSIDE_BAND")}
    for unread in (None, ("a", 2), (2, 1), (float("nan"), 2)):
        assert tl.default_bracket_stop(unread) == 1.5
    assert tl.default_bracket_target("x") == 3 and tl.default_bracket_target(3.25) == 3.25


def test_a_plans_summary_names_where_its_bracket_came_from():
    lines = [line for line in plan(BASE).critique() if line.startswith("trade bracket")]
    assert lines and "the platform's ATR 1.5" in lines[0] and "the platform's 3R" in lines[0]
    narrow = plan(replace(BASE, execution={"minStopLossAtrMultiple": 0.5, "maxStopLossAtrMultiple": 1.2,
                                           "minRiskRewardRatio": 3.5}))
    line = next(x for x in narrow.critique() if x.startswith("trade bracket: "))
    assert "OMEGA's fallback ATR 0.8" in line and "one 3.5R leg" in line
    own = plan(replace(BASE, trade_bracket=_bracket(_atr(1.2), (2, 100))))
    assert any(x.startswith("trade bracket: the thesis's own") for x in own.critique())


# --- the band rule (185: refused at commit) --------------------------------------------------------------------------
@pytest.mark.parametrize("lo, hi", [(1, 2), (0.8, 1.8)])
def test_an_atr_stop_outside_the_band_is_an_error_and_both_bounds_are_inclusive(lo, hi):
    dials = {**DIALS, "minStopLossAtrMultiple": lo, "maxStopLossAtrMultiple": hi}
    for inside in (lo, hi, (lo + hi) / 2):
        assert _judge(_bracket(_atr(inside), (3, 100)), dials) == [], inside
    for outside, verdict in ((round(lo - 0.01, 2), "BELOW_FLOOR"), (round(hi + 0.01, 2), "ABOVE_CEILING")):
        found = _judge(_bracket(_atr(outside), (3, 100)), dials)
        assert [(f.severity, f.code, f.path) for f in found] == [
            ("error", "TRADE_BRACKET_STOP_OUTSIDE_BAND", f"tradeBracket.{s}.stop.atrMultiple") for s in SIDES]
        assert all(verdict in f.message for f in found)
    # a PERCENT stop and a LEVEL stop are not judged on the band (their distance is per coin and per bar)
    assert _judge(_bracket({"kind": "PERCENT", "percent": 9}, (3, 100)), dials) == []
    assert _judge(_bracket({"kind": "LEVEL", "level": tl.level_ref("SMA200"), "bufferAtrMultiple": 0}, (3, 100)),
                  dials) == []


# --- what carries over from the menu ---------------------------------------------------------------------------------
def test_the_exit_plan_rules_carry_over_on_the_one_plan():
    path = "tradeBracket.LONG.exitPlan"

    def on_long(findings):
        return {(f.code, f.path) for f in findings if f.path.startswith("tradeBracket.LONG")}
    assert on_long(_judge(_bracket(_atr(1.5), (2, 50)), trailing=False)) == {
        ("TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING", path)}
    assert on_long(_judge(_bracket(_atr(1.5), (2, 50)), trailing=None)) == {
        ("TRADE_MENU_EXIT_PLAN_RUNNER_TRAILING_UNKNOWN", path)}
    assert on_long(_judge(_bracket(_atr(1.5), (3, 50), (2, 50)))) == {
        ("TRADE_MENU_EXIT_PLAN_OUT_OF_ORDER", f"{path}.targets[1]")}
    assert on_long(_judge(_bracket(_atr(1.5), (1.2, 100)))) == {("TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR", path)}
    assert on_long(_judge(_bracket(_atr(1.5), (2, 3), (3, 97)))) == {
        ("TRADE_MENU_EXIT_PLAN_LEG_UNDER_5", f"{path}.targets[0].closePct")}
    assert on_long(_judge(_bracket(_atr(1.5), (2, 0), (3, 100)))) >= {
        ("TRADE_MENU_EXIT_PLAN_FIRST_LEG_EMPTY", f"{path}.targets[0].closePct")}
    # judged as stated, to three decimals, on the floating-point sum (182.3.2, RR_PROBES `ties`)
    assert _judge(_bracket(_atr(1.5), (1.4995, 100))) == []
    assert on_long(_judge(_bracket(_atr(1.5), (0.8, 50), (2.199, 50)))) == {("TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR", path)}
    # a level leg: the stage judges neither pay nor order across it; a level the report does not read is refused
    mixed = _judge(_bracket(_atr(1.5), (2, 50), (tl.level_ref("SMA200"), 50)))
    assert _codes(mixed) == {("warning", "TRADE_MENU_EXIT_PLAN_JUDGED_PER_DECISION")}
    unread = _judge(_bracket(_atr(1.5), (tl.level_ref("BB_UPPER"), 100)))
    assert on_long(unread) == {("TRADE_MENU_LEVEL_NOT_YIELDED", f"{path}.targets[0].method.level")}


def test_a_level_stop_follows_the_level_rule_and_cannot_also_be_a_leg():
    sma = tl.level_ref("SMA200")
    assert _judge(_bracket({"kind": "LEVEL", "level": sma, "bufferAtrMultiple": 0.5}, (3, 100))) == []
    refused = _judge(_bracket({"kind": "LEVEL", "level": tl.level_ref("BB_UPPER"), "bufferAtrMultiple": 0}, (3, 100)))
    assert {(f.code, f.path) for f in refused} == {("TRADE_MENU_LEVEL_NOT_YIELDED", f"tradeBracket.{s}.stop.level")
                                                    for s in SIDES}
    both = _judge(_bracket({"kind": "LEVEL", "level": sma, "bufferAtrMultiple": 0}, (sma, 100)))
    assert {(f.code, f.path) for f in both if f.severity == "error"} == {
        ("TRADE_MENU_LEVEL_BOTH_SIDES", f"tradeBracket.{s}.exitPlan.targets[0].method.level") for s in SIDES}


# --- a thesis's own bracket, judged whole ----------------------------------------------------------------------------
def test_a_thesis_bracket_is_staged_as_written_and_judged_whole():
    own = _bracket(_atr(1.2), (1.5, 50), (3, 50))
    p = plan(replace(BASE, trade_bracket=own))
    assert p.axes()["TRADE_LEVEL_POLICY"]["tradeBracket"] == own and p.trade_bracket() is not own
    assert p.bracket_findings() == []
    # a bracket that is not a bracket: shape findings, never an exception
    for broken in (["not", "a", "bracket"], {"LONG": own["LONG"]}, {**own, "BOTH": own["LONG"]},
                   {s: {**own[s], "extra": 1} for s in SIDES}):
        found = plan(replace(BASE, trade_bracket=broken)).bracket_findings()
        assert found and {f.code for f in found} == {"TRADE_MENU_SHAPE"}, broken


def test_old_menu_input_is_refused_never_migrated():
    menu = tl.default_menu(1.5)                     # a 184 menu: {stops: [...], exitPlans: [...]} per direction
    # as a thesis bracket: the write schema's walk refuses it (no `stop`, no `exitPlan`, `stops` / `exitPlans` unknown)
    found = plan(replace(BASE, trade_bracket=menu)).bracket_findings()
    assert {f.code for f in found} == {"TRADE_MENU_SHAPE"}
    assert {"tradeBracket.LONG.stops", "tradeBracket.LONG.exitPlans", "tradeBracket.LONG.stop"} <= {f.path for f in found}
    # the field it used to have is gone: a TypeError, not an alias
    with pytest.raises(TypeError):
        Thesis(**{**BASE.__dict__, "trade_level_menu": menu})
    assert [f.name for f in __import__("dataclasses").fields(Thesis)].index("trade_bracket") == 9
    # and the stage refuses the key itself: TRADE_LEVEL_POLICY is closed
    assert _tlp_valid({**DIALS, "tradeLevelMenu": menu}) != []


# --- the UPDATE path -------------------------------------------------------------------------------------------------
# VWAP Reject 4h as the platform converted it (read 2026-11-27: the old menu became ATR 1.5 and 3R closing 100%)
LIVE_BRACKET = _bracket(_atr(1.5), (3, 100))
CURRENT = {"TRADE_LEVEL_POLICY": {"minAtrPct": 0.8, "minStopLossAtrMultiple": 1, "maxStopLossAtrMultiple": 1.8,
                                  "minRiskRewardRatio": 2, "tradeBracket": LIVE_BRACKET},
           "POSITION_MANAGEMENT": {**plan(BASE).axes()["POSITION_MANAGEMENT"], "trailingEnabled": True}}


def test_an_update_carries_the_live_bracket_exactly_as_get_strategy_serves_it():
    dial = plan(replace(BASE, execution={"minAtrPct": 0.4}))
    staged = dial.axes_update(CURRENT)["TRADE_LEVEL_POLICY"]
    assert staged == {**CURRENT["TRADE_LEVEL_POLICY"], "minAtrPct": 0.4}
    assert staged["tradeBracket"] == LIVE_BRACKET and staged["tradeBracket"] is not LIVE_BRACKET
    assert dial.update_bracket_findings(CURRENT) == [] == dial.update_menu_findings(CURRENT)     # the alias
    # no dial and no bracket named: the axis is not staged, and the live bracket is judged against the staged REPORT
    untouched = plan(BASE)
    assert "TRADE_LEVEL_POLICY" not in untouched.axes_update(CURRENT)
    assert untouched.update_bracket_findings(CURRENT) == []
    # a thesis bracket wins over the live one
    own = _bracket(_atr(1.2), (2, 100))
    assert plan(replace(BASE, trade_bracket=own)).axes_update(CURRENT)["TRADE_LEVEL_POLICY"]["tradeBracket"] == own
    # the dial raised alone: the carried plan is judged against it
    raised = plan(replace(BASE, execution={"minRiskRewardRatio": 3.5}))
    assert _codes(raised.update_bracket_findings(CURRENT)) == {("error", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR")}
    # the band narrowed under the carried stop: refused at commit since 185
    narrowed = plan(replace(BASE, execution={"maxStopLossAtrMultiple": 1.4}))
    assert {(f.code, f.path) for f in narrowed.update_bracket_findings(CURRENT)} == {
        ("TRADE_BRACKET_STOP_OUTSIDE_BAND", f"tradeBracket.{s}.stop.atrMultiple") for s in SIDES}


def test_an_unstaged_live_bracket_is_rejudged_against_the_axes_this_update_stages():
    # REPORT is restaged whole: a live level stop the new report does not read is refused (probe A3's rule)
    levelled = copy.deepcopy(CURRENT)
    levelled["TRADE_LEVEL_POLICY"]["tradeBracket"] = _bracket(
        {"kind": "LEVEL", "level": tl.level_ref("BB_LOWER"), "bufferAtrMultiple": 0}, (3, 100))
    found = plan(BASE).update_bracket_findings(levelled)
    assert _codes(found) == {("error", "TRADE_MENU_LEVEL_NOT_YIELDED")} and all("A3" in f.message for f in found)
    # Trailing switched off alone under a live runner (probe A2's rule)
    runner = copy.deepcopy(CURRENT)
    runner["TRADE_LEVEL_POLICY"]["tradeBracket"] = _bracket(_atr(1.5), (3, 50))
    off = plan(replace(BASE, execution={"trailingEnabled": False}))
    assert "TRADE_LEVEL_POLICY" not in off.axes_update(runner)
    found = off.update_bracket_findings(runner)
    assert _codes(found) == {("error", "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING")}
    assert all("A2" in f.message for f in found)
    # a rule none of whose axes the update stages: refused as unmeasured, failing closed
    outside = copy.deepcopy(CURRENT)
    outside["TRADE_LEVEL_POLICY"]["tradeBracket"] = _bracket(_atr(1.9), (3, 100))
    found = plan(BASE).update_bracket_findings(outside)
    assert _codes(found) == {("error", "TRADE_BRACKET_STOP_OUTSIDE_BAND")}
    assert all("unmeasured" in f.message for f in found)


@pytest.mark.parametrize("policy", [
    {k: v for k, v in CURRENT["TRADE_LEVEL_POLICY"].items() if k != "tradeBracket"},
    {**{k: v for k, v in CURRENT["TRADE_LEVEL_POLICY"].items() if k != "tradeBracket"},
     "tradeLevelMenu": tl.default_menu(2, stop_range=(1, 1.8))},
], ids=["no-bracket", "menu-only"])
def test_a_live_body_without_a_bracket_is_refused_never_invented(policy):
    current = {**CURRENT, "TRADE_LEVEL_POLICY": policy}
    menu_only = "tradeLevelMenu" in policy
    # staged (a dial named): the update cannot be built, and the findings say why
    dial = plan(replace(BASE, execution={"minAtrPct": 0.4}))
    with pytest.raises(BracketUnknown, match="never invents a live strategy's bracket") as raised:
        dial.axes_update(current)
    assert isinstance(raised.value, ValueError) and (("tradeLevelMenu" in str(raised.value)) == menu_only)
    found = dial.update_bracket_findings(current)
    assert [(f.severity, f.code, f.path) for f in found] == [
        ("error", "TRADE_BRACKET_LIVE_UNKNOWN", "TRADE_LEVEL_POLICY.tradeBracket")]
    assert ("never converts one" in found[0].message) == menu_only
    # not staged: the stage judges the bracket the strategy holds, which `current` does not carry
    found = plan(BASE).update_bracket_findings(current)
    assert [(f.severity, f.code) for f in found] == [("error", "TRADE_BRACKET_LIVE_UNKNOWN")]
    # a thesis naming its own bracket needs no live one, and never stages the live menu
    own = plan(replace(BASE, execution={"minAtrPct": 0.4}, trade_bracket=LIVE_BRACKET))
    staged = own.axes_update(current)["TRADE_LEVEL_POLICY"]
    assert staged["tradeBracket"] == LIVE_BRACKET and "tradeLevelMenu" not in staged
    assert own.update_bracket_findings(current) == []


def test_a_carried_live_bracket_beside_unread_dials_is_never_read_as_clean():
    # review 2026-11-27 finding 1: validate_bracket reads an absent band as no bound, so a partial `current` carrying
    # the live bracket without its dials read clean - and since 185 the band is a refusal, not a warning
    outside = _bracket(_atr(4.5), (3, 100))
    pm = CURRENT["POSITION_MANAGEMENT"]
    bare = plan(BASE).update_bracket_findings({"TRADE_LEVEL_POLICY": {"tradeBracket": outside}, "POSITION_MANAGEMENT": pm})
    assert [(f.severity, f.code, f.path) for f in bare] == [
        ("error", "TRADE_BRACKET_LIVE_UNKNOWN", f"TRADE_LEVEL_POLICY.{d}")
        for d in ("minStopLossAtrMultiple", "maxStopLossAtrMultiple", "minRiskRewardRatio")]
    assert all("unread" in f.message and "failing closed" in f.message for f in bare)
    # the band read: the band rule answers; the minimum still unread: refused on that dial alone
    banded = {"tradeBracket": outside, "minStopLossAtrMultiple": 1, "maxStopLossAtrMultiple": 1.8}
    found = plan(BASE).update_bracket_findings({"TRADE_LEVEL_POLICY": banded, "POSITION_MANAGEMENT": pm})
    assert [(f.code, f.path) for f in found] == [("TRADE_BRACKET_LIVE_UNKNOWN", "TRADE_LEVEL_POLICY.minRiskRewardRatio")]
    found = plan(BASE).update_bracket_findings(
        {"TRADE_LEVEL_POLICY": {**banded, "minRiskRewardRatio": 2, "minAtrPct": 0.8}, "POSITION_MANAGEMENT": pm})
    assert {(f.code, f.path) for f in found} == {
        ("TRADE_BRACKET_STOP_OUTSIDE_BAND", f"tradeBracket.{s}.stop.atrMultiple") for s in SIDES}
    # a PERCENT stop reads no band: only the minimum is needed (a null dial is as unread as an absent one)
    percent = _bracket({"kind": "PERCENT", "percent": 2}, (3, 100))
    found = plan(BASE).update_bracket_findings(
        {"TRADE_LEVEL_POLICY": {"tradeBracket": percent, "minRiskRewardRatio": None}, "POSITION_MANAGEMENT": pm})
    assert [(f.code, f.path) for f in found] == [("TRADE_BRACKET_LIVE_UNKNOWN", "TRADE_LEVEL_POLICY.minRiskRewardRatio")]
    # every dial carried (the get_strategy read, all required): nothing unread
    assert plan(BASE).update_bracket_findings(CURRENT) == []


# --- what the manager imports ----------------------------------------------------------------------------------------
def test_the_interface_the_manager_reads():
    assert list(inspect.signature(tl.default_bracket).parameters) == ["min_rr", "schema", "stop_range"]
    assert inspect.signature(tl.default_bracket).parameters["stop_range"].kind is inspect.Parameter.KEYWORD_ONLY
    assert list(inspect.signature(tl.plan_pays).parameters) == ["legs", "level_r"]
    assert tl.plan_pays([{"method": {"kind": "R_MULTIPLE", "multiple": 2}, "closePct": 100}]) == 2
    p = plan(BASE)
    for name in ("bracket_findings", "update_bracket_findings", "menu_findings", "update_menu_findings",
                 "trade_bracket", "update_bracket", "axes", "axes_update", "preview_request"):
        assert callable(getattr(p, name)), name
    assert issubclass(BracketUnknown, ValueError)


def test_every_trade_level_code_is_listed():
    """The codes the bracket path can emit (validate_bracket and the exit-plan / level rules it calls, the shape walk,
    and StrategyPlan.update_bracket_findings). TRADE_MENU_STOP_OUTSIDE_RANGE, TRADE_MENU_TARGET_BELOW_MIN_RR and
    TRADE_MENU_LIVE_UNKNOWN are the menu's alone (validate_menu, history): no bracket finding carries them."""
    source = inspect.getsource(tl)
    in_trade_levels = set(re.findall(r'"(TRADE_(?:MENU|BRACKET)_[A-Z_0-9]+)"', source))
    assert {"TRADE_BRACKET_STOP_OUTSIDE_BAND", "TRADE_MENU_SHAPE", "TRADE_MENU_LEVEL_BOTH_SIDES",
            "TRADE_MENU_LEVEL_NOT_YIELDED", "TRADE_MENU_LEVEL_UNMEASURED", "TRADE_MENU_LEVEL_NOT_PRICE",
            "TRADE_MENU_LEVEL_UNKNOWN_METRIC", "TRADE_MENU_EXIT_PLAN_OVER_100", "TRADE_MENU_EXIT_PLAN_RUNNER_UNDER_5",
            "TRADE_MENU_EXIT_PLAN_FIRST_LEG_EMPTY", "TRADE_MENU_EXIT_PLAN_LEG_UNDER_5",
            "TRADE_MENU_EXIT_PLAN_ZERO_NOT_LAST", "TRADE_MENU_EXIT_PLAN_ZERO_WITHOUT_RUNNER",
            "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING", "TRADE_MENU_EXIT_PLAN_RUNNER_TRAILING_UNKNOWN",
            "TRADE_MENU_EXIT_PLAN_OUT_OF_ORDER", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR",
            "TRADE_MENU_EXIT_PLAN_RR_TIE_UNMEASURED", "TRADE_MENU_EXIT_PLAN_JUDGED_PER_DECISION"} <= in_trade_levels
    bracket_source = inspect.getsource(tl.validate_bracket)
    assert "TRADE_MENU_STOP_OUTSIDE_RANGE" not in bracket_source and "TRADE_MENU_TARGET_BELOW_MIN_RR" not in bracket_source
    generate = set(re.findall(r'"(TRADE_(?:MENU|BRACKET)_[A-Z_0-9]+)"', inspect.getsource(G)))
    assert generate == {"TRADE_BRACKET_LIVE_UNKNOWN", "TRADE_MENU_EXIT_PLAN_RUNNER_TRAILING_UNKNOWN"}
