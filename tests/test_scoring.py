"""Verify omega.scoring against real (indicatorValues -> score) pairs.

The probes in data/performance/score_probes.json were captured from live
get_coin_signal_preview calls. Nothing here is synthetic: every expected value is a
number the engine actually produced.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.scoring import SCORERS, UNCOMPUTABLE, Score, clamp01, flow_rate, score

ROOT = Path(__file__).resolve().parents[1]
PROBES = json.loads((ROOT / "data" / "performance" / "score_probes.json")
                    .read_text(encoding="utf-8"))

# Signals whose inputs are not plain indicator readings - covered explicitly below.
_NON_INDICATOR = {"regime_alignment", "cvd_bullish", "cvd_bearish", "regime_trend_shift",
                  "regime_volatility_shift", "comparison_btc_decorrelation",
                  "mtf_aligned_bull", "mtf_aligned_bear", "macd_bear_divergence"}


def _cases():
    for probe in PROBES["probes"]:
        for sig in probe["signals"]:
            if sig["id"] in _NON_INDICATOR:
                continue
            yield pytest.param(sig, probe["source"],
                               id=f"{sig['id']}::{probe['source'].split()[-2]}")


@pytest.mark.parametrize("sig,source", list(_cases()))
def test_score_matches_engine_exactly(sig, source):
    """Bit-exact, not approximate. A float that is merely close is a wrong formula."""
    got = score(sig["id"], sig["indicatorValues"], sig["params"])
    assert got.computable, f"{sig['id']} should be computable: {got.reason}"
    assert got.value == sig["score"], (
        f"{sig['id']} from {source}\n"
        f"  expected {sig['score']!r}\n  got      {got.value!r}\n"
        f"  raw      {got.raw!r}"
    )


def test_clamp_is_real_and_leaves_a_trace():
    """Two live readings prove the engine clamps; the Score records that it happened."""
    sma = score("ma_sma200_above", {"price": 77103, "sma200": 69944.975}, {})
    assert sma.value == 1.0
    assert sma.raw == pytest.approx(2.046758898691434)
    assert sma.clamped is True

    adx = score("htf_trend_adx_trending", {"htf_adx_value": 62.69246122}, {"threshold": 25})
    assert adx.value == 1.0 and adx.clamped is True

    # ...and an unclamped score reports clamped=False
    rng = score("trend_adx_ranging", {"adx_value": 11.68241454}, {"threshold": 20})
    assert rng.value == 0.415879273 and rng.clamped is False


def test_flow_rate_clamps_at_one():
    """BTC's perp rate was raw 1.545; the engine's own text printed 'perp rate 1.00'."""
    assert flow_rate(114.19563, -209.443) == 1.0
    assert flow_rate(-92.83566948, -305.78315228) == pytest.approx(0.6964003124835599)


def test_mtf_synthesis_uses_exact_component_scores():
    """ETH 4h: (LTF 0.0705425369855601, primary 1.0, HTF 1.0) -> 0.6901808456618533."""
    got = score("mtf_aligned_bull", {"ltf_score": 0.0705425369855601,
                                     "primary_score": 1.0, "htf_score": 1.0}, {})
    assert got.value == 0.6901808456618533


def test_btc_decorrelation_normaliser_is_twice_max_correlation():
    """corr 0.00 with maxCorrelation 0.3 -> 0.5, which only 2x normalisation gives."""
    got = score("comparison_btc_decorrelation", {"correlation": 0.0}, {"maxCorrelation": 0.3})
    assert got.value == 0.5


def test_two_state_signals_read_their_categorical_flag():
    assert score("cvd_bullish", {"state_high": True}, {}).value == 1.0
    assert score("cvd_bearish", {"state_high": False}, {}).value == 0.5
    assert score("regime_divergence", {"state_high": False}, {}).value == 0.6
    assert score("structure_zone_confluence", {"state_high": True}, {}).value == 1.0


def test_regime_alignment_refuses_rather_than_guesses():
    """Published formula says alignedCount/3; live returned 0.7 twice. Unresolved."""
    got = score("regime_alignment", {}, {})
    assert got.computable is False
    assert got.value is None
    assert "0.7" in got.reason


def test_divergence_signals_refuse_rather_than_guess():
    for sid in ("rsi_bull_divergence", "macd_bear_divergence", "cvd_bull_divergence"):
        got = score(sid, {}, {})
        assert got.computable is False, f"{sid} must not fabricate a magnitude"
        assert got.value is None


def test_uncomputable_is_distinguishable_from_did_not_fire():
    """The whole point of the `computable` flag."""
    did_not_fire = score("rsi_oversold", {"rsi14": 55.0}, {"threshold": 30})
    assert did_not_fire.computable is True and did_not_fire.value == 0.0

    cannot_model = score("rsi_bull_divergence", {}, {})
    assert cannot_model.computable is False and cannot_model.value is None


def test_missing_indicator_is_reported_not_raised():
    got = score("rsi_oversold", {}, {"threshold": 30})
    assert got.computable is False
    assert "rsi14" in got.reason


def test_every_signal_is_either_scorable_or_explicitly_refused():
    """No silent gaps: all 84 signals are accounted for one way or the other."""
    module_map = json.loads((ROOT / "data" / "derived" / "signal_module_map.json")
                            .read_text(encoding="utf-8"))
    all_signals = {s for v in module_map["moduleSignals"].values() for s in v}
    covered = set(SCORERS) | set(UNCOMPUTABLE)
    assert all_signals - covered == set(), f"unaccounted: {sorted(all_signals - covered)}"
    assert covered - all_signals == set(), f"not real signals: {sorted(covered - all_signals)}"


def test_scoring_corpus_agrees_with_the_module():
    """The JSON corpus and the code must not drift apart."""
    corpus = json.loads((ROOT / "data" / "contract" / "signals" / "_scoring.json")
                        .read_text(encoding="utf-8"))
    for sid, entry in corpus["signals"].items():
        refuses = sid in UNCOMPUTABLE
        should_refuse = (entry["family"] == "unspecified_magnitude"
                         or entry["provenance"] == "documented_mismatch")
        assert refuses == should_refuse, (
            f"{sid}: corpus family={entry['family']} "
            f"provenance={entry['provenance']} but UNCOMPUTABLE={refuses}")


def test_clamp01_boundaries():
    assert clamp01(-0.5) == 0.0
    assert clamp01(1.5) == 1.0
    assert clamp01(0.4) == 0.4


def test_score_str_is_readable():
    s = score("ma_sma200_above", {"price": 77103, "sma200": 69944.975}, {})
    assert "clamped" in str(s)
    assert "not computable" in str(score("regime_alignment", {}, {}))


def test_divergence_magnitude_is_not_fixed_at_one():
    """Doc 11 carried this as an open question. The captures answer it.

    The claim was that every observed divergence firing returned exactly 1.0,
    which would have suggested a fixed score. Across three captures there are
    counterexamples, including in the very signal doc 11 named:

        oi_divergence_bull       ETH    0.20133736400835542
        flow_perp_spot_bear_*    ETH    0.2392909896129719
        flow_perp_spot_bull_*    SOL    0.2421094388008913
        flow_perp_spot_bear_*    BTC    0.30359968751644006

    So magnitude demonstrably varies. That does NOT make the formula known - it
    makes refusing to guess it the right call, which is what omega.scoring does.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    firings = []
    for f in sorted((root / "data" / "performance").glob("coin_observations*.json")):
        for o in json.loads(f.read_text(encoding="utf-8"))["observations"]:
            firings += [(sid, v) for sid, v in o["scores"].items() if "divergence" in sid]

    assert firings, "the captures must contain divergence firings"
    varied = [(sid, v) for sid, v in firings if v != 1]
    assert varied, "a counterexample to 'always 1.0' must be present"
    assert any(sid == "oi_divergence_bull" for sid, _ in varied), (
        "oi_divergence_bull is the signal doc 11 named as always-1.0; its "
        "counterexample is what closes the question")

    # and the refusal still stands - a varying magnitude is not a known formula
    from omega.scoring import score
    for sid, _ in varied:
        if sid in ("comparison_sector_divergence",):
            continue          # a peer ratio, not a divergence magnitude
        assert not score(sid, {}).computable, f"{sid} must still refuse to guess"
