"""The metric-anchor rule: measured at 54.1.0, unreachable since 61.2.0, removed in v0.14.3 (the ledger's M28).

At contract 54.1.0 the platform declared an absolute anchor on nine metrics - PDH, PDL and the seven pivots, all "1d".
Measured live 2026-09-09 on PIVOT_P: relative references and {abs: "1d"} are accepted, {abs: "4h"} is refused ("metric
'pivotP' is anchored to '1d' - it accepts only that absolute timeframe reference"); the record is
data/audit/metric_anchor_rule_2026-09-09.json. `validate_column` enforced it (METRIC_ANCHOR_MISMATCH and the warning
METRIC_ANCHOR_RELATIVE_UNVERIFIED) behind `m.anchor and not m.is_timeless`.

By the 61.2.0 re-extraction those nine had gone TIMELESS and lost their declared anchor, and no metric has declared
one since: at 171.0.0 none of the 581 does. The block could not fire - the 09-20 session record flagged it as dead
code - and v0.14.3 removed it. What stays:

1. the invariant, ASSERTED: no catalogued metric declares an anchor. If a re-extraction brings one back this fails
   loudly, and the rule must be re-measured (the 09-09 probe is the shape to repeat) and re-added: omega no longer
   enforces it, so this test is the only guard;
2. the proof that the removal changed nothing: the removed block, kept below verbatim as a reference, yields no finding
   for any catalogued metric through any transform it offers at any timeframe reference - so every validate_column
   answer is the one it gave with the block. (Measured once more while removing it: a digest of all 28,410 such
   answers, 10,517 findings, was identical before and after - docs/plans/2026-11-13-omega-v0-14-3-menu-band.md.)
"""
import dataclasses

import pytest

from omega.contract import load
from omega.types import Column
from omega.validate import Finding, validate_column

ANCHORED = "PIVOT_P"          # anchored to "1d" at 54.1.0; timeless since 61.x
ANCHOR = "1d"
TIMEFRAMES = ({"rel": "anchor"}, {"rel": "lower"}, {"rel": "regime"}, {"abs": "1h"}, {"abs": "4h"}, {"abs": "1d"})
ANCHOR_CODES = {"METRIC_ANCHOR_MISMATCH", "METRIC_ANCHOR_RELATIVE_UNVERIFIED"}


@pytest.fixture(scope="module")
def contract():
    return load()


def _removed_block(column: Column, m, path: str = "c") -> list[Finding]:
    """omega/validate.py's metric-anchor block as v0.14.2 shipped it (removed in v0.14.3), verbatim but for `out`."""
    out: list[Finding] = []
    if m.anchor and not m.is_timeless:
        got_abs = getattr(column.timeframe, "abs", None)
        if got_abs is not None and got_abs != m.anchor:
            out.append(Finding(
                "error", "METRIC_ANCHOR_MISMATCH", f"{path}.timeframe",
                f"{m.metric} is anchored to {m.anchor!r} - it accepts only that absolute "
                f"timeframe reference, not {got_abs!r}. Use "
                f'timeframe={{"abs": "{m.anchor}"}} or a relative reference.'))
        elif got_abs is None:
            out.append(Finding(
                "warning", "METRIC_ANCHOR_RELATIVE_UNVERIFIED", f"{path}.timeframe",
                f"{m.metric} declares anchor {m.anchor!r}. A relative reference is accepted "
                f"by the column contract (measured), but the vendor's authoring skill says "
                f'the save path accepts only {{"abs": "{m.anchor}"}}. That path is unmeasured; '
                f"pin it if the column must survive a save."))
    return out


# --- the invariant: why the block could go ------------------------------------------------------------------------------
def test_no_catalogued_metric_declares_an_anchor_while_not_timeless(contract):
    """The removed block's exact condition, over the whole live catalogue.

    If this fails, the platform has re-declared an anchor: re-measure the rule against the live contract (the 09-09
    probe in data/audit/metric_anchor_rule_2026-09-09.json is the shape to repeat) and re-add it to validate_column -
    since v0.14.3 omega does not enforce it."""
    live = [m.metric for m in (contract.metric(n) for n in contract.metrics) if m.anchor and not m.is_timeless]
    assert live == [], (
        f"{len(live)} metric(s) now declare an anchor while not timeless: {live}. The metric-anchor rule omega removed "
        "in v0.14.3 has a subject again - re-measure it and re-add it.")
    assert [n for n in contract.metrics if contract.metric(n).anchor] == []      # timeless or not: none at all


def test_the_nine_metrics_that_once_carried_an_anchor_are_now_timeless_and_carry_none(contract):
    """PDH, PDL and the seven pivots: the exact set that was anchored to "1d" at 54.1.0."""
    once_anchored = ["PDH", "PDL", "PIVOT_P", "PIVOT_R1", "PIVOT_R2", "PIVOT_R3",
                     "PIVOT_S1", "PIVOT_S2", "PIVOT_S3"]
    for name in once_anchored:
        m = contract.metric(name)
        assert m.anchor is None, f"{name} declares anchor {m.anchor!r} again"
        assert m.is_timeless, f"{name} is no longer timeless"


# --- the removal changed nothing ----------------------------------------------------------------------------------------
def test_the_removed_block_yields_nothing_on_the_catalogue(contract):
    """Every catalogued metric, through every transform it offers, at every timeframe reference: the block would have
    added no finding, so removing it leaves each validate_column answer as it was."""
    checked = 0
    for name in contract.metrics:
        m = contract.metric(name)
        for tid in m.transforms:
            for tf in TIMEFRAMES:
                column = Column.model_validate({"metric": name, "transformId": tid, "timeframe": tf})
                assert _removed_block(column, m) == [], (name, tid, tf)
                checked += 1
    assert checked == sum(len(contract.metric(n).transforms) for n in contract.metrics) * len(TIMEFRAMES)


@pytest.mark.parametrize("timeframe", TIMEFRAMES)
def test_validate_column_names_no_anchor_code(contract, timeframe):
    for name in ("PDH", "PDL", ANCHORED, "CLOSE", "RSI14", "SMA200"):
        found = validate_column(Column(metric=name, transformId="value", timeframe=timeframe), contract=contract)
        assert not ANCHOR_CODES & {f.code for f in found}, (name, timeframe)


def test_a_redeclared_anchor_is_no_longer_enforced_so_the_invariant_is_the_guard(contract):
    """The 54.1.0 shape restored on PIVOT_P (anchor "1d", candle): the block refused {abs: "4h"} and warned on a
    relative reference; validate_column now says neither. That is why the invariant above must fail first."""
    m = dataclasses.replace(contract.metric(ANCHORED), anchor=ANCHOR, timeframe_mode="anchored")
    with_anchor = dataclasses.replace(contract, metrics={**contract.metrics, m.metric: m})
    for tf in ({"abs": "4h"}, {"abs": ANCHOR}, {"rel": "anchor"}):
        column = Column(metric=m.metric, transformId="value", timeframe=tf)
        assert not ANCHOR_CODES & {f.code for f in validate_column(column, contract=with_anchor)}, tf
    # ... where the removed block would have answered, as at 54.1.0
    assert [f.code for f in _removed_block(Column(metric=m.metric, transformId="value", timeframe={"abs": "4h"}), m)] \
        == ["METRIC_ANCHOR_MISMATCH"]
    assert [f.severity for f in _removed_block(Column(metric=m.metric, transformId="value",
                                                      timeframe={"rel": "anchor"}), m)] == ["warning"]
    assert _removed_block(Column(metric=m.metric, transformId="value", timeframe={"abs": ANCHOR}), m) == []
