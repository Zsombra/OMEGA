"""v103: "`sideRequired` and `operandRequired` leave every transform entry `get_metric_construction_hints` serves. Each
restated a field the same entry already carries: read `authoring.parameters.side.required` and
`authoring.parameters.inputs.required` instead, where an absent parameter means the transform does not accept it"
(vendored README, "Contract history - v103").

The 95.0.0 output schema (battlegrid-manager tests/fixtures/2026-10-06-surface-95.0.0/output_schemas.json) shows both on
the same transform entry, and the 61.2.0 corpus agrees cell for cell. So omega reads the requirement from the
transform's authoring catalogue (data/contract/transforms/_authoring.json), which a re-extraction at 108 still
serves, and the operand and side checks cannot go silent when the per-metric flags stop arriving.
"""
from __future__ import annotations

import dataclasses

import pytest

from omega.contract import load
from omega.types import Column, Operand, RelTimeframe
from omega.validate import validate_column

C = load()


def _strip_v103_flags(c):
    """The corpus as a 108 re-extraction would write it: no per-metric operandRequired / sideRequired."""
    metrics = {name: dataclasses.replace(m, transforms={
        tid: {k: v for k, v in spec.items() if k not in ("operandRequired", "sideRequired")}
        for tid, spec in m.transforms.items()}) for name, m in c.metrics.items()}
    return dataclasses.replace(c, metrics=metrics)


def test_the_108_4_corpus_is_the_v103_shape_and_the_catalogue_carries_the_requirement():
    """Until 2026-10-13 the corpus was the 61.2.0 extraction, whose per-metric flags agreed with the catalogue on all
    619 cells (the check that justified reading the catalogue). The 2026-10-13 re-extraction at 108.4.0 is the v103
    shape itself: no transform entry carries either flag, and every operand / side requirement is in the catalogue."""
    cells = 0
    for m in C.metrics.values():
        for tid, spec in m.transforms.items():
            cells += 1
            assert "operandRequired" not in spec and "sideRequired" not in spec, (m.metric, tid)
    assert cells == 705   # 670 at 108.4.0; 705 at 110.2.0 (2026-10-14): - 18 retired + 53 added


def test_the_catalogue_names_exactly_spread_and_the_four_zone_transforms():
    assert {t for t in C.transforms if C.requires_operand(t)} == {"spread"}
    assert {t for t in C.transforms if C.requires_side(t)} == {
        "nearestZoneType", "nearestZoneRange", "nearestZoneDist", "nearestZoneAge"}


@pytest.mark.parametrize("contract", [C, _strip_v103_flags(C)], ids=["61.2.0-shape", "v103-shape"])
def test_the_operand_and_side_checks_hold_without_the_per_metric_flags(contract):
    no_operand = Column(metric="EMA5", transformId="spread", timeframe=RelTimeframe(rel="anchor"))
    assert "OPERAND_REQUIRED" in {f.code for f in validate_column(no_operand, contract=contract)}
    ok = no_operand.model_copy(update={"inputs": [Operand(metric="EMA13")]})
    assert not [f for f in validate_column(ok, contract=contract) if f.severity == "error"]

    no_side = Column(metric="STRUCT_ZONES", transformId="nearestZoneDist", timeframe=RelTimeframe(rel="regime"))
    assert "SIDE_REQUIRED" in {f.code for f in validate_column(no_side, contract=contract)}
    stray = Column(metric="RSI14", transformId="value", timeframe=RelTimeframe(rel="anchor"), side="support")
    assert "SIDE_IGNORED" in {f.code for f in validate_column(stray, contract=contract)}
