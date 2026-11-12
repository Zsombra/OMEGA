"""OMEGA v0.14.2 (2026-11-12): the six items v0.14.1 left unmeasured, measured at contract 171.0.0 and replayed offline.

data/audit/update_rules_171_2026-11-12.json (21:46:40 - 21:54:05Z, build 588e449a; GET /mcp/version read 171.0.0 before
and after every phase): 4 preview_strategy_report calls, 2 CREATE stages on the v0.14.0 base plan (both refused at
input), 8 UPDATE stages in 4 drafts on the unbound, archived sandbox "OMEGA-TEST: 110.8 stage probe" (7 staged, read
back, discarded and read null; 1 refused at input) and 5 preview_strategy_trade_levels calls on those drafts. Nothing
was committed.

(1) A2 - POSITION_MANAGEMENT staged alone with Trailing off draws the runner's draft error on the menu the draft holds;
    A3 - REPORT staged alone without the Bollinger columns draws the level refusal on the COMMITTED menu. The stage
    judges the whole draft: StrategyPlan.update_menu_findings now refuses (v0.14.1 warned).
(2) B1 - TRADE_LEVEL_POLICY without its menu is refused at input; B2 - the axis restaged whole with the live menu carried
    and the minimum raised is judged as a create ("pays 1.5R, below ... 2.5").
(3) C1, C2 - an off-step minimum on an UPDATE is a draft error, named or carried as the draft holds it
    (EXECUTION_CARRIED_OFF_STEP is now an error; a committed off-step value is unmeasured and refused, failing closed).
(4) S3, S4 - a 3% second leg and a 1% runner are refused at input with the sentences S1 / S2 measured.
(5) P1 - P4 - market, reference and benchmark sections hold the same joint chain depth bound as a per-coin section.
(6) A1's preview - a runner after a LEVEL leg rides at that level's R (plan_pays with level_r reproduces every setup and
    every refused pair); L1 - it is refused while Trailing is off.

Nothing here calls the platform.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from omega import preflight as P
from omega import trade_levels as tl
from omega.contract import load
from omega.execution import validate_execution
from omega.fanout import outputs_for
from omega.generate import PRESETS, Thesis, plan
from omega.types import CustomSection
from omega.validate import validate_section

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / tl.UPDATE_PROBES).read_text(encoding="utf-8"))
PROBES = RECORD["probes"]
SANDBOX = RECORD["sandbox"]
COMMITTED = SANDBOX["committed"]
BASE = json.loads((ROOT / tl.EXIT_PLAN_PROBES).read_text(encoding="utf-8"))["basePlan"]
VERSION = ("171.0.0", "588e449aa4cb93b3d805c360ce1e6c55f0037951")
# the one rule each staged UPDATE probe's draft error is about (the platform names only the first error it meets)
RULE = {"A2.trailing_off_alone": "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING",
        "A3.report_alone_rejudges_committed_menu": "TRADE_MENU_LEVEL_NOT_YIELDED",
        "B2.min_raised_live_menu_carried": "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR",
        "C1.off_step_min_named": "EXECUTION_OFF_STEP",
        "C2.off_step_min_carried": "EXECUTION_OFF_STEP",
        "L1.level_runner_trailing_off": "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING"}


def _field(path: str) -> str:
    """omega names a list position `[i]` and a dial `execution.<dial>` or `<AXIS>.<dial>`; an input issue names a
    position `.i` and a draft error names the dial bare - one spelling for comparing."""
    out = path.replace("[", ".").replace("]", "")
    for prefix in ("execution.", "TRADE_LEVEL_POLICY."):
        out = out.removeprefix(prefix)
    return out


def _platform_fields(probe: dict) -> set[str]:
    answer = probe["answer"]
    if not answer["staged"]:                    # refused at input: the issue paths below `axes.<AXIS>`
        return {_field(".".join(str(p) for p in issue["path"][2:])) for issue in answer["refusal"]["issues"]}
    return {_field(e["field"]) for e in answer["errors"]}


def _composed(name: str) -> dict:
    """The draft as the stage judged it: the committed axes, then every axis the draft's earlier stages wrote, then this
    stage's (each axis written whole; a stage refused at input wrote nothing)."""
    (draft,) = [d for d in RECORD["drafts"] if name in d["probes"]]
    composed = copy.deepcopy({k: COMMITTED[k] for k in ("TRADE_LEVEL_POLICY", "POSITION_MANAGEMENT", "REPORT")})
    for n in draft["probes"][:draft["probes"].index(name) + 1]:
        if PROBES[n]["answer"]["staged"]:
            composed.update(copy.deepcopy(PROBES[n]["sent"]["axes"]))
    return composed


def _judged(composed: dict) -> list:
    """omega on the whole draft: the menu rules (omega.trade_levels) and the dial's step (omega.execution)."""
    tlp = composed["TRADE_LEVEL_POLICY"]
    found = tl.validate_menu(tlp["tradeLevelMenu"], dials={k: v for k, v in tlp.items() if k != "tradeLevelMenu"},
                             sections=composed["REPORT"]["sections"], anchor=COMMITTED["anchor"],
                             trailing_enabled=composed["POSITION_MANAGEMENT"]["trailingEnabled"])
    return found + validate_execution({"minRiskRewardRatio": tlp["minRiskRewardRatio"]})


# --- the record ---------------------------------------------------------------------------------------------------------

def test_the_record_is_complete_and_nothing_was_committed():
    n = RECORD["counts"]
    assert n == {"reportPreviews": 4, "reportPreviewsAccepted": 1, "reportPreviewsRefused": 3, "stages": 10,
                 "createStages": 2, "updateStages": 8, "staged": 7, "refusedAtInput": 3, "drafts": 4, "discarded": 4,
                 "committed": 0, "tradeLevelPreviews": 5, "tradeLevelPreviewsRendered": 1,
                 "tradeLevelPreviewsRefused": 4}
    measured = RECORD["measuredAt"]
    assert (measured["contractVersion"], measured["buildSha"]) == VERSION
    reads = measured["versionReads"]
    assert len(reads) == 14 and {(r["contractVersion"], r["buildSha"]) for r in reads} == {VERSION}
    assert [r["readAt"] for r in reads] == sorted(r["readAt"] for r in reads)
    sent = [p["sentAt"] for p in PROBES.values()]
    assert reads[0]["readAt"] <= min(sent) and max(sent) <= reads[-1]["readAt"]
    # every UPDATE stage named the sandbox; every CREATE named none and draftVersion 0 (neither reached a draft)
    for name, probe in PROBES.items():
        if probe.get("kind") == "UPDATE":
            assert probe["sent"]["strategyId"] == SANDBOX["strategyId"], name
        elif probe.get("kind") == "CREATE":
            assert probe["sent"]["draftVersion"] == 0 and not probe["answer"]["staged"], name
    # each of the four drafts: the sandbox unbound, with no open position and no held draft before it; discarded at the
    # version read; read null after
    for draft in RECORD["drafts"]:
        before = draft["sandboxReadBefore"]
        assert (before["boundAgentCount"], before["openPositionCount"], before["heldDraft"]) == (0, 0, None)
        assert (before["revision"], before["committedRevision"], before["isActive"]) == (2, 2, False)
        assert draft["discardAnswer"] == {"strategyId": SANDBOX["strategyId"], "discarded": True}
        assert draft["draftAfterDiscard"] is None and draft["draftVersionAfterDiscard"] == 0
    # the drafts listed at the end are none of this probe's
    listed = RECORD["listStrategyDraftsAtEnd"]["answer"]["drafts"]
    assert [d["strategyId"] for d in listed] == ["c1fd5d4c-0a86-4b3f-9ab4-16ad57c46898"]
    assert listed[0]["updatedAt"].startswith("2026-10-23")
    # the sandbox: an OMEGA-TEST strategy no agent is bound to
    assert "OMEGA-TEST" in SANDBOX["name"]
    (row,) = [s for s in SANDBOX["omegaTestStrategies"] if s["strategyId"] == SANDBOX["strategyId"]]
    assert row["boundAgentCount"] == 0 and row["agents"] == []


def _draft_axes(name: str) -> set[str]:
    """The axes the draft holds after `name`: every axis a staged stage of its draft wrote, up to and including it."""
    (draft,) = [d for d in RECORD["drafts"] if name in d["probes"]]
    return {axis for n in draft["probes"][:draft["probes"].index(name) + 1] if PROBES[n]["answer"]["staged"]
            for axis in PROBES[n]["sent"]["axes"]}


def test_every_staged_update_was_read_back_as_sent():
    for name, probe in PROBES.items():
        if probe.get("kind") == "UPDATE" and probe["answer"]["staged"]:
            back = probe["readBack"]
            assert back["keptAsSent"] is True, name
            assert back["diagnostics"]["errors"] == probe["answer"]["errors"], name
            assert set(back["draftAxes"]) == _draft_axes(name), name


# --- (1) - (3), (6): every staged UPDATE replayed on the whole draft --------------------------------------------------------

@pytest.mark.parametrize("name", sorted(n for n, p in PROBES.items() if p.get("kind") == "UPDATE" and p["answer"]["staged"]))
def test_every_staged_update_replays_on_the_whole_draft(name):
    probe = PROBES[name]
    errors = [f for f in _judged(_composed(name)) if f.severity == "error"]
    platform = _platform_fields(probe)
    if not platform:
        assert errors == [], (name, [str(f) for f in errors])
        return
    # the platform names only the first error it meets; omega names every one, all of the probe's rule, the platform's
    # field among them
    assert {f.code for f in errors} == {RULE[name]}, (name, [str(f) for f in errors])
    assert platform <= {_field(f.path) for f in errors}, (name, platform, [f.path for f in errors])


def test_the_platform_names_only_the_first_menu_error():
    # A2: all three plans leave a runner on each side; the draft error names LONG exitPlans[0] alone
    a2 = [f for f in _judged(_composed("A2.trailing_off_alone")) if f.severity == "error"]
    assert [f.path for f in a2] == [f"tradeLevelMenu.{s}.exitPlans[{i}]" for s in tl.SIDES for i in range(3)]
    assert [e["field"] for e in PROBES["A2.trailing_off_alone"]["answer"]["errors"]] == ["tradeLevelMenu.LONG.exitPlans[0]"]
    # A3: two Bollinger stops and two Bollinger plans lose their column; the draft error names the LONG stop alone
    a3 = {f.path for f in _judged(_composed("A3.report_alone_rejudges_committed_menu")) if f.severity == "error"}
    assert a3 == {f"tradeLevelMenu.{s}.{k}[4]{tail}" for s in tl.SIDES
                  for k, tail in (("stops", ".level"), ("exitPlans", ".targets[0].method.level"))}
    assert [e["field"] for e in PROBES["A3.report_alone_rejudges_committed_menu"]["answer"]["errors"]] == [
        "tradeLevelMenu.LONG.stops[4].level"]


def test_a_stage_rejudges_the_axes_it_does_not_send():
    # (1) A2 sent POSITION_MANAGEMENT alone; the draft held A1's TRADE_LEVEL_POLICY, kept as staged
    a2 = PROBES["A2.trailing_off_alone"]
    assert list(a2["sent"]["axes"]) == ["POSITION_MANAGEMENT"] and a2["answer"]["stagedAxes"] == ["POSITION_MANAGEMENT"]
    assert a2["sent"]["axes"]["POSITION_MANAGEMENT"]["trailingEnabled"] is False
    assert set(a2["readBack"]["draftAxes"]) == {"POSITION_MANAGEMENT", "TRADE_LEVEL_POLICY"}
    assert "Trailing is off" in a2["answer"]["errors"][0]["message"]
    assert a2["preview"]["refused"]["field"] == a2["answer"]["errors"][0]["field"]
    # A1, the same draft before it, was clean: the error is the switch, not the menu
    assert PROBES["A1.runner_menu_staged"]["answer"]["errors"] == []
    # A3 sent REPORT alone on a fresh draft: the menu it judged is the COMMITTED one (no draft held a menu)
    a3 = PROBES["A3.report_alone_rejudges_committed_menu"]
    assert list(a3["sent"]["axes"]) == ["REPORT"] and a3["readBack"]["draftAxes"] == ["REPORT"]
    assert _composed("A3.report_alone_rejudges_committed_menu")["TRADE_LEVEL_POLICY"] == COMMITTED["TRADE_LEVEL_POLICY"]
    assert "not a level this strategy's report yields" in a3["answer"]["errors"][0]["message"]
    dropped = {c["metric"] for s in COMMITTED["REPORT"]["sections"] for c in s["columns"]} - {
        c["metric"] for s in a3["sent"]["axes"]["REPORT"]["sections"] for c in s["columns"]}
    assert dropped == {"BB_UPPER", "BB_LOWER"}


def _sandbox_thesis(**kw) -> Thesis:
    base = PRESETS["trend-continuation"]
    return Thesis(**{**base.__dict__, **kw})


def _r_only(menu: dict) -> dict:
    """The committed menu without its band entries (the preset's report reads no band)."""
    return {side: {"stops": [s for s in d["stops"] if s["kind"] == "ATR"],
                   "exitPlans": [p for p in d["exitPlans"]
                                 if all(t["method"]["kind"] == "R_MULTIPLE" for t in p["targets"])]}
            for side, d in menu.items()}


def test_omegas_update_path_refuses_what_the_stage_refused():
    """StrategyPlan.update_menu_findings, on the update forms measured: each refuses where the stage did (v0.14.1 warned
    on A2's form and C2's)."""
    live_pm = copy.deepcopy(COMMITTED["POSITION_MANAGEMENT"])
    live_tlp = {**{k: v for k, v in COMMITTED["TRADE_LEVEL_POLICY"].items() if k != "tradeLevelMenu"},
                "tradeLevelMenu": _r_only(COMMITTED["TRADE_LEVEL_POLICY"]["tradeLevelMenu"])}
    # (1) Trailing switched off alone under the runner the strategy holds (A1's T4 plan): refused, an error
    held = copy.deepcopy(live_tlp)
    held["tradeLevelMenu"] = {side: {"stops": d["stops"], "exitPlans": d["exitPlans"][:1]} for side, d in
                              PROBES["A1.runner_menu_staged"]["sent"]["axes"]["TRADE_LEVEL_POLICY"]["tradeLevelMenu"].items()}
    current = {"TRADE_LEVEL_POLICY": held, "POSITION_MANAGEMENT": live_pm}
    off = plan(_sandbox_thesis(execution={"trailingEnabled": False}))
    assert "TRADE_LEVEL_POLICY" not in off.axes_update(current)
    assert {(f.severity, f.code) for f in off.update_menu_findings(current)} == {
        ("error", "TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING")}
    # (2) the dial raised alone: the axis is restaged whole with the live menu carried, and the plans below it refused
    current = {"TRADE_LEVEL_POLICY": live_tlp, "POSITION_MANAGEMENT": live_pm}
    raised = plan(_sandbox_thesis(execution={"minRiskRewardRatio": 2.5}))
    staged = raised.axes_update(current)["TRADE_LEVEL_POLICY"]
    assert staged["tradeLevelMenu"] == live_tlp["tradeLevelMenu"] and staged["minRiskRewardRatio"] == 2.5
    found = raised.update_menu_findings(current)
    assert {(f.severity, f.code) for f in found} == {("error", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR")}
    assert {f.path for f in found} == {f"tradeLevelMenu.{s}.exitPlans[{i}]" for s in tl.SIDES for i in (0, 1)}
    # (3) the off-step minimum the draft holds (C2's carriedFrom), carried by an update naming another dial: refused
    carried_from = PROBES["C2.off_step_min_carried"]["carriedFrom"]["TRADE_LEVEL_POLICY"]
    assert carried_from["minRiskRewardRatio"] == 1.4
    current = {"TRADE_LEVEL_POLICY": {**live_tlp, "minRiskRewardRatio": carried_from["minRiskRewardRatio"]},
               "POSITION_MANAGEMENT": live_pm}
    atr = plan(_sandbox_thesis(execution={"minAtrPct": 0.4}))
    found = atr.update_menu_findings(current)
    assert [(f.severity, f.code, f.path) for f in found] == [
        ("error", "EXECUTION_CARRIED_OFF_STEP", "TRADE_LEVEL_POLICY.minRiskRewardRatio")]


# --- (2) the dial alone ---------------------------------------------------------------------------------------------------

def test_the_minimum_cannot_be_staged_without_the_menu():
    b1 = PROBES["B1.min_alone_without_menu"]
    sent = b1["sent"]["axes"]["TRADE_LEVEL_POLICY"]
    assert "tradeLevelMenu" not in sent and sent["minRiskRewardRatio"] == 2.5
    refusal = b1["answer"]["refusal"]
    assert [i["path"] for i in refusal["issues"]] == [["axes", "TRADE_LEVEL_POLICY", "tradeLevelMenu"]]
    assert "expected object, received undefined" in refusal["message"]
    # omega's walk of the write schema refuses the same field, and omega's update never stages the axis without a menu
    fails = [f for f in P.diff_schema(sent, tl._axis("TRADE_LEVEL_POLICY"), tl._root(),
                                      roster=P.read_roster(tl._doc(None))) if f.verdict == "FAIL"]
    assert [(f.cls, f.path) for f in fails] == [("MISSING_REQUIRED", "tradeLevelMenu")]
    with pytest.raises(ValueError, match="never invents a live strategy's menu"):
        plan(_sandbox_thesis(execution={"minRiskRewardRatio": 2.5})).axes_update(
            {"TRADE_LEVEL_POLICY": {k: v for k, v in sent.items()}})


def test_the_raised_minimum_names_what_the_carried_plan_pays():
    b2 = PROBES["B2.min_raised_live_menu_carried"]
    sent = b2["sent"]["axes"]["TRADE_LEVEL_POLICY"]
    assert sent["tradeLevelMenu"] == COMMITTED["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]          # carried verbatim
    assert {k: v for k, v in sent.items() if k not in ("tradeLevelMenu", "minRiskRewardRatio")} == {
        k: v for k, v in COMMITTED["TRADE_LEVEL_POLICY"].items() if k not in ("tradeLevelMenu", "minRiskRewardRatio")}
    (error,) = b2["answer"]["errors"]
    first = sent["tradeLevelMenu"]["LONG"]["exitPlans"][0]["targets"]
    assert tl.plan_pays(first) == 1.5 and "pays 1.5R, below this strategy's minimum risk-reward of 2.5" in error["message"]
    assert b2["preview"]["refused"]["field"] == error["field"]


# --- (3) the step on an UPDATE ----------------------------------------------------------------------------------------------

def test_an_off_step_minimum_is_refused_on_an_update_named_or_carried():
    c1, c2 = PROBES["C1.off_step_min_named"], PROBES["C2.off_step_min_carried"]
    assert c1["sent"]["axes"]["TRADE_LEVEL_POLICY"]["minRiskRewardRatio"] == 1.4
    # C2 carried exactly what get_strategy_draft read after C1 - the four dials and the menu - with minAtrPct changed
    carried = c2["carriedFrom"]["TRADE_LEVEL_POLICY"]
    assert c2["carriedFrom"]["draftVersion"] == c1["readBack"]["draftVersion"] == c2["sent"]["draftVersion"]
    assert c2["sent"]["axes"]["TRADE_LEVEL_POLICY"] == {**{k: carried[k] for k in (
        "minAtrPct", "minStopLossAtrMultiple", "maxStopLossAtrMultiple", "minRiskRewardRatio", "tradeLevelMenu")},
        "minAtrPct": 0.4}
    for probe in (c1, c2):
        assert probe["answer"]["errors"] == [{"code": "VALIDATION_ERROR", "field": "minRiskRewardRatio",
                                              "message": "minRiskRewardRatio must be a multiple of 0.25",
                                              "details": None}]
    # no committed off-step value was there to carry: the sandbox, and every strategy listed, sits on the step
    assert COMMITTED["TRADE_LEVEL_POLICY"]["minRiskRewardRatio"] == 1.5
    assert all(abs(float(v) / 0.25 - round(float(v) / 0.25)) < 1e-9
               for v in SANDBOX["listedMinRiskRewardRatios"]["counts"])


# --- (4) the 5% rules -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, code", [("S3.non_first_leg_3pct", "TRADE_MENU_EXIT_PLAN_LEG_UNDER_5"),
                                        ("S4.runner_1pct", "TRADE_MENU_EXIT_PLAN_RUNNER_UNDER_5")])
def test_the_five_percent_rules_replay_on_a_second_leg_and_a_1pct_runner(name, code):
    probe = PROBES[name]
    sent = probe["sent"]
    found = tl.validate_menu(sent["menu"], dials=sent["dials"], sections=BASE["reportSections"], anchor=BASE["anchor"],
                             trailing_enabled=sent["trailingEnabled"])
    errors = [f for f in found if f.severity == "error"]
    assert {f.code for f in errors} == {code}
    assert {_field(f.path) for f in errors} == _platform_fields(probe)          # LONG and SHORT, the same field each
    message = probe["answer"]["refusal"]["message"]
    assert message == ("A target closes at least 5%" if code.endswith("LEG_UNDER_5") else
                       "A runner holds 0% or at least 5% of the position; this plan leaves 1%")


# --- (5) deep chains off the per-coin subject ----------------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(n for n in PROBES if n.startswith("P")))
def test_the_chain_depth_bound_holds_on_market_reference_and_benchmark_sections(name):
    probe = PROBES[name]
    contract = load()
    found, headers = [], []
    for s in probe["sent"]["sections"]:
        assert s["marketScope"] is not None or s["benchmarkTicker"] is not None, name     # no per-coin section
        section = CustomSection(title="t", benchmarkTicker=s["benchmarkTicker"], marketScope=s["marketScope"],
                                columns=s["columns"])
        found += validate_section(section, contract=contract)
        headers += [o.header for col in section.columns for o in outputs_for(col, contract)]
    if probe["accepted"]:
        assert found == [] and headers == probe["render"]["headers"], name
        return
    refusal = probe["refusal"]
    assert refusal["authoringCode"] == "REPORT_COLUMN_DEPTH_EXCEEDED"
    assert [(f.code, f.path) for f in found] == [("DEPTH_EXCEEDED", "section.columns[0].chainedWindow")], name
    assert refusal["path"] == ["sections", 0, "columns", 0, "chainedWindow"]
    assert (refusal["context"]["depth"], refusal["context"]["cap"], refusal["receivedValue"]["need"]) == (2500, 64, 2437)
    assert f"reads {refusal['receivedValue']['need']} bars" in found[0].message
    assert f"fits beside window {probe['sent']['sections'][0]['columns'][0]['window']} is " \
           f"{refusal['allowedDomain']['maximum']}" in found[0].message


def test_the_deep_chain_values_off_the_coin_are_a_matter_of_stored_history():
    render = PROBES["P1.last_fit_market_reference_benchmark"]["render"]
    assert [s["rowIdentity"] for s in render["subjects"]] == ["Whole market", "USDT/USD", "ETH"]
    values = render["values"]
    # rendered, but null where the store holds less history than the window (market breadth; the pair's PAR_DEV)
    assert values["Deep chain market/mktBreadth_ema14_mean2385"] is None
    assert values["Deep chain reference/parDev_ema14_mean2385"] is None
    assert all(isinstance(values[k], float) for k in ("Deep chain reference/close_mean10_z2427",
                                                      "Deep chain benchmark/RSI14_ema14_mean2385",
                                                      "Deep chain benchmark/close_mean10_z2427"))
    # the hold room: 64 past every chain but the RSI14 one (50), as on a per-coin section (tests/test_v0_14_1.py)
    assert render["conditionHoldMaxWindow"] == {
        "Deep chain market/mktBreadth_ema14_mean2385": 64, "Deep chain reference/close_mean10_z2427": 64,
        "Deep chain reference/parDev_ema14_mean2385": 64, "Deep chain benchmark/RSI14_ema14_mean2385": 50,
        "Deep chain benchmark/close_mean10_z2427": 64}


# --- (6) a runner after a LEVEL leg -----------------------------------------------------------------------------------------

def _level_r(legs: list[dict], prices: list[float], entry: float, stop: float) -> dict[int, float]:
    return {i: abs(price - entry) / abs(entry - stop) for i, (leg, price) in enumerate(zip(legs, prices))
            if leg["method"]["kind"] == "LEVEL"}


def test_a_runner_after_a_level_leg_rides_at_the_levels_r_at_a_decision():
    preview = PROBES["A1.runner_menu_staged"]["preview"]
    checked = rejected = 0
    for side, direction in preview["directions"].items():
        entry = direction["entryPrice"]
        for setup in direction["setups"]:
            legs = setup["exitPlans"][0]["targets"]
            level_r = _level_r(legs, [t["price"] for t in setup["targets"]], entry, setup["stopLossPrice"])
            assert round(tl.plan_pays(legs, level_r), 3) == setup["riskRewardRatio"], (side, legs)
            checked += 1
        for pair in direction["rejectedPairs"]:
            legs = pair["exitPlan"]["targets"]
            # a refused pair carries one target price: the level's (every refused plan here has one level leg)
            level_r = {i: abs(pair["tpPrice"] - entry) / abs(entry - pair["slPrice"])
                       for i, leg in enumerate(legs) if leg["method"]["kind"] == "LEVEL"}
            assert round(tl.plan_pays(legs, level_r), 4) == pair["computedRR"], (side, pair["reason"])
            rejected += 1
    assert (checked, rejected) == (12, 6)
    # a level plan read share-weighted: the LONG band level closing 50% reads the level's own R, and 1R 30% + the level
    # 30% reads 0.3 + 0.7 x it - not the mean over the closed share (0.5 + 0.5 x it)
    long_ = preview["directions"]["LONG"]
    (one,) = [s for s in long_["setups"] if s["stop"][0]["atrMultiple"] == 1 and len(s["exitPlans"][0]["targets"]) == 1
              and s["exitPlans"][0]["targets"][0]["method"]["kind"] == "LEVEL"]
    level = abs(one["targets"][0]["price"] - long_["entryPrice"]) / abs(long_["entryPrice"] - one["stopLossPrice"])
    assert one["riskRewardRatio"] == round(level, 3) == 5.183
    (two,) = [s for s in long_["setups"] if s["stop"][0]["atrMultiple"] == 1 and len(s["exitPlans"][0]["targets"]) == 2
              and s["exitPlans"][0]["targets"][1]["method"]["kind"] == "LEVEL"]
    assert two["riskRewardRatio"] == round(0.3 + 0.7 * level, 3) != round(0.5 + 0.5 * level, 3)


def test_the_stage_still_does_not_judge_a_level_plans_pay():
    a1 = PROBES["A1.runner_menu_staged"]
    assert a1["answer"]["errors"] == [] and a1["sent"]["axes"]["TRADE_LEVEL_POLICY"]["minRiskRewardRatio"] == 1.5
    # ... although at the preview the SHORT band level paid below the minimum and was refused there
    short = a1["preview"]["directions"]["SHORT"]["rejectedPairs"]
    assert {p["reason"] for p in short} == {"RISK_REWARD_TOO_LOW", "TARGETS_OUT_OF_ORDER"}
    assert all(p["computedRR"] < 1.5 for p in short)
    # omega's stage reading: no pay without the level's R, so no below-minimum finding
    for plan_ in a1["sent"]["axes"]["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]["SHORT"]["exitPlans"]:
        if any(t["method"]["kind"] == "LEVEL" for t in plan_["targets"]):
            assert tl.plan_pays(plan_["targets"]) is None and tl.plan_pays_exact(plan_["targets"]) is None


def test_a_runner_after_a_level_leg_is_refused_while_trailing_is_off():
    l1 = PROBES["L1.level_runner_trailing_off"]
    menu = l1["sent"]["axes"]["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]
    assert [[t["method"]["kind"] for t in p["targets"]] for p in menu["LONG"]["exitPlans"]] == [["LEVEL"]]
    assert menu["LONG"]["exitPlans"][0]["targets"][0]["closePct"] == 50
    assert l1["sent"]["axes"]["POSITION_MANAGEMENT"]["trailingEnabled"] is False
    (error,) = l1["answer"]["errors"]
    assert error["field"] == "tradeLevelMenu.LONG.exitPlans[0]" and "Trailing is off" in error["message"]
    found = [f for f in _judged(_composed("L1.level_runner_trailing_off")) if f.severity == "error"]
    assert [(f.code, f.path) for f in found] == [("TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING",
                                                  f"tradeLevelMenu.{s}.exitPlans[0]") for s in tl.SIDES]


def test_plan_pays_with_level_r_needs_every_level_leg():
    legs = [{"method": {"kind": "R_MULTIPLE", "multiple": 1}, "closePct": 30},
            {"method": {"kind": "LEVEL", "level": tl.level_ref("DONCHIAN_UPPER")}, "closePct": 30}]
    assert tl.plan_pays(legs) is None and tl.plan_pays(legs, {}) is None and tl.plan_pays(legs, {0: 2}) is None
    assert tl.plan_pays(legs, {1: 2}) == pytest.approx(0.3 + 0.7 * 2)
    assert tl.plan_pays(legs, {1: float("nan")}) is None and tl.plan_pays(legs, {1: True}) is None
    # an R-only plan reads as before, whatever level_r says
    r_only = [{"method": {"kind": "R_MULTIPLE", "multiple": 1}, "closePct": 30},
              {"method": {"kind": "R_MULTIPLE", "multiple": 3}, "closePct": 30}]
    assert tl.plan_pays(r_only) == tl.plan_pays(r_only, {1: 9}) == pytest.approx(2.4)
