"""The first-ever compile of a GENERATED plan, 2026-08-28: refused, twice, informatively.

Two calls, the plan's hard cap, each on a materially different payload:

  1. sections carried omega's deterministic custom:<uuid5> sectionKeys
     -> REPORT_CUSTOM_SECTION_NOT_OWNED, allowedDomain enum [].
     A CREATE cannot claim section identities; the server mints them. Omega gap, fixed.
  2. sectionKeys stripped (12,210-byte plan)
     -> "Strategy report preview mcp_result_bytes limit exceeded: 395404 > 256000".
     The 256,000-byte cap the tool doc attaches to THE SERIALIZED PLAN was enforced
     against the compile's internal report preview across coinSelection ranked/ALL/30.
     A rule nobody published -> BG-14.

Neither refusal was the schema-derived keyMismatch this dry-run set out to test: the
reshaped CREATE body itself drew no unrecognized_keys and no missing-required either
time. These tests pin the records so drift in wire() or a quiet edit to the audit files
fails loudly.
"""
from __future__ import annotations

import json
from pathlib import Path

from omega.generate import PRESETS, plan
from scripts.compile_dry_run import PRESET, request

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads(
    (ROOT / "data/audit/compile_dry_run_2026-08-28.json").read_text(encoding="utf-8"))
ATTEMPT1 = json.loads(
    (ROOT / "data/audit/compile_dry_run_2026-08-28-refusal.json").read_text(encoding="utf-8"))


def test_the_record_exists_and_is_interpreted():
    for rec in (RECORD, ATTEMPT1):
        assert rec["verdict"] == "refused"
        assert "FILL IN" not in rec["_interpretation"]


def test_request_keys_match_current_wire_output():
    """If wire() gains or loses a top-level key, the recorded measurement no longer
    describes the current generator - this failing is the reminder to re-measure."""
    assert RECORD["requestKeys"] == sorted(request()["request"].keys())
    assert RECORD["preset"] == PRESET


def test_attempt_1_pinned_the_section_ownership_rule():
    d = ATTEMPT1["responseVerbatim"]["details"]
    assert d["authoringCode"] == "REPORT_CUSTOM_SECTION_NOT_OWNED"
    assert d["path"] == ["sections", 0, "sectionKey"]
    assert d["allowedDomain"] == {"kind": "enum", "values": []}, (
        "the empty enum is the finding: on CREATE, no client sectionKey is legal")


def test_attempt_2_pinned_the_preview_byte_cap():
    msg = RECORD["responseVerbatim"]["message"]
    assert "395404 > 256000" in msg and "mcp_result_bytes" in msg
    # The plan itself was 20x under the cap - the cap bit the PREVIEW, not the plan.
    body = json.dumps(request()["request"], separators=(",", ":")).encode("utf-8")
    assert len(body) < 256_000 // 20


def test_the_fix_reached_the_wire():
    """Attempt 2 got past section validation because wire() stopped emitting the keys."""
    for preset in PRESETS:
        for s in plan(PRESETS[preset]).wire()["sections"]:
            if s["kind"] == "custom":
                assert "sectionKey" not in s
