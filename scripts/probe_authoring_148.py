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

Contract 149.0.0 / 149.1.0 (undocumented in the README; read from the schemas and the 532 hints of 2026-11-06) added
to the same column the smoothers `rma`, `wma`, `rsi` and `cci` (transformId and chainedTransformId) and thirteen
optional knobs - atrPeriod, dSmoothing, fast, kSmoothing, period, rsiPeriod, signal, slow (bar counts), multiplier,
stdDev and PSAR's accelerationStart / Increment / Maximum - each served per metric in the hint's `parameters`. Group J
renders them. The run probes the served contract (PROBE_CONTRACT, default 149.1.0); the groups A - I written for
148.1.0 hold unchanged there (149 moved no metric, section or tool).

Groups (BTC, 1h anchor, detail "detailed"; one column per preview where a refusal is expected, batched columns where
acceptance is expected - a refused batch is re-probed column by column):
  A `ema`; B the `distance` chain outer / rolling offset; C swing pairs; D market structure; E EQH / EQL;
  F pivots (timeframe-inert bundles); G section subjects; H the 1,000-bar history; I knob + offset / timeframe combos;
  J the 149 smoothers and knobs.

The transforms each new key serves, and every knob's bounds, are read from the raw hints of the same contract
(PROBE_HINTS, the refresh_metric_contracts scratch dir hints_<STAMP>/), never assumed.

Headers minted go to data/contract/columns/_probe_<MAJOR>_<DATE>.json (HEADERS ONLY: render_coverage treats every
string in that file as a seen header); the run record, every refusal verbatim, to
data/audit/authoring_probe_<MAJOR>_<DATE>.json (MAJOR = the probed contract's major, 149). The run refuses either
output that already exists (PROBE_OVERWRITE=1 replaces them on purpose).

2026-11-08 (review pass 2, findings 4-7), the rules shared with probe_knob_spelling_149 and sweep_render_coverage:
- A refusal is a JSON body whose `code` is VALIDATION_ERROR. SERVICE_UNAVAILABLE (the preview's deadline) is recorded as
  a transient probe and the run goes on. A rate limit (RATE_LIMITED, "Rate limited" / 429 on stderr) backs off and is
  re-sent. Anything else - another platform code, an mcporter `isError` body, empty stdout, a timeout - is re-sent once
  after RETRY_PAUSE and then stops the run (TransportFailure), the partial record written. Never a refusal.
- Every GET /mcp/version is wrapped: a failed gate read stops the run (VersionReadFailed) with the partial record
  written; the gate compares contractVersion AND buildSha. The end read is retried once after a pause.
- The record carries contractVersion / buildSha (start) and versionAtEnd / buildShaAtEnd (end); `contractMoved` is True
  (they differ), False, or None (a read failed). The header cache is written only when contractMoved is False; else the
  headers stay in the record under `headersWithheld`. Exit 0 clean, 3 stopped early, 2 a completed run whose contract
  moved or could not be read.

Usage: PROBE_DATE=2026-11-07 PROBE_HINTS=C:/Users/rafae/omega-v012-hints/hints_20261106 \
       python scripts/probe_authoring_148.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, ".")

PROBE_DATE = os.environ.get("PROBE_DATE", "2026-11-07")
HINTS = os.environ.get("PROBE_HINTS")       # required by main(); read lazily so the module imports for tests
CONTRACT = os.environ.get("PROBE_CONTRACT", "149.1.0")
MAJOR = CONTRACT.split(".")[0]
HEADERS_OUT = f"data/contract/columns/_probe_{MAJOR}_{PROBE_DATE}.json"
RECORD_OUT = f"data/audit/authoring_probe_{MAJOR}_{PROBE_DATE}.json"
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
# The pause before the one re-send of an answer that is neither a render nor a refusal, and before the end version
# read's one retry.
RETRY_PAUSE = 20.0
VERSION_URL = "https://mcp.battlegrid.trade/mcp/version"
# The platform's code for an authoring refusal: every one of the 196 preview refusals recorded in data/audit carries it.
# Every other code of the served error enum (RATE_LIMITED, INTERNAL_ERROR, UNAUTHORIZED, ...) is about the call.
REFUSAL_CODE = "VALIDATION_ERROR"
DEADLINE_CODE = "SERVICE_UNAVAILABLE"
RATE_LIMIT_CODE = "RATE_LIMITED"


class TransportFailure(RuntimeError):
    """Nothing the platform rendered or refused: the call never produced a platform answer (OAuth / credential lost,
    timeout, empty or non-JSON stdout, a body with a code other than VALIDATION_ERROR / SERVICE_UNAVAILABLE). The run
    stops - such a probe is never recorded, least of all as a refusal."""


class ContractMoved(RuntimeError):
    """The served contract (version or build) left the one this run probes."""


class VersionReadFailed(RuntimeError):
    """A mid-run GET /mcp/version failed: the run cannot say which contract it is probing, so it stops."""


def version():
    with urllib.request.urlopen(VERSION_URL, timeout=30) as r:
        return json.loads(r.read().decode())


def is_rate_limit(text):
    return "Rate limited" in text or "429" in text


def classify(d):
    """The shared answer rule of the three probing scripts (review pass 2, finding 5): 'render' | 'refusal' (a
    VALIDATION_ERROR body) | 'deadline' (SERVICE_UNAVAILABLE) | 'rate_limited' | 'other' (another code, an mcporter
    `isError` body, anything else - never a refusal)."""
    if not isinstance(d, dict):
        return "other"
    if "budgetUsage" in d and isinstance(d.get("authoring"), dict):
        return "render"
    code = d.get("code")
    if code == REFUSAL_CODE and "authoring" not in d:
        return "refusal"
    if code == DEADLINE_CODE:
        return "deadline"
    if code == RATE_LIMIT_CODE:
        return "rate_limited"
    return "other"


def read_version_safely(read, retry_pause=None):
    """`read()` (a GET /mcp/version) that never raises: a failure -> {"error": ...}. With `retry_pause`, a failed read
    is retried once after that pause (the end-of-run read)."""
    err = None
    for attempt in (1, 2):
        try:
            v = read()
            if not isinstance(v, dict) or "error" in v:
                raise ValueError(f"no version object: {str(v)[:200]}")
            return v
        except Exception as exc:                  # HTTPError / URLError / timeout / a body that is not JSON
            err = f"{type(exc).__name__}: {str(exc)[:200]}"
        if retry_pause is None or attempt == 2:
            break
        time.sleep(retry_pause)
    return {"error": f"GET /mcp/version failed ({err})"}


def contract_fields(v0, v1):
    """The record's contract fields, shared by the three probing scripts: `contractVersion` / `buildSha` from the read
    before the first call, `versionAtEnd` / `buildShaAtEnd` from the read after the last one. `contractMoved` is True
    when they differ, None when either read failed (the run cannot say which contract it measured)."""
    v0, v1 = v0 or {}, v1 or {}
    fields = {"contractVersion": v0.get("contractVersion"), "buildSha": v0.get("buildSha"),
              "versionAtEnd": v1.get("contractVersion"), "buildShaAtEnd": v1.get("buildSha")}
    if "error" in v0 or "error" in v1 or not v0 or not v1:
        fields["contractMoved"] = None
        fields["versionReadErrors"] = {k: v["error"] for k, v in (("start", v0), ("end", v1)) if "error" in v}
    else:
        fields["contractMoved"] = ((v0.get("contractVersion"), v0.get("buildSha"))
                                   != (v1.get("contractVersion"), v1.get("buildSha")))
    return fields


def withheld_because(fields):
    """Why the header cache is held back (contractMoved not False), in words: moved, or unreadable."""
    if fields["contractMoved"] is None:
        return f"a version read failed, so the contract measured is unknown: {fields.get('versionReadErrors')}"
    return (f"the served contract moved during the run ({fields['contractVersion']} / {fields['buildSha']} -> "
            f"{fields['versionAtEnd']} / {fields['buildShaAtEnd']})")


def call(tool, args, timeout=240, attempts=4):
    """The platform's JSON answer (any JSON: preview() classifies it). Raises TransportFailure on anything else: an
    OAuth prompt at once (never retried - each retry would start another authorization), a rate limit after
    `attempts` backed-off sends; a timeout, empty stdout or non-JSON stdout after one re-send."""
    assert tool == "preview_strategy_report", tool
    err = None
    other = 0
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
        else:
            txt = out.decode("utf-8", errors="replace")
            if txt.strip():
                try:
                    return json.loads(txt)
                except json.JSONDecodeError:
                    err = f"stdout is not JSON: {txt[:400]}"
            else:
                err = (serr.decode(errors="replace") or "empty stdout")[:400]
                if any(marker in err for marker in AUTH_MARKERS):
                    raise TransportFailure(f"mcporter has no usable credential for battlegrid-anbu (re-authorizing is "
                                           f"the user's step): {err}")
                if is_rate_limit(err):
                    time.sleep(2.0 * attempt)
                    continue
        other += 1                                 # no platform answer: re-sent once, then the run stops
        if other >= 2:
            break
        time.sleep(RETRY_PAUSE)
    raise TransportFailure(f"no platform answer after {attempt} attempt(s): {err}")


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
    other = 0
    for attempt in range(1, 5):
        d = call("preview_strategy_report", req)
        kind = classify(d)
        if kind == "render":
            return req, d, None
        if kind in ("refusal", "deadline"):        # a deadline is the caller's to mark transient, never a refusal
            return req, None, d
        if kind == "rate_limited":
            time.sleep(2.0 * attempt)
            continue
        other += 1                                 # another code, an isError body: re-sent once, then the run stops
        if other >= 2:
            break
        time.sleep(RETRY_PAUSE)
    raise TransportFailure(f"neither a render nor a refusal (code {d.get('code') if isinstance(d, dict) else None!r}, "
                           f"after {attempt} send(s)): {json.dumps(d)[:600]}")


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


SMOOTHERS = ("rma", "wma", "rsi", "cci")


def window_max(metric, tid):
    """The served window maximum of `tid` on `metric` (the hint's authoring block), None when not served."""
    for t in hint(metric)["transforms"]:
        if t["id"] == tid:
            return ((t.get("authoring") or {}).get("parameters") or {}).get("window", {}).get("maximum")
    return None


def knob(metric, name):
    """The served spec of one knob on one metric: defaultValue / minimum / maximum / step / bound."""
    return hint(metric)["parameters"][name]


def group_j(batch, one):
    """J: what 149.0.0 / 149.1.0 added - the four smoothers and the thirteen knobs. Every maximum, minimum and step
    is the hint's; a value one step past it is the expected refusal."""
    print("J. the 149 smoothers")
    for tid in SMOOTHERS:
        wmax = window_max("RSI14", tid)
        batch(f"J.{tid}.accept", [C("RSI14", tid, window=14), C("CLOSE", tid, window=14), C("QUOTE_VOL", tid, window=14),
                                  C("RSI14", tid), C("RSI14", tid, window=1), C("RSI14", tid, window=wmax),
                                  C("CLOSE", tid, window=14, bars="closed")])
        one(f"J.RSI14.{tid}.w{wmax + 1}", C("RSI14", tid, window=wmax + 1))
        batch(f"J.{tid}.chainOuter", [C("CLOSE", "distance", chainedTransformId=tid, window=10),
                                      C("RSI14", "spread", inputs=[{"metric": "RSI7"}], chainedTransformId=tid, window=10),
                                      C("CLOSE", "relativeTo", chainedTransformId=tid, window=10)])
    one("J.CLOSE.distance.chain.rma.w119", C("CLOSE", "distance", chainedTransformId="rma", window=119))
    one("J.CLOSE.distance.chain.wma.w937", C("CLOSE", "distance", chainedTransformId="wma", window=937))
    one("J.RSI14.zscore.chain.rma", C("RSI14", "zscore", window=20, chainedTransformId="rma"))
    one("J.CLOSE.rma.chain.trajectory", C("CLOSE", "rma", window=14, chainedTransformId="trajectory"))
    one("J.RSI14.rma.offset1", C("RSI14", "rma", window=14, offset=1))
    one("J.PIVOT_WEEK_P.rsi", C("PIVOT_WEEK_P", "rsi", window=14))
    one("J.RSI14.cci.abs4h", C("RSI14", "cci", window=20, timeframe={"abs": "4h"}))

    print("J. the 149 knobs")
    batch("J.knobs.accept", [
        C("MACD_LINE", fast=8, slow=21, signal=5), C("MACD_LINE", fast=8), C("PPO_LINE", slow=30),
        C("MACD_HIST", signal=7), C("STOCH_K", period=21, kSmoothing=5, dSmoothing=5), C("STOCH_RSI_K", rsiPeriod=21),
        C("BB_UPPER", period=30, stdDev=2.5), C("BB_PCT_B", stdDev=1.5),
        C("KC_UPPER", period=30, atrPeriod=14, multiplier=1.5), C("ST_LINE", atrPeriod=14, multiplier=2),
        C("PSAR", accelerationStart=0.01, accelerationIncrement=0.01, accelerationMaximum=0.3),
        C("CMF20", period=30), C("MFI14", period=21), C("WILLR14", period=21)])
    batch("J.knobs.defaults", [
        C("MACD_LINE", fast=12, slow=26, signal=9), C("BB_UPPER", period=20, stdDev=2),
        C("PSAR", accelerationStart=0.02, accelerationIncrement=0.02, accelerationMaximum=0.2),
        C("ST_LINE", atrPeriod=knob("ST_LINE", "atrPeriod")["defaultValue"],
          multiplier=knob("ST_LINE", "multiplier")["defaultValue"])])
    # bounds: each knob kind at its served maximum (accepted) and one step past (refused), a minimum and an off-step
    for metric, name in (("MACD_LINE", "fast"), ("MACD_LINE", "signal"), ("STOCH_RSI_K", "rsiPeriod"),
                         ("ST_LINE", "atrPeriod"), ("BB_UPPER", "stdDev"), ("KC_UPPER", "multiplier"),
                         ("PSAR", "accelerationMaximum")):
        spec = knob(metric, name)
        step = spec.get("step") or 1
        one(f"J.{metric}.{name}.max", C(metric, **{name: spec["maximum"]}))
        one(f"J.{metric}.{name}.over", C(metric, **{name: round(spec["maximum"] + step, 6)}))
    for metric, name in (("BB_UPPER", "period"), ("BB_UPPER", "stdDev"), ("PSAR", "accelerationStart")):
        spec = knob(metric, name)
        step = spec.get("step") or 1
        one(f"J.{metric}.{name}.under", C(metric, **{name: round(spec["minimum"] - step, 6)}))
    one("J.BB_UPPER.stdDev.offstep", C("BB_UPPER", stdDev=2.25))
    one("J.BB_UPPER.period.nonInteger", C("BB_UPPER", period=20.5))
    one("J.MACD_LINE.fast.gt.slow", C("MACD_LINE", fast=30, slow=10))
    one("J.MACD_LINE.fast.eq.slow", C("MACD_LINE", fast=26, slow=26))
    one("J.EQH.equalThreshold.negative", C("EQH", equalThreshold=-0.1))
    # a knob the metric does not serve
    one("J.RSI14.period", C("RSI14", period=21))
    one("J.CLOSE.stdDev", C("CLOSE", stdDev=2))
    one("J.MACD_LINE.period", C("MACD_LINE", period=20))
    # under transforms: metricParametersAccepted false (aggregate, ema, the smoothers, relativeTo, zscore) / true
    one("J.MACD_LINE.aggregate.fast8", C("MACD_LINE", "aggregate", window=10, fast=8))
    one("J.MACD_LINE.ema.fast8", C("MACD_LINE", "ema", window=10, fast=8))
    one("J.MACD_LINE.rma.fast8", C("MACD_LINE", "rma", window=10, fast=8))
    one("J.BB_UPPER.relativeTo.stdDev", C("BB_UPPER", "relativeTo", stdDev=2.5))
    one("J.BB_UPPER.zscore.stdDev", C("BB_UPPER", "zscore", window=20, stdDev=2.5))
    one("J.BB_UPPER.distance.chain.rma.stdDev", C("BB_UPPER", "distance", chainedTransformId="rma", window=10,
                                                  stdDev=2.5))
    batch("J.knobs.transforms.accept", [
        C("MACD_LINE", "trajectory", window=4, fast=8), C("MACD_LINE", "crossDetect", fast=8),
        C("MACD_LINE", "spread", inputs=[{"metric": "MACD_SIGNAL"}], fast=8), C("MACD_LINE", "efficiency", window=20, fast=8),
        C("BB_UPPER", "distance", stdDev=2.5), C("BB_UPPER", "levelInteraction", stdDev=2.5),
        C("STOCH_K", "classifyZone", period=21), C("PSAR", "distance", accelerationMaximum=0.3)])
    # combinations: knobs + offset + a pinned / lower timeframe (header order)
    batch("J.knobs.combos", [C("MACD_LINE", fast=8, slow=21, offset=1), C("MACD_LINE", fast=8, timeframe={"abs": "4h"}),
                             C("BB_UPPER", period=30, stdDev=2.5, timeframe={"rel": "lower"}, offset=2),
                             C("KC_UPPER", multiplier=1.5, atrPeriod=14, period=30, offset=1)])


def main(extra_groups=None, what=None) -> int:
    """`extra_groups(batch, one, probe)`, when given, is sent INSTEAD of this probe's groups A - J, under the same rules
    (version gate, refusal rule, record and header cache): scripts/probe_authoring_161.py (2026-11-09) uses it."""
    # 2026-11-08 (review pass 1, finding 3): one run per PROBE_DATE. The default PROBE_DATE names the committed 11-07
    # record and seen-header cache, and an aborted run still writes both files: a re-run would replace the 225-probe
    # record and the 254-header cache (a render_coverage SEEN_FILES entry) with whatever it reached. As in
    # sweep_render_coverage (SWEEP_OVERWRITE), PROBE_OVERWRITE=1 replaces them on purpose.
    taken = [p for p in (RECORD_OUT, HEADERS_OUT) if os.path.exists(p)]
    if taken and os.environ.get("PROBE_OVERWRITE") != "1":
        sys.exit(f"{', '.join(taken)} already exist: give this run its own PROBE_DATE, or PROBE_OVERWRITE=1 to replace "
                 "them")
    if not HINTS:
        sys.exit("set PROBE_HINTS (the dir holding <METRIC>.json raw hints)")
    v0 = read_version_safely(version)
    if "error" in v0:                     # nothing sent yet, nothing to record
        sys.exit(f"{v0['error']}: stop before the first probe")
    if v0.get("contractVersion") != CONTRACT:
        sys.exit(f"served contract {v0.get('contractVersion')} is not {CONTRACT}: stop")
    record = {"_what": what or __doc__.strip().splitlines()[0], "contractVersion": CONTRACT, "buildSha": v0.get("buildSha"),
              "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "capturedAt": None, "probes": []}
    headers = set()
    t0 = time.time()

    def probe(name, sections, tickers=("BTC",), timeframe="1h", keep_candidates=False):
        if record["probes"] and len(record["probes"]) % VERSION_EVERY == 0:
            now = read_version_safely(version)
            if "error" in now:
                raise VersionReadFailed(f"the gate read after {len(record['probes'])} probes: {now['error']}")
            if (now.get("contractVersion"), now.get("buildSha")) != (CONTRACT, v0.get("buildSha")):
                raise ContractMoved(f"served contract {now.get('contractVersion')} / {now.get('buildSha')} after "
                                    f"{len(record['probes'])} probes, not {CONTRACT} / {v0.get('buildSha')}: {now}")
        req, d, e = preview(sections, tickers, timeframe)
        entry = {"probe": name,
                 "sections": [{k: s[k] for k in ("benchmarkTicker", "marketScope", "columns")} for s in sections],
                 "tickers": list(tickers), "timeframe": timeframe,
                 "accepted": d is not None, "render": digest(d) if d else None, "refusal": refusal(e)}
        if e is not None and e.get("code") == "SERVICE_UNAVAILABLE":
            # the preview's 15 s deadline (seen 2026-11-07 on two batches): a platform answer, NOT an authoring
            # refusal - a batch so answered is re-probed column by column like any refused batch
            entry["transient"] = True
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

        group_j(batch, one)

    aborted = None
    try:
        if extra_groups is not None:
            extra_groups(batch, one, probe)
        else:
            groups()
    except (TransportFailure, ContractMoved, VersionReadFailed) as exc:
        aborted = {"reason": type(exc).__name__, "message": str(exc)[:600],
                   "afterProbes": len(record["probes"]),
                   "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        print(f"\nABORTED after {len(record['probes'])} probes: {aborted['message']}", flush=True)

    v1 = read_version_safely(version, RETRY_PAUSE)   # never raises: the record of what WAS rendered is still written
    fields = contract_fields(v0, v1)
    record["capturedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record.update({k: v for k, v in fields.items() if k not in ("contractVersion",)})
    # A run that stopped on a transport failure or a contract move is PARTIAL: every probe in it is a platform answer
    # (a render or a verbatim refusal), and the groups after `aborted.afterProbes` were never sent.
    record["complete"] = aborted is None
    record["aborted"] = aborted
    record["how"] = ("preview_strategy_report via the mcporter CLI, read-only, detail detailed, BTC at a 1h anchor; one "
                     "custom section per probe, its benchmarkTicker / marketScope as recorded; GET /mcp/version before "
                     "and after")
    record["counts"] = {"probes": len(record["probes"]), "accepted": sum(p["accepted"] for p in record["probes"]),
                        "refused": sum(not p["accepted"] for p in record["probes"]),
                        "transient": sum(bool(p.get("transient")) for p in record["probes"]), "headersMinted": len(headers)}
    # The seen-header cache only for a run whose contract is known and did not move; otherwise the headers stay in the
    # record (nothing rendered is lost) and no SEEN_FILE names them.
    write_headers = fields["contractMoved"] is False
    record["headersWritten"] = write_headers
    if not write_headers:
        record["headersWithheld"] = sorted(headers)
        record["headersWithheldBecause"] = withheld_because(fields)
    os.makedirs(os.path.dirname(RECORD_OUT) or ".", exist_ok=True)
    with open(RECORD_OUT, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
        f.write("\n")
    if write_headers:
        os.makedirs(os.path.dirname(HEADERS_OUT) or ".", exist_ok=True)
        with open(HEADERS_OUT, "w", encoding="utf-8") as f:
            json.dump({"_what": (f"Headers minted live by preview_strategy_report in the {PROBE_DATE} authoring probe "
                                 f"at contract {CONTRACT} ({RECORD_OUT}). HEADERS ONLY - render_coverage treats every "
                                 "string in this file as a seen header, so nothing else may be added here."),
                       "headers": sorted(headers)}, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"\n{record['counts']}\nwrote {RECORD_OUT} and {HEADERS_OUT}")
    else:
        print(f"\n{record['counts']}\nwrote {RECORD_OUT} only; header cache withheld: {record['headersWithheldBecause']}")
    if aborted is not None:
        print(f"PARTIAL: aborted ({aborted['reason']}) after {aborted['afterProbes']} probes")
        return 3
    if fields["contractMoved"] is None:
        print(f"WARNING: the served contract could not be read at the end of the run: {fields['versionReadErrors']}")
        return 2
    if fields["contractMoved"]:
        print(f"WARNING: {withheld_because(fields)}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
