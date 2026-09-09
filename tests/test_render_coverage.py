"""Guards the two bugs that made me report live-render coverage wrong twice.

Both were edge cases in a throwaway measurement, and both produced a confident number:

  1. Unexpanded `spread` shapes have no operand, so outputs_for emits the placeholder
     header "ADX_?_spread". Scoring those against real rendered headers counts every
     spread uncovered no matter what was rendered -> "61% covered, 188 untested".
  2. Reading only _sweep_seen.json and concluding no spread had ever been rendered.
     Six other caches hold renders and 27 spread headers sit in them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega import contract as C
from omega.fanout import outputs_for
from omega.space import ColumnShape, enumerate_shapes
from scripts.render_coverage import (
    QUARANTINED, SEEN_FILES, coverage, is_placeholder, rendered_headers,
)

# Operand-expanded spread shapes: 1807, then 1743 after rankableSpreadOperands, then
# 1386 after the series-chain operand rule, then 8190 when the corpus was refreshed to
# the 144-metric roster on 2026-09-09 - spread expands over its operand pool, and the
# price-unit pool alone widened from 17 to 43 members.
EXPANDED_SPREAD_SHAPES = 8190


@pytest.fixture(scope="module")
def contract():
    return C.load()


def test_unexpanded_spread_header_is_a_placeholder(contract):
    """Bug 1's root cause, stated as a fact so the skip in coverage() stays justified."""
    shape = ColumnShape("ADX", "spread")
    assert shape.operand is None
    headers = [o.header for o in outputs_for(shape.to_column(), contract)]
    assert headers == ["ADX_?_spread"]
    assert "?" in headers[0], (
        "an unexpanded spread no longer emits a placeholder; the skip in "
        "scripts.render_coverage.coverage() may now be hiding real shapes")


def test_expanded_spread_header_names_both_sides(contract):
    expanded = [s for s in enumerate_shapes(expand_operands=True, contract=contract)
                if s.transform == "spread"]
    assert len(expanded) == EXPANDED_SPREAD_SHAPES
    shape = next(s for s in expanded if s.metric == "ADX" and s.operand == "RSI14")
    assert [o.header for o in outputs_for(shape.to_column(), contract)] == ["ADX_RSI14_spread"]


def test_rendered_headers_spans_every_cache():
    """Bug 2: a single cache is not the record of what was rendered."""
    assert len(SEEN_FILES) == 12   # 11 until the 2026-09-09 sweep added its own cache
    seen = rendered_headers()
    assert len(seen) > 900
    # The point of this test is bug 2 itself: NO single cache is the record. Assert that
    # directly rather than pinning a count, which the ongoing spread sweep keeps moving.
    import json
    from scripts.render_coverage import CACHE, _walk
    per_file = {}
    for name in SEEN_FILES:
        one = set()
        _walk(json.loads((CACHE / name).read_text(encoding="utf-8")), one)
        per_file[name] = {h for h in one if h.endswith("_spread")}
    spreads = {h for h in seen if h.endswith("_spread")}
    assert len(spreads) > max(len(v) for v in per_file.values()), (
        "the union of spread headers must exceed every individual cache - reading one "
        "cache understates coverage, which is how this was got wrong the first time")
    assert sum(1 for v in per_file.values() if v) >= 3, (
        "spread renders live in several caches: _family_seen, _renders_tfvariants and "
        "the sweep file")


def test_no_plan_file_is_counted_as_a_render():
    """A plan is an intention. Counting one would inflate coverage silently."""
    assert not [f for f in SEEN_FILES if "_plan" in f]



# --- scoping the coverage claim to what was actually rendered -------------------------
# The live sweep ran against the 86-metric roster of 2026-08-24. The corpus is now 144
# (contract 54.1.0). Shapes touching a metric added since have never been rendered, so
# they are counted separately instead of being dropped from the denominator - a shape
# that has not been rendered is not covered by declaring it out of scope.
_REC = json.loads((Path(__file__).resolve().parents[1]
                   / "data/derived/unmeasured_metrics.json").read_text(encoding="utf-8"))
UNMEASURED = set(_REC["unmeasured"])
RENDERED_ROSTER = set(_REC["renderedMechanisms"]["roster"])
RENDERED_MECHANISMS = _REC["renderedMechanisms"]["mechanisms"]


def _is_measured(shape) -> bool:
    """True when the sweep could actually have rendered this shape.

    Metric alone is not enough: `aggregate` became a top-level transform on 40 metrics
    that WERE in the rendered roster, so ADX x aggregate is a mechanism the sweep never
    saw even though ADX was swept. The chained successor and the spread operand have to
    have existed then too.
    """
    key = f"{shape.metric}|{shape.transform}"
    if key not in RENDERED_MECHANISMS:
        return False
    if shape.chained and shape.chained not in RENDERED_MECHANISMS[key]:
        return False
    return not (shape.operand and shape.operand not in RENDERED_ROSTER)


def _split(expand, contract):
    """(covered, uncovered_measured, uncovered_unmeasured) over renderable shapes."""
    cov, unc, _ = coverage(expand, contract)
    measured = [s for s in unc if _is_measured(s)]
    unmeasured = [s for s in unc if not _is_measured(s)]
    return cov, measured, unmeasured

def test_coverage_partitions_the_space(contract):
    """The partition itself must hold at any roster size: covered + uncovered is the whole
    renderable space, and the by-transform tally accounts for every uncovered shape."""
    for expand in (False, True):
        cov, unc, byt = coverage(expand, contract)
        assert cov + len(unc) == len(
            [s for s in enumerate_shapes(expand_operands=expand, contract=contract)
             if not is_placeholder(s) and (s.metric, s.transform) not in QUARANTINED])
        assert sum(byt.values()) == len(unc)


def test_structural_coverage_is_complete(contract):
    """Every metric x transform mechanism has been rendered live at least once.

    True on the 86-metric roster (301 shapes), briefly false when the 2026-09-09 refresh
    took the corpus to 144, and true again after the sweep of that date rendered the 7,840
    shapes the older caches had never seen. 675 now.
    """
    cov, unc, _ = coverage(False, contract)
    assert (cov, len(unc)) == (675, 0), (
        "every metric x transform mechanism has been rendered live at least once")


def test_live_coverage_is_complete(contract):
    """COMPLETED 2026-08-26 on the 86-metric roster, RE-COMPLETED 2026-09-09 on 144.

    Every operand-expanded shape omega can emit has been rendered against the live
    platform at least once, and every header matched omega.fanout.outputs_for exactly.
    The 2026-09-09 sweep rendered the 7,840 shapes the corpus refresh had put out of
    reach: 13,572 headers minted, ZERO refusals and ZERO predicted-but-not-rendered,
    which is the strongest agreement between omega and the platform measured so far.
    Run record: data/audit/coverage_sweep_2026-09-09.json.

    This is the strongest form of the claim the sweep set out to make, and it is only
    meaningful because the denominator is honest: the 357 shapes the platform refuses
    were REMOVED from the space rather than excused from the count. A shape that cannot
    render is not covered by declaring it out of scope.
    """
    cov, unc, byt = coverage(True, contract)
    assert (cov, len(unc)) == (8979, 0), (
        "live coverage regressed - a shape is enumerated that has never been rendered")
    assert not byt
