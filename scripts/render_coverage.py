"""How much of the shape space has actually been rendered against the live platform?

This exists because I answered the question twice with a one-liner and got it wrong both
times, in opposite directions:

  1. "300 of 488, 61% covered." Wrong: `outputs_for` on an unexpanded spread emits the
     placeholder header `ADX_?_spread`, which can never match a rendered header, so all
     175 spread structural shapes were counted uncovered BY CONSTRUCTION.
  2. "zero spread headers ever rendered." Wrong: I read only _sweep_seen.json. Six other
     caches hold renders; 27 spread headers live in them.

Both errors were edge cases in a throwaway script. So it is a real script now, with a
test, and it reports BOTH denominators because they answer different questions:

  structural      - is each (metric x transform) mechanism exercised at all?
  operand-expanded - is each concrete (metric x transform x operand) column proven?

The second is the risk-relevant one. A spread's legality depends on the OPERAND as well
as the base (both need a stored bar series), so an untested pair is an untested claim.

    python -m scripts.render_coverage
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from omega import contract as C, space
from omega.fanout import outputs_for

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/contract/columns"

# Caches recording what was actually RENDERED. *_plan.json files are intentions and are
# deliberately excluded - a plan is not a confirmation.
SEEN_FILES = [
    "_family_seen.json", "_sweep_seen.json", "_renders.json", "_renders_chains.json",
    "_renders_collision.json", "_renders_coverage.json", "_renders_infix.json",
    "_renders_tfvariants.json", "_contracts.json", "_coverage_sweep_2026-08-26.json", "_spread_sweep_2026-08-26.json",
]


def _walk(obj, out: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "header" and isinstance(v, str):
                out.add(v)
            else:
                _walk(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, out)
    elif isinstance(obj, str):
        out.add(obj)


def rendered_headers() -> set[str]:
    out: set[str] = set()
    for name in SEEN_FILES:
        _walk(json.loads((CACHE / name).read_text(encoding="utf-8")), out)
    return out


# Declared legal by the contract, INTERNAL_ERROR on every render. They cannot be covered,
# so counting them as a coverage gap overstates the work remaining. See
# sweep_2026-08-24.json['columnSweep']['quarantined'].
QUARANTINED = {(m, "rank") for m in (
    "CROWD_ACC", "CROWD_ACC_LIVE", "CROWD_CAPT", "CROWD_CAPT_LIVE",
    "CROWD_PICK", "CROWD_PICK_LIVE", "CROWD_UPBIAS", "CROWD_UPBIAS_LIVE")}

# Transforms whose header cannot be formed until a parameter the shape does not carry is
# chosen. `spread` needs `operand`; the nearestZone family needs `side`. Both emit a
# placeholder header ("X_?_spread", "zones_None_type") that can never match a render, and
# omega's own validator refuses the column - SIDE_REQUIRED / OPERAND_REQUIRED. Scoring
# them counts a whole family uncovered by construction.
SIDE_REQUIRED = {"nearestZoneType", "nearestZoneRange", "nearestZoneDist",
                 "nearestZoneAge"}


def is_placeholder(shape) -> bool:
    """True when the shape cannot yet form a testable header."""
    if shape.transform == "spread" and shape.operand is None:
        return True
    return shape.transform in SIDE_REQUIRED and getattr(shape, "side", None) is None


def coverage(expand_operands: bool, contract=None):
    """(covered, uncovered_shapes, by_transform), over RENDERABLE, testable shapes."""
    c = contract or C.load()
    seen = rendered_headers()
    covered, uncovered, by_transform = 0, [], Counter()
    for s in space.enumerate_shapes(expand_operands=expand_operands, contract=c):
        if is_placeholder(s) or (s.metric, s.transform) in QUARANTINED:
            continue
        headers = [o.header for o in outputs_for(s.to_column(), c)]
        if headers and all(h in seen for h in headers):
            covered += 1
        else:
            uncovered.append(s)
            by_transform[s.transform] += 1
    return covered, uncovered, by_transform


def main() -> int:
    c = C.load()
    seen = rendered_headers()
    print(f"headers rendered live across {len(SEEN_FILES)} caches: {len(seen)}")
    print(f"  of which spread: {sum(1 for h in seen if h.endswith('_spread'))}\n")
    for expand, label in ((False, "structural   "), (True, "operand-expanded")):
        cov, unc, byt = coverage(expand, c)
        total = cov + len(unc)
        print(f"{label}: {cov}/{total} rendered ({cov/total:.0%}), {len(unc)} never")
        for t, n in byt.most_common():
            print(f"      {t:18s} {n}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
