"""Membership (IN_REPORT) is not 'all scoring inputs rendered' - measured 2026-08-28
via the 12 non-blocking compile advisories. This warns on the MEASURED pairs only;
the other 72 signals are unmeasured, and unmeasured means silent, not satisfied."""
from omega.generate import PRESETS, plan
from omega.membership import scoring_gaps


def test_trend_continuation_reproduces_the_12_measured_advisories():
    p = plan(PRESETS["trend-continuation"])
    gaps = scoring_gaps(p.report, p.rules)
    assert len(gaps) == 12
    assert all(f.code == "SCORING_INPUT_NOT_RENDERED" and f.severity == "warning"
               for f in gaps)


def test_presets_without_measured_signals_stay_silent():
    """mean-reversion allocates none of the 12 measured signals (its htf/ltf_rsi rungs
    are UNMEASURED, and unmeasured means silent) - so zero warnings, not guessed ones."""
    p = plan(PRESETS["mean-reversion"])
    assert not scoring_gaps(p.report, p.rules)


def test_an_anchor_column_satisfies_an_anchor_rung():
    """ma_ema_aligned_bull wants EMA20@anchor (measured). A report that actually
    renders EMA20 at rel:anchor must not warn for it."""
    from omega.types import Column, CustomSection, Report, Rule
    report = Report(anchor="1h", sections=[CustomSection(
        title="t", benchmarkTicker=None,
        columns=[Column.model_validate({"metric": "EMA20", "transformId": "value",
                                        "timeframe": {"rel": "anchor"}})])])
    rules = [Rule(signalId="ma_ema_aligned_bull", allocation=2, required=False)]
    assert not scoring_gaps(report, rules)
    # and the same rule against a report WITHOUT EMA20 does warn
    bare = Report(anchor="1h", sections=[CustomSection(
        title="t", benchmarkTicker=None,
        columns=[Column.model_validate({"metric": "CLOSE", "transformId": "value",
                                        "timeframe": {"rel": "anchor"}})])])
    assert len(scoring_gaps(bare, rules)) == 1
