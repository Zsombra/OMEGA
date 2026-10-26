"""Contract 92.0.0 retired the token budget: "tokenCountModel and budgetUsage.estimatedTokens leave the preview ...
list_strategy_vocabulary drops budgets.estimatedTokens, and previewExecutionLimits.maxResultBytes is renamed
maxResultChars" (vendor README, Contract history - v92). The stored vocabulary carries the budgets as
list_strategy_vocabulary served them at 95.0.0 (read 2026-10-06 ~22:45Z). omega's own token estimate stays - it is
still a fair measure of how much the agent reads - but it is information, never a breach of a platform cap."""
from __future__ import annotations

from omega.contract import load
from omega.fanout import cost_report
from omega.generate import PRESETS, plan

SERVED_95 = {"sections": 32, "sectionColumns": 32, "columnLookback": 32, "distinctTimeframes": 8,
             "strategyConditions": 16, "conditionClauses": 16, "conditionFrameReads": 256, "reportNoteChars": 3200}
# list_strategy_vocabulary at 135.2.0, 2026-10-26: columnLookback 64 (README v135), strategyConditions and
# conditionClauses 32, and v123's required marketReadChars
SERVED_135 = SERVED_95 | {"columnLookback": 64, "strategyConditions": 32, "conditionClauses": 32,
                          "marketReadChars": 4000}


def test_the_stored_budgets_are_the_served_ones():
    c = load()
    assert c.budgets == SERVED_135
    assert c.shared["previewExecutionLimits"] == {"maxResultChars": 150000, "deadlineMs": 15000}


def test_a_large_token_estimate_is_not_a_breach_any_more():
    p = plan(PRESETS["trend-continuation"])
    report = cost_report(p.report)
    assert not [b for b in report.breaches if "token" in b]
    assert report.estimated_tokens > 0


def test_the_critique_says_the_token_figure_is_an_estimate_with_no_platform_cap():
    lines = plan(PRESETS["trend-continuation"]).critique()
    [line] = [x for x in lines if "token" in x]
    assert "no platform token cap since contract 92" in line and "headroom" not in line
