"""Knob header spellings omega.fanout predicts but the 2026-11-07 authoring probe never rendered, rendered at 149.1.0.

The authoring probe (scripts/probe_authoring_148.py, data/audit/authoring_probe_149_2026-11-07.json) rendered each knob
family once. omega.fanout.knob_token generalises those renders into two regimes (a SET spelled whole once any of its
knobs is off default, SINGLE knobs spelled one by one), and a few of its predictions have no render behind them:
swingLength and confluenceFilter together, STOCH_RSI with a knob other than rsiPeriod off, the D / signal / lower-band
siblings of the rendered keys, a knob with a Developing read. This sends them, one section, one preview, and compares.

Read-only: `preview_strategy_report` over mcporter (battlegrid-anbu), the helpers of probe_authoring_148. A column the
platform refuses is re-sent alone. Writes data/audit/knob_spelling_probe_149_<DATE>.json (sent, predicted, rendered)
and data/contract/columns/_probe_149_knobs_<DATE>.json (headers only, for render_coverage).

    PATH=<npx shim>:$PATH python -m scripts.probe_knob_spelling_149
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


def main() -> int:
    for out in (RECORD_OUT, HEADERS_OUT):
        if os.path.exists(out):
            sys.exit(f"{out} exists: one run per PROBE_DATE")
    v0 = version()
    if v0.get("contractVersion") != CONTRACT:
        sys.exit(f"served contract {v0.get('contractVersion')} is not {CONTRACT}: stop")
    c = OC.load()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entries, headers = [], set()

    def send(columns, name):
        _, d, e = preview([section(columns, name)])
        if d is None:
            return None, refusal(e)
        rendered = [x["key"] for s in digest(d)["sections"] for x in s["columns"] if x.get("role") != "identity"]
        return rendered, None

    rendered, err = send(COLUMNS, "knobs")
    groups = [(COLUMNS, rendered, err)] if err is None else []
    if err is not None:                                  # attribute the refusal: each column alone
        for i, col in enumerate(COLUMNS):
            r, e = send([col], f"knobs#{i}")
            groups.append(([col], r, e))
    for cols, rend, e in groups:
        pred = [o.header for col in cols for o in outputs_for(Column(**col), c)]
        entries.append({"columns": cols, "predicted": pred, "rendered": rend, "refusal": e,
                        "agree": rend == pred if rend is not None else None})
        headers.update(rend or ())
    v1 = version()
    record = {"_what": __doc__.strip().splitlines()[0], "contractVersion": CONTRACT, "buildSha": v0.get("buildSha"),
              "startedAt": started, "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "versionAtEnd": v1.get("contractVersion"), "entries": entries,
              "agree": all(x["agree"] for x in entries if x["agree"] is not None),
              "refused": sum(1 for x in entries if x["refusal"] is not None)}
    with open(RECORD_OUT, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(HEADERS_OUT, "w", encoding="utf-8") as f:
        json.dump({"_what": f"Headers minted live by {RECORD_OUT}. HEADERS ONLY - render_coverage treats every string "
                            f"in this file as a seen header.", "headers": sorted(headers)}, f, ensure_ascii=False,
                  indent=1)
        f.write("\n")
    for x in entries:
        print("AGREE" if x["agree"] else "DIFF ", x["predicted"], x["rendered"], x["refusal"])
    print(f"wrote {RECORD_OUT} and {HEADERS_OUT}; version at end {v1.get('contractVersion')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
