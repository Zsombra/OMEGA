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

ALL_PROBES = json.loads((DERIVED_DIR / "compiler_probes.json").read_text(encoding="utf-8"))["cases"]
# A retired case describes a surface the platform removed (its `retiredBecause` quotes the changelog); it stays in
# the oracle as history and is not replayed against today's validator.
PROBES = [c for c in ALL_PROBES if "retiredOn" not in c]
CONTRACT = load()


def test_the_retired_probes_are_exactly_the_section_override():
    retired = [c["id"] for c in ALL_PROBES if "retiredOn" in c]
    assert retired == ["timeless-metric-in-overridden-section"]
    assert all("48.0.0" in c["retiredBecause"] for c in ALL_PROBES if "retiredOn" in c)


def _column(case) -> Column:
    """The probe's column under today's roster: a probe recorded on a metric contract 110 retired for the SAME series
    (MACD -> MACD_HIST, PPO -> PPO_HIST: "the same histograms", data/contract/metrics/_moves_110.json) is replayed on
    its replacement, so the recorded verdict is checked against the series it measured."""
    spec = dict(case["column"])
    rec = CONTRACT.retired_metrics.get(spec.get("metric"))
    if rec and rec.get("sameSeries"):
        spec["metric"] = rec["author"]
    return Column.model_validate(spec)


@pytest.mark.parametrize("case", PROBES, ids=[c["id"] for c in PROBES])
def test_validator_agrees_with_compiler(case):
    findings = validate_column(
        _column(case),
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
    # 156 as of the 2026-09-20 refresh (contract 61.2.0); 144 on 2026-09-09 at 54.1.0;
    # 86 on 2026-08-24. The twelve added are all prior-session structure (TPO, naked POC, PDO).
    # 171 since the re-extraction at 108.4.0, 2026-10-13 (docs/plans/2026-10-13-omega-reextraction-108-4.md); the 15 are v100's twelve bar-geometry metrics and v101.1's three swing ones.
    # 177 since the re-extraction at 110.2.0, 2026-10-14: MACD, PPO, KC_MID retired, nine added (_moves_110.json).
    # 183 since the re-extraction at 110.8.0, 2026-10-15: none retired, six added (_moves_110_8.json).
    assert len(CONTRACT.metrics) == 183


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

    Verified live on 2026-08-24 (data/contract/columns/_renders_collision.json): a section with RSI14 at offset 0 and
    offset 3 rendered BOTH under `RSI14` and produced NO conditionColumns entry - the failure was silent. Since the
    header token carries the offset (`RSI14_o3`, 2026-10-13) that pair no longer collides; two IDENTICAL columns still
    do, and omega refuses them up front. (history: on 2026-08-24 an offset never named the header, so `RSI14` at offsets 0 and 3 collided (data/contract/columns/_renders_collision.json); by 2026-10-13 it does (`RSI14_o3`, data/contract/columns/header_tokens_2026-10-13.json). The changelog names no version for the change.)
    """
    from omega.types import Column, CustomSection, RelTimeframe
    from omega.validate import validate_section

    cols = [Column(metric="RSI14", transformId="value", timeframe=RelTimeframe(rel="anchor")),
            Column(metric="RSI14", transformId="value", timeframe=RelTimeframe(rel="anchor"))]
    section = CustomSection(kind="custom", title="collide", benchmarkTicker=None, columns=cols)
    codes = {f.code for f in validate_section(section)}
    assert "DUPLICATE_HEADER" in codes, "a header collision must not pass validation"


def test_offset_now_names_the_header():
    """`offset` changes the VALUE and, since the header token, the header too. (history: on 2026-08-24 an offset never named the header, so `RSI14` at offsets 0 and 3 collided (data/contract/columns/_renders_collision.json); by 2026-10-13 it does (`RSI14_o3`, data/contract/columns/header_tokens_2026-10-13.json). The changelog names no version for the change.)"""
    from omega.fanout import outputs_for
    from omega.types import Column, RelTimeframe

    base = Column(metric="RSI14", transformId="value", timeframe=RelTimeframe(rel="anchor"))
    assert [o.header for o in outputs_for(base.model_copy(update={"offset": 0}))] == ["RSI14"]
    assert [o.header for o in outputs_for(base.model_copy(update={"offset": 7}))] == ["RSI14_o7"]


def test_distinct_headers_still_pass():
    """The guard must not fire on a legitimate section."""
    from omega.types import Column, CustomSection, RelTimeframe
    from omega.validate import validate_section

    cols = [Column(metric="RSI14", transformId="value", timeframe=RelTimeframe(rel="anchor")),
            Column(metric="ADX", transformId="value", timeframe=RelTimeframe(rel="anchor"))]
    section = CustomSection(kind="custom", title="fine",
                            benchmarkTicker=None, columns=cols)
    assert not [f for f in validate_section(section) if f.severity == "error"]
