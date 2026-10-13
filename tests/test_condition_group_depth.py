"""Group depth: the vendor strategy-examples skill (exported at 105.0.0) says "Groups: `ALL | ANY | NOT | N_OF` (with
`n`), depth ≤ 2". The 108 write schema does not bound it (a group's members are definitions again, recursively), and
v103 serves the real figure under `list_strategy_vocabulary`'s `conditionGrammar`, unread here. So omega warns,
quoting the source, and never errs.

Depth counts groups nested inside ONE condition's definition. A `conditionRef` adds none: "a referenced condition is
resolved once and contributes the same answer" (61.0.1 CONDITION_HOLD_ILLEGAL sentence) - it is a leaf of the
referring definition, and its own definition is judged when its turn comes.
"""
from __future__ import annotations

from omega.conditions import (all_of, any_of, condition, num, ref, validate_conditions)
from omega.generate import PRESETS, plan
from omega.types import Column, CustomSection, RelTimeframe, Report

REPORT = Report(sections=[CustomSection(title="t", columns=[
    Column(metric="RSI14", transformId="value", timeframe=RelTimeframe(rel="anchor"))])])


def _depth_warnings(conds):
    return [f for f in validate_conditions(REPORT, conds) if "depth" in f.message]


def leaf():
    return num("RSI14", "gt", 50)


def test_two_levels_of_groups_draw_nothing():
    two = condition("TWO", "two", all_of(any_of(leaf(), leaf()), leaf()), verdict="UP")
    assert _depth_warnings([two]) == []


def test_three_levels_warn_once_at_the_third_quoting_the_vendor():
    three = condition("THREE", "three", all_of(any_of(all_of(leaf(), leaf()), leaf()), leaf()), verdict="UP")
    found = _depth_warnings([three])
    assert [(f.severity, f.condition_key, f.path) for f in found] == [
        ("warning", "THREE", ".definition.members[0].members[0]")]
    assert "maxGroupDepth 2" in found[0].message


def test_a_condition_ref_resets_the_depth():
    inner = condition("INNER", "inner", all_of(any_of(leaf(), leaf()), leaf()))
    outer = condition("OUTER", "outer", all_of(any_of(ref("INNER"), leaf()), leaf()), verdict="UP")
    assert _depth_warnings([inner, outer]) == []


def test_no_preset_nests_deeper_than_two():
    for name, thesis in PRESETS.items():
        p = plan(thesis)
        assert _depth_warnings_for(p) == [], name


def _depth_warnings_for(p):
    return [f for f in p.condition_findings() if "depth" in getattr(f, "message", "")]


def test_the_limit_is_the_served_max_group_depth():
    """2026-10-13: list_strategy_vocabulary serves conditionGrammar.maxGroupDepth at 108.4.0."""
    from omega.conditions import GROUP_DEPTH_MAX
    from omega.contract import load
    assert GROUP_DEPTH_MAX == load().shared["conditionGrammar"]["maxGroupDepth"] == 2
