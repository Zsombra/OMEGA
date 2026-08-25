"""The tier-C rule search must stay reproducible from its stored sample.

Every number in data/audit/tier_c_coherence.json['_ruleSearch2'] is recomputed here from
data/samples/tier_c_drivers_1h.md. If the sample or the scoring changes, these fail rather
than letting a stale claim sit in the record looking measured.

The discipline being guarded is margin-reporting: a verdict is only meaningful next to the
mode baseline it beat. A rule that scores 69% sounds strong until you see the baseline was
65%.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.tier_c_rule_search import ROWS, confidence, oi_velocity, regime_mom

ROOT = Path(__file__).resolve().parents[1]
REC = json.loads((ROOT / "data/audit/tier_c_coherence.json").read_text(
    encoding="utf-8"))["_ruleSearch2"]


def test_sample_parses_completely():
    assert len(ROWS) == 78
    # the crypto-only columns are null exactly where the asset class nulls them
    crypto = [r for r in ROWS if r["conf"] is not None]
    assert len(crypto) == 36
    for r in ROWS:
        assert len(r["OI"]) == 4 and all(v > 0 for v in r["OI"])


@pytest.mark.parametrize("fn,name", [
    (regime_mom, "REGIME_MOM"), (oi_velocity, "OI_VELOCITY"), (confidence, "CONFIDENCE")])
def test_recorded_numbers_are_reproducible(fn, name, capsys):
    live = fn()
    capsys.readouterr()                       # the functions print their own report
    rec = REC[name]
    for field in ("baseline", "best", "margin", "bestRule", "distribution"):
        assert live[field] == rec[field], f"{name}.{field} drifted"


def test_every_verdict_carries_its_margin(capsys):
    """No verdict may be recorded without the baseline it was judged against."""
    for fn in (regime_mom, oi_velocity, confidence):
        live = fn()
        capsys.readouterr()
        assert live["margin"] == pytest.approx(live["best"] - live["baseline"], abs=1e-9)
        assert 0.0 <= live["baseline"] <= 1.0


def test_negatives_are_genuinely_noise_sized(capsys):
    """The two 'NOT identified' verdicts must not be hiding a strong winner."""
    for fn, name in ((regime_mom, "REGIME_MOM"), (confidence, "CONFIDENCE")):
        live = fn()
        capsys.readouterr()
        assert live["verdict"] == "NOT identified", name
        assert live["margin"] < 0.15, f"{name} margin {live['margin']} is no longer noise"


def test_oi_velocity_beats_its_baseline_decisively(capsys):
    live = oi_velocity()
    capsys.readouterr()
    assert live["verdict"] == "PARTIAL"
    assert live["margin"] >= 0.20
    assert "d_last" in live["bestRule"], "the winner must still be the second difference"
    # the subset is a diagnostic, so it must never be the only number recorded
    assert "resolvableSubset" in live and live["resolvableSubset"]["rows"] < live["rows"]


def test_confidence_is_not_perp_spot_strength():
    """The recorded 'ruledOut' claim, checked against the data rather than asserted."""
    crypto = [r for r in ROWS if r["conf"] is not None]
    agree = sum(r["conf"] == r["perpSpotStr"] for r in crypto)
    assert agree / len(crypto) < 0.6, (
        "CONFIDENCE now tracks PERP_SPOT_STRENGTH; the 'CONFIDENCE idiom' wording would "
        "then mean a shared value, not a shared bucketing function")
    # 32 low, CRV high, PENGU moderate, MELANIA and PURR null - perpSpotStr is nearly
    # constant here while conf splits 15/21, so they cannot be the same value
    assert sum(r["perpSpotStr"] == "low" for r in crypto) == 32
    assert sum(r["conf"] == "high" for r in crypto) == 15


def test_regime_mom_inversion_case_still_present():
    """AMZN is the evidence that REGIME_MOM does not read the anchor grid."""
    amzn = next(r for r in ROWS if r["coin"] == "AMZN")
    assert amzn["regMom"] == "bullish"
    assert all(amzn[k] < 0 for k in ("ROC", "PPO", "MACD", "chg4h", "chg24h"))
    assert amzn["RSI14"] < 40
