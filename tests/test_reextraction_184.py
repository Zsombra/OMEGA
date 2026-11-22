"""OMEGA v0.17.0: the re-extraction at contract 184.3.2, replayed against its live record.

Record: data/audit/reextraction_184_2026-11-22.json (drafts R and X, the stage-and-discard proof). Plan:
docs/plans/2026-11-22-omega-reextraction-184.md. No rule of OMEGA's moved; what these tests hold is that the rules
measured at 182.3.2 reproduce every answer read at 184.3.2, where a decision's prices are on the venue's price grid.
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from omega.contract import load, stage_schema
from omega.trade_levels import (GRID_PROBES, STOP_RANGE_VERDICTS, entry_side_findings, outside_stop_range,
                                plan_pays_double, plan_pays_exact, stated_rr, validate_menu)

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / GRID_PROBES).read_text(encoding="utf-8"))
AT_182 = json.loads((ROOT / "data" / "audit" / "reextraction_182_2026-11-20.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "data" / "contract" / "_manifest.json").read_text(encoding="utf-8"))
MOVES = json.loads((ROOT / "data" / "contract" / "metrics" / "_moves_184.json").read_text(encoding="utf-8"))
R, X, PROOF = RECORD["drafts"]["R"], RECORD["drafts"]["X"], RECORD["proof"]
STAGES = {s["id"]: s for d in (X, R) for s in d["stages"]}           # T0 is draft R's
LEVELS = {(t["id"], t["coinTicker"]): t["answer"] for d in (R, X) for t in d["tradeLevels"]}
SIDES = {"LONG": 1, "SHORT": -1}
# one step of the price grid per coin: the finest decimal any stop or target of that coin was served at
TICKS = {"BTC": Fraction(1), "ETH": Fraction(1, 10), "SOL": Fraction(1, 1000), "XRP": Fraction(1, 10 ** 5),
         "DOGE": Fraction(1, 10 ** 6), "kPEPE": Fraction(1, 10 ** 6), "PUMP": Fraction(1, 10 ** 6)}


def F(value) -> Fraction:
    return Fraction(str(value))


def _results():
    """(preview id, coin, side, the direction's block) of every trade level preview."""
    for (ident, coin), answer in LEVELS.items():
        for side in SIDES:
            yield ident, coin, side, answer[side]


# --- the extraction -------------------------------------------------------------------------------------------------
def test_the_extraction_and_the_write_surface_are_184_3_2():
    from tests.manifest_chain import versions
    assert versions(MANIFEST)[:2] == ["184.3.2", "182.3.2"]
    assert versions(MANIFEST["writeSurface"])[:2] == ["184.3.2", "182.3.2"]
    assert MANIFEST["writeSurface"]["buildSha"] == RECORD["buildSha"]
    assert stage_schema()["contractVersion"] == RECORD["contractVersion"] == "184.3.2"
    index = json.loads((ROOT / "data/contract/metrics/_index.json").read_text(encoding="utf-8"))
    assert (index["contractVersion"], index["buildSha"], index["metricCount"]) == ("184.3.2", RECORD["buildSha"], 586)
    assert 'version = "0.17.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_the_six_draft_tools_did_not_move():
    from tests.manifest_chain import surface
    old = json.loads((ROOT / surface("182.3.2", MANIFEST)["schema"]).read_text(encoding="utf-8"))
    new = stage_schema()
    assert len(MANIFEST["writeSurface"]["tools"]) == 6
    for tool in MANIFEST["writeSurface"]["tools"]:
        assert old[tool] == new[tool], tool


def test_of_the_ten_other_authoring_tools_the_trade_level_preview_alone_moved():
    """The first diff of the sidecar (182.3.2 is its first capture). No input schema moved."""
    import scripts.capture_write_surface as cws
    from tests.manifest_chain import surface
    block = MANIFEST["writeSurface"]["authoringTools"]
    side = json.loads((ROOT / block["schema"]).read_text(encoding="utf-8"))
    assert (side["contractVersion"], side["buildSha"]) == ("184.3.2", RECORD["buildSha"])
    assert side["beside"] == Path(MANIFEST["writeSurface"]["schema"]).name and side["_absent"] == []
    assert side["liveListSha256"] == stage_schema()["liveListSha256"]                   # one list wrote both
    new = side["tools"]
    old = json.loads((ROOT / surface("182.3.2", MANIFEST)["authoringTools"]["schema"]).read_text(encoding="utf-8"))["tools"]
    assert set(new) == set(old) == set(cws.AUTHORING_TOOLS)
    moved = {(t, part) for t in new for part in ("description", "inputSchema", "outputSchema", "annotations")
             if old[t][part] != new[t][part]}
    assert moved == {("preview_strategy_trade_levels", "description"), ("preview_strategy_trade_levels", "outputSchema")}

    def built(tools):
        items = tools["preview_strategy_trade_levels"]["outputSchema"]["properties"]["previews"]["items"]
        return items["properties"]["result"]["anyOf"][2]["properties"]
    for key, field in (("setups", "stopLossDistanceAtrMultiple"), ("rejectedPairs", "slDistanceAtrMultiple")):
        before, after = built(old)[key]["items"], built(new)[key]["items"]
        assert field in before["properties"] and field in before["required"]
        assert set(before["properties"]) - set(after["properties"]) == {field}
        assert set(after["properties"]) <= set(before["properties"])
        assert set(before["required"]) - set(after["required"]) == {field}
    text = new["preview_strategy_trade_levels"]["description"]
    for phrase in ("Every price is on the venue's price grid, rounded once the way its order rests",
                   "a stop toward entry, a target away from it, a resting entry away from the mark",
                   "measured between those grid prices and stated to 4 decimals",
                   "a stop row's distance is its option's own figure"):
        assert phrase in text
        assert phrase not in old["preview_strategy_trade_levels"]["description"]
    assert "an ATR option's own multiple; bounds are inclusive" in text


def test_five_glosses_moved_in_the_corpus_and_nothing_else():
    assert (MOVES["recordsMoved"], MOVES["recordsEqual"]) == (5, 581) and MOVES["movedKeys"] == ["gloss"]
    assert MOVES["added"] == MOVES["retired"] == MOVES["anythingElseMoved"] == []
    assert set(MOVES["glosses"]) == {"SPOT_AVG_TRADE", "SPOT_CLOSE_BN", "SPOT_CLOSE_CB", "SPOT_CVD", "SPOT_DOMINANCE"}
    for metric, gloss in MOVES["glosses"].items():
        assert "own unit" in gloss["at182_3_2"] and "own unit" not in gloss["at184_3_2"]
        assert "in the unit the coin's perp is quoted in (Hyperliquid's kPEPE is 1,000 PEPE)" in gloss["at184_3_2"]
        stored = json.loads((ROOT / f"data/contract/metrics/{metric}.json").read_text(encoding="utf-8"))
        assert stored["gloss"] == gloss["at184_3_2"]
    archived = {r["metric"]: r for p in sorted((ROOT / "data/contract/metrics/archive_20261120_extraction").glob("_batch*.json"))
                for r in json.loads(p.read_text(encoding="utf-8"))}
    now = {r["metric"]: r for p in sorted((ROOT / "data/contract/metrics").glob("_batch*.json"))
           for r in json.loads(p.read_text(encoding="utf-8"))}
    assert set(archived) == set(now) == set(load().metrics) and len(now) == 586
    for metric, record in now.items():
        assert {k: v for k, v in record.items() if k != "gloss"} == {k: v for k, v in archived[metric].items() if k != "gloss"}
        assert (record["gloss"] != archived[metric]["gloss"]) == (metric in MOVES["glosses"]), metric


def test_no_condition_vocabulary_and_no_shape_count_moved():
    from tests.manifest_chain import extraction
    old, new = extraction("182.3.2", MANIFEST)["counts"], extraction("184.3.2", MANIFEST)["counts"]
    assert {k: v for k, v in old.items() if k != "_note"} == {k: v for k, v in new.items() if k != "_note"}
    shared = json.loads((ROOT / "data/contract/vocabulary/_shared.json").read_text(encoding="utf-8"))["_refreshed"]
    assert shared["contractVersion"] == "184.3.2" and shared["previous"]["contractVersion"] == "182.3.2"
    assert shared["moved"] == ["nothing: every category-invariant block is as stored"]


# --- the stage: every replayed R:R case answers as at 182.3.2 -------------------------------------------------------
def _recorded(stage: str) -> dict:
    """The stage of that id in the 182.3.2 record: the ties, else draft L, else draft E's T4."""
    for rows in (AT_182["ties"]["stages"], AT_182["drafts"]["L"]["stages"], AT_182["drafts"]["E"]["stages"]):
        for row in rows:
            if row["id"] == stage:
                return row
    raise KeyError(stage)


RR_CASES = [  # (stage, the pay exactly as written, accepted by the stage): the 182.3.2 tie cases and their controls
    ("K1", "2.2496", True), ("K2", "2.2494", False), ("K3", "1.4995", True), ("A", "2.2495", True), ("B", "2.4995", True),
    ("D6", "2.7495", True), ("D7", "2.9995", True), ("D8", "0.4995", True), ("C", "1.4995", True),
    ("D1", "1.4995", False), ("D2", "1.4995", True), ("D3", "2.2495", True), ("D4", "0.9995", True),
    ("D5", "2.7495", False), ("G4", "1.49949", False), ("G5", "1.4996", True), ("G6", "1.4994", False),
    ("T4", "1.49996", True), ("X5", "0.9994", False), ("X6", "1.9994", False)]


@pytest.mark.parametrize("stage, pays, accepted", RR_CASES)
def test_the_minimum_risk_reward_at_the_stage(stage, pays, accepted):
    record = STAGES[stage]
    sent = record["sent"]["TRADE_LEVEL_POLICY"]
    plan = sent["tradeLevelMenu"]["LONG"]["exitPlans"][1]["targets"]
    minimum = sent["minRiskRewardRatio"]
    assert plan_pays_exact(plan) == Fraction(pays) and record["answer"]["warnings"] == []
    errors = record["answer"]["errors"]
    stated = stated_rr(plan_pays_double(plan))
    assert (not errors) is accepted is (stated >= F(minimum))
    ours = [f for f in validate_menu(sent["tradeLevelMenu"], dials={k: v for k, v in sent.items() if k != "tradeLevelMenu"},
                                     sections=[], anchor="1h", trailing_enabled=True) if f.severity == "error"]
    assert bool(ours) is not accepted
    if not accepted:
        assert ours[0].code == "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR" and ours[0].path == errors[0]["field"]
        assert f"pays {float(stated):g}R" in ours[0].message
        # one wording moved: the minimum is stated to two decimals (as many as it needs at 182.3.2)
        assert errors[0]["message"] == (
            f"The LONG exit plan pays {float(stated):g}R, below this strategy's minimum risk-reward of "
            f"{float(minimum):.2f}: every pair it makes would be refused. Change the plan or lower the minimum.")


@pytest.mark.parametrize("stage", [s for s, _, _ in RR_CASES if not s.startswith("X")] + ["G1", "F1", "F4"])
def test_a_replayed_stage_sent_the_182_body_and_got_its_verdict(stage):
    old, new = _recorded(stage), STAGES[stage]
    assert new["sent"] == old["sent"]

    def verdict(row, keys):
        return [[(e["field"], e["message"].split(" of ")[0]) for e in row["answer"][key]] for key in keys]
    assert verdict(new, ("errors", "warnings")) == verdict(old, ("errors", "warnings"))
    if not old["answer"]["errors"]:
        assert new["answer"]["errors"] == []
    elif stage in ("G4", "G6", "D1"):
        assert "minimum risk-reward of 1.5:" in old["answer"]["errors"][0]["message"]
        assert "minimum risk-reward of 1.50:" in new["answer"]["errors"][0]["message"]


# --- a decision: prices on the grid, the R:R the plan's own ----------------------------------------------------------
def test_every_price_is_on_the_grid_rounded_the_way_its_order_rests():
    """A stop toward entry, a target away from it, each within one tick of the unrounded price; a target at R is R
    times the distance to the ROUNDED stop. (An at-market entry is the mark as it stands: not on the grid.)"""
    stops = {"ATR": 0, "LEVEL": 0}
    targets = off_grid_marks = 0
    for ident, coin, side, block in _results():
        result, sign, tick = block["result"], SIDES[side], TICKS[coin]
        entry, atr = F(result["snapshot"]["entryPrice"]), F(result["snapshot"]["atr"])
        off_grid_marks += (entry / tick).denominator != 1
        for s in result["stopCandidates"]:
            if s["price"] is None:
                assert s["verdict"] == "LEVEL_UNREAD"
                continue
            price = F(s["price"])
            unrounded = entry - sign * F(s["atrMultiple"]) * atr if s["method"]["kind"] == "ATR" else F(s["levelReading"])
            assert (price / tick).denominator == 1 and 0 <= sign * (price - unrounded) < tick, (ident, coin, side, s)
            stops[s["method"]["kind"]] += 1
        for s in result["setups"]:
            risk = abs(entry - F(s["stopLossPrice"]))
            for plan in s["exitPlans"]:
                for leg, priced in zip(plan["targets"], s["targets"], strict=True):
                    price = F(priced["price"])
                    assert (price / tick).denominator == 1 and leg["closePct"] == priced["closePct"]
                    if leg["method"]["kind"] == "R_MULTIPLE":
                        unrounded = entry + sign * F(leg["method"]["multiple"]) * risk
                        assert 0 <= sign * (price - unrounded) < tick, (ident, coin, side, s)
                        targets += 1
    assert (stops, targets) == ({"ATR": 214, "LEVEL": 21}, 380)
    assert off_grid_marks == 4                    # BTC at 59081.7 (LB) and 59073.8 (LLV) (two previews, both directions)


def test_a_pairs_distances_are_between_grid_prices_and_a_stop_rows_is_its_options_own():
    fields = set()
    for _, _, side, block in _results():
        result = block["result"]
        entry, atr = F(result["snapshot"]["entryPrice"]), F(result["snapshot"]["atr"])

        def pct(price):
            return float(abs(F(price) - entry) / entry * 100)
        for s in result["setups"]:
            fields |= set(s)
            assert s["stopLossDistancePct"] == pytest.approx(round(pct(s["stopLossPrice"]), 4), abs=1e-9)
            assert s["takeProfitDistancePct"] == pytest.approx(round(pct(s["takeProfitPrice"]), 4), abs=1e-9)
        for s in result["rejectedPairs"]:
            fields |= set(s)
        for s in result["stopCandidates"]:
            if s["price"] is None:
                continue
            assert s["distancePct"] == pytest.approx(pct(s["price"]), abs=1e-9)          # in full, not four decimals
            if s["method"]["kind"] == "ATR":
                assert s["distanceAtrMultiple"] == s["atrMultiple"] == s["method"]["atrMultiple"]
            else:
                assert s["distanceAtrMultiple"] == pytest.approx(float(abs(F(s["price"]) - entry) / atr), abs=1e-9)
    assert not fields & {"stopLossDistanceAtrMultiple", "slDistanceAtrMultiple"}          # README v183


def _level_r(plan: dict, prices: list, entry: Fraction, stop) -> dict:
    """The R each level leg makes between the served grid prices."""
    return {i: float(abs(F(price) - entry) / abs(entry - F(stop)))
            for i, (leg, price) in enumerate(zip(plan["targets"], prices, strict=True))
            if leg["method"]["kind"] == "LEVEL"}


def test_the_risk_reward_is_the_plans_own_whatever_the_grid_makes_of_its_prices():
    """Every plan of every setup, and every refused pair: stated_rr(plan_pays_double(legs, level_r)), an R leg at its
    own multiple and a level leg at the R between the grid prices. The ratio of the rounded prices differs on 56."""
    plans = parted = 0
    for ident, coin, side, block in _results():
        result = block["result"]
        entry = F(result["snapshot"]["entryPrice"])
        for s in result["setups"]:
            risk = abs(entry - F(s["stopLossPrice"]))
            for plan in s["exitPlans"]:
                level_r = _level_r(plan, [t["price"] for t in s["targets"]], entry, s["stopLossPrice"])
                assert float(stated_rr(plan_pays_double(plan["targets"], level_r))) == s["riskRewardRatio"], (ident, coin, side)
                assert F(s["riskRewardRatio"]) >= F(block["minRiskRewardRatio"])
                plans += 1
                ratio = sum(Fraction(t["closePct"], 100) * abs(F(t["price"]) - entry) / risk for t in s["targets"])
                parted += round(float(ratio), 3) != s["riskRewardRatio"]
    assert (plans, parted) == (301, 56)
    refused = [(side, block, pair) for _, _, side, block in _results() for pair in block["result"]["rejectedPairs"]]
    assert len(refused) == 11
    for _, block, pair in refused:
        entry = F(block["result"]["snapshot"]["entryPrice"])
        legs = pair["exitPlan"]["targets"]
        # every refused plan's only level leg is its last, whose price is the pair's tpPrice
        level_r = _level_r(pair["exitPlan"], [pair["tpPrice"]] * len(legs), entry, pair["slPrice"])
        assert set(level_r) <= {len(legs) - 1}
        stated = stated_rr(plan_pays_double(legs, level_r))
        assert float(stated) == pair["computedRR"]
        below = stated < F(block["minRiskRewardRatio"])
        assert pair["reason"] in ("RISK_REWARD_TOO_LOW", "TARGETS_OUT_OF_ORDER")
        assert below or pair["reason"] == "TARGETS_OUT_OF_ORDER"


def test_the_level_leg_pays_the_grid_prices_not_the_unrounded_stop():
    block = LEVELS[("LLV", "BTC")]["LONG"]["result"]
    entry, atr = F(block["snapshot"]["entryPrice"]), F(block["snapshot"]["atr"])
    [pair] = [s for s in block["setups"] if s["riskRewardRatio"] == 3.157]
    [stop] = [s for s in block["stopCandidates"] if s["method"] == {"kind": "ATR", "atrMultiple": 1}]
    assert pair["stopLossPrice"] == stop["price"] == 58470
    assert round(float((F(pair["takeProfitPrice"]) - entry) / atr), 3) == 3.154      # against the unrounded 1 ATR stop


def test_the_r_leg_pays_its_multiple_where_the_rounded_prices_make_another_ratio():
    block = LEVELS[("LG1", "PUMP")]["LONG"]["result"]
    entry = F(block["snapshot"]["entryPrice"])
    [pair] = [s for s in block["setups"] if s["stopLossMethods"] == [{"kind": "ATR", "atrMultiple": 1}]
              and len(s["targets"]) == 1]
    ratio = abs(F(pair["takeProfitPrice"]) - entry) / abs(entry - F(pair["stopLossPrice"]))
    assert pair["riskRewardRatio"] == 1.5 and round(float(ratio), 3) == 1.512


def test_a_runner_rides_at_the_last_closing_leg_as_before():
    """X3: 1R 50% + 2R 20% + a 30% runner pays 1.5R, with or without a trail objective at 6R (trail 2.7R = 6 x the 45%
    giveback, as at 171.0.0). X4: a level leg closing 50% and its runner pay the level's R."""
    for coin in ("BTC", "PUMP"):
        for side in SIDES:
            rows = LEVELS[("LX3", coin)][side]["result"]["setups"]
            assert [(s["riskRewardRatio"], s["runnerTrail"]["rMultiple"]) for s in rows] == [(1.5, 1), (1.5, 2.7)]
            block = LEVELS[("LX4", coin)][side]["result"]
            [row] = block["setups"]
            entry = F(block["snapshot"]["entryPrice"])
            level = abs(F(row["takeProfitPrice"]) - entry) / abs(entry - F(row["stopLossPrice"]))
            assert row["riskRewardRatio"] == round(float(level), 3) and row["targets"][0]["closePct"] == 50
    assert LEVELS[("LX4", "BTC")]["LONG"]["result"]["setups"][0]["riskRewardRatio"] == 3.419


def test_what_the_grid_makes_equal_becomes_one_setup():
    """No two setups of a direction share their stop and target prices: two plans at one set of prices are one row with
    two exitPlans, two surviving stops at one price one row with two stopLossMethods (X2, PUMP). At 182.3.2 every tie
    preview made four setups a side."""
    plans = stops = 0
    for _, _, _, block in _results():
        rows = block["result"]["setups"]
        keys = [(s["stopLossPrice"], tuple((t["price"], t["closePct"]) for t in s["targets"])) for s in rows]
        assert len(keys) == len(set(keys)) == block["result"]["counters"]["survivingSetups"]
        plans += sum(len(s["exitPlans"]) == 2 for s in rows)
        stops += sum(len(s["stopLossMethods"]) == 2 for s in rows)
    assert (plans, stops) == (28, 4)
    old = next(t for t in AT_182["ties"]["tradeLevels"] if t["id"] == "LK1")["answer"]["LONG"]["setups"]
    new = LEVELS[("LK1", "BTC")]["LONG"]["result"]["setups"]
    assert (len(old), len(new)) == (4, 2)
    for row in new:
        assert [p["targets"][0]["method"]["multiple"] for p in row["exitPlans"]] == [2.25, 2.2496]
        assert row["riskRewardRatio"] == 2.25
    for side in SIDES:
        for coin, methods in (("PUMP", [[0.8, 0.801], [1.5, 1.501]]), ("BTC", [[0.8], [0.801], [1.5], [1.501]])):
            rows = LEVELS[("LX2", coin)][side]["result"]["setups"]
            assert [[m["atrMultiple"] for m in s["stopLossMethods"]] for s in rows] == methods, (side, coin)


def test_two_legs_at_one_grid_price_are_refused_at_a_decision_the_stage_accepts_them():
    """X1: 1.5R 50% + 1.5001R 50% stages clean (the second leg is farther as written) and survives on BTC; on kPEPE both
    price at one tick and the pair is refused TARGETS_OUT_OF_ORDER. OMEGA knows no coin's tick and says nothing."""
    assert STAGES["X1"]["answer"] == {"errors": [], "warnings": []}
    sent = STAGES["X1"]["sent"]["TRADE_LEVEL_POLICY"]
    assert validate_menu(sent["tradeLevelMenu"], dials={"minRiskRewardRatio": 1.5}, sections=[], anchor="1h",
                         trailing_enabled=True) == []
    for side, sign in SIDES.items():
        survived = LEVELS[("LX1", "BTC")][side]["result"]
        assert survived["rejectedPairs"] == [] and [len(s["targets"]) for s in survived["setups"]] == [1, 2]
        first, second = survived["setups"][1]["targets"]
        assert sign * (second["price"] - first["price"]) == 1                       # one dollar, one tick
        coarse = LEVELS[("LX1", "kPEPE")][side]["result"]
        [pair] = coarse["rejectedPairs"]
        assert (pair["reason"], pair["computedRR"]) == ("TARGETS_OUT_OF_ORDER", 1.5)
        assert [len(s["targets"]) for s in coarse["setups"]] == [1]
        assert coarse["setups"][0]["takeProfitPrice"] == pair["tpPrice"]             # 1.5R itself prices at that tick


@pytest.mark.parametrize("coin", ["BTC", "ETH", "SOL", "DOGE", "XRP", "kPEPE", "PUMP"])
def test_the_stop_range_is_judged_on_the_multiple_on_every_coin(coin):
    """G1 again (0.5 / 0.79 / 0.8 / 1 / 1.5 / 1.8 / 1.81 / 2 under 0.8 - 1.8), on seven coins: the bounds are inclusive
    and the verdict is the option's own multiple. The 0.8 stop's percent distance lies below the floor's on all seven
    (its price is rounded toward entry) and it survives - the SOL case of 182.3.2, now everywhere; the 1.8 stop's lies
    below the ceiling's everywhere, so 182.3.2's other half (above it) no longer occurs."""
    for side in SIDES:
        block = LEVELS[("LG1", coin)][side]
        assert (block["minStopLossAtrMultiple"], block["maxStopLossAtrMultiple"]) == (0.8, 1.8)
        stops = {s["atrMultiple"]: s for s in block["result"]["stopCandidates"]}
        assert sorted(stops) == [0.5, 0.79, 0.8, 1, 1.5, 1.8, 1.81, 2]
        for multiple, s in stops.items():
            verdict = outside_stop_range(multiple, 0.8, 1.8)
            assert s["verdict"] == (verdict or "SURVIVED"), (coin, side, s)
            assert s["responsibleBound"] == STOP_RANGE_VERDICTS.get(verdict)
        band = block["result"]["stopBand"]
        assert stops[0.8]["distancePct"] < band["requestedMinPct"] and stops[0.8]["verdict"] == "SURVIVED"
        assert stops[1.8]["distancePct"] < band["requestedMaxPct"] and stops[1.8]["verdict"] == "SURVIVED"
        if coin in ("kPEPE", "PUMP"):
            # one price, one percent distance, two verdicts
            assert stops[0.79]["price"] == stops[0.8]["price"] and stops[0.79]["distancePct"] == stops[0.8]["distancePct"]
            assert (stops[0.79]["verdict"], stops[0.8]["verdict"]) == ("BELOW_FLOOR", "SURVIVED")
            assert stops[1.81]["price"] == stops[1.8]["price"] and stops[1.81]["verdict"] == "ABOVE_CEILING"
            assert stops[1.81]["distancePct"] < stops[1.81]["rejectedByThresholdPct"]


def test_every_atr_stop_of_every_preview_is_judged_on_its_multiple():
    seen = 0
    for _, _, _, block in _results():
        for s in block["result"]["stopCandidates"]:
            if s["method"]["kind"] == "ATR":
                verdict = outside_stop_range(s["atrMultiple"], block["minStopLossAtrMultiple"],
                                             block["maxStopLossAtrMultiple"])
                assert s["verdict"] == (verdict or "SURVIVED")
                seen += 1
    assert seen == 214


# --- the level entry ----------------------------------------------------------------------------------------------------
def test_a_resting_entry_is_on_the_grid_away_from_the_mark():
    seen = []
    for ident, coin, side, block in _results():
        entry = block["entry"]
        if entry is None:
            continue
        tick, sign = TICKS[coin], SIDES[side]
        placed, level, mark, atr = (F(entry[k]) for k in ("placedPrice", "levelPrice", "mark", "atr"))
        offset = F(entry["offsetAtrMultiple"]) * atr
        # a stop order beyond the level, a limit on this side of it
        unrounded = level + sign * offset
        away = 1 if entry["placedSide"] == "above" else -1
        assert (placed / tick).denominator == 1 and 0 <= away * (placed - unrounded) < tick and away * (placed - mark) > 0
        assert entry["outcome"] == "RESTS" and entry["validForMinutes"] == 240
        assert entry["distancePct"] == pytest.approx(round(float(abs(placed - mark) / mark * 100), 4), abs=1e-9)
        assert entry["distanceAtr"] == pytest.approx(float(abs(placed - mark) / atr), abs=1e-9)       # in full
        assert block["result"]["snapshot"]["entryPrice"] == entry["placedPrice"]     # the pairs are built at it
        seen.append((ident, coin, side, entry["orderType"]))
    assert len(seen) == 8 and {order for _, _, _, order in seen} == {"TRIGGER", "LIMIT"}


@pytest.mark.parametrize("stage", ["F1", "F2", "F4", "N1", "N2"])
def test_the_side_warning_fires_as_omega_draws_it(stage):
    """F4 (Donchian) and N1 (a nearest level: the naked POCs) warn under STOP_THROUGH_LEVEL; N2, the same level under
    the order that rests there, and the Bollinger bands do not."""
    record = STAGES[stage]
    platform = sorted((w["field"], w["message"]) for w in record["answer"]["warnings"])
    assert {w["code"] for w in record["answer"]["warnings"]} <= {"ENTRY_LEVEL_USUALLY_SKIPPED"}
    ours = sorted((f.path, f.message) for f in entry_side_findings(record["sent"]["ENTRY"]["entry"]))
    assert ours == platform and len(platform) == (2 if stage in ("F4", "N1") else 0)
    assert record["answer"]["errors"] == []


def test_a_nearest_stop_level_looks_past_its_own_pick_to_one_beyond_the_entry():
    """README v183's sentence, on SOL: at the market entry the naked POC above is 70.60; with the short resting at
    71.443 (F2) that one is on the profit side, and the row reads the next, 72.66."""
    def poc(ident):
        block = LEVELS[(ident, "SOL")]["SHORT"]["result"]
        [row] = [s for s in block["stopCandidates"] if s["method"].get("level", {}).get("metric") == "NAKED_POC_ABOVE"]
        return block["snapshot"]["entryPrice"], row["levelReading"], row["verdict"]
    market, resting = poc("LLV"), poc("LF2")
    assert market == (69.185, 70.60339825, "ABOVE_CEILING")
    assert resting == (71.443, 72.66399375, "SURVIVED") and market[1] < resting[0] < resting[1]


# --- the drafts and the proof -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("draft", ["R", "X"])
def test_the_draft_was_staged_in_order_discarded_and_read_back_null(draft):
    d = RECORD["drafts"][draft]
    for when in ("versionBefore", "versionAfter"):
        assert (d[when]["contractVersion"], d[when]["buildSha"]) == ("184.3.2", RECORD["buildSha"])
    assert d["versionBefore"]["at"] < d["stages"][0]["at"] < d["discard"]["at"] < d["versionAfter"]["at"]
    for when in ("listStrategyDraftsBefore", "listStrategyDraftsAfter"):
        [only] = d[when]["drafts"]
        assert (only["strategyId"][:8], only["strategyName"], only["version"], only["updatedAt"][:10]) == (
            "c1fd5d4c", "VWAP Reject 15m", 9, "2026-10-23")
    n = len(d["stages"])
    assert [(s["namedDraftVersion"], s["versionAfter"]) for s in d["stages"]] == [(i, i + 1) for i in range(n)]
    assert d["stages"][0]["answer"] == {"errors": [], "warnings": []}
    assert d["readBack"]["draftVersion"] == d["discard"]["draftVersion"] == n and d["readBack"]["committedRevision"] is None
    assert d["discard"]["answer"] == {"strategyId": d["strategyId"], "discarded": True}
    assert d["discard"]["readAfter"] == {"draft": None, "draftVersion": 0, "committedRevision": None}


def test_the_call_counts_are_the_records():
    calls = RECORD["calls"]
    assert calls["createDrafts"] == {R["strategyId"]: 26, X["strategyId"]: 7, PROOF["strategyId"]: 1}
    assert sum(calls["createDrafts"].values()) == calls["stage_strategy_draft"] == 34
    assert calls["discard_strategy_draft"] == 3
    assert calls["preview_strategy_trade_levels"] == len(R["tradeLevels"]) + len(X["tradeLevels"]) + 1 == 38
    assert (calls["preview_strategy_report"], calls["get_metric_construction_hints"]) == (1, 586)


def test_the_proof_body_is_what_omega_generates_and_it_staged_clean():
    from omega.generate import PRESETS, plan
    from omega.preflight import body_sha256
    axes = plan(PRESETS[PROOF["preset"]]).axes()
    assert axes == PROOF["sentAxes"] and body_sha256(axes) == PROOF["bodySha256Sent"]
    assert PROOF["stage"]["answer"] == {"errors": [], "warnings": []}
    assert sorted(PROOF["stage"]["stagedAxes"]) == sorted(axes)
    read = PROOF["readBack"]
    assert read["diagnostics"] == {"errors": [], "warnings": []} and read["committedRevision"] is None
    assert read["contentEqualsSentAsValues"] is True and read["axesThatDiffer"] == []
    assert read["bodySha256Read"] == read["bodySha256SentWithIntegralFloatsAsIntegers"]
    report = PROOF["reportPreview"]
    assert report["missingConditionColumns"] == report["duplicateHeaders"] == [] and len(report["renderedSections"]) == 3
    for side in SIDES:
        assert PROOF["tradeLevels"][side] == {
            "entry": None, "stage": "OK", "stops": [[1, "SURVIVED"], [1.5, "SURVIVED"], [2, "SURVIVED"]],
            "survivingSetups": 9, "riskRewardRatios": [1.5, 2, 3]}
    assert PROOF["discard"]["answer"]["discarded"] is True
    assert PROOF["discard"]["readAfter"] == {"draft": None, "draftVersion": 0, "committedRevision": None}
    [only] = PROOF["discard"]["listStrategyDraftsAfter"]["drafts"]
    assert only["strategyName"] == "VWAP Reject 15m" and only["version"] == 9
    assert PROOF["versionBefore"]["contractVersion"] == PROOF["versionAfter"]["contractVersion"] == "184.3.2"
    # the same body the 182.3.2 proof staged, read back to the same bytes: the generator did not move
    assert AT_182["proof"]["bodySha256Sent"] == PROOF["bodySha256Sent"]
    assert AT_182["proof"]["readBack"]["bodySha256Read"] == read["bodySha256Read"]
