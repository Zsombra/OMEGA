"""Emit the render payloads that sweep every untested spread (base, operand) pair.

1,712 pairs remain unrendered - the whole of the remaining live-coverage gap. They are
batched here rather than sampled, because the risk being tested is a narrowing rule the
contract does not publish, and a sample cannot rule that out for the pairs it skips.

Two measurements set the batch size, both taken live rather than assumed:

  sectionColumns is a PER-SECTION cap, not a global one. Two sections of 3 columns
  reports "used: 3, cap: 32" - the max, not the sum. So a render holds up to 32 sections
  x 32 columns = 1,024 columns. (omega/validate.py already enforced it per-section and
  doc 04 already said "columns per section"; the doubt was mine.)

  estimatedTokens is what actually binds: 16,000, and a header costs ~39 of them with a
  single ticker. Chained trajectories fan out to 5 headers per column, so batching counts
  HEADERS, not columns.

    python -m scripts.spread_sweep            # summarise the batch plan
    python -m scripts.spread_sweep 3          # print render 3's sections JSON
"""
from __future__ import annotations

import json
import sys
from collections import Counter

from omega import contract as C
from omega.fanout import outputs_for
from scripts.render_coverage import coverage

MAX_COLUMNS_PER_SECTION = 32
MAX_SECTIONS = 32
HEADER_BUDGET = 300          # ~11.7k of the 16k estimated-token cap, leaving margin


def untested(contract):
    _, uncovered, _ = coverage(expand_operands=True, contract=contract)
    spread = [s for s in uncovered if s.transform == "spread"]
    # Group by chain so each render is homogeneous and its header cost is predictable.
    order = {"none": 0, "rank": 1, "aggregate": 2, "efficiency": 3, "trajectory": 4}
    return sorted(spread, key=lambda s: (order.get(s.chained or "none", 9),
                                         s.metric, s.operand or ""))


def plan(contract):
    """[[section, ...], ...] - one entry per render."""
    renders, sections, section, seen_here, headers_here = [], [], [], set(), 0
    for shape in untested(contract):
        hs = [o.header for o in outputs_for(shape.to_column(), contract)]
        # A duplicate header inside ONE section silently drops the whole section from
        # conditionColumns, so split on collision as well as on count.
        if len(section) >= MAX_COLUMNS_PER_SECTION or (seen_here & set(hs)):
            sections.append(section)
            section, seen_here = [], set()
        if headers_here + len(hs) > HEADER_BUDGET or len(sections) >= MAX_SECTIONS:
            if section:
                sections.append(section)
            renders.append(sections)
            sections, section, seen_here, headers_here = [], [], set(), 0
        section.append(shape)
        seen_here |= set(hs)
        headers_here += len(hs)
    if section:
        sections.append(section)
    if sections:
        renders.append(sections)
    return renders


def payload(sections, contract, index):
    out = []
    for i, sec in enumerate(sections, 1):
        cols = [s.to_column().wire() | {"timeframe": {"rel": "anchor"}} for s in sec]
        out.append({"kind": "custom", "title": f"Spread sweep {index}.{i}",
                    "benchmarkTicker": None, "columns": cols})
    return out


def main() -> int:
    c = C.load()
    renders = plan(c)
    if len(sys.argv) > 1:
        i = int(sys.argv[1])
        secs = renders[i - 1]
        print(json.dumps(payload(secs, c, i), separators=(",", ":")))
        return 0

    total_shapes = total_headers = 0
    print(f"{len(renders)} renders for {sum(len(s) for r in renders for s in r)} sections\n")
    for i, secs in enumerate(renders, 1):
        shapes = [s for sec in secs for s in sec]
        hdrs = sum(len(outputs_for(s.to_column(), c)) for s in shapes)
        chains = Counter(s.chained or "none" for s in shapes)
        total_shapes += len(shapes)
        total_headers += hdrs
        print(f"  render {i:>2}: {len(secs):>2} sections, {len(shapes):>3} columns, "
              f"{hdrs:>3} headers   {dict(chains)}")
    print(f"\n  totals: {total_shapes} columns, {total_headers} headers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
