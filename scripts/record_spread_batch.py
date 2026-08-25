"""Verify a spread-sweep render against prediction, then record it.

Large renders overflow the inline tool-result limit and are written to a file instead.
That is useful rather than annoying: it means the response can be checked by script
instead of by eye, so a 320-column batch costs no more to verify than a 32-column one.

The check is exact and ordered: the headers the platform returned must equal the headers
omega.fanout.outputs_for predicted for the shapes that were sent, in the same order.
Nothing is recorded unless that holds, so the cache can never claim a pair was confirmed
when it was not.

    python -m scripts.record_spread_batch <result-file> <n_sections> <batch_no>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from omega import contract as C
from omega.fanout import outputs_for
from scripts.spread_sweep import plan

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/contract/columns/_spread_sweep_2026-08-26.json"


def main() -> int:
    result_file, n_sections, batch_no = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    c = C.load()

    payload = json.loads(Path(result_file).read_text(encoding="utf-8"))
    returned = [o["header"] for s in payload["conditionColumns"]
                if s["title"].startswith("SS ") for o in s["outputs"]]

    # Flatten across render boundaries: a batch I send by hand may span two of the
    # planner's renders, and slicing plan()[0] alone would silently under-record it.
    sections = [sec for render in plan(c) for sec in render]
    shapes = [s for sec in sections[:n_sections] for s in sec]
    predicted = [o.header for s in shapes for o in outputs_for(s.to_column(), c)]

    if returned != predicted:
        missing = sorted(set(predicted) - set(returned))
        extra = sorted(set(returned) - set(predicted))
        print(f"MISMATCH - nothing recorded.\n  sent {len(shapes)} shapes expecting "
              f"{len(predicted)} headers, got {len(returned)}")
        if missing:
            print(f"  predicted but absent ({len(missing)}): {missing[:12]}")
        if extra:
            print(f"  returned but unpredicted ({len(extra)}): {extra[:12]}")
        if not missing and not extra:
            print("  same set, different ORDER - the platform reordered the columns")
        return 1

    rec = json.loads(CACHE.read_text(encoding="utf-8"))
    if any(b["batch"] == batch_no for b in rec["batches"]):
        print(f"batch {batch_no} already recorded - refusing to double-count")
        return 1
    rec["batches"].append({
        "batch": batch_no, "sections": n_sections, "columns": len(shapes),
        "headers": len(predicted), "mismatches": 0,
        "budget": json.dumps(payload["budgetUsage"]),
        "confirmed": sorted(predicted),
    })
    CACHE.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")

    total = sum(b["columns"] for b in rec["batches"])
    print(f"batch {batch_no}: {len(shapes)} columns, {len(predicted)} headers, "
          f"0 mismatches (exact ordered match)")
    print(f"  budget: {payload['budgetUsage']['estimatedTokens']}")
    print(f"  swept so far: {total} of 1712")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
