"""Build and PREVIEW (no writes) a corrected, purely-TPO condition ladder for 56c08ef6.

WHAT WAS WRONG, measured 2026-09-11 over all 36 CRYPTO instruments on 3d720de3:
  5 of 11 conditions fired but never decided a verdict -- unreachable, because verdict
  resolution is FIRST-TRUE-WINS in array order and VAL_CONFLUENCE_UP fired 32/36 from
  index 3. 31 of 36 verdicts (86%) were decided by two conditions, NEITHER of which
  compares a TPO level to price: both compare a TPO level to a DONCHIAN band. Every
  condition expressing price-versus-prior-value -- the actual Market Profile thesis --
  was dead code. POC_ABOVE was true on 26/36 and decided nothing, ever.

WHAT THIS BUILDS INSTEAD: a value-migration ladder built from TPO-versus-TPO columns,
which no live strategy uses. `spread` accepts any metric as its operand, so the current
session's developing profile can be compared directly against the prior session's, with
no history required -- which matters because TPO has no history by any route here.

  tpoPOC vs pTpoVAH  -> developing value has migrated ABOVE prior value entirely
  tpoPOC vs pTpoVAL  -> ... or BELOW it entirely
  tpoPOC vs pTpoPOC  -> direction of value migration while still inside prior value
  CLOSE  vs tpoPOC   -> price versus the DEVELOPING point of control (confirmation)

The ladder is ordered most-specific-first so that it PARTITIONS the universe: every
instrument is decided, and every condition is reachable by construction.

THE FIRST-UTC-HOUR GAP: every tpo* (current-session) metric is, in the platform's own
words, "absent for the session's first 60 minutes", and a clause on an absent value reads
FALSE. So conditions 0-6 all read FALSE in the first UTC hour and the verdict would be
UNRESOLVED. Conditions 7-9 are a fallback tier using ONLY pTpo* columns, which are
available around the clock. They are unreachable during normal hours BY DESIGN -- that is
a fallback tier, not dead code -- and they are UNVERIFIED until a run between 00:00 and
01:00 UTC, which cannot be forced.

Read-only. This script previews only; it performs NO compile and NO apply.
"""
import json, os, subprocess, sys
from collections import Counter

ALLOWED = {"preview_strategy_report", "get_coin_metadata", "get_strategy"}
STRAT = "56c08ef6-480b-4293-8136-81beed2161cf"
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
        return None, json.dumps(j)[:1600]
    return j, None

meta, err = call("get_coin_metadata", {})
if meta is None:
    print("metadata failed:", err); sys.exit(1)
crypto = sorted(c["ticker"] for c in meta["coins"]
                if c.get("assetClass") == "CRYPTO" and c.get("isActive"))

live, err = call("get_strategy", {"strategyId": STRAT})
if live is None:
    print("strategy read failed:", err); sys.exit(1)
live = live.get("strategy", live)
SK = live["sections"][0]["sectionKey"]          # reuse the OWNED key; UPDATE accepts it
print("reusing owned sectionKey:", SK)

def S(metric, operand):
    return {"metric": metric, "transformId": "spread", "timeframe": {"rel": "anchor"},
            "inputs": [{"metric": operand}]}

COLUMNS = [
    # prior-session location, available around the clock
    S("PRIOR_TPO_VAH", "CLOSE"),
    S("PRIOR_TPO_VAL", "CLOSE"),
    S("PRIOR_TPO_POC", "CLOSE"),
    S("PRIOR_TPO_VAH", "PRIOR_TPO_VAL"),        # prior value WIDTH, the normaliser
    S("PRIOR_TPO_VAL", "OPEN"),                 # the only lawful origin read
    # developing-vs-prior value migration, the core of this revision
    S("TPO_POC", "PRIOR_TPO_VAH"),
    S("TPO_POC", "PRIOR_TPO_VAL"),
    S("TPO_POC", "PRIOR_TPO_POC"),
    S("CLOSE", "TPO_POC"),
    S("TPO_VAH", "TPO_VAL"),                    # developing value width
    {"metric": "TPO_SHAPE", "transformId": "value", "timeframe": {"rel": "anchor"}},
]

def H(metric_code, operand_code=None, transform="spread"):
    """Header spelling the server generates: <code>_<operandCode>_<transform>."""
    return metric_code + ("_" + operand_code if operand_code else "") + "_" + transform

def clause(header, op, **kw):
    d = {"kind": "clause", "column": {"sectionKey": SK, "header": header}, "op": op}
    d.update(kw)
    return d

def allof(*m):
    return {"kind": "group", "op": "ALL", "members": list(m)}

def cond(key, name, definition, verdict):
    return {"conditionKey": key, "name": name, "definition": definition,
            "verdict": verdict, "required": False, "exit": False,
            "clock": "LIVE", "closes": 1}

# header spellings, read off the probe output rather than guessed
h_pVAH_close = "pTpoVAH_close_spread"
h_pVAL_close = "pTpoVAL_close_spread"
h_POC_pVAH   = "tpoPOC_pTpoVAH_spread"
h_POC_pVAL   = "tpoPOC_pTpoVAL_spread"
h_POC_pPOC   = "tpoPOC_pTpoPOC_spread"
h_close_POC  = "close_tpoPOC_spread"

CONDITIONS = [
    # --- tier 1: value migrated clean of prior value (most specific first) ---
    cond("VALUE_ABOVE_CONFIRMED",
         "Developing value above all prior value, price above developing POC",
         allof(clause(h_POC_pVAH, "gte", value=0.0), clause(h_close_POC, "gte", value=0.0)),
         "UP"),
    cond("VALUE_ABOVE",
         "Developing point of control above the entire prior value area",
         clause(h_POC_pVAH, "gte", value=0.0), "UP"),
    cond("VALUE_BELOW_CONFIRMED",
         "Developing value below all prior value, price below developing POC",
         allof(clause(h_POC_pVAL, "lte", value=0.0), clause(h_close_POC, "lte", value=0.0)),
         "DOWN"),
    cond("VALUE_BELOW",
         "Developing point of control below the entire prior value area",
         clause(h_POC_pVAL, "lte", value=0.0), "DOWN"),
    # --- tier 2: still inside prior value, so read the direction of migration ---
    cond("VALUE_RISING_IN_BALANCE",
         "Developing point of control building above the prior point of control",
         clause(h_POC_pPOC, "gte", value=0.25), "UP"),
    cond("VALUE_FALLING_IN_BALANCE",
         "Developing point of control building below the prior point of control",
         clause(h_POC_pPOC, "lte", value=-0.25), "DOWN"),
    cond("VALUE_UNCHANGED_IN_BALANCE",
         "Developing point of control sitting on the prior point of control",
         clause(h_POC_pPOC, "between", low=-0.25, high=0.25), "NEITHER"),
    # --- tier 3: fallback for the first UTC hour, prior-session columns only ---
    cond("PRE_PROFILE_BELOW_VALUE",
         "No developing profile yet, close below prior value low",
         clause(h_pVAL_close, "gte", value=0.05), "DOWN"),
    cond("PRE_PROFILE_ABOVE_VALUE",
         "No developing profile yet, close above prior value high",
         clause(h_pVAH_close, "lte", value=-0.05), "UP"),
    cond("PRE_PROFILE_INSIDE_VALUE",
         "No developing profile yet, close inside prior value",
         allof(clause(h_pVAL_close, "lt", value=0.05),
               clause(h_pVAH_close, "gt", value=-0.05)), "NEITHER"),
]

SECTION = {"kind": "custom", "sectionKey": SK,
           "title": "TPO value migration",
           "benchmarkTicker": None,
           "notes": ("Developing (current UTC session) value area against the prior "
                     "completed session's. Positive spread means the first metric sits "
                     "above the second."),
           "columns": COLUMNS}

def one(tickers):
    return call("preview_strategy_report",
                {"timeframe": "1h",
                 "coinSelection": {"mode": "explicit", "tickers": tickers},
                 "sections": [SECTION], "conditions": CONDITIONS})

outs, rows = [], []
for i in range(0, len(crypto), BATCH):
    chunk = crypto[i:i + BATCH]
    pv, err = one(chunk)
    if pv is None:
        print("BATCH %s REFUSED:\n%s" % (",".join(chunk), err)); sys.exit(1)
    outs.extend(pv.get("conditionOutcomes", []))
    txt = pv["renderedSections"][0]["section"]["text"]
    tbl = [r for r in txt.splitlines() if r.startswith("|")]
    rows.extend(tbl if not rows else tbl[2:])
    print("  batch ok: " + ",".join(chunk))

print()
print("\n".join(rows))
print()

order = [c["conditionKey"] for c in CONDITIONS]
verd = {c["conditionKey"]: c["verdict"] for c in CONDITIONS}
fires, decides = Counter(), Counter()
for o in outs:
    for x in o["outcomes"]:
        if x["outcome"] == "TRUE":
            fires[x["conditionKey"]] += 1
    if o.get("decidedBy"):
        decides[o["decidedBy"]] += 1

n = len(outs)
print("=== REACHABILITY of the proposed ladder over %d instruments ===" % n)
print("%-3s %-27s %-8s %9s %9s  %s" % ("#", "conditionKey", "verdict", "fires", "decides", "note"))
for i, k in enumerate(order):
    f, d = fires.get(k, 0), decides.get(k, 0)
    if i >= 7:
        note = "fallback tier - expected 0 outside the first UTC hour"
    elif d == 0 and f == 0:
        note = "reachable by construction, not observed at this instant"
    elif d == 0:
        note = "UNREACHABLE - fires but never decides"
    else:
        note = "deciding"
    print("%-3d %-27s %-8s %5d/%-3d %5d/%-3d  %s" % (i, k, verd[k], f, n, d, n, note))

print()
print("verdict tally:", json.dumps(dict(Counter(str(o.get("verdict")) for o in outs))))
unresolved = [o["ticker"] for o in outs if not o.get("decidedBy")]
print("instruments with NO deciding condition:", unresolved or "none")
print()
for o in outs:
    print("  %-9s %-9s %s" % (o["ticker"], str(o.get("verdict")), o.get("decidedBy")))

d = os.path.dirname(os.path.abspath(__file__))
json.dump({"section": SECTION, "conditions": CONDITIONS},
          open(os.path.join(d, "rev4_payload.json"), "w", encoding="utf-8"), indent=1)
print()
print("payload saved:", os.path.join(d, "rev4_payload.json"))
