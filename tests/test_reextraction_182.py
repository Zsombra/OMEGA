"""OMEGA v0.16.0: the re-extraction at contract 182.3.2, replayed against its live record.

Record: data/audit/reextraction_182_2026-11-20.json (previews A1 - A7, B, C, D, H1 - H8, V182, TF; drafts E, L and the
side sweep S; the stage-and-discard proof). Plan: docs/plans/2026-11-20-omega-reextraction-182.md.
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import get_args

import pytest

from omega.contract import REFERENCE_PRICES, load, price_operand_refused, stage_schema
from omega.fanout import outputs_for
from omega.types import Column
from omega.validate import validate_column

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data" / "audit" / "reextraction_182_2026-11-20.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "data" / "contract" / "_manifest.json").read_text(encoding="utf-8"))
MOVES = json.loads((ROOT / "data" / "contract" / "metrics" / "_moves_182.json").read_text(encoding="utf-8"))
P = RECORD["previews"]
DRAFTS = RECORD["drafts"]
L_STAGES = {s["id"]: s for s in DRAFTS["L"]["stages"]}
E_STAGES = {s["id"]: s for s in DRAFTS["E"]["stages"]}
L_LEVELS = {(t["id"], t["coinTicker"]): t["answer"] for t in DRAFTS["L"]["tradeLevels"]}
SCHEMA_180_4 = ROOT / "data/contract/stage_strategy_draft/schema_20261119T202415Z.json"


def _errors(column: Column):
    return [f for f in validate_column(column) if f.severity == "error"]


def _refused(preview: dict) -> dict | None:
    return preview["answer"]["refusal"]


def _sent(preview: dict) -> list[Column]:
    return [Column.model_validate(c) for c in preview["sent"]["columns"]]


# --- the extraction -------------------------------------------------------------------------------------------------
def test_the_extraction_and_the_write_surface_are_182_3_2():
    from tests.manifest_chain import versions
    assert versions(MANIFEST)[:2] == ["182.3.2", "180.4.0"]
    assert versions(MANIFEST["writeSurface"])[:2] == ["182.3.2", "180.4.0"]
    assert MANIFEST["writeSurface"]["buildSha"] == RECORD["buildSha"]
    assert stage_schema()["contractVersion"] == RECORD["contractVersion"] == "182.3.2"
    index = json.loads((ROOT / "data/contract/metrics/_index.json").read_text(encoding="utf-8"))
    assert (index["contractVersion"], index["buildSha"], index["metricCount"]) == ("182.3.2", RECORD["buildSha"], 586)
    assert 'version = "0.16.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_the_six_draft_tools_moved_in_one_output_schema_and_no_input():
    """180.4.0 -> 182.3.2: preview_strategy_report's output schema (README v182) and nothing else - no description,
    no input schema. v181 moved no schema."""
    old = json.loads(SCHEMA_180_4.read_text(encoding="utf-8"))
    new = stage_schema()
    tools = MANIFEST["writeSurface"]["tools"]
    moved = {(t, part) for t in tools for part in ("description", "inputSchema", "outputSchema", "annotations")
             if old[t].get(part) != new[t].get(part)}
    assert moved == {("preview_strategy_report", "outputSchema")}
    out_old = old["preview_strategy_report"]["outputSchema"]["properties"]
    out_new = new["preview_strategy_report"]["outputSchema"]["properties"]

    def outcome(props):
        return props["authoring"]["anyOf"][0]["properties"]["conditionOutcomes"]["items"]["properties"]["outcomes"]["items"]
    assert "developingRead" in outcome(out_old)["properties"] and "developingRead" in outcome(out_old)["required"]
    assert "developingRead" not in outcome(out_new)["properties"]
    assert "developingAsOf" in outcome(out_new)["properties"] and "developingAsOf" in outcome(out_new)["required"]

    def column(props):
        return props["renderedSections"]["items"]["oneOf"][0]["properties"]["section"]["properties"]["columns"]["items"]
    assert "asOf" not in column(out_old)["properties"]
    assert "asOf" in column(out_new)["properties"] and "asOf" not in column(out_new).get("required", [])


def test_the_other_authoring_tools_are_captured_from_this_contract_on():
    import scripts.capture_write_surface as cws
    block = MANIFEST["writeSurface"]["authoringTools"]
    side = json.loads((ROOT / block["schema"]).read_text(encoding="utf-8"))
    assert (side["contractVersion"], side["buildSha"]) == ("182.3.2", RECORD["buildSha"])
    assert side["beside"] == Path(MANIFEST["writeSurface"]["schema"]).name and side["_absent"] == []
    assert set(side["tools"]) == set(cws.AUTHORING_TOOLS)
    for tool in side["tools"].values():
        assert tool["description"] and tool["inputSchema"]["type"] == "object"
    # the three statements 182.3.x added to the trade level preview's description, each measured below
    text = side["tools"]["preview_strategy_trade_levels"]["description"]
    for phrase in ("an ATR option's own multiple; bounds are inclusive", "stated to three decimals",
                   "distancePct, distanceAtr", "validForMinutes"):
        assert phrase in text


def test_the_sidecar_refuses_a_list_that_is_not_the_capture_it_sits_beside():
    import scripts.capture_write_surface as cws
    from datetime import UTC, datetime
    version = {"contractVersion": "182.3.2", "buildSha": "b" * 40}
    tools = [{"name": n, "description": f"d-{n}", "inputSchema": {"type": "object"}, "outputSchema": {}}
             for n in cws.TOOLS + cws.AUTHORING_TOOLS[:-1]]
    beside = {**version, **{t["name"]: {k: t[k] for k in cws.PARTS} for t in tools if t["name"] in cws.TOOLS}}
    at = datetime(2026, 11, 20, 16, 30, tzinfo=UTC)
    side = cws.authoring_tools(version=version, raw=b"x", tools=tools, listed_at=at, beside=beside,
                               beside_name="schema_a.json")
    assert side["beside"] == "schema_a.json" and side["_absent"] == [cws.AUTHORING_TOOLS[-1]]
    assert set(side["tools"]) == set(cws.AUTHORING_TOOLS[:-1])
    moved = {**beside, "get_strategy": {**beside["get_strategy"], "description": "other"}}
    with pytest.raises(SystemExit, match="differ from schema_a.json"):
        cws.authoring_tools(version=version, raw=b"x", tools=tools, listed_at=at, beside=moved,
                            beside_name="schema_a.json")
    with pytest.raises(SystemExit, match="not the same surface"):
        cws.authoring_tools(version=version, raw=b"x", tools=tools, listed_at=at,
                            beside={**beside, "buildSha": "c" * 40}, beside_name="schema_a.json")
    own = cws.authoring_tools(version=version, raw=b"x", tools=tools, listed_at=at)
    assert own["beside"] == "schema_20261120T163000Z.json"


# --- v181, served: the hints carry the rule -------------------------------------------------------------------------
def test_the_hints_list_no_reference_price_for_a_base_that_is_not_one():
    c = load()
    assert REFERENCE_PRICES == ("CLOSE", "LAST")
    price = [m for m in c.metrics.values() if m.unit == "price"]
    others = [m for m in price if m.metric not in REFERENCE_PRICES]
    assert (len(price), len(others)) == (418, 416) == (MOVES["priceBases"], MOVES["recordsMoved"])
    for m in c.metrics.values():
        if m.metric in REFERENCE_PRICES:
            continue
        for served in (m.spread_operands, m.spread_operands_off_anchor or ()):
            assert not set(REFERENCE_PRICES) & set(served), m.metric
        for spec in m.transforms.values():
            for outer in (spec.get("chainedOuters") or {}).values():
                for key in ("operands", "operandsOffAnchor"):
                    assert not set(REFERENCE_PRICES) & set(outer.get(key) or ()), (m.metric, key)
    close, last = c.metrics["CLOSE"], c.metrics["LAST"]
    assert "LAST" in close.spread_operands and "CLOSE" in last.spread_operands
    assert "LAST" in close.spread_operands_off_anchor and "CLOSE" in last.spread_operands_off_anchor
    # an average of price stays an operand of every price base (README v181: the averaged lists are unchanged)
    assert all("CLOSE" in m.spread_average_operands for m in price)
    # and CLOSE's own averages keep LAST: the base decides, averaged or not
    assert sorted(t for t, spec in close.transforms.items()
                  if "LAST" in ((spec.get("chainedOuters") or {}).get("spread") or {}).get("operands", ())) == [
        "aggregate", "ema", "rma", "wma"]
    assert MOVES["anythingElseMoved"] == [] and MOVES["movedAreThePriceBasesThatAreNotReferencePrices"] is True
    assert MOVES["operandLists"]["plainListsOfTheBase"]["removed"] == {
        "spreadOperands": {"CLOSE": 416, "LAST": 416}, "spreadOperandsOffAnchor": {"CLOSE": 416, "LAST": 416}}
    # the served text names the reference prices
    authoring = json.loads((ROOT / "data/contract/transforms/_authoring.json").read_text(encoding="utf-8"))
    assert "never a reference price (CLOSE, LAST) unless the base is one" in (
        authoring["transforms"]["spread"]["parameters"]["inputs"]["description"])


@pytest.mark.parametrize("key", ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "H4", "H5", "H7"])
def test_the_refused_forms_are_refused_live_and_by_omega(key):
    """Each is REPORT_COLUMN_OPERAND_UNSUPPORTED on the platform, naming the form to write where the server admits it
    at the column's rung; omega refuses the same column from extracted data and names a form in the same cases."""
    refusal = _refused(P[key])
    assert refusal["code"] == "VALIDATION_ERROR" and refusal["authoringCode"] == "REPORT_COLUMN_OPERAND_UNSUPPORTED"
    assert refusal["receivedValue"] in REFERENCE_PRICES and "is a reference price" in refusal["message"]
    assert refusal["path"] == ["sections", 0, "columns", 0, "inputs", 0, "metric"]
    [column] = _sent(P[key])
    found = [f for f in _errors(column) if f.code == "OPERAND_NOT_ALLOWED"]
    assert len(found) == 1 and "v181" in found[0].message
    platform_names_a_form = "; write " in refusal["message"]
    assert platform_names_a_form == ("Write " in found[0].message), (refusal["message"], found[0].message)
    assert platform_names_a_form == (key not in ("A6", "A7"))
    if platform_names_a_form:
        # the same form, in the platform's spelling (x for the multiplication sign, `{ metric: ... }` spaced)
        written = refusal["message"].split("; write ", 1)[1].replace("×", "x")
        ours = found[0].message.split("Write ", 1)[1].split(": price is the base", 1)[0]
        assert written.replace("{ ", "{").replace(" }", "}") == ours


def test_the_refusal_names_the_operands_it_admits_and_no_reference_price():
    domain = _refused(P["A1"])["allowedDomain"]
    assert domain["kind"] == "enum" and domain["holds"]["CLOSE"] is False and domain["holds"]["LAST"] is False
    assert all(domain["holds"][k] for k in ("MARK", "ORACLE", "OPEN", "HIGH", "LOW", "HL2", "HLC3", "OHLC4", "EMA20"))
    assert domain["count"] == len(load().metrics["PRIOR_TPO_VAL"].spread_operands)


def test_the_reference_prices_are_close_and_last_and_no_other_price():
    """B: every other price renders as EMA20's plain operand. D: every other price is refused as the base of a spread
    over CLOSE - it is "another reading", not a reference price."""
    assert set(P["B"]["cases"]) == {"MARK", "ORACLE", "OPEN", "HIGH", "LOW", "HL2", "HLC3", "OHLC4", "SPOT_CLOSE_CB",
                                    "SPOT_CLOSE_BN"}
    for operand, preview in P["B"]["cases"].items():
        assert _refused(preview) is None, operand
        [column] = _sent(preview)
        assert not _errors(column) and not price_operand_refused("EMA20", operand)
        assert [o.header for o in outputs_for(column)] == [c["key"] for c in preview["answer"]["columns"]]
    assert set(P["D"]["cases"]) == {"MARK", "ORACLE", "OPEN", "HIGH", "LOW", "HL2"}
    for base, preview in P["D"]["cases"].items():
        assert _refused(preview)["authoringCode"] == "REPORT_COLUMN_OPERAND_UNSUPPORTED", base
        assert f"write CLOSE × spread({base})" in _refused(preview)["message"]
        [column] = _sent(preview)
        assert [f.code for f in _errors(column)] == ["OPERAND_NOT_ALLOWED"] and price_operand_refused(base, "CLOSE")


@pytest.mark.parametrize("key", ["C", "H1", "H2", "H3", "H8", "COV"])
def test_the_kept_forms_render_and_omega_predicts_their_headers(key):
    """C: two reference prices in both orders, an averaged price operand, price as the base. H1 - H3: CLOSE's own
    averages spread against LAST, on and off the anchor - the form v0.15.0 refused on the README's one example. COV:
    the same four chains as omega.space writes them, the shapes the coverage ledger now holds."""
    preview = P[key]
    assert _refused(preview) is None
    rendered = [c["key"] for c in preview["answer"]["columns"]]
    predicted = []
    for column in _sent(preview):
        assert not _errors(column), column
        predicted += [o.header for o in outputs_for(column)]
    assert predicted == rendered
    if key == "H1":
        assert rendered == ["close_ema34_last_spread"]
    if key == "COV":
        from scripts.render_coverage import CACHE, SEEN_FILES
        assert rendered == ["close_mean24_last_spread", "close_ema20_last_spread", "close_rma14_last_spread",
                            "close_wma20_last_spread"]
        assert "_probe_182_2026-11-20.json" in SEEN_FILES
        assert set(rendered) <= set(json.loads((CACHE / "_probe_182_2026-11-20.json").read_text(
            encoding="utf-8"))["headers"])
    if key == "C":
        assert rendered[:2] == ["close_last_spread", "last_close_spread"]


def test_a_chain_after_a_reference_price_spread_is_refused_for_its_own_reason():
    """H6: CLOSE x spread(LAST) -> trajectory is no chain (LAST has no per-bar value); not the v181 refusal."""
    refusal = _refused(P["H6"])
    assert refusal["authoringCode"] == "REPORT_COLUMN_CHAIN_UNSUPPORTED" and "no per-bar value" in refusal["message"]
    column = _sent(P["H6"])[1]
    assert _errors(column) and not any("v181" in f.message for f in _errors(column))


def test_no_enumerated_shape_is_one_the_platform_refused():
    from omega.space import enumerate_shapes
    shapes = enumerate_shapes(expand_operands=True)
    assert len(shapes) == MANIFEST["counts"]["operandExpandedShapes"] == 515965
    held = {(s.metric, s.transform, s.chained, s.operand) for s in shapes if s.operand in REFERENCE_PRICES}
    assert ("CLOSE", "ema", "spread", "LAST") in held and ("CLOSE", "spread", None, "LAST") in held
    assert ("LAST", "spread", None, "CLOSE") in held
    assert all(metric in REFERENCE_PRICES for metric, *_ in held)
    assert len(enumerate_shapes()) == MANIFEST["counts"]["structuralShapes"] == 27424


# --- v182: a Developing read states when it was read ------------------------------------------------------------------
def test_an_outcome_states_developing_as_of_and_the_inventory_keeps_developing_read():
    answer = P["V182"]["answer"]
    assert "developingAsOf" in answer["outcomeKeys"] and "developingRead" not in answer["outcomeKeys"]
    assert "developingRead" in answer["inventoryOutputKeys"]
    inventory = {o["header"]: o["developingRead"] for o in answer["inventory"]}
    assert inventory == {"RSI14_4h_dev": True, "RSI14_4h": False, "RSI14": False, "chg4h": True,
                         "quoteVol_4h_dev": True}
    for coin in answer["conditionOutcomes"]:
        by_key = {o["conditionKey"]: o for o in coin["outcomes"]}
        assert not any(o["hasDevelopingRead"] for o in coin["outcomes"])
        assert by_key["DEV_UP"]["developingAsOf"] and by_key["DEV_DOWN"]["developingAsOf"]
        assert by_key["CLOSED_HTF"]["developingAsOf"] is None and by_key["ANCHOR_ONLY"]["developingAsOf"] is None
        # narrower than the flag it replaced: a fixed-horizon change is provisional and read no bar in progress
        assert by_key["HORIZON"]["developingAsOf"] is None and by_key["HORIZON"]["provisional"] is True
    columns = {c["key"]: c for c in answer["columns"]}
    assert {k for k, c in columns.items() if "asOf" in c} == {"RSI14_4h_dev", "quoteVol_4h_dev"}
    assert columns["RSI14_4h_dev"]["bars"] == "Developing" and columns["RSI14_4h"]["bars"] == "Confirmed"


def test_omega_reads_no_condition_outcome():
    """v182 removed an OUTPUT field; nothing in omega/ reads an outcome, so nothing broke."""
    for path in sorted((ROOT / "omega").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "conditionOutcomes" not in text and "developingAsOf" not in text, path.name


# --- the nine main candles ---------------------------------------------------------------------------------------------
def test_the_rungs_at_the_nine_main_candles_are_recorded_and_omega_keeps_its_four():
    from omega.generate import REGIME_TF_FOR_ANCHOR
    from omega.types import ANCHOR_TIMEFRAMES
    anchors = P["TF"]["anchors"]
    assert list(anchors) == ["5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d"]
    assert {a: v["regime"] for a, v in anchors.items()} == {
        "5m": "15m", "15m": "1h", "30m": "2h", "1h": "4h", "2h": "8h", "4h": "12h", "8h": "1d", "12h": "1w", "1d": "1w"}
    assert {a: v["lower"] for a, v in anchors.items()} == {
        "5m": "1m", "15m": "5m", "30m": "15m", "1h": "30m", "2h": "1h", "4h": "2h", "8h": "4h", "12h": "8h", "1d": "12h"}
    shared = json.loads((ROOT / "data/contract/vocabulary/_shared.json").read_text(encoding="utf-8"))
    refs = {r["rel"]: r["resolvedByAnchor"] for r in shared["timeframeRefs"]}
    assert refs["lower"] == {a: v["lower"] for a, v in anchors.items()}       # the lower rung is served; measured equal
    assert set(refs["regime"].values()) == {None}                              # the regime rung is not: measured only
    assert shared["timeframes"] == list(anchors)
    assert set(get_args(ANCHOR_TIMEFRAMES)) == set(REGIME_TF_FOR_ANCHOR) == {"5m", "15m", "1h", "4h"} < set(anchors)
    assert REGIME_TF_FOR_ANCHOR == {a: anchors[a]["regime"] for a in REGIME_TF_FOR_ANCHOR}
    assert set(P["TF"]["refused"]) == {"1m", "3m", "3d", "1w"}
    assert {r["authoringCode"] for r in P["TF"]["refused"].values()} == {"REPORT_TIMEFRAME_NOT_AUTHORABLE"}


def test_the_headers_are_the_same_at_every_main_candle():
    columns = [Column.model_validate(c) for c in P["TF"]["columnsSent"]]
    predicted = [o.header for column in columns for o in outputs_for(column)]
    for anchor, answer in P["TF"]["anchors"].items():
        assert list(answer["headers"]) == predicted, anchor
        assert answer["headers"]["RSI14"] == answer["headers"]["atrPct"] == anchor
        assert answer["headers"]["close_htf_EMA20_spread"] == answer["regime"]


# --- the trade level preview: bounds, R:R, the level entry ------------------------------------------------------------
@pytest.mark.parametrize("coin", ["BTC", "ETH", "SOL"])
def test_the_stop_range_bounds_are_inclusive_and_judged_on_the_multiple(coin):
    from omega.trade_levels import STOP_RANGE_VERDICTS, outside_stop_range
    answer = L_LEVELS[("LG1", coin)]
    for side in ("LONG", "SHORT"):
        assert answer[side]["range"] == [0.8, 1.8]
        stops = answer[side]["stops"]
        assert [s["atrMultiple"] for s in stops] == [0.5, 0.79, 0.8, 1, 1.5, 1.8, 1.81, 2]
        for s in stops:
            verdict = outside_stop_range(s["atrMultiple"], 0.8, 1.8)
            assert s["verdict"] == (verdict or "SURVIVED"), (coin, side, s)
            assert s["responsibleBound"] == STOP_RANGE_VERDICTS.get(verdict)
            assert s["distanceAtrMultiple"] == s["atrMultiple"]
        assert answer[side]["counters"]["stopsRemovedByFloor"] == answer[side]["counters"]["stopsRemovedByCeiling"] == 2


def test_a_stop_at_the_bound_survives_where_its_percent_distance_rounds_outside_it():
    """SOL, 2026-11-20: the 0.8 stop's distance in percent is BELOW the floor's and the 1.8 stop's ABOVE the ceiling's,
    by floating-point rounding, and both survive - the stop is judged on its own multiple."""
    side = L_LEVELS[("LG1", "SOL")]["LONG"]
    stops = {s["atrMultiple"]: s for s in side["stops"]}
    assert stops[0.8]["distancePct"] < side["stopBand"]["requestedMinPct"] and stops[0.8]["verdict"] == "SURVIVED"
    assert stops[1.8]["distancePct"] > side["stopBand"]["requestedMaxPct"] and stops[1.8]["verdict"] == "SURVIVED"


def _menu_errors(stage: dict):
    from omega.trade_levels import validate_menu
    policy = stage["sent"]["TRADE_LEVEL_POLICY"]
    dials = {k: v for k, v in policy.items() if k != "tradeLevelMenu"}
    return [f for f in validate_menu(policy["tradeLevelMenu"], dials=dials, sections=[], anchor="1h",
                                     trailing_enabled=True) if f.severity == "error"]


@pytest.mark.parametrize("stage, pays", [("G2", "1.4996"), ("G3", "1.4995"), ("G4", "1.49949"), ("G5", "1.4996"),
                                         ("G6", "1.4994"), ("G7", "2.2496"), ("G8", "2.2494")])
def test_the_minimum_risk_reward_is_judged_at_three_decimals(stage, pays):
    from omega.trade_levels import plan_pays_exact, stated_rr
    sent = L_STAGES[stage]["sent"]["TRADE_LEVEL_POLICY"]
    plan = sent["tradeLevelMenu"]["LONG"]["exitPlans"][1]["targets"]
    assert plan_pays_exact(plan) == Fraction(pays)
    platform = [e for e in L_STAGES[stage]["answer"]["errors"]]
    ours = _menu_errors(L_STAGES[stage])
    below = stated_rr(Fraction(pays)) < Fraction(str(sent["minRiskRewardRatio"]))
    assert bool(platform) == bool(ours) == below, (stage, platform, ours)
    if platform:
        assert platform[0]["field"] == "tradeLevelMenu.LONG.exitPlans[1]" == ours[0].path
        assert f"pays {float(stated_rr(Fraction(pays))):g}R" in platform[0]["message"]
        assert f"pays {float(stated_rr(Fraction(pays))):g}R" in ours[0].message
        assert ours[0].code == "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"


def test_a_pair_just_under_the_minimum_survives_a_decision_stated_at_the_minimum():
    for key in ("LG2", "LG3"):
        for side in ("LONG", "SHORT"):
            answer = L_LEVELS[(key, "BTC")][side]
            assert answer["rejectedPairs"] == [] and answer["counters"]["pairsRemovedByRiskReward"] == 0
            assert {s["riskRewardRatio"] for s in answer["setups"]} == {1.5} and len(answer["setups"]) == 4
    assert E_STAGES["T2"]["answer"] == {"errors": [], "warnings": []}
    assert "pays 1.499R" in E_STAGES["T3"]["answer"]["errors"][0]["message"]
    assert E_STAGES["T4"]["answer"] == {"errors": [], "warnings": []}


def test_a_level_entry_states_its_distance_and_how_long_it_stays_valid():
    at_market = L_LEVELS[("LF0", "BTC")]
    assert at_market["LONG"]["entry"] is None and at_market["SHORT"]["entry"] is None
    for key, bars, long_order in (("LF1", 4, "TRIGGER"), ("LF3", 24, "TRIGGER")):
        entry = L_LEVELS[(key, "BTC")]["LONG"]["entry"]
        assert entry["outcome"] == "RESTS" and entry["orderType"] == long_order
        assert entry["validForMinutes"] == bars * 60          # validForBars x the 1h strategy bar
        assert entry["placedPrice"] == pytest.approx(entry["levelPrice"] + 0.2 * entry["atr"])
        assert entry["distanceAtr"] == pytest.approx(abs(entry["placedPrice"] - entry["mark"]) / entry["atr"])
        assert entry["distancePct"] == pytest.approx(100 * abs(entry["placedPrice"] - entry["mark"]) / entry["mark"],
                                                     rel=0.02)
    short = L_LEVELS[("LF2", "BTC")]["SHORT"]["entry"]
    assert (short["outcome"], short["orderType"], short["validForMinutes"]) == ("RESTS", "LIMIT", 360)
    wrong = L_LEVELS[("LF2", "BTC")]["LONG"]
    assert wrong["entry"]["outcome"] == "WRONG_SIDE" and wrong["stage"] == "ENTRY_LEVEL_UNAVAILABLE"
    assert (wrong["entry"]["placedSide"], wrong["entry"]["requiredSide"]) == ("above", "below")
    assert "distancePct" not in wrong["entry"] and "setups" not in wrong
    for side in ("LONG", "SHORT"):
        assert L_LEVELS[("LF4", "BTC")][side]["entry"]["outcome"] == "WRONG_SIDE"


# --- ENTRY_LEVEL_USUALLY_SKIPPED ------------------------------------------------------------------------------------
def _entry_warnings(stage: dict):
    from omega.trade_levels import entry_side_findings
    return sorted((f.path, f.message) for f in entry_side_findings(stage["sent"]["ENTRY"]["entry"]))


def test_the_warning_fires_on_a_level_with_a_side_by_definition_under_the_wrong_order():
    staged = [s for s in list(E_STAGES.values()) + list(L_STAGES.values())
              if isinstance((s["sent"].get("ENTRY") or {}).get("entry"), dict)
              and "levels" in s["sent"]["ENTRY"]["entry"]]
    assert len(staged) == 21
    warned = 0
    for stage in staged:
        platform = sorted((w["field"], w["message"]) for w in stage["answer"]["warnings"])
        assert {w["code"] for w in stage["answer"]["warnings"]} <= {"ENTRY_LEVEL_USUALLY_SKIPPED"}
        assert _entry_warnings(stage) == platform, stage["what"]
        warned += bool(platform)
    assert warned == 3                                    # E9, F4 (stop through the wrong side), F5 (retest of it)
    assert L_STAGES["F6"]["answer"]["warnings"] == [] and L_STAGES["F7"]["answer"]["warnings"] == []
    assert "sits below price by definition, but a buy stop must rest above price" in (
        L_STAGES["F4"]["answer"]["warnings"][0]["message"])
    assert "sits above price by definition, but a buy limit must rest below price" in (
        L_STAGES["F5"]["answer"]["warnings"][0]["message"])


def test_the_sides_by_definition_are_the_swept_ones():
    from omega.trade_levels import ENTRY_LEVEL_SIDES, entry_level_sides
    sweep = DRAFTS["S"]
    derived = json.loads((ROOT / ENTRY_LEVEL_SIDES).read_text(encoding="utf-8"))
    assert derived["below"] == sweep["below"] and derived["above"] == sweep["above"]
    assert sorted(derived["measured"]) == sorted(sweep["below"] + sweep["above"] + sweep["neither"])
    assert sweep["other"] == {} and sweep["measured"] == len(derived["measured"])
    c = load()
    legal = {name for name, m in c.metrics.items() if m.unit == "price"
             and not _errors(Column(metric=name, transformId="value", timeframe={"rel": "anchor"}))}
    assert set(derived["measured"]) | set(derived["unmeasured"]) == legal and len(legal) == 418
    sides = entry_level_sides()
    assert sides["DONCHIAN_LOWER"] == "below" and sides["DONCHIAN_UPPER"] == "above"
    # a name does not tell the side: a broken Donchian HIGH sits below price, the prior bar's band has none
    assert sides["DONCHIAN_BROKEN_HI"] == "below" and sides["DONCHIAN_BROKEN_LO"] == "above"
    assert "DONCHIAN_UPPER_PRIOR" not in sides and "BB_UPPER" not in sides and "PDH" not in sides


def test_validate_entry_levels_warns_only_on_the_form_the_sweep_staged():
    from omega.trade_levels import validate_entry_levels

    def level(metric, **kw):
        return {"metric": metric, "timeframe": {"rel": "anchor"}, "bars": None, "offset": 0, "knobs": {},
                "windowExtreme": None, **kw}
    sections = [{"kind": "custom", "title": "Levels", "benchmarkTicker": None, "marketScope": None, "notes": None,
                 "columns": [{"metric": m, "transformId": "value", "timeframe": {"rel": "anchor"}}
                             for m in ("DONCHIAN_LOWER", "DONCHIAN_UPPER")]}]

    def entry(trigger, long, short):
        return {"trigger": trigger, "levelOffsetAtrMultiple": 0.2, "validForBars": 4,
                "levels": {"LONG": long, "SHORT": short}}
    wrong = validate_entry_levels(entry("STOP_THROUGH_LEVEL", level("DONCHIAN_LOWER"), level("DONCHIAN_UPPER")),
                                  sections=sections, anchor="1h")
    assert [(f.severity, f.code, f.path) for f in wrong] == [
        ("warning", "ENTRY_LEVEL_USUALLY_SKIPPED", "entry.levels.LONG"),
        ("warning", "ENTRY_LEVEL_USUALLY_SKIPPED", "entry.levels.SHORT")]
    for trigger, long, short in (("STOP_THROUGH_LEVEL", "DONCHIAN_UPPER", "DONCHIAN_LOWER"),
                                 ("ON_RETEST", "DONCHIAN_LOWER", "DONCHIAN_UPPER"),
                                 ("EITHER_SIDE_OF_LEVEL", "DONCHIAN_LOWER", "DONCHIAN_UPPER")):
        assert validate_entry_levels(entry(trigger, level(long), level(short)), sections=sections, anchor="1h") == []
    # an unread level is an error and the other direction's warning stands beside it (omega's own reading: whether the
    # stage reports a warning beside an entry level error is not measured)
    unread = validate_entry_levels(entry("STOP_THROUGH_LEVEL", level("DONCHIAN_LOWER"), level("BB_UPPER")),
                                   sections=sections, anchor="1h")
    assert [(f.severity, f.path) for f in unread] == [("error", "entry.levels.SHORT"),
                                                      ("warning", "entry.levels.LONG")]
    # another form of the same metric was not swept and draws nothing
    back = validate_entry_levels(entry("STOP_THROUGH_LEVEL", level("DONCHIAN_LOWER", offset=1),
                                       level("DONCHIAN_UPPER", offset=1)), sections=sections, anchor="1h")
    assert not [f for f in back if f.code == "ENTRY_LEVEL_USUALLY_SKIPPED"]


# --- the drafts and the proof -------------------------------------------------------------------------------------------
def test_every_draft_was_discarded_and_read_back_null():
    for key in ("E", "L"):
        discard = DRAFTS[key]["discard"]
        assert discard["answer"]["discarded"] is True
        assert discard["readAfter"] == {"draft": None, "draftVersion": 0, "committedRevision": None}
        for when in ("listStrategyDraftsBefore", "listStrategyDraftsAfter"):
            [only] = DRAFTS[key][when]["drafts"]
            assert (only["strategyName"], only["version"], only["updatedAt"][:10]) == ("VWAP Reject 15m", 9, "2026-10-23")
    second = DRAFTS["S"]["secondRun"]["draft"]
    assert second["discard"]["discarded"] is True and second["readAfter"]["draft"] is None
    assert [d["strategyName"] for d in second["draftsAfter"]["drafts"]] == ["VWAP Reject 15m"]
    assert RECORD["proof"]["discard"]["readAfter"] == {"draft": None, "draftVersion": 0, "committedRevision": None}


def test_the_proof_body_is_what_omega_generates_and_it_staged_clean():
    from omega.generate import PRESETS, plan
    from omega.preflight import body_sha256
    proof = RECORD["proof"]
    axes = plan(PRESETS[proof["preset"]]).axes()
    assert axes == proof["sentAxes"] and body_sha256(axes) == proof["bodySha256Sent"]
    assert proof["stage"]["answer"] == {"errors": [], "warnings": []}
    assert sorted(proof["stage"]["stagedAxes"]) == sorted(axes)
    read = proof["readBack"]
    assert read["diagnostics"] == {"errors": [], "warnings": []} and read["committedRevision"] is None
    assert read["contentEqualsSentAsValues"] is True and read["axesThatDiffer"] == []
    assert proof["discard"]["answer"]["discarded"] is True
    [only] = proof["discard"]["listStrategyDraftsAfter"]["drafts"]
    assert only["strategyName"] == "VWAP Reject 15m" and only["version"] == 9
    assert proof["versionBefore"]["contractVersion"] == proof["versionAfter"]["contractVersion"] == "182.3.2"
    # the same body the 180.4.0 proof staged: the generator did not move
    old = json.loads((ROOT / "data/audit/reextraction_180_4_2026-11-19.json").read_text(encoding="utf-8"))
    assert old["proof"]["bodySha256Sent"] == proof["bodySha256Sent"]
