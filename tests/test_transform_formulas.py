"""The transform formulas, pinned to the arithmetic that was measured live.

`docs/19` checked the METRICS - RSI, ATR, SMA, EMA - against the textbook. It never
touched the TRANSFORMS, which are the layer the whole column algebra sits on. Before
2026-08-25 exactly one of the seventeen had been checked against its stated formula.

These tests do not call the platform. They replay observations recorded in
`data/audit/transform_formula_audit.json` through the stated formula and assert the
formula reproduces what the engine rendered. If someone later edits a stated formula in
`_authoring.json` to something that would not have produced the observed number, that is
a lie the repo can no longer tell quietly.
"""
from __future__ import annotations

import json

import pytest

from omega.contract import DERIVED_DIR

AUDIT = json.loads(
    (DERIVED_DIR.parent / "audit" / "transform_formula_audit.json").read_text(encoding="utf-8"))


def _rounds_to(value: float, shown: float, dp: int) -> bool:
    return abs(round(value, dp) - shown) < 10 ** -(dp + 3)


# --- the arithmetic, replayed -----------------------------------------------

def test_efficiency_is_net_move_over_path_length():
    """|last - first| / sum |consecutive change|."""
    btc = [78740.0, 78924.0, 78971.0, 78729.0, 78996.0]
    path = sum(abs(b - a) for a, b in zip(btc, btc[1:]))
    assert _rounds_to(abs(btc[-1] - btc[0]) / path, 0.35, 2)

    sol = [96.50, 96.50, 97.49, 97.49, 99.05]
    path = sum(abs(b - a) for a, b in zip(sol, sol[1:]))
    # a perfectly monotonic run must give exactly 1.0 - the strong half of the check
    assert abs(abs(sol[-1] - sol[0]) / path - 1.0) < 1e-12


def test_max_share_is_max_over_sum():
    vols = [1315.32156, 1002.39314, 845.78639, 1356.15002]
    assert _rounds_to(max(vols) / sum(vols), 0.30, 2)


def test_aggregate_is_the_arithmetic_mean_not_a_median():
    """Measured on OI, which varies. The first attempt used FUNDING_RATE, whose eight
    slots were all identical - a series that matches any central-tendency statistic and
    therefore distinguishes nothing."""
    sol = [441.3, 443.6, 443.6, 458.7, 492.2, 519.1]
    assert _rounds_to(sum(sol) / len(sol), 466.4, 1)

    med = sorted(sol)[len(sol) // 2 - 1:len(sol) // 2 + 1]
    assert abs(sum(med) / 2 - 466.4) > 1.0, "median must NOT also fit, or the test is vacuous"

    doge = [71.2, 71.2, 71.5, 71.8, 72.0, 71.9]
    assert _rounds_to(sum(doge) / len(doge), 71.6, 1)


def test_distance_is_price_relative_to_base():
    assert _rounds_to((78869 - 78473.20) / 78473.20 * 100, 0.50, 2)
    assert _rounds_to((100.46 - 96.06) / 96.06 * 100, 4.58, 2)


def test_spread_is_base_relative_to_operand():
    assert _rounds_to((78915.23 - 78746.02) / 78746.02 * 100, 0.21, 2)
    assert _rounds_to((0.0017 - 1.33) / 1.33 * 100, -99.87, 2)


RANKS = {"AVAX": (36, 43), "BTC": (48, 31), "DOGE": (25, 54), "ETH": (40, 39), "SOL": (29, 50)}
ATR_PCT = {"AVAX": 1.11, "BTC": 0.78, "DOGE": 1.54, "ETH": 1.01, "SOL": 1.52}
UNIVERSE = 78


@pytest.mark.parametrize("coin", sorted(RANKS))
def test_rank_hi_and_lo_are_exact_inverses(coin):
    """hi + lo == universe + 1 holds only for a tie-free ordinal over a fixed universe.
    It held on all five coins, which is what makes `rank` verified rather than plausible."""
    hi, lo = RANKS[coin]
    assert hi + lo == UNIVERSE + 1


def test_rank_is_monotone_in_the_underlying_value():
    by_value = sorted(ATR_PCT, key=lambda c: -ATR_PCT[c])
    by_rank_hi = sorted(RANKS, key=lambda c: RANKS[c][0])
    assert by_value == by_rank_hi
    by_rank_lo = sorted(RANKS, key=lambda c: RANKS[c][1])
    assert by_value == list(reversed(by_rank_lo))


# --- the record has to stay honest ------------------------------------------

def test_the_audit_covers_every_transform_the_contract_declares():
    from omega.contract import load
    declared = set(load().transforms)
    seen = {v["transform"] for v in AUDIT["verified"]}
    seen |= {v["transform"] for v in AUDIT["notVerified"]}
    missing = declared - seen
    assert not missing, f"transforms with no audit verdict either way: {sorted(missing)}"


def test_value_offset_shifts_the_window_by_exactly_n():
    """offset=3 must select the window ending 3 observations back - not 2, not 4.
    Recomputed from the cached candles; only one window fits."""
    import json as _json
    from pathlib import Path as _Path
    d = _json.loads((_Path("data/audit/candles_btc_1h_battlegrid.json")
                     ).read_text(encoding="utf-8"))
    closes = [x["c"] for x in d["candles"]] + [d["_reportSnapshot"]["close"]]

    def sma20_ending(back):
        end = len(closes) - back
        return sum(closes[end - 20:end]) / 20

    assert abs(sma20_ending(3) - 78215.50) < 0.01
    for other in (0, 1, 2, 4, 5):
        assert abs(sma20_ending(other) - 78215.50) > 1.0, (
            f"offset={other} also fits - the test does not discriminate")


def test_a_header_collision_is_recorded_as_a_platform_defect():
    """Two columns differing only by offset produce the same header, render anyway, and
    both drop out of conditionColumns. omega predicts the collision; the platform does
    not refuse it."""
    from omega.fanout import outputs_for
    from omega.types import Column, RelTimeframe
    plain = [o.header for o in outputs_for(
        Column(metric="SMA20", transformId="value", timeframe=RelTimeframe(rel="anchor")))]
    shifted = [o.header for o in outputs_for(
        Column(metric="SMA20", transformId="value",
               timeframe=RelTimeframe(rel="anchor"), offset=3))]
    assert plain == shifted, "offset must not disambiguate, or the defect is stale"
    assert any(x["id"] == "duplicate-header-drops-conditionability"
               for x in AUDIT["platformDefects"])


def test_classify_state_is_observable_but_still_not_authorable():
    """Two separate facts, and an earlier version of this test conflated them.

    NOT AUTHORABLE: refused for custom columns by the contract endpoint and by the
    renderer, so it must stay out of omega's 16.

    OBSERVABLE: a platform section renders it, so its behaviour CAN be checked. The
    earlier conclusion "not buildable, so not verifiable" mistook authoring for
    observing, and that mistake is why this sat unverified longer than it needed to."""
    from omega.contract import load
    assert "classifyState" not in load().transforms

    entry = next(x for x in AUDIT["verified"] if x["transform"] == "classifyState")
    assert "PLATFORM_ONLY" in entry["stated"]
    assert "not authorable" in entry["result"]


# --- crossDetect scope, and the rung sweep ----------------------------------

def test_cross_detect_reads_the_last_pair_only():
    """The discriminating evidence. GOOGL and ZEC both crossed zero one bar before the
    last pair, and crossDetect returned null on both - so it is
    crossDirection(base[t-1], base[t]), not 'a cross anywhere in the window'."""
    googl = (-0.0065, 0.0275, 0.0660)
    zec = (0.4217, -0.2616, -0.7253)
    for t2, t1, now in (googl, zec):
        assert (t2 > 0) != (t1 > 0), "the earlier pair must straddle zero"
        assert (t1 > 0) == (now > 0), "the last pair must not"
    v = next(x for x in AUDIT["verified"] if x["transform"] == "crossDetect")
    assert "LAST PAIR" in v["check"]
    assert v.get("caveat"), "the unpinned trigger threshold must stay recorded"


RUNGS = ("lower", "anchor", "regime")


def test_rung_variants_do_not_collide():
    """Unlike offset (BG-8), the rung infix disambiguates the header - which is why the
    same metric can be read at all three rungs in one section."""
    from omega.fanout import outputs_for
    from omega.types import Column, RelTimeframe
    for metric, tid, kw in (("RSI14", "value", {}),
                            ("ADX", "trajectory", {"window": 3}),
                            ("SMA20", "distance", {}),
                            ("STRUCT_ZONES", "count", {})):
        got = [tuple(o.header for o in outputs_for(
            Column(metric=metric, transformId=tid,
                   timeframe=RelTimeframe(rel=r), **kw))) for r in RUNGS]
        assert len(set(got)) == 3, f"{metric} x {tid} collides across rungs: {got}"


def test_the_rung_sweep_is_recorded_as_closed():
    f = next(x for x in AUDIT["operationalFindings"] if "rungs are fully modelled" in x["finding"])
    assert "30 headers" in f["evidence"]


def test_rung_rank_scoping_contradiction_is_recorded():
    d = next(x for x in AUDIT["platformDefects"]
             if x["id"] == "ltf-htf-rank-scoping-described-two-ways-in-one-response")
    assert "78" in d["repro"] and "Report size is 2" in d["repro"]
