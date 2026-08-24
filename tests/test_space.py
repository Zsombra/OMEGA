"""The custom-column design space, enumerated from the extracted corpus.

The counts pinned here are the whole point: chaining is capped at two stages
(composition_rules.chaining.stages), which is what makes the space finite and
countable rather than open-ended.
"""
from __future__ import annotations

import csv
from pathlib import Path

from omega.contract import DERIVED_DIR, load
from omega.space import (
    ColumnShape, enumerate_shapes, header_cost, platform_used, query,
)

ROOT = Path(__file__).resolve().parents[1]


def _matrix_rows():
    with (DERIVED_DIR / "composability_matrix.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_matrix_is_the_full_metric_by_transform_grid():
    rows = _matrix_rows()
    assert len(rows) == 1376
    assert len({r["metric"] for r in rows}) == 86
    assert len({r["transform"] for r in rows}) == 16


def test_structural_shape_count_is_488():
    """322 legal atoms + 166 chained forms. Chaining stops at two stages."""
    shapes = enumerate_shapes()
    atoms = [s for s in shapes if s.chained is None]
    chained = [s for s in shapes if s.chained is not None]
    assert len(atoms) == 322
    assert len(chained) == 166
    assert len(shapes) == 488


def test_enumeration_agrees_with_the_matrix_on_which_atoms_are_legal():
    """The enumeration must not invent or drop an atom the corpus disagrees with."""
    from_matrix = {(r["metric"], r["transform"])
                   for r in _matrix_rows() if r["legal"] == "yes"}
    from_code = {(s.metric, s.transform)
                 for s in enumerate_shapes() if s.chained is None}
    assert from_code == from_matrix


def test_chain_successors_split_42_and_10():
    """42 atoms take the 3 general successors; 10 also take rank."""
    shapes = enumerate_shapes()
    by_atom: dict[tuple[str, str], set[str]] = {}
    for s in shapes:
        if s.chained:
            by_atom.setdefault((s.metric, s.transform), set()).add(s.chained)
    three = [k for k, v in by_atom.items() if v == {"trajectory", "aggregate", "efficiency"}]
    four = [k for k, v in by_atom.items()
            if v == {"trajectory", "aggregate", "efficiency", "rank"}]
    assert len(three) == 42
    assert len(four) == 10


def test_expanding_operands_and_orderings_gives_2200():
    assert len(enumerate_shapes(expand_operands=True)) == 2200


def test_chained_rank_expands_over_its_own_ordering_axis():
    """chainedRankOrderings is separate from the metric's own rankOrderings.

    Missing this axis undercounts the space by 78. The 10 rank-chain atoms carry
    [hi, lo, far, near] and expand to 104 forms once spread operands multiply in.
    """
    expanded = enumerate_shapes(expand_operands=True)
    rank_chains = [s for s in expanded if s.chained == "rank"]
    assert len(rank_chains) == 104
    assert {s.ordering for s in rank_chains} == {"hi", "lo", "far", "near"}


def test_expansion_produces_no_duplicate_rows():
    expanded = enumerate_shapes(expand_operands=True)
    assert len(expanded) == len(set(expanded))


def test_expansion_never_loses_a_shape():
    """Every structural shape must survive expansion under some operand/ordering."""
    plain = {(s.metric, s.transform, s.chained) for s in enumerate_shapes()}
    wide = {(s.metric, s.transform, s.chained)
            for s in enumerate_shapes(expand_operands=True)}
    assert plain == wide


def test_shape_converts_to_a_validatable_column():
    shape = ColumnShape(metric="EMA5", transform="spread",
                        chained="trajectory", operand="EMA13", ordering=None)
    col = shape.to_column()
    assert col.metric == "EMA5"
    assert col.transformId == "spread"
    assert col.chainedTransformId == "trajectory"
    assert col.inputs is not None and col.inputs[0].metric == "EMA13"
    assert col.timeframe.rel == "anchor"


# --- querying the space -----------------------------------------------------

def test_only_trajectory_fans_out():
    """composition_rules.fanOut: every other transform emits exactly one header."""
    plain = ColumnShape(metric="RSI14", transform="value")
    traj = ColumnShape(metric="RSI14", transform="trajectory")
    assert header_cost(plain) == 1
    assert header_cost(traj, window=4) == 5      # 4 slots + _trend
    assert header_cost(traj, window=8) == 9


def test_platform_used_pairs_come_from_the_shipped_templates():
    used = platform_used()
    assert used, "platform templates must yield at least one (metric, transform) pair"
    assert all(isinstance(p, tuple) and len(p) == 2 for p in used)


def test_query_filters_by_family():
    want = {m for m, mm in load().metrics.items() if mm.family == "volumeFlow"}
    got = query(family="volumeFlow")
    assert got
    assert {s.metric for s in got} == want


def test_query_by_max_headers_excludes_fan_out():
    cheap = query(max_headers=1)
    assert cheap
    assert all("trajectory" not in (s.transform, s.chained) for s in cheap)


def test_query_can_isolate_what_the_platform_never_uses():
    """The 'what haven't I thought of' question, answered against shipped templates."""
    unused = query(platform_uses=False)
    used = query(platform_uses=True)
    assert unused and used
    assert not ({(s.metric, s.transform) for s in used}
                & {(s.metric, s.transform) for s in unused})
    assert len(unused) + len(used) == 488


def test_query_with_no_filters_is_the_whole_space():
    assert len(query()) == 488
    assert len(query(expand_operands=True)) == 2200
