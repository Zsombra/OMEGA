"""Schema-drift preflight CLI (design: docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md),
at contract 108: the body is a stage_strategy_draft request of eight axes, walked axis by axis (SIGNAL_RULES and
SETUP_GATES are refused since 108.0.0; the signalId fingerprint went with them).

  recipe <body.json>
      Print the numbered, read-only session procedure for THIS body: which definition to
      load and exactly where to save the verbatim capture.
  run <body.json> --schema <capture> [--previous-schema <capture>]
      [--expires-minutes 60] [--out data/audit/stage_preflight_<date>[-<slug>].json]
      [--slug <slug>] [--force] [--now <ISO Z>]
      Walk the body against the capture; write the receipt; print the gate line.
      Refuses to overwrite an existing receipt at the resolved path unless --force is
      given (a FAIL run must not be silently destroyed by a later PASS run on the same
      day). Exit 0 on PASS, 1 on FAIL.
  gate <receipt> --body <body.json> [--now <ISO Z>]
      Exit 0 only if the receipt is PASS, the body sha matches, it has not expired and
      it is not voided.

The body file is a stage request - {"request": {draftVersion, axes, strategyId?}} or the
request object itself, as omega.generate.emit_plan writes it; top-level "_"-prefixed keys
are local metadata and are stripped before the walk and the sha.

compile_strategy_plan was removed at contract 85.0.0, and the read-back mirror is retired
until a v91 read-back is captured (every get_strategy record on disk predates v84 and
carries `closes`/`exit`): `run` takes no --readback (plan 2026-10-06, Work step 4). The
compile-era receipts under data/audit/compile_preflight_*.json stay as history.

This script never calls the connector. The capture is an agent transcription of a
read-only definition load; `run` checks its fidelity before it trusts it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omega import preflight as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCHEMA_DIR = ROOT / "data" / "contract" / "stage_strategy_draft"
AUDIT_DIR = ROOT / "data" / "audit"
TOOL = "mcp__c330236a-7aee-4d07-ae11-e487c8cbc894__stage_strategy_draft"
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


def repo_template_keys() -> set[str]:
    t = json.loads((ROOT / "data/contract/templates/platform/_all.json").read_text(encoding="utf-8"))["templates"]
    return {e["sectionKey"] for e in t}


def repo_timeframes() -> list[str]:
    return json.loads((ROOT / "data/contract/vocabulary/_shared.json").read_text(encoding="utf-8"))["absoluteTimeframes"]


def _load_body(path: str) -> dict:
    """The stage request object. emit_plan's local metadata ("_"-prefixed keys) never goes
    to the API, so it is no part of what is walked or hashed."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    req = doc.get("request", doc) if isinstance(doc, dict) else doc
    return {k: v for k, v in req.items() if not k.startswith("_")} if isinstance(req, dict) else req


def _load_capture(path: str) -> tuple[dict, dict]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"capturedAt", "how", "request", "response"}
    missing = required - (set(doc.keys()) if isinstance(doc, dict) else set())
    if missing:
        raise SystemExit(f"{path}: not a capture (need capturedAt/how/request/response; missing {sorted(missing)})")
    return doc, doc["response"]


def _now(arg: str | None) -> datetime:
    return P.parse_iso(arg) if arg else datetime.now(timezone.utc).replace(microsecond=0)


def _operation(body: dict) -> str:
    """v85: a stage with no strategyId opens a NEW create draft."""
    return "UPDATE" if body.get("strategyId") else "CREATE"


def cmd_recipe(a) -> int:
    body = _load_body(a.body)
    axes = body.get("axes", {}) if isinstance(body, dict) else {}
    conds = (axes.get("CONDITIONS") or {}).get("conditions", [])
    stamp = "<YYYYMMDDTHHMMSSZ, the UTC time of the fetch>"
    print(f"""Schema-drift preflight - read-only session procedure for {a.body}
({_operation(body)} stage, {len(axes)} axes, {len(conds)} conditions). Nothing below writes to the platform.

1. Load the stage_strategy_draft definition (a definition load, NOT a call):
     ToolSearch  select:{TOOL}   max_results 1
   Save the returned definition VERBATIM to
     {CAPTURE_SCHEMA_DIR.relative_to(ROOT).as_posix()}/schema_{stamp}.json
   as {{"capturedAt": "<YYYY-MM-DDTHH:MM:SSZ, fractional seconds accepted>", "how": "ToolSearch select:<tool>", "request": null, "response": <the definition>}}.
   The definition is ~15 KB compact (~32 KB indented; measured on the saved 108.0.0 copy). If one Write fails or truncates, write it in <= 6 KB chunks and
   concatenate, and say so in "how". Never edit, reorder or repair the text.

2. No read-back: the get_strategy mirror is retired until a v91 read-back is captured (every
   record on disk predates contract 84 and carries `closes`/`exit`).

3. Run the walk:
     python scripts/preflight.py run {a.body} --schema <step 1 file>
   It checks the capture's fidelity first (the eight axes of 108.0.0; 25 platform section keys,
   13 timeframes), then walks every axis, writes the receipt under data/audit/,
   and prints the gate line.

4. On FAIL: stop. For each MISSING_* finding, mirror the value from the changelog or a record
   in omega in its own commit with tests; if neither carries it, the user chooses and the
   receipt records it as user-chosen. Re-run step 3 (the capture is reusable within the expiry
   window).

5. On PASS: quote the printed gate line in the plan's authorization checkbox, then ask the
   user for the stage. A stage is a WRITE into the player's draft and a commit publishes it;
   the preflight changes nothing about who authorizes either.""")
    return 0


def _repo_relative(path: Path) -> str:
    """Receipts are committed; a machine-absolute path in the gate line would make them
    machine-specific. Under the repo root the path is recorded repo-relative (posix)."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def cmd_run(a) -> int:
    if getattr(a, "slug", None) and not _SLUG_RE.match(a.slug):
        raise SystemExit(f"--slug {a.slug!r}: use letters, digits, '-' or '_' (max 40)")
    body = _load_body(a.body)
    schema_doc, definition = _load_capture(a.schema)
    now = _now(a.now)
    operation = _operation(body)
    request_schema, root = P.resolve_request(definition)
    axis_schemas, _ = P.resolve_axes(definition)
    findings: list[P.Finding] = P.fingerprint_axes(
        axis_schemas, root, template_keys=repo_template_keys(), timeframes=repo_timeframes())
    schema_fp_ok = not findings
    if schema_fp_ok:
        findings += P.diff_schema(body, request_schema, root)
        if a.previous_schema:
            _, prev_def = _load_capture(a.previous_schema)
            prev_request, prev_root = P.resolve_request(prev_def)
            findings += P.changelog(P.schema_index(prev_request, prev_root),
                                    P.schema_index(request_schema, root))
    if a.out:
        out = Path(a.out)
    else:
        slug = f"-{a.slug}" if getattr(a, "slug", None) else ""
        out = AUDIT_DIR / f"stage_preflight_{now.strftime('%Y-%m-%d')}{slug}.json"
    if out.exists() and not getattr(a, "force", False):
        raise SystemExit(f"{out} already exists; refusing to silently overwrite a previous "
                         "receipt (a FAIL followed by a PASS on the same day would destroy the "
                         "FAIL evidence) - pass --force to overwrite, or --slug/--out to pick a "
                         "different name")
    receipt = P.build_receipt(
        body=body, body_path=a.body, operation=operation,
        schema_meta={"path": a.schema, "capturedAt": schema_doc["capturedAt"],
                     "fingerprint": "ok" if schema_fp_ok else "suspect"},
        readback_meta=None,
        findings=findings, now=now, expires_minutes=a.expires_minutes, receipt_path=_repo_relative(out),
        unmeasured=["the builder's judgement (a stage's diagnostics observe it; a stage is a write)",
                    "whether additionalProperties:false is enforced (schema-derived, not measured)",
                    "the operator bounds a create is judged at since v89 (served in diagnostics)",
                    "semantics of any field first seen in this capture"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for f in findings:
        print(f"  [{f.verdict:4}] {f.cls:20} {f.path or '<root>'}: {f.detail}")
    print(f"receipt: {out}")
    if receipt["verdict"] == "PASS":
        print(P.gate_line(receipt, _repo_relative(out)))
        print(f"note: {P.DISCLAIMER}")
        return 0
    print("PREFLIGHT FAIL - stop; mirror from the changelog or a record, never invent (see the recipe, step 4)")
    return 1


def cmd_gate(a) -> int:
    receipt = json.loads(Path(a.receipt).read_text(encoding="utf-8"))
    ok, why = P.gate_check(receipt, _load_body(a.body), _now(a.now))
    if ok:
        print(P.gate_line(receipt, a.receipt))
        print(f"note: {P.DISCLAIMER}")
    else:
        print(f"PREFLIGHT GATE REFUSED: {why}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recipe"); r.add_argument("body")
    r.set_defaults(fn=cmd_recipe)
    u = sub.add_parser("run"); u.add_argument("body"); u.add_argument("--schema", required=True)
    u.add_argument("--previous-schema")
    u.add_argument("--expires-minutes", type=int, default=60); u.add_argument("--out"); u.add_argument("--now")
    u.add_argument("--slug"); u.add_argument("--force", action="store_true")
    u.set_defaults(fn=cmd_run)
    g = sub.add_parser("gate"); g.add_argument("receipt"); g.add_argument("--body", required=True); g.add_argument("--now")
    g.set_defaults(fn=cmd_gate)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
