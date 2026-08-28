"""The advisor-ready creation registry and the prepare-never-execute checklist
(design 2026-08-29). One committed JSON per assistant-created strategy so that IF
the user ever lets one trade, performance can attach later without rework. The
checklist NAMES the capital-bearing steps for the user; nothing here executes them."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

CREATED_DIR = Path(__file__).resolve().parents[1] / "data" / "created"


def new_entry(strategy_id: str, created_date: str, thesis,
              audit_record: str, disposition: str) -> dict:
    return {"id": strategy_id, "createdDate": created_date,
            "thesis": asdict(thesis) if is_dataclass(thesis) else thesis,
            "revisions": [], "disposition": disposition,
            "auditRecords": [audit_record]}


def add_revision(entry: dict, date: str, revision: int, change: str,
                 audit_record: str) -> dict:
    entry["revisions"].append({"date": date, "revision": revision, "change": change})
    if audit_record not in entry["auditRecords"]:
        entry["auditRecords"].append(audit_record)
    return entry


def save(entry: dict) -> Path:
    CREATED_DIR.mkdir(parents=True, exist_ok=True)
    p = CREATED_DIR / f"{entry['id']}.json"
    p.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    return p


def load(strategy_id: str) -> dict:
    return json.loads((CREATED_DIR / f"{strategy_id}.json").read_text(encoding="utf-8"))


def checklist(entry: dict) -> str:
    """The prepare-never-execute checklist (phase decision 4, 2026-08-28): the exact
    manual steps the USER would take to let this strategy trade. The assistant never
    executes any of them - these steps move real capital."""
    sid = entry["id"]
    return "\n".join([
        f"# Letting {sid} trade - the steps YOU would take",
        "",
        "> Binding and deployment move **real capital**. The assistant prepares this",
        "> list and never executes it; no general 'go ahead' authorises these steps.",
        "",
        f"1. Review the registry entry (`data/created/{sid}.json`), its audit",
        "   records, and the latest brief. Confirm this is the revision you mean.",
        f"2. If archived (disposition: {entry['disposition']}): restore it yourself -",
        f"   `restore_strategy` with strategyId `{sid}` and the CURRENT revision",
        "   (read it first with `get_strategy includeInactive:true`; never assume).",
        "3. Bind it to an agent yourself: `rebind_intelligence_agent` with an agentId",
        "   you choose and this strategyId. The agent's capital settings (exposure,",
        "   drawdown, daily-loss caps) live on the agent, not the strategy - review",
        "   them first. Exact request fields: read the tool's schema at call time",
        "   (unverified here - no bind has ever been executed from this repo).",
        "4. Give it per-coin trade authority yourself: `upsert_radar_deployment` per",
        "   coin. Also unverified here, for the same reason.",
        "5. Watch the first sessions (`get_agent_activity_feed`, open positions) and",
        "   record outcomes back into the registry entry so performance attaches to",
        "   this strategy's history.",
        "",
        "The assistant never executes steps 2-4. This list prepares; you decide.",
    ])
