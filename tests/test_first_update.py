"""The generated UPDATE (design 2026-08-29): wire_update is wire() plus exactly three
patched fields - the Thesis stays the single source of truth and the server computes
the diff. The record pins for the live loop are appended by the execution task."""
from __future__ import annotations

import pytest

from omega.generate import PRESETS, plan
from tests.test_write_surface import API_ACCEPTS

NIL_ID = "00000000-0000-0000-0000-000000000000"
API_UPDATE_REQUIRES = {"operation", "intentSummary", "assumptions", "coinSelection",
                       "strategyId", "expectedRevision"}


def test_wire_update_is_wire_plus_exactly_three_fields():
    p = plan(PRESETS["trend-continuation"])
    w, u = p.wire(), p.wire_update(NIL_ID, 3)
    assert u["operation"] == "UPDATE"
    assert u["strategyId"] == NIL_ID and u["expectedRevision"] == 3
    assert {k for k in set(w) | set(u) if w.get(k) != u.get(k)} == {
        "operation", "strategyId", "expectedRevision"}


def test_wire_update_refuses_a_nonpositive_revision():
    with pytest.raises(ValueError):
        plan(PRESETS["trend-continuation"]).wire_update(NIL_ID, 0)


def test_wire_update_satisfies_the_update_arm():
    u = plan(PRESETS["trend-continuation"]).wire_update(NIL_ID, 1)
    assert API_UPDATE_REQUIRES <= set(u)
    assert set(u) <= API_ACCEPTS | {"strategyId", "expectedRevision"}


def test_update_mode_body_differs_from_small_in_exactly_the_declared_fields():
    """The proof body: the known-viable small body re-targeted, with the ONE thesis
    change (the R:R override). assumptions moves too - its third entry flips to the
    overrides wording, which is Decision 1(a) working as designed."""
    from scripts.compile_dry_run import request, update_request
    small = request(small=True)["request"]
    up = update_request(NIL_ID, 3)["request"]
    assert {k for k in set(small) | set(up) if small.get(k) != up.get(k)} == {
        "operation", "strategyId", "expectedRevision", "minRiskRewardRatio",
        "assumptions"}
    assert up["minRiskRewardRatio"] == 2.0
    assert "execution overrides set: ['minRiskRewardRatio']" in up["assumptions"][2]
