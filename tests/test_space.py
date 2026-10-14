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
    """156 x 16 as of 2026-09-21 (contract 61.2.0). Was 144 x 16 = 2304 on 2026-09-09,
    86 x 16 = 1376 on 2026-08-24 and 135 metrics on 2026-09-05; the roster is the
    platform's to grow, so these track it."""
    rows = _matrix_rows()
    # 171 x 16 since the re-extraction at 108.4.0, 2026-10-13 - still 16 transforms: the served list swapped bandTouch for
    # levelInteraction (data/contract/vocabulary/_shared.json, list_strategy_vocabulary)
    # 177 x 16 since the re-extraction at 110.2.0, 2026-10-14 (data/contract/metrics/_moves_110.json): MACD, PPO, KC_MID out, nine in.
    assert len(rows) == 2832
    assert len({r["metric"] for r in rows}) == 177
    assert len({r["transform"] for r in rows}) == 16
    assert "levelInteraction" in {r["transform"] for r in rows} and "bandTouch" not in {r["transform"] for r in rows}


def test_structural_shape_count_is_1018():
    """619 legal atoms + 301 chained forms = 920 since 2026-10-12: the 61.2.0 corpus less the 62 `bandTouch`
    atoms that left at v100 (the 108 write schema's transformId enum has no `bandTouch`; omega.contract derives
    the retirement and drops it from every Metric.transforms). bandTouch never chained, so the 301 are unchanged.

    It was 681 + 301 = 982 at contract 61.2.0.

    Was 663 + 355 = 1018 at 54.1.0 (name kept for history; the number moved). Atoms grew
    12 -> 681 (663 + 18): the twelve new metrics contribute 45 atoms of their own (eleven
    at 4 transforms each plus PRIOR_TPO_SHAPE at 1), while PDH, PDL and the seven pivots
    each shed 3 atoms (trajectory, aggregate, efficiency) going candle -> timeless,
    -27. 45 - 27 = 18, matching the corpus's own 663 -> 681.

    Chained forms FELL despite atoms growing, because the same nine metrics also lost
    `chainSuccessors: [trajectory, aggregate, efficiency]` on their `distance` and
    `spread` atoms - two chain-bearing atoms per metric, 18 removed from the
    "three general successors" bucket (93 -> 75 below), each worth 3 chained forms:
    18 x 3 = 54 fewer chained shapes (355 -> 301). The "four successors" (+rank) bucket
    is untouched (19 -> 19) because none of the nine ever chained spread into rank."""
    shapes = enumerate_shapes()
    atoms = [s for s in shapes if s.chained is None]
    chained = [s for s in shapes if s.chained is not None]
    # 670 + 229 = 899 since the re-extraction at 108.4.0, 2026-10-13. Atoms: 619 + 42 (the 15 new metrics' cells)
    # + 41 (levelInteraction on existing levels) - 30 (efficiency left oscillators/ratios) - 1 (a maxShare) - 1
    # (SPOT_CVD's spread) = 670. Chained: efficiency left every distance/spread chain, 301 -> 229. 920 on 2026-10-12.
    # 705 + 242 = 947 since the re-extraction at 110.2.0, 2026-10-14 (data/contract/metrics/_moves_110.json): atoms 670 - 18 (MACD 5, PPO 6, KC_MID 7) + 53 (the nine new metrics);
    # chained 229 -> 242 (the new metrics' distance/spread chains, less KC_MID's).
    assert len(atoms) == 705
    assert len(chained) == 242
    assert len(shapes) == 947


def test_enumeration_agrees_with_the_matrix_on_which_atoms_are_legal():
    """The enumeration must not invent or drop an atom the corpus disagrees with. The matrix is the 61.2.0
    extraction's record and keeps `bandTouch`; the space has dropped what the served enum retired since."""
    retired = set(load().retired_transforms)
    from_matrix = {(r["metric"], r["transform"])
                   for r in _matrix_rows() if r["legal"] == "yes" and r["transform"] not in retired}
    from_code = {(s.metric, s.transform)
                 for s in enumerate_shapes() if s.chained is None}
    assert from_code == from_matrix


def test_chain_successors_split_93_and_19():
    """75 atoms take the 3 general successors; 19 also take rank, at contract 61.2.0.

    Was 93/19 at 54.1.0 (name kept for history), 42/10 on the 86-metric August roster.
    The three-successor bucket lost exactly PDH, PDL and the seven pivots' `distance`
    and `spread` atoms (9 metrics x 2 = 18) when those nine went candle -> timeless and
    dropped chainSuccessors from both: 93 - 18 = 75. The four-successor (+rank) bucket
    is untouched at 19 - none of the nine ever offered a rank chain."""
    shapes = enumerate_shapes()
    by_atom: dict[tuple[str, str], set[str]] = {}
    for s in shapes:
        if s.chained:
            by_atom.setdefault((s.metric, s.transform), set()).add(s.chained)
    three = [k for k, v in by_atom.items() if v == {"trajectory", "aggregate", "efficiency"}]
    four = [k for k, v in by_atom.items()
            if v == {"trajectory", "aggregate", "efficiency", "rank"}]
    # since the re-extraction at 108.4.0, 2026-10-13 the general successors are TWO (trajectory, aggregate): 83 atoms take
    # them, 21 also take rank. Was 75 x {trajectory, aggregate, efficiency} and 19 with rank at 61.2.0.
    two = [k for k, v in by_atom.items() if v == {"trajectory", "aggregate"}]
    two_rank = [k for k, v in by_atom.items() if v == {"trajectory", "aggregate", "rank"}]
    assert (len(three), len(four)) == (0, 0)
    # 91 and 20 since the re-extraction at 110.2.0, 2026-10-14 (data/contract/metrics/_moves_110.json): KC_MID's distance -> rank left with it.
    assert len(two) == 91
    assert len(two_rank) == 20


def test_expanding_operands_and_orderings_gives_8999():
    """8,429 at contract 61.2.0 (name kept for history - was 8999 at 54.1.0, 2,200 until
    2026-08-26, when 64 illegal shapes came out of the enumeration).

    The 570-shape drop nets two opposing moves. Unchained spread shapes grew (every
    metric's spreadOperands pool widened to include the twelve new metrics, and eleven
    of those twelve offer their own unchained spread atom). Chained spread shapes fell
    much further: PDH, PDL and the seven pivots no longer chain spread into a series at
    all (they lost the chainSuccessors), AND every one of those nine plus the twelve new
    metrics is timeless, so any OTHER metric's spread chained into aggregate/trajectory/
    efficiency now refuses whenever the operand is one of these 21 names (see
    tests/test_spread_chain_operand.py - a series chain needs a candle-backed operand).
    Net effect verified directly against the corpus: -570.

    Chaining spread -> rank narrows the legal operand set via the contract's
    `rankableSpreadOperands`; the enumerator paired the chain with all of spread's
    operands instead. omega's own validator had always refused those 64 - only
    enumerate_shapes disagreed. See tests/test_space_validate_agreement.py.
    """
    # 8,575 since the re-extraction at 108.4.0, 2026-10-13; 8,367 on 2026-10-12 (bandTouch retired).
    # 9,103 since the re-extraction at 110.2.0, 2026-10-14 (data/contract/metrics/_moves_110.json).
    assert len(enumerate_shapes(expand_operands=True)) == 9103


def test_chained_rank_expands_over_its_own_ordering_axis():
    """chainedRankOrderings is separate from the metric's own rankOrderings.

    Missing this axis undercounts the space. The rank-chain atoms carry
    [hi, lo, far, near] and expand to 40 forms - 104 until 2026-08-26, when the
    rankableSpreadOperands narrowing was applied and 64 illegal pairings were dropped.
    """
    expanded = enumerate_shapes(expand_operands=True)
    rank_chains = [s for s in expanded if s.chained == "rank"]
    assert len(rank_chains) == 80      # 76 at 61.2.0; the swing fractals +8 (108.4); KC_MID's -4 at 110.2.0 (2026-10-14)
    assert {s.ordering for s in rank_chains} == {"hi", "lo", "far", "near"}


def test_expansion_produces_no_duplicate_rows():
    expanded = enumerate_shapes(expand_operands=True)
    assert len(expanded) == len(set(expanded))


# Structural shapes that legally enumerate but have NO legal expansion. Measured
# 2026-09-09, not assumed: RVOL gained the `spread` transform (the August corpus noted it
# had none), and its whole operand pool is the two ratio-unit regime metrics
# REGIME_VOL_ATR_RATIO and REGIME_VOL_BBW_RATIO - both TIMELESS. Chaining a spread whose
# operand is timeless is refused (REPORT_COLUMN_CHAIN_UNSUPPORTED, see
# tests/test_spread_chain_operand.py), so every expansion of RVOL x spread x <successor>
# is illegal and the shape drops out. The unchained RVOL x spread survives.
EXPANSION_DEAD_ENDS = {
    ("RVOL", "spread", "trajectory"),
    ("RVOL", "spread", "aggregate"),
    # ("RVOL", "spread", "efficiency") left with efficiency itself from every spread chain (re-extraction at 108.4.0, 2026-10-13)
}


def test_expansion_loses_only_the_measured_dead_ends():
    """Every structural shape survives expansion EXCEPT the measured dead ends above.

    Held with no exceptions on the 86-metric August roster. If this set grows, a new
    metric has been given a transform whose only operands cannot carry it - which is
    worth knowing rather than papering over.
    """
    plain = {(s.metric, s.transform, s.chained) for s in enumerate_shapes()}
    wide = {(s.metric, s.transform, s.chained)
            for s in enumerate_shapes(expand_operands=True)}
    assert plain - wide == EXPANSION_DEAD_ENDS
    assert wide - plain == set()


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
    assert len(unused) + len(used) == 947


def test_query_with_no_filters_is_the_whole_space():
    assert len(query()) == 947                       # 899 at 108.4.0
    assert len(query(expand_operands=True)) == 9103   # 8575 at 108.4.0
