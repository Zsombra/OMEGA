"""Guards the two bugs that made me report live-render coverage wrong twice.

Both were edge cases in a throwaway measurement, and both produced a confident number:

  1. Unexpanded `spread` shapes have no operand, so outputs_for emits the placeholder
     header "ADX_?_spread". Scoring those against real rendered headers counts every
     spread uncovered no matter what was rendered -> "61% covered, 188 untested".
  2. Reading only _sweep_seen.json and concluding no spread had ever been rendered.
     Six other caches hold renders and 27 spread headers sit in them.
"""
from __future__ import annotations

import pytest

from omega import contract as C
from omega.fanout import outputs_for
from omega.space import ColumnShape, enumerate_shapes
from scripts.render_coverage import SEEN_FILES, coverage, rendered_headers


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
    assert len(expanded) == 1386      # 1807, then 1743 after rankableSpreadOperands,
                                      # then 1386 after the series-chain operand rule
    shape = next(s for s in expanded if s.metric == "ADX" and s.operand == "RSI14")
    assert [o.header for o in outputs_for(shape.to_column(), contract)] == ["ADX_RSI14_spread"]


def test_rendered_headers_spans_every_cache():
    """Bug 2: a single cache is not the record of what was rendered."""
    assert len(SEEN_FILES) == 11
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


def test_coverage_partitions_the_space(contract):
    for expand, total in ((False, 301), (True, 1759)):
        cov, unc, byt = coverage(expand, contract)
        assert cov + len(unc) == total
        assert sum(byt.values()) == len(unc)


def test_structural_coverage_is_complete(contract):
    cov, unc, _ = coverage(False, contract)
    assert (cov, len(unc)) == (301, 0), (
        "every metric x transform mechanism has been rendered live at least once")


def test_spread_is_the_only_remaining_gap(contract):
    """The spread sweep is incremental, so this asserts SHAPE and DIRECTION, not a frozen
    number - a pinned count would fail on every batch and teach us to edit it blindly."""
    cov, unc, byt = coverage(True, contract)
    assert cov + len(unc) == 1759
    assert set(byt) <= {"spread"}, (
        "every rank ordering and distance chain was swept on 2026-08-26; anything else "
        "appearing here is a regression, not sweep progress")
    assert cov >= 948, "live coverage must not go backwards"
    assert len(unc) <= 811, "untested spread pairs must not grow"
