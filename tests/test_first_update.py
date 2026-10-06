"""The generated UPDATE (design 2026-08-29, carried onto the v85 draft lifecycle):
axes_update() is axes() without ENTRY - the Thesis stays the single source of truth and
the draft's diff says what moves. The 2026-08-29 compile UPDATE (wire_update) and its
tests are in the repository history. The record pins for the live loop follow."""
from __future__ import annotations

from dataclasses import replace

from omega.generate import PRESETS, plan


def test_axes_update_is_axes_minus_entry():
    """v85: "Axes you omit keep the values the draft has" - so leaving ENTRY out of an
    update is how an existing strategy's entry axis is never touched (the 2026-08-29 rule:
    its semantics on an update are unmeasured). strategyId and draftVersion are request
    fields, never axes."""
    p = plan(PRESETS["trend-continuation"])
    a, u = p.axes(), p.axes_update()
    assert "ENTRY" not in u
    assert {k for k in set(a) | set(u) if a.get(k) != u.get(k)} == {"ENTRY"}
    assert not {"strategyId", "draftVersion", "expectedRevision"} & set(u)


def test_an_override_moves_exactly_its_own_axis_on_an_update():
    """The 2026-08-29 proof change (one R:R override) lands on TRADE_LEVEL_POLICY and
    nowhere else."""
    base = plan(PRESETS["trend-continuation"]).axes_update()
    t = replace(PRESETS["trend-continuation"], execution={"minRiskRewardRatio": 2.0})
    up = plan(t).axes_update()
    assert {k for k in base if base[k] != up[k]} == {"TRADE_LEVEL_POLICY"}
    assert up["TRADE_LEVEL_POLICY"]["minRiskRewardRatio"] == 2.0


# --- the live loop, 2026-08-29: pinned record ---------------------------------

import json
from pathlib import Path

from omega.execution import PLATFORM_EXECUTION_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
REC = json.loads(
    (ROOT / "data/audit/first_generated_update_2026-08-29.json").read_text(encoding="utf-8"))


def test_the_loop_is_recorded_end_to_end():
    assert set(REC["probes"]) >= {"preState", "restore", "compile", "apply",
                                  "readBack", "archive"}
    assert "FILL IN" not in REC["_interpretation"]
    assert REC["verdicts"]["sectionKeysOnUpdate"] in ("PRESERVED", "LOCKSTEP_REMINT")
    assert REC["verdicts"]["rrDiffAxis"] == "tradeLevelPolicy"


def test_the_override_landed_and_nothing_else_moved():
    pre = REC["probes"]["preState"]["strategy"]
    post = REC["probes"]["readBack"]["strategy"]
    assert pre["minRiskRewardRatio"] == 1.5 and post["minRiskRewardRatio"] == 2
    for k in PLATFORM_EXECUTION_DEFAULTS:
        if k != "minRiskRewardRatio":
            assert post[k] == pre[k]
    assert post["signalRules"] == pre["signalRules"]
    assert post["marketReadText"] == pre["marketReadText"]
    strip = lambda secs: [{k: v for k, v in s.items() if k != "sectionKey"}
                          for s in secs]
    assert strip(post["sections"]) == strip(pre["sections"])
    if REC["verdicts"]["sectionKeysOnUpdate"] == "PRESERVED":
        assert post["sections"] == pre["sections"]


def test_the_remint_was_lockstep_consistent():
    """The loop's one platform finding: a full-body UPDATE re-mints custom section
    identities even when the re-sent report is byte-identical - but re-resolves every
    condition reference to the new keys. Semantically safe; identity churns."""
    import re
    post = REC["probes"]["readBack"]["strategy"]
    post_keys = {s["sectionKey"] for s in post["sections"]}
    refs = set(re.findall(r'custom:[0-9a-f-]{36}', json.dumps(post["conditions"])))
    assert refs and refs <= post_keys
    pre_keys = {s["sectionKey"] for s in REC["probes"]["preState"]["strategy"]["sections"]}
    assert post_keys.isdisjoint(pre_keys), "keys re-minted - this pin documents it"


def test_the_lifecycle_ends_where_it_started():
    assert REC["probes"]["readBack"]["strategy"]["isActive"] is True
    assert REC["probes"]["archive"]["strategy"]["isActive"] is False
    assert REC["probes"]["apply"]["appliedImpact"]["committedRevision"] == 4
    assert REC["probes"]["apply"]["appliedImpact"]["boundAgentCount"] == 0
    assert REC["probes"]["apply"]["appliedImpact"]["propagatedAgentCount"] == 0
    tok = REC["probes"]["compile"].get("planToken")
    assert tok is not None and set(tok) == {"_redacted", "length", "sha256"}
