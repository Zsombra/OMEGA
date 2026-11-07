"""Close the live-render coverage gap left by a corpus refresh.

First run 2026-09-09 (7,840 shapes, 13,572 headers, zero refusals); re-run 2026-09-20 for the
61.2.0 refresh. SWEEP_DATE names the output pair so each run keeps its own evidence.

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

One SWEEP_DATE per pass: a second subject or scope under the same SWEEP_DATE would overwrite the first pass's pair,
so the run refuses an existing output (SWEEP_OVERWRITE=1 replaces it on purpose); name each pass, as 11-02 did
("2026-11-02" and "2026-11-02-market").

The run stops - it never bisects - on anything that is not a platform answer: an OAuth prompt, a platform 5xx (the
11-05 14:43Z-16:31Z outage answered "HTTP 502" to every call), a version GET that fails or a served contract that
moved. What rendered before the stop is kept, and the record measures header agreement on the shapes it sent only.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, ".")
from omega.contract import load                      # noqa: E402
from omega.fanout import outputs_for                 # noqa: E402
from scripts.render_coverage import (                # noqa: E402
    QUARANTINED, coverage, is_placeholder, rendered_headers,
)

COLS_PER_SECTION = 32
# 4 since the 2026-10-13 run: v92 made the preview cap 150,000 result CHARACTERS and a "detailed" render (the only
# one that carries authoring.conditionColumns) is larger than the concise one; an over-cap batch is bisected anyway.
SECTIONS_PER_CALL = int(os.environ.get("SWEEP_SECTIONS_PER_CALL", "4"))
SWEEP_DATE = os.environ.get("SWEEP_DATE", "2026-09-09")
HEADERS_OUT = f"data/contract/columns/_coverage_sweep_{SWEEP_DATE}.json"
RECORD_OUT = f"data/audit/coverage_sweep_{SWEEP_DATE}.json"
NOTE = f"OMEGA read-only coverage sweep {SWEEP_DATE}"
# 2026-11-02 (contract 146.0.1): the section's subject. A custom section with `marketScope: null` is an evaluated-coin
# section and refuses a market metric ("metric 'MKT_UP' is not read on a evaluated-coin section's bars",
# REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED); a named scope makes a MARKET section, which reads the thirteen MKT_*
# metrics and refuses every other one. So the sweep sends one subject per run: SWEEP_MARKET_SCOPE names the scope of
# every section it builds (unset = null, the per-coin sections every earlier sweep sent), and SWEEP_METRICS (a comma
# list) restricts the shapes to those metrics, so a market pass renders the market family and nothing else.
SWEEP_MARKET_SCOPE = os.environ.get("SWEEP_MARKET_SCOPE") or None
SWEEP_METRICS = {m for m in os.environ.get("SWEEP_METRICS", "").split(",") if m} or None
# 2026-11-05 (contract 148.1.0): the other two section subjects every served metric now names in `subjectKinds`
# (README v146). A `benchmarkTicker` makes the section read another instrument: a declared stablecoin pair
# (USDT_USD, USDC_USDT) is a `reference` section - OPEN / HIGH / LOW / CLOSE / PAR_DEV - and any other ticker a
# `benchmark` section. SWEEP_BENCHMARK names the ticker of every section the run builds (unset = null, as before);
# it is sent beside SWEEP_MARKET_SCOPE, never with it (a section has one subject).
SWEEP_BENCHMARK = os.environ.get("SWEEP_BENCHMARK") or None
# Stop the run at once on any of these in mcporter's stderr: the stored OAuth credential has no usable token and every
# further call would start another interactive authorization (seen 2026-11-05 from ~10:18Z).
AUTH_MARKERS = ("/authorize", "If the browser did not open", "OAuth", "Unauthorized", "401")
# A gateway / platform outage, on stderr ("[mcporter] battlegrid-anbu.<tool> responded with HTTP 502 (Version
# negotiation failed ...)", 2026-11-05 14:43Z) or as an nginx page on stdout. Never a column's refusal: bisecting it
# costs ~383 previews per 128-column batch against a dead platform and records the gateway text as each column's error.
PLATFORM_DOWN = re.compile(r"HTTP 5\d\d|Bad Gateway|Service (Temporarily )?Unavailable|Gateway Time-?out", re.I)
SWEEP_CONTRACT = os.environ.get("SWEEP_CONTRACT")      # when set, GET /mcp/version every VERSION_EVERY previews
VERSION_EVERY = 25
_calls = [0]


class SweepStopped(RuntimeError):
    """The run cannot go on: no usable credential, a platform outage, an unreadable version, or a moved contract."""


def version():
    """GET /mcp/version. Any failure (HTTPError on the nginx 502, URLError / a timeout, a body that is not a JSON
    object) is a stop, never an uncaught exception that loses the partial record."""
    try:
        with urllib.request.urlopen("https://mcp.battlegrid.trade/mcp/version", timeout=30) as r:
            v = json.loads(r.read().decode())
    except (OSError, ValueError) as exc:      # HTTPError / URLError / TimeoutError; JSONDecodeError / UnicodeDecodeError
        raise SweepStopped(f"GET /mcp/version failed ({type(exc).__name__}: {str(exc)[:200]})") from None
    if not isinstance(v, dict):
        raise SweepStopped(f"GET /mcp/version answered no JSON object: {str(v)[:200]}")
    return v


def _stop_on_outage(msg):
    if PLATFORM_DOWN.search(msg):
        raise SweepStopped(f"platform outage after {_calls[0]} previews (not a refusal): {msg}")


def call(tool, args, timeout=240):
    if SWEEP_CONTRACT and _calls[0] % VERSION_EVERY == 0:
        served = version().get("contractVersion")
        if served != SWEEP_CONTRACT:
            raise SweepStopped(f"served contract {served} after {_calls[0]} previews, not {SWEEP_CONTRACT}")
    _calls[0] += 1
    time.sleep(0.45)                      # one worker, well under the account's 3 req/s
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
        msg = (err.decode(errors="replace") or "empty stdout")[:400]
        if any(marker in msg for marker in AUTH_MARKERS):
            raise SweepStopped(f"mcporter has no usable credential for battlegrid-anbu: {msg}")
        _stop_on_outage(msg)
        return None, msg
    try:
        return json.loads(txt), None
    except json.JSONDecodeError:
        _stop_on_outage(txt[:400])
        return None, txt[:400]


def render(columns):
    """-> (headers, error). One preview carrying `columns` split across sections."""
    secs = []
    for i in range(0, len(columns), COLS_PER_SECTION):
        secs.append({"kind": "custom", "title": f"sweep {len(secs) + 1}",
                     "benchmarkTicker": SWEEP_BENCHMARK, "marketScope": SWEEP_MARKET_SCOPE, "notes": NOTE,
                     "columns": columns[i:i + COLS_PER_SECTION]})
    # The request at v85+ (`source.kind: "FIELDS"`) and the read at v92+ (`conditionColumns` left the top level for
    # `authoring`, served only at detail "detailed"); the 09-09 / 09-20 runs used the flat compile-era shape.
    req = {"coinSelection": {"mode": "explicit", "tickers": ["BTC"]}, "detail": "detailed",
           "source": {"kind": "FIELDS", "timeframe": "1h", "sections": secs}}
    d, err = call("preview_strategy_report", req)
    if d is None:
        return None, err
    if "budgetUsage" not in d or not isinstance(d.get("authoring"), dict):
        return None, json.dumps(d)[:400]
    hdrs = []
    for cc in d["authoring"].get("conditionColumns", []):
        if str(cc.get("title", "")).startswith("sweep "):
            hdrs += [o["header"] for o in cc["outputs"]]
    return hdrs, None


def bisect(columns, refusals, render_fn, acc, depth=0):
    """Attribute a refusal to the exact column(s). Headers go into `acc` as they render, so a stop inside the bisect
    keeps what the platform already minted."""
    if len(columns) == 1:
        hdrs, err = render_fn(columns)
        if err:
            refusals.append({"column": columns[0], "error": err[:300]})
        else:
            acc += hdrs
        return
    mid = len(columns) // 2
    for half in (columns[:mid], columns[mid:]):
        hdrs, err = render_fn(half)
        if err:
            bisect(half, refusals, render_fn, acc, depth + 1)
        else:
            acc += hdrs


def collect_targets(c):
    """Every uncovered shape, structural and operand-expanded, deduped by its column payload. SWEEP_SCOPE=structural
    renders the structural shapes only, SWEEP_SCOPE=nonspread every uncovered shape that is not a spread pair
    (2026-10-30: the 144.0.0 corpus left 83,480 uncovered expanded shapes - the 78 added metrics as spread operands -
    against 3,3xx structural ones; every new header pattern is structural, the expansions re-mint it with another
    operand code)."""
    scope = os.environ.get("SWEEP_SCOPE", "all")
    targets, keys = [], set()
    for expand in ((False,) if scope == "structural" else (False, True)):
        _, unc, _ = coverage(expand, c)
        for s in unc:
            if scope == "nonspread" and s.transform == "spread":
                continue        # the 2026-10-30 second pass: every uncovered expansion that is not a spread operand pair
            if SWEEP_METRICS is not None and s.metric not in SWEEP_METRICS:
                continue        # 2026-11-02: one subject per run (see SWEEP_METRICS above)
            col = s.to_column().model_dump(exclude_none=True)
            k = json.dumps(col, sort_keys=True)
            if k in keys:
                continue
            keys.add(k)
            targets.append((s, col))
    return scope, targets


def run_sweep(targets, render_fn=render, per_call=COLS_PER_SECTION * SECTIONS_PER_CALL):
    """One preview per `per_call` columns; a refused batch is bisected. -> {headers (sorted, distinct), refusals,
    batches, aborted, sent}: `sent` is the shapes of the batches that completed - after a stop, the only shapes the
    run measured. Headers minted by an interrupted batch are kept; its shapes are not counted as sent."""
    all_headers, refusals, batches, sent = [], [], [], []
    aborted = None
    t0 = time.time()
    for i in range(0, len(targets), per_call):
        chunk = targets[i:i + per_call]
        cols = [col for _, col in chunk]
        batch_hdrs = []
        try:
            hdrs, err = render_fn(cols)
            if err:
                print(f"  batch {i // per_call + 1}: REFUSED, bisecting ({err[:90]})")
                bisect(cols, refusals, render_fn, batch_hdrs)
            else:
                batch_hdrs += hdrs
        except SweepStopped as exc:
            # what rendered before the stop is kept; the record says where and why it stopped
            all_headers += batch_hdrs
            aborted = {"message": str(exc)[:600], "afterBatches": len(batches),
                       "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            print(f"STOPPED: {aborted['message']}")
            break
        all_headers += batch_hdrs
        sent += [s for s, _ in chunk]
        batches.append({"batch": i // per_call + 1, "columns": len(cols), "headers": len(batch_hdrs)})
        done = min(i + per_call, len(targets))
        print(f"  [{done}/{len(targets)}] headers so far {len(set(all_headers))} "
              f"refusals {len(refusals)} ({round(time.time() - t0)}s)")
    return {"headers": sorted(set(all_headers)), "refusals": refusals, "batches": batches, "aborted": aborted,
            "sent": sent}


def agreement(shapes, headers, seen_before, predict):
    """Header agreement: does omega predict what the platform minted? `predict(shape)` -> the predicted headers."""
    known = set(headers) | seen_before
    mismatches = []
    for s in shapes:
        pred = predict(s)
        missing = [h for h in pred if h not in known]
        if missing:
            mismatches.append({"shape": f"{s.metric}|{s.transform}|{s.chained}|{s.operand}|{s.ordering}",
                               "predicted": pred, "notRendered": missing})
    return mismatches


def run_record(scope, targets, out, mismatches):
    """`shapesTargeted` = every uncovered shape; `shapesRequested` = the shapes of the completed batches (equal on a
    complete run); `predictedButNotRendered` is judged on the requested shapes only."""
    aborted = out["aborted"]
    return {"_what": (f"Run record for the {SWEEP_DATE} live coverage sweep: what was asked for, what "
                      "the platform refused, and every shape whose omega-predicted header did not "
                      "turn up in the render. Kept OUT of data/contract/columns/ so none of these "
                      "strings can be mistaken for a rendered header. A stopped run (complete false) "
                      "judges header agreement on the shapes it sent, never on the ones it did not."),
            "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "how": ("preview_strategy_report via the mcporter CLI, read-only, BTC only, "
                    f"{COLS_PER_SECTION} columns per custom section, up to {SECTIONS_PER_CALL} "
                    "sections per call; refused batches bisected to the offending column."),
            "scope": scope, "marketScope": SWEEP_MARKET_SCOPE, "benchmarkTicker": SWEEP_BENCHMARK,
            "metricsRestrictedTo": sorted(SWEEP_METRICS) if SWEEP_METRICS else None,
            "shapesTargeted": len(targets), "shapesRequested": len(out["sent"]), "batches": out["batches"],
            "complete": aborted is None, "aborted": aborted,
            "headersMinted": len(out["headers"]),
            "refusalCount": len(out["refusals"]), "refusals": out["refusals"],
            "predictedButNotRenderedCount": len(mismatches),
            "predictedButNotRendered": mismatches[:200]}


def main():
    if SWEEP_BENCHMARK and SWEEP_MARKET_SCOPE:
        sys.exit("SWEEP_BENCHMARK and SWEEP_MARKET_SCOPE name two subjects; a section has one")
    taken = [p for p in (HEADERS_OUT, RECORD_OUT) if os.path.exists(p)]
    if taken and os.environ.get("SWEEP_OVERWRITE") != "1":
        sys.exit(f"{', '.join(taken)} already exist: give this pass its own SWEEP_DATE (e.g. "
                 f"{SWEEP_DATE}-nonspread), or SWEEP_OVERWRITE=1 to replace them")
    c = load()
    seen_before = rendered_headers()
    scope, targets = collect_targets(c)
    print(f"uncovered shapes to render: {len(targets)}")

    out = run_sweep(targets)

    headers = out["headers"]
    os.makedirs(os.path.dirname(HEADERS_OUT), exist_ok=True)
    json.dump({"_what": ("Headers minted live by preview_strategy_report during the " + SWEEP_DATE + " "
                         "coverage sweep. HEADERS ONLY - render_coverage treats every string in "
                         "this file as a seen header, so nothing else may be added here."),
               "headers": headers},
              open(HEADERS_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    mismatches = agreement(out["sent"], headers, seen_before,
                           lambda s: [o.header for o in outputs_for(s.to_column(), c)])
    os.makedirs(os.path.dirname(RECORD_OUT), exist_ok=True)
    json.dump(run_record(scope, targets, out, mismatches),
              open(RECORD_OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nrendered {len(headers)} distinct headers; refusals {len(out['refusals'])}; "
          f"predicted-but-not-rendered {len(mismatches)} of {len(out['sent'])} sent"
          + ("" if out["aborted"] is None else f" (STOPPED after {out['aborted']['afterBatches']} batches)"))
    print(f"wrote {HEADERS_OUT} and {RECORD_OUT}")


if __name__ == "__main__":
    main()
