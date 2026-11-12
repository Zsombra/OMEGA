"""Capture the live write surface: data/contract/stage_strategy_draft/schema_<UTC stamp>.json.

The 2026-10-29 .. 2026-11-09 captures were written by session scripts that were not kept; this is the same read as a
script (first run: contract 168.2.0, 2026-11-11). Read-only: `mcporter list battlegrid-anbu --schema --output json`
(the tool list, no tool call) and GET /mcp/version before and after it.

It writes the six draft tools (description / inputSchema / outputSchema / annotations) with:
  contractVersion, buildSha   read from /mcp/version, the SAME before and after the list (else nothing is written);
  liveListSha256, sourceSha256  the sha256 of the listed surface as mcporter printed it;
  readFrom                    what was read, when, and against what it was compared;
  managerRowAgrees            per tool, whether its description / inputSchema / outputSchema equal battlegrid-manager's
                              stored row for the same contract (MANAGER_ROW: the watch's `manager_schemas` row exported
                              to a file, {contractVersion, buildSha, at, hash, tools}); surfaceHash and observedAt are
                              that row's hash and instant. Without MANAGER_ROW they are null and the comparison is
                              recorded as not made;
  _absent                     a tool of the six the live list does not hold.
A manager row for another contract or build is refused: the comparison would mean nothing.

    PATH=<npx shim>:$PATH MANAGER_ROW=<path> python -m scripts.capture_write_surface
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "contract" / "stage_strategy_draft"
TOOLS = ("stage_strategy_draft", "get_strategy_draft", "commit_strategy_draft", "list_strategy_drafts",
         "preview_strategy_report", "get_strategy")
PARTS = ("description", "inputSchema", "outputSchema")
VERSION_URL = os.environ.get("EXTRACTION_VERSION_URL") or "https://mcp.battlegrid.trade/mcp/version"
AUTH_MARKERS = ("/authorize", "If the browser did not open", "OAuth", "Unauthorized", "401")


def read_version() -> dict:
    with urllib.request.urlopen(VERSION_URL, timeout=30) as r:
        body = json.loads(r.read().decode("utf-8"))
    version, build = body.get("contractVersion"), body.get("buildSha")
    if not (isinstance(version, str) and isinstance(build, str)):
        sys.exit(f"{VERSION_URL} did not serve contractVersion / buildSha: {str(body)[:200]}")
    return {"contractVersion": version, "buildSha": build}


def list_surface() -> tuple[bytes, list]:
    """The live tool list as mcporter prints it (bytes, for the hash) and its tools."""
    p = subprocess.run(["cmd", "/c", "npx", "mcporter", "list", "battlegrid-anbu", "--schema", "--output", "json"],
                       capture_output=True, timeout=180)       # an argument list, as scripts/snapshot_vocabulary.py
    err = p.stderr.decode(errors="replace")
    if any(m in err for m in AUTH_MARKERS):
        sys.exit("mcporter asks for an OAuth sign-in: stop (the credential is the user's to renew)")
    if p.returncode != 0 or not p.stdout.strip():
        sys.exit(f"mcporter list failed: {err[:300] or 'empty stdout'}")
    doc = json.loads(p.stdout.decode("utf-8"))
    tools = doc.get("tools") if isinstance(doc, dict) else doc
    if not isinstance(tools, list) or not tools:
        sys.exit("the listed surface holds no tools")
    return p.stdout, tools


def capture(*, version: dict, raw: bytes, tools: list, manager_row: dict | None, row_name: str | None,
            listed_at: datetime) -> dict:
    by_name = {t.get("name"): t for t in tools if isinstance(t, dict)}
    absent = [t for t in TOOLS if t not in by_name]
    digest = hashlib.sha256(raw).hexdigest()
    stamp = listed_at.strftime("%Y-%m-%dT%H:%MZ")
    read_from = (f"the live surface listed {stamp} (mcporter list battlegrid-anbu --schema --output json, "
                 f"{len(tools)} tools, GET /mcp/version {version['contractVersion']} / {version['buildSha'][:8]} "
                 f"before and after)")
    agrees: dict | None = None
    surface_hash = observed_at = None
    if manager_row is not None:
        if (manager_row.get("contractVersion"), manager_row.get("buildSha")) != (version["contractVersion"],
                                                                                 version["buildSha"]):
            sys.exit(f"MANAGER_ROW is {manager_row.get('contractVersion')} / {str(manager_row.get('buildSha'))[:8]}, "
                     f"the live surface {version['contractVersion']} / {version['buildSha'][:8]}: not comparable")
        rows = manager_row.get("tools")
        missing = [t for t in TOOLS if not isinstance(rows, dict) or t not in rows]
        if missing:
            # a row that lacks a tool compares nothing for it: "agrees on all six" over fewer than six is not agreement
            sys.exit(f"MANAGER_ROW holds no row for {missing}: the comparison would not cover the six draft tools")
        agrees = {t: {part: by_name[t].get(part) == rows[t].get(part) for part in PARTS}
                  for t in TOOLS if t in by_name}
        surface_hash = manager_row.get("hash")
        observed_at = str(manager_row.get("at", ""))[:19] + "Z" if manager_row.get("at") else None
        read_from += (f"; each of the six draft tools' description / inputSchema / outputSchema compared to "
                      f"battlegrid-manager's stored observed {version['contractVersion']} manager_schemas row "
                      f"({row_name}, hash {str(surface_hash)[:8]})")
    else:
        read_from += "; no battlegrid-manager row was given, so no comparison was made"
    doc = {"contractVersion": version["contractVersion"], "buildSha": version["buildSha"],
           "surfaceHash": surface_hash, "observedAt": observed_at, "readFrom": read_from,
           "sourceSha256": digest, "liveListSha256": digest, "_absent": absent, "managerRowAgrees": agrees}
    for t in TOOLS:
        if t in by_name:
            doc[t] = {k: by_name[t].get(k) for k in ("description", "inputSchema", "outputSchema", "annotations")}
    return doc


def main() -> int:
    before = read_version()
    listed_at = datetime.now(UTC)
    raw, tools = list_surface()
    after = read_version()
    if before != after:
        sys.exit(f"the contract moved during the list ({before} -> {after}): nothing written, run again")
    row_path = os.environ.get("MANAGER_ROW")
    row = json.loads(Path(row_path).read_text(encoding="utf-8")) if row_path else None
    doc = capture(version=before, raw=raw, tools=tools, manager_row=row,
                  row_name=Path(row_path).name if row_path else None, listed_at=listed_at)
    if doc["_absent"]:
        sys.exit(f"the live surface lacks {doc['_absent']}: nothing written")
    out = OUT_DIR / f"schema_{listed_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    disagree = {t: [p for p, ok in parts.items() if not ok] for t, parts in (doc["managerRowAgrees"] or {}).items()
                if not all(parts.values())}
    print(f"wrote {out.relative_to(ROOT).as_posix()}: {doc['contractVersion']} / {doc['buildSha'][:8]}, "
          f"{len(tools)} tools listed, sha256 {doc['liveListSha256'][:8]}; "
          f"manager row {'not given' if row is None else ('agrees on all six' if not disagree else f'DISAGREES: {disagree}')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
