"""Sweep the whole legal column space past the live compiler.

Two halves, because omega opens no sockets:

    python -m scripts.sweep plan     -> writes batches + predicted headers to disk
    python -m scripts.sweep ingest   -> reads captured header rows, diffs them

The claim under test is the one the whole toolkit rests on: that
`omega.fanout.outputs_for` predicts the platform's headers exactly, for every
legal shape - not just the handful anyone happened to probe.

WHAT columnLookback ACTUALLY IS
------------------------------
Measured, not assumed. Three renders of 12, 8 and 4 columns each reported
`columnLookback: 24`, and a fourth of 24 columns reported 24 again. It is not
a per-column sum - it is the deepest history the report needs, in BARS. So the
cap that binds a sweep is `sectionColumns: 32`, and a batch is limited by how
far back its hungriest column reaches, not by how many columns it holds.

Consequence: metrics needing more than 32 bars of history (SMA50, SMA200)
cannot share a section budget with anything. They are planned into their own
batch so one deep column cannot fail an otherwise good one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from omega.contract import load
from omega.fanout import outputs_for
from omega.space import ColumnShape, enumerate_shapes
from omega.validate import validate_report
from omega.types import CustomSection, Report

OUT = Path("data/contract/columns")
PLAN = OUT / "_sweep_plan.json"
SEEN = OUT / "_sweep_seen.json"

LOOKBACK_CAP = 32
COLUMN_CAP = 32

BATCH_COLUMNS = 30        # under the measured cap of 32, leaving headroom

# Metrics whose own period exceeds the 32-bar lookback cap. Isolated so one
# deep column cannot take an otherwise valid batch down with it.
DEEP_HISTORY = {"SMA50", "SMA200"}

# DECLARED LEGAL, CANNOT RENDER
# ----------------------------
# Every crowd-family metric declares transforms ["rank", "value"] in the
# platform's own contract, and every one of them returns INTERNAL_ERROR when
# `rank` is actually rendered - alone or in company, settled or _LIVE. The
# matching `value` shapes all render fine. Measured 2026-08-24; four confirmed
# one column at a time (CROWD_ACC, CROWD_ACC_LIVE, CROWD_CAPT, CROWD_UPBIAS),
# the remaining four covered by group renders that failed as a set.
#
# Quarantined rather than deleted: they are legal by the contract, so omega
# must keep enumerating them, but shipping one poisons a whole batch.
UNRENDERABLE = {(m, "rank") for m in (
    "CROWD_ACC", "CROWD_ACC_LIVE", "CROWD_CAPT", "CROWD_CAPT_LIVE",
    "CROWD_PICK", "CROWD_PICK_LIVE", "CROWD_UPBIAS", "CROWD_UPBIAS_LIVE",
)}


def legal(shape: ColumnShape, contract) -> bool:
    """Only ship shapes omega.validate already accepts - the illegal ones are
    tested offline, and one bad column would fail a whole batch."""
    col = shape.to_column()
    section = CustomSection(kind="custom", title="sweep", benchmarkTicker=None,
                            columns=[col])
    report = Report(anchor="1h", sections=[section])
    return not [f for f in validate_report(report).findings if f.severity == "error"]


def build(overrides: dict[str, int]) -> list[dict]:
    c = load()
    shapes = [s for s in enumerate_shapes(contract=c) if legal(s, c)]
    shapes = [s for s in shapes
              if (s.metric, s.chained or s.transform) not in UNRENDERABLE]
    shallow = [s for s in shapes if s.metric not in DEEP_HISTORY]
    deep = [s for s in shapes if s.metric in DEEP_HISTORY]

    n = overrides.get("_columns", BATCH_COLUMNS)
    batches = [shallow[i:i + n] for i in range(0, len(shallow), n)]
    # deep-history shapes go last, in small batches of their own
    batches += [deep[i:i + 4] for i in range(0, len(deep), 4)]

    out = []
    for i, batch in enumerate(batches):
        cols, headers = [], []
        for s in batch:
            col = s.to_column()
            cols.append(col.wire())
            headers.extend(o.header for o in outputs_for(col, c))
        out.append({
            "index": i,
            "shapes": [[s.metric, s.transform, s.chained, s.operand, s.ordering]
                       for s in batch],
            "columns": cols,
            "predictedHeaders": headers,
            "deepHistory": sorted({s.metric for s in batch} & DEEP_HISTORY),
        })
    return out


def cmd_plan(argv: list[str]) -> int:
    overrides = {}
    for a in argv:
        if a.startswith("--columns="):
            overrides["_columns"] = int(a[len("--columns="):])
    batches = build(overrides)
    OUT.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(batches, indent=1), encoding="utf-8")
    total = sum(len(b["shapes"]) for b in batches)
    heads = sum(len(b["predictedHeaders"]) for b in batches)
    print(f"{total} legal shapes -> {len(batches)} batches, {heads} predicted headers")
    print(f"wrote {PLAN}")
    for b in batches[:3]:
        print(f"  batch {b['index']:>2}: {len(b['shapes'])} cols"
              + (f"  DEEP {b['deepHistory']}" if b["deepHistory"] else ""))
    return 0


def cmd_show(argv: list[str]) -> int:
    """Print one batch's columns as a paste-ready sections payload."""
    i = int(argv[0])
    b = json.loads(PLAN.read_text(encoding="utf-8"))[i]
    print(json.dumps([{"kind": "custom", "title": f"sweep {i}",
                       "benchmarkTicker": None, "columns": b["columns"]}]))
    return 0


def cmd_record(argv: list[str]) -> int:
    """Record one batch's live header row, given verbatim as a markdown row.

        python -m scripts.sweep record 3 "| coin | ADX | ATR | ... |"

    Parsing the row rather than a hand-listed set keeps the captured value a
    transcription of what the platform printed, not a retyping of it.
    """
    i, row = argv[0], argv[1]
    headers = [h.strip() for h in row.strip().strip("|").split("|")]
    seen = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}
    seen[str(int(i))] = headers
    SEEN.write_text(json.dumps(seen, indent=1), encoding="utf-8")
    print(f"batch {i}: recorded {len(headers)} headers (incl. coin)")
    return 0


def cmd_ingest(argv: list[str]) -> int:
    """Diff every captured header row against the prediction."""
    plan = {b["index"]: b for b in json.loads(PLAN.read_text(encoding="utf-8"))}
    seen = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}

    ok = bad = 0
    problems = []
    for k, actual in sorted(seen.items(), key=lambda kv: int(kv[0])):
        b = plan[int(k)]
        pred = b["predictedHeaders"]
        # the rendered row always leads with the coin column
        act = [h for h in actual if h != "coin"]
        if act == pred:
            ok += len(b["shapes"])
            continue
        bad += len(b["shapes"])
        only_pred = [h for h in pred if h not in act]
        only_act = [h for h in act if h not in pred]
        problems.append((int(k), only_pred, only_act))

    covered = ok + bad
    total = sum(len(b["shapes"]) for b in plan.values())
    print(f"batches captured : {len(seen)} of {len(plan)}")
    print(f"shapes verified  : {covered} of {total}")
    print(f"headers match    : {ok} shapes exact, {bad} in mismatched batches")
    for i, mp, ma in problems:
        print(f"\n  batch {i}")
        if mp:
            print(f"    predicted, absent live : {mp}")
        if ma:
            print(f"    live, not predicted    : {ma}")
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    return {"plan": cmd_plan, "show": cmd_show, "record": cmd_record,
            "ingest": cmd_ingest}[cmd](rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
