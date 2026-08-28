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


# --- the live loop, 2026-08-29: pinned record ---------------------------------

import json
from pathlib import Path

from omega.execution import PLATFORM_EXECUTION_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
REC = json.loads(
    (ROOT / "data/audit/first_generated_update_2026-08-29.json").read_text(encoding="utf-8"))


def test_the_loop_is_recorded_end_to_end():
    assert set(REC["probes"]) >= {"preState", "restore", "compile", "apply",
                                  "readBack", "archive"}
    assert "FILL IN" not in REC["_interpretation"]
    assert REC["verdicts"]["sectionKeysOnUpdate"] in ("PRESERVED", "LOCKSTEP_REMINT")
    assert REC["verdicts"]["rrDiffAxis"] == "tradeLevelPolicy"


def test_the_override_landed_and_nothing_else_moved():
    pre = REC["probes"]["preState"]["strategy"]
    post = REC["probes"]["readBack"]["strategy"]
    assert pre["minRiskRewardRatio"] == 1.5 and post["minRiskRewardRatio"] == 2
    for k in PLATFORM_EXECUTION_DEFAULTS:
        if k != "minRiskRewardRatio":
            assert post[k] == pre[k]
    assert post["signalRules"] == pre["signalRules"]
    assert post["marketReadText"] == pre["marketReadText"]
    strip = lambda secs: [{k: v for k, v in s.items() if k != "sectionKey"}
                          for s in secs]
    assert strip(post["sections"]) == strip(pre["sections"])
    if REC["verdicts"]["sectionKeysOnUpdate"] == "PRESERVED":
        assert post["sections"] == pre["sections"]


def test_the_remint_was_lockstep_consistent():
    """The loop's one platform finding: a full-body UPDATE re-mints custom section
    identities even when the re-sent report is byte-identical - but re-resolves every
    condition reference to the new keys. Semantically safe; identity churns."""
    import re
    post = REC["probes"]["readBack"]["strategy"]
    post_keys = {s["sectionKey"] for s in post["sections"]}
    refs = set(re.findall(r'custom:[0-9a-f-]{36}', json.dumps(post["conditions"])))
    assert refs and refs <= post_keys
    pre_keys = {s["sectionKey"] for s in REC["probes"]["preState"]["strategy"]["sections"]}
    assert post_keys.isdisjoint(pre_keys), "keys re-minted - this pin documents it"


def test_the_lifecycle_ends_where_it_started():
    assert REC["probes"]["readBack"]["strategy"]["isActive"] is True
    assert REC["probes"]["archive"]["strategy"]["isActive"] is False
    assert REC["probes"]["apply"]["appliedImpact"]["committedRevision"] == 4
    assert REC["probes"]["apply"]["appliedImpact"]["boundAgentCount"] == 0
    assert REC["probes"]["apply"]["appliedImpact"]["propagatedAgentCount"] == 0
    tok = REC["probes"]["compile"].get("planToken")
    assert tok is not None and set(tok) == {"_redacted", "length", "sha256"}
