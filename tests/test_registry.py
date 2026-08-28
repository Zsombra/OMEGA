"""The advisor-ready creation registry and the prepare-never-execute checklist
(design 2026-08-29). The backfilled entry for 6a8bca67 is the registry's first
citizen - the strategy whose create (2026-08-28) and revise (2026-08-29) loops are
already on the record."""
from __future__ import annotations

import json
from pathlib import Path

from omega.registry import CREATED_DIR, checklist, load, new_entry, add_revision

ROOT = Path(__file__).resolve().parents[1]
SIX_A = "6a8bca67-45a3-428e-85ba-71ec2cd2218e"


def test_entry_roundtrip(tmp_path, monkeypatch):
    import omega.registry as R
    monkeypatch.setattr(R, "CREATED_DIR", tmp_path)
    e = new_entry("test-id", "2026-08-29", None, "data/audit/x.json", "archived")
    e = add_revision(e, "2026-08-29", 2, "archived after verification",
                     "data/audit/x.json")
    p = R.save(e)
    assert p.parent == tmp_path
    assert R.load("test-id") == e
    assert e["auditRecords"] == ["data/audit/x.json"]     # deduped


def test_the_backfilled_entry_matches_the_audit_records():
    e = load(SIX_A)
    assert e["id"] == SIX_A
    assert e["createdDate"] == "2026-08-28"
    assert e["disposition"] == "archived"
    assert [r["revision"] for r in e["revisions"]] == [2, 3, 4, 5]
    assert "data/audit/first_generated_apply_2026-08-28.json" in e["auditRecords"]
    assert "data/audit/first_generated_update_2026-08-29.json" in e["auditRecords"]
    assert e["thesis"]["execution"] == {"minRiskRewardRatio": 2.0}


def test_the_checklist_prepares_and_never_executes():
    text = checklist(load(SIX_A))
    assert SIX_A in text
    assert "restore_strategy" in text
    assert "rebind_intelligence_agent" in text
    assert "upsert_radar_deployment" in text
    assert "real capital" in text
    assert "never executes" in text
    assert "unverified" in text        # app-UI specifics labeled, not invented


def test_the_committed_checklist_matches_the_generator():
    committed = (CREATED_DIR / f"{SIX_A}.checklist.md").read_text(encoding="utf-8")
    assert committed == checklist(load(SIX_A))
