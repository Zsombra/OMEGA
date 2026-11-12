"""The REPORT surface at contract 108: the custom section and its column, against the saved schemas.

Sources (all on disk): the 108 write schema the manifest names (`stage_strategy_draft` REPORT axis,
data/contract/stage_strategy_draft/schema_20261010T215326Z.json), the `get_strategy_column_contract` input schema at
104.1.0 (data/contract/get_strategy_column_contract/schema_104.1.0.json, copied from battlegrid-manager's fixture), and
the vendored README "Contract history" entries quoted beside each assertion. Plan:
docs/plans/2026-10-12-omega-report-surface-108.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pydantic
import pytest

from omega import condition_vocabulary as CV
from omega.contract import load
from omega.probe import contract_request
from omega.space import ColumnShape, enumerate_shapes
from omega.types import Column, CustomSection, PlatformSection, RelTimeframe, Report
from omega.validate import validate_column, validate_report, validate_section

ROOT = Path(__file__).resolve().parents[1]
C = load()
V = CV.vocabulary()
COLUMN_CONTRACT = json.loads((ROOT / "data/contract/get_strategy_column_contract/schema_104.1.0.json")
                             .read_text(encoding="utf-8"))


def col(metric="RSI14", transform="value", **kw) -> Column:
    return Column(metric=metric, transformId=transform, timeframe=RelTimeframe(rel="anchor"), **kw)


def codes(findings) -> set[str]:
    return {f.code for f in findings if f.severity == "error"}


# --- the inventory derives the section, not only the column -----------------------------------------
def test_the_inventory_carries_the_custom_section_arm():
    sec = V["reportSection"]
    # marketScope since 146.0.0 (2026-11-01): required, null or one of nine category names (tests/test_v146.py)
    assert sec["fields"] == ["benchmarkTicker", "columns", "kind", "marketScope", "notes", "sectionKey", "title"]
    assert sec["required"] == ["kind", "title", "benchmarkTicker", "marketScope", "notes", "columns"]
    assert sec["additionalProperties"] is False
    # v103: "The fixed 64 maximums leave strategy authoring: ... a custom section's columns"
    assert sec["columns"] == {"minItems": 1}
    assert CV.resolve(json.loads(CV.schema_path().read_text(encoding="utf-8")), sec["pointer"])["properties"]


def test_the_column_integer_bounds_are_derived():
    # v103: "`window` and `offset` keep their integer floors"; v100: buffer "whole basis points ... 0-500"
    # 161.0.0 (2026-11-09): buffer's maximum is now the safe-integer cap like the other knobs (it was 500 until the
    # 149.1.0 capture), and six more `$ref`s to barCount join the bounds: the four Ichimoku knobs (basePeriod,
    # conversionPeriod, displacement, spanBPeriod), chainedWindow and ADX/ATR/DI/VWMA20's period (already below)
    assert V["reportColumn"]["bounds"] == {"buffer": {"minimum": 0, "maximum": 9007199254740991},
                                          "offset": {"minimum": 0, "maximum": 9007199254740991},
                                          "window": {"minimum": 1, "maximum": 9007199254740991},   # v115.1
                                          # v146.9 / v146.11, the 148.1.0 capture (2026-11-05)
                                          "leftBars": {"minimum": 1, "maximum": 9007199254740991},
                                          "rightBars": {"minimum": 1, "maximum": 9007199254740991},
                                          "swingLength": {"minimum": 1, "maximum": 9007199254740991},
                                          "equalBars": {"minimum": 1, "maximum": 9007199254740991},
                                          # the 149.1.0 capture (2026-11-07): equalThreshold loses its minimum 0; the
                                          # eight new length knobs are `$ref`s to $defs/barCount (integer >= 1, read
                                          # through the ref); multiplier, stdDev and PSAR's three are bare numbers
                                          "equalThreshold": {},
                                          **{k: {"minimum": 1, "maximum": 9007199254740991} for k in (
                                              "atrPeriod", "dSmoothing", "fast", "kSmoothing", "period",
                                              "rsiPeriod", "signal", "slow", "basePeriod", "chainedWindow",
                                              "conversionPeriod", "displacement", "spanBPeriod")},
                                          **{k: {} for k in ("multiplier", "stdDev", "touchAtr", "accelerationStart",   # touchAtr: 161.0.0 (2026-11-09), a bare number
                                                             "accelerationIncrement", "accelerationMaximum",
                                                             # 2026-11-11, contract 168.3.0 (the capture of
                                                             # schema_20261111T213257Z.json): two of the three knobs 168
                                                             # added to the column are bare numbers ({"type": "number"},
                                                             # no minimum / maximum); the third, usedUpOnClose, is a
                                                             # boolean and so has no numeric bound to derive
                                                             "supplyDemandThreshold", "supplyDemandResolution")}}


def test_the_gaps_name_only_the_retired_section_field():
    gaps = CV.gaps()
    # since the 148.1.0 capture (2026-11-05): the six v146.9 / v146.11 knobs, served and not modelled (unmeasured: the
    # re-extraction stopped before the hints that serve them per metric)
    # since the 149.1.0 capture (2026-11-07): plus the thirteen 149.x knobs, served and not modelled either
    # since the model step of 2026-11-07 omega.types.Column carries all nineteen (omega.types.KNOBS): no gap
    assert gaps["columnFields"] == {"schemaOnly": [], "omegaOnly": []}
    # kept on the model so a pre-48 record still loads; validate_section refuses it
    assert gaps["sectionFields"] == {"schemaOnly": [], "omegaOnly": ["timeframe"]}


# --- transforms: retired and unmeasured, both derived from the served enum ---------------------------
def test_the_retired_transforms_are_the_corpus_minus_the_served_enum():
    assert set(C.retired_transforms) == {"bandTouch"}
    # retired at 108 (README v100/v108); `servedAt` is the schema checked, the 110.13.0 (v111) capture since 2026-10-16
    # (the 135.2.0 capture since 2026-10-26, the 144.0.0 one since 2026-10-30, the 146.0.0 one since 2026-11-01, the
    # 148.1.0 one since 2026-11-05, the 149.1.0 one since 2026-11-07, the 161.0.0 one since 2026-11-09, the 168.3.0 one
    # since 2026-11-11: data/derived/condition_vocabulary_108.json source.contractVersion, the schema the enum is read from)
    assert C.retired_transforms["bandTouch"]["servedAt"] == "169.4.0"   # 2026-11-12: was 168.3.0 (2026-11-11), 161.0.0 (2026-11-09), 149.1.0 before
    assert not any("bandTouch" in m.transforms for m in C.metrics.values())


def test_no_served_transform_is_unmeasured_since_the_108_4_extraction():
    """levelInteraction was served-but-unmeasured from 2026-10-12 until the 2026-10-13 re-extraction read it per metric
    (43 metrics offer it). classifyState is served too, and is the platform-privileged one. 44 since the re-extraction at
    110.2.0 (2026-10-14): KC_MID retired, the two Donchian break levels (DONCHIAN_BROKEN_HI/LO) offer it - unlike the
    Donchian rails - and their headers rendered live (_coverage_sweep_2026-10-14.json). 46 since 110.8.0 (2026-10-15):
    the two prior-bar Donchian edges (DONCHIAN_UPPER/LOWER_PRIOR, README v110.6: "They take `levelInteraction`");
    the four single-print zone edges do not (value, distance, spread only)."""
    # since the 148.1.0 capture (2026-11-05): v146.7's `ema`, served and not extracted (the hint step stopped first)
    # and since the 149.1.0 capture (2026-11-07) the four 149.0 smoothers / oscillators rma, wma, rsi and cci
    # all five folded in by the refresh at 149.1.0 and rendered by the probe of 2026-11-07: none unmeasured since
    assert C.unmeasured_transforms == {}
    assert {"ema", "rma", "wma", "rsi", "cci"} <= set(C.transforms)
    # 318 since the refresh at 149.1.0: the 198 pivots, the structure / swing levels and EQH / EQL of 148.1.0
    # 352 since 161.0.0 (2026-11-09, _moves_161.json): +33 existing levels (the session highs / lows / opens, IB extensions,
    # opening ranges and the TPO / week / month profile levels), -2 (DONCHIAN_BROKEN_HI / LO) and +3 added (VWMA20 and the
    # two DONCHIAN_BROKEN_*_PRIOR)
    # 2026-11-11, contract 168.3.0 (extraction 20261111): 393 = 352 + 41 of the 47 added metrics (_moves_168.json): EMA55,
    # EQH_LEVEL / EQL_LEVEL, the four *_PENDING_* levels, LIQUIDITY_POOL_ABOVE / _BELOW and their _RETIRED, the 24
    # PRIOR_<session>_DEMAND_* / _SUPPLY_* and the six ZONE_*; not the four pool flags (_INTACT / _RECLAIMED) nor the two
    # _TOUCHES counts. No existing metric gained or lost it.
    assert sum("levelInteraction" in m.transforms for m in C.metrics.values()) == 393   # 352 at 161.0.0; 118 at 144.0.0; 58 at 135.2.0 (46 at 110.8.0); 118 at 144.0.0: the v137.2 VWAP lines, bands and profile levels


def test_a_retired_transform_is_refused_naming_its_replacement():
    f = validate_column(col("OPEN", "bandTouch"), contract=C)
    assert codes(f) == {"TRANSFORM_RETIRED"}
    msg = f[0].message
    # 161.0.0 (2026-11-09): the retired transform is judged against the 161.0.0 schema, and BB_TOUCH itself is gone
    # from the enum (the message names its replacement BB_PCT_B / BB_UPPER x levelInteraction)
    assert "BB_TOUCH" in msg and "levelInteraction" in msg and "161.0.0" in msg
    # 2026-11-11, contract 168.3.0: the schema judged against is the 168.3.0 capture. "161.0.0" above still holds, but
    # only through the replacement text ("BB_TOUCH itself was removed at contract 161.0.0"), so the served version is
    # pinned on its own here - without this line the assertion above no longer tracks the schema the message names.
    # 2026-11-12: the 169.4.0 capture (its six draft tools byte-identical to 168.3.0's)
    assert "the contract 169.4.0 write schema" in msg


def test_level_interaction_validates_on_a_level_and_is_refused_on_a_price_fact():
    """README v100: offered on "a candle-homed level (a band, VWAP, a moving average, ST_LINE, PSAR, the Ichimoku
    lines) or a prior-session level or pivot"; "not offered on a price fact (CLOSE, MARK, HLC3), a developing-session
    level (TPO_*), the naked points of control, or the Donchian rails". The extraction agrees on every one named."""
    assert codes(validate_column(col("BB_UPPER", "levelInteraction"), contract=C)) == set()
    # 161.0.0 (2026-11-09): the developing-session TPO levels now OFFER it (_moves_161.json, measured at 161.0.0 - the
    # README's "not offered on TPO_*" no longer holds): TPO_POC moves from the refused list to the accepted line above
    assert codes(validate_column(col("TPO_POC", "levelInteraction"), contract=C)) == set()
    for fact in ("CLOSE", "MARK", "HLC3", "NAKED_POC_ABOVE", "DONCHIAN_UPPER"):
        assert codes(validate_column(col(fact, "levelInteraction"), contract=C)) == {"REPORT_COLUMN_PAIR_UNSUPPORTED"}


def test_level_interaction_headers_are_the_measured_ones():
    """get_strategy_column_contract, 2026-10-13 (data/contract/columns/levelInteraction_108_4_2026-10-13.json), under
    the code v123 gave BB_UPPER (`bbUpper` -> `bbUpper20`; the measurement read `bbUpper_lvl`, `bbUpper_lvl_b25`)."""
    from omega.fanout import outputs_for
    assert [o.header for o in outputs_for(col("BB_UPPER", "levelInteraction"))] == ["bbUpper20_lvl"]
    assert [o.header for o in outputs_for(col("BB_UPPER", "levelInteraction", buffer=25))] == ["bbUpper20_lvl_b25"]
    lower = Column(metric="VWAP", transformId="levelInteraction", timeframe=RelTimeframe(rel="lower"))
    out = outputs_for(lower)
    assert [(o.header, o.kind) for o in out] == [("VWAP_ltf_lvl", "classification")]
    assert out[0].vocabulary == ("touch_from_below", "touch_from_above", "reject_from_below", "reject_from_above", "none")


def test_the_space_never_enumerates_a_retired_transform_and_does_enumerate_level_interaction():
    shapes = enumerate_shapes(expand_operands=True)
    assert not [s for s in shapes if "bandTouch" in (s.transform, s.chained)]
    # 2026-11-11, contract 168.3.0 (extraction 20261111): 393, one atom per metric that offers it (the count above)
    assert len([s for s in shapes if s.transform == "levelInteraction"]) == 393      # 352 at 161.0.0 (2026-11-09: 318 at 149.1.0); 118 at 146.0.1; 58 at 135.2.0; 43 at 108.4.0, 44 at 110.2.0, 46 at 110.8.0


# --- buffer ----------------------------------------------------------------------------------------
def test_buffer_carries_the_schema_bounds():
    assert col("BB_UPPER", "value", buffer=0).buffer == 0
    assert col("BB_UPPER", "value", buffer=500).buffer == 500
    for bad in (-1, 501):
        with pytest.raises(pydantic.ValidationError):
            col("BB_UPPER", "value", buffer=bad)


def test_buffer_on_any_transform_but_level_interaction_is_refused():
    # v100: "`buffer` on any other transform is refused as an undeclared parameter"
    assert "BUFFER_UNDECLARED" in codes(validate_column(col("BB_UPPER", "value", buffer=25), contract=C))
    assert "BUFFER_UNDECLARED" not in codes(
        validate_column(col("BB_UPPER", "levelInteraction", buffer=25), contract=C))


# --- the section anchor override left at 48.0.0 ----------------------------------------------------
def test_a_section_timeframe_is_refused_as_retired():
    sec = CustomSection(title="pinned", columns=[col("RSI14", "value")], timeframe="4h")
    f = validate_section(sec, contract=C)
    assert codes(f) == {"SECTION_TIMEFRAME_RETIRED"}
    assert "48.0.0" in f[0].message


def test_the_old_override_rules_left_with_the_override():
    # 48.0.0: "REPORT_COLUMN_SECTION_TIMEFRAME_UNSUPPORTED leaves the authoringCode vocabulary"
    sec = CustomSection(title="pinned", columns=[col("FUNDING_RATE", "value")], timeframe="4h")
    assert codes(validate_section(sec, contract=C)) == {"SECTION_TIMEFRAME_RETIRED"}


# --- the fixed 64 maximums left at v103; the budgets judge ------------------------------------------
def test_window_and_offset_have_floors_and_no_fixed_ceiling():
    assert col("RSI14", "trajectory", window=100).window == 100
    assert col("RSI14", "value", offset=100).offset == 100
    assert "LOOKBACK_EXCEEDED" in codes(validate_column(col("RSI14", "trajectory", window=100), contract=C))
    with pytest.raises(pydantic.ValidationError):
        col("RSI14", "trajectory", window=0)
    with pytest.raises(pydantic.ValidationError):
        col("RSI14", "value", offset=-1)


def test_a_section_and_a_report_have_no_fixed_ceiling_and_the_budgets_judge():
    many = [col("CLOSE", "trajectory", window=2 + (i % 30)) for i in range(65)]
    sec = CustomSection(title="wide", columns=many)
    assert "SECTION_COLUMNS_EXCEEDED" in codes(validate_section(sec, contract=C))
    report = Report(sections=[PlatformSection(sectionKey="includeRsi")] * 65)
    assert "SECTIONS_EXCEEDED" in codes(validate_report(report, contract=C).findings)


def test_benchmark_ticker_is_a_coin_symbol():
    for ok in ("BTC", "kPEPE", "xyz:BRENTOIL", None):
        assert CustomSection(title="t", columns=[col()], benchmarkTicker=ok).benchmarkTicker == ok
    for bad in ("", "BTC USD", "-BTC", "A" * 21):
        with pytest.raises(pydantic.ValidationError):
            CustomSection(title="t", columns=[col()], benchmarkTicker=bad)


# --- the column-contract request at 104.1.0 -------------------------------------------------------
def test_the_column_contract_request_names_the_anchor_and_validates_against_the_capture():
    req = contract_request(ColumnShape("EMA5", "spread", "trajectory", "EMA13"), window=4)
    assert "sectionTimeframe" not in req
    assert req["anchorTimeframe"] == "1h"
    jsonschema.validate(req, COLUMN_CONTRACT["definition"]["inputSchema"])


def test_the_column_contract_capture_names_its_source():
    assert COLUMN_CONTRACT["contractVersion"] == "104.1.0"
    assert len(COLUMN_CONTRACT["sourceSha256"]) == 64
    assert COLUMN_CONTRACT["definition"]["name"] == "get_strategy_column_contract"
