"""The custom-column design space, enumerated from the extracted corpus.

WHY THIS IS FINITE
------------------
`composition_rules.chaining.stages` is 2. A column is one metric, one transform,
and at most one chained successor - so the structural space can be counted rather
than sampled:

    1376 metric x transform pairs
     322 legal atoms
     166 chained forms   (42 atoms x 3 general successors, 10 x 4 including rank)
     488 structural shapes

Expanding spread operands and rank orderings gives 2200 concrete forms.

PARAMETERS ARE NOT ENUMERATED, DELIBERATELY
-------------------------------------------
`window` is 1-64, `offset` 0-64, `bars` is one of two values and `inputs` takes up
to four metrics. Materialising that cross-product would produce millions of rows of
no value. Parameters are axes you vary on a shape you have already chosen - and
their EFFECTIVE values are not guessable, so ask the platform via omega.probe
rather than assuming. `trajectory` defaults to window 4, `efficiency` to 21, and
`bars` to "all", which includes the live forming bar (cookbook trap #1).

Pure local computation - performs no network or MCP calls.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contract import Contract, Metric, load
from .types import Column, Operand, RelTimeframe


@dataclass(frozen=True)
class ColumnShape:
    """One structural point in the space: metric x transform x optional chain."""

    metric: str
    transform: str
    chained: str | None = None
    operand: str | None = None
    ordering: str | None = None

    def to_column(self, timeframe_rel: str = "anchor") -> Column:
        """The authorable Column this shape denotes, with no parameters set."""
        return Column(
            metric=self.metric,
            transformId=self.transform,
            timeframe=RelTimeframe(rel=timeframe_rel),
            chainedTransformId=self.chained,
            ordering=self.ordering,
            inputs=[Operand(metric=self.operand)] if self.operand else None,
        )


def _variants(m: Metric, transform: str, expand: bool) -> list[tuple[str | None, str | None]]:
    """(operand, ordering) pairs for one atom. Exactly one entry when not expanding."""
    if not expand:
        return [(None, None)]
    if transform == "spread" and m.spread_operands:
        return [(o, None) for o in m.spread_operands]
    if transform == "rank" and m.rank_orderings:
        return [(None, o) for o in m.rank_orderings]
    return [(None, None)]


def enumerate_shapes(expand_operands: bool = False,
                     contract: Contract | None = None) -> list[ColumnShape]:
    """Every structural shape in the space.

    `expand_operands=False` gives the 488 structural shapes. `True` enumerates each
    spread operand and rank ordering separately, giving 2200.

    THREE ORDERING AXES, NOT ONE
    ----------------------------
    A `rank` ATOM varies over the metric's `rankOrderings`. A chained `rank` varies
    over the atom's own `chainedRankOrderings`, which the contract publishes
    separately - `EMA13 x distance` carries chainSuccessors [..., "rank"] AND
    chainedRankOrderings [hi, lo, far, near]. Dropping that second axis undercounts
    the space by 78 (2122 instead of 2200), so it is enumerated explicitly below.
    A shape has at most one rank stage, so a single `ordering` field serves both.
    """
    c = contract or load()
    out: list[ColumnShape] = []
    for name, m in c.metrics.items():
        for transform, flags in m.transforms.items():
            for operand, ordering in _variants(m, transform, expand_operands):
                out.append(ColumnShape(name, transform, None, operand, ordering))
                for succ in (flags.get("chainSuccessors") or ()):
                    if succ == "rank" and expand_operands:
                        for o in (flags.get("chainedRankOrderings") or (None,)):
                            out.append(ColumnShape(name, transform, succ, operand, o))
                    else:
                        out.append(ColumnShape(name, transform, succ, operand, ordering))
    return out
