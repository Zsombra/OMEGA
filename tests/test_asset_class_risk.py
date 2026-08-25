"""Which families break off-crypto, and which cannot be gated.

Measured 2026-08-25 across STOCKS, TRADFI, INDICES and COMMODITIES. Two things the
census had never asked about its own 46 buildable families.

The failure mode being guarded here is the quiet one. A family built on `VWAP` does not
error on GOOGL - it renders an em-dash, and a null reads FALSE rather than UNRESOLVED
(cookbook trap 11). The scorecard looks fully populated while the gate is answering from
absence of data.
"""
from __future__ import annotations

import json

import pytest

from omega.contract import DERIVED_DIR

FAM = json.loads((DERIVED_DIR / "indicator_families.json").read_text(encoding="utf-8"))
COVERAGE = FAM["_assetClassCoverage"]
BUILDABLE = {f["id"]: f for f in FAM["buildable"]}

AFFECTED = {"vwap-deviation", "venue-dislocation", "stretch-ranking",
            "perp-spot-cvd", "obv-divergence", "basis"}


@pytest.mark.parametrize("fid", sorted(AFFECTED))
def test_an_affected_family_is_flagged_in_the_census(fid):
    """Anyone reading the census must see the crypto-only constraint on the entry
    itself, not only in a note further down the file."""
    assert BUILDABLE[fid].get("cryptoOnly"), f"{fid} lost its cryptoOnly flag"


def test_no_other_family_is_flagged():
    flagged = {k for k, v in BUILDABLE.items() if v.get("cryptoOnly")}
    assert flagged == AFFECTED


def test_the_rule_is_the_daily_anchor_not_order_flow():
    """The sharp version of the finding. CVD, SPOT_CVD, OBV and VWAP are all described
    by the platform as accumulated since the daily 00:00-UTC anchor, and all four are
    null off-crypto. Per-bar order-flow metrics render fine."""
    rule = COVERAGE["rule"]
    for m in ("CVD", "SPOT_CVD", "OBV", "VWAP"):
        assert m in rule
    for m in ("BUY_VOLUME", "SELL_VOLUME", "BUY_PRESSURE"):
        assert m in rule, f"{m} renders off-crypto and the rule must say so"


def test_buy_and_sell_volume_are_not_treated_as_crypto_only():
    """This was guessed wrong once. BUY_VOLUME and SELL_VOLUME DO render off-crypto -
    measured on MU (3.9K/5.4K) and SKHX (28.3K/22.5K). If a future edit re-adds them to
    the crypto-only set, order-flow-imbalance would be wrongly condemned."""
    assert "order-flow-imbalance" not in AFFECTED
    assert not BUILDABLE["order-flow-imbalance"].get("cryptoOnly")
    assert "correctionMade" in COVERAGE


def test_non_crypto_tickers_are_recorded_as_perps():
    """The prior assumption - that stocks would lack funding and open interest - was
    wrong, and the census now says so out loud."""
    assert "perpetual" in COVERAGE["surprise"].lower()


# --- gateability ------------------------------------------------------------

def test_label_only_families_are_marked():
    """A family whose only output is categorical can be matched against a label but
    never thresholded. Two of the 46 are in that position."""
    marked = {k for k, v in BUILDABLE.items() if v.get("gateability") == "label-only"}
    assert marked == {"oscillator-zone", "crossover-event"}
    assert FAM["_gateability"]["numericGateable"] == 44


def test_the_ungateable_transform_is_named():
    """nearestZoneRange returns conditionOperators: [] - it renders and cannot be
    referenced by any condition at all."""
    # nearestZoneRange is now VERIFIED (its bounds match a real FVG to the dollar) and
    # still UNGATEABLE. Those are independent facts, and conflating them is what this
    # test originally did - it looked the transform up in notVerified, which broke the
    # moment the transform was verified. Gateability is its own record.
    assert FAM["_gateability"]["ungateable"] == []
    assert "nearestZoneRange" in FAM["_gateability"]["note"]

    audit = json.loads((DERIVED_DIR.parent / "audit" /
                        "transform_formula_audit.json").read_text(encoding="utf-8"))
    entry = next(x for x in audit["verified"] if x["transform"] == "nearestZoneRange")
    assert "exact" in entry["result"]


# --- the attribution caveat -------------------------------------------------

def test_attributions_are_flagged_as_judgement_not_measurement():
    """Every other claim in the census was measured against the live engine. The
    academic attribution was not, and the file has to say so - otherwise it reads with
    the same authority as the measurements next to it."""
    caveat = FAM["_attributionCaveat"]
    assert "not a measurement" in caveat
    assert "judgement" in caveat or "judgment" in caveat


def test_every_attributed_family_still_carries_its_attribution():
    attributed = [f for f in FAM["buildable"] if f.get("attribution")]
    assert len(attributed) >= 5, "attributions vanished - the caveat now guards nothing"


# --- the zone-distance defect ----------------------------------------------

def test_nearest_zone_dist_sign_defect_is_recorded():
    """The stated formula gives +1.3% where the engine renders -1.2%. Anyone building
    from the machine-readable formula rather than the header prose gets a reversed gate."""
    audit = json.loads((DERIVED_DIR.parent / "audit" /
                        "transform_formula_audit.json").read_text(encoding="utf-8"))
    d = next(x for x in audit["platformDefects"]
             if x["id"] == "nearest-zone-dist-formula-is-documented-with-the-wrong-sign")
    assert "INVERTED" in d["finding"]

    # the arithmetic that settles it, replayed
    lo, hi, close = 77859.00, 77923.00, 78883.00
    mid = (lo + hi) / 2
    stated = (close - mid) / mid * 100
    actual = (mid - close) / close * 100
    assert stated > 0 and actual < 0, "the sign disagreement is the whole finding"
    assert abs(actual - (-1.2)) < 0.15
