"""Hold omega.validate and omega.fanout to the live compiler's recorded behaviour.

The oracle is data/derived/compiler_probes.json - 20 columns submitted to
get_strategy_column_contract with their verbatim results.
"""
from __future__ import annotations

import json

import pytest

from omega.contract import DERIVED_DIR, load
from omega.fanout import outputs_for
from omega.types import Column
from omega.validate import validate_column

PROBES = json.loads((DERIVED_DIR / "compiler_probes.json").read_text(encoding="utf-8"))["cases"]
CONTRACT = load()


def _column(case) -> Column:
    return Column.model_validate(case["column"])


@pytest.mark.parametrize("case", PROBES, ids=[c["id"] for c in PROBES])
def test_validator_agrees_with_compiler(case):
    findings = validate_column(
        _column(case),
        section_timeframe=case.get("sectionTimeframe"),
        contract=CONTRACT,
    )
    errors = [f for f in findings if f.severity == "error"]

    if case["expect"] == "legal":
        assert not errors, f"expected legal, validator raised: {[str(e) for e in errors]}"
    else:
        assert errors, "expected the validator to reject this column"
        if "errorCode" in case:
            assert case["errorCode"] in {e.code for e in errors}, (
                f"expected code {case['errorCode']}, got {[e.code for e in errors]}")


@pytest.mark.parametrize(
    "case",
    [c for c in PROBES if c["expect"] == "legal" and "headers" in c],
    ids=[c["id"] for c in PROBES if c["expect"] == "legal" and "headers" in c],
)
def test_predicted_headers_match_compiler(case):
    predicted = [o.header for o in outputs_for(_column(case), CONTRACT)]
    assert predicted == case["headers"], (
        f"header mismatch\n  predicted: {predicted}\n  compiler:  {case['headers']}")


def test_corpus_is_complete():
    assert len(CONTRACT.metrics) == 86


def test_every_privileged_pair_is_rejected():
    assert CONTRACT.privileged_pairs, "expected at least one platform-privileged pair"
    for metric, transform in CONTRACT.privileged_pairs:
        col = Column(metric=metric, transformId=transform, timeframe={"rel": "anchor"})
        errors = [f for f in validate_column(col, contract=CONTRACT) if f.severity == "error"]
        assert errors, f"{metric} x {transform} should be rejected"
        assert "PLATFORM-PRIVILEGED" in errors[0].message


def test_spread_pools_are_symmetric_and_exclude_self():
    graph = json.loads((DERIVED_DIR / "spread_operand_graph.json").read_text(encoding="utf-8"))
    for metric, operands in graph["edges"].items():
        assert metric not in operands, f"{metric} lists itself as a spread operand"
        for other in operands:
            assert metric in graph["edges"][other], f"{metric}->{other} is not reciprocal"
