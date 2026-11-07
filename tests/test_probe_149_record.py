"""The 2026-11-07 authoring probe at contract 149.1.0 (scripts/probe_authoring_148.py, PROBE_CONTRACT 149.1.0), pinned.

data/audit/authoring_probe_149_2026-11-07.json is what preview_strategy_report rendered or refused, verbatim; these
tests hold the facts stage 2 of the v0.12 re-extraction builds the model from (headers, knob tokens, maxima, refusal
wording), so a later edit of the record or a re-run that disagrees is caught. Nothing here calls the platform.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data/audit/authoring_probe_149_2026-11-07.json").read_text(encoding="utf-8"))
HEADERS = json.loads((ROOT / "data/contract/columns/_probe_149_2026-11-07.json").read_text(encoding="utf-8"))
P = {e["probe"]: e for e in RECORD["probes"]}


def keys(name):
    return [c["key"] for s in P[name]["render"]["sections"] for c in s["columns"] if c["key"] != "coin"]


def refused(name):
    e = P[name]
    assert not e["accepted"], name
    return e["refusal"]


def test_the_run_is_complete_at_149_1_0():
    assert RECORD["contractVersion"] == "149.1.0" and RECORD["buildSha"].startswith("aa4ab640")
    assert RECORD["versionAtEnd"]["contractVersion"] == "149.1.0"
    assert RECORD["complete"] is True and RECORD["aborted"] is None
    assert RECORD["counts"] == {"probes": 225, "accepted": 104, "refused": 121, "transient": 2, "headersMinted": 254}
    assert len(HEADERS["headers"]) == 254


def test_a_preview_deadline_is_transient_and_its_columns_render_alone():
    transient = [e["probe"] for e in RECORD["probes"] if e.get("transient")]
    assert transient == ["F.PIVOT_CAM_R1.served", "J.rma.chainOuter"]
    for name in transient:
        assert refused(name)["code"] == "SERVICE_UNAVAILABLE"
        alone = [e for e in RECORD["probes"] if e["probe"].startswith(name + "#")]
        assert alone and all(e["accepted"] for e in alone)


@pytest.mark.parametrize("tid,default,maximum", [("ema", 20, 269), ("rma", 14, 118), ("wma", 20, 936),
                                                 ("rsi", 14, 118), ("cci", 20, 936)])
def test_each_smoother_renders_its_served_maximum_and_refuses_one_more(tid, default, maximum):
    accept = "A.accept" if tid == "ema" else f"J.{tid}.accept"
    rendered = [k for e in RECORD["probes"] if e["probe"].startswith(accept) and e["accepted"] for k in keys(e["probe"])]
    assert f"RSI14_{tid}{maximum}" in rendered
    assert f"RSI14_{tid}{default}" in rendered, "the default window is spelled in the header"
    over = refused("A.RSI14.ema.w270" if tid == "ema" else f"J.RSI14.{tid}.w{maximum + 1}")
    assert over["authoringCode"] == "REPORT_COLUMN_DEPTH_EXCEEDED"
    assert "at most 936 of the 1000 readable bars" in over["message"]


def test_cci_needs_a_window_of_two():
    assert refused("J.cci.accept#4")["message"] == "[column-grammar] transform 'cci' requires params.window >= 2 (got 1)"


@pytest.mark.parametrize("tid", ["rma", "wma", "rsi", "cci"])
def test_the_149_smoothers_chain_as_outers_of_distance_spread_relative_to(tid):
    names = [f"J.{tid}.chainOuter"] if P[f"J.{tid}.chainOuter"]["accepted"] else \
        [f"J.{tid}.chainOuter#{i}" for i in range(3)]
    rendered = [k for n in names for k in keys(n)]
    assert rendered == [f"dist_close_{tid}10", f"RSI14_RSI7_spread_{tid}10", f"close_BTC_rel_{tid}10"]


def test_the_smoothers_refuse_offset_inner_chains_and_unserved_metrics():
    assert refused("J.RSI14.rma.offset1")["message"] == "[column-grammar] transform 'rma' does not accept params.offset"
    assert refused("A.RSI14.ema.offset1")["message"] == "[column-grammar] transform 'ema' does not accept params.offset"
    for name in ("J.CLOSE.rma.chain.trajectory", "J.RSI14.zscore.chain.rma", "A.RSI14.zscore.chain.ema"):
        assert refused(name)["authoringCode"] == "REPORT_COLUMN_CHAIN_UNSUPPORTED"
    assert refused("J.PIVOT_WEEK_P.rsi")["authoringCode"] == "REPORT_COLUMN_PAIR_UNSUPPORTED"
    assert keys("J.RSI14.cci.abs4h") == ["RSI14_4h_cci20"], "the timeframe token precedes the smoother"


def test_knob_tokens_spell_the_whole_set_once_any_knob_is_off_default():
    assert [o["header"] for o in P["J.knobs.accept"]["render"]["outputs"]] == [
        "MACDline_fast8slow21sig5", "MACDline_fast8slow26sig9", "PPOline_fast12slow30sig9", "MACDhist_fast12slow26sig7",
        "K_p21s5d5", "stochRsiK_rsi21_p14s3d3", "bbUpper20_p30sd2.5", "pctB20_p20sd1.5", "kcUpper_p30atr14mult1.5",
        "stLine_atr14mult2", "PSAR_start0.01inc0.01max0.3", "CMF20_p30", "MFI14_p21", "willR14_p21"]
    assert keys("J.knobs.defaults") == ["MACDline", "bbUpper20", "PSAR", "stLine"], "explicit defaults mint no token"


def test_knob_header_order_with_transforms_timeframe_and_offset():
    assert keys("J.knobs.combos") == ["MACDline_fast8slow21sig9_o1", "MACDline_fast8slow26sig9_4h",
                                      "bbUpper20_p30sd2.5_ltf_o2", "kcUpper_p30atr14mult1.5_o1"]
    assert keys("J.knobs.transforms.accept") == [
        "MACDline_fast8slow26sig9_t3", "MACDline_fast8slow26sig9_t2", "MACDline_fast8slow26sig9_t1",
        "MACDline_fast8slow26sig9_now", "MACDline_fast8slow26sig9_trend", "MACDline_fast8slow26sig9_cross",
        "MACDline_fast8slow26sig9_MACDsig_spread", "MACDline_fast8slow26sig9_er", "dist_bbUpper20_p20sd2.5",
        "bbUpper20_p20sd2.5_lvl", "K_p21s1d3_zone", "dist_PSAR_start0.02inc0.02max0.3"]


def test_bar_count_knobs_are_depth_bound_and_range_knobs_step_bound():
    for name, header in (("J.MACD_LINE.fast.max", "MACDline_fast260slow26sig9"),
                         ("J.MACD_LINE.signal.max", "MACDline_fast12slow26sig243"),
                         ("J.STOCH_RSI_K.rsiPeriod.max", "stochRsiK_rsi116_p14s3d3"),
                         ("J.ST_LINE.atrPeriod.max", "stLine_atr118mult3"), ("J.BB_UPPER.stdDev.max", "bbUpper20_p20sd5"),
                         ("J.KC_UPPER.multiplier.max", "kcUpper_p20atr10mult10"),
                         ("J.PSAR.accelerationMaximum.max", "PSAR_start0.02inc0.02max1")):
        assert keys(name) == [header]
    for name in ("J.MACD_LINE.fast.over", "J.MACD_LINE.signal.over", "J.STOCH_RSI_K.rsiPeriod.over",
                 "J.ST_LINE.atrPeriod.over"):
        assert refused(name)["authoringCode"] == "REPORT_COLUMN_DEPTH_EXCEEDED", name
    assert refused("J.BB_UPPER.stdDev.over")["message"] == \
        "[column-grammar] metric 'BB_UPPER' requires params.stdDev from 0.1 to 5 in steps of 0.1 (got 5.1)"
    assert refused("J.BB_UPPER.stdDev.offstep")["message"].endswith("in steps of 0.1 (got 2.25)")
    assert refused("J.BB_UPPER.period.under")["message"] == \
        "[column-grammar] metric 'BB_UPPER' requires params.period >= 2 (got 1)"
    assert refused("J.BB_UPPER.period.nonInteger")["code"] == "VALIDATION_ERROR"
    assert refused("J.EQH.equalThreshold.negative")["message"] == \
        "[column-grammar] metric 'EQH' requires params.equalThreshold from 0 to 0.5 in steps of 0.1 (got -0.1)"


def test_no_ordering_rule_between_fast_and_slow():
    assert keys("J.MACD_LINE.fast.gt.slow") == ["MACDline_fast30slow10sig9"]
    assert keys("J.MACD_LINE.fast.eq.slow") == ["MACDline_fast26slow26sig9"]


def test_an_undeclared_knob_and_a_knob_under_a_history_transform_are_refused():
    for name, metric, knob in (("J.RSI14.period", "RSI14", "period"), ("J.CLOSE.stdDev", "CLOSE", "stdDev"),
                               ("J.MACD_LINE.period", "MACD_LINE", "period"), ("C.RSI14.leftBars", "RSI14", "leftBars")):
        assert refused(name)["message"] == f"[column-grammar] metric '{metric}' does not accept params.{knob}"
    for name in ("J.MACD_LINE.aggregate.fast8", "J.MACD_LINE.ema.fast8", "J.MACD_LINE.rma.fast8",
                 "J.BB_UPPER.zscore.stdDev", "J.BB_UPPER.distance.chain.rma.stdDev"):
        assert "its window reaches slots older than the history" in refused(name)["message"], name
    assert "cannot be read under 'relativeTo'" in refused("J.BB_UPPER.relativeTo.stdDev")["message"]


def test_the_148_widening_renders_as_the_hints_serve_it():
    assert keys("B.HIGH.rollingMax.w55.o1.chain.distance") == ["dist_high_o1_max55"]
    assert "at offset 0 cannot be chained into 'distance'" in refused("B.HIGH.rollingMax.w55.o0.chain.distance")["message"]
    assert keys("C.l3r5")[0] == "fractalHi_l3r5"
    assert keys("C.explicit2-2.and.single") == ["fractalHi", "fractalLo_l4r2", "fractalLabel_l2r3"]
    assert [keys(f"D.SWING_STRUCTURE_LEVEL.s{n}") for n in (10, 50, 100)] == \
        [["structLvl_s10"], ["structLvl"], ["structLvl_s100"]]
    assert keys("D.INTERNAL_STRUCTURE_TREND.confluenceFilter") == ["iStructTrend_cf"]
    assert refused("D.knobs.accept#0")["message"] == \
        "[column-grammar] metric 'SWING_STRUCTURE_TREND' does not accept params.confluenceFilter"
    assert keys("E.accept") == ["eqh", "eql", "eqh_e1", "eqh", "eqh_atr0", "eqh", "eql_atr0.5", "eql_e5_atr0.2"]
    assert keys("E.EQH.equalBars.max") == ["eqh_e935"]
    assert keys("F.week.value")[0] == "pivotWeekP"
    assert "timeframe-inert" in refused("F.PIVOT_WEEK_P.offset1")["message"]


def test_section_subjects_as_rendered():
    assert keys("G.USDT_USD.pair") == ["parDev", "parDev_zone", "open", "high", "low", "close"]
    assert keys("G.ETH.benchmark") == ["RSI14", "pivotWeekP", "close", "structTrend"]
    for name, subject in (("G.USDT_USD.RSI14", "reference"), ("G.ETH.PAR_DEV", "benchmark"),
                          ("G.coin.PAR_DEV", "evaluated-coin"), ("G.market.PAR_DEV", "market")):
        r = refused(name)
        assert r["authoringCode"] == "REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED"
        assert f"section's bars" in r["message"] and subject in r["message"], name
    assert refused("G.USDT_USD.plus.marketScope")["message"] == ("A section reads one subject: bind an instrument in "
                                                                 "`benchmarkTicker` or the market in `marketScope`, not both.")


def test_the_history_caps():
    assert keys("H.accept") == ["RSI14_mean64", "RSI14_mean65", "RSI14_mean936", "RSI14_z64", "RSI14_pctl63", "RSI14_er",
                                "RSI14_o63", "RSI14"]
    assert refused("H.RSI14.value.offset64")["authoringCode"] == "REPORT_COLUMN_LOOKBACK_EXCEEDED"
    assert refused("H.RSI14.aggregate.w937")["authoringCode"] == "REPORT_COLUMN_DEPTH_EXCEEDED"
