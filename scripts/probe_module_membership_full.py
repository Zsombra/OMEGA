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

Usage: python scripts/probe_module_membership_full.py [--limit N]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, ".")
from omega.contract import load          # noqa: E402
from omega.space import enumerate_shapes  # noqa: E402

PARTIAL = "data/audit/_module_membership_full_partial.json"
OUT = "data/audit/module_membership_full_2026-09-09.json"
NOTE = "OMEGA read-only full membership probe 2026-09-09"


def call(tool, args, timeout=180):
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
    for i, (metric, transform, col, operand) in enumerate(todo, 1):
        key = f"{metric}|{transform}"
        sigs, err = signals_for(col, f"probe {key}")
        done[key] = {"signalsFed": sigs, "error": err, "operand": operand}
        if i % 5 == 0 or i == len(todo):
            json.dump(done, open(PARTIAL, "w", encoding="utf-8"), ensure_ascii=False)
        if i % 25 == 0 or i == len(todo):
            rate = (time.time() - t0) / i
            print(f"  [{i}/{len(todo)}] {key} -> "
                  f"{len(sigs) if sigs is not None else 'ERR'} "
                  f"({round(time.time()-t0)}s, ~{round(rate*(len(todo)-i)/60,1)}min left)")
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

    # A spread column puts TWO metrics in the report - the base and its operand - so the
    # operand's own signals appear in the result. Subtract them, or every spread cell looks
    # transform-dependent when it is really operand contribution. Measured on ADX x spread
    # with operand RSI14: 14 signals, of which the 8 RSI ones are RSI14's, not ADX's.
    def own(m):
        """A metric's own signals, from its non-spread cells."""
        return set().union(*[v for t, v in raw.get(m, {}).items() if t != "spread"])             if any(t != "spread" for t in raw.get(m, {})) else set()

    by_metric, unattributed = {}, []
    for metric, per in raw.items():
        by_metric[metric] = {}
        for transform, sigs in per.items():
            if transform == "spread":
                op = operands.get(f"{metric}|spread")
                # Only subtract when the operand's OWN cells were probed. On a partial run
                # they may not be, and under-subtracting would invent transform-dependence.
                if op and any(t != "spread" for t in raw.get(op, {})):
                    sigs = sigs - own(op)
                elif op:
                    unattributed.append(f"{metric}|spread (operand {op} not probed)")
                    continue
            by_metric[metric][transform] = sigs

    transform_dependent, feeds, none = {}, {}, []
    for metric, per in sorted(by_metric.items()):
        union = set().union(*per.values()) if per else set()
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
        "spreadCellsUnattributed": unattributed,
        "membershipIsTransformDependent": bool(transform_dependent),
        "transformDependentMetrics": transform_dependent,
        "_spreadAttribution": ("For a spread cell the operand metric is also in the report, so its own "
                       "signals are subtracted before attributing anything to the base metric. "
                       "The operand used for each spread probe is recorded in the partial file."),
        "metricsFeedingAModule": feeds,
        "metricsSatisfyingNoModule": sorted(none),
        "counts": {"feed": len(feeds), "feedNothing": len(none),
                   "transformDependent": len(transform_dependent)},
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
