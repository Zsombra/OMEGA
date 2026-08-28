"""BG-14's missing number: the largest ranked selection whose compile preview fits
the 256,000-byte cap - measured 2026-08-28 by model-guided search, for the
trend-continuation report shape. The answer is FOUR: the linearity prediction failed
(the byte curve is concave - the first handful of coins spends most of the budget),
so ranked universes are usable but tiny, and realistic breadth needs explicit lists.
Report-relative: a wider report refuses earlier."""
import json
from pathlib import Path

from omega.generate import PRESETS, RANKED_LIMIT_MEASURED_MAX, plan

ROOT = Path(__file__).resolve().parents[1]
CAP = json.loads(
    (ROOT / "data/audit/cap_boundary_2026-08-28.json").read_text(encoding="utf-8"))


def test_the_boundary_matches_the_record():
    assert RANKED_LIMIT_MEASURED_MAX == CAP["boundary"]["largestViableLimit"] == 4
    assert "FILL IN" not in CAP["_interpretation"]
    assert "report" in " ".join(CAP["_honestLimits"]).lower()


def test_the_bracket_is_proven_by_adjacent_probes():
    b = CAP["boundary"]
    assert b["exact"] is True
    assert b["smallestRefusedLimit"] == b["largestViableLimit"] + 1
    assert CAP["probes"]["ALL-4"]["approvedPlan"]["viability"]["viable"] is True
    assert "258883 > 256000" in CAP["probes"]["ALL-5"]["error"]["message"]
    assert "368235 > 256000" in CAP["probes"]["ALL-19"]["error"]["message"]


def test_the_category_transfer_was_checked_at_the_boundary():
    assert CAP["probes"]["CRYPTO-4"]["approvedPlan"]["viability"]["viable"] is True


def test_the_linearity_prediction_failure_is_recorded():
    assert "FAILED" in CAP["_predictionStatedBeforeMeasuring"]


def test_ranked_defaults_now_fit_the_measured_boundary():
    for preset in PRESETS:
        sel = plan(PRESETS[preset]).wire()["coinSelection"]
        if sel["mode"] == "ranked":
            assert sel["limit"] <= RANKED_LIMIT_MEASURED_MAX


def test_an_oversized_ranked_selection_draws_a_critique_warning():
    from dataclasses import replace
    t = replace(PRESETS["trend-continuation"],
                coin_selection={"mode": "ranked", "category": "ALL",
                                "limit": RANKED_LIMIT_MEASURED_MAX + 5})
    text = " ".join(plan(t).critique())
    assert "BG-14" in text and str(RANKED_LIMIT_MEASURED_MAX) in text
