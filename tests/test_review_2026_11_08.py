"""The first review pass over the v0.12 branch (2026-11-08), the omega model findings. Each test failed at e847fd1.

F1  a chained window above 64 was refused: the window check read the INNER transform's maximum (distance, spread and
    relativeTo serve none, so it fell back to the 64-bar budget) while the window belongs to the outer, whose served
    chainedOuters.<outer>.windowMaximum is 269 / 118 / 936 - the platform's own "the largest window that fits is 269" on
    HIGH x distance -> ema (data/audit/authoring_probe_149_2026-11-07.json, A.HIGH.distance.chain.ema.w270).
F2  a knob float carrying representation noise (0.1 * 3) was accepted, sent as 0.30000000000000004 and predicted as
    `sd0.3`; 2.0000000001 counted as off its default and printed `sd2`, which omega's own rule says never renders.
F3  a served knob with no measured spelling, at its default beside an off-default sibling, was silently left out of a
    SET header instead of raising.
F5  a range knob served without a step (or a bound) made the out-of-range message raise TypeError.
Nothing here calls the platform.
"""
from __future__ import annotations

import dataclasses

import pytest

from omega.contract import load
from omega.fanout import knob_token, outputs_for
from omega.types import Column
from omega.validate import validate_column


@pytest.fixture(scope="module")
def contract():
    return load()


def _errors(column, contract) -> list[str]:
    return [f.code for f in validate_column(column, contract=contract) if f.severity == "error"]


# --- F1 ---------------------------------------------------------------------------------------------------------------
# 161.0.0 (2026-11-09): the served maxima moved with the readable depth (1000 -> 2500 bars): the chained ema / rma / wma
# maxima were 269 / 118 / 936 at 149.1.0 and are 704 / 308 / 2436 now, and CLOSE no longer serves `distance` (so HIGH, which
# does, stands in for it). The intent of F1 is that omega follows the OUTER's SERVED maximum, so each case reads that
# maximum from the corpus (chainedOuters.<outer>.windowMaximum) rather than hard-coding a number that moves with the depth.
def _outer_max(contract, metric, inner, outer) -> int:
    return contract.metric(metric).transforms[inner]["chainedOuters"][outer]["windowMaximum"]


@pytest.mark.parametrize("metric,inner,outer,window,extra", [
    ("HIGH", "distance", "ema", 65, {}),                     # above the 64-bar budget the inner's fallback used to apply
    ("HIGH", "distance", "ema", "max", {}),                  # the served largest that fits (269 at 149.1.0, 704 at 161)
    ("HIGH", "distance", "rma", "max", {}),                  # 118 at 149.1.0, 308 at 161
    ("HIGH", "distance", "wma", "max", {}),                  # 936 at 149.1.0, 2436 at 161
    ("HIGH", "distance", "zscore", 100, {}),
    ("RSI14", "relativeTo", "ema", 100, {}),
    ("RSI14", "spread", "ema", 100, {"inputs": [{"metric": "RSI7"}]}),
])
def test_a_chained_window_within_the_outers_served_maximum_is_accepted(metric, inner, outer, window, extra, contract):
    if window == "max":
        window = _outer_max(contract, metric, inner, outer)
        assert window > 64            # the point of F1: a served maximum above the 64-bar fallback is accepted
    column = Column(metric=metric, transformId=inner, chainedTransformId=outer, window=window,
                    timeframe={"rel": "anchor"}, **extra)
    assert _errors(column, contract) == []


@pytest.mark.parametrize("outer", ["ema", "rma", "wma"])
def test_a_chained_window_over_the_outers_served_maximum_is_depth_only(outer, contract):
    """A.HIGH.distance.chain.ema.w270, J.CLOSE.distance.chain.rma.w119 / .wma.w937 at 149.1.0 (and, at 161.0.0,
    O.HIGH.distance.ema.over at 705): REPORT_COLUMN_DEPTH_EXCEEDED alone (omega also said LOOKBACK_EXCEEDED, from the
    inner's fallback). The window is the served maximum + 1 of the corpus (270 / 119 / 937 at 149.1.0)."""
    window = _outer_max(contract, "HIGH", "distance", outer) + 1
    column = Column(metric="HIGH", transformId="distance", chainedTransformId=outer, window=window,
                    timeframe={"rel": "anchor"})
    assert _errors(column, contract) == ["DEPTH_EXCEEDED"]


def test_a_plain_series_window_still_reads_its_own_maximum(contract):
    # 270 at 149.1.0 was one past ema's served maximum; the maximum is 704 at 161.0.0 and is read, not hard-coded
    maximum = contract.metric("RSI14").transforms["ema"]["maximums"]["window"]
    assert _errors(Column(metric="RSI14", transformId="ema", window=maximum + 1, timeframe={"rel": "anchor"}),
                   contract) == ["DEPTH_EXCEEDED"]
    assert _errors(Column(metric="RSI14", transformId="ema", window=maximum, timeframe={"rel": "anchor"}), contract) == []
    assert _errors(Column(metric="RSI14", transformId="zscore", window=100, timeframe={"rel": "anchor"}), contract) == []


# --- F2 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("value", [0.1 * 3, 0.1 * 7, 2.0000000001])
def test_a_noisy_knob_float_is_refused_not_predicted(value, contract):
    column = Column(metric="BB_UPPER", transformId="value", timeframe={"rel": "anchor"}, stdDev=value)
    assert _errors(column, contract) == ["PARAMETER_OUT_OF_RANGE"]


@pytest.mark.parametrize("value,header", [(0.3, "bbUpper20_p20sd0.3"), (2.5, "bbUpper20_p20sd2.5"),
                                          (2.0, "bbUpper20"), (5, "bbUpper20_p20sd5")])
def test_an_exact_knob_float_on_the_grid_is_accepted(value, header, contract):
    column = Column(metric="BB_UPPER", transformId="value", timeframe={"rel": "anchor"}, stdDev=value)
    assert _errors(column, contract) == []
    assert [o.header for o in outputs_for(column, contract)] == [header]


# --- F3 ---------------------------------------------------------------------------------------------------------------
def _with_unspelled_knob(contract):
    m = contract.metric("BB_UPPER")
    params = dict(m.parameters)
    params["smoothing"] = {"defaultValue": 1, "minimum": 1, "maximum": 10, "bound": "depth"}
    return dataclasses.replace(contract, metrics={**contract.metrics, "BB_UPPER": dataclasses.replace(m, parameters=params)})


def test_an_unspelled_served_knob_raises_once_any_knob_is_off(contract):
    c2 = _with_unspelled_knob(contract)
    with pytest.raises(ValueError, match="never rendered"):
        knob_token(Column(metric="BB_UPPER", transformId="value", timeframe={"rel": "anchor"}, stdDev=2.5), c2)


def test_an_unspelled_served_knob_with_every_knob_at_default_spells_nothing(contract):
    c2 = _with_unspelled_knob(contract)
    assert knob_token(Column(metric="BB_UPPER", transformId="value", timeframe={"rel": "anchor"}), c2) == ""


# --- F5 ---------------------------------------------------------------------------------------------------------------
def test_a_range_knob_served_without_a_step_or_bound_gives_a_finding_not_a_crash(contract):
    m = contract.metric("BB_UPPER")
    params = dict(m.parameters)
    params["stdDev"] = {**params["stdDev"], "step": None, "maximum": None}
    c2 = dataclasses.replace(contract, metrics={**contract.metrics, "BB_UPPER": dataclasses.replace(m, parameters=params)})
    column = Column(metric="BB_UPPER", transformId="value", timeframe={"rel": "anchor"}, stdDev=0.05)
    [finding] = [f for f in validate_column(column, contract=c2) if f.severity == "error"]
    assert finding.code == "PARAMETER_OUT_OF_RANGE" and ">= 0.1" in finding.message


# --- F4 ---------------------------------------------------------------------------------------------------------------
import json
from pathlib import Path

from omega.fanout import KNOB_SPELLING_RENDERED
from omega.types import KNOBS

AUDIT = Path(__file__).resolve().parents[1] / "data" / "audit"


def _j(name: str) -> dict:
    return json.loads((AUDIT / name).read_text(encoding="utf-8"))


def test_the_second_knob_probe_rendered_the_27_cells_as_predicted(contract):
    """2026-11-08 04:46Z, one preview at 149.1.0 (scripts/probe_knob_spelling_149.py, KNOB_COLUMNS): every served
    (metric, knob) the 11-07 renders never showed off its default, MACD_SIGNAL and PPO_HIST among them."""
    rec = _j("knob_spelling_probe_149_2026-11-08.json")
    assert rec["contractVersion"] == rec["versionAtEnd"] == "149.1.0" and rec["refused"] == 0 and rec["agree"] is True
    sent = [col for e in rec["entries"] for col in e["columns"]]
    assert len(sent) == 27
    assert [h for e in rec["entries"] for h in e["rendered"]] == \
        [o.header for col in sent for o in outputs_for(Column(**col), contract)]
    assert {"MACDsig_fast12slow26sig5", "PPOhist_fast12slow21sig9", "stochRsiD_rsi21_p14s3d3"} <= \
        {h for e in rec["entries"] for h in e["rendered"]}


def test_knob_spelling_rendered_is_what_the_three_records_rendered(contract):
    rendered: dict[str, set] = {}

    def take(col):
        m = contract.metric(col["metric"])
        for k in KNOBS:
            if k in col and k in m.parameters and col[k] != m.parameters[k].get("defaultValue"):
                rendered.setdefault(col["metric"], set()).add(k)

    for p in _j("authoring_probe_149_2026-11-07.json")["probes"]:
        if p["accepted"]:
            for s in p["sections"]:
                for col in s["columns"]:
                    take(col)
    for date in ("2026-11-07", "2026-11-08"):
        for e in _j(f"knob_spelling_probe_149_{date}.json")["entries"]:
            for col in e["columns"]:
                take(col)
    # 161.0.0 (2026-11-09): a fourth record - the authoring probe at 161.0.0 rendered the 25 cells 161 added on ten metrics
    # (ADX / ATR / DI_PLUS / DI_MINUS / VWMA20 `period`, the four knobs on each of the five ICHI_*; _moves_161.json
    # parametersAdded): 106 served cells on 46 metrics, all rendered
    for p in _j("authoring_probe_161_2026-11-09.json")["probes"]:
        if p["accepted"]:
            for s in p["sections"]:
                for col in s["columns"]:
                    take(col)
    assert {m: frozenset(v) for m, v in rendered.items()} == KNOB_SPELLING_RENDERED
    # and that is every served cell: 81 of 81 on 36 metrics at 149.1.0
    served = {n: frozenset(m.parameters) for n, m in contract.metrics.items() if m.parameters}
    assert served == KNOB_SPELLING_RENDERED and sum(map(len, served.values())) == 106


def test_a_known_knob_name_on_a_metric_never_rendered_with_it_raises(contract):
    """`period` is spelled `p` on twelve metrics; a thirteenth serving it is not spelled by analogy."""
    m = contract.metric("RSI14")
    c2 = dataclasses.replace(contract, metrics={**contract.metrics, "RSI14": dataclasses.replace(
        m, parameters={"period": {"defaultValue": 14, "minimum": 2, "maximum": 100, "bound": "depth"}})})
    with pytest.raises(ValueError, match="never rendered"):
        knob_token(Column(metric="RSI14", transformId="value", timeframe={"rel": "anchor"}, period=21), c2)
    assert knob_token(Column(metric="RSI14", transformId="value", timeframe={"rel": "anchor"}), c2) == ""


# --- pass 2, finding 1: the spelling guard is a refusal in the validator, not an exception --------------------------
from pydantic import ValidationError

from omega import fanout
from omega.types import CustomSection
from omega.validate import validate_section


def test_a_never_rendered_knob_cell_is_refused_by_the_validator_not_raised(contract, monkeypatch):
    """MACD_SIGNAL as it stood before the 2026-11-08 render: validate_column said nothing and validate_section raised
    ValueError while predicting headers. Now both refuse it KNOB_SPELLING_UNMEASURED and nothing raises."""
    monkeypatch.delitem(fanout.KNOB_SPELLING_RENDERED, "MACD_SIGNAL")
    column = Column(metric="MACD_SIGNAL", transformId="value", timeframe={"rel": "anchor"}, fast=8)
    assert _errors(column, contract) == ["KNOB_SPELLING_UNMEASURED"]
    section = CustomSection(title="t", columns=[column, Column(metric="RSI14", transformId="value",
                                                               timeframe={"rel": "anchor"})])
    assert [f.code for f in validate_section(section, contract=contract) if f.severity == "error"] == \
        ["KNOB_SPELLING_UNMEASURED"]
    # at its defaults it spells nothing, so nothing is unmeasured
    assert _errors(Column(metric="MACD_SIGNAL", transformId="value", timeframe={"rel": "anchor"}, fast=12),
                   contract) == []


def test_an_unspelled_served_knob_is_refused_by_the_validator_not_raised(contract):
    c2 = _with_unspelled_knob(contract)
    column = Column(metric="BB_UPPER", transformId="value", timeframe={"rel": "anchor"}, stdDev=2.5)
    assert _errors(column, c2) == ["KNOB_SPELLING_UNMEASURED"]
    section = CustomSection(title="t", columns=[column])
    assert [f.code for f in validate_section(section, contract=c2) if f.severity == "error"] == \
        ["KNOB_SPELLING_UNMEASURED"]


def test_every_rendered_cell_validates_without_the_spelling_finding(contract):
    for metric, knobs in fanout.KNOB_SPELLING_RENDERED.items():
        params = contract.metric(metric).parameters
        for k in knobs:
            p = params[k]
            if p.get("bound") == "flag":
                value = not p.get("defaultValue")
            elif p.get("bound") == "range":
                value = round(p["defaultValue"] + p["step"], 6) if p["defaultValue"] + p["step"] <= p["maximum"] \
                    else round(p["defaultValue"] - p["step"], 6)
            else:
                value = p["defaultValue"] + 1
            column = Column(metric=metric, transformId="value", timeframe={"rel": "anchor"}, **{k: value})
            assert "KNOB_SPELLING_UNMEASURED" not in _errors(column, contract), (metric, k)


# --- pass 2, finding 10: NaN / inf ----------------------------------------------------------------------------------
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_knob_is_refused_by_the_model(value):
    with pytest.raises(ValidationError):
        Column(metric="BB_UPPER", transformId="value", timeframe={"rel": "anchor"}, stdDev=value)


# --- pass-2 re-review: every header-predicting caller skips an unmeasured knob header instead of raising -----------
def test_cost_report_headers_and_emit_skip_an_unmeasured_knob_column(contract, monkeypatch, tmp_path):
    from omega.conditions import report_headers
    from omega.emit import RefusedToEmit, emit
    from omega.fanout import cost_report
    from omega.types import Report

    monkeypatch.delitem(fanout.KNOB_SPELLING_RENDERED, "MACD_SIGNAL")
    report = Report(sections=[CustomSection(title="t", columns=[
        Column(metric="MACD_SIGNAL", transformId="value", timeframe={"rel": "anchor"}, fast=8),
        Column(metric="RSI14", transformId="value", timeframe={"rel": "anchor"})])])
    assert cost_report(report, contract).headers == 1
    assert "RSI14" in report_headers(report) and not any(h.startswith("MACDsig") for h in report_headers(report))
    with pytest.raises(RefusedToEmit, match="never rendered"):
        emit(report, "t", out_dir=tmp_path)
