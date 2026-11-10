"""OMEGA v0.12 (in progress): the model step at contract 149.1.0, 2026-11-07.

The refreshed corpus (hints read 2026-11-06, _moves_149.json) plus the model changes - the nineteen knobs on
omega.types.Column, their header spelling (omega.fanout.knob_token), the five smoothers, `offset` on the rolling extremes
and `distance` after them, four section subjects - judged against every answer the platform gave at 149.1.0: the
authoring probe (225 previews), the knob-spelling probe and the coverage sweeps. Nothing here calls the platform.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from omega.contract import CONTRACT_DIR, REFERENCE_PAIRS, load, section_subject
from omega.fanout import knob_token, outputs_for
from omega.types import Column, CustomSection
from omega.validate import validate_column, validate_section

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "audit"


def _j(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


PROBE = _j(AUDIT / "authoring_probe_149_2026-11-07.json")
KNOBS = _j(AUDIT / "knob_spelling_probe_149_2026-11-07.json")
MOVES = _j(CONTRACT_DIR / "metrics" / "_moves_149.json")


@pytest.fixture(scope="module")
def contract():
    return load()


def _section(sent: dict) -> CustomSection:
    return CustomSection(title="t", benchmarkTicker=sent.get("benchmarkTicker"), marketScope=sent.get("marketScope"),
                         columns=sent["columns"])


# --- headers ----------------------------------------------------------------------------------------------------------
def test_every_rendered_probe_section_is_predicted_header_for_header(contract):
    """104 sections rendered at 149.1.0; omega predicts each one's headers exactly, in order (the smoothers, the knob
    sets and singles, high_o1_max55 / dist_high_o1_max55, the pivots, parDev on a pair section)."""
    sections = 0
    for p in PROBE["probes"]:
        if not p["accepted"]:
            continue
        for sent, rend in zip(p["sections"], p["render"]["sections"]):
            got = [x["key"] for x in rend["columns"] if x.get("role") != "identity"]
            pred = [o.header for col in sent["columns"] for o in outputs_for(Column(**col), contract)]
            assert pred == got, p["probe"]
            sections += 1
    assert sections == 104


def test_the_knob_spellings_the_probe_had_not_rendered(contract):
    """Thirteen predictions sent in one preview at 17:31Z (scripts/probe_knob_spelling_149.py): all as predicted."""
    assert KNOBS["contractVersion"] == KNOBS["versionAtEnd"] == "149.1.0" and KNOBS["refused"] == 0 and KNOBS["agree"]
    [entry] = KNOBS["entries"]
    assert entry["rendered"] == entry["predicted"] == [o.header for col in entry["columns"]
                                                        for o in outputs_for(Column(**col), contract)]
    assert {"iStructLvl_s20_cf", "iStructTrend_s20_cf_ltf", "stochRsiK_rsi14_p21s3d3", "D_p21s1d3",
            "eql_e5_dev"} <= set(entry["rendered"])


@pytest.mark.parametrize("col,header", [
    ({"metric": "MACD_LINE", "fast": 8}, "MACDline_fast8slow26sig9"),          # a set: spelled whole once one is off
    ({"metric": "MACD_LINE", "fast": 12, "slow": 26, "signal": 9}, "MACDline"),  # explicit defaults spell nothing
    ({"metric": "STOCH_RSI_K", "rsiPeriod": 21}, "stochRsiK_rsi21_p14s3d3"),    # rsiPeriod: its own token, first
    ({"metric": "EQH", "equalThreshold": 0}, "eqh_atr0"),                       # singles: each only when off default
    ({"metric": "INTERNAL_STRUCTURE_LEVEL", "confluenceFilter": True}, "iStructLvl_cf"),   # a flag spells no value
    ({"metric": "BB_UPPER", "stdDev": 5}, "bbUpper20_p20sd5"),                  # an integral number loses its point
    ({"metric": "PSAR", "accelerationMaximum": 0.3}, "PSAR_start0.02inc0.02max0.3"),
])
def test_knob_token_spelling(col, header, contract):
    column = Column(transformId="value", timeframe={"rel": "anchor"}, **col)
    assert [o.header for o in outputs_for(column, contract)] == [header]


def test_a_knob_the_metric_does_not_serve_is_not_spelled(contract):
    column = Column(metric="RSI14", transformId="value", timeframe={"rel": "anchor"}, period=21)
    assert knob_token(column, contract) == ""


def test_a_non_integer_bar_count_is_refused_by_the_model():
    """J.BB_UPPER.period.nonInteger: "Invalid input: expected int, received number" (schema VALIDATION_ERROR)."""
    with pytest.raises(ValidationError):
        Column(metric="BB_UPPER", transformId="value", timeframe={"rel": "anchor"}, period=30.5)


# --- refusals ---------------------------------------------------------------------------------------------------------
def _verdict(p: dict, contract) -> list[str]:
    errors = []
    for sent in p["sections"]:
        try:
            section = _section(sent)
        except ValidationError:
            errors.append("SCHEMA")
            continue
        errors += [f.code for f in validate_section(section, contract=contract) if f.severity == "error"]
    return errors


def _moved_at_161(p: dict) -> str | None:
    """161.0.0 (2026-11-09): the two platform moves that changed an answer the 149.1.0 probe recorded. `pair`: CLOSE no
    longer serves `distance` (README undocumented, _moves_161.json transformsLostByExistingMetrics), so a CLOSE x distance
    column is refused PAIR_UNSUPPORTED now. `depth`: the readable depth went 1000 -> 2500 bars, so a window refused at 149.1.0
    "of the 1000 readable bars" fits now (the served maxima: ema 269 -> 704, aggregate 936 -> 2436 ...)."""
    if any(c.get("metric") == "CLOSE" and c.get("transformId") == "distance" for s in p["sections"] for c in s["columns"]):
        return "pair"
    if "of the 1000 readable bars" in ((p.get("refusal") or {}).get("message") or ""):
        return "depth"
    return None


def test_omega_agrees_with_every_probe_answer(contract):
    """Every non-transient probe: refused by the platform <=> refused by omega. The five accepted sections omega
    refuses are the ones the probe built with a duplicate header on purpose: the platform renders them and flags
    `duplicateHeaders` (the section then leaves conditionColumns), which is exactly omega's DUPLICATE_HEADER."""
    agree = duplicates = 0
    moved = {"pair": [], "depth": []}
    for p in PROBE["probes"]:
        if (p.get("refusal") or {}).get("code") == "SERVICE_UNAVAILABLE":
            continue
        errors = _verdict(p, contract)
        if _moved_at_161(p):
            # the 149.1.0 answer is history: omega at 161.0.0 follows the platform's later move instead
            moved[_moved_at_161(p)].append(p["probe"])
            if _moved_at_161(p) == "pair":
                assert "REPORT_COLUMN_PAIR_UNSUPPORTED" in errors, p["probe"]
            else:
                assert not {"DEPTH_EXCEEDED", "PARAMETER_OUT_OF_RANGE"} & set(errors), (p["probe"], errors)
            continue
        if p["accepted"]:
            if errors:
                assert set(errors) == {"DUPLICATE_HEADER"} and p["render"]["duplicateHeaders"], p["probe"]
                duplicates += 1
        else:
            # Refused for the platform's reason, not just refused (review 2026-11-08: `assert errors` passed on any code)
            refusal = p["refusal"]
            allowed = REFUSAL_CLASSES[refusal.get("authoringCode")]
            assert set(errors) & allowed, (p["probe"], refusal.get("authoringCode"), errors)
        agree += 1
    # 161.0.0 (2026-11-09): (201, 5) agree on the 149.1.0 answers that still hold; 22 moved (223 - 22): six touch
    # CLOSE x distance (the four J.<smoother>.chainOuter sections accepted at 149 and the two J.CLOSE.distance.chain
    # depth refusals) and sixteen were depth refusals at the 1000-bar depth (the served maxima moved with the 2500-bar depth)
    assert (len(moved["pair"]), len(moved["depth"])) == (6, 16)
    assert (agree, duplicates) == (201, 5)


# The platform's refusal class (authoringCode; None = a schema-level VALIDATION_ERROR) -> the omega codes that state it.
# Not one to one: depth is the transform window's (DEPTH_EXCEEDED) or a knob's (PARAMETER_OUT_OF_RANGE), and
# construction covers every grammar refusal. Cross-tabbed over the 121 refusals at 149.1.0 on 2026-11-08.
REFUSAL_CLASSES = {
    "REPORT_COLUMN_DEPTH_EXCEEDED": {"DEPTH_EXCEEDED", "PARAMETER_OUT_OF_RANGE"},
    "REPORT_COLUMN_CONSTRUCTION_FAILED": {"OFFSET_REFUSED", "OFFSET_BELOW_MINIMUM", "PARAMETER_UNDECLARED",
                                          "PARAMETER_NOT_ACCEPTED", "PARAMETER_OUT_OF_RANGE", "WINDOW_BELOW_MINIMUM",
                                          "TIMELESS_OFFSET_REFUSED", "REPORT_COLUMN_CONSTRUCTION_FAILED"},
    "REPORT_COLUMN_CHAIN_UNSUPPORTED": {"REPORT_COLUMN_CHAIN_UNSUPPORTED"},
    "REPORT_COLUMN_PAIR_UNSUPPORTED": {"REPORT_COLUMN_PAIR_UNSUPPORTED"},
    "REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED": {"SECTION_SUBJECT_METRIC_UNSUPPORTED"},
    "REPORT_COLUMN_INSTRUMENT_UNKNOWN": {"REFERENCE_INSTRUMENT_REQUIRED"},
    "REPORT_COLUMN_LOOKBACK_EXCEEDED": {"LOOKBACK_EXCEEDED"},
    None: {"SCHEMA", "SECTION_SUBJECT_CONFLICT"},
}


@pytest.mark.parametrize("probe,code", [
    ("A.RSI14.ema.offset1", "OFFSET_REFUSED"),
    ("B.HIGH.rollingMax.w55.o0.chain.distance", "OFFSET_BELOW_MINIMUM"),
    ("C.RSI14.leftBars", "PARAMETER_UNDECLARED"),
    ("C.SWING_FRACTAL_HIGH.aggregate.l3r5", "PARAMETER_NOT_ACCEPTED"),
    ("C.SWING_FRACTAL_HIGH.relativeTo.l3r5", "PARAMETER_NOT_ACCEPTED"),
    ("C.SWING_FRACTAL_HIGH.distance.chain.rank.l3r5", "PARAMETER_NOT_ACCEPTED"),
    ("D.SWING_STRUCTURE_LEVEL.s101", "PARAMETER_OUT_OF_RANGE"),
    ("E.EQH.equalThreshold.offstep", "PARAMETER_OUT_OF_RANGE"),
    ("J.cci.accept", "WINDOW_BELOW_MINIMUM"),
    ("J.BB_UPPER.zscore.stdDev", "PARAMETER_NOT_ACCEPTED"),
    ("G.USDT_USD.RSI14", "SECTION_SUBJECT_METRIC_UNSUPPORTED"),
    ("G.ETH.PAR_DEV", "SECTION_SUBJECT_METRIC_UNSUPPORTED"),
    ("G.coin.PAR_DEV", "SECTION_SUBJECT_METRIC_UNSUPPORTED"),
    ("G.USDT_USD.plus.marketScope", "SECTION_SUBJECT_CONFLICT"),
    ("G.USDT_USD.PAR_DEV.served", "REFERENCE_INSTRUMENT_REQUIRED"),
])
def test_each_refusal_class_maps_to_its_omega_code(probe, code, contract):
    [p] = [x for x in PROBE["probes"] if x["probe"] == probe]
    assert not p["accepted"]
    assert code in _verdict(p, contract)


# 161.0.0 (2026-11-09): the three depth refusals of this table at 149.1.0 (A.RSI14.ema.w270, C.SWING_FRACTAL_HIGH.both.max,
# J.MACD_LINE.fast.over) were judged at the 1000-bar depth. The platform's depth is 2500 now, so the same three classes
# are pinned at the SERVED maximum read from the corpus (maximum + 1 refused, the maximum accepted); the 161.0.0 probe's
# own depth refusals (O.* / K.RSI14.roc.over) are in tests/test_v161.py.
def test_the_depth_refusals_follow_the_served_maxima(contract):
    def errors(**kw):
        col = Column(timeframe={"rel": "anchor"}, **kw)
        return [f.code for f in validate_column(col, contract=contract) if f.severity == "error"]
    window = contract.metric("RSI14").transforms["ema"]["maximums"]["window"]
    assert errors(metric="RSI14", transformId="ema", window=window) == []
    assert errors(metric="RSI14", transformId="ema", window=window + 1) == ["DEPTH_EXCEEDED"]
    fast = contract.metric("MACD_LINE").parameters["fast"]["maximum"]
    assert errors(metric="MACD_LINE", transformId="value", fast=fast) == []
    assert errors(metric="MACD_LINE", transformId="value", fast=fast + 1) == ["PARAMETER_OUT_OF_RANGE"]
    # the swing pair's L + R + 1 <= readable depth less the lookback budget rule (2436): 1217 / 1217 fits, 1218 / 1218 reads 2437
    assert errors(metric="SWING_FRACTAL_HIGH", transformId="value", leftBars=1217, rightBars=1217) == []
    assert errors(metric="SWING_FRACTAL_HIGH", transformId="value", leftBars=1218, rightBars=1218) == ["PARAMETER_OUT_OF_RANGE"]


def test_two_depth_bound_knobs_off_together_are_warned_not_judged(contract):
    """Each served maximum holds with the metric's other knobs at their defaults; the joint depth of two is unmeasured
    (the swing pair's L + R + 1 rule excepted - it was measured, C.SWING_FRACTAL_HIGH.both.max)."""
    col = Column(metric="MACD_LINE", transformId="value", timeframe={"rel": "anchor"}, fast=200, signal=200)
    findings = validate_column(col, contract=contract)
    assert [f.code for f in findings if f.severity == "error"] == []
    assert "PARAMETER_DEPTH_UNVERIFIED" in [f.code for f in findings if f.severity == "warning"]


# --- subjects ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("ticker,scope,subject", [
    (None, None, "evaluated-coin"), (None, "crypto", "market"), ("ETH", None, "benchmark"),
    ("USDT_USD", None, "reference"), ("usdc_usdt", None, "reference")])
def test_the_four_section_subjects(ticker, scope, subject):
    assert section_subject(ticker, scope) == subject
    assert REFERENCE_PAIRS == ("USDT_USD", "USDC_USDT")


def test_par_dev_relative_to_needs_the_other_pair(contract):
    """G.USDT_USD.PAR_DEV.served: "relativeTo on a section bound to 'USDT_USD' requires an instrument - another
    declared reference pair"; with USDC_USDT it rendered parDev_USDC_USDT_rel (2026-11-07-reference sweep)."""
    def section(instrument):
        col = {"metric": "PAR_DEV", "transformId": "relativeTo", "timeframe": {"rel": "anchor"}}
        if instrument:
            col["instrument"] = instrument
        return CustomSection(title="t", benchmarkTicker="USDT_USD", marketScope=None, columns=[col])
    for bad in (None, "BTC", "USDT_USD"):
        assert [f.code for f in validate_section(section(bad), contract=contract) if f.severity == "error"] == [
            "REFERENCE_INSTRUMENT_REQUIRED"], bad
    ok = section("USDC_USDT")
    assert [f.code for f in validate_section(ok, contract=contract) if f.severity == "error"] == []
    assert [o.header for o in outputs_for(ok.columns[0], contract)] == ["parDev_USDC_USDT_rel"]


# --- the sweeps and the record ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("date,shapes,headers,scope,ticker", [
    ("2026-11-07-smoothers", 2074, 2074, None, None),
    ("2026-11-07-smoothers-market", 65, 65, "crypto", None),
    ("2026-11-07-reference", 15, 19, None, "USDT_USD")])
def test_the_model_step_sweeps(date, shapes, headers, scope, ticker):
    r = _j(AUDIT / f"coverage_sweep_{date}.json")
    assert r["complete"] and r["aborted"] is None and r["scope"] == "structural"
    assert (r["marketScope"], r["benchmarkTicker"]) == (scope, ticker)
    assert (r["shapesRequested"], r["headersMinted"]) == (shapes, headers)
    assert r["refusalCount"] == 0 and r["predictedButNotRenderedCount"] == 0


def test_the_moves_record(contract):
    assert MOVES["contractVersion"] == "149.1.0" and MOVES["retired"] == {} and len(MOVES["added"]) == 206
    # 161.0.0 (2026-11-09): the corpus holds the 149.1.0 additions plus _moves_161.json's three, less BB_TOUCH
    assert {k: len(v) for k, v in MOVES["addedByReadmeEntry"].items()} == {
        "v146.10": 82, "v146.11": 8, "v146.5": 34, "v146.8": 82}
    assert {k: len(v) for k, v in MOVES["transformsGainedByExistingMetrics"].items()} == {
        t: 165 for t in ("cci", "ema", "rma", "rsi", "wma")}
    assert MOVES["transformsLostByExistingMetrics"] == {}
    assert len(MOVES["parametersServed"]) == 36
    assert MOVES["subjectKindsCounts"] == {"evaluated-coin + benchmark": 489, "evaluated-coin": 25, "market": 13,
                                           "evaluated-coin + benchmark + reference": 4, "reference": 1}
    assert set(MOVES["added"]) <= set(contract.metrics) and len(contract.metrics) == 534   # 532 at 149.1.0
    for key, knobs in MOVES["parametersServed"].items():
        assert list(contract.metric(key).parameters) == knobs, key


def test_the_vocabulary_read_at_149_1_0(contract):
    shared = _j(CONTRACT_DIR / "vocabulary" / "_shared.json")
    # 161.0.0 (2026-11-09): _shared.json was re-read at 161.0.0 (2026-11-09T16:22Z, `roc` added: 29 transforms); the 149.1.0
    # read is its `previous` and its own snapshot (20261107T1736Z) keeps the 28 as read
    assert shared["_refreshed"]["contractVersion"] == "161.0.0" and shared["_refreshed"]["at"] == "2026-11-09T16:22Z"
    prev = shared["_refreshed"]["previous"]
    assert prev["contractVersion"] == "149.1.0" and prev["at"] == "2026-11-07T17:36Z"
    assert len(shared["transforms"]) == 29 and contract.budgets["conditionFrameReads"] == 5048
    snap = CONTRACT_DIR / "vocabulary" / "20261107T1736Z"
    assert len(list(snap.glob("*.json"))) == 12
    assert len(_j(snap / "derived.json")["transforms"]) == 28
    assert _j(snap / "structure.json")["code"] == "RESULT_TOO_LARGE"
