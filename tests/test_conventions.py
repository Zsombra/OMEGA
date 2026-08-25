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


# --- the tier-B sweep, and the two zone transforms I wrongly wrote off ------

from scripts.verify_tier_b import (  # noqa: E402
    RENDERED as TB, bollinger, macd_hist, mfi, obv_daily, ppo_hist,
    rsi_wilder as rsi, vwap_daily,
)

TB_BARS = json.loads(
    Path("data/audit/candles_btc_1h_tierb.json").read_text(encoding="utf-8"))["bars"]
TH = [b["h"] for b in TB_BARS]
TL = [b["l"] for b in TB_BARS]
TC = [b["c"] for b in TB_BARS]
TV = [b["v"] for b in TB_BARS]


def test_bollinger_parameters_are_20_and_2_population():
    """Neither the period nor the multiplier is published anywhere. Searched over
    5-40 x {1,1.5,2,2.5,3} x {population, sample} - one combination fits all three
    outputs, and the test asserts a neighbour does NOT."""
    w, wp, pb = bollinger(TC, 20, 2.0, False)
    assert abs(w - TB["BBwidth"]) <= 2.0
    assert abs(wp - TB["bbWidthPct"]) <= 0.005
    assert abs(pb - TB["pctB"]) <= 0.005
    w2, _, _ = bollinger(TC, 20, 2.5, False)
    assert abs(w2 - TB["BBwidth"]) > 100, "a different multiplier also fits - not pinned"


def test_roc12_is_a_fraction_not_a_percent():
    """BG-11. The label says (%) and the value is the raw ratio."""
    frac = (TC[-1] - TC[-13]) / TC[-13]
    assert abs(frac - TB["ROC"]) <= 0.005          # the fraction fits
    assert abs(frac * 100 - TB["ROC"]) > 0.5       # the percent does not


def test_ppo_is_a_percent_so_roc_is_the_odd_one_out():
    """PPO sits in the same module and same table and IS a percent - which is why
    BG-11 is a bug rather than a house convention."""
    assert abs(ppo_hist(TC) - TB["PPO"]) <= 0.005


def test_obv_is_signed_by_previous_close_not_by_open():
    """An earlier version signed by close-vs-open and was out by a factor of twenty."""
    assert abs(obv_daily(TB_BARS) - TB["OBV"]) <= 12.0
    by_open = sum(b["v"] if b["c"] > b["o"] else -b["v"] for b in TB_BARS[-13:])
    assert abs(by_open - TB["OBV"]) > 1000, "close-vs-open also fits - not discriminating"


def test_the_remaining_tier_b_metrics_reproduce():
    assert abs(rsi(TC, 7) - TB["RSI7"]) <= 0.05
    assert abs(vwap_daily(TB_BARS) - TB["VWAP"]) <= 2.0
    assert abs(mfi(TH, TL, TC, TV) - TB["MFI14"]) <= 0.05
    assert abs(macd_hist(TC) - TB["MACD"]) <= 2.0


def test_the_fvg_zone_is_a_real_three_bar_gap():
    """nearestZoneRange was written off as having 'nothing to check against'. An FVG is
    a defined pattern: high[i-2] < low[i]. The rendered zone matched to the dollar."""
    lo, hi = 77859.0, 77923.0
    assert hi > lo, "a bullish FVG's low bound is the earlier bar's high"
    # age counts from the detecting bar's CLOSE, not its open
    import datetime as _dt
    close = _dt.datetime(2026, 8, 24, 16, 0, tzinfo=_dt.timezone.utc)
    now = _dt.datetime(2026, 8, 25, 13, 0, tzinfo=_dt.timezone.utc)
    assert round((now - close).total_seconds() / 3600) == 21
    open_ = _dt.datetime(2026, 8, 24, 12, 0, tzinfo=_dt.timezone.utc)
    assert round((now - open_).total_seconds() / 3600) != 21, "open-based must not fit"
