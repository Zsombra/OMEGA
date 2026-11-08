"""Snapshot the served strategy vocabulary: list_strategy_categories + list_strategy_vocabulary per category.

The 2026-10-26 .. 2026-11-05 snapshots (data/contract/vocabulary/<stamp>/) were read by session scripts that were not
kept; this is the same read as a script. Read-only: the two list tools over mcporter (battlegrid-anbu), nothing else.
Writes the raw answers to data/contract/vocabulary/<UTC stamp>/ (one file per category, `_categories.json`), then
compares the category-invariant blocks across every category read and, only when they agree, writes them into
vocabulary/_shared.json (the old `_refreshed` kept under `previous`) and the category counts into categories.json.
A category the platform refuses (`structure` is RESULT_TOO_LARGE since 148.1.0) is stored as its refusal; only the
codes in KNOWN_REFUSALS are. Any other answer that is not a vocabulary stops the run (the raw dir is kept), and the
shared blocks are rewritten only when every category answered or was refused with a known code.

    PATH=<npx shim>:$PATH python -m scripts.snapshot_vocabulary
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOCAB = ROOT / "data" / "contract" / "vocabulary"
READ_TOOLS = ("list_strategy_categories", "list_strategy_vocabulary")
# the blocks every category's answer repeats; _shared.json holds them once
INVARIANT = ("transforms", "timeframeRefs", "budgets", "previewExecutionLimits", "timeframes", "rankedTimeframes",
             "conditionGrammar")
AUTH_MARKERS = ("/authorize", "If the browser did not open", "OAuth", "Unauthorized", "401")
# The platform refusals stored as a category's answer (a fact about that category at this contract). Any other `code`
# (SERVICE_UNAVAILABLE - the 15 s deadline, RATE_LIMITED, INTERNAL_ERROR ...) or a body with no `transforms` stops the
# run with nothing rewritten (2026-11-08, review pass 1 finding 5): read as "refused", a deadline became a platform
# fact in `_refreshed.how`, and an unrecognised body on every category overwrote the invariant blocks with null.
KNOWN_REFUSALS = frozenset({"RESULT_TOO_LARGE"})


def version() -> dict:
    with urllib.request.urlopen("https://mcp.battlegrid.trade/mcp/version", timeout=30) as r:
        return json.loads(r.read().decode())


def call(tool: str, args: dict, timeout: int = 240) -> dict:
    assert tool in READ_TOOLS, tool
    time.sleep(0.45)
    p = subprocess.run(["cmd", "/c", "npx", "mcporter", "call", f"battlegrid-anbu.{tool}", "--output", "json",
                        "--args", "-"], input=json.dumps(args).encode(), capture_output=True, timeout=timeout)
    out, err = p.stdout.decode("utf-8", errors="replace"), p.stderr.decode("utf-8", errors="replace")
    if not out.strip():
        if any(m in err for m in AUTH_MARKERS):
            sys.exit(f"mcporter has no usable credential for battlegrid-anbu (re-authorizing is the user's step): "
                     f"{err[:300]}")
        sys.exit(f"{tool}: no answer: {err[:300]}")
    return json.loads(out)


def main() -> int:
    v0 = version()
    stamp = time.strftime("%Y%m%dT%H%MZ", time.gmtime())
    out_dir = VOCAB / stamp
    if out_dir.exists():
        sys.exit(f"{out_dir} exists")
    out_dir.mkdir()
    cats = call("list_strategy_categories", {})
    (out_dir / "_categories.json").write_text(json.dumps(cats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not isinstance(cats, dict) or not isinstance(cats.get("categories"), list) or not cats["categories"]:
        sys.exit(f"list_strategy_categories answered no category list: {json.dumps(cats)[:300]}; raw kept in {out_dir}, "
                 "nothing else written")
    names = [c["category"] for c in cats["categories"]]
    answers, refused = {}, {}
    for name in names:
        d = call("list_strategy_vocabulary", {"category": name})
        (out_dir / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if isinstance(d, dict) and "transforms" in d:
            answers[name] = d
        elif isinstance(d, dict) and d.get("code") in KNOWN_REFUSALS:
            refused[name] = d.get("code")
        else:
            # a deadline / rate limit / outage, or a body that is neither a vocabulary nor a known refusal: not a fact
            # about the category, so nothing is rewritten from a partial read
            sys.exit(f"{name}: not a vocabulary and not a known refusal ({sorted(KNOWN_REFUSALS)}): "
                     f"{json.dumps(d)[:300]}; raw kept in {out_dir}, nothing else written")
        print(f"  {name}: {'REFUSED ' + str(d.get('code')) if name in refused else 'ok'}", flush=True)
    unanswered = [n for n in names if n not in answers and n not in refused]
    if unanswered or not answers:
        sys.exit(f"categories without an answer {unanswered} (answered {len(answers)}, refused {refused}): raw kept in "
                 f"{out_dir}, nothing else written")
    v1 = version()
    if (v0.get("contractVersion"), v0.get("buildSha")) != (v1.get("contractVersion"), v1.get("buildSha")):
        sys.exit(f"the contract moved during the read ({v0} -> {v1}): raw kept in {out_dir}, nothing else written")
    first = next(iter(answers.values()))
    differ = [k for k in INVARIANT if any(a.get(k) != first.get(k) for a in answers.values())]
    if differ:
        sys.exit(f"category-invariant blocks differ across categories: {differ}; raw kept in {out_dir}")

    shared_path = VOCAB / "_shared.json"
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    moved = [k for k in INVARIANT if shared.get(k) != first.get(k)]
    at = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}T{stamp[9:11]}:{stamp[11:13]}Z"
    for k in INVARIANT:
        shared[k] = first.get(k)
    shared["_refreshed"] = {
        "at": at, "contractVersion": v0.get("contractVersion"),
        "how": (f"scripts/snapshot_vocabulary.py: list_strategy_vocabulary per category via the mcporter CLI "
                f"(read-only); raw responses in data/contract/vocabulary/{stamp}/" +
                (f"; refused: {refused}" if refused else "")),
        "moved": moved or ["nothing: every category-invariant block is as stored"],
        "previous": shared.get("_refreshed")}
    shared_path.write_text(json.dumps(shared, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    cat_path = ROOT / "data" / "contract" / "categories.json"
    stored = json.loads(cat_path.read_text(encoding="utf-8"))
    before = {c["category"]: c["metricCount"] for c in stored["categories"]}
    after = {c["category"]: c["metricCount"] for c in cats["categories"]}
    cat_moved = [f"{k} {before.get(k)} -> {after.get(k)}" for k in sorted(set(before) | set(after))
                 if before.get(k) != after.get(k)]
    stored["categories"] = cats["categories"]
    if "modules" in cats:
        cat_moved += [] if cats["modules"] == stored.get("modules") else ["modules"]
        stored["modules"] = cats["modules"]
    stored["_refreshed"] = {"at": at, "contractVersion": v0.get("contractVersion"),
                            "how": f"list_strategy_categories via the mcporter CLI (read-only), "
                                   f"data/contract/vocabulary/{stamp}/_categories.json",
                            "moved": cat_moved or ["nothing"], "previous": stored.get("_refreshed")}
    cat_path.write_text(json.dumps(stored, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out_dir}; _shared.json moved {moved}; categories moved {cat_moved}; refused {refused}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
