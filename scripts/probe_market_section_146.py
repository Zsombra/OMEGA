"""Contract 146 probe: which section SUBJECT reads each of the 24 metric keys 146.0.0 added, and what the market
section mints. Read-only: every call is `preview_strategy_report`, which renders "without saving or mutating strategy
state"; no draft is staged, nothing is committed.

Since 146.0.0 a custom section carries `marketScope`: null is an evaluated-coin section (the shape every section OMEGA
has ever built); a named scope (all, crypto, l1, memes, defi, tradfi, stocks, indices, commodities) makes a MARKET
section whose subject is the field at that scope, not the coin being evaluated. The platform refuses a column whose
metric the section's subject does not read (`REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED`) and, in the refusal, serves the
whole domain the subject does read (`details.allowedDomain.candidates`). That served list is the membership
measurement: one refusal per subject names every metric that subject reads.

What is probed (one preview per column unless stated; BTC, 1h anchor, detail "detailed"):
  A. the two subject domains, read off the refusals (a market metric on a coin section; a coin metric on a market one);
  B. each of the 24 keys x `value`, on a coin section and on a market section (crypto): accepted or the refusal text;
  C. the market section at each of the nine scopes: the header, the section title and the identity the row carries;
  D. applicability on the market family and the other three groups: rank / relativeTo / distance / scope / offset where
     the hint does not serve them (refusal text), the served transforms (headers), a pinned and a relative timeframe;
  E. mixed reports: a coin section beside a market section, and two market sections at two scopes (does the same
     header mint twice, and what does the platform say about it).

Headers minted go to data/contract/columns/_probe_146_<DATE>.json (HEADERS ONLY: render_coverage treats every string
in that file as a seen header); the run record, every refusal verbatim, to data/audit/market_section_probe_146_<DATE>.json.

Usage: PROBE_DATE=2026-11-02 python scripts/probe_market_section_146.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, ".")

PROBE_DATE = os.environ.get("PROBE_DATE", "2026-11-02")
HEADERS_OUT = f"data/contract/columns/_probe_146_{PROBE_DATE}.json"
RECORD_OUT = f"data/audit/market_section_probe_146_{PROBE_DATE}.json"
NOTE = f"OMEGA read-only market-section probe {PROBE_DATE}"
SCOPES = ["all", "crypto", "l1", "memes", "defi", "tradfi", "stocks", "indices", "commodities"]
MARKET = ["MKT_UP", "MKT_DOWN", "MKT_NET", "MKT_AVG_CHG", "MKT_DISPERSION", "MKT_PPO_UP", "MKT_PPO_DOWN",
          "MKT_PPO_NET", "MKT_AVG_PPO", "MKT_VOL_NET", "MKT_STRETCH", "MKT_ABOVE_EMA", "MKT_UNIVERSE"]
CROWD_Z = ["CROWD_UP_LEAN_Z", "CROWD_UP_EXCESS_Z", "CROWD_CAPT_EXCESS_Z", "CROWD_ACC_EDGE_Z",
           "CROWD_UP_LEAN_Z_LIVE", "CROWD_UP_EXCESS_Z_LIVE", "CROWD_CAPT_EXCESS_Z_LIVE", "CROWD_ACC_EDGE_Z_LIVE"]
OTHER = ["PAR_DEV", "REGIME_WARNING_CRASH", "REGIME_WARNING_DIVERGENCE"]
ADDED = MARKET + CROWD_Z + OTHER

# The server allows 3 requests/second sustained (data/audit/rate_limit_2026-09-09.json); space the calls wider.
_MIN_INTERVAL = 0.45
_last = [0.0]


def call(tool, args, timeout=240, attempts=4):
    err = None
    for attempt in range(1, attempts + 1):
        wait = _last[0] + _MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
        p = subprocess.Popen(
            ["cmd", "/c", "npx", "mcporter", "call", f"battlegrid-anbu.{tool}",
             "--output", "json", "--args", "-"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out, serr = p.communicate(json.dumps(args).encode(), timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            err = "TIMEOUT"
            continue
        txt = out.decode(errors="replace")
        if not txt.strip():
            err = (serr.decode(errors="replace") or "empty stdout")[:400]
            if "Rate limited" in err:
                time.sleep(1.5 * attempt)
                continue
            return None, err
        try:
            return json.loads(txt), None
        except json.JSONDecodeError:
            return None, txt[:400]
    return None, err


def V(metric, **kw):
    col = {"metric": metric, "transformId": kw.pop("transformId", "value"), "timeframe": kw.pop("timeframe", {"rel": "anchor"})}
    col.update(kw)
    return col


def section(columns, scope, title):
    return {"kind": "custom", "title": title, "benchmarkTicker": None, "marketScope": scope, "notes": NOTE,
            "columns": columns}


def preview(sections, tickers=("BTC",), timeframe="1h"):
    req = {"coinSelection": {"mode": "explicit", "tickers": list(tickers)}, "detail": "detailed",
           "source": {"kind": "FIELDS", "timeframe": timeframe, "sections": sections}}
    d, err = call("preview_strategy_report", req)
    if d is None:
        return req, None, {"transport": err}
    if "code" in d and "message" in d and "authoring" not in d:
        # a VALIDATION_ERROR envelope: {code, message, details{authoringCode, path, receivedValue, allowedDomain, context}}
        return req, None, d
    if "budgetUsage" not in d or not isinstance(d.get("authoring"), dict):
        return req, None, {"unexpected": json.dumps(d)[:600]}
    return req, d, None


def digest(d):
    """The parts of an accepted render worth keeping: per section, its title, provenance, the identity its rows carry,
    the rendered column units, and the authoring outputs (header, meaning, operators, vocabulary, hold, family)."""
    out = {"sections": [], "outputs": [], "duplicateHeaders": d.get("duplicateHeaders"),
           "missingConditionColumns": d.get("missingConditionColumns")}
    for rs in d.get("renderedSections", []):
        s = rs.get("section") or {}
        rows = s.get("rows") or []
        out["sections"].append({
            "sectionKey": rs.get("sectionKey"), "shape": rs.get("shape"), "title": s.get("title"),
            "provenance": s.get("provenance"), "anchorTf": s.get("anchorTf"),
            "columns": [{k: c.get(k) for k in ("key", "group", "role", "timeframe", "window", "bars", "unit", "precision")}
                        for c in (s.get("columns") or [])],
            "firstRow": rows[0] if rows else None, "rowCount": len(rows)})
    for cc in d["authoring"].get("conditionColumns", []):
        for o in cc.get("outputs", []):
            out["outputs"].append({"section": cc.get("title"), **{k: o.get(k) for k in (
                "header", "meaning", "conditionOperators", "conditionVocabulary", "markerToken", "conditionHold",
                "developingRead", "family", "readBy")}})
    return out


def refusal(e):
    if e is None:
        return None
    det = e.get("details") or {}
    dom = det.get("allowedDomain") or {}
    return {"code": e.get("code"), "message": e.get("message"), "authoringCode": det.get("authoringCode"),
            "path": det.get("path"), "receivedValue": det.get("receivedValue"),
            "allowedDomainKind": dom.get("kind"), "allowedDomainRule": dom.get("rule"),
            "candidateCount": len(dom.get("candidates") or []) if isinstance(dom.get("candidates"), list) else None,
            "context": det.get("context"), **({"transport": e["transport"]} if "transport" in e else {}),
            **({"unexpected": e["unexpected"]} if "unexpected" in e else {})}


def main() -> int:
    record = {"_what": __doc__.strip().splitlines()[0], "capturedAt": None, "probes": []}
    headers = set()
    t0 = time.time()

    def probe(name, sections, tickers=("BTC",), timeframe="1h", keep_candidates=False):
        req, d, e = preview(sections, tickers, timeframe)
        entry = {"probe": name, "sections": [{"marketScope": s["marketScope"], "columns": s["columns"]} for s in sections],
                 "tickers": list(tickers), "timeframe": timeframe,
                 "accepted": d is not None, "render": digest(d) if d else None, "refusal": refusal(e)}
        if keep_candidates and e is not None:
            entry["candidates"] = ((e.get("details") or {}).get("allowedDomain") or {}).get("candidates")
        if d:
            headers.update(o["header"] for o in entry["render"]["outputs"])
        record["probes"].append(entry)
        tag = "OK " + ",".join(o["header"] for o in entry["render"]["outputs"]) if d else \
            "REFUSED " + str((entry["refusal"] or {}).get("message", entry["refusal"]))[:110]
        print(f"  [{len(record['probes'])}] {name}: {tag} ({round(time.time() - t0)}s)")
        return entry

    print("A. the subject domains")
    probe("A.coinSection.domain", [section([V("MKT_UP")], None, "coin subject")], keep_candidates=True)
    probe("A.marketSection.domain", [section([V("CLOSE")], "crypto", "market subject")], keep_candidates=True)

    print("B. each added key x value, on a coin section and on a market section (crypto)")
    for m in ADDED:
        probe(f"B.{m}.coin", [section([V(m)], None, f"coin {m}")])
        probe(f"B.{m}.market", [section([V(m)], "crypto", f"market {m}")])

    print("C. MKT_UP at each of the nine scopes")
    for sc in SCOPES:
        probe(f"C.MKT_UP.{sc}", [section([V("MKT_UP")], sc, f"scope {sc}")])

    print("D. applicability")
    D = [
        ("D.MKT_UP.rank", [V("MKT_UP", transformId="rank", ordering="hi")], "crypto"),
        ("D.MKT_UP.relativeTo", [V("MKT_UP", transformId="relativeTo", instrument="ETH")], "crypto"),
        ("D.MKT_UP.distance", [V("MKT_UP", transformId="distance")], "crypto"),
        ("D.MKT_UP.value.scopeKnob", [V("MKT_UP", scope="crypto")], "crypto"),
        ("D.MKT_UP.value.offset1", [V("MKT_UP", offset=1)], "crypto"),
        ("D.MKT_UP.value.abs4h", [V("MKT_UP", timeframe={"abs": "4h"})], "crypto"),
        ("D.MKT_UP.value.higher", [V("MKT_UP", timeframe={"rel": "higher"})], "crypto"),
        ("D.MKT_UP.value.lower", [V("MKT_UP", timeframe={"rel": "lower"})], "crypto"),
        ("D.MKT_UP.trajectory", [V("MKT_UP", transformId="trajectory", window=4)], "crypto"),
        ("D.MKT_UP.zscore", [V("MKT_UP", transformId="zscore", window=20)], "crypto"),
        ("D.MKT_UP.spread.MKT_DOWN", [V("MKT_UP", transformId="spread", inputs=[{"metric": "MKT_DOWN"}])], "crypto"),
        ("D.MKT_UP.spread.CROWD_ACC", [V("MKT_UP", transformId="spread", inputs=[{"metric": "CROWD_ACC"}])], "crypto"),
        ("D.MKT_UP.spread.chain.trajectory", [V("MKT_UP", transformId="spread", chainedTransformId="trajectory",
                                               inputs=[{"metric": "MKT_DOWN"}], window=4)], "crypto"),
        ("D.MKT_UP.maxShare", [V("MKT_UP", transformId="maxShare", window=4)], "crypto"),
        ("D.MKT_ABOVE_EMA.classifyZone", [V("MKT_ABOVE_EMA", transformId="classifyZone")], "crypto"),
        ("D.MKT_UNIVERSE.value", [V("MKT_UNIVERSE")], "crypto"),
        ("D.MKT_VOL_NET.efficiency", [V("MKT_VOL_NET", transformId="efficiency", window=4)], "crypto"),
        ("D.CROWD_UP_LEAN_Z.rank.hi", [V("CROWD_UP_LEAN_Z", transformId="rank", ordering="hi")], None),
        ("D.CROWD_UP_LEAN_Z.rank.scope", [V("CROWD_UP_LEAN_Z", transformId="rank", ordering="hi", scope="crypto")], None),
        ("D.CROWD_UP_LEAN_Z.value.offset1", [V("CROWD_UP_LEAN_Z", offset=1)], None),
        ("D.CROWD_UP_LEAN_Z.trajectory", [V("CROWD_UP_LEAN_Z", transformId="trajectory", window=4)], None),
        ("D.CROWD_UP_LEAN_Z_LIVE.rank.lo", [V("CROWD_UP_LEAN_Z_LIVE", transformId="rank", ordering="lo")], None),
        ("D.CROWD_ACC_EDGE_Z.value.abs4h", [V("CROWD_ACC_EDGE_Z", timeframe={"abs": "4h"})], None),
        ("D.PAR_DEV.relativeTo.ETH", [V("PAR_DEV", transformId="relativeTo", instrument="ETH")], None),
        ("D.PAR_DEV.relativeTo.default", [V("PAR_DEV", transformId="relativeTo")], None),
        ("D.PAR_DEV.classifyZone", [V("PAR_DEV", transformId="classifyZone")], None),
        ("D.PAR_DEV.value.lower", [V("PAR_DEV", timeframe={"rel": "lower"})], None),
        ("D.PAR_DEV.rank", [V("PAR_DEV", transformId="rank", ordering="hi")], None),
        ("D.PAR_DEV.distance", [V("PAR_DEV", transformId="distance")], None),
        ("D.PAR_DEV.spread.ATR_PCT", [V("PAR_DEV", transformId="spread", inputs=[{"metric": "ATR_PCT"}])], None),
        ("D.REGIME_WARNING_CRASH.value", [V("REGIME_WARNING_CRASH")], None),
        ("D.REGIME_WARNING_CRASH.trajectory", [V("REGIME_WARNING_CRASH", transformId="trajectory", window=4)], None),
        ("D.REGIME_WARNING_DIVERGENCE.value.offset1", [V("REGIME_WARNING_DIVERGENCE", offset=1)], None),
        ("D.REGIME_WARNING_DIVERGENCE.classifyZone", [V("REGIME_WARNING_DIVERGENCE", transformId="classifyZone")], None),
    ]
    for name, cols, sc in D:
        probe(name, [section(cols, sc, name)])

    print("E. mixed reports")
    probe("E.coin+market", [section([V("CLOSE")], None, "coin"), section([V("MKT_UP")], "crypto", "market")])
    probe("E.market.crypto+tradfi", [section([V("MKT_UP")], "crypto", "crypto"), section([V("MKT_UP")], "tradfi", "tradfi")])
    probe("E.market.crypto.twoCoins", [section([V("MKT_UP"), V("MKT_NET")], "crypto", "market two coins")],
          tickers=("BTC", "SOL"))
    probe("E.market.all.4h", [section([V("MKT_ABOVE_EMA"), V("MKT_UNIVERSE")], "all", "market 4h")], timeframe="4h")

    record["capturedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record["contractVersion"] = os.environ.get("PROBE_CONTRACT", "146.0.1")
    record["how"] = ("preview_strategy_report via the mcporter CLI, read-only, detail detailed, BTC at a 1h anchor unless "
                     "the probe says otherwise; one custom section per probe (two in E), its marketScope as recorded")
    record["counts"] = {"probes": len(record["probes"]), "accepted": sum(p["accepted"] for p in record["probes"]),
                        "refused": sum(not p["accepted"] for p in record["probes"]), "headersMinted": len(headers)}
    os.makedirs(os.path.dirname(RECORD_OUT), exist_ok=True)
    with open(RECORD_OUT, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(HEADERS_OUT, "w", encoding="utf-8") as f:
        json.dump({"_what": (f"Headers minted live by preview_strategy_report in the {PROBE_DATE} market-section probe at "
                             f"contract 146 ({RECORD_OUT}). HEADERS ONLY - render_coverage treats every string in this "
                             "file as a seen header, so nothing else may be added here."),
                   "headers": sorted(headers)}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\n{record['counts']}\nwrote {RECORD_OUT} and {HEADERS_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
