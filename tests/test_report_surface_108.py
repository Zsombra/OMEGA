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
    assert sec["fields"] == ["benchmarkTicker", "columns", "kind", "notes", "sectionKey", "title"]
    assert sec["required"] == ["kind", "title", "benchmarkTicker", "notes", "columns"]
    assert sec["additionalProperties"] is False
    # v103: "The fixed 64 maximums leave strategy authoring: ... a custom section's columns"
    assert sec["columns"] == {"minItems": 1}
    assert CV.resolve(json.loads(CV.schema_path().read_text(encoding="utf-8")), sec["pointer"])["properties"]


def test_the_column_integer_bounds_are_derived():
    # v103: "`window` and `offset` keep their integer floors"; v100: buffer "whole basis points ... 0-500"
    assert V["reportColumn"]["bounds"] == {"buffer": {"minimum": 0, "maximum": 500},
                                          "offset": {"minimum": 0}, "window": {"minimum": 1}}


def test_the_gaps_name_only_the_retired_section_field():
    gaps = CV.gaps()
    assert gaps["columnFields"] == {"schemaOnly": [], "omegaOnly": []}
    # kept on the model so a pre-48 record still loads; validate_section refuses it
    assert gaps["sectionFields"] == {"schemaOnly": [], "omegaOnly": ["timeframe"]}


# --- transforms: retired and unmeasured, both derived from the served enum ---------------------------
def test_the_retired_transforms_are_the_corpus_minus_the_served_enum():
    assert set(C.retired_transforms) == {"bandTouch"}
    assert C.retired_transforms["bandTouch"]["servedAt"] == "108.0.0"
    assert not any("bandTouch" in m.transforms for m in C.metrics.values())


def test_the_unmeasured_transforms_are_served_and_neither_extracted_nor_privileged():
    # classifyState is served too, and is the platform-privileged one (data/derived/platform_privileged.json)
    assert set(C.unmeasured_transforms) == {"levelInteraction"}


def test_a_retired_transform_is_refused_naming_its_replacement():
    f = validate_column(col("OPEN", "bandTouch"), contract=C)
    assert codes(f) == {"TRANSFORM_RETIRED"}
    msg = f[0].message
    assert "BB_TOUCH" in msg and "levelInteraction" in msg and "108.0.0" in msg


def test_an_unmeasured_transform_is_refused_until_its_contract_is_read():
    f = validate_column(col("BB_UPPER", "levelInteraction"), contract=C)
    assert codes(f) == {"TRANSFORM_UNMEASURED"}
    assert "get_strategy_column_contract" in f[0].message


def test_the_space_never_enumerates_a_retired_or_unmeasured_transform():
    for shape in enumerate_shapes(expand_operands=True):
        assert {shape.transform, shape.chained} & {"bandTouch", "levelInteraction"} == set()


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
