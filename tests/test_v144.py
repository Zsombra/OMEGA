"""Contracts v136 - v144 (battlegrid-mcp README "Contract history"), against the corpus re-extracted at 144.0.0 on
2026-10-30 (docs/plans/2026-10-30-omega-reextraction-144.md).

- v136: a `rank` column takes a category `scope`, which lands in the header; refused off rank and on a report-scoped rank.
- v136.1 / v137 / v137.2 / v137.3 / v138: 78 metrics added; STOCH_RSI14 (v137) and BB_WIDTH (v138) retired.
- v137: `points`; a spread over a comparable unit is a difference. v142.3: `relativeTo`, `instrument`, `priceRatio`.
- v138: OBV's level reads are refused.

Every header and refusal asserted here was rendered 2026-10-30 (data/audit/relative_to_probe_144*_2026-10-30.json).
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from omega.contract import CONTRACT_DIR, load
from omega.fanout import instrument_token, outputs_for, scope_token
from omega.types import Column
from omega.validate import validate_column

A, L = {"rel": "anchor"}, {"rel": "lower"}
AUDIT = CONTRACT_DIR.parent / "audit"
PROBE = json.loads((AUDIT / "relative_to_probe_144_2026-10-30.json").read_text(encoding="utf-8"))
PROBE_B = json.loads((AUDIT / "relative_to_probe_144b_2026-10-30.json").read_text(encoding="utf-8"))
MOVES = json.loads((CONTRACT_DIR / "metrics" / "_moves_144.json").read_text(encoding="utf-8"))
# an instrument spelled entirely in lower case with the exchange's k prefix (`kpepe`) resolved live to kPEPE and printed
# PEPE: a roster lookup omega cannot make offline, kept out of the exact-prediction cases and pinned below
UNPREDICTED_INSTRUMENTS = {"kpepe"}
RENDERED = [c for p in (PROBE, PROBE_B) for c in p["renders"]
            if c["outputs"] and c["column"].get("instrument") not in UNPREDICTED_INSTRUMENTS]
REFUSED = {json.dumps(c["column"], sort_keys=True): c["refused"]
           for p in (PROBE, PROBE_B) for c in p["renders"] if not c["outputs"]}


@pytest.fixture(scope="module")
def contract():
    return load()


def _findings(col: dict, contract, severity="error") -> list:
    return [f for f in validate_column(Column.model_validate(col), path="c", contract=contract)
            if f.severity == severity]


def _refusal(col: dict) -> str:
    return REFUSED[json.dumps(col, sort_keys=True)]


# --- the roster ---------------------------------------------------------------------------------------------------
def test_the_roster_moved_as_recorded(contract):
    """302 metrics: 226 - 2 retired + 78 added (_moves_144.json), every added key a record of its own."""
    assert len(contract.metrics) == 302
    assert MOVES["contractVersion"] == "144.0.0" and len(MOVES["added"]) == 78
    assert set(MOVES["added"]) <= set(contract.metrics)
    assert set(MOVES["retired"]) == {"STOCH_RSI14", "BB_WIDTH"}
    assert set(MOVES["retired"]).isdisjoint(contract.metrics)
    for key in MOVES["added"]:
        assert (CONTRACT_DIR / "metrics" / f"{key}.json").is_file(), key
        assert MOVES["added_detail"][key]["code"] == contract.metric(key).code


def test_every_retirement_record_is_read(contract):
    """omega.contract reads every _moves_*.json: the three of 110 and the two of 144, each naming its record."""
    assert set(contract.retired_metrics) == {"MACD", "PPO", "KC_MID", "STOCH_RSI14", "BB_WIDTH"}
    assert contract.retired_metrics["STOCH_RSI14"]["record"] == "_moves_144.json"
    assert contract.retired_metrics["STOCH_RSI14"]["retiredAt"] == "144.0.0"
    assert contract.retired_metrics["MACD"]["record"] == "_moves_110.json"


@pytest.mark.parametrize("key,author", [("STOCH_RSI14", "STOCH_RSI_K"), ("BB_WIDTH", "BB_WIDTH_PCT")])
def test_a_retired_key_is_refused_naming_its_replacement(key, author, contract):
    col = {"metric": key, "transformId": "value", "timeframe": A}
    assert "VALIDATION_ERROR" in _refusal(col)          # refused live 2026-10-30
    [f] = _findings(col, contract)
    assert f.code == "METRIC_RETIRED" and author in f.message and "_moves_144.json" in f.message


def test_a_key_retired_between_the_two_extractions_was_never_in_a_corpus(contract):
    """SPOT_CLOSE_BYB (v136.1 -> v140) and BUY_PRES_BYB (v136.1 -> v139): not retired *from* OMEGA, so not in
    `retired_metrics`; validate reports an unknown metric, as the platform refuses it."""
    assert set(MOVES["retiredBetweenExtractions"]) == {"SPOT_CLOSE_BYB", "BUY_PRES_BYB"}
    assert "SPOT_CLOSE_BYB" not in contract.metrics and "SPOT_CLOSE_BYB" not in contract.retired_metrics
    assert "VALIDATION_ERROR" in _refusal({"metric": "SPOT_CLOSE_BYB", "transformId": "value", "timeframe": A})
    assert _findings({"metric": "SPOT_CLOSE_BYB", "transformId": "value", "timeframe": A}, contract)


def test_the_served_scalars_are_recorded(contract):
    """v138 `provenance` and v136 `rankScope` on every record; the report-scoped CROWD_UPBIAS is not exchangeWide."""
    assert all(m.provenance in ("tradingView", "battleGridDerived") for m in contract.metrics.values())
    assert contract.metric("RSI14").rank_scope == "exchangeWide"
    assert contract.metric("CROWD_UPBIAS").rank_scope not in (None, "exchangeWide")
    assert contract.metric("STOCH_RSI_K").provenance == "tradingView"
    assert contract.metric("CUM_VOLUME_DELTA").provenance == "tradingView"      # README v138: TradingView's CVD


# --- v142.3 relativeTo ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("case", RENDERED, ids=lambda c: json.dumps(c["column"], sort_keys=True))
def test_every_probed_header_is_predicted_exactly(case, contract):
    """relativeTo at each timeframe reference, with and without an instrument, in every measured instrument spelling,
    as a chain inner; scoped ranks; the v137 / v138 replacement metrics - rendered live, predicted offline."""
    col = Column.model_validate(case["column"])
    assert [o.header for o in outputs_for(col, contract)] == [o["header"] for o in case["outputs"]]


def test_the_instrument_token_is_the_roster_spelling():
    """Measured: ETH / eth -> ETH; omitted -> BTC; kPEPE / kpepe -> PEPE; xyz:BRENTOIL -> BRENTOIL; AAPL -> AAPL."""
    assert instrument_token(None) == "BTC"
    assert instrument_token("eth") == instrument_token("ETH") == "ETH"
    assert instrument_token("kPEPE") == "PEPE" and instrument_token("xyz:BRENTOIL") == "BRENTOIL"
    assert instrument_token("AAPL") == "AAPL" and instrument_token("KAITO") == "KAITO"


def test_an_all_lower_case_k_symbol_is_a_roster_lookup_omega_does_not_make():
    """Measured: `kpepe` rendered RSI14_PEPE_rel (the roster's kPEPE); omega predicts KPEPE. `kPEPE` is predicted."""
    [case] = [c for p in (PROBE, PROBE_B) for c in p["renders"] if c["column"].get("instrument") == "kpepe"]
    assert [o["header"] for o in case["outputs"]] == ["RSI14_PEPE_rel"]
    assert instrument_token("kpepe") == "KPEPE" != "PEPE"


def test_relative_to_is_in_every_vocabulary(contract):
    assert "relativeTo" in contract.transforms
    assert "relativeTo" in contract.metric("RSI14").transforms
    assert "relativeTo" in contract.metric("CLOSE").transforms


def test_a_comparable_unit_is_a_difference_and_a_price_a_ratio():
    """README v142.3, rendered: RSI14_ETH_rel in `points`, close_BTC_rel in `priceRatio`."""
    units = {}
    for c in PROBE["renders"]:
        # the rendered section's columns in order (the ticker column first, unit null), then the first row
        served = [r["unit"] for r in c.get("rendered", []) if "unit" in r]
        if c["outputs"] and served:
            units[c["outputs"][0]["header"]] = served[-1]
    assert units["RSI14_ETH_rel"] == "points"
    assert units["close_BTC_rel"] == "priceRatio"
    assert units["DIplus14_DIminus14_spread"] == "points"       # v137: a spread over a comparable unit


def test_inputs_on_relative_to_are_refused(contract):
    col = {"metric": "RSI14", "transformId": "relativeTo", "timeframe": A, "inputs": [{"metric": "RSI7"}]}
    assert "does not accept params.inputs" in _refusal(col)
    assert "OPERAND_REFUSED" in {f.code for f in _findings(col, contract)}


def test_instrument_off_relative_to_is_refused(contract):
    col = {"metric": "RSI14", "transformId": "value", "timeframe": A, "instrument": "ETH"}
    assert "does not accept params.instrument" in _refusal(col)
    assert "INSTRUMENT_UNDECLARED" in {f.code for f in _findings(col, contract)}


def test_relative_to_never_chains_rank(contract):
    col = {"metric": "CLOSE", "transformId": "relativeTo", "timeframe": A, "instrument": "ETH", "chainedTransformId": "rank"}
    assert "VALIDATION_ERROR" in _refusal(col)
    assert "REPORT_COLUMN_CHAIN_UNSUPPORTED" in {f.code for f in _findings(col, contract)}


def test_an_unknown_instrument_is_a_live_refusal_omega_cannot_predict(contract):
    """REPORT_COLUMN_INSTRUMENT_UNKNOWN is the platform's: omega holds no roster, so it passes the column."""
    col = {"metric": "RSI14", "transformId": "relativeTo", "timeframe": A, "instrument": "NOPE_NOT_A_COIN"}
    assert "VALIDATION_ERROR" in _refusal(col)
    assert not _findings(col, contract)


def test_the_instrument_shape_is_the_schema_s():
    Column(metric="RSI14", transformId="relativeTo", timeframe=A, instrument="xyz:BRENTOIL")
    with pytest.raises(ValidationError):
        Column(metric="RSI14", transformId="relativeTo", timeframe=A, instrument="")
    with pytest.raises(ValidationError):
        Column(metric="RSI14", transformId="relativeTo", timeframe=A, instrument="ETH USD")
    with pytest.raises(ValidationError):
        Column(metric="RSI14", transformId="relativeTo", timeframe=A, instrument="X" * 21)


# --- v136 rank scope ---------------------------------------------------------------------------------------------
def test_a_scope_lands_in_the_header_after_the_ordering():
    assert scope_token(Column(metric="RSI14", transformId="rank", timeframe=A, scope="crypto")) == "_crypto"
    assert scope_token(Column(metric="RSI14", transformId="rank", timeframe=A, scope="all")) == ""
    assert scope_token(Column(metric="RSI14", transformId="rank", timeframe=A)) == ""
    with pytest.raises(ValidationError):
        Column(metric="RSI14", transformId="rank", timeframe=A, scope="moon")


def test_scope_off_rank_is_refused(contract):
    col = {"metric": "RSI14", "transformId": "value", "timeframe": A, "scope": "crypto"}
    assert "does not accept params.scope" in _refusal(col)
    assert "SCOPE_UNDECLARED" in {f.code for f in _findings(col, contract)}


def test_scope_on_a_report_scoped_rank_is_refused(contract):
    col = {"metric": "CROWD_UPBIAS", "transformId": "rank", "timeframe": A, "scope": "crypto"}
    assert "takes no category scope" in _refusal(col)
    assert "REPORT_COLUMN_PAIR_UNSUPPORTED" in {f.code for f in _findings(col, contract)}


def test_scope_on_a_chained_rank_is_declared(contract):
    col = {"metric": "EMA5", "transformId": "spread", "chainedTransformId": "rank", "timeframe": A,
           "inputs": [{"metric": "EMA13"}], "ordering": "hi", "scope": "l1"}
    assert not _findings(col, contract)
    assert [o.header for o in outputs_for(Column.model_validate(col), contract)] == ["EMA5_EMA13_spread_rank_hi_l1"]


# --- a knob the transform does not declare (probe c) ---------------------------------------------------------
PROBE_C = json.loads((AUDIT / "relative_to_probe_144c_2026-10-30.json").read_text(encoding="utf-8"))
REFUSED_C = {json.dumps(c["column"], sort_keys=True): c["refused"] for c in PROBE_C["renders"] if not c["outputs"]}
RENDERED_C = {json.dumps(c["column"], sort_keys=True): [o["header"] for o in c["outputs"]]
              for c in PROBE_C["renders"] if c["outputs"]}


@pytest.mark.parametrize("col,code", [
    ({"metric": "RSI14", "transformId": "value", "timeframe": A, "window": 5}, "WINDOW_REFUSED"),
    ({"metric": "RSI14", "transformId": "rank", "timeframe": A, "window": 5}, "WINDOW_REFUSED"),
    ({"metric": "RSI14", "transformId": "trajectory", "timeframe": A, "window": 4, "offset": 2}, "OFFSET_REFUSED"),
    ({"metric": "RSI14", "transformId": "relativeTo", "timeframe": A, "instrument": "ETH", "offset": 2}, "OFFSET_REFUSED"),
    ({"metric": "RSI14", "transformId": "relativeTo", "timeframe": A, "instrument": "ETH", "window": 5}, "WINDOW_REFUSED"),
    ({"metric": "RSI14", "transformId": "rank", "timeframe": A, "ordering": "hi", "scope": "crypto", "bars": "closed"}, "BARS_REFUSED"),
], ids=lambda x: x if isinstance(x, str) else json.dumps(x, sort_keys=True))
def test_a_knob_the_transform_does_not_declare_is_refused(col, code, contract):
    """Until 144 omega warned IGNORED; measured 2026-10-30: "[column-grammar] transform 'X' does not accept params.Y"."""
    refusal = REFUSED_C.get(json.dumps(col, sort_keys=True)) or _refusal(col)
    assert "does not accept params." in refusal
    assert code in {f.code for f in _findings(col, contract)}


@pytest.mark.parametrize("col", [
    {"metric": "RSI14", "transformId": "value", "timeframe": A, "bars": "all"},
    {"metric": "RSI14", "transformId": "classifyZone", "timeframe": A, "bars": "closed"},
    {"metric": "RSI14", "transformId": "relativeTo", "timeframe": A, "instrument": "ETH", "bars": "closed"},
    {"metric": "RSI14", "transformId": "relativeTo", "timeframe": A, "instrument": "ETH", "chainedTransformId": "rollingMax",
     "window": 12, "bars": "closed"},
], ids=lambda x: json.dumps(x, sort_keys=True))
def test_bars_is_accepted_where_measured(col, contract):
    """`bars` renders on value (RSI14_dev), classifyZone and relativeTo: no finding at all, and the header predicted."""
    assert not validate_column(Column.model_validate(col), path="c", contract=contract)
    assert [o.header for o in outputs_for(Column.model_validate(col), contract)] == RENDERED_C[json.dumps(col, sort_keys=True)]


# --- v138 OBV ----------------------------------------------------------------------------------------------------
def test_obv_reads_only_its_changes(contract):
    """README v138: value, rank, spread and every transform outside the six are refused on OBV."""
    served = list(contract.metric("OBV").transforms)
    assert "value" not in served and "rank" not in served and "spread" not in served
    assert {"trajectory", "zscore", "stddev", "linregSlope", "pctl", "efficiency"} <= set(served)
    for tid in ("value", "rank", "zscore"):
        col = {"metric": "OBV", "transformId": tid, "timeframe": A}
        refused = json.dumps(col, sort_keys=True) in REFUSED
        assert refused == (tid in ("value", "rank")), tid
        assert bool(_findings(col, contract)) == refused, tid


# --- the condition vocabulary ------------------------------------------------------------------------------------
def test_the_condition_vocabulary_carries_the_new_knobs():
    v = json.loads((CONTRACT_DIR.parent / "derived" / "condition_vocabulary_108.json").read_text(encoding="utf-8"))
    col = v["reportColumn"]
    assert "relativeTo" in col["transformId"]["enum"] and "relativeTo" not in col["chainedTransformId"]["enum"]
    assert "instrument" in col["fields"] and "scope" in col["fields"]
    assert col["metric"]["count"] == 302
