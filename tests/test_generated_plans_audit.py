"""Every preset thesis must survive the traps the extraction work measured.

Validation answers "will the platform accept this". This answers the different and
harder question: "is it worth accepting". A plan can pass omega.validate and still be
quietly wrong - a gate on a label that never occurs, a threshold 100x off because ROC12
renders a fraction while labelled a percent, two section slots spent on one measurement
because rank_lo and rank_near are the same column for a non-negative metric.

The known finding is pinned by name below rather than waived. A NEW one fails.
"""
from __future__ import annotations

import pytest

from omega import contract as C
from omega.generate import PRESETS
from scripts.audit_generated_plans import audit

# The one finding that exists today, recorded so a regression is a NEW entry rather than
# a silent addition to a growing list. flow-divergence gates on PERP_SPOT_FLOW
# 'perp_led_fragile', which 78 coins x 4 anchors never produced. It sits inside an N_OF
# needing 2 of 4, so the condition still fires - the THRESHOLD moves: the gate is really
# 2-of-3. Not fixed by substitution, because every observed alternative
# (neutral / spot_led_accumulation / confirmed_bear) means something materially different
# from "perp-led and fragile", and changing it would change what the strategy believes.
# That is the author's call, not the toolkit's.
KNOWN = {
    "flow-divergence": ["INERT CLAUSE PERP_SPOT_FLOW is 'perp_led_fragile'"],
}


@pytest.fixture(scope="module")
def contract():
    return C.load()


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_preset_has_only_known_findings(preset, contract):
    _, _, findings = audit(preset, contract)
    expected = KNOWN.get(preset, [])
    assert len(findings) == len(expected), (
        f"{preset}: expected {len(expected)} known finding(s), got {len(findings)}:\n"
        + "\n".join(f"  - {f}" for f in findings))
    for got, want in zip(findings, expected):
        assert got.startswith(want), f"{preset}: {got!r} does not match known {want!r}"


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_every_preset_validates(preset, contract):
    """No preset may emit a column the platform would refuse."""
    _, _, findings = audit(preset, contract)
    assert not [f for f in findings if f.startswith("VALIDATION")]


def test_no_preset_uses_roc12_without_acknowledging_bg11(contract):
    """BG-11: ROC12 renders a fraction while its label says percent. A threshold written
    as a percent is 100x wrong, so its presence must surface, not pass silently."""
    for preset in PRESETS:
        _, _, findings = audit(preset, contract)
        assert not [f for f in findings if f.startswith("BG-11")], (
            f"{preset} uses ROC12; confirm the threshold is a FRACTION, then pin it here")


def test_the_inert_clause_effect_is_reported_structurally(contract):
    """The first version of the audit called every unobserved label 'FALSE forever'.
    That is only true for a bare clause or an ALL member. This one is an N_OF member,
    where the real effect is a moved threshold - a different bug with a different fix."""
    _, _, findings = audit("flow-divergence", contract)
    assert len(findings) == 1
    assert "N_OF needing 2" in findings[0]
    assert "2-of-3" in findings[0], "the audit must state the EFFECTIVE gate, not just 'inert'"
