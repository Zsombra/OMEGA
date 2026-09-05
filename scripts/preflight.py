"""Schema-drift preflight CLI (design: docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md).

  recipe <body.json> --reference <strategyId>
      Print the numbered, read-only session procedure for THIS body: which definition to
      load, which record to read back, exactly where to save each verbatim capture.
  run <body.json> --schema <capture> --readback <capture> [--previous-schema <capture>]
      [--expires-minutes 60] [--out data/audit/compile_preflight_<date>[-<slug>].json]
      [--slug <slug>] [--force] [--now <ISO Z>]
      Diff the body against both captures; write the receipt; print the gate line.
      Refuses to overwrite an existing receipt at the resolved path unless --force is
      given (a FAIL run must not be silently destroyed by a later PASS run on the same
      day). Exit 0 on PASS, 1 on FAIL.
  gate <receipt> --body <body.json> [--now <ISO Z>]
      Exit 0 only if the receipt is PASS, the body sha matches, it has not expired and
      it is not voided.

This script never calls the connector. The captures are agent transcriptions of read-only
calls; `run` checks their fidelity before it trusts them.
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
CAPTURE_SCHEMA_DIR = ROOT / "data" / "contract" / "compile_strategy_plan"
CAPTURE_READBACK_DIR = ROOT / "data" / "contract" / "get_strategy"
AUDIT_DIR = ROOT / "data" / "audit"
TOOL = "mcp__c330236a-7aee-4d07-ae11-e487c8cbc894__compile_strategy_plan"
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


def repo_signal_ids() -> set[str]:
    m = json.loads((ROOT / "data/derived/signal_module_map.json").read_text(encoding="utf-8"))["moduleSignals"]
    return {s for sigs in m.values() for s in sigs}


def repo_template_keys() -> set[str]:
    t = json.loads((ROOT / "data/contract/templates/platform/_all.json").read_text(encoding="utf-8"))["templates"]
    return {e["sectionKey"] for e in t}


def repo_timeframes() -> list[str]:
    return json.loads((ROOT / "data/contract/vocabulary/_shared.json").read_text(encoding="utf-8"))["absoluteTimeframes"]


def _load_body(path: str) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return doc.get("request", doc) if isinstance(doc, dict) else doc


def _load_capture(path: str) -> tuple[dict, dict]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"capturedAt", "how", "request", "response"}
    missing = required - (set(doc.keys()) if isinstance(doc, dict) else set())
    if missing:
        raise SystemExit(f"{path}: not a capture (need capturedAt/how/request/response; missing {sorted(missing)})")
    return doc, doc["response"]


def _now(arg: str | None) -> datetime:
    return P.parse_iso(arg) if arg else datetime.now(timezone.utc).replace(microsecond=0)


def cmd_recipe(a) -> int:
    body = _load_body(a.body)
    stamp = "<YYYYMMDDTHHMMSSZ, the UTC time of the fetch>"
    print(f"""Schema-drift preflight - read-only session procedure for {a.body}
(operation {body.get('operation', '?')}, {len(body.get('conditions', []))} conditions). Nothing below writes to the platform.

1. Load the compile definition (a definition load, NOT a call):
     ToolSearch  select:{TOOL}   max_results 1
   Save the returned definition VERBATIM to
     {CAPTURE_SCHEMA_DIR.relative_to(ROOT).as_posix()}/schema_{stamp}.json
   as {{"capturedAt": "<YYYY-MM-DDTHH:MM:SSZ, fractional seconds accepted>", "how": "ToolSearch select:<tool>", "request": null, "response": <the definition>}}.
   The definition is ~21 KB. If one Write fails or truncates, write it in <= 6 KB chunks and
   concatenate, and say so in "how". Never edit, reorder or repair the text.

2. Read back the reference record (read-only: the 2026-09-04 and 2026-09-05 read-backs of
   b9438519 left its revision at 2 and updatedAt at 2026-08-30T04:41:44Z; whether a read
   touches the strategy quota is not separately measured, but quota counts strategies):
     get_strategy  {{"strategyId": "{a.reference}", "includeInactive": true}}
   Save the response VERBATIM to
     {CAPTURE_READBACK_DIR.relative_to(ROOT).as_posix()}/{a.reference}_{stamp}.json
   as {{"capturedAt": "<YYYY-MM-DDTHH:MM:SSZ, fractional seconds accepted>", "how": "get_strategy", "request": {{...the call...}}, "response": <the response>}}.

3. Run the diff:
     python scripts/preflight.py run {a.body} --schema <step 1 file> --readback <step 2 file>
   It checks the captures' fidelity first (signalId enum == 84 ids, 25 platform section keys,
   13 timeframes; record id, 84 signalRules), then diffs, writes the receipt under
   data/audit/, and prints the gate line.

4. On FAIL: stop. For each MISSING_* finding, mirror the record's value in omega in its own
   commit with tests; if no record carries the field, the user chooses and the receipt
   records it as user-chosen. Re-run step 3 (captures reusable within the expiry window).

5. On PASS: quote the printed gate line in the plan's authorization checkbox, then request
   the doc 20 section 5 authorization sentence from the user exactly as before. The preflight
   changes nothing about who authorizes the compile.""")
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
    readback_doc, record = _load_capture(a.readback)
    now = _now(a.now)
    operation = body.get("operation", "CREATE")
    arms, root = P.resolve_arms(definition)
    if operation not in arms:
        raise SystemExit(f"operation {operation!r} has no arm in the captured definition ({sorted(arms)})")
    arm = arms[operation]
    schema_fp = P.fingerprint_schema(arm, root, signal_ids=repo_signal_ids(),
                                     template_keys=repo_template_keys(), timeframes=repo_timeframes())
    strategy_id = (readback_doc.get("request") or {}).get("strategyId") or P.record_request_view(record).get("id")
    readback_fp = P.fingerprint_readback(record, strategy_id)
    findings: list[P.Finding] = schema_fp + readback_fp
    if not findings:
        findings += P.diff_schema(body, arm, root)
        findings += P.diff_record(body, record, arm, root)
        findings += P.mirror_findings(body, record)
        if a.previous_schema:
            _, prev_def = _load_capture(a.previous_schema)
            prev_arms, prev_root = P.resolve_arms(prev_def)
            if operation in prev_arms:
                findings += P.changelog(P.schema_index(prev_arms[operation], prev_root), P.schema_index(arm, root))
    rec = P.record_request_view(record)
    if a.out:
        out = Path(a.out)
    else:
        slug = f"-{a.slug}" if getattr(a, "slug", None) else ""
        out = AUDIT_DIR / f"compile_preflight_{now.strftime('%Y-%m-%d')}{slug}.json"
    if out.exists() and not getattr(a, "force", False):
        raise SystemExit(f"{out} already exists; refusing to silently overwrite a previous "
                         "receipt (a FAIL followed by a PASS on the same day would destroy the "
                         "FAIL evidence) - pass --force to overwrite, or --slug/--out to pick a "
                         "different name")
    receipt = P.build_receipt(
        body=body, body_path=a.body, operation=operation,
        schema_meta={"path": a.schema, "capturedAt": schema_doc["capturedAt"],
                     "fingerprint": "ok" if not schema_fp else "suspect"},
        readback_meta={"path": a.readback, "capturedAt": readback_doc["capturedAt"], "strategyId": strategy_id,
                       "revision": rec.get("revision"), "fingerprint": "ok" if not readback_fp else "suspect"},
        findings=findings, now=now, expires_minutes=a.expires_minutes, receipt_path=_repo_relative(out),
        unmeasured=["the runtime validator (only a compile observes it)",
                    "whether additionalProperties:false is enforced (schema-derived, not measured)",
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
    print("PREFLIGHT FAIL - stop; mirror from a record, never invent (see the recipe, step 4)")
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
    r = sub.add_parser("recipe"); r.add_argument("body"); r.add_argument("--reference", required=True)
    r.set_defaults(fn=cmd_recipe)
    u = sub.add_parser("run"); u.add_argument("body"); u.add_argument("--schema", required=True)
    u.add_argument("--readback", required=True); u.add_argument("--previous-schema")
    u.add_argument("--expires-minutes", type=int, default=60); u.add_argument("--out"); u.add_argument("--now")
    u.add_argument("--slug"); u.add_argument("--force", action="store_true")
    u.set_defaults(fn=cmd_run)
    g = sub.add_parser("gate"); g.add_argument("receipt"); g.add_argument("--body", required=True); g.add_argument("--now")
    g.set_defaults(fn=cmd_gate)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
