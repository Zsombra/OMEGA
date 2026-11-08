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
from scripts.probe_authoring_148 import C, digest, preview, refusal, section, version

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


def main() -> int:
    for out in (RECORD_OUT, HEADERS_OUT):
        if os.path.exists(out):
            sys.exit(f"{out} exists: one run per PROBE_DATE")
    cols_all, source = columns()
    for col in cols_all:                  # a malformed column stops here, before any call
        Column(**col)
    v0 = version()
    if v0.get("contractVersion") != CONTRACT:
        sys.exit(f"served contract {v0.get('contractVersion')} is not {CONTRACT}: stop")
    c = OC.load()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entries, headers = [], set()
    transient = []

    def send(cols, name):
        for attempt in (1, 2):
            _, d, e = preview([section(cols, name)])
            if d is None and (e or {}).get("code") == "SERVICE_UNAVAILABLE":
                # the preview's deadline: a platform answer about load, never about these columns
                transient.append({"section": name, "attempt": attempt, "answer": refusal(e)})
                if attempt == 1:
                    print(f"  {name}: SERVICE_UNAVAILABLE, re-sending once after {RETRY_PAUSE:.0f}s", flush=True)
                    time.sleep(RETRY_PAUSE)
                    continue
                raise DeadlineStop(f"{name}: SERVICE_UNAVAILABLE twice: {(e or {}).get('message')}")
            if d is None:
                return None, refusal(e)
            rendered = [x["key"] for s in digest(d)["sections"] for x in s["columns"] if x.get("role") != "identity"]
            return rendered, None

    aborted = None
    try:
        rendered, err = send(cols_all, "knobs")
        groups = [(cols_all, rendered, err)] if err is None else []
        if err is not None:                                  # attribute the refusal: each column alone
            for i, col in enumerate(cols_all):
                r, e = send([col], f"knobs#{i}")
                groups.append(([col], r, e))
    except DeadlineStop as exc:
        groups = []
        aborted = {"reason": "SERVICE_UNAVAILABLE", "message": str(exc)[:600],
                   "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for cols, rend, e in groups:
        pred = [o.header for col in cols for o in outputs_for(Column(**col), c)]
        entries.append({"columns": cols, "predicted": pred, "rendered": rend, "refusal": e,
                        "agree": rend == pred if rend is not None else None})
        headers.update(rend or ())
    v1 = version()
    moved = (v0.get("contractVersion"), v0.get("buildSha")) != (v1.get("contractVersion"), v1.get("buildSha"))
    judged = [x["agree"] for x in entries if x["agree"] is not None]
    record = {"_what": __doc__.strip().splitlines()[0], "contractVersion": CONTRACT, "buildSha": v0.get("buildSha"),
              "startedAt": started, "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "versionAtEnd": v1.get("contractVersion"), "buildShaAtEnd": v1.get("buildSha"),
              "contractMoved": moved, "columnsFrom": source,
              "complete": aborted is None, "aborted": aborted, "transient": transient, "entries": entries,
              # None when nothing rendered: agreement over zero renders is not agreement
              "agree": all(judged) if judged else None,
              "refused": sum(1 for x in entries if x["refusal"] is not None)}
    write_headers = aborted is None and not moved
    if not write_headers:
        record["headersWritten"] = False
        record["headersWithheld"] = ("the run stopped on a deadline answer" if aborted is not None else
                                     f"the served contract moved during the run ({v0} -> {v1})")
    os.makedirs(os.path.dirname(RECORD_OUT) or ".", exist_ok=True)
    with open(RECORD_OUT, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
        f.write("\n")
    for x in entries:
        print("AGREE" if x["agree"] else "DIFF ", x["predicted"], x["rendered"], x["refusal"])
    if aborted is not None:
        print(f"ABORTED: {aborted['message']}; wrote {RECORD_OUT} only")
        return 3
    if moved:
        print(f"the served contract moved during the run ({v0} -> {v1}): wrote {RECORD_OUT} only, no header cache")
        return 2
    os.makedirs(os.path.dirname(HEADERS_OUT) or ".", exist_ok=True)
    with open(HEADERS_OUT, "w", encoding="utf-8") as f:
        json.dump({"_what": f"Headers minted live by {RECORD_OUT}. HEADERS ONLY - render_coverage treats every string "
                            f"in this file as a seen header.", "headers": sorted(headers)}, f, ensure_ascii=False,
                  indent=1)
        f.write("\n")
    print(f"wrote {RECORD_OUT} and {HEADERS_OUT}; version at end {v1.get('contractVersion')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
