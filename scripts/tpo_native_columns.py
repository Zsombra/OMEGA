"""Measure the TPO-versus-TPO column space, which the live strategies never use.

The live TPO strategy only ever spreads a TPO level against CLOSE or against a DONCHIAN
band. But `spread` takes ANY metric as its operand, so TPO-vs-TPO columns are legal:

  TPO_POC   vs PRIOR_TPO_POC   -> value migration: is today's developing POC building
                                  above or below yesterday's POC?
  TPO_VAH   vs PRIOR_TPO_VAH   -> value-area migration, upper edge
  TPO_VAL   vs PRIOR_TPO_VAL   -> value-area migration, lower edge
  TPO_POC   vs PRIOR_TPO_VAH   -> is today's POC building ABOVE yesterday's whole value?
  TPO_POC   vs PRIOR_TPO_VAL   -> ... or BELOW it?
  PRIOR_TPO_VAH vs PRIOR_TPO_VAL -> prior value-area WIDTH as a percentage
  TPO_VAH   vs TPO_VAL         -> developing value width
  TPO_IB_HIGH vs TPO_IB_LOW    -> initial-balance width
  CLOSE     vs TPO_POC         -> price versus the DEVELOPING point of control

Every one of these is a current read. None needs history, which matters because TPO has
no history by any route on this platform (offset inert, chaining refused, CLOSE clock
refused -- all measured previously).

Read-only. Allowlisted to two reads. Batched because preview caps results at 256000 bytes.
"""
import json, os, subprocess, sys, uuid

ALLOWED = {"preview_strategy_report", "get_coin_metadata"}
BATCH = 12

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
print("universe: %d CRYPTO instruments" % len(crypto))

def S(metric, operand):
    return {"metric": metric, "transformId": "spread", "timeframe": {"rel": "anchor"},
            "inputs": [{"metric": operand}]}

cols = [
    S("TPO_POC", "PRIOR_TPO_POC"),          # POC migration
    S("TPO_VAL", "PRIOR_TPO_VAL"),          # value-area migration, low edge
    S("TPO_VAH", "PRIOR_TPO_VAH"),          # value-area migration, high edge
    S("TPO_POC", "PRIOR_TPO_VAH"),          # developing POC vs prior value top
    S("TPO_POC", "PRIOR_TPO_VAL"),          # developing POC vs prior value bottom
    S("PRIOR_TPO_VAH", "PRIOR_TPO_VAL"),    # prior value width
    S("TPO_VAH", "TPO_VAL"),                # developing value width
    S("TPO_IB_HIGH", "TPO_IB_LOW"),         # initial balance width
    S("CLOSE", "TPO_POC"),                  # price vs developing POC
    {"metric": "TPO_SHAPE", "transformId": "value", "timeframe": {"rel": "anchor"}},
]

def one(tickers):
    req = {"timeframe": "1h",
           "coinSelection": {"mode": "explicit", "tickers": tickers},
           "sections": [{"kind": "custom", "sectionKey": "custom:" + str(uuid.uuid4()),
                         "title": "TPO-native column space", "benchmarkTicker": None,
                         "notes": "read-only measurement probe", "columns": cols}],
           "conditions": []}
    return call("preview_strategy_report", req)

rows, legend = [], None
for i in range(0, len(crypto), BATCH):
    chunk = crypto[i:i + BATCH]
    pv, err = one(chunk)
    if pv is None:
        print("BATCH %s REFUSED:\n%s" % (",".join(chunk), err))
        sys.exit(1)
    txt = pv["renderedSections"][0]["section"]["text"]
    if legend is None:
        legend = txt.split("|")[0].strip()
    tbl = [r for r in txt.splitlines() if r.startswith("|")]
    rows.extend(tbl if not rows else tbl[2:])
    print("  batch ok: " + ",".join(chunk))

print()
print(legend)
print()
print("\n".join(rows))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tpo_native.txt")
open(out, "w", encoding="utf-8").write(legend + "\n\n" + "\n".join(rows))
print()
print("saved:", out)
