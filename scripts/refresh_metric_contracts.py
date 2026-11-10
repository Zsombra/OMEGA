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

Resumable: a metric whose raw hint is already in hints_<STAMP>/ is not re-read.

Two phases (2026-11-05): every raw hint is read first, and nothing under data/ is written unless all of them are on
disk. The first version rewrote each metric file as it read it and wrote _index.json with the count of THIS run's
records before checking for failures, so a partial run (the 148.1.0 run stopped at 170 / 532 on a lost OAuth
credential) left `metricCount` 170 beside 326 files and omega.contract.load() raised "corpus incomplete" for every
consumer. An OAuth prompt from mcporter stops the fetch at once: each further call would start another interactive
authorization.

2026-11-08 (review pass 1, findings 1 and 2): phase 1 caches an answer only when it is a hint (a `metric` object with
metric / code / family / transforms); a `{code, message}` body is a failed read. A re-run re-validates every cached raw
hint first and stops, naming it, on a bad one. Phase 2 builds every record, the index, the batches and the catalogue
and runs every check (authoring invariance, chainOuterParameters invariance, the archive path) before the first write
under data/: a failing check exits non-zero with data/ untouched.

2026-11-08 (review pass 2, finding 9): the contract the hints were read at is read, never assumed. Phase 1 reads GET
/mcp/version (VERSION_URL, the probes' endpoint; EXTRACTION_VERSION_URL overrides it for an offline test) before its
first fetch, every VERSION_EVERY fetches and after its last one, and stores {contractVersion, buildSha, readAt} in
hints_<STAMP>/_version.json at the first read. A resume whose served contract (version or build) differs from it, a
contract that moves mid-fetch, or a failed read stops the fetch. A partial raw dir with no _version.json (cached by an
earlier version of this script) is not resumed: its hints' contract is unknown. Phase 2 refuses to build without
_version.json unless EXTRACTION_CONTRACT asserts the contract (recorded as asserted, not read), and refuses when
EXTRACTION_CONTRACT differs from it. _index.json records contractVersion / buildSha and how they were known.

Re-run 2026-09-20 at contract 61.2.0. EXTRACTION_SCRATCH and EXTRACTION_STAMP replace the constants the
first run pinned to one session's scratch directory, which no longer exists.
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

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
# v135 (README "Contract history - v135") replaced rankableSpreadOperands with chainedOuters: present exactly when
# chainSuccessors is, keyed by its members, each {operands, windowMaximum}. The old flag is kept in the tuple so a
# pre-135 raw dir still refreshes as it did.
TRANSFORM_FLAGS = ("operandRequired", "chainSuccessors", "chainedRankOrderings",
                   "sideRequired", "rankableSpreadOperands", "chainedOuters")


OWN_LENGTH = re.compile(r" (Separate from .+? own \d+-bar length\.)$")
# mcporter's stderr when the stored OAuth credential has no usable token (seen 2026-11-05 from ~10:18Z).
AUTH_MARKERS = ("/authorize", "If the browser did not open", "OAuth", "Unauthorized", "401")
# The endpoint probe_authoring_148 / probe_knob_spelling_149 / sweep_render_coverage read (VERSION_URL there). This
# script runs standalone (a copy in a throwaway tree in the tests), so it does not import it.
VERSION_URL = os.environ.get("EXTRACTION_VERSION_URL") or "https://mcp.battlegrid.trade/mcp/version"
VERSION_EVERY = 40                    # fetches between two version reads (the 11-06 fetch_hints.py gate)
VERSION_FILE = os.path.join(RAW, "_version.json")
ASSERTED = os.environ.get("EXTRACTION_CONTRACT") or None


def version():
    """-> ({contractVersion, buildSha, readAt}, None) or (None, why). Never raises."""
    try:
        with urllib.request.urlopen(VERSION_URL, timeout=30) as r:
            v = json.loads(r.read().decode())
    except (OSError, ValueError) as exc:      # HTTPError / URLError / timeout; a body that is not JSON
        return None, f"GET /mcp/version failed ({type(exc).__name__}: {str(exc)[:200]})"
    if not isinstance(v, dict) or not v.get("contractVersion"):
        return None, f"GET /mcp/version answered no contract: {str(v)[:200]}"
    return {"contractVersion": v["contractVersion"], "buildSha": v.get("buildSha"),
            "readAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, None


def stored_version():
    """hints_<STAMP>/_version.json, None when absent. A file that is not a version record stops the run."""
    if not os.path.exists(VERSION_FILE):
        return None
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            v = json.load(f)
    except (OSError, ValueError) as exc:
        sys.exit(f"{VERSION_FILE} is unreadable ({type(exc).__name__}: {str(exc)[:120]}). Nothing under data/ was "
                 "written.")
    if not isinstance(v, dict) or not v.get("contractVersion"):
        sys.exit(f"{VERSION_FILE} names no contractVersion: {str(v)[:200]}. Nothing under data/ was written.")
    return v


def taint(reason):
    """Mark hints_<STAMP>/_version.json so no later run builds from or adds to this raw dir: its hints are no longer
    known to be of one contract (review pass 2 re-review, 2026-11-08: the stop alone left the old _version.json, and a
    re-run with nothing left to fetch built a mixed corpus labelled as read at the old contract)."""
    v = stored_version()
    if v is None:
        return
    v["tainted"] = {"reason": reason, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    tmp = VERSION_FILE + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, indent=1)
    os.replace(tmp, VERSION_FILE)


def refuse_if_tainted(v):
    if v is not None and v.get("tainted"):
        sys.exit(f"{VERSION_FILE} is marked tainted ({v['tainted']['reason'][:200]}, {v['tainted']['at']}): the hints "
                 f"in {RAW} may span two contracts. Start a new EXTRACTION_STAMP. Nothing under data/ was written.")


def same_contract(a, b):
    return (a.get("contractVersion"), a.get("buildSha")) == (b.get("contractVersion"), b.get("buildSha"))


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


# 2026-11-08 (review pass 1, findings 1 and 2): a raw hint is cached only when it IS a hint. mcporter prints a platform
# error ({code, message}: INTERNAL_ERROR, SERVICE_UNAVAILABLE, an unknown-metric refusal) as JSON on stdout, and the
# first two-phase version cached any JSON it got: phase 2 then died on `KeyError: 'metric'` after rewriting some metric
# files, and "resumable" skipped the poisoned file on every re-run.
HINT_KEYS = ("metric", "code", "family", "transforms")


def hint_problem(resp, cached=False):
    """None when `resp` is a construction hint ({metric: {metric, code, family, transforms, ...}, ...}); else why not.

    `cached`: a raw hint already on disk from an earlier run may also be the flat shape (the metric object itself at the
    top level), which phase 2 has always read; a fresh answer must be the served wrapped shape."""
    if not isinstance(resp, dict):
        return f"not a JSON object ({type(resp).__name__})"
    m = resp.get("metric")
    if not isinstance(m, dict):
        if "code" in resp and ("message" in resp or "metric" not in resp):
            return f"a platform error body: {resp.get('code')}: {str(resp.get('message'))[:160]}"
        if not cached:
            return "no `metric` object"
        m = resp                                   # the flat shape of an earlier raw dir
    missing = [k for k in HINT_KEYS if k not in m]
    if missing:
        return f"the hint's metric lacks {missing}"
    if not isinstance(m["transforms"], list):
        return "`transforms` is not a list"
    return None


records = {}
labels = {}           # transformId -> label (served on the transform entry, beside its authoring block)

authoring_seen = {}   # transformId -> {json of authoring block: [metrics]}
outer_params_seen = {}  # v135 chainOuterParameters (served once per response, beside `metric`): {json: [metrics]}
failed = []

# Resume: every raw hint already on disk is re-validated before anything is fetched. A bad one (an error body cached by
# an earlier run, a truncated file) stops the run with nothing written: delete it and re-run, which re-reads it.
bad_cached = {}
for name in names:
    rawp = os.path.join(RAW, f"{name}.json")
    if not os.path.exists(rawp):
        continue
    try:
        with open(rawp, encoding="utf-8") as f:
            problem = hint_problem(json.load(f), cached=True)
    except (OSError, ValueError) as exc:
        problem = f"unreadable ({type(exc).__name__}: {str(exc)[:120]})"
    if problem:
        bad_cached[name] = problem
if bad_cached:
    for name, problem in bad_cached.items():
        print(f"  cached raw hint {os.path.join(RAW, name + '.json')}: {problem}")
    sys.exit(f"{len(bad_cached)} cached raw hint(s) are not hints ({sorted(bad_cached)[:10]}): delete them and re-run. "
             "Nothing under data/ was written.")

# Phase 1: every raw hint on disk. Nothing under data/ is touched here.
# 2026-11-08 (review pass 2, finding 9): the served contract is read before the first fetch and every VERSION_EVERY
# fetches; the hints of one raw dir are all of one contract and build, or the fetch stops.
contract_read = stored_version()
refuse_if_tainted(contract_read)
cached_before = sum(os.path.exists(os.path.join(RAW, f"{n}.json")) for n in names)
fetched = 0


def gate(when):
    """Read the served contract; stop the fetch (nothing under data/ written) on a failed read or a move."""
    global contract_read
    now, why = version()
    if now is None:
        if fetched:                    # the hints since the last read are of an unverified contract
            taint(f"version read failed {when}: {why}")
        sys.exit(f"{why} ({when}): fetch stopped after {fetched} fetches. Nothing under data/ was written.")
    if contract_read is None:
        if cached_before:
            sys.exit(f"{cached_before} raw hint(s) are already in {RAW} with no _version.json: the contract they were "
                     "read at is unknown, so this fetch cannot add to them. Start a new EXTRACTION_STAMP (or, when "
                     "every hint is cached, run phase 2 with EXTRACTION_CONTRACT). Nothing under data/ was written.")
        contract_read = now
        tmp = VERSION_FILE + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(now, f, ensure_ascii=False, indent=1)
        os.replace(tmp, VERSION_FILE)
        print(f"  served contract {now['contractVersion']} ({now['buildSha']}) at {now['readAt']}: {VERSION_FILE}")
    elif not same_contract(now, contract_read):
        taint(f"served {now['contractVersion']} ({now['buildSha']}) {when}, read at {contract_read['contractVersion']} "
              f"({contract_read.get('buildSha')})")
        sys.exit(f"the served contract is {now['contractVersion']} ({now['buildSha']}) {when}, but the hints in {RAW} "
                 f"were read at {contract_read['contractVersion']} ({contract_read.get('buildSha')}): fetch stopped "
                 f"after {fetched} fetches (the hints fetched since the last matching read may be of either). Start a "
                 "new EXTRACTION_STAMP. Nothing under data/ was written.")


for i, name in enumerate(names, 1):
    rawp = os.path.join(RAW, f"{name}.json")
    if os.path.exists(rawp):
        continue
    if fetched % VERSION_EVERY == 0:
        gate("before the first fetch" if fetched == 0 else f"after {fetched} fetches")
    fetched += 1
    resp, err = call("get_metric_construction_hints", {"metric": name})
    if resp is None:
        print(f"  [{i}/{len(names)}] {name}: FAILED {err}")
        failed.append(name)
        if any(marker in (err or "") for marker in AUTH_MARKERS):
            failed.extend(n for n in names[i:] if not os.path.exists(os.path.join(RAW, f"{n}.json")))
            print("  mcporter has no usable credential for battlegrid-anbu: fetch stopped (re-authorizing is the "
                  "user's step)")
            break
        continue
    problem = hint_problem(resp)
    if problem:                    # an answer, but not a hint: a fetch failure, never cached
        print(f"  [{i}/{len(names)}] {name}: FAILED (not cached) {problem}")
        failed.append(name)
        continue
    tmp = rawp + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(resp, f, ensure_ascii=False)
    os.replace(tmp, rawp)
    if i % 20 == 0:
        print(f"  [{i}/{len(names)}] read ... {name}")
if failed:
    print(f"\nnot read: {len(failed)} of {len(names)} ({failed[:5]}{' ...' if len(failed) > 5 else ''}); "
          f"{len(names) - len(failed)} raw hints are in {RAW} and a re-run skips them. Nothing under data/ was written.")
    sys.exit(1)
if fetched:
    gate("after the last fetch")          # the hints since the last read were read at the same contract too

# Phase 2's contract: read (hints_<STAMP>/_version.json), or asserted (EXTRACTION_CONTRACT) - never neither, never two.
contract_read = stored_version()
refuse_if_tainted(contract_read)
if contract_read is None and ASSERTED is None:
    sys.exit(f"{VERSION_FILE} is missing: the contract these hints were read at is unknown. Set EXTRACTION_CONTRACT "
             "to assert it (recorded as asserted, not read), or re-fetch under a new EXTRACTION_STAMP. Nothing under "
             "data/ was written.")
if contract_read is not None and ASSERTED is not None and ASSERTED != contract_read["contractVersion"]:
    sys.exit(f"EXTRACTION_CONTRACT {ASSERTED} differs from the contract the hints were read at "
             f"({contract_read['contractVersion']}, {VERSION_FILE}). Nothing under data/ was written.")
if contract_read is not None:
    CONTRACT_FIELDS = {"contractVersion": contract_read["contractVersion"], "buildSha": contract_read.get("buildSha"),
                       "contractKnownBy": f"read: GET /mcp/version at {contract_read.get('readAt')} before the first "
                                          f"fetch of extraction {STAMP} (hints_{STAMP}/_version.json)"}
else:
    CONTRACT_FIELDS = {"contractVersion": ASSERTED, "buildSha": None,
                       "contractKnownBy": f"asserted: EXTRACTION_CONTRACT, not read (hints_{STAMP} has no "
                                          "_version.json)"}
print(f"contract: {CONTRACT_FIELDS['contractVersion']} ({CONTRACT_FIELDS['contractKnownBy']})")


def build_record(name, resp):
    """One metric file's content (and the transform side-tables) from its raw hint. Nothing is written here."""
    m = resp["metric"] if isinstance(resp, dict) and "metric" in resp and isinstance(resp["metric"], dict) else resp
    if isinstance(resp, dict) and "chainOuterParameters" in resp:
        outer_params_seen.setdefault(json.dumps(resp["chainOuterParameters"], sort_keys=True), []).append(name)
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
    # 144.0.0 (2026-10-30): two more served scalars, recorded as served. `provenance` (README v138: `tradingView`
    # where TradingView publishes the same value at its default settings, `battleGridDerived` where it does not) and
    # `rankScope` (v136: the ranked set a `rank` column reads - `exchangeWide` on a metric the platform ranks).
    for served in ("provenance", "rankScope"):
        if served in m:
            rec[served] = m[served]
    # 148.1.0 (2026-11-05, README v146 / v146.9 / v146.11): every metric serves `gloss`, `subjectKinds` (the section
    # subjects that read it: evaluated-coin, benchmark, market, reference) and `parameters` (its author-set knobs, each
    # with defaultValue / minimum / maximum / step / bound / required / description; null on a metric with none).
    # Recorded as served.
    for served in ("gloss", "subjectKinds", "parameters"):
        if served in m:
            rec[served] = m[served]
    for t in m.get("transforms", []):
        entry = {"id": t["id"]}
        for flag in TRANSFORM_FLAGS:
            if flag in t:
                entry[flag] = t[flag]
        # v146.9: whether this column accepts the metric's knobs off their defaults (false on a metric with none, and
        # where an off-default knob is refused: rank / relativeTo / aggregate / ema). Per metric x transform.
        if "metricParametersAccepted" in t:
            entry["metricParametersAccepted"] = t["metricParametersAccepted"]
        rec["transforms"].append(entry)
        labels.setdefault(t["id"], t.get("label"))
        if "authoring" in t:
            # 108.4.0: a parameter's `maximum` is served PER METRIC (value.offset: 0 on a timeless metric, 31 on most
            # candle metrics, 30/21/12/11 on the bar-geometry ones); everything else in the block is invariant. The
            # maxima go on this metric's transform entry; the catalogue keeps the invariant rest.
            auth = json.loads(json.dumps(t["authoring"]))
            maxima = {}
            bounds = {}
            for pname, pspec in (auth.get("parameters") or {}).items():
                if isinstance(pspec, dict) and "maximum" in pspec:
                    maxima[pname] = pspec.pop("maximum")
                # v146.7: every served bounded window carries `bound` (lookback | depth) beside its `maximum` - per
                # metric like the maximum it qualifies, so it goes on the metric's entry as `bounds`.
                if isinstance(pspec, dict) and "bound" in pspec:
                    bounds[pname] = pspec.pop("bound")
            if maxima:
                entry["maximums"] = maxima
            if bounds:
                entry["bounds"] = bounds
            # 135.x: a series window's description ends, on a metric with its own indicator length, with a sentence
            # naming it ("Separate from ADX (14)'s own 14-bar length."). It is served per metric like the maxima, so
            # it goes on the metric's entry and the catalogue keeps the invariant rest.
            win = (auth.get("parameters") or {}).get("window")
            if isinstance(win, dict) and isinstance(win.get("description"), str):
                found = OWN_LENGTH.search(win["description"])
                if found:
                    entry["windowOwnLength"] = found.group(1)
                    win["description"] = win["description"][:found.start()]
            blob = json.dumps(auth, sort_keys=True)
            authoring_seen.setdefault(t["id"], {}).setdefault(blob, []).append(m["metric"])
    if m.get("spreadOperands"):
        rec["spreadOperands"] = m["spreadOperands"]
    # 161.0.0 (2026-11-09, undocumented): the operands a spread takes when it reads off the anchor bar, served per
    # metric beside spreadOperands (null on a metric with none). Recorded as served.
    if m.get("spreadOperandsOffAnchor"):
        rec["spreadOperandsOffAnchor"] = m["spreadOperandsOffAnchor"]
    if m.get("rankOrderings"):
        rec["rankOrderings"] = m["rankOrderings"]
    return rec


# Phase 2 (2026-11-08, review pass 1 finding 2): every record, the index, the batches and the catalogue are built and
# every check is run IN MEMORY first - the authoring invariance, the chainOuterParameters invariance and the archive
# path. The first two-phase version wrote the metric files and _index.json (and moved the batches) before those checks,
# so a failing check left the records at the new stamp and the catalogue at the old one. Nothing under data/ is written
# unless every check passes.
for i, name in enumerate(names, 1):
    rawp = os.path.join(RAW, f"{name}.json")
    try:
        with open(rawp, encoding="utf-8") as f:
            records[name] = build_record(name, json.load(f))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        sys.exit(f"raw hint {rawp} cannot be built into a record ({type(exc).__name__}: {str(exc)[:160]}); "
                 "nothing under data/ was written")
    if i % 20 == 0 or i == len(names):
        print(f"  [{i}/{len(names)}] built ... {name}")

# metrics the platform no longer serves (removed in the write step)
retired = sorted(os.path.basename(path)[:-5] for path in glob.glob(os.path.join(OUT, "*.json"))
                 if not os.path.basename(path).startswith("_") and os.path.basename(path)[:-5] not in names)

# index
by_family = {}
for name in sorted(records):
    by_family.setdefault(records[name]["family"], []).append(name)
idx = {"metricCount": len(records), "byFamily": {k: sorted(v) for k, v in sorted(by_family.items())},
       **CONTRACT_FIELDS}

# authoring-invariance re-check (the evidence goes to the scratch dir, never under data/)
variants = {tid: len(blobs) for tid, blobs in authoring_seen.items()}
with open(os.path.join(SP, "authoring_invariance_" + STAMP + ".json"), "w", encoding="utf-8") as f:
    json.dump({"_what": "get_metric_construction_hints authoring blocks grouped by transform, "
                        "2026-09-09 sweep. variants>1 would falsify the invariance claim in "
                        "transforms/_authoring.json.",
               "variantsPerTransform": variants,
               "metricsPerTransform": {t: sum(len(v) for v in b.values()) for t, b in authoring_seen.items()}},
              f, ensure_ascii=False, indent=1)
print(f"\nbuilt {len(records)}; retiring {retired}")
print("authoring variants per transform (1 == invariant):", variants)

# The batches build_corpus merges: the ones this run replaces are archived, then the new set is written in platform
# order, 30 per batch (the shape of every earlier extraction's batches).
arch = os.path.join(OUT, f"archive_{ARCHIVE}_extraction")
old = sorted(glob.glob(os.path.join(OUT, "_batch*.json")))
ordered = [records[n] for n in names if n in records]
batches = [ordered[b:b + 30] for b in range(0, len(ordered), 30)]

# The transform catalogue (data/contract/transforms/_authoring.json), built in memory.
cat_path = os.path.join(ROOT, "data", "contract", "transforms", "_authoring.json")
cat = json.load(open(cat_path, encoding="utf-8"))
added, changed = [], []
problems = []
# v135's chainOuterParameters, the parameters each chain outer takes (window with its `unit`, bars): recorded only
# when every response serves the same block, like the authoring catalogue.
if len(outer_params_seen) > 1:
    problems.append(f"chainOuterParameters VARY across metrics ({len(outer_params_seen)} variants) - not recorded")
# The catalogue only when every transform's authoring block is invariant across the metrics that serve it - otherwise
# the catalogue's own claim is false.
if any(v != 1 for v in variants.values()):
    problems.append("authoring blocks VARY across metrics - the catalogue is not refreshed; inspect "
                    f"{os.path.join(SP, 'authoring_invariance_' + STAMP + '.json')}")
if old and os.path.exists(arch):
    problems.append(f"{arch} already exists: the batches this run replaces cannot be archived there (give "
                    "EXTRACTION_ARCHIVE the stamp of the batches being replaced)")
if problems:
    for p in problems:
        print(f"  CHECK FAILED: {p}")
    sys.exit(f"{len(problems)} check(s) failed: {'; '.join(problems)}. Nothing under data/ was written.")

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

# Every check passed: write.
for name in names:
    with open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(records[name], f, indent=2, ensure_ascii=False)
        f.write("\n")
for name in retired:
    os.remove(os.path.join(OUT, f"{name}.json"))
with open(os.path.join(OUT, "_index.json"), "w", encoding="utf-8") as f:
    json.dump(idx, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"written {len(records)}; retired {retired}")

if old:
    os.makedirs(arch, exist_ok=False)
    for path in old:
        os.replace(path, os.path.join(arch, os.path.basename(path)))
for n, chunk in enumerate(batches, 1):
    with open(os.path.join(OUT, f"_batch{n:02d}.json"), "w", encoding="utf-8") as f:
        json.dump(chunk, f, indent=1, ensure_ascii=False)
        f.write("\n")
print(f"batches: {len(old)} archived to {os.path.basename(arch)}; {len(batches)} written")

if outer_params_seen:
    with open(os.path.join(ROOT, "data", "contract", "transforms", "_chain_outer_parameters.json"), "w",
              encoding="utf-8") as f:
        json.dump({"_what": "get_metric_construction_hints chainOuterParameters (contract v135+): each chain outer's "
                            "parameters, served identically on every metric of extraction " + STAMP,
                   "chainOuterParameters": json.loads(next(iter(outer_params_seen)))},
                  f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"chainOuterParameters: invariant across {len(next(iter(outer_params_seen.values())))} metrics")

with open(cat_path, "w", encoding="utf-8") as f:
    json.dump(cat, f, indent=1, ensure_ascii=False)
    f.write("\n")
print(f"catalogue: added {added}; authoring changed on {changed}; untouched (no metric serves them): "
      f"{sorted(set(cat['transforms']) - set(authoring_seen))}")
