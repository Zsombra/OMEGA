"""Contract 148.1.0 probe: the 146.1 - 146.14 authoring widening, rendered. Read-only: every call is
`preview_strategy_report`, which renders "without saving or mutating strategy state"; no draft is staged, nothing is
committed.

What 146.1 - 146.14 added to the custom-section column (README "Contract history - v146.1 to v146.12", v146.13,
v146.14): the `ema` transform (header `_ema{n}`, window unit smoothingLength), `distance` as a chain outer of an
offset rolling extreme (`high_o1_max55`, `chainedOuters[outer].offsetMinimum`), six author-set knobs (`leftBars` /
`rightBars` on the swing metrics, `_l<L>r<R>` off 2/2; `swingLength`, `confluenceFilter`, `equalBars`, `equalThreshold`
on the market-structure metrics, `_s<n>`, `_cf`, `_e<m>`, `_atr<t>` off their defaults), 206 metric keys (the six
Pivot Points Standard types on five periods, LuxAlgo market structure, EQH / EQL), the 1,000-bar history and
`REPORT_COLUMN_DEPTH_EXCEEDED`. Every served metric now carries `subjectKinds` - four subjects; group G renders the
`reference` (a stablecoin-pair section) and `benchmark` subjects no earlier probe set.

Groups (BTC, 1h anchor, detail "detailed"; one column per preview where a refusal is expected, batched columns where
acceptance is expected - a refused batch is re-probed column by column):
  A `ema`; B the `distance` chain outer / rolling offset; C swing pairs; D market structure; E EQH / EQL;
  F pivots (timeframe-inert bundles); G section subjects; H the 1,000-bar history; I knob + offset / timeframe combos.

The transforms each new key serves are read from the raw hints of the same day (PROBE_HINTS, the
refresh_metric_contracts scratch dir hints_<STAMP>/), never assumed.

Headers minted go to data/contract/columns/_probe_148_<DATE>.json (HEADERS ONLY: render_coverage treats every string
in that file as a seen header); the run record, every refusal verbatim, to data/audit/authoring_probe_148_<DATE>.json.

Usage: PROBE_DATE=2026-11-05 PROBE_HINTS=<scratch>/hints_20261105 python scripts/probe_authoring_148.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, ".")

PROBE_DATE = os.environ.get("PROBE_DATE", "2026-11-05")
HINTS = os.environ.get("PROBE_HINTS")       # required by main(); read lazily so the module imports for tests
CONTRACT = os.environ.get("PROBE_CONTRACT", "148.1.0")
HEADERS_OUT = f"data/contract/columns/_probe_148_{PROBE_DATE}.json"
RECORD_OUT = f"data/audit/authoring_probe_148_{PROBE_DATE}.json"
NOTE = f"OMEGA read-only authoring probe {PROBE_DATE}"

SWING = ["SWING_FRACTAL_HIGH", "SWING_FRACTAL_LOW", "PRIOR_SWING_FRACTAL_HIGH", "PRIOR_SWING_FRACTAL_LOW",
         "SWING_FRACTAL_HIGH_BARS_AGO", "SWING_FRACTAL_LOW_BARS_AGO", "SWING_FRACTAL_LABEL"]
STRUCTURE = ["INTERNAL_STRUCTURE_EVENT", "INTERNAL_STRUCTURE_TREND", "INTERNAL_STRUCTURE_LEVEL",
             "SWING_STRUCTURE_EVENT", "SWING_STRUCTURE_TREND", "SWING_STRUCTURE_LEVEL"]
PERIODS = {"day": "PIVOT_", "week": "PIVOT_WEEK_", "month": "PIVOT_MONTH_", "quarter": "PIVOT_QUARTER_",
           "year": "PIVOT_YEAR_"}
# one key per type: Traditional (P on the four new periods, R4 on the day - its P is the 144-era PIVOT_P), Fibonacci,
# Classic, Camarilla, Woodie, DM
TYPE_SUFFIX = ["P", "R4", "FIB_R1", "CLASSIC_R3", "CAM_R1", "WOODIE_P", "DM_P"]

# The server allows 3 requests/second sustained (data/audit/rate_limit_2026-09-09.json); space the calls wider.
_MIN_INTERVAL = 0.45
_last = [0.0]
# Re-read GET /mcp/version every this many previews: a contract that moves mid-run stops the run (three drifts landed
# on 2026-11-04), not only a check at the start and the end.
VERSION_EVERY = 25
# mcporter's stderr when the stored OAuth credential has no usable token: every call then starts an interactive
# authorization (a new dynamic client, possibly a browser tab) and takes minutes. Seen 2026-11-05 from ~10:18Z.
AUTH_MARKERS = ("/authorize", "If the browser did not open", "OAuth", "Unauthorized", "401")


class TransportFailure(RuntimeError):
    """Nothing the platform rendered or refused: the call never produced a platform answer (OAuth / credential lost,
    timeout, empty or non-JSON stdout, an unrecognised body). The run stops - such a probe is never recorded, least of
    all as a refusal."""


class ContractMoved(RuntimeError):
    """The served contract left the one this run probes."""


def version():
    with urllib.request.urlopen("https://mcp.battlegrid.trade/mcp/version", timeout=30) as r:
        return json.loads(r.read().decode())


def call(tool, args, timeout=240, attempts=4):
    """The platform's JSON answer (a render or a refusal). Raises TransportFailure on anything else: an OAuth prompt
    at once (never retried - each retry would start another authorization), a timeout or a rate limit after
    `attempts`, empty or non-JSON stdout."""
    assert tool == "preview_strategy_report", tool
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
        txt = out.decode("utf-8", errors="replace")
        if not txt.strip():
            err = (serr.decode(errors="replace") or "empty stdout")[:400]
            if any(marker in err for marker in AUTH_MARKERS):
                raise TransportFailure(f"mcporter has no usable credential for battlegrid-anbu (re-authorizing is the "
                                       f"user's step): {err}")
            if "Rate limited" in err or "429" in err:
                time.sleep(2.0 * attempt)
                continue
            raise TransportFailure(err)
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            raise TransportFailure(f"stdout is not JSON: {txt[:400]}") from None
    raise TransportFailure(f"no answer after {attempts} attempts: {err}")


def hint(metric):
    path = os.path.join(HINTS, f"{metric}.json")
    return json.load(open(path, encoding="utf-8"))["metric"]


def served_transforms(metric):
    return [t["id"] for t in hint(metric)["transforms"]]


def C(metric, transformId="value", timeframe=None, **kw):
    col = {"metric": metric, "transformId": transformId, "timeframe": timeframe or {"rel": "anchor"}}
    col.update(kw)
    return col


def section(columns, title, benchmark=None, scope=None):
    return {"kind": "custom", "title": title, "benchmarkTicker": benchmark, "marketScope": scope, "notes": NOTE,
            "columns": columns}


def preview(sections, tickers=("BTC",), timeframe="1h"):
    req = {"coinSelection": {"mode": "explicit", "tickers": list(tickers)}, "detail": "detailed",
           "source": {"kind": "FIELDS", "timeframe": timeframe, "sections": sections}}
    d = call("preview_strategy_report", req)
    if "code" in d and "message" in d and "authoring" not in d:
        return req, None, d
    if "budgetUsage" not in d or not isinstance(d.get("authoring"), dict):
        raise TransportFailure(f"neither a render nor a refusal: {json.dumps(d)[:600]}")
    return req, d, None


def digest(d):
    out = {"sections": [], "outputs": [], "duplicateHeaders": d.get("duplicateHeaders"),
           "missingConditionColumns": d.get("missingConditionColumns")}
    for rs in d.get("renderedSections", []):
        s = rs.get("section") or {}
        rows = s.get("rows") or []
        out["sections"].append({
            "sectionKey": rs.get("sectionKey"), "shape": rs.get("shape"), "title": s.get("title"),
            "provenance": s.get("provenance"), "anchorTf": s.get("anchorTf"),
            "columns": [{k: c.get(k) for k in ("key", "group", "role", "chainedRole", "timeframe", "window", "bars",
                                               "unit", "precision", "lookback", "spanFragments")}
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
            "allowedDomain": {k: v for k, v in dom.items() if k != "candidates"} or None,
            "candidateCount": len(dom.get("candidates") or []) if isinstance(dom.get("candidates"), list) else None,
            "context": det.get("context")}


def main() -> int:
    if not HINTS:
        sys.exit("set PROBE_HINTS (the dir holding <METRIC>.json raw hints)")
    v0 = version()
    if v0.get("contractVersion") != CONTRACT:
        sys.exit(f"served contract {v0.get('contractVersion')} is not {CONTRACT}: stop")
    record = {"_what": __doc__.strip().splitlines()[0], "contractVersion": CONTRACT, "buildSha": v0.get("buildSha"),
              "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "capturedAt": None, "probes": []}
    headers = set()
    t0 = time.time()

    def probe(name, sections, tickers=("BTC",), timeframe="1h", keep_candidates=False):
        if record["probes"] and len(record["probes"]) % VERSION_EVERY == 0:
            now = version()
            if now.get("contractVersion") != CONTRACT:
                raise ContractMoved(f"served contract {now.get('contractVersion')} after {len(record['probes'])} "
                                    f"probes, not {CONTRACT}: {now}")
        req, d, e = preview(sections, tickers, timeframe)
        entry = {"probe": name,
                 "sections": [{k: s[k] for k in ("benchmarkTicker", "marketScope", "columns")} for s in sections],
                 "tickers": list(tickers), "timeframe": timeframe,
                 "accepted": d is not None, "render": digest(d) if d else None, "refusal": refusal(e)}
        if keep_candidates and e is not None:
            entry["candidates"] = ((e.get("details") or {}).get("allowedDomain") or {}).get("candidates")
        if d:
            headers.update(o["header"] for o in entry["render"]["outputs"])
        record["probes"].append(entry)
        tag = "OK " + ",".join(o["header"] for o in entry["render"]["outputs"]) if d else \
            "REFUSED " + str((entry["refusal"] or {}).get("message", entry["refusal"]))[:140]
        print(f"  [{len(record['probes'])}] {name}: {tag} ({round(time.time() - t0)}s)", flush=True)
        return entry

    def batch(name, columns, benchmark=None, scope=None):
        """Columns expected to be accepted, in one preview; a refusal re-probes each column alone."""
        e = probe(name, [section(columns, name, benchmark, scope)])
        if not e["accepted"] and len(columns) > 1:
            for i, col in enumerate(columns):
                probe(f"{name}#{i}", [section([col], f"{name}#{i}", benchmark, scope)])
        return e

    def one(name, col, benchmark=None, scope=None, keep_candidates=False):
        return probe(name, [section([col], name, benchmark, scope)], keep_candidates=keep_candidates)

    def groups():
        print("A. ema")
        batch("A.accept", [C("RSI14", "ema", window=14), C("CLOSE", "ema", window=14), C("QUOTE_VOL", "ema", window=14),
                           C("RSI14", "ema", window=1), C("RSI14", "ema"), C("RSI14", "ema", window=269),
                           C("CLOSE", "ema", window=14, bars="closed")])
        one("A.RSI14.ema.w270", C("RSI14", "ema", window=270))
        one("A.CLOSE.ema.w270", C("CLOSE", "ema", window=270))
        one("A.RSI14.ema.offset1", C("RSI14", "ema", window=14, offset=1))
        one("A.RSI14.zscore.chain.ema", C("RSI14", "zscore", window=20, chainedTransformId="ema"))
        one("A.CLOSE.ema.chain.trajectory", C("CLOSE", "ema", window=14, chainedTransformId="trajectory"))
        one("A.RSI14.spread.RSI7.chain.ema", C("RSI14", "spread", inputs=[{"metric": "RSI7"}], chainedTransformId="ema",
                                               window=10))
        one("A.HIGH.distance.chain.ema", C("HIGH", "distance", chainedTransformId="ema", window=10))
        one("A.CLOSE.relativeTo.chain.ema", C("CLOSE", "relativeTo", chainedTransformId="ema", window=10))
        one("A.HIGH.distance.chain.ema.w270", C("HIGH", "distance", chainedTransformId="ema", window=270))
        one("A.PIVOT_WEEK_P.ema", C("PIVOT_WEEK_P", "ema", window=14))

        print("B. distance as a chain outer / the rolling offset")
        one("B.HIGH.rollingMax.w55.o1.chain.distance", C("HIGH", "rollingMax", window=55, offset=1,
                                                         chainedTransformId="distance"))
        one("B.LOW.rollingMin.w55.o1.chain.distance", C("LOW", "rollingMin", window=55, offset=1,
                                                        chainedTransformId="distance"))
        batch("B.accept.unchained", [C("HIGH", "rollingMax", window=55, offset=1), C("HIGH", "rollingMax", window=20, offset=44),
                                     C("HIGH", "rollingMax", window=55, offset=9), C("CLOSE", "rollingMin", window=20, offset=2),
                                     C("HIGH", "rollingMax", window=20, offset=0)])
        one("B.HIGH.rollingMax.w55.o0.chain.distance", C("HIGH", "rollingMax", window=55, offset=0,
                                                         chainedTransformId="distance"))
        one("B.HIGH.rollingMax.w55.nooffset.chain.distance", C("HIGH", "rollingMax", window=55,
                                                               chainedTransformId="distance"))
        one("B.HIGH.rollingMax.w20.o45", C("HIGH", "rollingMax", window=20, offset=45))
        one("B.HIGH.rollingMax.w55.o10", C("HIGH", "rollingMax", window=55, offset=10))
        one("B.HIGH.rollingMax.o1.chain.trajectory", C("HIGH", "rollingMax", window=20, offset=1,
                                                       chainedTransformId="trajectory"))
        one("B.RSI14.rollingMax.o1.chain.distance", C("RSI14", "rollingMax", window=20, offset=1,
                                                      chainedTransformId="distance"))
        one("B.CLOSE.rollingMin.w20.o2.chain.distance", C("CLOSE", "rollingMin", window=20, offset=2,
                                                          chainedTransformId="distance"))

        print("C. swing pairs")
        batch("C.default", [C(m) for m in SWING])
        batch("C.l3r5", [C(m, leftBars=3, rightBars=5) for m in SWING])
        batch("C.explicit2-2.and.single", [C("SWING_FRACTAL_HIGH", leftBars=2, rightBars=2),
                                           C("SWING_FRACTAL_LOW", leftBars=4), C("SWING_FRACTAL_LABEL", rightBars=3)])
        sfh = hint("SWING_FRACTAL_HIGH")["parameters"]
        lmax, rmax = sfh["leftBars"]["maximum"], sfh["rightBars"]["maximum"]
        one("C.SWING_FRACTAL_HIGH.left.max", C("SWING_FRACTAL_HIGH", leftBars=lmax))
        one("C.SWING_FRACTAL_HIGH.left.over", C("SWING_FRACTAL_HIGH", leftBars=lmax + 1))
        one("C.SWING_FRACTAL_HIGH.right.max", C("SWING_FRACTAL_HIGH", rightBars=rmax))
        one("C.SWING_FRACTAL_HIGH.right.over", C("SWING_FRACTAL_HIGH", rightBars=rmax + 1))
        one("C.SWING_FRACTAL_HIGH.both.max", C("SWING_FRACTAL_HIGH", leftBars=lmax, rightBars=rmax))
        one("C.SWING_FRACTAL_HIGH.left0", C("SWING_FRACTAL_HIGH", leftBars=0))
        one("C.RSI14.leftBars", C("RSI14", leftBars=3))
        one("C.EQH.leftBars", C("EQH", leftBars=3))
        one("C.SWING_FRACTAL_HIGH.swingLength", C("SWING_FRACTAL_HIGH", swingLength=50))
        one("C.SWING_FRACTAL_HIGH.relativeTo.l3r5", C("SWING_FRACTAL_HIGH", "relativeTo", leftBars=3, rightBars=5))
        one("C.SWING_FRACTAL_HIGH.relativeTo.l2r2", C("SWING_FRACTAL_HIGH", "relativeTo", leftBars=2, rightBars=2))
        one("C.SWING_FRACTAL_HIGH.aggregate.l3r5", C("SWING_FRACTAL_HIGH", "aggregate", window=10, leftBars=3, rightBars=5))
        one("C.SWING_FRACTAL_HIGH.ema.l3r5", C("SWING_FRACTAL_HIGH", "ema", window=10, leftBars=3, rightBars=5))
        one("C.SWING_FRACTAL_HIGH.distance.chain.rank.l3r5", C("SWING_FRACTAL_HIGH", "distance", chainedTransformId="rank",
                                                               ordering="near", leftBars=3, rightBars=5))
        one("C.SWING_FRACTAL_HIGH.distance.chain.aggregate.l3r5", C("SWING_FRACTAL_HIGH", "distance",
                                                                    chainedTransformId="aggregate", window=10,
                                                                    leftBars=3, rightBars=5))
        batch("C.accept.transforms", [C("SWING_FRACTAL_HIGH", "trajectory", window=4, leftBars=3, rightBars=5),
                                      C("SWING_FRACTAL_HIGH", "distance", leftBars=3, rightBars=5),
                                      C("SWING_FRACTAL_HIGH", "distance", chainedTransformId="trajectory", window=4,
                                        leftBars=3, rightBars=5),
                                      C("SWING_FRACTAL_LOW", "levelInteraction", leftBars=3, rightBars=5),
                                      C("SWING_FRACTAL_HIGH", "relativeTo"), C("SWING_FRACTAL_HIGH", "aggregate", window=10),
                                      C("SWING_FRACTAL_HIGH", "ema", window=10),
                                      C("SWING_FRACTAL_HIGH", "distance", chainedTransformId="rank", ordering="near")])
        one("C.SWING_FRACTAL_HIGH.spread.l3r5.operand", C("SWING_FRACTAL_HIGH", "spread", inputs=[{"metric": "CLOSE"}],
                                                          leftBars=3, rightBars=5))

        print("D. market structure")
        for m in STRUCTURE:
            cols = []
            for tid in served_transforms(m):
                kw = {}
                if tid == "spread":
                    ops = hint(m).get("spreadOperands") or []
                    if not ops:
                        continue
                    kw["inputs"] = [{"metric": "CLOSE" if "CLOSE" in ops else ops[0]}]
                cols.append(C(m, tid, **kw))
            batch(f"D.{m}.served", cols)
            for tid in ("rank", "relativeTo", "aggregate", "ema"):
                if tid not in served_transforms(m):
                    one(f"D.{m}.{tid}", C(m, tid, **({"window": 10} if tid in ("aggregate", "ema") else {})))
        for n in (9, 10, 50, 100, 101):
            one(f"D.SWING_STRUCTURE_LEVEL.s{n}", C("SWING_STRUCTURE_LEVEL", swingLength=n))
        batch("D.knobs.accept", [C("SWING_STRUCTURE_TREND", confluenceFilter=True),
                                 C("SWING_STRUCTURE_TREND", confluenceFilter=False),
                                 C("SWING_STRUCTURE_EVENT", swingLength=20, confluenceFilter=True),
                                 C("SWING_STRUCTURE_LEVEL", "distance", swingLength=20),
                                 C("SWING_STRUCTURE_LEVEL", "levelInteraction", swingLength=20, confluenceFilter=True)])
        for m in ("INTERNAL_STRUCTURE_LEVEL", "INTERNAL_STRUCTURE_TREND"):
            one(f"D.{m}.swingLength20", C(m, swingLength=20))
            one(f"D.{m}.confluenceFilter", C(m, confluenceFilter=True))
        one("D.SWING_STRUCTURE_LEVEL.equalBars", C("SWING_STRUCTURE_LEVEL", equalBars=5))
        one("D.SWING_STRUCTURE_LEVEL.s50.explicit", C("SWING_STRUCTURE_LEVEL", "trajectory", window=4, swingLength=50,
                                                      confluenceFilter=False))
        one("D.SWING_STRUCTURE_LEVEL.distance.chain.aggregate.s20", C("SWING_STRUCTURE_LEVEL", "distance",
                                                                      chainedTransformId="aggregate", window=10,
                                                                      swingLength=20))

        print("E. EQH / EQL")
        eqh = hint("EQH")["parameters"]
        emax = eqh["equalBars"]["maximum"]
        batch("E.accept", [C("EQH"), C("EQL"), C("EQH", equalBars=1), C("EQH", equalBars=3), C("EQH", equalThreshold=0),
                           C("EQH", equalThreshold=0.1), C("EQL", equalThreshold=0.5), C("EQL", equalBars=5, equalThreshold=0.2)])
        one("E.EQH.equalBars.max", C("EQH", equalBars=emax))
        one("E.EQH.equalBars.over", C("EQH", equalBars=emax + 1))
        one("E.EQH.equalThreshold.offstep", C("EQH", equalThreshold=0.25))
        one("E.EQH.equalThreshold.over", C("EQH", equalThreshold=0.6))
        one("E.EQH.swingLength", C("EQH", swingLength=20))
        for tid in served_transforms("EQH"):
            if tid != "value":
                one(f"E.EQH.{tid}", C("EQH", tid))
        for tid in ("trajectory", "rank", "aggregate", "ema"):
            if tid not in served_transforms("EQH"):
                one(f"E.EQH.{tid}.notServed", C("EQH", tid, **({"window": 10} if tid in ("aggregate", "ema", "trajectory") else {})))

        print("F. pivots")
        for period, prefix in PERIODS.items():
            cols = []
            for suf in TYPE_SUFFIX:
                key = prefix + suf
                try:
                    hint(key)
                except FileNotFoundError:
                    continue
                cols.append(C(key))
            batch(f"F.{period}.value", cols)
        for key in ("PIVOT_WEEK_P", "PIVOT_CAM_R1", "PIVOT_MONTH_FIB_R1", "PIVOT_QUARTER_WOODIE_P"):
            cols = []
            for tid in served_transforms(key):
                kw = {}
                if tid == "spread":
                    kw["inputs"] = [{"metric": "CLOSE"}]
                cols.append(C(key, tid, **kw))
            batch(f"F.{key}.served", cols)
        batch("F.spread.pivot.vs.pivot", [C("PIVOT_WEEK_P", "spread", inputs=[{"metric": "PIVOT_WEEK_R1"}]),
                                          C("PIVOT_CAM_R3", "spread", inputs=[{"metric": "PIVOT_CAM_S3"}]),
                                          C("CLOSE", "spread", inputs=[{"metric": "PIVOT_MONTH_DM_P"}])])
        one("F.PIVOT_WEEK_P.abs4h", C("PIVOT_WEEK_P", timeframe={"abs": "4h"}))
        one("F.PIVOT_WEEK_P.lower", C("PIVOT_WEEK_P", timeframe={"rel": "lower"}))
        one("F.PIVOT_WEEK_P.offset1", C("PIVOT_WEEK_P", offset=1))
        one("F.PIVOT_WEEK_P.trajectory", C("PIVOT_WEEK_P", "trajectory", window=4))
        one("F.PIVOT_WEEK_P.rank", C("PIVOT_WEEK_P", "rank"))

        print("G. section subjects")
        one("G.USDT_USD.RSI14", C("RSI14"), benchmark="USDT_USD", keep_candidates=True)
        batch("G.USDT_USD.pair", [C("PAR_DEV"), C("PAR_DEV", "classifyZone"), C("OPEN"), C("HIGH"), C("LOW"), C("CLOSE")],
              benchmark="USDT_USD")
        batch("G.USDC_USDT.pair", [C("PAR_DEV"), C("CLOSE")], benchmark="USDC_USDT")
        one("G.ETH.PAR_DEV", C("PAR_DEV"), benchmark="ETH", keep_candidates=True)
        batch("G.ETH.benchmark", [C("RSI14"), C("PIVOT_WEEK_P"), C("CLOSE"), C("SWING_STRUCTURE_TREND")], benchmark="ETH")
        one("G.ETH.MKT_UP", C("MKT_UP"), benchmark="ETH")
        one("G.USDT_USD.plus.marketScope", C("PAR_DEV"), benchmark="USDT_USD", scope="crypto")
        one("G.ETH.plus.marketScope", C("MKT_UP"), benchmark="ETH", scope="crypto")
        one("G.coin.PAR_DEV", C("PAR_DEV"), keep_candidates=True)
        one("G.market.PAR_DEV", C("PAR_DEV"), scope="crypto")
        batch("G.USDT_USD.PAR_DEV.served", [C("PAR_DEV", tid, **({"inputs": [{"metric": "CLOSE"}]} if tid == "spread" else {}))
                                            for tid in served_transforms("PAR_DEV") if tid not in ("value", "classifyZone")],
              benchmark="USDT_USD")

        print("H. the 1,000-bar history")
        batch("H.accept", [C("RSI14", "aggregate", window=64), C("RSI14", "aggregate", window=65),
                           C("RSI14", "aggregate", window=936), C("RSI14", "zscore", window=64), C("RSI14", "pctl", window=63),
                           C("RSI14", "efficiency", window=63), C("RSI14", offset=63), C("RSI14")])
        one("H.RSI14.aggregate.w937", C("RSI14", "aggregate", window=937))
        one("H.RSI14.zscore.w65", C("RSI14", "zscore", window=65))
        one("H.RSI14.pctl.w64", C("RSI14", "pctl", window=64))
        one("H.RSI14.efficiency.w64", C("RSI14", "efficiency", window=64))
        one("H.RSI14.value.offset64", C("RSI14", offset=64))

        print("I. combinations")
        batch("I.accept", [C("SWING_FRACTAL_HIGH", leftBars=3, rightBars=5, offset=1),
                           C("SWING_FRACTAL_HIGH", leftBars=3, rightBars=5, timeframe={"abs": "4h"}),
                           C("SWING_FRACTAL_HIGH", leftBars=3, rightBars=5, timeframe={"rel": "lower"}, offset=2),
                           C("SWING_STRUCTURE_LEVEL", swingLength=20, confluenceFilter=True, offset=1),
                           C("SWING_STRUCTURE_LEVEL", swingLength=20, confluenceFilter=True, timeframe={"abs": "4h"}),
                           C("EQH", equalBars=5, equalThreshold=0.2, offset=2),
                           C("EQL", equalBars=5, equalThreshold=0.2, timeframe={"rel": "lower"}),
                           C("RSI14", "ema", window=14, timeframe={"abs": "4h"}),
                           C("HIGH", "rollingMax", window=55, offset=1, timeframe={"rel": "lower"}),
                           C("HIGH", "rollingMax", window=55, offset=1, chainedTransformId="distance",
                             timeframe={"abs": "4h"})])

    aborted = None
    try:
        groups()
    except (TransportFailure, ContractMoved) as exc:
        aborted = {"reason": type(exc).__name__, "message": str(exc)[:600],
                   "afterProbes": len(record["probes"]),
                   "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        print(f"\nABORTED after {len(record['probes'])} probes: {aborted['message']}", flush=True)

    try:
        v1 = version()
    except Exception as exc:              # the record of what WAS rendered is still written
        v1 = {"error": str(exc)[:300]}
    record["capturedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record["versionAtEnd"] = v1
    # A run that stopped on a transport failure or a contract move is PARTIAL: every probe in it is a platform answer
    # (a render or a verbatim refusal), and the groups after `aborted.afterProbes` were never sent.
    record["complete"] = aborted is None
    record["aborted"] = aborted
    record["how"] = ("preview_strategy_report via the mcporter CLI, read-only, detail detailed, BTC at a 1h anchor; one "
                     "custom section per probe, its benchmarkTicker / marketScope as recorded; GET /mcp/version before "
                     "and after")
    record["counts"] = {"probes": len(record["probes"]), "accepted": sum(p["accepted"] for p in record["probes"]),
                        "refused": sum(not p["accepted"] for p in record["probes"]), "headersMinted": len(headers)}
    os.makedirs(os.path.dirname(RECORD_OUT), exist_ok=True)
    with open(RECORD_OUT, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(HEADERS_OUT, "w", encoding="utf-8") as f:
        json.dump({"_what": (f"Headers minted live by preview_strategy_report in the {PROBE_DATE} authoring probe at "
                             f"contract {CONTRACT} ({RECORD_OUT}). HEADERS ONLY - render_coverage treats every string in "
                             "this file as a seen header, so nothing else may be added here."),
                   "headers": sorted(headers)}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\n{record['counts']}\nwrote {RECORD_OUT} and {HEADERS_OUT}")
    if aborted is not None:
        print(f"PARTIAL: aborted ({aborted['reason']}) after {aborted['afterProbes']} probes")
        return 3
    if v1.get("contractVersion") != CONTRACT:
        print(f"WARNING: the served contract moved during the run: {v1}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
