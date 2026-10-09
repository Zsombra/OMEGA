"""Membership (IN_REPORT) is not 'all scoring inputs rendered'. Since 2026-10-06 the map is
the platform's own: a draft with all 84 signals on and a report showing only Price Action
listed, in `diagnostics.mismatches` ACTIVE_SIGNAL_DATA_NOT_IN_REPORT, the (metric, rung)
data each of 83 signals scores on (data/derived/signal_data_rungs_91.json). It replaces
the 2026-08-28 partial map (12 of 84). An anchor rung is satisfied by a rel:anchor column
whose metric - or a spread input - is the metric, whatever the transform (measured by M1);
a lower or signalHigher rung is UNMEASURED against any report column, so it always warns."""
import json
from pathlib import Path

from omega.generate import PRESETS, plan
from omega.membership import scoring_gaps
from omega.types import Column, CustomSection, Report, Rule

ROOT = Path(__file__).resolve().parents[1]
M1 = json.loads((ROOT / "data/contract/stage_strategy_draft/m1_m3_live_20261006T055532Z.json")
                .read_text(encoding="utf-8"))


def _platform_mismatches() -> dict[str, set[tuple[str, str]]]:
    """What BattleGrid itself said about the trend-continuation create axes (M1, 05:55Z)."""
    read = next(c for c in M1["calls"] if c["label"] == "M1 read after OMEGA axes")["answer"]
    out: dict[str, set[tuple[str, str]]] = {}
    for m in read["diagnostics"]["mismatches"]:
        if m["code"] == "ACTIVE_SIGNAL_DATA_NOT_IN_REPORT":
            out[m["signalId"]] = {(d["metric"], d["rung"]) for d in m["data"]}
    return out


def _report(*cols) -> Report:
    return Report(anchor="1h", sections=[CustomSection(
        title="t", benchmarkTicker=None, columns=[Column.model_validate(c) for c in cols])])


def test_trend_continuation_reproduces_the_platforms_own_mismatches_exactly():
    """The ground truth: the signals OMEGA flags, and the data it says each is missing, are
    exactly what BattleGrid's diagnostics listed for the same axes."""
    p = plan(PRESETS["trend-continuation"])
    gaps = scoring_gaps(p.report, p.rules)
    assert all(f.code == "SCORING_INPUT_NOT_RENDERED" and f.severity == "warning" for f in gaps)
    predicted = {f.path.removeprefix("rules."): f.missing for f in gaps}
    assert predicted == _platform_mismatches()


def test_every_preset_now_warns_from_the_measured_map_not_silence():
    """Before the probe, a signal outside the 12 measured was silent. Now every weighted
    signal is judged; each preset's warnings name only data the map lists for that signal."""
    from omega.membership import _signal_data
    for name in PRESETS:
        p = plan(PRESETS[name])
        for f in scoring_gaps(p.report, p.rules):
            sid = f.path.removeprefix("rules.")
            assert f.missing <= {(d["metric"], d["rung"]) for d in _signal_data()[sid]}, (name, sid)


def test_an_anchor_rung_is_satisfied_by_any_transform_and_by_a_spread_input():
    """ma_ema_aligned_bull scores on EMA5, EMA13 and EMA20 @ anchor (measured). An EMA5-EMA13
    spread plus an EMA20 distance shows all three (M1: the spread's input satisfied EMA13)."""
    rules = [Rule(signalId="ma_ema_aligned_bull", allocation=2, required=False)]
    full = _report({"metric": "EMA5", "transformId": "spread", "timeframe": {"rel": "anchor"},
                    "inputs": [{"metric": "EMA13"}]},
                   {"metric": "EMA20", "transformId": "distance", "timeframe": {"rel": "anchor"}})
    assert not scoring_gaps(full, rules)
    partial = _report({"metric": "EMA20", "transformId": "value", "timeframe": {"rel": "anchor"}})
    [gap] = scoring_gaps(partial, rules)
    assert gap.missing == {("EMA5", "anchor"), ("EMA13", "anchor")}


def test_a_lower_or_higher_rung_always_warns_because_it_is_unmeasured():
    """No report column at a lower or higher timeframe has been staged against these rungs,
    so OMEGA does not assume rel:lower / rel:regime satisfies them: it warns and says why."""
    rules = [Rule(signalId="htf_ma_aligned_bull", allocation=1, required=False),
             Rule(signalId="ltf_ma_aligned_bull", allocation=1, required=False)]
    report = _report({"metric": "MA_ALIGN", "transformId": "value", "timeframe": {"rel": "regime"}},
                     {"metric": "MA_ALIGN", "transformId": "value", "timeframe": {"rel": "lower"}})
    gaps = {f.path: f for f in scoring_gaps(report, rules)}
    assert set(gaps) == {"rules.htf_ma_aligned_bull", "rules.ltf_ma_aligned_bull"}
    assert all("UNMEASURED" in f.message for f in gaps.values())


def test_unweighted_and_unmapped_signals_stay_silent():
    rules = [Rule(signalId="htf_ma_aligned_bull", allocation=0, required=False),
             Rule(signalId="comparison_btc_decorrelation", allocation=2, required=False)]
    assert not scoring_gaps(_report({"metric": "CLOSE", "transformId": "value",
                                     "timeframe": {"rel": "anchor"}}), rules)
