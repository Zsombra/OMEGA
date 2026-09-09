"""Refresh data/contract/metrics/ from the live platform. First run: contract 54.1.0, 2026-09-09.

Writes the raw hint responses to a scratch dir and the extraction batches to
data/contract/metrics/_batch*.json; run scripts/build_corpus.py afterwards to regenerate the
per-metric files, the index and every derived artefact. Archive the previous batches first -
they are the raw record earlier measurements were built from.

One get_metric_construction_hints call per metric, for every metric the live vocabulary
lists. Writes each file in the existing convention: id + flags per transform (the
invariant `authoring` block stays in transforms/_authoring.json, not duplicated here),
spreadOperands and rankOrderings only when the platform returns them.

Also collects each transform's `authoring` block so the "byte-identical regardless of
which metric it is attached to" claim in transforms/_authoring.json can be re-checked
rather than assumed.

Resumable: a metric whose file already carries this run's stamp is skipped.
"""
import glob
import json
import os
import subprocess
import sys
import time

ROOT = r"C:\Users\rafae\Documents\GitHub\OMEGA\.claude\worktrees\vwap-strategy-dev-c75dc9"
OUT = os.path.join(ROOT, "data", "contract", "metrics")
SP = r"C:\Users\rafae\AppData\Local\Temp\claude\C--Users-rafae-Documents-GitHub-OMEGA--claude-worktrees-vwap-strategy-dev-c75dc9\79a52272-a56d-4902-9595-98fac9bb1dda\scratchpad"
RAW = os.path.join(SP, "hints_20260909")
os.makedirs(RAW, exist_ok=True)

# Every per-transform flag the platform actually returns, enumerated from the 144 responses
# of the 2026-09-09 sweep - NOT assumed. A first pass listed only the first three and silently
# dropped chainedRankOrderings and rankableSpreadOperands, which the suite caught.
TRANSFORM_FLAGS = ("operandRequired", "chainSuccessors", "chainedRankOrderings",
                   "sideRequired", "rankableSpreadOperands")


def call(tool, args, timeout=120):
    p = subprocess.Popen(
        ["cmd", "/c", "npx", "mcporter", "call", f"battlegrid-anbu.{tool}",
         "--output", "json", "--args", "-"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(json.dumps(args).encode(), timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        return None, "TIMEOUT"
    if p.returncode != 0 or not out.strip():
        return None, (err.decode(errors="replace") or "empty stdout")[:300]
    try:
        return json.loads(out.decode(errors="replace")), None
    except json.JSONDecodeError:
        return None, out.decode(errors="replace")[:300]


live = json.load(open(os.path.join(SP, "vocab_live_flat.json"), encoding="utf-8"))
names = sorted(live)
print(f"live metrics: {len(names)}")

authoring_seen = {}   # transformId -> {json of authoring block: [metrics]}
written, failed = [], []

for i, name in enumerate(names, 1):
    rawp = os.path.join(RAW, f"{name}.json")
    if os.path.exists(rawp):
        resp = json.load(open(rawp, encoding="utf-8"))
    else:
        resp, err = call("get_metric_construction_hints", {"metric": name})
        if resp is None:
            print(f"  [{i}/{len(names)}] {name}: FAILED {err}")
            failed.append(name)
            continue
        json.dump(resp, open(rawp, "w", encoding="utf-8"), ensure_ascii=False)
    m = resp["metric"] if isinstance(resp, dict) and "metric" in resp and isinstance(resp["metric"], dict) else resp
    rec = {
        "metric": m["metric"],
        "label": m["label"],
        "code": m["code"],
        "family": m["family"],
        "nativeOutput": m["nativeOutput"],
        "outputKind": m.get("outputKind", "scalar"),
        "timeframeMode": m["timeframeMode"],
        "transforms": [],
    }
    for t in m.get("transforms", []):
        entry = {"id": t["id"]}
        for flag in TRANSFORM_FLAGS:
            if flag in t:
                entry[flag] = t[flag]
        rec["transforms"].append(entry)
        if "authoring" in t:
            blob = json.dumps(t["authoring"], sort_keys=True)
            authoring_seen.setdefault(t["id"], {}).setdefault(blob, []).append(m["metric"])
    if m.get("spreadOperands"):
        rec["spreadOperands"] = m["spreadOperands"]
    if m.get("rankOrderings"):
        rec["rankOrderings"] = m["rankOrderings"]
    with open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)
        f.write("\n")
    written.append(name)
    if i % 20 == 0 or i == len(names):
        print(f"  [{i}/{len(names)}] ... {name}")

# retire metrics the platform no longer serves
retired = []
for path in glob.glob(os.path.join(OUT, "*.json")):
    base = os.path.basename(path)
    if base.startswith("_"):
        continue
    if base[:-5] not in live:
        os.remove(path)
        retired.append(base[:-5])

# index
by_family = {}
for name in sorted(live):
    by_family.setdefault(live[name]["family"], []).append(name)
idx = {"metricCount": len(live), "byFamily": {k: sorted(v) for k, v in sorted(by_family.items())}}
with open(os.path.join(OUT, "_index.json"), "w", encoding="utf-8") as f:
    json.dump(idx, f, indent=2, ensure_ascii=False)
    f.write("\n")

# authoring-invariance re-check
variants = {tid: len(blobs) for tid, blobs in authoring_seen.items()}
json.dump({"_what": "get_metric_construction_hints authoring blocks grouped by transform, "
                    "2026-09-09 sweep. variants>1 would falsify the invariance claim in "
                    "transforms/_authoring.json.",
           "variantsPerTransform": variants,
           "metricsPerTransform": {t: sum(len(v) for v in b.values()) for t, b in authoring_seen.items()}},
          open(os.path.join(SP, "authoring_invariance_20260909.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"\nwritten {len(written)}; retired {retired}; failed {failed or 'none'}")
print("authoring variants per transform (1 == invariant):", variants)
if failed:
    sys.exit(1)
