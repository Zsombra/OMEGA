"""OMEGA v0.13.1: what contract 168 served and v0.13.0 left unmeasured, measured at 169.4.0 (build c9703bf9) on
2026-11-12 and modelled.

  `spread` as a chain outer after aggregate / ema / rma / wma        omega.validate._chained_spread_operand, omega.fanout
  a spread operand under an average, inputs[] {metric, transformId, window}   omega.types.Operand, omega.validate._averaged_operand
  the condition group op SEQUENCE (`within`), and the frame-read budget        omega.conditions.sequence / _walk_sequence /
                                                                                frame_reads

Every rule is pinned here to the records it was read from: each preview probe is replayed through omega and must get
the platform's verdict, its header and, where the refusal states one, its frame-read count. Read-only probes, no draft:
data/audit/authoring_probe_169_2026-11-12.json (groups V, W) and -c.json (group J); data/audit/sequence_probe_169_
2026-11-12.json and -b .. -g.json (seven rounds); the structural sweep of the 660 chained-spread shapes,
data/audit/coverage_sweep_2026-11-12.json and -market.json. The corpus did not move: 581 hints re-read at 169.4.0, each
identical to 168.3.0's.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from omega import conditions as K
from omega.contract import load, stage_schema
from omega.fanout import outputs_for
from omega.generate import PRESETS, plan
from omega.space import enumerate_shapes
from omega.trade_levels import report_readings
from omega.types import Column, Operand
from omega.validate import validate_column

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data/audit"
MANIFEST = json.loads((ROOT / "data/contract/_manifest.json").read_text(encoding="utf-8"))
BUILD = "c9703bf90d9afc15dae83bc46513d3b49587c8bf"
ANCHOR = {"rel": "anchor"}
AUTHORING = [AUDIT / "authoring_probe_169_2026-11-12.json", AUDIT / "authoring_probe_169_2026-11-12-c.json"]
SEQUENCES = sorted(AUDIT.glob("sequence_probe_169_2026-11-12*.json"))


def _j(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _errors(column: Column) -> list[str]:
    return [f.code for f in validate_column(column) if f.severity == "error"]


def _col(metric, tid, **kw) -> Column:
    return Column(metric=metric, transformId=tid, timeframe=kw.pop("timeframe", ANCHOR), **kw)


# --- the records ---------------------------------------------------------------------------------------------------

def test_every_probe_ran_at_169_4_0_and_the_contract_did_not_move():
    for path in AUTHORING + SEQUENCES:
        rec = _j(path)
        assert (rec["contractVersion"], rec["buildSha"]) == ("169.4.0", BUILD), path.name
        assert rec["contractMoved"] is False, path.name
    assert len(SEQUENCES) == 7


def test_the_manifest_is_the_169_re_read_and_its_counts_are_the_corpus():
    assert (MANIFEST["servedContractVersion"], MANIFEST["extractedOn"]) == ("169.4.0", "2026-11-12")
    assert BUILD in MANIFEST["contractVersionSource"]
    assert MANIFEST["supersedes"]["servedContractVersion"] == "168.3.0"
    surface = MANIFEST["writeSurface"]
    assert (surface["servedContractVersion"], surface["buildSha"]) == ("169.4.0", BUILD)
    assert stage_schema()["contractVersion"] == "169.4.0"
    index = _j(ROOT / "data/contract/metrics/_index.json")
    assert (index["contractVersion"], index["buildSha"]) == ("169.4.0", BUILD)
    c = load()
    counts = MANIFEST["counts"]
    assert counts["metrics"] == len(c.metrics) == 581
    assert counts["structuralShapes"] == len(enumerate_shapes(contract=c)) == 27244
    assert counts["operandExpandedShapes"] == len(enumerate_shapes(expand_operands=True, contract=c)) == 508207
    assert c.unmeasured_chain_outers == {} and c.unmeasured_transforms == {} and c.unmeasured_metrics == {}


# --- the chained spread and the averaged operand: every probe replayed ------------------------------------------------

def _single_column_probes():
    for path in AUTHORING:
        for p in _j(path)["probes"]:
            cols = [col for s in p["sections"] for col in s["columns"]]
            if len(cols) == 1:
                yield p, cols[0]


def test_every_single_column_probe_gets_the_platforms_verdict_and_header():
    seen = accepted = 0
    for p, col in _single_column_probes():
        seen += 1
        try:
            column = Column(**col)
        except ValueError:
            assert not p["accepted"], p["probe"]
            continue
        errors = _errors(column)
        assert p["accepted"] == (not errors), (p["probe"], errors, (p["refusal"] or {}).get("message"))
        if p["accepted"]:
            accepted += 1
            assert [o.header for o in outputs_for(column)] == [o["header"] for o in p["render"]["outputs"]], p["probe"]
    assert (seen, accepted) == (59, 28)


def test_the_batch_that_rendered_whole_is_predicted_whole():
    rendered = [p for p in _j(AUTHORING[0])["probes"] if p["probe"] == "W.accept"]
    assert len(rendered) == 1 and rendered[0]["accepted"]
    columns = [Column(**col) for s in rendered[0]["sections"] for col in s["columns"]]
    assert all(_errors(column) == [] for column in columns)
    assert sorted(o.header for column in columns for o in outputs_for(column)) == sorted(
        o["header"] for o in rendered[0]["render"]["outputs"])


@pytest.mark.parametrize("column, header", [
    (_col("CLOSE", "ema", window=20, chainedTransformId="spread", inputs=[Operand(metric="EMA50")]),
     "close_ema20_EMA50_spread"),
    (_col("CLOSE", "ema", chainedTransformId="spread", inputs=[Operand(metric="EMA50")]), "close_ema20_EMA50_spread"),
    (_col("RSI14", "aggregate", window=14, chainedTransformId="spread", inputs=[Operand(metric="RSI7")]),
     "RSI14_mean14_RSI7_spread"),
    (_col("CLOSE", "ema", window=20, timeframe={"abs": "4h"}, chainedTransformId="spread",
          inputs=[Operand(metric="SMA20")]), "close_4h_ema20_SMA20_spread"),
    (_col("CLOSE", "ema", window=20, bars="all", chainedTransformId="spread", inputs=[Operand(metric="EMA50")]),
     "close_dev_ema20_EMA50_spread"),
    (_col("CLOSE", "ema", window=704, chainedTransformId="spread",
          inputs=[Operand(metric="CLOSE", transformId="aggregate", window=2436)]), "close_ema704_close_mean2436_spread"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="CLOSE", transformId="ema", window=20)]), "close_close_ema20_spread"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="SMA50", transformId="rma", window=14)]),
     "close_SMA50_rma14_spread"),
    (_col("CLOSE", "spread", timeframe={"rel": "lower"}, inputs=[Operand(metric="CLOSE", transformId="ema", window=20)]),
     "close_ltf_close_ema20_spread"),
])
def test_the_headers_spell_as_rendered(column, header):
    assert _errors(column) == []
    assert [o.header for o in outputs_for(column)] == [header]


@pytest.mark.parametrize("column, code", [
    # the averaged operand
    (_col("CLOSE", "spread", inputs=[Operand(metric="CLOSE", transformId="ema")]), "OPERAND_AVERAGE_INCOMPLETE"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="CLOSE", window=20)]), "OPERAND_AVERAGE_INCOMPLETE"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="CLOSE", transformId="zscore", window=14)]),
     "OPERAND_AVERAGE_TRANSFORM"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="CLOSE", transformId="ema", window=1)]), "WINDOW_BELOW_MINIMUM"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="CLOSE", transformId="ema", window=705)]), "DEPTH_EXCEEDED"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="CLOSE", transformId="rma", window=309)]), "DEPTH_EXCEEDED"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="CLOSE", transformId="aggregate", window=2437)]), "DEPTH_EXCEEDED"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="MARK", transformId="ema", window=20)]), "OPERAND_NOT_ALLOWED"),
    (_col("CLOSE", "spread", inputs=[Operand(metric="ASIA_HIGH", transformId="ema", window=20)]),
     "OPERAND_NOT_ALLOWED"),
    (_col("CLOSE", "spread", chainedTransformId="trajectory", window=4,
          inputs=[Operand(metric="CLOSE", transformId="ema", window=20)]), "REPORT_COLUMN_CHAIN_UNSUPPORTED"),
    # the chained spread
    (_col("CLOSE", "ema", window=20, chainedTransformId="spread"), "OPERAND_REQUIRED"),
    (_col("CLOSE", "ema", window=20, chainedTransformId="spread", inputs=[Operand(metric="CLOSE")]),
     "REPORT_COLUMN_OPERAND_UNSUPPORTED"),
    (_col("CLOSE", "ema", window=20, timeframe={"abs": "4h"}, chainedTransformId="spread",
          inputs=[Operand(metric="PIVOT_WEEK_P")]), "REPORT_COLUMN_OPERAND_UNSUPPORTED"),
    (_col("CLOSE", "ema", window=705, chainedTransformId="spread", inputs=[Operand(metric="SMA20")]), "DEPTH_EXCEEDED"),
    (_col("CLOSE", "ema", window=20, chainedTransformId="spread", chainedWindow=5, inputs=[Operand(metric="EMA50")]),
     "CHAINED_WINDOW_REFUSED"),
    (_col("CLOSE", "ema", window=20, chainedTransformId="spread", offset=1, inputs=[Operand(metric="EMA50")]),
     "OFFSET_REFUSED"),
    (_col("CLOSE", "rma", window=308, chainedTransformId="spread",
          inputs=[Operand(metric="CLOSE", transformId="rma", window=308)]), "OPERAND_SELF"),
    (_col("RSI14", "zscore", window=20, chainedTransformId="spread", inputs=[Operand(metric="RSI7")]),
     "REPORT_COLUMN_CHAIN_UNSUPPORTED"),
])
def test_each_refusal_is_the_platforms(column, code):
    assert code in _errors(column)


def test_the_chained_spread_shapes_are_in_the_space_and_were_all_rendered():
    c = load()
    shapes = [s for s in enumerate_shapes(contract=c) if s.chained == "spread"]
    assert len(shapes) == 660 and {s.transform for s in shapes} == {"aggregate", "ema", "rma", "wma"}
    assert all(s.operand is not None and _errors(s.to_column()) == [] for s in shapes)
    coin, market = _j(AUDIT / "coverage_sweep_2026-11-12.json"), _j(AUDIT / "coverage_sweep_2026-11-12-market.json")
    for rec, n in ((coin, 620), (market, 40)):
        assert (rec["shapesTargeted"], rec["headersMinted"], rec["refusalCount"],
                rec["predictedButNotRenderedCount"], rec["complete"], rec["contractMoved"]) == (n, n, 0, 0, True, False)


def test_an_averaged_or_chained_spread_operand_is_no_level_reading():
    sections = [{"kind": "custom", "marketScope": None, "benchmarkTicker": None, "columns": [
        {"metric": "CLOSE", "transformId": "ema", "window": 20, "chainedTransformId": "spread",
         "inputs": [{"metric": "EMA50"}], "timeframe": ANCHOR},
        {"metric": "HIGH", "transformId": "spread", "inputs": [{"metric": "SMA50", "transformId": "ema", "window": 9}],
         "timeframe": ANCHOR}]}]
    yields, _, unmeasured = report_readings(sections, "1h")
    assert {y[0] for y in yields} == {"CLOSE", "HIGH"} and unmeasured == {"EMA50", "SMA50"}


# --- SEQUENCE --------------------------------------------------------------------------------------------------------

# `within` above a step column's stored history: the bound is the column's served conditionHold.maxWindow
# (MACDhist_trend 2449 at 1h, MAalign 2499), the same per-column number that bounds a hold's `of`. Only the preview serves
# it, so omega refuses past the longest measured (2499, which covers X2.seq.within2500) and leaves a step column's own
# bound below that to the builder - as it does a hold's `of` (review 2026-11-12, finding 1).


def test_every_sequence_probe_gets_the_platforms_verdict_and_frame_read_count():
    p = plan(PRESETS["trend-continuation"])
    base = list(p.conditions)
    assert K.frame_reads(base) == 11
    seen, counted = 0, 0
    for path in SEQUENCES:
        for probe in _j(path)["probes"]:
            extra = probe["condition"]
            conds = base + (extra if isinstance(extra, list) else [extra] if extra else [])
            errors = [f for f in K.validate_conditions(p.report, conds) if f.severity == "error"]
            seen += 1
            message = str((probe.get("refusal") or {}).get("message") or "")
            assert probe["accepted"] == (not errors), (path.name, probe["probe"], [f.message for f in errors], message)
            count = re.search(r"declares (\d+) condition frame reads", message)
            if count:
                counted += 1
                assert K.frame_reads(conds) == int(count.group(1)), probe["probe"]
    assert (seen, counted) == (57, 10)


def test_the_builder_makes_what_the_platform_accepts():
    a, b, c = K.is_("MAalign", "bullish"), K.is_("MACDhist_trend", "rising"), K.is_("OBV_trend", "rising")
    seq = K.sequence(a, b, c, within=10)
    assert seq == {"kind": "group", "op": "SEQUENCE", "hold": {"atLeast": 1, "of": 1}, "members": [a, b, c],
                   "within": 10}
    K.sequence(K.all_of(a), K.any_of(b, c), within=5)
    K.sequence(K.n_of(1, a, b), K.not_(c), within=5)
    K.sequence(K.ref("TC_RISK_ON"), a, within=5)
    cond = K.condition("SEQ", "in order", seq, verdict="UP", required=True)
    assert cond["definition"] is seq and cond["exitSide"] is None


@pytest.mark.parametrize("build, words", [
    (lambda a, b: K.sequence(a, b, within=1), "at least 2"),
    (lambda a, b: K.sequence(a, b, within=2500), "2499 closes"),
    (lambda a, b: K.sequence(a, within=5), "orders at least 2"),
    (lambda a, b: K.sequence(K.is_("MAalign", "bullish", hold=(2, 3)), b, within=5), "cannot count closes"),
    (lambda a, b: K.sequence(K.all_of(K.all_of(a), b), b, within=5), "group inside a group"),
    (lambda a, b: K.sequence(K.all_of(K.ref("TC_RISK_ON"), a), b, within=5), "step of its own"),
    (lambda a, b: K.group("SEQUENCE", [a, b]), "sequence("),
    (lambda a, b: K.condition("SEQ", "x", K.sequence(a, b, within=5), exit_side="SHORT"), "entry only"),
    (lambda a, b: K.condition("SEQ", "x", K.sequence(a, b, within=5), hold=(1, 3)), "holds Once"),
    (lambda a, b: K.close_on(K.condition("SEQ", "x", K.sequence(a, b, within=5))), "in order"),
])
def test_the_builder_refuses_what_the_platform_refuses(build, words):
    a, b = K.is_("MAalign", "bullish"), K.is_("MACDhist_trend", "rising")
    with pytest.raises(ValueError, match=re.escape(words)):
        build(a, b)


def test_the_frame_read_count_is_the_platforms_arithmetic():
    a = K.is_("MAalign", "bullish")
    one = [K.condition("A", "a", a)]
    assert K.frame_reads(one) == 1
    held = K.is_("MAalign", "bullish", hold=(1, 5100))
    assert K.frame_reads([K.condition("A", "a", K.all_of(held, a))]) == 5101
    assert K.frame_reads([K.condition("A", "a", K.all_of(a, a, hold=(1, 3000)))]) == 6000
    # a prior-bar operator adds one close, not one per bar
    assert K.frame_reads([K.condition("A", "a", K.all_of(K.enters("MAalign", "bullish"), a, hold=(1, 2400)))]) == 4801
    # a sequence's window is every step clause's; a reference step reads the referenced condition on each bar
    seq = K.sequence(K.ref("A"), K.all_of(a, a), a, within=100)
    assert K.frame_reads(one + [K.condition("S", "s", seq)]) == 1 + 100 + 200 + 100
    # a reference member of a plain group costs nothing: the referenced condition is counted once, as itself
    assert K.frame_reads(one + [K.condition("B", "b", K.all_of(K.ref("A"), a))]) == 2
    assert load().budgets["conditionFrameReads"] == 5048


def test_an_exit_rule_may_not_be_or_read_a_sequence():
    p = plan(PRESETS["trend-continuation"])
    a, b = K.is_("MAalign", "bullish"), K.is_("MACDhist_trend", "rising")
    seq = K.condition("SEQ", "in order", K.sequence(a, b, within=5))
    rule = K.exit_rule("CLOSE_ON_SEQ", "close", K.ref("SEQ"), "LONG")
    deeper = K.exit_rule("CLOSE_DEEP", "close", K.all_of(K.ref("USES_SEQ")), "BOTH")
    uses = K.condition("USES_SEQ", "uses", K.all_of(K.ref("SEQ"), a))
    findings = K.validate_conditions(p.report, list(p.conditions) + [seq, rule, uses, deeper])
    errors = {(f.condition_key, "CONDITION_EXIT_SEQUENCE_UNSUPPORTED" in f.message) for f in findings if f.severity == "error"}
    assert errors == {("CLOSE_ON_SEQ", True), ("CLOSE_DEEP", True)}
    # an entry condition may reference a sequence from a group (X3.ref.from.group rendered)
    assert not [f for f in K.validate_conditions(p.report, list(p.conditions) + [seq, uses]) if f.severity == "error"]


def test_the_frame_read_budget_refuses_a_plan_offline():
    p = plan(PRESETS["trend-continuation"])
    a, b, c = K.is_("MAalign", "bullish"), K.is_("MACDhist_trend", "rising"), K.is_("OBV_trend", "rising")
    seq = K.condition("SEQ", "in order", K.sequence(a, b, c, within=2000))
    findings = [f for f in K.validate_conditions(p.report, list(p.conditions) + [seq]) if f.severity == "error"]
    assert [f.condition_key for f in findings] == ["<report>"] and "6011 condition frame reads" in findings[0].message


# --- the independent review of 2026-11-12 ------------------------------------------------------------------------------

def test_a_member_that_is_not_an_object_is_a_finding_not_a_crash():
    p = plan(PRESETS["trend-continuation"])
    a = K.is_("MAalign", "bullish")
    bad = {"kind": "group", "op": "SEQUENCE", "hold": {"atLeast": 1, "of": 1}, "members": ["x", a], "within": 5}
    plain = {"kind": "group", "op": "ALL", "hold": {"atLeast": 1, "of": 1}, "members": [None, a]}
    for definition in (bad, plain):
        findings = K.validate_conditions(p.report, list(p.conditions) + [K.condition("BAD", "bad", definition)])
        assert any(f.severity == "error" and f.condition_key == "BAD" for f in findings)


def test_an_averaged_operand_off_spread_is_refused_not_ignored():
    column = _col("CLOSE", "ema", window=20, inputs=[Operand(metric="EMA50", transformId="ema", window=20)])
    assert _errors(column) == ["OPERAND_REFUSED"]
    # a plain operand there keeps its old warning (OPERAND_IGNORED), as before 168
    plain = _col("CLOSE", "ema", window=20, inputs=[Operand(metric="EMA50")])
    assert [f.code for f in validate_column(plain)] == ["OPERAND_IGNORED"]


def test_an_operand_carrying_only_a_window_is_no_level_reading():
    sections = [{"kind": "custom", "marketScope": None, "benchmarkTicker": None, "columns": [
        {"metric": "CLOSE", "transformId": "spread", "inputs": [{"metric": "EMA50", "window": 20}],
         "timeframe": ANCHOR}]}]
    yields, _, unmeasured = report_readings(sections, "1h")
    assert {y[0] for y in yields} == {"CLOSE"} and unmeasured == {"EMA50"}
