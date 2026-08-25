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
    assert len(expanded) == 1743      # 1807 before the rankableSpreadOperands fix
    shape = next(s for s in expanded if s.metric == "ADX" and s.operand == "RSI14")
    assert [o.header for o in outputs_for(shape.to_column(), contract)] == ["ADX_RSI14_spread"]


def test_rendered_headers_spans_every_cache():
    """Bug 2: a single cache is not the record of what was rendered."""
    assert len(SEEN_FILES) == 10
    seen = rendered_headers()
    assert len(seen) > 900
    spreads = {h for h in seen if h.endswith("_spread")}
    assert len(spreads) == 27, (
        "spread renders are recorded in _family_seen.json and _renders_tfvariants.json, "
        "not in _sweep_seen.json - reading one cache understates coverage")


def test_no_plan_file_is_counted_as_a_render():
    """A plan is an intention. Counting one would inflate coverage silently."""
    assert not [f for f in SEEN_FILES if "_plan" in f]


def test_coverage_partitions_the_space(contract):
    for expand, total in ((False, 301), (True, 2116)):
        cov, unc, byt = coverage(expand, contract)
        assert cov + len(unc) == total
        assert sum(byt.values()) == len(unc)


def test_recorded_coverage_numbers(contract):
    """Pinned so a change in the space or the caches is visible rather than silent."""
    cov, unc, byt = coverage(False, contract)
    assert (cov, len(unc)) == (301, 0), (
        "structural coverage is complete: every metric x transform mechanism has been "
        "rendered live at least once")

    cov, unc, byt = coverage(True, contract)
    assert (cov, len(unc)) == (404, 1712)
    assert set(byt) == {"spread"}, (
        "spread is the ONLY remaining gap - every rank ordering and distance chain was "
        "swept on 2026-08-26")
    assert byt["spread"] == 1712, "the risk-relevant gap: untested (base, operand) pairs"
