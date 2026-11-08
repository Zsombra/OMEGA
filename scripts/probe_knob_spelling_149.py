"""Knob header spellings omega.fanout predicts but the 2026-11-07 authoring probe never rendered, rendered at 149.1.0.

The authoring probe (scripts/probe_authoring_148.py, data/audit/authoring_probe_149_2026-11-07.json) rendered each knob
family once. omega.fanout.knob_token generalises those renders into two regimes (a SET spelled whole once any of its
knobs is off default, SINGLE knobs spelled one by one), and a few of its predictions have no render behind them:
swingLength and confluenceFilter together, STOCH_RSI with a knob other than rsiPeriod off, the D / signal / lower-band
siblings of the rendered keys, a knob with a Developing read. This sends them, one section, one preview, and compares.

Read-only: `preview_strategy_report` over mcporter (battlegrid-anbu), the helpers of probe_authoring_148. A column the
platform refuses is re-sent alone. Writes data/audit/knob_spelling_probe_149_<DATE>.json (sent, predicted, rendered)
and data/contract/columns/_probe_149_knobs_<DATE>.json (headers only, for render_coverage). Either output that already
exists is refused: one run per PROBE_DATE.

A second probe needs no edit: KNOB_COLUMNS names a JSON file holding the list of column dicts to send (default: the
thirteen built-in columns of 11-07) and PROBE_DATE names the outputs (default 2026-11-07, the committed pair).

2026-11-08 (review pass 1, finding 4): the preview's 15 s deadline answer (`SERVICE_UNAVAILABLE`) is transient, not a
refusal - it is re-sent once after a pause, and a second one stops the run (record marked aborted, no header cache,
exit 3). `agree` is None when nothing rendered. A contract or build that moved between the first and the last version
read exits 2 with the record saying so and no header cache written.

2026-11-08 (review pass 2, findings 2, 5, 7, 8):
- Every column is predicted BEFORE the first preview. A column omega cannot predict (fanout raises ValueError on a
  (metric, knob) cell no render has shown) is recorded with "predicted": null and "unpredicted": <why>, its entry's
  `agree` null - and it is still sent: rendering such cells is what this probe is for.
- A refusal is a VALIDATION_ERROR body. Any other code (and, through preview(), an isError body or a lost transport)
  is re-sent once and then stops the run (exit 3), never a refusal.
- A stop during the per-column re-sends keeps every entry already answered (complete false, header cache withheld).
- Every version read is wrapped (the end read retried once after a pause): `contractMoved` is True / False / None
  (unreadable). The header cache is written only for a complete run with contractMoved False; otherwise the headers
  stay in the record under `headersWithheld`. Exit 0 clean, 3 stopped early, 2 a completed run whose contract moved or
  could not be read.

    PATH=<npx shim>:$PATH [KNOB_COLUMNS=cols.json] [PROBE_DATE=2026-11-09] python -m scripts.probe_knob_spelling_149
"""
from __future__ import annotations

import json
import os
import sys
import time

from omega import contract as OC
from omega.fanout import outputs_for
from omega.types import Column
from scripts.probe_authoring_148 import (C, REFUSAL_CODE, TransportFailure, contract_fields, digest, preview,
                                         read_version_safely, refusal, section, version, withheld_because)

CONTRACT = "149.1.0"
DATE = os.environ.get("PROBE_DATE", "2026-11-07")
RECORD_OUT = f"data/audit/knob_spelling_probe_149_{DATE}.json"
HEADERS_OUT = f"data/contract/columns/_probe_149_knobs_{DATE}.json"
# the pause before the one re-send of a deadline answer
RETRY_PAUSE = 20.0

COLUMNS = [
    C("INTERNAL_STRUCTURE_LEVEL", swingLength=20, confluenceFilter=True),
    C("INTERNAL_STRUCTURE_TREND", swingLength=20, confluenceFilter=True, timeframe={"rel": "lower"}),
    C("INTERNAL_STRUCTURE_EVENT", confluenceFilter=True),
    C("STOCH_RSI_K", period=21),
    C("STOCH_RSI_D", kSmoothing=5),
    C("STOCH_D", period=21),
    C("BB_LOWER", stdDev=2.5),
    C("PPO_SIGNAL", fast=8),
    C("ST_DIR", multiplier=2),
    C("KC_LOWER", period=30),
    C("EQL", equalBars=5, bars="all"),
    C("SWING_FRACTAL_LOW_BARS_AGO", rightBars=4),
    C("PSAR", accelerationStart=0.01),
]


class DeadlineStop(RuntimeError):
    """The platform answered SERVICE_UNAVAILABLE twice for the same preview: not a refusal, the run stops."""


def columns():
    """-> (columns, source): KNOB_COLUMNS' JSON list of column dicts, else the built-in COLUMNS."""
    path = os.environ.get("KNOB_COLUMNS")
    if not path:
        return COLUMNS, "built-in"
    with open(path, encoding="utf-8") as f:
        cols = json.load(f)
    if not isinstance(cols, list) or not cols or not all(isinstance(c, dict) and "metric" in c for c in cols):
        sys.exit(f"KNOB_COLUMNS {path}: not a non-empty JSON list of column objects with a `metric`")
    return cols, path


def predict(cols, c):
    """-> (predicted headers, None), or (None, reason) when omega cannot predict a column: omega.fanout raises
    ValueError on a (metric, knob) cell no render has shown (KNOB_SPELLING_RENDERED) - exactly the cells this probe
    exists to send. Such a column is still sent and its render recorded."""
    pred, reasons = [], []
    for col in cols:
        try:
            pred += [o.header for o in outputs_for(Column(**col), c)]
        except ValueError as exc:
            reasons.append(f"{col.get('metric')}: {str(exc)[:300]}")
    return (None, "; ".join(reasons)) if reasons else (pred, None)


def main() -> int:
    for out in (RECORD_OUT, HEADERS_OUT):
        if os.path.exists(out):
            sys.exit(f"{out} exists: one run per PROBE_DATE")
    cols_all, source = columns()
    for col in cols_all:                  # a malformed column stops here, before any call
        Column(**col)
    c = OC.load()
    # review pass 2, finding 2: every prediction is made BEFORE the first call, so a column omega cannot predict never
    # loses a live answer to an exception raised after it
    predictions = {"batch": predict(cols_all, c), "each": [predict([col], c) for col in cols_all]}
    v0 = read_version_safely(version)
    if "error" in v0:                     # nothing sent yet, nothing to record
        sys.exit(f"{v0['error']}: stop before the first preview")
    if v0.get("contractVersion") != CONTRACT:
        sys.exit(f"served contract {v0.get('contractVersion')} is not {CONTRACT}: stop")
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entries, headers = [], set()
    transient = []

    def send(cols, name):
        """-> (rendered keys, None) or (None, refusal). A deadline answer is re-sent once, then DeadlineStop; any code
        other than VALIDATION_ERROR is re-sent once, then TransportFailure - neither is ever a refusal."""
        for attempt in (1, 2):
            _, d, e = preview([section(cols, name)])
            code = (e or {}).get("code")
            if d is not None:
                rendered = [x["key"] for s in digest(d)["sections"] for x in s["columns"] if x.get("role") != "identity"]
                return rendered, None
            if code == REFUSAL_CODE:
                return None, refusal(e)
            # the preview's deadline, or any other code: a platform answer about the call, never about these columns
            transient.append({"section": name, "attempt": attempt, "answer": refusal(e)})
            if attempt == 1:
                print(f"  {name}: {code}, re-sending once after {RETRY_PAUSE:.0f}s", flush=True)
                time.sleep(RETRY_PAUSE)
                continue
            if code == "SERVICE_UNAVAILABLE":
                raise DeadlineStop(f"{name}: SERVICE_UNAVAILABLE twice: {(e or {}).get('message')}")
            raise TransportFailure(f"{name}: {code} twice, not a refusal: {(e or {}).get('message')}")

    aborted = None
    groups = []                           # filled as answers arrive: a stop keeps every one already received
    try:
        rendered, err = send(cols_all, "knobs")
        if err is None:
            groups.append((cols_all, rendered, None, predictions["batch"]))
        else:                                                # attribute the refusal: each column alone
            for i, col in enumerate(cols_all):
                r, e = send([col], f"knobs#{i}")
                groups.append(([col], r, e, predictions["each"][i]))
    except (DeadlineStop, TransportFailure) as exc:
        aborted = {"reason": "SERVICE_UNAVAILABLE" if isinstance(exc, DeadlineStop) else type(exc).__name__,
                   "message": str(exc)[:600], "afterEntries": len(groups),
                   "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for cols, rend, e, (pred, why) in groups:
        entry = {"columns": cols, "predicted": pred, "rendered": rend, "refusal": e,
                 "agree": rend == pred if rend is not None and pred is not None else None}
        if why is not None:
            entry["unpredicted"] = why
        entries.append(entry)
        headers.update(rend or ())
    v1 = read_version_safely(version, RETRY_PAUSE)        # never raises; a failed read is retried once after a pause
    fields = contract_fields(v0, v1)
    judged = [x["agree"] for x in entries if x["agree"] is not None]
    record = {"_what": __doc__.strip().splitlines()[0], **fields, "contractVersion": CONTRACT,
              "startedAt": started, "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "columnsFrom": source,
              "complete": aborted is None, "aborted": aborted, "transient": transient, "entries": entries,
              # None when nothing both rendered and was predicted: agreement over zero renders is not agreement
              "agree": all(judged) if judged else None,
              "refused": sum(1 for x in entries if x["refusal"] is not None),
              "unpredicted": sum(1 for x in entries if "unpredicted" in x)}
    # The seen-header cache only for a complete run whose contract is known and did not move; otherwise the headers
    # stay in the record, so nothing rendered is lost.
    write_headers = aborted is None and fields["contractMoved"] is False
    record["headersWritten"] = write_headers
    if not write_headers:
        record["headersWithheld"] = sorted(headers)
        record["headersWithheldBecause"] = (f"the run stopped early ({aborted['reason']})" if aborted is not None
                                            else withheld_because(fields))
    os.makedirs(os.path.dirname(RECORD_OUT) or ".", exist_ok=True)
    with open(RECORD_OUT, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
        f.write("\n")
    for x in entries:
        print({True: "AGREE", False: "DIFF ", None: "N/A  "}[x["agree"]], x["predicted"], x["rendered"], x["refusal"],
              x.get("unpredicted") or "")
    if aborted is not None:
        print(f"ABORTED: {aborted['message']}; wrote {RECORD_OUT} only ({len(entries)} answered entries kept)")
        return 3
    if not write_headers:
        print(f"{record['headersWithheldBecause']}: wrote {RECORD_OUT} only, no header cache")
        return 2
    os.makedirs(os.path.dirname(HEADERS_OUT) or ".", exist_ok=True)
    with open(HEADERS_OUT, "w", encoding="utf-8") as f:
        json.dump({"_what": f"Headers minted live by {RECORD_OUT}. HEADERS ONLY - render_coverage treats every string "
                            f"in this file as a seen header.", "headers": sorted(headers)}, f, ensure_ascii=False,
                  indent=1)
        f.write("\n")
    print(f"wrote {RECORD_OUT} and {HEADERS_OUT}; version at end {fields['versionAtEnd']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
