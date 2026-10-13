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

Re-run 2026-09-20 at contract 61.2.0. EXTRACTION_SCRATCH and EXTRACTION_STAMP replace the constants the
first run pinned to one session's scratch directory, which no longer exists.
"""
import glob
import json
import os
import subprocess
import sys
import time

# Re-run 2026-10-13 at contract 108.4.0: the root is this checkout (the first two runs hard-coded a worktree that no
# longer exists), and the stamp, the scratch dir and the archive stamp are required - a default pointed at another
# session's scratch, which is how a stale raw dir could be read silently.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "contract", "metrics")
STAMP = os.environ.get("EXTRACTION_STAMP") or sys.exit("set EXTRACTION_STAMP (e.g. 20261013)")
SP = os.environ.get("EXTRACTION_SCRATCH") or sys.exit("set EXTRACTION_SCRATCH (the dir holding hints_<STAMP>/)")
# The batches this run replaces are archived to data/contract/metrics/archive_<ARCHIVE>_extraction/.
ARCHIVE = os.environ.get("EXTRACTION_ARCHIVE") or sys.exit("set EXTRACTION_ARCHIVE (the stamp of the batches replaced)")
RAW = os.path.join(SP, "hints_" + STAMP)
os.makedirs(RAW, exist_ok=True)

# Every per-transform flag the platform actually returns, enumerated from the 144 responses
# of the 2026-09-09 sweep - NOT assumed. A first pass listed only the first three and silently
# dropped chainedRankOrderings and rankableSpreadOperands, which the suite caught.
# Since v103 a served entry no longer carries operandRequired / sideRequired ("read
# authoring.parameters.side.required and authoring.parameters.inputs.required instead"): a refresh at
# 108 writes neither, and that is fine - omega.contract.requires_operand / requires_side, omega.validate
# and both corpus builders read the requirement from the transform's authoring block, which this
# script still collects (tests/test_v103_transform_entry.py runs the checks on a flag-less corpus).
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


# The roster, in platform order: the write schema's column metric enum (data/derived/condition_vocabulary_108.json,
# derived from the manifest's writeSurface). A vocab_live_flat.json in the scratch dir (the 09-09 / 09-20 runs) wins.
_flat = os.path.join(SP, "vocab_live_flat.json")
if os.path.exists(_flat):
    names = sorted(json.load(open(_flat, encoding="utf-8")))
else:
    names = json.load(open(os.path.join(ROOT, "data", "derived", "condition_vocabulary_108.json"),
                           encoding="utf-8"))["reportColumn"]["metric"]["enum"]
print(f"live metrics: {len(names)}")
records = {}
labels = {}           # transformId -> label (served on the transform entry, beside its authoring block)

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
    if "study" in m:          # served since the v100 catalogue additions; recorded as served
        rec["study"] = m["study"]
    for t in m.get("transforms", []):
        entry = {"id": t["id"]}
        for flag in TRANSFORM_FLAGS:
            if flag in t:
                entry[flag] = t[flag]
        rec["transforms"].append(entry)
        labels.setdefault(t["id"], t.get("label"))
        if "authoring" in t:
            # 108.4.0: a parameter's `maximum` is served PER METRIC (value.offset: 0 on a timeless metric, 31 on most
            # candle metrics, 30/21/12/11 on the bar-geometry ones); everything else in the block is invariant. The
            # maxima go on this metric's transform entry; the catalogue keeps the invariant rest.
            auth = json.loads(json.dumps(t["authoring"]))
            maxima = {}
            for pname, pspec in (auth.get("parameters") or {}).items():
                if isinstance(pspec, dict) and "maximum" in pspec:
                    maxima[pname] = pspec.pop("maximum")
            if maxima:
                entry["maximums"] = maxima
            blob = json.dumps(auth, sort_keys=True)
            authoring_seen.setdefault(t["id"], {}).setdefault(blob, []).append(m["metric"])
    if m.get("spreadOperands"):
        rec["spreadOperands"] = m["spreadOperands"]
    if m.get("rankOrderings"):
        rec["rankOrderings"] = m["rankOrderings"]
    with open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)
        f.write("\n")
    records[name] = rec
    written.append(name)
    if i % 20 == 0 or i == len(names):
        print(f"  [{i}/{len(names)}] ... {name}")

# retire metrics the platform no longer serves
retired = []
for path in glob.glob(os.path.join(OUT, "*.json")):
    base = os.path.basename(path)
    if base.startswith("_"):
        continue
    if base[:-5] not in names:
        os.remove(path)
        retired.append(base[:-5])

# index
by_family = {}
for name in sorted(records):
    by_family.setdefault(records[name]["family"], []).append(name)
idx = {"metricCount": len(records), "byFamily": {k: sorted(v) for k, v in sorted(by_family.items())}}
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
          open(os.path.join(SP, "authoring_invariance_" + STAMP + ".json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"\nwritten {len(written)}; retired {retired}; failed {failed or 'none'}")
print("authoring variants per transform (1 == invariant):", variants)
if failed:
    sys.exit(1)

# The batches build_corpus merges: archive the ones this run replaces, then write the new set in platform order, 30
# per batch (the shape of every earlier extraction's batches).
arch = os.path.join(OUT, f"archive_{ARCHIVE}_extraction")
old = sorted(glob.glob(os.path.join(OUT, "_batch*.json")))
if old:
    os.makedirs(arch, exist_ok=False)
    for path in old:
        os.replace(path, os.path.join(arch, os.path.basename(path)))
ordered = [records[n] for n in names if n in records]
for b in range(0, len(ordered), 30):
    with open(os.path.join(OUT, f"_batch{b // 30 + 1:02d}.json"), "w", encoding="utf-8") as f:
        json.dump(ordered[b:b + 30], f, indent=1, ensure_ascii=False)
        f.write("\n")
print(f"batches: {len(old)} archived to {os.path.basename(arch)}; {-(-len(ordered) // 30)} written")

# The transform catalogue (data/contract/transforms/_authoring.json): only when every transform's authoring block is
# invariant across the metrics that serve it - otherwise the catalogue's own claim is false and nothing is written.
if any(v != 1 for v in variants.values()):
    sys.exit("authoring blocks VARY across metrics - the catalogue is not refreshed; inspect authoring_invariance_*")
cat_path = os.path.join(ROOT, "data", "contract", "transforms", "_authoring.json")
cat = json.load(open(cat_path, encoding="utf-8"))
added, changed = [], []
for tid, blobs in sorted(authoring_seen.items()):
    block = json.loads(next(iter(blobs)))
    entry = dict(cat["transforms"].get(tid, {}))
    before = dict(entry)
    entry.update(block)
    if any("maximums" in tr for r in records.values() for tr in r["transforms"] if tr["id"] == tid):
        entry["_maximumServedPerMetric"] = ("a parameter's `maximum` is served per metric since 108.4.0 - read it from "
                                           "the metric record's transform entry (`maximums`), never from here")
    if labels.get(tid):
        entry["label"] = labels[tid]
    if tid not in cat["transforms"]:
        added.append(tid)
        entry.setdefault("_addedAt", f"extraction {STAMP}; `emits` and any `range` are not served by this tool - "
                                     "set them from a measured render, never assumed")
    elif entry != before:
        changed.append(tid)
    cat["transforms"][tid] = entry
with open(cat_path, "w", encoding="utf-8") as f:
    json.dump(cat, f, indent=1, ensure_ascii=False)
    f.write("\n")
print(f"catalogue: added {added}; authoring changed on {changed}; untouched (no metric serves them): "
      f"{sorted(set(cat['transforms']) - set(authoring_seen))}")
