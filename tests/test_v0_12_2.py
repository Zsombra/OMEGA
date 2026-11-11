"""OMEGA v0.12.2 (2026-11-11): the joint depth bound of a rolling-inner chain, and the chained touchAtr maximum.

Measured live at contract 161.0.0 on 2026-11-11, read-only (3 hints and 47 previews, 07:31:43Z - 07:50:11Z, then an
independent verification of 5 previews, 08:02:12Z - 08:03:29Z; data/audit/authoring_limits_161_2026-11-11.json):

(A) A chain whose inner is a rolling transform has ONE limit, a bar count, not one limit per window:

        need(inner, window) + need(outer, chainedWindow) - 1  <=  2436

    refused REPORT_COLUMN_DEPTH_EXCEEDED: "Column 'RSI14 x ema' chainedWindow 2364 reads 4774 bars for one value - at
    most 2436 of the 2500 readable bars, leaving the lookback budget 64; the largest chainedWindow that fits is 26."
    The served windowMaximum / innerWindowMaximum are that rule with the OTHER window at its default, so v0.12.1, which
    compared each window with its own served maximum and only warned, passed fifteen shapes the platform refuses.
(B) touchAtr on a CHAINED levelInteraction is bounded as on the transform itself (0.1 to 2 in steps of 0.1): v0.12.1
    read the maximum only where transformId was levelInteraction, so a chained 2.1 passed.

Nothing here calls the platform.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from omega.contract import CONTRACT_DIR, load
from omega.fanout import outputs_for
from omega.types import Column, CustomSection
from omega.validate import bars_needed, depth_budget, largest_window, validate_column, validate_section

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data" / "audit" / "authoring_limits_161_2026-11-11.json"
PROBE_161 = ROOT / "data" / "audit" / "authoring_probe_161_2026-11-09.json"
DEPTH, GRAMMAR = "REPORT_COLUMN_DEPTH_EXCEEDED", "REPORT_COLUMN_CONSTRUCTION_FAILED"
# The platform's authoring code -> the omega finding that refuses the same column. Every construction refusal of this
# probe is a touchAtr off its served range (the replay checks the message says so).
REFUSES = {DEPTH: "DEPTH_EXCEEDED", GRAMMAR: "PARAMETER_OUT_OF_RANGE"}
ANCHOR = {"rel": "anchor"}


@pytest.fixture(scope="module")
def contract():
    return load()


@pytest.fixture(scope="module")
def record():
    return json.loads(AUDIT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def probes(record):
    return record["probes"]


def _col(metric, inner, outer=None, *, timeframe=ANCHOR, **kw) -> Column:
    return Column(metric=metric, transformId=inner, chainedTransformId=outer, timeframe=timeframe, **kw)


def _found(column, contract) -> list[tuple[str, str, str]]:
    return [(f.severity, f.code, f.path) for f in validate_column(column, contract=contract)]


def _default(contract, tid) -> int:
    return contract.transforms[tid]["parameters"]["window"]["defaultValue"]


def _rolling_chains(m):
    """(inner, outer, served cell) for every chain of the metric whose outer window is `chainedWindow`."""
    return [(inner, outer, cell) for inner, t in m.transforms.items()
            for outer, cell in (t.get("chainedOuters") or {}).items() if cell.get("windowParameter") == "chainedWindow"]


# --- the record -------------------------------------------------------------------------------------------------------

def test_the_record_holds_every_call_of_the_run_and_of_its_verification(record, probes):
    n = record["counts"]
    assert (n["calls"], n["hints"], n["previews"]) == (55, 3, 52)
    assert n["run"] == {"previews": 47, "accepted": 23, "refused": 24}
    assert n["verification"] == {"previews": 5, "accepted": 1, "refused": 4}
    run_calls = [call for call in range(2, 51) if call not in (23, 24)]
    assert [p["call"] for p in probes] == run_calls + ["V1", "V2", "V3", "V4", "V5"]
    # the contract version was not read: 161.0.0 rests on the three live hints being the 2026-11-09 ones
    assert [(h["call"], h["metric"], h["identicalToHints20261109"]) for h in record["hints"]] == [
        (1, "RSI14", True), (23, "HIGH", True), (24, "BB_UPPER", True)]
    codes = [p["refusal"]["authoringCode"] for p in probes if not p["accepted"]]
    assert (codes.count(DEPTH), codes.count(GRAMMAR), len(codes)) == (19, 9, 28)
    assert {p["refusal"]["code"] for p in probes if not p["accepted"]} == {"VALIDATION_ERROR"}


# --- every answer, replayed through omega -----------------------------------------------------------------------------

def test_omega_agrees_with_every_answer_of_the_limit_probe(contract, probes):
    """52 previews at 161.0.0. Every accepted one validates with NO finding - neither an error nor a warning: inside the
    joint bound omega says nothing, whatever the served per-window maxima are - and renders exactly the headers
    omega.fanout predicts, in order. Every refused one is refused by omega with the one finding that maps to the
    platform's code, on the field the platform names (`chainedWindow` or `window` for a depth refusal)."""
    assert len(probes) == 52
    for p in probes:
        found, predicted = [], []
        for s in p["sections"]:
            section = CustomSection(title="t", benchmarkTicker=s["benchmarkTicker"], marketScope=s["marketScope"],
                                    columns=s["columns"])
            found += validate_section(section, contract=contract)
            predicted += [o.header for col in section.columns for o in outputs_for(col, contract)]
        if p["accepted"]:
            assert found == [], (p["probe"], found)
            assert predicted == p["render"]["headers"], p["probe"]
            continue
        refusal = p["refusal"]
        expected = [("error", REFUSES[refusal["authoringCode"]])]
        assert [(f.severity, f.code) for f in found] == expected, (p["probe"], found)
        if refusal["authoringCode"] == DEPTH:
            _, _, _, index, field = refusal["path"]
            assert found[0].path == f"section.columns[{index}].{field}", (p["probe"], found[0].path)
        else:
            assert "requires params.touchAtr from 0.1 to 2 in steps of 0.1" in refusal["message"], p["probe"]
            assert found[0].path == "section.columns[0].touchAtr", (p["probe"], found[0].path)


def test_the_bar_count_and_the_largest_fit_are_the_platforms_on_every_depth_refusal(contract, probes):
    """Each of the 19 depth refusals carries the platform's own arithmetic: details.receivedValue.need (its "reads N
    bars"), allowedDomain.maximum (its "the largest <field> that fits") and context depth 2500 / cap 64. bars_needed
    gives the same N on all 19 - rma at 1, 2, 10 and 100, rsi at 1 and 57, ema at 1 to 1394 as an inner and 500 to 702
    as an outer - and largest_window the same maximum, with the OTHER window held as sent, as the platform does; the
    finding states that maximum. V4 and V5 were predicted on disk before they were sent."""
    refused = [p for p in probes if not p["accepted"] and p["refusal"]["authoringCode"] == DEPTH]
    assert len(refused) == 19
    for p in refused:
        (col,) = p["sections"][0]["columns"]
        refusal = p["refusal"]
        field = refusal["path"][-1]
        budget = depth_budget(contract.metric(col["metric"]))
        assert budget == refusal["context"]["depth"] - refusal["context"]["cap"] == 2436
        need_in = bars_needed(col["transformId"], col["window"])
        need_out = bars_needed(col["chainedTransformId"], col["chainedWindow"])
        assert need_in + need_out - 1 == refusal["receivedValue"]["need"], p["probe"]
        fits = (largest_window(col["chainedTransformId"], budget + 1 - need_in) if field == "chainedWindow"
                else largest_window(col["transformId"], budget + 1 - need_out))
        assert fits == refusal["allowedDomain"]["maximum"], p["probe"]
        (finding,) = validate_column(Column.model_validate(col), contract=contract)
        assert f"the largest {field} that fits" in finding.message, finding.message
        assert f" is {fits} " in finding.message, finding.message
    by_probe = {p["probe"]: p["refusal"] for p in refused}
    v4, v5 = by_probe["V4.mid.rma100.ema500"], by_probe["V5.mid.rsi57.rma280"]
    assert (v4["receivedValue"]["need"], v4["allowedDomain"]["maximum"]) == (2518, 476)
    assert (v5["receivedValue"]["need"], v5["allowedDomain"]["maximum"]) == (2659, 251)


def test_the_hold_room_of_every_rendered_rolling_column_is_the_depth_less_its_bars(contract, probes):
    """The same arithmetic read off ACCEPTED columns. Each rendered header serves conditionHold.maxWindow, and on every
    rolling column of the probe it is the room of the metric's plain value column, plus the one bar that column reads,
    less the bars need() counts: 2500 - bars on CLOSE (plain `close` serves 2499), 2486 - bars on RSI14 (plain `RSI14`
    serves 2485: the metric's own 14 bars). So the fitted forms are pinned where the platform RENDERED, not only where
    it refused: ema at 1, 14, 20, 50, 100, 200, 280, 300, 400, 500, 650, 697, 703 and 704, rma at 10, and at {abs 4h},
    {abs 1d} and {rel lower}."""
    rendered = [(p["probe"], col, header, p["render"]["conditionHoldMaxWindow"][header])
                for p in probes if p["accepted"]
                for col, header in zip(p["sections"][0]["columns"], p["render"]["headers"], strict=True)]
    plain: dict[str, set] = {}
    for _, col, _, room in rendered:
        if col["transformId"] == "value":
            plain.setdefault(col["metric"], set()).add(room)
    assert plain == {"CLOSE": {2499}, "RSI14": {2485}}
    checked, ema_windows = 0, set()
    for probe, col, header, room in rendered:
        inner, outer = col["transformId"], col.get("chainedTransformId")
        if inner == "value" or col["metric"] not in plain:
            continue                           # the levelInteraction columns (group B) read no rolling depth
        bars = bars_needed(inner, col.get("window", _default(contract, inner)))
        if outer:
            bars += bars_needed(outer, col.get("chainedWindow", _default(contract, outer))) - 1
        (base,) = plain[col["metric"]]
        assert room == base + 1 - bars, (probe, header, room, bars)
        checked += 1
        ema_windows |= {col["window"]} if inner == "ema" else set()
    assert checked == 73
    assert ema_windows == {1, 14, 20, 50, 100, 200, 280, 300, 400, 500, 650, 697, 703, 704}


# --- need(): the bars one value reads ---------------------------------------------------------------------------------

def test_the_counted_forms_read_the_window_and_roc_and_pctl_one_bar_more():
    for tid in ("aggregate", "wma", "cci", "zscore", "stddev", "linregSlope", "rollingMin", "rollingMax"):
        assert [bars_needed(tid, w) for w in (1, 2, 24, 2436)] == [1, 2, 24, 2436], tid
    for tid in ("roc", "pctl"):
        assert [bars_needed(tid, w) for w in (1, 9, 2435)] == [2, 10, 2436], tid


def test_the_fitted_forms_at_the_measured_lengths():
    """ema / rma / rsi are FITTED. The smallest lengths were read off the refusal's own figure with chainedWindow 5000
    (calls 46 - 48: rma 1 reads 1 bar, rsi 1 reads 2, rma 2 reads 12); the rest are the "reads N bars" of calls 2 - 12,
    21 - 22, 49 - 50 and V4 / V5, less the other transform's share."""
    assert (bars_needed("rma", 1), bars_needed("rsi", 1), bars_needed("rma", 2)) == (1, 2, 12)
    assert [bars_needed("ema", w) for w in (1, 14, 20, 697, 698, 703, 704, 705, 1394)] == [
        7, 52, 73, 2411, 2415, 2432, 2435, 2439, 4819]
    assert (bars_needed("rma", 10), bars_needed("rma", 100), bars_needed("rsi", 57)) == (76, 788, 449)
    assert (bars_needed("ema", 500), bars_needed("ema", 702), bars_needed("rma", 280)) == (1731, 2429, 2211)


def test_the_fitted_forms_reproduce_the_one_point_the_catalogue_serves_for_each(contract):
    """The catalogue serves each smoother's settling rule in words and at one length: "needs at least the bars after
    which the average's seed weighs at most 0.1 % - 73 bars at length 20" (ema), "108 bars at length 14" (rma), "109
    bars at length 14" (rsi). The closed forms are fitted to the refusals; these three served numbers anchor them
    offline."""
    for tid, served, bars in (("ema", "73 bars at length 20", 73), ("rma", "108 bars at length 14", 108),
                              ("rsi", "109 bars at length 14", 109)):
        spec = contract.transforms[tid]["parameters"]["window"]
        assert served in spec["description"], tid
        assert bars_needed(tid, spec["defaultValue"]) == bars, tid


def test_a_transform_outside_the_need_table_has_no_bar_count():
    for tid in ("hma", "value", "spread", "distance", "trajectory", "efficiency", "maxShare", "levelInteraction"):
        assert bars_needed(tid, 20) is None and largest_window(tid, 2436) is None, tid


def test_largest_window_is_the_inverse_of_bars_needed():
    for tid in ("aggregate", "roc", "ema", "rma", "rsi"):
        for bars in (1, 2, 7, 12, 13, 52, 108, 109, 2411, 2436):
            w = largest_window(tid, bars)
            if w is None:
                assert bars_needed(tid, 1) > bars, (tid, bars)
            else:
                assert bars_needed(tid, w) <= bars < bars_needed(tid, w + 1), (tid, bars, w)
    assert largest_window("ema", 0) is None and largest_window("aggregate", -5) is None


# --- the budget comes from served data --------------------------------------------------------------------------------

def test_the_depth_budget_is_the_metrics_served_aggregate_maximum(contract, probes):
    """aggregate reads exactly its window in bars, so its served standalone maximum IS the bars one value may read. It
    is 2436 on every metric that serves a rolling-inner chain at 161.0.0, and equals the readable depth less the
    lookback budget every depth refusal states (context depth 2500, cap 64 = the served budgets.columnLookback). The
    corpus carries the maximum, not the 2500. This fails when the served number moves."""
    rolling = [m for m in contract.metrics.values() if _rolling_chains(m)]
    assert len(rolling) == 166
    for m in rolling:
        served = m.transforms["aggregate"]
        assert served["bounds"]["window"] == "depth", m.metric
        assert depth_budget(m) == served["maximums"]["window"] == 2436, m.metric
    contexts = {(p["refusal"]["context"]["depth"], p["refusal"]["context"]["cap"])
                for p in probes if not p["accepted"] and p["refusal"]["authoringCode"] == DEPTH}
    assert contexts == {(2500, 64)}
    assert contract.budgets["columnLookback"] == 64 and 2500 - contract.budgets["columnLookback"] == 2436
    # no depth-bound aggregate served -> no budget (the chain check then refuses the chain as unmeasured)
    assert depth_budget(contract.metric("REGIME_MOM")) is None


# --- the whole corpus: the joint rule IS the served arithmetic --------------------------------------------------------

def test_the_joint_rule_reproduces_every_served_rolling_chain_cell_and_depth_maximum(contract):
    """Offline, over every metric file: each served chainedOuters.<outer>.windowMaximum is the largest chainedWindow
    that fits with the INNER at its default window, each innerWindowMaximum the largest window that fits with the OUTER
    at its default, and each standalone depth maximum (maximums.window, bound `depth`) the largest window that fits
    alone. 15,106 chain cells (166 metrics x 7 inners x 13 outers) and 2,184 standalone maxima (168 metrics x 13
    transforms) at 161.0.0. A re-extraction at a later contract fails here if the platform's arithmetic moved (the
    counts are re-pinned with the roster). OBV alone serves depth maxima (four statistics) with no aggregate to take a
    budget from; it serves no rolling chain either, so nothing reads a budget on it."""
    cells = standalone = 0
    wrong, no_budget = [], []
    for m in contract.metrics.values():
        budget = depth_budget(m)
        for inner, outer, cell in _rolling_chains(m):
            assert budget is not None, (m.metric, inner, outer)
            need_in = bars_needed(inner, _default(contract, inner))
            need_out = bars_needed(outer, _default(contract, outer))
            assert need_in is not None and need_out is not None, (m.metric, inner, outer)     # nothing fails closed
            predicted = (largest_window(outer, budget + 1 - need_in), largest_window(inner, budget + 1 - need_out))
            cells += 1
            if predicted != (cell["windowMaximum"], cell["innerWindowMaximum"]):
                wrong.append((m.metric, inner, outer, (cell["windowMaximum"], cell["innerWindowMaximum"]), predicted))
        for tid, t in m.transforms.items():
            if (t.get("bounds") or {}).get("window") != "depth":
                continue
            assert bars_needed(tid, 1) is not None, (m.metric, tid)
            if budget is None:
                no_budget.append((m.metric, tid))
                continue
            standalone += 1
            if largest_window(tid, budget) != t["maximums"]["window"]:
                wrong.append((m.metric, tid, t["maximums"]["window"], largest_window(tid, budget)))
    assert wrong == []
    assert (cells, standalone) == (15106, 2184)
    assert no_budget == [("OBV", tid) for tid in ("zscore", "stddev", "linregSlope", "pctl")]


def test_the_inners_and_outers_of_the_corpus_are_the_need_table(contract):
    """Seven rolling inners and thirteen outers at 161.0.0, every one in the need table - so CHAIN_DEPTH_UNMEASURED
    fires on no served chain, only on a transform a later contract adds."""
    chains = [(inner, outer) for m in contract.metrics.values() for inner, outer, _ in _rolling_chains(m)]
    assert {i for i, _ in chains} == {"aggregate", "ema", "rma", "wma", "rsi", "cci", "roc"}
    assert {o for _, o in chains} == {"aggregate", "ema", "rma", "wma", "rsi", "cci", "roc", "zscore", "stddev",
                                      "linregSlope", "pctl", "rollingMin", "rollingMax"}
    # the outer's default and minimum are the catalogue's, as the chain-outer parameters serve them too
    for outer in {o for _, o in chains}:
        served = contract.chain_outer_parameters[outer]["window"]
        catalogue = contract.transforms[outer]["parameters"]["window"]
        assert (served["defaultValue"], served["minimum"]) == (catalogue["defaultValue"], catalogue["minimum"]), outer


# --- the measured boundaries ------------------------------------------------------------------------------------------

OK = None
CW = "chainedWindow"
# (metric, inner, window, outer, chainedWindow, timeframe, the field omega refuses on or OK): each row one platform
# answer, the call beside it
BOUNDARIES = [
    # RSI14 x ema -> aggregate (served windowMaximum 2364, innerWindowMaximum 697; ema alone 704)
    ("RSI14", "ema", 14, "aggregate", 2385, ANCHOR, OK),          # call 3, rendered RSI14_ema14_mean2385
    ("RSI14", "ema", 14, "aggregate", 2386, ANCHOR, CW),          # call 4, reads 2437
    ("RSI14", "ema", 14, "aggregate", 4728, ANCHOR, CW),          # call 2, reads 4779
    ("RSI14", "ema", 703, "aggregate", 5, ANCHOR, OK),            # call 6
    ("RSI14", "ema", 704, "aggregate", 5, ANCHOR, CW),            # call 7, reads 2439: chainedWindow 2 still fits
    ("RSI14", "ema", 1394, "aggregate", 5, ANCHOR, "window"),     # call 5, reads 4823: no chainedWindow fits
    ("RSI14", "ema", 20, "aggregate", 2364, ANCHOR, OK),          # call 8, the served maximum at the default inner
    ("RSI14", "ema", 20, "aggregate", 2365, ANCHOR, CW),          # call 9
    ("RSI14", "ema", 697, "aggregate", 24, ANCHOR, OK),           # call 10, the served inner maximum, default outer
    ("RSI14", "ema", 698, "aggregate", 24, ANCHOR, CW),           # call 11, reads 2438
    ("RSI14", "ema", 697, "aggregate", 2364, ANCHOR, CW),         # call 12, both served maxima together: 4774
    ("RSI14", "ema", 704, "aggregate", 2, ANCHOR, OK),            # call 38
    ("RSI14", "ema", 705, "aggregate", 1, ANCHOR, "window"),      # call 39, reads 2439 at the smallest outer
    ("RSI14", "ema", 1, "aggregate", 2430, ANCHOR, OK),           # call 40
    ("RSI14", "ema", 1, "aggregate", 2431, ANCHOR, CW),           # call 41
    # the other outers
    ("CLOSE", "aggregate", 10, "zscore", 2427, ANCHOR, OK),       # call 19 (served windowMaximum 2413)
    ("CLOSE", "aggregate", 10, "zscore", 2428, ANCHOR, CW),       # call 20
    ("RSI14", "rma", 10, "roc", 2360, ANCHOR, OK),                # call 21 (served 2328)
    ("RSI14", "rma", 10, "roc", 2361, ANCHOR, CW),                # call 22
    ("CLOSE", "aggregate", 10, "ema", 701, ANCHOR, OK),           # call 49 (served 697)
    ("CLOSE", "aggregate", 10, "ema", 702, ANCHOR, CW),           # call 50, reads 2438
    # the smallest lengths, and the two mid-range points predicted before they were sent
    ("RSI14", "rma", 1, "aggregate", 5000, ANCHOR, CW),           # call 46, reads 5000
    ("RSI14", "rsi", 1, "aggregate", 5000, ANCHOR, CW),           # call 47, reads 5001
    ("RSI14", "rma", 2, "aggregate", 5000, ANCHOR, CW),           # call 48, reads 5011
    ("RSI14", "rma", 100, "ema", 500, ANCHOR, CW),                # V4, reads 2518
    ("RSI14", "rsi", 57, "rma", 280, ANCHOR, CW),                 # V5, reads 2659
    # off the anchor: the same bound on a pinned and on a lower column timeframe
    ("RSI14", "ema", 14, "aggregate", 2385, {"abs": "4h"}, OK),   # V1, RSI14_4h_ema14_mean2385
    ("RSI14", "ema", 14, "aggregate", 2385, {"abs": "1d"}, OK),   # V1, RSI14_1d_ema14_mean2385
    ("RSI14", "ema", 14, "aggregate", 2385, {"rel": "lower"}, OK),   # V1, RSI14_ltf_ema14_mean2385
    ("CLOSE", "aggregate", 10, "zscore", 2427, {"abs": "4h"}, OK),   # V1, close_4h_mean10_z2427
    ("RSI14", "ema", 14, "aggregate", 2386, {"abs": "4h"}, CW),   # V2
    ("RSI14", "ema", 14, "aggregate", 2386, {"abs": "1d"}, CW),   # V3
    # the two 2026-11-09 cases, one past each served maximum, rendered: 2416 and 2419 bars
    ("RSI14", "ema", 14, "aggregate", 2365, ANCHOR, OK),          # N.chainedWindow.over
    ("RSI14", "ema", 698, "aggregate", 5, ANCHOR, OK),            # N.innerWindow.over
]


@pytest.mark.parametrize("metric,inner,window,outer,chained_window,timeframe,field", BOUNDARIES)
def test_the_joint_bound_at_the_measured_numbers(metric, inner, window, outer, chained_window, timeframe, field,
                                                 contract):
    column = _col(metric, inner, outer, timeframe=timeframe, window=window, chainedWindow=chained_window)
    expected = [] if field is OK else [("error", "DEPTH_EXCEEDED", f"column.{field}")]
    assert _found(column, contract) == expected


def test_every_boundary_row_is_a_recorded_answer(probes):
    """The table above is typed from the record; this keeps it honest: every row is a column some preview sent, with
    the answer the row states (the two 2026-11-09 rows are in authoring_probe_161_2026-11-09.json)."""
    def key(col):
        return (col["metric"], col["transformId"], col["window"], col["chainedTransformId"], col["chainedWindow"],
                json.dumps(col["timeframe"], sort_keys=True), col.get("bars"))

    earlier = [p for p in json.loads(PROBE_161.read_text(encoding="utf-8"))["probes"]
               if p["probe"] in ("N.chainedWindow.over", "N.innerWindow.over")]
    assert len(earlier) == 2
    sent = {key(col): p["accepted"] for p in [*probes, *earlier] for col in p["sections"][0]["columns"]
            if col.get("chainedWindow") is not None}
    for metric, inner, window, outer, chained_window, timeframe, field in BOUNDARIES:
        row = (metric, inner, window, outer, chained_window, json.dumps(timeframe, sort_keys=True), None)
        assert sent.get(row) == (field is OK), row


def test_an_omitted_window_is_judged_at_the_catalogue_default(contract):
    """N.no.window / N.no.chainedWindow (2026-11-09) rendered close_ema20_mean5 / close_ema20_mean24: an omitted window
    is the catalogue's default (ema 20, aggregate 24). The served maxima are the bound at exactly those defaults, so
    with one window omitted the other may reach its served maximum and no further (calls 8 - 11 sent the same four
    shapes with the default spelled)."""
    cell = contract.metric("RSI14").transforms["ema"]["chainedOuters"]["aggregate"]
    assert (cell["windowMaximum"], cell["innerWindowMaximum"]) == (2364, 697)
    assert (_default(contract, "ema"), _default(contract, "aggregate")) == (20, 24)
    refused = [("error", "DEPTH_EXCEEDED", "column.chainedWindow")]
    assert _found(_col("RSI14", "ema", "aggregate", chainedWindow=2364), contract) == []
    assert _found(_col("RSI14", "ema", "aggregate", chainedWindow=2365), contract) == refused
    assert _found(_col("RSI14", "ema", "aggregate", window=697), contract) == []
    assert _found(_col("RSI14", "ema", "aggregate", window=698), contract) == refused
    assert _found(_col("RSI14", "ema", "aggregate"), contract) == []
    assert _found(_col("CLOSE", "ema", "aggregate", chainedWindow=5), contract) == []        # N.no.window
    assert _found(_col("CLOSE", "ema", "aggregate", window=20), contract) == []             # N.no.chainedWindow


def test_the_finding_names_window_only_when_no_chained_window_fits(contract):
    """The platform names `chainedWindow` while some chainedWindow at or above the outer's minimum still fits beside the
    sent window (call 7: "the largest chainedWindow that fits is 2"), else `window`, with the largest window that fits
    beside the SENT chainedWindow (call 5: 703 beside chainedWindow 5; call 39: 704 beside 1)."""
    (f,) = validate_column(_col("RSI14", "ema", "aggregate", window=704, chainedWindow=5), contract=contract)
    assert f.path == "column.chainedWindow" and "reads 2439 bars" in f.message
    assert "the largest chainedWindow that fits beside window 704 is 2 " in f.message
    (f,) = validate_column(_col("RSI14", "ema", "aggregate", window=1394, chainedWindow=5), contract=contract)
    assert f.path == "column.window" and "the largest window that fits beside chainedWindow 5 is 703 " in f.message
    (f,) = validate_column(_col("RSI14", "ema", "aggregate", window=705, chainedWindow=1), contract=contract)
    assert f.path == "column.window" and "the largest window that fits beside chainedWindow 1 is 704 " in f.message
    # zscore's minimum is 2: ema 704 leaves 2 bars, which a zscore of 2 reads; an aggregate of 2436 leaves 1: none fits
    assert contract.transforms["zscore"]["parameters"]["window"]["minimum"] == 2
    assert _found(_col("CLOSE", "ema", "zscore", window=704, chainedWindow=3), contract) == [
        ("error", "DEPTH_EXCEEDED", "column.chainedWindow")]
    assert _found(_col("CLOSE", "aggregate", "zscore", window=2436, chainedWindow=2), contract) == [
        ("error", "DEPTH_EXCEEDED", "column.window")]


def test_a_window_beyond_any_float_is_refused_not_raised(contract):
    """The schema's own window maximum is 2^53 - 1 and omega's type has none. The fitted forms are never evaluated past
    the budget (every form reads at least its window), so an absurd length is a depth refusal, not an arithmetic
    error."""
    for tid in ("ema", "rma", "rsi", "aggregate"):
        assert _found(_col("RSI14", tid, "aggregate", window=10 ** 400, chainedWindow=5), contract) == [
            ("error", "DEPTH_EXCEEDED", "column.window")], tid
        assert _found(_col("RSI14", "aggregate", tid, window=5, chainedWindow=10 ** 400), contract) == [
            ("error", "DEPTH_EXCEEDED", "column.chainedWindow")], tid


# --- fail closed ------------------------------------------------------------------------------------------------------

UNMEASURED = [("error", "CHAIN_DEPTH_UNMEASURED", "column.chainedTransformId")]


def _with_transform(contract, metric, tid, entry, catalogue):
    """The contract with one more transform served on `metric` and catalogued - what a later contract's rolling
    transform looks like before omega has measured it."""
    m = contract.metric(metric)
    return dataclasses.replace(
        contract, transforms={**contract.transforms, tid: catalogue},
        metrics={**contract.metrics, metric: dataclasses.replace(m, transforms={**m.transforms, tid: entry})})


def test_an_inner_the_need_table_does_not_know_is_refused_as_unmeasured(contract):
    ema = contract.metric("RSI14").transforms["ema"]
    c2 = _with_transform(contract, "RSI14", "hma", {**ema, "id": "hma"}, contract.transforms["ema"])
    column = _col("RSI14", "hma", "aggregate", window=10, chainedWindow=5)
    assert _found(column, c2) == UNMEASURED
    (f,) = validate_column(column, contract=c2)
    assert "'hma'" in f.message and "UNMEASURED" in f.message


def test_an_outer_the_need_table_does_not_know_is_refused_as_unmeasured(contract):
    m = contract.metric("RSI14")
    ema = m.transforms["ema"]
    served = {**ema, "chainSuccessors": [*ema["chainSuccessors"], "hma"],
              "chainedOuters": {**ema["chainedOuters"], "hma": dict(ema["chainedOuters"]["ema"])}}
    c2 = _with_transform(contract, "RSI14", "ema", served, contract.transforms["ema"])
    c2 = dataclasses.replace(c2, transforms={**c2.transforms, "hma": contract.transforms["ema"]})
    assert _found(_col("RSI14", "ema", "hma", window=10, chainedWindow=5), c2) == UNMEASURED
    # the chains the need table knows are untouched on the same doctored metric
    assert _found(_col("RSI14", "ema", "aggregate", window=14, chainedWindow=2385), c2) == []


def test_a_rolling_chain_on_a_metric_with_no_served_budget_is_refused_as_unmeasured(contract):
    m = contract.metric("RSI14")
    aggregate = {k: v for k, v in m.transforms["aggregate"].items() if k not in ("maximums", "bounds")}
    c2 = dataclasses.replace(contract, metrics={**contract.metrics, "RSI14": dataclasses.replace(
        m, transforms={**m.transforms, "aggregate": aggregate})})
    assert _found(_col("RSI14", "ema", "aggregate", window=14, chainedWindow=5), c2) == UNMEASURED


def test_an_omitted_window_with_no_catalogued_default_is_refused_as_unmeasured(contract):
    aggregate = contract.transforms["aggregate"]
    window = {k: v for k, v in aggregate["parameters"]["window"].items() if k != "defaultValue"}
    c2 = dataclasses.replace(contract, transforms={**contract.transforms, "aggregate": {
        **aggregate, "parameters": {**aggregate["parameters"], "window": window}}})
    assert _found(_col("RSI14", "ema", "aggregate", window=14), c2) == UNMEASURED
    assert _found(_col("RSI14", "ema", "aggregate", window=14, chainedWindow=5), c2) == []    # spelled: no default read


# --- touchAtr on a chained levelInteraction ---------------------------------------------------------------------------

def test_the_contract_carries_the_served_chain_outer_parameters(contract):
    """data/contract/transforms/_chain_outer_parameters.json (get_metric_construction_hints chainOuterParameters, served
    identically on every metric and rewritten by scripts/refresh_metric_contracts.py) was on disk and unread. It is the
    only served source of a CHAINED levelInteraction's touchAtr maximum: the catalogue carries no maximum, and HIGH /
    LOW serve no levelInteraction entry of their own."""
    on_disk = json.loads((CONTRACT_DIR / "transforms" / "_chain_outer_parameters.json")
                         .read_text(encoding="utf-8"))["chainOuterParameters"]
    assert contract.chain_outer_parameters == on_disk
    touch = contract.chain_outer_parameters["levelInteraction"]["touchAtr"]
    assert (touch["minimum"], touch["maximum"], touch["step"], touch["bound"]) == (0.1, 2, 0.1, "range")
    assert "maximum" not in contract.transforms["levelInteraction"]["parameters"]["touchAtr"]
    assert "levelInteraction" not in contract.metric("HIGH").transforms
    assert "levelInteraction" not in contract.metric("LOW").transforms


@pytest.mark.parametrize("metric,inner,touch,refused", [
    ("HIGH", "rollingMax", 0.5, False),      # call 25, high_o1_max20_lvl_a0.5
    ("HIGH", "rollingMax", 2, False),        # call 26, high_o1_max20_lvl_a2
    ("HIGH", "rollingMax", 2.1, True),       # call 27
    ("HIGH", "rollingMax", 100, True),       # call 28
    ("LOW", "rollingMin", 2.1, True),        # call 37
    ("LOW", "rollingMin", 2, False),         # the served maximum on the other rolling extreme
])
def test_the_chained_touch_atr_maximum(metric, inner, touch, refused, contract):
    """"[column-grammar] transform 'levelInteraction' requires params.touchAtr from 0.1 to 2 in steps of 0.1 (got 2.1)",
    REPORT_COLUMN_CONSTRUCTION_FAILED, on HIGH x rollingMax (20, offset 1) -> levelInteraction and on LOW x
    rollingMin."""
    column = _col(metric, inner, "levelInteraction", window=20, offset=1, touchAtr=touch)
    assert _found(column, contract) == ([("error", "PARAMETER_OUT_OF_RANGE", "column.touchAtr")] if refused else [])
    if refused:
        (f,) = validate_column(column, contract=contract)
        assert f.message == (f"params.touchAtr {float(touch)} on {metric} x {inner} -> levelInteraction is over the "
                             f"served maximum 2 (chainOuterParameters.levelInteraction.touchAtr.maximum)")


def test_the_unchained_touch_atr_maximum_is_unchanged(contract):
    """BB_UPPER x levelInteraction: 0.5 and 2 rendered, 2.1 and 100 refused (calls 29 - 32) - the metric's own served
    maximum, the finding as v0.12.1 worded it."""
    for touch in (0.5, 2):
        assert _found(_col("BB_UPPER", "levelInteraction", touchAtr=touch), contract) == []
    for touch in (2.1, 100):
        (f,) = validate_column(_col("BB_UPPER", "levelInteraction", touchAtr=touch), contract=contract)
        assert (f.severity, f.code, f.path) == ("error", "PARAMETER_OUT_OF_RANGE", "column.touchAtr")
        assert f.message == f"params.touchAtr {float(touch)} on BB_UPPER is over the served maximum 2"


@pytest.mark.parametrize("column", [
    _col("HIGH", "rollingMax", "levelInteraction", window=20, offset=1, touchAtr=0.05),     # call 33
    _col("HIGH", "rollingMax", "levelInteraction", window=20, offset=1, touchAtr=0.15),     # call 34
    _col("HIGH", "rollingMax", "levelInteraction", window=20, offset=1, touchAtr=0),        # call 35
    _col("BB_UPPER", "levelInteraction", touchAtr=0.15),                                    # call 36
])
def test_the_touch_atr_minimum_and_step_are_unchanged(column, contract):
    (f,) = validate_column(column, contract=contract)
    assert (f.severity, f.code, f.path) == ("error", "PARAMETER_OUT_OF_RANGE", "column.touchAtr")
    assert f.message == f"levelInteraction requires params.touchAtr >= 0.1 in steps of 0.1 (got {column.touchAtr!r})"
