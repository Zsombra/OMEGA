"""OMEGA v0.15.0: the re-extraction at contract 180.4.0, replayed against its live record.

Record: data/audit/reextraction_180_4_2026-11-19.json (P1, R1 - R4: preview_strategy_report; D1 - D7: one CREATE draft
staged, read back, discarded and read null). Plan: docs/plans/2026-11-19-omega-reextraction-180-4.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.contract import (REFERENCE_PRICES, flipped_price_spread_clause, flipped_price_spread_threshold, load,
                            price_operand_refused, stage_schema)
from omega.fanout import outputs_for
from omega.types import Column, Operand
from omega.validate import validate_column

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data" / "audit" / "reextraction_180_4_2026-11-19.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "data" / "contract" / "_manifest.json").read_text(encoding="utf-8"))
P1 = {c["key"]: c for c in RECORD["previews"]["P1"]["answer"]["columns"]}
STAGES = {s["id"]: s for s in RECORD["draft"]["stages"]}


def _col(metric, operand=None, tf=None, **kw) -> Column:
    tid = kw.pop("tid", "spread")
    inputs = None
    if operand is not None:
        inputs = [Operand(**operand) if isinstance(operand, dict) else Operand(metric=operand)]
    return Column(metric=metric, transformId=tid, timeframe=tf or {"rel": "anchor"}, inputs=inputs, **kw)


def _errors(column: Column, code: str | None = None):
    return [f for f in validate_column(column) if f.severity == "error" and (code is None or f.code == code)]


# --- the extraction -------------------------------------------------------------------------------------------------
def test_the_extraction_and_the_write_surface_are_180_4():
    assert MANIFEST["servedContractVersion"] == "180.4.0"
    assert MANIFEST["writeSurface"]["servedContractVersion"] == "180.4.0"
    assert MANIFEST["writeSurface"]["buildSha"] == RECORD["buildSha"]
    assert MANIFEST["writeSurface"]["supersedes"]["servedContractVersion"] == "171.0.0"
    assert stage_schema()["contractVersion"] == "180.4.0"


def test_the_five_metric_keys_added_since_171_are_extracted():
    c = load()
    roster = set(stage_schema()["get_strategy"]["outputSchema"]["$defs"]["metricKey"]["enum"])
    assert {"ATH", "DAY_HIGH", "DAY_LOW", "WEEK_HIGH", "WEEK_LOW"} <= roster == set(c.metrics)
    for metric, code in {"DAY_HIGH": "dayHi", "DAY_LOW": "dayLo", "WEEK_HIGH": "weekHi", "WEEK_LOW": "weekLo"}.items():
        assert c.metrics[metric].code == code
        [out] = outputs_for(_col(metric, tid="value"))
        assert out.header == code and P1[code]["unit"] == "price" and P1[code]["family"] == "levels"


# --- v181: price is the base of every spread over another reading (announced) ---------------------------------------
@pytest.mark.parametrize("column", [
    _col("PRIOR_TPO_VAL", "CLOSE"), _col("PRIOR_TPO_VAH", "CLOSE"), _col("PRIOR_TPO_POC", "CLOSE"),
    _col("EMA20", "CLOSE"), _col("EMA20", "LAST"),
    _col("HL2", "CLOSE", tid="ema", window=34, chainedTransformId="spread"),
], ids=lambda c: f"{c.metric}-{c.transformId}-{c.inputs[0].metric}")
def test_the_forms_v181_refuses_are_refused_now(column):
    errs = _errors(column, "REPORT_COLUMN_OPERAND_UNSUPPORTED")
    assert len(errs) == 1 and "v181" in errs[0].message and "not served at 180.4.0" in errs[0].message


@pytest.mark.parametrize("column", [
    _col("CLOSE", "PRIOR_TPO_VAL"), _col("CLOSE", "PRIOR_TPO_VAH"), _col("CLOSE", "PRIOR_TPO_POC"),
    _col("CLOSE", "EMA20"), _col("LAST", "CLOSE"), _col("CLOSE", "LAST"),
    _col("CLOSE", {"metric": "HL2", "transformId": "ema", "window": 34}),
    _col("EMA20", {"metric": "CLOSE", "transformId": "ema", "window": 34}),
], ids=lambda c: f"{c.metric}-{c.inputs[0].metric}")
def test_the_forms_v181_keeps_are_accepted(column):
    assert not _errors(column)


def test_the_refusal_names_the_form_to_write_where_the_corpus_admits_it():
    [err] = _errors(_col("PRIOR_TPO_VAH", "CLOSE"))
    assert "write CLOSE x spread(PRIOR_TPO_VAH)" in err.message
    [err] = _errors(_col("HL2", "CLOSE", tid="ema", window=34, chainedTransformId="spread"))
    assert "CLOSE x spread({metric: HL2, transformId: ema, window: 34})" in err.message
    # "or LAST off the anchor, it names none"
    [err] = _errors(_col("EMA20", "LAST", tf={"abs": "4h"}), "REPORT_COLUMN_OPERAND_UNSUPPORTED")
    assert "no form with price as the base" in err.message


def test_the_headers_omega_predicts_are_the_ones_p1_rendered():
    for column, header in [(_col("CLOSE", "PRIOR_TPO_VAL"), "close_pTpoVAL_spread"),
                           (_col("CLOSE", "PRIOR_TPO_VAH"), "close_pTpoVAH_spread"),
                           (_col("CLOSE", "PRIOR_TPO_POC"), "close_pTpoPOC_spread"),
                           (_col("PRIOR_TPO_VAL", "CLOSE"), "pTpoVAL_close_spread"),
                           (_col("EMA20", "CLOSE"), "EMA20_close_spread"),
                           (_col("CLOSE", "EMA20"), "close_EMA20_spread"),
                           (_col("LAST", "CLOSE"), "last_close_spread"),
                           (_col("CLOSE", "LAST"), "close_last_spread"),
                           (_col("CLOSE", {"metric": "HL2", "transformId": "ema", "window": 34}),
                            "close_hl2_ema34_spread")]:
        assert [o.header for o in outputs_for(column)] == [header]
        assert P1[header]["timeframe"] == "4h"


def test_the_flipped_threshold_reproduces_the_two_rendered_values():
    old, new = P1["pTpoVAL_close_spread"]["value"], P1["close_pTpoVAL_spread"]["value"]
    assert flipped_price_spread_threshold(old) == pytest.approx(new, abs=1e-9)
    assert flipped_price_spread_threshold(new) == pytest.approx(old, abs=1e-9)
    assert new != pytest.approx(-old, abs=1e-3)                          # not a negation
    assert flipped_price_spread_clause("gte", 0.05) == ("lte", pytest.approx(-0.0499750124937531))
    assert flipped_price_spread_clause("crossesAbove", 0) == ("crossesBelow", 0)
    with pytest.raises(ValueError):
        flipped_price_spread_clause("increased", 0)
    with pytest.raises(ValueError):
        flipped_price_spread_threshold(-100)


def test_the_reference_prices_and_the_rule():
    assert REFERENCE_PRICES == ("CLOSE", "LAST")
    assert price_operand_refused("EMA20", "CLOSE") and price_operand_refused("PRIOR_TPO_VAL", "LAST")
    assert not price_operand_refused("CLOSE", "LAST") and not price_operand_refused("LAST", "CLOSE")
    assert not price_operand_refused("CLOSE", "EMA20")
    assert price_operand_refused("CLOSE", "LAST", chained=True)      # the average is the base


def test_no_enumerated_shape_carries_a_refused_operand():
    from omega.space import enumerate_shapes
    for expand in (False, True):
        bad = [s for s in enumerate_shapes(expand_operands=expand)
               if s.operand and price_operand_refused(s.metric, s.operand,
                                                      chained=s.chained == "spread" and s.transform != "spread")]
        assert not bad, bad[:5]


def test_no_preset_and_no_tpo_suite_column_uses_a_refused_form():
    from omega.generate import PRESETS, plan
    for name, thesis in PRESETS.items():
        for section in plan(thesis).report.sections:
            for column in getattr(section, "columns", None) or ():
                assert not _errors(column, "REPORT_COLUMN_OPERAND_UNSUPPORTED"), (name, column)
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("tpo_suite_build_v181", ROOT / "scripts" / "tpo_suite_build.py")
    builder = importlib.util.module_from_spec(spec)
    sys.modules["tpo_suite_build_v181"] = builder
    spec.loader.exec_module(builder)
    assert [c.metric for c in builder.SPINE].count("CLOSE") == 3
    for column in builder.SPINE:
        assert not _errors(column, "REPORT_COLUMN_OPERAND_UNSUPPORTED")


# --- v175: a Developing read decides at the decided close (measured D1 / D4 / D7) ---------------------------------
def test_the_record_holds_the_v175_answers():
    d1 = STAGES["D1"]["answer"]["errors"]
    assert [e["authoringCode"] for e in d1] == ["CONDITION_HOLD_ILLEGAL"]
    assert d1[0]["path"] == ["conditions", "DEV_HOLD", "definition", "hold"] and d1[0]["context"]["maxWindow"] == 1
    assert STAGES["D7"]["answer"] == {"errors": [], "warnings": []}
    assert RECORD["draft"]["discard"]["readAfter"]["draft"] is None


# --- level entries: EITHER_SIDE_OF_LEVEL (measured D5 / D6 / D7) ----------------------------------------------------
def test_the_level_triggers_are_read_off_the_write_schema():
    from omega.trade_levels import LEVEL_TRIGGERS, level_triggers
    assert level_triggers() == LEVEL_TRIGGERS == ("STOP_THROUGH_LEVEL", "ON_RETEST", "EITHER_SIDE_OF_LEVEL")


def _level(metric):
    return {"metric": metric, "timeframe": {"rel": "anchor"}, "bars": None, "offset": 0, "knobs": {},
            "windowExtreme": None}


SECTIONS = [{"kind": "custom", "title": "Probe", "benchmarkTicker": None, "marketScope": None, "notes": None,
             "columns": [{"metric": "PRIOR_TPO_VAL", "transformId": "value", "timeframe": {"rel": "anchor"}},
                         {"metric": "CLOSE", "transformId": "spread", "timeframe": {"rel": "anchor"},
                          "inputs": [{"metric": "PRIOR_TPO_VAH"}]}]}]


def test_either_side_of_level_judges_its_levels_as_the_platform_did():
    from omega.trade_levels import validate_entry_levels

    def entry(short):
        return {"trigger": "EITHER_SIDE_OF_LEVEL", "levelOffsetAtrMultiple": 0.2, "validForBars": 4,
                "levels": {"LONG": _level("PRIOR_TPO_VAL"), "SHORT": _level(short)}}
    d5 = validate_entry_levels(entry("PRIOR_TPO_POC"), sections=SECTIONS, anchor="1h")
    assert [f.path for f in d5 if f.severity == "error"] == ["entry.levels.SHORT"]
    assert STAGES["D5"]["answer"]["errors"][0]["field"] == "entry.levels.SHORT"
    d6 = validate_entry_levels(entry("PRIOR_TPO_VAH"), sections=SECTIONS, anchor="1h")
    assert not [f for f in d6 if f.severity == "error"]                   # a spread's plain operand yields it
    assert STAGES["D6"]["answer"]["errors"][0]["field"].startswith("tradeLevelMenu")   # the entry passed


# --- the regime rung ------------------------------------------------------------------------------------------------
def test_the_regime_rung_is_the_measured_one():
    from omega.generate import REGIME_TF_FOR_ANCHOR
    measured = {"1h": RECORD["previews"]["R1"]["answer"]["RSI14_htf"],
                "15m": RECORD["previews"]["R2"]["answer"]["RSI14_htf"],
                "5m": RECORD["previews"]["R3"]["answer"]["RSI14_htf"],
                "4h": P1["RSI14_htf"]["timeframe"]}
    assert REGIME_TF_FOR_ANCHOR == measured == {"5m": "15m", "15m": "1h", "1h": "4h", "4h": "12h"}


# --- the stage-and-discard proof ------------------------------------------------------------------------------------
def test_the_proof_body_is_what_omega_generates_and_it_staged_clean():
    from omega.generate import PRESETS, plan
    from omega.preflight import body_sha256
    proof = RECORD["proof"]
    axes = plan(PRESETS["trend-continuation"]).axes()
    assert axes == proof["sentAxes"] and body_sha256(axes) == proof["bodySha256Sent"]
    assert proof["stages"][0]["answer"] == {"errors": [], "warnings": []}
    assert proof["readBack"]["contentEqualsSentAsValues"] and proof["discard"]["readAfter"]["draft"] is None


def test_the_served_anchor_set_is_recorded_and_omega_keeps_its_measured_four():
    from typing import get_args
    from omega.types import ANCHOR_TIMEFRAMES
    served = RECORD["proof"]["stages"][2]["answer"]["errors"][0]["allowedDomain"]["values"]
    assert served == ["5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d"]
    assert set(get_args(ANCHOR_TIMEFRAMES)) == {"5m", "15m", "1h", "4h"} < set(served)
