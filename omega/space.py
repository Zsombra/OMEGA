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

Expanding spread operands and rank orderings gives 1779 concrete forms.

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
from .fanout import outputs_for
from .types import Column, Operand, RelTimeframe

# Chain successors of `spread` that build a SERIES. Chaining into one needs a per-bar
# series on both sides; `rank` reduces to an ordinal instead and is restricted by the
# contract's own rankableSpreadOperands. Mirrors omega.validate.SERIES_CHAINS.
_SERIES_CHAINS = {"aggregate", "trajectory", "efficiency"}


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
        # A rank column with no explicit ordering resolves to "hi", and not every metric
        # offers it - CLOSE_CHANGE allows only ['far', 'near']. Leaving ordering None
        # there emitted a shape omega's own validator refuses. Name the default when it
        # is legal, otherwise the first ordering the metric does offer.
        if transform == "rank" and m.rank_orderings:
            orderings = tuple(m.rank_orderings)
            return [(None, "hi" if "hi" in orderings else orderings[0])]
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
    spread operand and rank ordering separately, giving 1779.

    THREE ORDERING AXES, NOT ONE
    ----------------------------
    A `rank` ATOM varies over the metric's `rankOrderings`. A chained `rank` varies
    over the atom's own `chainedRankOrderings`, which the contract publishes
    separately - `EMA13 x distance` carries chainSuccessors [..., "rank"] AND
    chainedRankOrderings [hi, lo, far, near]. Dropping that second axis undercounts
    the space by 78, so it is enumerated explicitly below. Chaining to rank also
    NARROWS the operands - see rankableSpreadOperands below.
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
                        # Chaining to rank NARROWS the legal operand set. The contract
                        # publishes rankableSpreadOperands: for EMA5 x spread that is
                        # ['EMA13'] alone, because "raw price-unit metrics never rank -
                        # rank the composition, not the level". Pairing the chain with
                        # all of spread's operands emitted 64 shapes omega's own
                        # validator refuses. See tests/test_space_validate_agreement.py.
                        rankable = flags.get("rankableSpreadOperands")
                        if rankable is not None and operand not in rankable:
                            continue
                        for o in (flags.get("chainedRankOrderings") or (None,)):
                            out.append(ColumnShape(name, transform, succ, operand, o))
                    elif (transform == "spread" and succ in _SERIES_CHAINS
                          and operand is not None and c.metric(operand).is_timeless):
                        # A series-building chain needs a per-bar series on BOTH sides.
                        # A timeless operand is a bundle read: the spread is a single
                        # scalar with nothing to build a series from. The contract does
                        # not publish this - it was found by rendering, and it accounted
                        # for 357 enumerated shapes the platform refuses. See
                        # data/audit/spread_chain_operand.json.
                        continue
                    else:
                        out.append(ColumnShape(name, transform, succ, operand, ordering))
    return out


# --- querying ---------------------------------------------------------------

def header_cost(shape: ColumnShape, window: int = 4,
                contract: Contract | None = None) -> int:
    """How many report headers this shape emits.

    Only `trajectory` fans out (composition_rules.fanOut); everything else is 1.
    `window` matters only when trajectory is present, and defaults to 4 because
    that is the platform's own default for the transform - not a guess.
    """
    col = shape.to_column()
    if "trajectory" in (shape.transform, shape.chained):
        col = col.model_copy(update={"window": window})
    return len(outputs_for(col, contract))


def platform_used(contract: Contract | None = None) -> set[tuple[str, str]]:
    """(metric, transformId) pairs the platform's own shipped templates use.

    This is the honest denominator for "what has nobody built yet" - far stronger
    than measuring against the eight cookbook recipes, and free, because the
    templates are already extracted.
    """
    c = contract or load()
    out: set[tuple[str, str]] = set()
    for template in c.platform_templates.values():
        for col in template.get("columns", []) or []:
            metric, transform = col.get("metric"), col.get("transformId")
            if metric and transform:
                out.add((metric, transform))
                if chained := col.get("chainedTransformId"):
                    out.add((metric, chained))
    return out


def query(*, family: str | None = None, transform: str | None = None,
          unit: str | None = None, timeframe_mode: str | None = None,
          chained: bool | None = None, max_headers: int | None = None,
          platform_uses: bool | None = None, expand_operands: bool = False,
          contract: Contract | None = None) -> list[ColumnShape]:
    """Filter the space. Every argument is optional; omitted means 'do not filter'."""
    c = contract or load()
    used = platform_used(c) if platform_uses is not None else set()
    out: list[ColumnShape] = []
    for s in enumerate_shapes(expand_operands, c):
        m = c.metrics[s.metric]
        if family is not None and m.family != family:
            continue
        if transform is not None and transform not in (s.transform, s.chained):
            continue
        if unit is not None and m.unit != unit:
            continue
        if timeframe_mode is not None and m.timeframe_mode != timeframe_mode:
            continue
        if chained is not None and (s.chained is not None) != chained:
            continue
        if max_headers is not None and header_cost(s, contract=c) > max_headers:
            continue
        if platform_uses is not None and ((s.metric, s.transform) in used) != platform_uses:
            continue
        out.append(s)
    return out
