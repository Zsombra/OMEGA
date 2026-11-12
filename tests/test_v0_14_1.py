"""OMEGA v0.14.1 (2026-11-12): the last chain-window limits, measured at contract 171.0.0.

Measured live at contract 171.0.0 / build 588e449a on 2026-11-12, 14:10:40Z - 14:14:48Z (GET /mcp/version read before
and after): 22 previews and 3 CREATE stages, each stage read back, discarded and read null
(data/audit/authoring_limits_171_2026-11-12.json):

(a) The platform's own last accepted chain window is the joint depth bound v0.12.2 measured at 161.0.0 -
        need(inner, window) + need(outer, chainedWindow) - 1  <=  2436
    - unchanged at 171: every 161 boundary answered the same count and the same largest fit, on BTC and ETH, at every
    authorable main candle (5m, 15m, 1h, 4h; 1d is refused as a main candle before any depth is judged), and a stage
    carries the preview's refusal as a draft error. Its bottom, unsent until now: a chainedWindow below the outer's
    catalogued minimum (2 on zscore, stddev, linregSlope, cci, rollingMin, rollingMax) is refused
    "[column-grammar] transform 'zscore' requires params.chainedWindow >= 2 (got 1)". v0.14.0 passed all six (and the
    stage) with no finding; v0.14.1 refuses them (CHAINED_WINDOW_BELOW_MINIMUM).
(b) The chained touchAtr maximum was measured at 161.0.0 (tests/test_v0_12_2.py) and is not re-probed; the 171 corpus
    serves the same range.
(c) The operand-expanded spread pairs stay unrendered by standing decision.

Nothing here calls the platform.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest

from omega.authoring import CADENCE_FOR_ANCHOR
from omega.contract import load
from omega.fanout import outputs_for
from omega.types import ANCHOR_TIMEFRAMES, Column, CustomSection
from omega.validate import bars_needed, depth_budget, largest_window, validate_column, validate_section

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "audit" / "authoring_limits_171_2026-11-12.json"
AUDIT_161 = ROOT / "data" / "audit" / "authoring_limits_161_2026-11-11.json"
DEPTH, GRAMMAR, ANCHOR_REFUSED = ("REPORT_COLUMN_DEPTH_EXCEEDED", "REPORT_COLUMN_CONSTRUCTION_FAILED",
                                  "REPORT_TIMEFRAME_NOT_AUTHORABLE")
REFUSES = {DEPTH: "DEPTH_EXCEEDED", GRAMMAR: "CHAINED_WINDOW_BELOW_MINIMUM"}
MIN_TWO_OUTERS = ("zscore", "stddev", "linregSlope", "cci", "rollingMin", "rollingMax")
ANCHOR = {"rel": "anchor"}
# The room a plain value column serves beside its own one bar, measured at 161.0.0 (tests/test_v0_12_2.py: plain
# `close` 2499, plain `RSI14` 2485, each + 1).
PLAIN_ROOM = {"CLOSE": 2500, "RSI14": 2486}


@pytest.fixture(scope="module")
def contract():
    return load()


@pytest.fixture(scope="module")
def record():
    return json.loads(AUDIT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def probes(record):
    return record["probes"]


def _found(sections, contract):
    found, headers = [], []
    for s in sections:
        section = CustomSection(title="t", benchmarkTicker=s["benchmarkTicker"], marketScope=s["marketScope"],
                                columns=s["columns"])
        found += validate_section(section, contract=contract)
        headers += [o.header for col in section.columns for o in outputs_for(col, contract)]
    return found, headers


def _col(metric, inner, outer, **kw) -> Column:
    return Column(metric=metric, transformId=inner, chainedTransformId=outer, timeframe=ANCHOR, **kw)


# --- the record -------------------------------------------------------------------------------------------------------

def test_the_record_holds_every_call_and_every_stage_was_discarded(record, probes):
    assert (record["contractVersion"], record["buildSha"][:8]) == ("171.0.0", "588e449a")
    n = record["counts"]
    assert (n["previews"], n["accepted"], n["refused"]) == (22, 4, 18) == (
        len(probes), sum(p["accepted"] for p in probes), sum(not p["accepted"] for p in probes))
    assert n["refusedByCode"] == {DEPTH: 10, GRAMMAR: 6, ANCHOR_REFUSED: 2}
    assert {p["refusal"]["code"] for p in probes if not p["accepted"]} == {"VALIDATION_ERROR"}
    assert [p["tool"] for p in probes] == ["preview_strategy_report"] * 22
    times = [p["sentAt"] for p in probes] + [s["stagedAt"] for s in record["stages"]]
    assert times == sorted(times) and record["startedAt"] <= times[0] and times[-1] <= record["capturedAt"]
    # three CREATE stages, each read back as sent, discarded, and read null after: nothing was committed
    assert (n["stages"], n["discarded"], n["committed"]) == (3, 3, 0)
    for s in record["stages"]:
        assert s["sent"]["draftVersion"] == 0 and "strategyId" not in s["sent"], s["probe"]
        assert s["readBack"]["keptAsSent"] and s["discarded"] is True and s["draftAfterDiscard"] is None, s["probe"]
        assert set(s["answer"]["stagedAxes"]) == set(s["sent"]["axes"]) == {"IDENTITY", "TIMEFRAME_PROFILE", "REPORT"}


# --- every answer, replayed through omega -----------------------------------------------------------------------------

def test_omega_agrees_with_every_preview_of_the_limit_probe(contract, probes):
    """Every accepted preview validates with NO finding and renders exactly the headers omega.fanout predicts; every
    column refusal is refused by omega with the one finding that maps to the platform's code, on the field it names."""
    for p in probes:
        if p["refusal"] and p["refusal"]["authoringCode"] == ANCHOR_REFUSED:
            continue                                   # a main-candle refusal: no column was judged (next test)
        found, headers = _found(p["sections"], contract)
        if p["accepted"]:
            assert found == [], (p["probe"], found)
            assert headers == p["render"]["headers"], p["probe"]
            continue
        refusal = p["refusal"]
        assert [(f.severity, f.code) for f in found] == [("error", REFUSES[refusal["authoringCode"]])], (p["probe"], found)
        if refusal["authoringCode"] == DEPTH:
            assert found[0].path == f"section.columns[0].{refusal['path'][-1]}", p["probe"]
        else:
            assert found[0].path == "section.columns[0].chainedWindow", p["probe"]
            # omega states the platform's own sentence, less its "[column-grammar] " prefix
            assert refusal["message"].removeprefix("[column-grammar] ") in found[0].message, found[0].message


def test_omega_agrees_with_every_stage(contract, record, probes):
    """A stage judges the report column as the preview does: S1 (chainedWindow 2386) and S3 (zscore chainedWindow 1)
    stage as drafts carrying the preview's refusal - same message, same details - as their only error; S2 (2385 and
    zscore 2) stages with no error (NO_ENTRY_CONDITION is the empty strategy's warning, not the column's)."""
    by_probe = {p["probe"]: p for p in probes}
    same_as = {"S1.stage.agg2386": "A2.ema14.agg2386", "S3.stage.z1": "M.zscore.cw1"}
    for s in record["stages"]:
        errors = s["answer"]["diagnostics"]["errors"]
        found, _ = _found(s["sent"]["axes"]["REPORT"]["sections"], contract)
        if s["probe"] in same_as:
            preview = by_probe[same_as[s["probe"]]]["refusal"]
            (error,) = errors
            assert error["message"] == preview["message"]
            assert error["details"]["authoringCode"] == preview["authoringCode"]
            for key in ("path", "receivedValue", "allowedDomain"):
                assert error["details"][key] == preview[key], (s["probe"], key)
            assert [f.code for f in found] == [REFUSES[preview["authoringCode"]]], s["probe"]
        else:
            assert errors == [] and found == [], s["probe"]
            assert [w["code"] for w in s["answer"]["diagnostics"]["warnings"]] == ["NO_ENTRY_CONDITION"]


def test_a_main_candle_outside_the_four_is_refused_before_any_column(probes):
    """1d as the strategy timeframe is refused REPORT_TIMEFRAME_NOT_AUTHORABLE for the column that fits and the one that
    does not alike - the main-candle rule omega already holds (ANCHOR_TIMEFRAMES, measured 2026-08-28)."""
    refused = [p for p in probes if p["refusal"] and p["refusal"]["authoringCode"] == ANCHOR_REFUSED]
    assert [(p["probe"], p["timeframe"]) for p in refused] == [("T.1d.agg2385", "1d"), ("T.1d.agg2386", "1d")]
    for p in refused:
        assert p["refusal"]["allowedDomain"]["values"] == list(get_args(ANCHOR_TIMEFRAMES)) == ["5m", "15m", "1h", "4h"]
        assert p["timeframe"] not in get_args(ANCHOR_TIMEFRAMES) and p["timeframe"] not in CADENCE_FOR_ANCHOR


# --- (a) the top: the joint bound, unchanged at 171 -------------------------------------------------------------------

def test_the_bar_count_and_the_largest_fit_are_the_platforms_on_every_depth_refusal(contract, probes):
    refused = [p for p in probes if p["refusal"] and p["refusal"]["authoringCode"] == DEPTH]
    assert len(refused) == 10
    for p in refused:
        (col,) = p["sections"][0]["columns"]
        refusal = p["refusal"]
        budget = depth_budget(contract.metric(col["metric"]))
        assert budget == refusal["context"]["depth"] - refusal["context"]["cap"] == 2436, p["probe"]
        need_in = bars_needed(col["transformId"], col["window"])
        need_out = bars_needed(col["chainedTransformId"], col["chainedWindow"])
        assert need_in + need_out - 1 == refusal["receivedValue"]["need"], p["probe"]
        assert refusal["path"][-1] == "chainedWindow", p["probe"]
        assert largest_window(col["chainedTransformId"], budget + 1 - need_in) == refusal["allowedDomain"]["maximum"]
        # the bottom of the range the platform states is the outer's catalogued minimum (2 on zscore, else 1)
        minimum = contract.transforms[col["chainedTransformId"]]["parameters"]["window"]["minimum"]
        assert refusal["allowedDomain"]["minimum"] == minimum, p["probe"]


def test_every_161_boundary_answers_the_same_at_171(probes):
    """Each column of the 161 run that was sent again (same column, same main candle) got the same verdict, and a
    refused one the same count and the same largest fit; a rendered one the same hold room."""
    old = {}
    for p in json.loads(AUDIT_161.read_text(encoding="utf-8"))["probes"]:
        for i, c in enumerate(p["sections"][0]["columns"]):
            room = (p["render"] or {}).get("conditionHoldMaxWindow", {})
            header = p["render"]["headers"][i] if p["accepted"] else None
            old[(json.dumps(c, sort_keys=True), p["timeframe"])] = (p["accepted"], p["refusal"], room.get(header))
    matched = []
    for p in probes:
        for i, c in enumerate(p["sections"][0]["columns"]):
            then = old.get((json.dumps(c, sort_keys=True), p["timeframe"]))
            if then is None:
                continue
            accepted, refusal, room = then
            assert accepted == p["accepted"], p["probe"]
            if accepted:
                header = p["render"]["headers"][i]
                assert room == p["render"]["conditionHoldMaxWindow"][header], (p["probe"], header)
            else:
                for key in ("message", "receivedValue", "allowedDomain", "context"):
                    assert refusal[key] == p["refusal"][key], (p["probe"], key)
            matched.append(p["probe"])
    assert sorted(set(matched)) == sorted({"A1.last_accepted_batch", "A2.ema14.agg2386", "A3.ema697.agg2364",
                                           "A4.ema698.agg24", "A5.close.agg10.z2428", "A6.rma10.roc2361",
                                           "A7.close.agg10.ema702", "C.eth.agg2386"})
    assert matched.count("A1.last_accepted_batch") == 5


def test_the_bound_is_bars_at_every_authorable_main_candle_and_on_eth(contract, probes):
    """RSI14 x ema 14 -> aggregate: 2385 renders and 2386 is refused (2437 bars, largest 2385) at 5m, 15m, 1h and 4h,
    and on ETH - the budget counts bars of the column's timeframe, whatever that timeframe is."""
    seen = {}
    for p in probes:
        (col, *rest) = p["sections"][0]["columns"]
        if (col["metric"], col["transformId"], col["window"], col.get("chainedTransformId")) != (
                "RSI14", "ema", 14, "aggregate") or col["chainedWindow"] not in (2385, 2386):
            continue
        if p["refusal"] and p["refusal"]["authoringCode"] == ANCHOR_REFUSED:
            continue
        seen[(p["timeframe"], col["chainedWindow"], tuple(p["tickers"]))] = (
            p["accepted"], p["render"]["conditionHoldMaxWindow"]["RSI14_ema14_mean2385"] if p["accepted"] else
            (p["refusal"]["receivedValue"]["need"], p["refusal"]["allowedDomain"]["maximum"]))
    assert seen == {
        ("1h", 2385, ("BTC", "ETH")): (True, 50), ("1h", 2386, ("BTC",)): (False, (2437, 2385)),
        ("1h", 2386, ("ETH",)): (False, (2437, 2385)),
        ("4h", 2385, ("BTC",)): (True, 50), ("4h", 2386, ("BTC",)): (False, (2437, 2385)),
        ("15m", 2385, ("BTC",)): (True, 50), ("15m", 2386, ("BTC",)): (False, (2437, 2385)),
        ("5m", 2385, ("BTC",)): (True, 50), ("5m", 2386, ("BTC",)): (False, (2437, 2385))}
    assert set(get_args(ANCHOR_TIMEFRAMES)) == {tf for tf, _, _ in seen}


def test_the_hold_room_of_every_rendered_column_is_the_depth_less_its_bars(contract, probes):
    """conditionHold.maxWindow on every rendered chain is the plain column's room less the bars need() counts - the
    count read where the platform RENDERED, at both ends of the chain window (2385 / 2427 / 2360 / 701 and 2)."""
    checked = 0
    for p in probes:
        if not p["accepted"]:
            continue
        for col, header in zip(p["sections"][0]["columns"], p["render"]["headers"], strict=True):
            bars = bars_needed(col["transformId"], col["window"]) + bars_needed(col["chainedTransformId"],
                                                                                 col["chainedWindow"]) - 1
            assert p["render"]["conditionHoldMaxWindow"][header] == PLAIN_ROOM[col["metric"]] - bars, (p["probe"],
                                                                                                      header)
            checked += 1
    assert checked == 14


def test_the_deep_columns_carried_values_at_171(probes):
    """At 161 every chain value came back null (the cause was not established). At 171 every rendered cell holds a
    number, on BTC and ETH, at the deepest windows the bound admits."""
    for p in probes:
        if p["accepted"]:
            for row in p["render"]["rows"]:
                assert all(isinstance(v, (int, float)) for v in row[1:]), (p["probe"], row)


# --- (a) the bottom: the outer's catalogued minimum -------------------------------------------------------------------

@pytest.mark.parametrize("outer", MIN_TWO_OUTERS)
def test_a_chained_window_below_the_outers_minimum_is_refused(outer, contract):
    assert contract.transforms[outer]["parameters"]["window"]["minimum"] == 2
    one = validate_column(_col("RSI14", "ema", outer, window=14, chainedWindow=1), contract=contract)
    assert [(f.severity, f.code, f.path) for f in one] == [("error", "CHAINED_WINDOW_BELOW_MINIMUM", "column.chainedWindow")]
    assert f"transform {outer!r} requires params.chainedWindow >= 2 (got 1)" in one[0].message
    assert validate_column(_col("RSI14", "ema", outer, window=14, chainedWindow=2), contract=contract) == []


def test_every_rolling_chain_of_the_corpus_is_judged_at_its_outers_minimum(contract):
    """Over every served rolling-inner chain cell (windowParameter chainedWindow) of RSI14 and CLOSE: one below the
    outer's catalogued minimum is refused with exactly this finding, the minimum itself with none (the default inner
    window, so the depth bound is far away)."""
    checked = 0
    for metric in ("RSI14", "CLOSE"):
        m = contract.metric(metric)
        for inner, t in m.transforms.items():
            for outer, cell in (t.get("chainedOuters") or {}).items():
                if cell.get("windowParameter") != "chainedWindow":
                    continue
                minimum = contract.transforms[outer]["parameters"]["window"]["minimum"]
                at = validate_column(_col(metric, inner, outer, chainedWindow=minimum), contract=contract)
                assert at == [], (metric, inner, outer, at)
                if minimum > 1:
                    below = validate_column(_col(metric, inner, outer, chainedWindow=minimum - 1), contract=contract)
                    assert [f.code for f in below] == ["CHAINED_WINDOW_BELOW_MINIMUM"], (metric, inner, outer)
                checked += 1
    assert checked > 50


def test_an_omitted_chained_window_is_the_outers_default_and_never_below_its_minimum(contract):
    for outer in MIN_TWO_OUTERS:
        assert validate_column(_col("RSI14", "ema", outer, window=14), contract=contract) == []


def test_a_chained_window_on_a_chain_that_refuses_it_is_one_finding_not_two(contract):
    """distance -> zscore reads its outer window from `window`: a chainedWindow there is refused for that reason
    alone (CHAINED_WINDOW_REFUSED, measured 2026-11-09), never also as below a minimum."""
    found = validate_column(_col("CLOSE", "distance", "zscore", chainedWindow=1), contract=contract)
    codes = [f.code for f in found]
    assert "CHAINED_WINDOW_BELOW_MINIMUM" not in codes and "CHAINED_WINDOW_REFUSED" in codes, codes


# --- (b) touchAtr: measured at 161, not re-probed ---------------------------------------------------------------------

def test_the_chained_touch_atr_range_is_served_unchanged_at_171(contract, record):
    """v0.12.2 measured it (0.1 to 2 in steps of 0.1 on a chained levelInteraction, 2.1 refused) and tests/
    test_v0_12_2.py replays that run; the 171.0.0 corpus serves the same range, so it was not re-probed."""
    served = contract.chain_outer_parameters["levelInteraction"]["touchAtr"]
    assert (served["minimum"], served["maximum"], served["step"]) == (0.1, 2, 0.1)
    assert "touchAtrOnAChainedLevelInteraction" in record["notTouched"]
    assert "spreadOperandPairs" in record["notTouched"]
