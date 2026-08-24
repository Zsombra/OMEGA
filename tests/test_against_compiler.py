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


# --- colliding headers: silent on the platform, an error here ---------------

def test_duplicate_headers_in_one_section_are_an_error():
    """Two columns that compile to the same header make the section unaddressable.

    Verified live (data/contract/columns/_renders_collision.json): a section with
    RSI14 at offset 0 and offset 3 renders BOTH columns under the header `RSI14`,
    and the platform raises nothing. But that section then produces NO
    conditionColumns entry at all - the agent can read the table while no condition
    can reference either column. The failure is completely silent.

    omega refuses it up front instead.
    """
    from omega.types import Column, CustomSection, RelTimeframe
    from omega.validate import validate_section

    cols = [Column(metric="RSI14", transformId="value",
                   timeframe=RelTimeframe(rel="anchor"), offset=0),
            Column(metric="RSI14", transformId="value",
                   timeframe=RelTimeframe(rel="anchor"), offset=3)]
    section = CustomSection(kind="custom", title="collide",
                            benchmarkTicker=None, columns=cols)
    errs = [f for f in validate_section(section) if f.severity == "error"]
    assert errs, "a header collision must not pass validation"
    assert any(f.code == "DUPLICATE_HEADER" for f in errs), [f.code for f in errs]
    assert "RSI14" in errs[0].message


def test_offset_alone_does_not_distinguish_a_header():
    """`offset` changes the VALUE but never appears in the header."""
    from omega.fanout import outputs_for
    from omega.types import Column, RelTimeframe

    base = Column(metric="RSI14", transformId="value", timeframe=RelTimeframe(rel="anchor"))
    assert [o.header for o in outputs_for(base.model_copy(update={"offset": 0}))] \
        == [o.header for o in outputs_for(base.model_copy(update={"offset": 7}))] \
        == ["RSI14"]


def test_distinct_headers_still_pass():
    """The guard must not fire on a legitimate section."""
    from omega.types import Column, CustomSection, RelTimeframe
    from omega.validate import validate_section

    cols = [Column(metric="RSI14", transformId="value", timeframe=RelTimeframe(rel="anchor")),
            Column(metric="ADX", transformId="value", timeframe=RelTimeframe(rel="anchor"))]
    section = CustomSection(kind="custom", title="fine",
                            benchmarkTicker=None, columns=cols)
    assert not [f for f in validate_section(section) if f.severity == "error"]
