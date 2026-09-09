"""Full signal-module membership probe: EVERY legal metric x transform pair, not one per metric.

The 2026-09-09 first pass probed each metric once, with `value` where offered, and recorded the
caveat that a metric feeding a module only through some OTHER transform would not have been
seen. This closes that caveat by probing all 663 unchained atoms - exactly one per legal
metric x transform cell - so the map rests on the whole surface rather than a slice of it.

`derive_strategy_rule_view` reads no persisted strategy and writes nothing.

The control is what makes a result attributable: a section carrying a single CLOSE value column
returns ZERO signals in report. It is re-run at the start and must be empty, otherwise a
non-empty probe result could be an artefact of the section existing and the run aborts.

Resumable: each result is appended to the partial file as it is measured, and a re-run skips
pairs already recorded there.

Runs WORKERS probes concurrently (default 4), THROTTLED. The server rate-limits and says so
in as many words:

    "Rate limited: 3 requests/second sustained, up to 120 banked. Retry after 1s, or wait
     40s for full capacity."

An unthrottled 4-worker run burned the 120-request bank and then failed 162 of 663 cells.
The limiter is explicit, never silent, so a throttled run that still fails is failing for
some other reason. Calls are spaced to stay under the sustained rate and a rate-limited
call is retried with backoff.

Usage: python scripts/probe_module_membership_full.py [--limit N] [--workers N]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, ".")
from omega.contract import load          # noqa: E402
from omega.space import enumerate_shapes  # noqa: E402

PARTIAL = "data/audit/_module_membership_full_partial.json"
OUT = "data/audit/module_membership_full_2026-09-09.json"
NOTE = "OMEGA read-only full membership probe 2026-09-09"


# The server allows 3 requests/second sustained. Space call STARTS a little wider than that
# so a burst cannot outrun the bucket, and never rely on the 120-request bank: it refills at
# the sustained rate, so a long run consumes it once and then lives at the sustained rate.
_MIN_INTERVAL = 0.45
_rate_lock = threading.Lock()
_last_call = [0.0]


def _throttle():
    with _rate_lock:
        wait = _last_call[0] + _MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()


def call(tool, args, timeout=180, attempts=4):
    for attempt in range(1, attempts + 1):
        _throttle()
        res, err = _call_once(tool, args, timeout)
        if err and "Rate limited" in err:
            time.sleep(1.5 * attempt)      # the limiter says "retry after 1s"
            continue
        return res, err
    return None, err


def _call_once(tool, args, timeout=180):
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
        return None, (err.decode(errors="replace") or "empty stdout")[:300]
    try:
        return json.loads(txt), None
    except json.JSONDecodeError:
        return None, txt[:300]


def signals_for(column, label):
    d, err = call("derive_strategy_rule_view", {"sections": [
        {"kind": "custom", "title": label, "benchmarkTicker": None,
         "notes": NOTE, "columns": [column]}]})
    if d is None:
        return None, err
    if "rules" not in d:
        return None, json.dumps(d)[:300]
    return sorted(r["signalId"] for r in d["rules"] if r.get("inReport")), None


def main() -> int:
    c = load()
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    control, err = signals_for(
        {"metric": "CLOSE", "transformId": "value", "timeframe": {"rel": "anchor"}}, "control")
    if control is None:
        print(f"control call failed: {err}")
        return 1
    if control:
        print(f"control is NOT empty ({len(control)} signals) - results would not be "
              f"attributable to the column under test. Aborting.")
        return 1
    print("control (CLOSE value only): 0 signals in report - attributable")

    # one column per legal metric x transform cell
    targets = []
    for s in enumerate_shapes():
        if s.chained is not None:
            continue
        col = s.to_column().model_dump(exclude_none=True)
        operand = None
        if s.transform == "spread" and "inputs" not in col:
            ops = c.metric(s.metric).spread_operands
            if not ops:
                continue
            operand = ops[0]
            col["inputs"] = [{"metric": operand}]
        targets.append((s.metric, s.transform, col, operand))
    targets.sort(key=lambda t: (t[0], t[1]))
    print(f"legal metric x transform cells to probe: {len(targets)}")

    done = {}
    if os.path.exists(PARTIAL):
        done = json.load(open(PARTIAL, encoding="utf-8"))
        print(f"resuming: {len(done)} already recorded")

    t0 = time.time()
    todo = [t for t in targets if f"{t[0]}|{t[1]}" not in done]
    if limit:
        todo = todo[:limit]
    workers = 4
    if "--workers" in sys.argv:
        workers = int(sys.argv[sys.argv.index("--workers") + 1])
    lock = threading.Lock()
    counter = {"n": 0}

    def one(job):
        metric, transform, col, operand = job
        key = f"{metric}|{transform}"
        sigs, err = signals_for(col, f"probe {key}")
        with lock:
            done[key] = {"signalsFed": sigs, "error": err, "operand": operand}
            counter["n"] += 1
            i = counter["n"]
            if i % 10 == 0 or i == len(todo):
                json.dump(done, open(PARTIAL, "w", encoding="utf-8"), ensure_ascii=False)
            if i % 25 == 0 or i == len(todo):
                rate = (time.time() - t0) / i
                print(f"  [{i}/{len(todo)}] {key} -> "
                      f"{len(sigs) if sigs is not None else 'ERR ' + str(err)[:60]} "
                      f"({round(time.time()-t0)}s, ~{round(rate*(len(todo)-i)/60,1)}min left)")

    print(f"probing with {workers} workers")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, todo))
    json.dump(done, open(PARTIAL, "w", encoding="utf-8"), ensure_ascii=False)

    # ---- collate ----------------------------------------------------------------
    raw, failures, operands = {}, {}, {}
    for key, v in done.items():
        metric, transform = key.split("|", 1)
        if v.get("error"):
            failures[key] = v["error"]
            continue
        raw.setdefault(metric, {})[transform] = set(v["signalsFed"])
        if v.get("operand"):
            operands[key] = v["operand"]

    # A spread column puts TWO metrics in the report - the base and its operand - so it
    # CANNOT isolate the base's contribution. Subtracting the operand's own signals looked
    # like a fix and is not: when base and operand feed the SAME module the subtraction
    # removes the base's contribution too, and the cell reads as zero. Measured: PPO x spread
    # with operand ROC12 came back empty that way, while PPO x value/trajectory/rank/crossDetect
    # all return the same four relative-strength signals. So spread cells are EXCLUDED from
    # attribution and from the transform-dependence question, and recorded separately with
    # their operand so the exclusion is inspectable rather than silent.
    spread_cells = {}
    by_metric = {}
    for metric, per in raw.items():
        for transform, sigs in per.items():
            if transform == "spread":
                spread_cells[f"{metric}|spread"] = {
                    "operand": operands.get(f"{metric}|spread"),
                    "signalsInReport": sorted(sigs),
                    "attributable": False}
            else:
                by_metric.setdefault(metric, {})[transform] = sigs

    transform_dependent, feeds, none, spread_only = {}, {}, [], []
    for metric in sorted(raw):
        per = by_metric.get(metric)
        if not per:                      # every legal cell for this metric is a spread cell
            spread_only.append(metric)
            continue
        union = set().union(*per.values())
        distinct = {frozenset(v) for v in per.values()}
        if union:
            feeds[metric] = sorted(union)
        else:
            none.append(metric)
        if len(distinct) > 1:
            transform_dependent[metric] = {t: sorted(v) for t, v in per.items()}

    out = {
        "_what": ("Signal-module membership probed at EVERY legal metric x transform cell "
                  "(663 unchained atoms), one column per probe, 2026-09-09. Supersedes the "
                  "single-transform pass in module_membership_new_metrics_2026-09-09.json and "
                  "closes its caveat."),
        "_control": ("A section carrying only CLOSE value returns ZERO signals in report, "
                     "re-verified at the start of this run, so a non-empty result is "
                     "attributable to the column under test."),
        "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cellsProbed": len(done) - len(failures),
        "failures": failures,
        "membershipIsTransformDependent": bool(transform_dependent),
        "transformDependentMetrics": transform_dependent,
        "_spreadAttribution": ("A spread cell puts the base AND its operand in the report, so it cannot "
                              "attribute membership to the base. Subtracting the operand's own signals is "
                              "NOT a fix: where base and operand feed the same module it removes the base's "
                              "contribution too. Spread cells are therefore excluded from the counts and "
                              "from the transform-dependence question, and listed under spreadCells with "
                              "their operand so the exclusion can be checked."),
        "spreadCells": spread_cells,
        "metricsWithOnlySpreadCells": spread_only,
        "metricsFeedingAModule": feeds,
        "metricsSatisfyingNoModule": sorted(none),
        "counts": {"feed": len(feeds), "feedNothing": len(none),
                   "transformDependent": len(transform_dependent),
                   "spreadCellsExcluded": len(spread_cells),
                   "attributedFromNonSpreadCells": len(feeds) + len(none)},
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\ncells probed {out['cellsProbed']}, failures {len(failures)}")
    print(f"metrics feeding a module {len(feeds)}, feeding nothing {len(none)}")
    print(f"membership transform-dependent: {bool(transform_dependent)}"
          + (f" -> {sorted(transform_dependent)}" if transform_dependent else ""))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
