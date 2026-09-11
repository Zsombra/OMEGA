"""The suite builder's wire bodies must pass the schema-drift preflight walker OFFLINE.

Why this test exists (2026-09-11): the builder had emitted design records and called them
"submit-ready". Run through scripts/preflight.py against a fresh schema capture, every one
FAILED - five required fields missing, ten undeclared keys. Offline validation had passed
with zero errors. This test closes that gap by walking every wire body against the
COMMITTED compile schema capture with the same walker the preflight uses.

Pure: no network, no files written.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from omega import preflight as P

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tpo_suite_build", ROOT / "scripts" / "tpo_suite_build.py")
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)  # type: ignore[union-attr]

SCHEMA_CAPTURE = ROOT / "data/contract/compile_strategy_plan/schema_20260909T080307Z.json"
DEFINITION = json.loads(SCHEMA_CAPTURE.read_text(encoding="utf-8"))["response"]
ARMS, SCHEMA_ROOT = P.resolve_arms(DEFINITION)
CREATE_ARM = ARMS["CREATE"]

# The annotation keys the design record carries and the wire body must NOT.
DESIGN_ONLY = {"_what", "_provenance", "id", "thesis", "teaches", "nullExposure", "anchor",
               "predictedHeaders", "thresholds", "validation", "entryMirror"}

BUILT = builder.build()
IDS = [s["id"] for s, *_ in BUILT]


def _wire(sid):
    return next(body for s, _sec, _design, body, *_ in BUILT if s["id"] == sid)


def test_every_suite_entry_validates_offline():
    for s, _sec, _design, _body, rep_errs, cond_errs, _warns in BUILT:
        assert not rep_errs and not cond_errs, (s["id"], rep_errs, cond_errs)


@pytest.mark.parametrize("sid", IDS)
def test_wire_body_passes_the_create_arm_of_the_committed_schema(sid):
    body = _wire(sid)
    findings = P.diff_schema(body, CREATE_ARM, SCHEMA_ROOT)
    fails = [f for f in findings if f.verdict == "FAIL"]
    assert not fails, "\n".join("%s %s: %s" % (f.cls, f.path, f.detail) for f in fails)


@pytest.mark.parametrize("sid", IDS)
def test_wire_body_carries_every_create_required_field_and_no_design_keys(sid):
    body = _wire(sid)
    required = set(P.deref(CREATE_ARM, SCHEMA_ROOT)["required"])
    assert required <= set(body), sorted(required - set(body))
    assert not (DESIGN_ONLY & set(body)), sorted(DESIGN_ONLY & set(body))
    assert body["operation"] == "CREATE"


@pytest.mark.parametrize("sid", IDS)
def test_wire_body_respects_the_string_caps(sid):
    body = _wire(sid)
    assert len(body["name"]) <= 50
    assert len(body["tagline"]) <= 80
    assert len(body["description"]) <= 500
    assert 0 < len(body["intentSummary"]) <= 2000
    assert 0 < len(body["assumptions"]) <= 20
    assert all(0 < len(a) <= 500 for a in body["assumptions"])


@pytest.mark.parametrize("sid", IDS)
def test_wire_body_never_sends_a_custom_section_key(sid):
    # Measured 2026-08-28 and 2026-09-10: CREATE refuses a caller-supplied custom sectionKey.
    for sec in _wire(sid)["sections"]:
        if sec.get("kind") == "custom":
            assert "sectionKey" not in sec, sec.keys()


@pytest.mark.parametrize("sid", IDS)
def test_wire_body_entry_is_the_mirror_not_an_invention(sid):
    body = _wire(sid)
    assert body["entry"] == builder.ENTRY_MIRROR
    assert body["entry"]["confirmTf"] == builder.ANCHOR
    assert set(body["entry"]) == set(P.MIRROR_ENTRY_FIELDS) | {"confirmTf"}


def test_entry_mirror_matches_a_committed_readback_when_one_exists():
    """If the read-back capture the mirror cites is committed, the mirror must equal it
    field for field. Skips rather than fails when the capture is absent, so pruning old
    captures cannot break the suite - but it can never pass with a stale mirror."""
    caps = sorted((ROOT / "data/contract/get_strategy").glob("56c08ef6-*.json"))
    if not caps:
        pytest.skip("no committed 56c08ef6 read-back capture")
    rec = P.record_request_view(json.loads(caps[-1].read_text(encoding="utf-8"))["response"])
    assert rec["entry"] == builder.ENTRY_MIRROR, (rec["entry"], builder.ENTRY_MIRROR)
    assert rec["minAggregateScore"] == builder.GATE_MIRROR["minAggregateScore"]
    assert rec["minRequiredCount"] == builder.GATE_MIRROR["minRequiredCount"]


def test_conditions_are_directional_first_so_neither_cannot_shadow():
    # Measured 2026-09-10/11: verdicts resolve first-true-wins in array order.
    rank = {"UP": 0, "DOWN": 0, None: 1, "NEITHER": 2}
    for s, *_ in BUILT:
        ranks = [rank.get(c.get("verdict"), 1) for c in s["conds"]]
        assert ranks == sorted(ranks), (s["id"], [c.get("verdict") for c in s["conds"]])
