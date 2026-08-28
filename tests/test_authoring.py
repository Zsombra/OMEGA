"""The authoring surface (design 2026-08-29): the menu, the guardrails, the brief.
Everything derived from the measured maps; MODULE_DESCRIPTIONS is the one
hand-written table and these tests pin it complete."""
from __future__ import annotations

from omega.authoring import MODULE_DESCRIPTIONS, vocabulary
from omega.execution import PLATFORM_EXECUTION_DEFAULTS
from omega.generate import MODULE_CLAUSES, MODULE_RECIPES, RANKED_LIMIT_MEASURED_MAX


def test_the_vocabulary_covers_every_module_exactly():
    v = vocabulary()
    assert set(v["modules"]) == set(MODULE_RECIPES) == set(MODULE_DESCRIPTIONS)
    for m, entry in v["modules"].items():
        assert entry["measures"] == MODULE_DESCRIPTIONS[m]
        assert entry["directional"] == ("up" in MODULE_CLAUSES[m])
        assert set(entry["readings"]) == set(MODULE_CLAUSES[m])
        assert all(isinstance(t, str) and t for t in entry["readings"].values())


def test_directional_split_matches_the_clause_map():
    v = vocabulary()
    directional = {m for m, e in v["modules"].items() if e["directional"]}
    assert len(directional) == 15
    assert {"TREND_STRENGTH", "VOLATILITY"} == set(v["modules"]) - directional


def test_the_measured_constants_flow_through():
    v = vocabulary()
    assert set(v["anchors"]) == {"5m", "15m", "1h", "4h"}
    assert v["anchors"]["4h"] == {"cadence": "SWING", "regimeTimeframe": "1d"}
    assert v["universe"]["rankedMaxLimit"] == RANKED_LIMIT_MEASURED_MAX == 4
    assert v["universe"]["explicitMaxTickers"] == 50
    assert v["execution"]["defaults"] == PLATFORM_EXECUTION_DEFAULTS
    assert v["execution"]["catalogEnforced"] == {"minRiskRewardRatio": True,
                                                 "minAtrPct": False}


def test_clause_text_renders_every_op():
    from omega.authoring import _clause_text
    col = {"sectionKey": None, "header": "H"}
    assert _clause_text({"kind": "clause", "column": col, "op": "is", "label": "x"}) == "H is 'x'"
    assert _clause_text({"kind": "clause", "column": col, "op": "gte", "value": 25}) == "H gte 25"
    assert _clause_text({"kind": "clause", "column": col, "op": "between",
                         "low": -1, "high": 1}) == "H between -1 and 1"
