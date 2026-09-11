"""Reachability audit of the LIVE TPO strategy's conditions.

Verdict resolution on this platform is FIRST-TRUE-WINS in array order (measured
2026-09-10). That makes a condition placed after a near-tautology UNREACHABLE: it can
be TRUE and still never decide anything. This script takes the live section and
conditions VERBATIM, previews them across the platform's whole CRYPTO universe, and
reports for each condition:

  fires   - how often the clause evaluates TRUE
  decides - how often it is the one that actually sets the verdict

A condition with fires > 0 and decides == 0 is dead code.

The preview result is capped at 256000 bytes, so the universe is batched and merged.
Read-only. Allowlisted to three reads.
"""
import json, os, subprocess, sys
from collections import Counter

ALLOWED = {"preview_strategy_report", "get_coin_metadata", "get_strategy"}
STRAT = "3d720de3-6d36-4ef8-ae74-87bd8b6025bd"
BATCH = 9

def call(tool, args, timeout=900):
    if tool not in ALLOWED:
        raise RuntimeError("refusing non-allowlisted tool: " + tool)
    p = subprocess.Popen(["cmd", "/c", "npx", "--no-install", "mcporter", "call",
                          "battlegrid-anbu." + tool, "--output", "json", "--args", "-"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(json.dumps(args).encode(), timeout=timeout)
    o, e = out.decode(errors="replace"), err.decode(errors="replace")
    if p.returncode != 0 or not o.strip():
        return None, (e or o)[:900] or "(empty, rc=%s)" % p.returncode
    j = json.loads(o)
    if isinstance(j, dict) and j.get("isError"):
        return None, json.dumps(j)[:1500]
    return j, None

meta, err = call("get_coin_metadata", {})
if meta is None:
    print("metadata failed:", err); sys.exit(1)
crypto = sorted(c["ticker"] for c in meta["coins"]
                if c.get("assetClass") == "CRYPTO" and c.get("isActive"))

s, err = call("get_strategy", {"strategyId": STRAT})
if s is None:
    print("strategy read failed:", err); sys.exit(1)
s = s.get("strategy", s)

def one(tickers):
    req = {"timeframe": "1h",
           "coinSelection": {"mode": "explicit", "tickers": tickers},
           "sections": [dict(s["sections"][0])],
           "conditions": s["conditions"]}
    return call("preview_strategy_report", req)

outs, rows = [], []
for i in range(0, len(crypto), BATCH):
    chunk = crypto[i:i + BATCH]
    pv, err = one(chunk)
    if pv is None:
        print("batch %s failed: %s" % (",".join(chunk), err)); sys.exit(1)
    outs.extend(pv.get("conditionOutcomes", []))
    txt = pv["renderedSections"][0]["section"]["text"]
    tbl = [r for r in txt.splitlines() if r.startswith("|")]
    rows.extend(tbl if not rows else tbl[2:])
    print("  batch ok: " + ",".join(chunk))

print()
print("\n".join(rows))
print()

order = [c["conditionKey"] for c in s["conditions"]]
verdicts = {c["conditionKey"]: c.get("verdict") for c in s["conditions"]}
fires, decides = Counter(), Counter()
for o in outs:
    for x in o["outcomes"]:
        if x["outcome"] == "TRUE":
            fires[x["conditionKey"]] += 1
    d = o.get("decidedBy")
    if d:
        decides[d] += 1

n = len(outs)
print("=== REACHABILITY over %d CRYPTO instruments (first-true-wins, array order) ===" % n)
print("%-3s %-22s %-8s %9s %9s  %s" % ("#", "conditionKey", "verdict", "fires", "decides", "status"))
for i, k in enumerate(order):
    f, d = fires.get(k, 0), decides.get(k, 0)
    if f == 0:
        st = "DEAD - never fires"
    elif d == 0:
        st = "UNREACHABLE - fires but never decides"
    elif f == n:
        st = "TAUTOLOGY - always true"
    else:
        st = "live"
    print("%-3d %-22s %-8s %5d/%-3d %5d/%-3d  %s" % (i, k, str(verdicts[k]), f, n, d, n, st))

print()
print("verdict tally:", json.dumps(dict(Counter(str(o.get("verdict")) for o in outs))))
print()
print("=== per-instrument ===")
for o in outs:
    print("  %-9s %-9s decidedBy=%s" % (o["ticker"], str(o.get("verdict")), o.get("decidedBy")))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reach_raw.json")
json.dump({"conditionOutcomes": outs}, open(out, "w", encoding="utf-8"), indent=1)
print()
print("saved:", out)
