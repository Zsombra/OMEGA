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

Since 2026-11-20 (contract 182.3.2) the same list also writes authoring_tools_<UTC stamp>.json: the OTHER tools an
authoring pass calls (AUTHORING_TOOLS: the trade level preview, the discard, the hints, the vocabulary, the column
contract, the section templates, the strategy list, the saved sections), with the same contractVersion / buildSha /
liveListSha256. The captures through 180.4.0 held the six draft tools only, so the 180.4.0 -> 182.3.2 pass had nothing
of OMEGA's to diff these against (preview_strategy_trade_levels' description moved at 182.3.x and was read from
battlegrid-manager's audit event). A tool of AUTHORING_TOOLS the list lacks is named in `_absent`, not fatal.

    python -m scripts.capture_write_surface --authoring-only <schema_....json>
writes the sidecar alone, beside a capture already taken: the list must be of that capture's contract and build and
its six draft tools must equal the capture's (description / inputSchema / outputSchema), else nothing is written.

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
AUTHORING_TOOLS = ("preview_strategy_trade_levels", "discard_strategy_draft", "get_metric_construction_hints",
                   "list_strategy_vocabulary", "list_strategy_categories", "get_strategy_column_contract",
                   "get_strategy_section_template", "list_strategies", "save_report_section",
                   "remove_saved_report_section")
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


def authoring_tools(*, version: dict, raw: bytes, tools: list, listed_at: datetime, beside: dict | None = None,
                    beside_name: str | None = None) -> dict:
    """The sidecar: AUTHORING_TOOLS as listed (description / inputSchema / outputSchema / annotations), keyed under
    `tools`. From the capture's own list (the same liveListSha256), or - `beside`, a capture already on disk - from a
    later list of the same contract and build whose six draft tools equal that capture's; any difference exits with
    nothing written, because the sidecar would then describe another surface than the capture it sits beside."""
    by_name = {t.get("name"): t for t in tools if isinstance(t, dict)}
    read_from = (f"the live surface listed {listed_at.strftime('%Y-%m-%dT%H:%MZ')} (mcporter list battlegrid-anbu "
                 f"--schema --output json, {len(tools)} tools, GET /mcp/version {version['contractVersion']} / "
                 f"{version['buildSha'][:8]} before and after)")
    if beside is None:
        read_from += f", the list of the schema_{listed_at.strftime('%Y%m%dT%H%M%SZ')}.json capture beside it"
    else:
        if (beside.get("contractVersion"), beside.get("buildSha")) != (version["contractVersion"], version["buildSha"]):
            sys.exit(f"{beside_name} is {beside.get('contractVersion')} / {str(beside.get('buildSha'))[:8]}, the live "
                     f"surface {version['contractVersion']} / {version['buildSha'][:8]}: not the same surface")
        moved = [f"{t}.{part}" for t in TOOLS for part in PARTS
                 if (by_name.get(t) or {}).get(part) != (beside.get(t) or {}).get(part)]
        if moved:
            sys.exit(f"the six draft tools of this list differ from {beside_name}: {moved}; nothing written")
        read_from += (f"; a later list than {beside_name}'s, of the same contract and build, whose six draft tools "
                      f"equal that capture's on description / inputSchema / outputSchema")
    return {"contractVersion": version["contractVersion"], "buildSha": version["buildSha"],
            "liveListSha256": hashlib.sha256(raw).hexdigest(),
            "beside": beside_name or f"schema_{listed_at.strftime('%Y%m%dT%H%M%SZ')}.json", "readFrom": read_from,
            "_absent": [t for t in AUTHORING_TOOLS if t not in by_name],
            "tools": {t: {k: by_name[t].get(k) for k in ("description", "inputSchema", "outputSchema", "annotations")}
                      for t in AUTHORING_TOOLS if t in by_name}}


def _shown(path: Path) -> str:
    """A written file as the console names it: relative to the repository when it is inside it."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _write(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    """One list of the live surface -> the capture AND its sidecar (the default), or the sidecar alone beside a
    capture already on disk (`--authoring-only <schema_....json>`). Both documents are built before either is
    written, so a list one of them refuses writes nothing."""
    argv = sys.argv[1:] if argv is None else argv
    before = read_version()
    listed_at = datetime.now(UTC)
    raw, tools = list_surface()
    after = read_version()
    if before != after:
        sys.exit(f"the contract moved during the list ({before} -> {after}): nothing written, run again")
    stamp = listed_at.strftime("%Y%m%dT%H%M%SZ")
    side_out = OUT_DIR / f"authoring_tools_{stamp}.json"

    def absent(side: dict) -> str:
        return f" (absent: {', '.join(side['_absent'])})" if side["_absent"] else ""

    if "--authoring-only" in argv:
        name = argv[argv.index("--authoring-only") + 1]
        beside = json.loads((OUT_DIR / name).read_text(encoding="utf-8"))
        side = authoring_tools(version=before, raw=raw, tools=tools, listed_at=listed_at, beside=beside,
                               beside_name=name)
        _write(side_out, side)
        print(f"wrote {_shown(side_out)} beside {name}: {len(side['tools'])} of {len(AUTHORING_TOOLS)} authoring "
              f"tools{absent(side)}")
        return 0
    row_path = os.environ.get("MANAGER_ROW")
    row = json.loads(Path(row_path).read_text(encoding="utf-8")) if row_path else None
    doc = capture(version=before, raw=raw, tools=tools, manager_row=row,
                  row_name=Path(row_path).name if row_path else None, listed_at=listed_at)
    if doc["_absent"]:
        sys.exit(f"the live surface lacks {doc['_absent']}: nothing written")
    # the sidecar of THIS list: the same tools, the same liveListSha256, beside the capture it names
    side = authoring_tools(version=before, raw=raw, tools=tools, listed_at=listed_at)
    out = OUT_DIR / f"schema_{stamp}.json"
    _write(out, doc)
    _write(side_out, side)
    disagree = {t: [p for p, ok in parts.items() if not ok] for t, parts in (doc["managerRowAgrees"] or {}).items()
                if not all(parts.values())}
    print(f"wrote {_shown(out)}: {doc['contractVersion']} / {doc['buildSha'][:8]}, "
          f"{len(tools)} tools listed, sha256 {doc['liveListSha256'][:8]}; "
          f"manager row {'not given' if row is None else ('agrees on all six' if not disagree else f'DISAGREES: {disagree}')}")
    print(f"wrote {_shown(side_out)}: {len(side['tools'])} of {len(AUTHORING_TOOLS)} authoring tools{absent(side)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
