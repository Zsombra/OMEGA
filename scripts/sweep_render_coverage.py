"""Close the live-render coverage gap left by the 2026-09-09 corpus refresh.

Renders every uncovered shape through preview_strategy_report (read-only: it renders without
saving or mutating strategy state) and records the headers the platform actually mints.

Two output files, deliberately separate:
  data/contract/columns/_coverage_sweep_2026-09-09.json  - headers ONLY. This file is read by
      scripts/render_coverage.rendered_headers, which walks any JSON and treats every string
      as a seen header, so nothing but real headers may go in it.
  data/audit/coverage_sweep_2026-09-09.json - the run record: batches, refusals, and any
      shape whose rendered header disagreed with omega.fanout.outputs_for.

A refused batch is bisected down to the offending column so the refusal is attributed
exactly, never written off as "the batch failed".
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, ".")
from omega.contract import load                      # noqa: E402
from omega.fanout import outputs_for                 # noqa: E402
from scripts.render_coverage import (                # noqa: E402
    QUARANTINED, coverage, is_placeholder, rendered_headers,
)

COLS_PER_SECTION = 32
SECTIONS_PER_CALL = 8
HEADERS_OUT = "data/contract/columns/_coverage_sweep_2026-09-09.json"
RECORD_OUT = "data/audit/coverage_sweep_2026-09-09.json"
NOTE = "OMEGA read-only coverage sweep 2026-09-09"


def call(tool, args, timeout=240):
    p = subprocess.Popen(
        ["cmd", "/c", "npx", "mcporter", "call", f"battlegrid-anbu.{tool}",
         "--output", "json", "--args", "-"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(json.dumps(args).encode(), timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        return None, "TIMEOUT"
    txt = out.decode(errors="replace")
    if not txt.strip():
        return None, (err.decode(errors="replace") or "empty stdout")[:400]
    try:
        return json.loads(txt), None
    except json.JSONDecodeError:
        return None, txt[:400]


def render(columns):
    """-> (headers, error). One preview carrying `columns` split across sections."""
    secs = []
    for i in range(0, len(columns), COLS_PER_SECTION):
        secs.append({"kind": "custom", "title": f"sweep {len(secs) + 1}",
                     "benchmarkTicker": None, "notes": NOTE,
                     "columns": columns[i:i + COLS_PER_SECTION]})
    req = {"timeframe": "1h", "coinSelection": {"mode": "explicit", "tickers": ["BTC"]},
           "sections": secs}
    d, err = call("preview_strategy_report", req)
    if d is None:
        return None, err
    if "budgetUsage" not in d:
        return None, json.dumps(d)[:400]
    hdrs = []
    for cc in d.get("conditionColumns", []):
        if str(cc.get("title", "")).startswith("sweep "):
            hdrs += [o["header"] for o in cc["outputs"]]
    return hdrs, None


def bisect(columns, refusals, depth=0):
    """Attribute a refusal to the exact column(s)."""
    if len(columns) == 1:
        hdrs, err = render(columns)
        if err:
            refusals.append({"column": columns[0], "error": err[:300]})
            return []
        return hdrs
    mid = len(columns) // 2
    out = []
    for half in (columns[:mid], columns[mid:]):
        hdrs, err = render(half)
        if err:
            out += bisect(half, refusals, depth + 1)
        else:
            out += hdrs
    return out


c = load()
seen_before = rendered_headers()

# every uncovered shape, structural and operand-expanded, deduped by its column payload
targets, keys = [], set()
for expand in (False, True):
    _, unc, _ = coverage(expand, c)
    for s in unc:
        col = s.to_column().model_dump(exclude_none=True)
        k = json.dumps(col, sort_keys=True)
        if k in keys:
            continue
        keys.add(k)
        targets.append((s, col))
print(f"uncovered shapes to render: {len(targets)}")

per_call = COLS_PER_SECTION * SECTIONS_PER_CALL
all_headers, refusals, batches = [], [], []
t0 = time.time()
for i in range(0, len(targets), per_call):
    chunk = targets[i:i + per_call]
    cols = [col for _, col in chunk]
    hdrs, err = render(cols)
    if err:
        print(f"  batch {i // per_call + 1}: REFUSED, bisecting ({err[:90]})")
        hdrs = bisect(cols, refusals)
    all_headers += hdrs
    batches.append({"batch": i // per_call + 1, "columns": len(cols), "headers": len(hdrs)})
    done = min(i + per_call, len(targets))
    print(f"  [{done}/{len(targets)}] headers so far {len(set(all_headers))} "
          f"refusals {len(refusals)} ({round(time.time() - t0)}s)")

headers = sorted(set(all_headers))
os.makedirs(os.path.dirname(HEADERS_OUT), exist_ok=True)
json.dump({"_what": ("Headers minted live by preview_strategy_report during the 2026-09-09 "
                     "coverage sweep. HEADERS ONLY - render_coverage treats every string in "
                     "this file as a seen header, so nothing else may be added here."),
           "headers": headers},
          open(HEADERS_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# header agreement: does omega predict what the platform minted?
mismatches = []
for s, col in targets:
    pred = [o.header for o in outputs_for(s.to_column(), c)]
    missing = [h for h in pred if h not in set(headers) | seen_before]
    if missing:
        mismatches.append({"shape": f"{s.metric}|{s.transform}|{s.chained}|{s.operand}|{s.ordering}",
                           "predicted": pred, "notRendered": missing})
json.dump({"_what": ("Run record for the 2026-09-09 live coverage sweep: what was asked for, what "
                     "the platform refused, and every shape whose omega-predicted header did not "
                     "turn up in the render. Kept OUT of data/contract/columns/ so none of these "
                     "strings can be mistaken for a rendered header."),
           "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "how": ("preview_strategy_report via the mcporter CLI, read-only, BTC only, "
                   f"{COLS_PER_SECTION} columns per custom section, up to {SECTIONS_PER_CALL} "
                   "sections per call; refused batches bisected to the offending column."),
           "shapesRequested": len(targets), "batches": batches,
           "headersMinted": len(headers),
           "refusalCount": len(refusals), "refusals": refusals,
           "predictedButNotRenderedCount": len(mismatches),
           "predictedButNotRendered": mismatches[:200]},
          open(RECORD_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"\nrendered {len(headers)} distinct headers; refusals {len(refusals)}; "
      f"predicted-but-not-rendered {len(mismatches)}")
print(f"wrote {HEADERS_OUT} and {RECORD_OUT}")
