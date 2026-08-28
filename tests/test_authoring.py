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


from dataclasses import replace

from omega.generate import PRESETS
from omega.authoring import validate_thesis


def _codes(thesis):
    return {f.code for f in validate_thesis(thesis)}


def test_the_presets_pass_clean():
    for p in PRESETS.values():
        assert not [f for f in validate_thesis(p) if f.severity == "error"]


def test_unknown_module_is_an_error_not_a_silent_drop():
    t = replace(PRESETS["trend-continuation"],
                weights={**PRESETS["trend-continuation"].weights, "ELON_TWEETS": 3})
    assert "THESIS_UNKNOWN_MODULE" in _codes(t)


def test_too_few_directional_modules_is_an_error():
    """plan() silently emits NO conditions below 2 directional modules (verified
    2026-08-29) - the assistant must refuse before that happens."""
    t = replace(PRESETS["trend-continuation"],
                weights={"TREND_STRENGTH": 2, "VOLATILITY": 1, "RSI": 2})
    assert "THESIS_TOO_FEW_DIRECTIONAL" in _codes(t)
    t2 = replace(t, weights={"RSI": 2, "MACD": 2})
    assert "THESIS_TOO_FEW_DIRECTIONAL" not in _codes(t2)


def test_bad_weight_stance_and_anchor():
    base = PRESETS["trend-continuation"]
    assert "THESIS_BAD_WEIGHT" in _codes(replace(base, weights={"RSI": 5, "MACD": 2}))
    assert "THESIS_BAD_STANCE" in _codes(replace(base, stance="YOLO"))
    assert "THESIS_UNMEASURED_ANCHOR" in _codes(replace(base, anchor="1d"))


def test_universe_bounds_are_the_measured_ones():
    base = PRESETS["trend-continuation"]
    wide = replace(base, coin_selection={"mode": "ranked", "category": "ALL", "limit": 9})
    assert "THESIS_UNIVERSE_TOO_WIDE" in _codes(wide)
    fat = replace(base, coin_selection={"mode": "explicit",
                                        "tickers": [f"T{i}" for i in range(51)]})
    assert "THESIS_UNIVERSE_TOO_WIDE" in _codes(fat)


def test_unfeedable_required_signal_is_an_error():
    t = replace(PRESETS["trend-continuation"], required=["cvd_bullish"])  # CVD unweighted
    assert "THESIS_UNFEEDABLE_REQUIRED" in _codes(t)


def test_execution_findings_flow_through():
    t = replace(PRESETS["trend-continuation"], execution={"minRiskRewardRatio": 9})
    assert "EXECUTION_OUTSIDE_CATALOG_BOUND" in _codes(t)
