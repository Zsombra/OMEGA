"""Measure signal-module membership for the 58 metrics added since the August probes.

`derive_strategy_rule_view` reads no persisted strategy and writes nothing. One probe per
metric: a single custom section carrying that metric alone, and whatever signals come back
IN_REPORT are the ones that metric feeds.

The control matters and is run first: a section carrying only CLOSE returns ZERO signals in
report, so membership is metric-driven here and a non-empty result is attributable to the
metric under test rather than to the section existing.
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, ".")
from omega.contract import load  # noqa: E402


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
        return None, (err.decode(errors="replace") or "empty stdout")[:300]
    try:
        return json.loads(txt), None
    except json.JSONDecodeError:
        return None, txt[:300]


def signals_for(columns, label):
    d, err = call("derive_strategy_rule_view", {"sections": [
        {"kind": "custom", "title": label, "benchmarkTicker": None,
         "notes": "OMEGA read-only module-membership probe 2026-09-09",
         "columns": columns}]})
    if d is None:
        return None, err
    return sorted(r["signalId"] for r in d["rules"] if r.get("inReport")), None


c = load()
unmeasured = json.load(open("data/derived/unmeasured_metrics.json", encoding="utf-8"))["unmeasured"]

control, err = signals_for(
    [{"metric": "CLOSE", "transformId": "value", "timeframe": {"rel": "anchor"}}], "control")
print(f"CONTROL (CLOSE value only): {len(control) if control is not None else err} signals")
if control is None or control:
    print("control is not empty - membership is not cleanly metric-attributable; aborting")
    raise SystemExit(1)

results, failures = {}, {}
t0 = time.time()
for i, m in enumerate(unmeasured, 1):
    tid = "value" if "value" in c.metric(m).transforms else sorted(c.metric(m).transforms)[0]
    col = {"metric": m, "transformId": tid, "timeframe": {"rel": "anchor"}}
    if tid == "spread" and c.metric(m).spread_operands:
        col["inputs"] = [{"metric": c.metric(m).spread_operands[0]}]
    if tid in ("nearestZoneDist", "nearestZoneType", "nearestZoneRange", "nearestZoneAge"):
        col["side"] = "support"
    sigs, err = signals_for([col], f"probe {m}")
    if sigs is None:
        failures[m] = err
        print(f"  [{i}/{len(unmeasured)}] {m}: FAILED {err[:80]}")
        continue
    results[m] = {"transformProbed": tid, "signalsFed": sigs}
    if i % 10 == 0 or sigs:
        print(f"  [{i}/{len(unmeasured)}] {m} ({tid}): {len(sigs)} signals "
              f"{sigs if sigs else ''} ({round(time.time() - t0)}s)")

feeds = {m: v for m, v in results.items() if v["signalsFed"]}
none = sorted(m for m, v in results.items() if not v["signalsFed"])
out = {
    "_what": ("Signal-module membership for the metrics added to the platform after the "
              "2026-08-24 probes, measured 2026-09-09 with derive_strategy_rule_view (reads "
              "no persisted strategy, writes nothing). One probe per metric, the metric alone "
              "in one custom section."),
    "_control": ("A section carrying only CLOSE returns ZERO signals in report, so a non-empty "
                 "result below is attributable to the metric under test, not to the section "
                 "existing. The control was re-run at the start of this sweep and was empty."),
    "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "probed": len(results), "failed": failures,
    "metricsFeedingAModule": feeds,
    "metricsSatisfyingNoModule": none,
    "counts": {"feed": len(feeds), "feedNothing": len(none)},
}
json.dump(out, open("data/audit/module_membership_new_metrics_2026-09-09.json", "w",
                    encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nprobed {len(results)}; feed a module {len(feeds)}; feed nothing {len(none)}; "
      f"failed {len(failures)}")
