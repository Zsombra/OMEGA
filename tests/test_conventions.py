"""The three indicators where two implementations are both defensible.

ADX, CCI and Stochastic each have competing conventions in the wild. These tests replay
the measured values through both candidates and assert that the one BattleGrid implements
reproduces the rendered number AND that the alternative does not — a test that only
checked the winner would pass against an engine that had silently switched.

Data: `data/audit/candles_btc_1h_conventions.json`, 876 Hyperliquid bars ending on the
exact bar an `offset: 1` read targeted (2026-08-25T11:00Z, close 79,108).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_conventions import RENDERED, adx, cci, stoch

BARS = json.loads(
    Path("data/audit/candles_btc_1h_conventions.json").read_text(encoding="utf-8"))["bars"]
H = [b["h"] for b in BARS]
L = [b["l"] for b in BARS]
C = [b["c"] for b in BARS]


def test_the_tape_still_ends_on_the_anchor_bar():
    """Every number below is only meaningful against this exact bar."""
    assert C[-1] == 79108.0
    assert len(C) == 876


def test_adx_uses_wilder_smoothing_not_a_moving_average():
    assert abs(adx(H, L, C, 14, "wilder") - RENDERED["ADX"]) <= 0.05
    other = adx(H, L, C, 14, "sma")
    assert abs(other - RENDERED["ADX"]) > 5, (
        f"the rejected convention now fits too ({other:.2f}) - the test discriminates nothing")


def test_cci_uses_mean_absolute_deviation_not_standard_deviation():
    assert abs(cci(H, L, C, 20, 0.015, "mad") - RENDERED["CCI"]) <= 0.05
    other = cci(H, L, C, 20, 0.015, "std")
    assert abs(other - RENDERED["CCI"]) > 2, (
        f"the rejected convention now fits too ({other:.2f})")


def test_stochastic_is_slow_14_3_3():
    k, d = stoch(H, L, C, 14, 3, 3)
    assert abs(k - RENDERED["K"]) <= 0.5
    assert abs(d - RENDERED["D"]) <= 0.5


@pytest.mark.parametrize("k_smooth,d_smooth", [(1, 3), (3, 1)])
def test_the_other_stochastic_variants_are_rejected(k_smooth, d_smooth):
    """(14,3,1) is the instructive one: it reproduces %K exactly and gets %D wrong. A
    test that checked %K alone would have confirmed the wrong convention."""
    k, d = stoch(H, L, C, 14, k_smooth, d_smooth)
    fits_k = abs(k - RENDERED["K"]) <= 0.5
    fits_d = abs(d - RENDERED["D"]) <= 0.5
    assert not (fits_k and fits_d), f"({k_smooth},{d_smooth}) fits both - ambiguous"


def test_the_declared_stochastic_parameters_match_the_implementation():
    """Unlike BG-9, where the published formula was wrong, the column meaning here says
    '%K (14,3,3)' and that is what ships. The docs are unreliable in specific places,
    not uniformly."""
    k, d = stoch(H, L, C, 14, 3, 3)
    assert abs(k - RENDERED["K"]) <= 0.5 and abs(d - RENDERED["D"]) <= 0.5
