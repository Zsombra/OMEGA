"""Tier C: the 32 metrics no exchange publishes.

docs/19's method - diff against Hyperliquid - cannot touch these. But "no external
referent" is not "uncheckable": most can be tested for COHERENCE against BattleGrid's
own tier-A numbers, or against each other.

Read the verdicts honestly. Coherence shows a metric is consistent with its stated
definition and its neighbours. It cannot show the classification is CORRECT - a regime
classifier can be perfectly self-consistent and still wrong about the regime. These
tests guard "not broken in a way this test could see", which is weaker than what
tests/test_conventions.py guards, and the distinction is the point.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

C = json.loads(Path("data/audit/tier_c_coherence.json").read_text(encoding="utf-8"))
COHERENT = {m for e in C["coherent"] for m in e["metrics"]}
OPEN = {m for e in C["notVerifiable"] for m in e["metrics"]}

TIER_C = {
    "BUY_PRESSURE", "BUY_TRADES", "BUY_VOLUME", "CAPTAIN_CONF", "CONFIDENCE",
    "CROWD_ACC", "CROWD_ACC_LIVE", "CROWD_CAPT", "CROWD_CAPT_LIVE", "CROWD_PICK",
    "CROWD_PICK_LIVE", "CROWD_UPBIAS", "CROWD_UPBIAS_LIVE", "CVD", "FLOW_ALIGN",
    "OI_PX_REGIME", "OI_VELOCITY", "PERP_SPOT_CONFIRMS", "PERP_SPOT_FLOW",
    "PERP_SPOT_STRENGTH", "PRICE_ZONE", "REGIME_MOM", "REGIME_TREND", "REGIME_VOL",
    "SELL_TRADES", "SELL_VOLUME", "SETTLED_AT", "SMART_RETAIL", "SPOT_CVD",
    "STRUCT_ZONES", "SWING_HIGH", "SWING_LOW",
}


def test_every_tier_c_metric_has_a_verdict():
    """Silence is the failure mode this file exists to prevent. A metric with no entry
    either way reads as 'fine' to anyone skimming."""
    missing = TIER_C - COHERENT - OPEN
    # SPOT_CVD is crypto-only and was measured null off-crypto; it has no coherence
    # test of its own yet, and saying so is better than pretending otherwise.
    assert missing == {"SPOT_CVD"}, f"unaccounted tier-C metrics: {sorted(missing)}"


def test_no_metric_is_both_coherent_and_open():
    assert not (COHERENT & OPEN)


# --- the arithmetic, replayed ----------------------------------------------

def test_cvd_delta_equals_the_per_bar_buy_sell_split():
    """SOL, four consecutive closed bars. Displayed K values carry 1 dp, so the bound
    is 100 units - and the deltas are tens of thousands, so it still discriminates."""
    cvd = [128434, 60187, 15140, 34702, 126782]
    buy = [96600, 101500, 71300, 210900, 237300]
    sell = [77600, 169700, 116300, 191400, 145200]
    for i in range(1, len(cvd)):
        delta = cvd[i] - cvd[i - 1]
        split = buy[i] - sell[i]
        assert abs(delta - split) <= 100, f"bar {i}: dCVD {delta} vs split {split}"


def test_cvd_is_not_price_scaled():
    """Its declared unit is signedPrice, but the arithmetic is in base-asset units.
    If it were price-scaled the deltas would be ~100x larger on SOL."""
    delta = 126782 - 34702
    split = 237300 - 145200
    assert abs(delta - split) <= 100
    assert abs(delta - split * 98.63) > 1000, "price-scaling must NOT also fit"


def test_price_zone_is_NOT_position_between_the_swings():
    """This test asserted the opposite until a 30-coin sample falsified it.

    Three coins fit a position rule and it looked coherent. Thirty coins produce 31
    inverted pairs: XRP at 10.0% reads 'mid-range' while ETH at 22.2% reads 'near low'.
    The test now pins the falsification, so the wrong rule cannot be re-adopted by
    someone who checks three coins again."""
    from scripts.regime_sample import ROWS
    order = {"near low": 0, "mid-range": 1, "near high": 2}
    pos = [((r[10] - r[9]) / (r[8] - r[9]), r[0], r[7]) for r in ROWS]
    inverted = [(a, b) for a in pos for b in pos
                if a[0] < b[0] and order[a[2]] > order[b[2]]]
    assert len(inverted) > 20, (
        "position ordering now separates the labels - PRICE_ZONE may have changed, "
        "or the sample no longer discriminates")

    entry = next(e for e in C["notVerifiable"] if "PRICE_ZONE" in e["metrics"])
    assert "DOWNGRADED" in entry["correction"]


def test_smart_retail_rule_holds_on_every_non_null_case():
    """flow pressure vs crowd bias, 13 of 13. This one went the other way - a verdict
    upgraded from 'not verifiable' once the sample was big enough to carry cases."""
    from scripts.flow_sample import ROWS as F
    hits = total = 0
    for r in F:
        if r[4] is None:
            continue
        total += 1
        fb, cb = r[10] > 0.5, r[9] > 50
        want = "confirmed" if fb == cb else (
            "hidden accumulation" if fb else "hidden distribution")
        hits += want == r[4]
    assert total >= 12 and hits == total, f"{hits}/{total}"


def test_flow_align_uses_the_last_bar_cvd_delta_not_the_window_trend():
    """PENGU is the discriminating case: CVD_trend reads 'falling' across the window
    while its last bar rose +12.8M, and FLOW_ALIGN reports 'divergent'."""
    cases = [("AVAX", -97030, -97653, 28.6, "aligned bearish"),
             ("GRAM", 367281, 406103, 100.0, "aligned bullish"),
             ("LINK", -16893, -37159, 60.0, "divergent"),
             ("PENGU", 21868877, 34661366, 0.0, "divergent")]
    for coin, prev, now, up, expected in cases:
        fb, cb = (now - prev) > 0, up > 50
        got = ("aligned bullish" if fb and cb else
               "aligned bearish" if not fb and not cb else "divergent")
        assert got == expected, coin


def test_oi_px_regime_is_the_classic_quadrant():
    """BTC OI rising + price down -> new shorts. SOL OI falling + price down ->
    long liquidation."""
    for oi_rising, chg, expected in [(True, -0.44, "new shorts"),
                                     (False, -1.94, "long liquidation")]:
        got = (("new longs" if chg > 0 else "new shorts") if oi_rising
               else ("short covering" if chg > 0 else "long liquidation"))
        assert got == expected


def test_the_wrong_operand_is_recorded_not_quietly_dropped():
    """An earlier pass called BTC a mismatch by testing against OI_CHG, which measures
    OI against its own 24h MEAN rather than its recent change."""
    e = next(x for x in C["coherent"] if "OI_PX_REGIME" in x["metrics"])
    assert "24 hourly samples" in e["correction"]


def test_crowd_percentages_share_a_denominator():
    """SOL's 22.2% and 88.9% are 2/9 and 8/9 - the same nine picks."""
    for up, acc, n in [(22.2, 88.9, 9), (20.0, 40.0, 5)]:
        assert abs(up - round(up * n / 100) / n * 100) < 0.2
        assert abs(acc - round(acc * n / 100) / n * 100) < 0.2


@pytest.mark.parametrize("m", sorted({"REGIME_TREND", "REGIME_VOL", "REGIME_MOM",
                                      "OI_VELOCITY", "CONFIDENCE", "PRICE_ZONE"}))
def test_the_unverifiable_ones_stay_marked_unverifiable(m):
    """If one of these is ever upgraded to 'coherent', it must come with evidence -
    not because a later pass forgot the driver was never exposed."""
    assert m in OPEN


def test_the_freshness_gap_is_recorded_as_the_gap_not_the_staleness():
    """The framing matters and was sharpened once already.

    The 32-day staleness is probably ACCOUNT STATE - no sessions had settled recently -
    so calling it a platform defect would overclaim. What IS structural is that
    SETTLED_AT carries the age and returns conditionOperators: [], so no strategy can
    detect the staleness from the inside. The finding must state the gap; the staleness
    belongs in the evidence as what made it visible."""
    f = next(x for x in C["findings"]
             if x["id"] == "crowd-data-is-a-month-stale-and-its-timestamp-cannot-be-gated")
    assert "conditionOperators: []" in f["finding"]
    assert "32 days" in f["evidence"]
    assert "account state" in f["evidence"], "the overclaim guard must stay"
