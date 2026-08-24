"""Render every buildable indicator family against the live compiler.

    python -m scripts.family_probe plan          -> batches, paste-ready
    python -m scripts.family_probe show N
    python -m scripts.family_probe record N "| coin | ... |"
    python -m scripts.family_probe ingest

Offline validation proves omega thinks a family is legal. It does not prove the
platform will render it - `CROWD_UPBIAS x rank` validates cleanly and returns
INTERNAL_ERROR every time. This closes that gap for the whole census.

Batching respects three constraints measured earlier:
  - sectionColumns <= 32
  - columnLookback = max(window + offset) <= 32
  - headers must be unique WITHIN a section, or the section is dropped silently
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from omega.contract import DERIVED_DIR, load
from omega.fanout import outputs_for
from omega.types import Column, Operand, RelTimeframe

OUT = Path("data/contract/columns")
PLAN = OUT / "_family_plan.json"
SEEN = OUT / "_family_seen.json"

BATCH_COLUMNS = 24        # under the 32 cap, leaving room for trajectory fan-out
LOOKBACK_CAP = 32
DEFAULT_WINDOW = {"aggregate": 24, "maxShare": 24, "efficiency": 21,
                  "trajectory": 4, "value": 24}


def _column(spec: dict) -> Column:
    return Column(
        metric=spec["metric"], transformId=spec["transformId"],
        timeframe=RelTimeframe(rel=spec.get("rel", "anchor")),
        chainedTransformId=spec.get("chainedTransformId"),
        window=spec.get("window"), offset=spec.get("offset"),
        bars=spec.get("bars"), ordering=spec.get("ordering"), side=spec.get("side"),
        inputs=[Operand(metric=i["metric"]) for i in spec["inputs"]] if spec.get("inputs") else None,
    )


def _lookback(spec: dict) -> int:
    t = spec.get("chainedTransformId") or spec["transformId"]
    w = spec.get("window") or DEFAULT_WINDOW.get(t, 24)
    return w + (spec.get("offset") or 0)


def build() -> list[dict]:
    c = load()
    fam = json.loads((DERIVED_DIR / "indicator_families.json").read_text(encoding="utf-8"))

    # flatten to (family id, spec, headers), dropping exact duplicate specs
    items, seen_spec = [], set()
    for f in fam["buildable"]:
        for spec in f["columns"]:
            key = json.dumps(spec, sort_keys=True)
            if key in seen_spec:
                continue
            seen_spec.add(key)
            items.append({"family": f["id"], "spec": spec,
                          "headers": [o.header for o in outputs_for(_column(spec), c)],
                          "lookback": _lookback(spec)})

    batches, cur, cur_heads, cur_lb = [], [], set(), 0
    for it in items:
        clash = cur_heads & set(it["headers"])
        over_cols = len(cur) >= BATCH_COLUMNS
        over_lb = max(cur_lb, it["lookback"]) > LOOKBACK_CAP
        if cur and (clash or over_cols or over_lb):
            batches.append(cur)
            cur, cur_heads, cur_lb = [], set(), 0
        cur.append(it)
        cur_heads |= set(it["headers"])
        cur_lb = max(cur_lb, it["lookback"])
    if cur:
        batches.append(cur)

    return [{"index": i,
             "families": sorted({x["family"] for x in b}),
             "columns": [_column(x["spec"]).wire() for x in b],
             "predictedHeaders": [h for x in b for h in x["headers"]],
             "lookback": max(x["lookback"] for x in b)}
            for i, b in enumerate(batches)]


def cmd_plan(_argv):
    batches = build()
    OUT.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(batches, indent=1), encoding="utf-8")
    fams = {f for b in batches for f in b["families"]}
    cols = sum(len(b["columns"]) for b in batches)
    print(f"{len(fams)} families, {cols} distinct columns -> {len(batches)} batches")
    for b in batches:
        print(f"  batch {b['index']}: {len(b['columns']):>2} cols, "
              f"{len(b['predictedHeaders']):>2} headers, lookback {b['lookback']}")
    print(f"wrote {PLAN}")
    return 0


def cmd_show(argv):
    b = json.loads(PLAN.read_text(encoding="utf-8"))[int(argv[0])]
    print(json.dumps([{"kind": "custom", "title": f"families {b['index']}",
                       "benchmarkTicker": None, "columns": b["columns"]}]))
    return 0


def cmd_record(argv):
    i, row = argv[0], argv[1]
    headers = [h.strip() for h in row.strip().strip("|").split("|")]
    seen = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}
    seen[str(int(i))] = headers
    SEEN.write_text(json.dumps(seen, indent=1), encoding="utf-8")
    print(f"batch {i}: recorded {len(headers)} headers")
    return 0


def cmd_ingest(_argv):
    plan = {b["index"]: b for b in json.loads(PLAN.read_text(encoding="utf-8"))}
    seen = json.loads(SEEN.read_text(encoding="utf-8")) if SEEN.exists() else {}
    ok, problems = 0, []
    covered = set()
    for k, actual in sorted(seen.items(), key=lambda kv: int(kv[0])):
        b = plan[int(k)]
        act = [h for h in actual if h != "coin"]
        covered |= set(b["families"])
        if act == b["predictedHeaders"]:
            ok += 1
            continue
        problems.append((int(k),
                         [h for h in b["predictedHeaders"] if h not in act],
                         [h for h in act if h not in b["predictedHeaders"]]))
    total_fams = {f for b in plan.values() for f in b["families"]}
    print(f"batches rendered : {len(seen)} of {len(plan)}")
    print(f"batches exact    : {ok}")
    print(f"families covered : {len(covered)} of {len(total_fams)}")
    for i, missing, extra in problems:
        print(f"\n  batch {i}  families={plan[i]['families']}")
        if missing:
            print(f"    predicted, absent live : {missing}")
        if extra:
            print(f"    live, not predicted    : {extra}")
    return 1 if problems else 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    return {"plan": cmd_plan, "show": cmd_show,
            "record": cmd_record, "ingest": cmd_ingest}[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
