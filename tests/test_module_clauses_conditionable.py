"""Every MODULE_CLAUSES reading can carry a condition, by omega's own derived vocabulary.

v0.8.2: the MFI recipe gated on `MFI14_zone is overbought/oversold`, a header whose declared
vocabulary is disjoint from what it emits (data/contract/columns/_observed_vocabulary.json),
so the MFI module could never gate - and nothing caught it until the strategist's first proof
(2026-10-17, check #9). This sweeps every module and reading through the same checks the
plan runs (report_headers + validate_conditions), so a stale recipe fails here next time."""
from __future__ import annotations

import pytest

from omega.conditions import condition, observed_vocabulary, report_headers, validate_conditions
from omega.generate import MODULE_CLAUSES, Thesis, plan

READINGS = [(m, r) for m, spec in sorted(MODULE_CLAUSES.items()) for r in sorted(spec)]


@pytest.mark.parametrize("module, reading", READINGS)
def test_every_clause_is_conditionable(module, reading):
    p = plan(Thesis(name="Clause Sweep", weights={module: 2}))
    headers = report_headers(p.report)
    clause = MODULE_CLAUSES[module][reading]()
    header = clause["column"]["header"]

    assert header in headers, f"{module}.{reading}: {header!r} is not a header the module's recipe produces"
    spec = headers[header]
    assert clause["op"] in spec["ops"], f"{module}.{reading}: {header!r} does not admit {clause['op']!r}"
    if clause["op"] == "is":
        assert clause["label"] in spec["vocab"], (module, reading, clause["label"], spec["vocab"])
    measured = observed_vocabulary().get(header, {})
    assert not (measured.get("observed") and measured.get("observedInDeclared") == 0), (
        f"{module}.{reading}: {header!r} is measured DISJOINT - display-only")

    findings = validate_conditions(p.report, [condition("CS_PROBE", "probe", clause, verdict=None)])
    errors = [str(f) for f in findings if f.severity == "error"]
    assert not errors, errors


def test_mfi_reads_the_measured_midline():
    """The numeric replacement measured live 2026-08-24: MFI14 lt 50 (bearish) / gte 50 (bullish)."""
    mfi = {r: f() for r, f in MODULE_CLAUSES["MFI"].items()}
    assert {r: (c["column"]["header"], c["op"], c["value"]) for r, c in mfi.items()} == {
        "up": ("MFI14_now", "gte", 50), "down": ("MFI14_now", "lt", 50),
        "fade_up": ("MFI14_now", "lt", 50), "fade_down": ("MFI14_now", "gte", 50)}
    assert observed_vocabulary()["MFI14_zone"]["numericReplacement"] == \
        "MFI14 lt 50 (bearish) / MFI14 gte 50 (bullish)"


def test_an_mfi_thesis_plans_without_condition_errors():
    p = plan(Thesis(name="Money Flow", weights={"MFI": 2, "RSI": 2}))
    assert not [f for f in p.condition_findings() if f.severity == "error"]
    assert p.entry_gates()
