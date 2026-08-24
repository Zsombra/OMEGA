"""The indicator census, checked against the engine rather than trusted.

`data/derived/indicator_families.json` claims that ~47 named indicator families
are constructible here and ~27 are not. A census is only worth having if it
cannot quietly become false, so every buildable entry is built and validated,
and every blocked entry has to carry a cause.

The point is not that these tests could fail today - they pass. It is that they
fail the day the platform's contract moves under them, which is the failure mode
this repo exists to catch.
"""
from __future__ import annotations

import json

import pytest

from omega.contract import DERIVED_DIR, load
from omega.fanout import outputs_for
from omega.space import enumerate_shapes
from omega.types import Column, CustomSection, Operand, RelTimeframe, Report
from omega.validate import validate_report

FAMILIES = json.loads((DERIVED_DIR / "indicator_families.json").read_text(encoding="utf-8"))
BUILDABLE = FAMILIES["buildable"]
BLOCKED = FAMILIES["blocked"]

CAUSES = {"operator-absent", "guard-refuses", "needs-state", "data-absent",
          "renderer-fails"}


def _column(spec: dict) -> Column:
    return Column(
        metric=spec["metric"],
        transformId=spec["transformId"],
        timeframe=RelTimeframe(rel=spec.get("rel", "anchor")),
        chainedTransformId=spec.get("chainedTransformId"),
        window=spec.get("window"),
        offset=spec.get("offset"),
        bars=spec.get("bars"),
        ordering=spec.get("ordering"),
        side=spec.get("side"),
        inputs=[Operand(metric=i["metric"]) for i in spec["inputs"]] if spec.get("inputs") else None,
    )


def _ids(entries):
    return [e["id"] for e in entries]


# --- every buildable family must actually build -----------------------------

@pytest.mark.parametrize("fam", BUILDABLE, ids=_ids(BUILDABLE))
def test_a_buildable_family_validates(fam):
    """Its columns must survive omega.validate with no errors."""
    cols = [_column(s) for s in fam["columns"]]
    report = Report(anchor="1h", sections=[CustomSection(
        kind="custom", title=fam["name"][:60], benchmarkTicker=None, columns=cols)])
    errors = [f for f in validate_report(report).findings if f.severity == "error"]
    assert not errors, f"{fam['id']}: {[f.message for f in errors]}"


@pytest.mark.parametrize("fam", BUILDABLE, ids=_ids(BUILDABLE))
def test_a_buildable_family_is_in_the_enumerated_space(fam):
    """A spec omega.validate accepts but omega.space never enumerates would mean
    the two disagree about what is legal."""
    c = load()
    legal = {(s.metric, s.transform, s.chained) for s in enumerate_shapes(contract=c)}
    for spec in fam["columns"]:
        key = (spec["metric"], spec["transformId"], spec.get("chainedTransformId"))
        assert key in legal, f"{fam['id']}: {key} is not in the enumerated space"


@pytest.mark.parametrize("fam", BUILDABLE, ids=_ids(BUILDABLE))
def test_a_buildable_family_emits_headers(fam):
    """A column that produces nothing cannot carry an indicator."""
    for spec in fam["columns"]:
        assert outputs_for(_column(spec)), f"{fam['id']}: {spec} emits no header"


# --- the specific claims the census makes -----------------------------------

def _fam(fid, group=BUILDABLE):
    return next(f for f in group if f["id"] == fid)


def test_the_carry_factor_is_a_rank_on_funding():
    """The headline institutional claim: funding IS the carry in perpetuals."""
    fam = _fam("carry-factor")
    assert fam["columns"] == [{"metric": "FUNDING_RATE", "transformId": "rank", "ordering": "hi"}]


def test_cross_sectional_momentum_does_not_use_a_chg_metric():
    """CHG_* cannot be ranked - a correction to an earlier published claim."""
    c = load()
    rankable = {s.metric for s in enumerate_shapes(contract=c) if s.transform == "rank"}
    for m in ("CHG_5M", "CHG_15M", "CHG_1H", "CHG_4H", "CHG_24H"):
        assert m not in rankable, f"{m} became rankable - the census needs revisiting"
    assert _fam("xs-momentum")["columns"][0]["metric"] in rankable


def test_basis_is_recorded_as_unchainable():
    """MARK's spread does not chain, so basis momentum is not buildable."""
    c = load()
    chained = {(s.metric, s.transform) for s in enumerate_shapes(contract=c) if s.chained}
    assert ("MARK", "spread") not in chained
    assert "does not chain" in _fam("basis")["note"]


def test_spread_stays_within_a_unit_class():
    """The clique rule is what blocks Amihud and average trade size."""
    c = load()
    for s in enumerate_shapes(expand_operands=True, contract=c):
        if s.transform == "spread" and s.operand:
            assert c.metrics[s.metric].unit == c.metrics[s.operand].unit, \
                f"{s.metric} x {s.operand} crosses unit classes"


# --- the blocked list has to stay honest ------------------------------------

@pytest.mark.parametrize("fam", BLOCKED, ids=_ids(BLOCKED))
def test_a_blocked_family_names_a_cause(fam):
    """'Blocked' without a cause is not a finding, it is a shrug."""
    assert fam["cause"] in CAUSES, f"{fam['id']}: unknown cause {fam.get('cause')!r}"
    if fam["cause"] == "operator-absent":
        assert fam.get("needs"), f"{fam['id']}: says the operator is absent but not which one"


def test_only_one_family_is_blocked_for_missing_data():
    """The census's central claim: almost everything blocked is a missing
    equation, not a missing input. If that stops being true, the summary
    everywhere else is wrong."""
    data_absent = [f["id"] for f in BLOCKED if f["cause"] == "data-absent"]
    assert data_absent == ["historical-rank"], data_absent


def test_no_blocked_operator_secretly_exists():
    """A family blocked for a missing operator must not name one the contract
    already offers."""
    c = load()
    have = set(c.transforms)
    for fam in BLOCKED:
        if fam["cause"] != "operator-absent":
            continue
        first = fam["needs"].split()[0].strip(",")
        assert first not in have, f"{fam['id']} wants {first!r}, which already exists"


def test_no_family_appears_in_both_lists():
    assert not (set(_ids(BUILDABLE)) & set(_ids(BLOCKED)))


def test_rank_orderings_split_into_three_groups():
    """hi/lo is a magnitude sort; far/near is a distance-from-zero sort. A spec
    that asks for the wrong one is refused, which is how the census's original
    cross-sectional reversal entry was caught."""
    from collections import defaultdict
    c = load()
    ordv = defaultdict(set)
    for s in enumerate_shapes(expand_operands=True, contract=c):
        if s.transform == "rank" and s.ordering:
            ordv[s.metric].add(s.ordering)
    groups = defaultdict(list)
    for m, o in ordv.items():
        groups[frozenset(o)].append(m)
    assert set(map(frozenset, ({"hi", "lo"}, {"far", "near"},
                               {"hi", "lo", "far", "near"}))) == set(groups)
    # CLOSE_CHANGE is the only far/near-only metric
    assert groups[frozenset({"far", "near"})] == ["CLOSE_CHANGE"]



def test_no_buildable_family_uses_a_shape_the_renderer_refuses():
    """Offline-legal is not the same as live-renderable. The 8 crowd rank shapes
    validate cleanly and INTERNAL_ERROR on every render, so the census has to be
    checked against the quarantine list too - this is how the cross-sectional
    positioning family was caught."""
    import sys
    sys.path.insert(0, "scripts")
    from sweep import UNRENDERABLE
    for fam in BUILDABLE:
        for spec in fam["columns"]:
            key = (spec["metric"], spec.get("chainedTransformId") or spec["transformId"])
            assert key not in UNRENDERABLE, f"{fam['id']} uses unrenderable {key}"
