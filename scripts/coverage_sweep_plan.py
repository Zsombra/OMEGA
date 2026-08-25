"""Plan the renders that would close the live-coverage gap, cheapest first.

scripts/render_coverage.py says what has never been rendered. This turns that into
batches that respect the platform's per-render caps, and prints the exact `sections` JSON
to hand to preview_strategy_report.

Caps enforced (from data/derived, verified live): 32 columns per section, 32 sections,
columnLookback = max(window + offset) <= 32, 16k estimated tokens. Duplicate headers
inside one section are the silent killer - the platform renders both and then omits the
whole section from conditionColumns - so batching splits on header collision, not just
on count.

    python -m scripts.coverage_sweep_plan               # bounded gaps: rank + distance
    python -m scripts.coverage_sweep_plan spread 64     # a stratified spread sample
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

from omega import contract as C
from omega.fanout import outputs_for
from scripts.render_coverage import coverage

MAX_COLUMNS = 32


def batches(shapes, contract):
    """Greedy pack into sections, splitting whenever a header would collide."""
    out, current, seen = [], [], set()
    for s in shapes:
        headers = [o.header for o in outputs_for(s.to_column(), contract)]
        if len(current) >= MAX_COLUMNS or seen & set(headers):
            out.append(current)
            current, seen = [], set()
        current.append(s)
        seen |= set(headers)
    if current:
        out.append(current)
    return out


def stratify(shapes, limit, contract):
    """Spread has 1,776 untested pairs. Cover every base-family x operand-family
    combination once before repeating any, so a sample of 64 still touches every
    mechanism rather than 64 variants of the same one."""
    def fam(metric):
        m = contract.metric(metric)
        return (m.timeframe_mode, m.unit)

    buckets = defaultdict(list)
    for s in shapes:
        buckets[(fam(s.metric), fam(s.operand) if s.operand else None)].append(s)
    picked, keys = [], sorted(buckets, key=str)
    while len(picked) < limit and any(buckets[k] for k in keys):
        for k in keys:
            if buckets[k] and len(picked) < limit:
                picked.append(buckets[k].pop(0))
    return picked


def main() -> int:
    c = C.load()
    which = sys.argv[1] if len(sys.argv) > 1 else "bounded"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 64

    _, uncovered, _ = coverage(expand_operands=True, contract=c)
    if which == "spread":
        target = stratify([s for s in uncovered if s.transform == "spread"], limit, c)
        label = f"stratified spread sample ({limit} of 1,776)"
    else:
        target = [s for s in uncovered if s.transform != "spread"]
        label = "bounded gaps: every untested rank ordering and distance variant"

    packed = batches(target, c)
    print(f"# {label}: {len(target)} columns in {len(packed)} render(s)\n")
    for i, batch in enumerate(packed, 1):
        cols = [s.to_column().wire() | {"timeframe": {"rel": "anchor"}} for s in batch]
        section = [{"kind": "custom", "title": f"Coverage {which} {i}",
                    "benchmarkTicker": None, "columns": cols}]
        headers = [o.header for s in batch for o in outputs_for(s.to_column(), c)]
        print(f"## batch {i}: {len(cols)} columns, {len(headers)} headers")
        print(json.dumps(section, separators=(",", ":")))
        print(f"# expect: {sorted(headers)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
