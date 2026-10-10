"""An UPDATE carries the current section keys forward (2026-10-10).

Measured 2026-10-10 06:34Z on the first live UPDATE of a strategy omega generated the day
before (battlegrid-manager tests/fixtures/2026-10-09-strategy-first-live/
action_62_update_stage.json, `response.review.diff`): re-staging `axes_update(current)`
showed 14 changes of no substance - two custom `sections[].sectionKey` "custom:…" -> null
and twelve clause `column.sectionKey`s ("reference-pairs" x2, "market-breadth" x2, the
strategy's own "custom:854d0e89-…" x8) -> null - because a CREATE sends no key and the
server mints or derives them at commit. The commit (action_63) kept every live key, so the
diff was cosmetic; but a user approving the card sees 14 phantom changes.

The committed body read back, `current_7534b2ee_from_get_strategy.json` (manager commit
8450268), is copied to data/contract/stage_strategy_draft/ as the measured fixture.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import replace
from pathlib import Path

from omega.generate import PRESETS, plan

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/contract/stage_strategy_draft/current_7534b2ee_from_get_strategy_20261010T0634Z.json"
CURRENT = json.loads(FIXTURE.read_text(encoding="utf-8"))["draft"]["content"]
CUSTOM_KEY = re.compile(r"^custom:[0-9a-fA-F-]{36}$")

SIGNALS_KEY = "custom:854d0e89-aefa-847e-8d24-9697100f2ddd"
CONTEXT_KEY = "custom:1035fbda-380e-8d68-86c5-eeb5534b8cfb"


def _clauses(defn: dict) -> list[dict]:
    if defn.get("kind") == "clause":
        return [defn]
    out: list[dict] = []
    for m in defn.get("members", []) or ([defn["member"]] if "member" in defn else []):
        out.extend(_clauses(m))
    return out


def _clause_keys(axes: dict) -> dict[str, list[tuple[str, str | None]]]:
    """conditionKey -> [(header, column.sectionKey)] in definition order."""
    return {c["conditionKey"]: [(x["column"]["header"], x["column"]["sectionKey"])
                                for x in _clauses(c["definition"])]
            for c in axes["CONDITIONS"]["conditions"]}


def _without_keys(current: dict) -> dict:
    cur = copy.deepcopy(current)
    for s in cur["REPORT"]["sections"]:
        if s.get("kind") == "custom":
            s.pop("sectionKey", None)
    for c in cur["CONDITIONS"]["conditions"]:
        for x in _clauses(c["definition"]):
            x["column"]["sectionKey"] = None
    return cur


def test_the_fixture_is_the_measured_committed_body():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert raw["source"] == "get_strategy" and raw["committedRevision"] == 1
    assert [s["sectionKey"] for s in CURRENT["REPORT"]["sections"]] == [SIGNALS_KEY, CONTEXT_KEY]
    live = {k for ks in _clause_keys(CURRENT).values() for _, k in ks}
    assert live == {"reference-pairs", "market-breadth", SIGNALS_KEY}


def test_a_create_still_sends_no_section_keys():
    """axes() is a CREATE: the server mints custom keys and derives a clause's section, so
    a custom section carries no sectionKey and every clause's column.sectionKey is null."""
    a = plan(PRESETS["trend-continuation"]).axes()
    assert all("sectionKey" not in s for s in a["REPORT"]["sections"] if s["kind"] == "custom")
    assert {k for ks in _clause_keys(a).values() for _, k in ks} == {None}


def test_the_round_trip_restages_the_committed_body_exactly():
    """plan.axes() was committed (the fixture is what the server made of it); re-staging
    axes_update(current) must carry the live keys so REPORT and CONDITIONS read back
    identical - the 14-line diff of action 62 collapses to nothing."""
    u = plan(PRESETS["trend-continuation"]).axes_update(CURRENT)
    assert [s.get("sectionKey") for s in u["REPORT"]["sections"]] == [SIGNALS_KEY, CONTEXT_KEY]
    assert u["REPORT"] == CURRENT["REPORT"]
    assert _clause_keys(u) == _clause_keys(CURRENT)
    assert u["CONDITIONS"] == CURRENT["CONDITIONS"]


def test_a_current_without_keys_leaves_the_nulls():
    p = plan(PRESETS["trend-continuation"])
    a = p.axes()
    for cur in (_without_keys(CURRENT), {k: v for k, v in CURRENT.items()
                                          if k not in ("REPORT", "CONDITIONS")}):
        u = p.axes_update(cur)
        assert u["REPORT"] == a["REPORT"]
        assert u["CONDITIONS"] == a["CONDITIONS"]


def test_a_dropped_custom_section_does_not_carry_its_key():
    """A thesis without the REGIME context no longer generates the Context section; the
    platform drops it at commit and omega does not carry its key anywhere."""
    t = replace(PRESETS["trend-continuation"], context=[])
    u = plan(t).axes_update(CURRENT)
    customs = [s for s in u["REPORT"]["sections"] if s["kind"] == "custom"]
    assert [s["title"] for s in customs] == ["Trend Continuation Signals"]
    assert customs[0]["sectionKey"] == SIGNALS_KEY
    assert CONTEXT_KEY not in json.dumps(u)
    assert _clause_keys(u) == _clause_keys(CURRENT)


def test_a_changed_metric_does_not_inherit_a_key():
    """The current strategy's Signals section holds no MA_ALIGN column any more (its
    metric moved), so the MAalign clauses - same conditionKey, same header - do not inherit
    the custom key; the other clauses and the section keys still do."""
    cur = copy.deepcopy(CURRENT)
    signals = next(s for s in cur["REPORT"]["sections"] if s["sectionKey"] == SIGNALS_KEY)
    col = next(c for c in signals["columns"] if c["metric"] == "MA_ALIGN")
    col["metric"] = "RSI14"
    u = plan(PRESETS["trend-continuation"]).axes_update(cur)
    assert [s.get("sectionKey") for s in u["REPORT"]["sections"]] == [SIGNALS_KEY, CONTEXT_KEY]
    keys = _clause_keys(u)
    for cond in ("TC_CORE_UP", "TC_CORE_DOWN"):
        by_header = dict(keys[cond])
        assert by_header["MAalign"] is None
        assert by_header["MACD_trend"] == SIGNALS_KEY
        assert by_header["OBV_trend"] == SIGNALS_KEY
        assert by_header["ADX_now"] == SIGNALS_KEY
    assert dict(keys["TC_CTX_UP"])["mktBreadth_all"] == "market-breadth"


def test_a_key_is_copied_only_within_the_same_condition_and_section():
    """TC_CTX_DOWN reads the same header as TC_CTX_UP; without a current TC_CTX_DOWN its
    clause stays null. A current key that contradicts where the header lives (a
    `session-field` key on a market-breadth header) is never copied either."""
    cur = copy.deepcopy(CURRENT)
    conds = cur["CONDITIONS"]["conditions"]
    cur["CONDITIONS"]["conditions"] = [c for c in conds if c["conditionKey"] != "TC_CTX_DOWN"]
    up = next(c for c in cur["CONDITIONS"]["conditions"] if c["conditionKey"] == "TC_CTX_UP")
    up["definition"]["column"]["sectionKey"] = "session-field"
    u = plan(PRESETS["trend-continuation"]).axes_update(cur)
    keys = _clause_keys(u)
    assert keys["TC_CTX_DOWN"] == [("mktBreadth_all", None)]
    assert keys["TC_CTX_UP"] == [("mktBreadth_all", None)]
    assert keys["TC_RISK_ON"] == [("usdtUsdDev_market", "reference-pairs"),
                                  ("usdcUsdtDev_market", "reference-pairs")]


def test_an_illegal_key_is_never_sent():
    """Only values the v91 schema admits are carried: a custom section's sectionKey must
    match ^custom:[0-9a-fA-F-]{36}$; a clause's column.sectionKey is a string of 1..120
    characters. Anything else stays as a CREATE sends it."""
    cur = copy.deepcopy(CURRENT)
    cur["REPORT"]["sections"][0]["sectionKey"] = "custom:not-a-uuid"
    cur["REPORT"]["sections"][1]["sectionKey"] = ""
    for c in cur["CONDITIONS"]["conditions"]:
        for x in _clauses(c["definition"]):
            if x["column"]["sectionKey"] == "reference-pairs":
                x["column"]["sectionKey"] = "x" * 121
            elif x["column"]["sectionKey"] == "market-breadth":
                x["column"]["sectionKey"] = ""
    u = plan(PRESETS["trend-continuation"]).axes_update(cur)
    assert all("sectionKey" not in s for s in u["REPORT"]["sections"])
    flat = {k for ks in _clause_keys(u).values() for _, k in ks}
    # the Signals section's custom key no longer matches a carried section, so it is not
    # copied onto its clauses either: nothing but nulls survives
    assert flat == {None}


def test_sections_match_by_title_then_by_position_only_when_unambiguous():
    """Titles are omega's deterministic identity; a retitled strategy falls back to position
    only when no title matches, the counts are equal and the titles are unique on both
    sides. A partial title match carries only what matched."""
    p = plan(PRESETS["trend-continuation"])
    renamed = copy.deepcopy(CURRENT)
    for s, title in zip(renamed["REPORT"]["sections"], ("Alpha", "Beta")):
        s["title"] = title
    u = p.axes_update(renamed)
    assert [s["sectionKey"] for s in u["REPORT"]["sections"]] == [SIGNALS_KEY, CONTEXT_KEY]
    assert u["CONDITIONS"] == CURRENT["CONDITIONS"]

    partial = copy.deepcopy(CURRENT)
    partial["REPORT"]["sections"][1]["title"] = "Beta"
    u = p.axes_update(partial)
    assert [s.get("sectionKey") for s in u["REPORT"]["sections"]] == [SIGNALS_KEY, None]
    assert u["CONDITIONS"] == CURRENT["CONDITIONS"]

    # no title matches and the counts differ: nothing is carried
    short = copy.deepcopy(renamed)
    short["REPORT"]["sections"] = short["REPORT"]["sections"][:1]
    u = p.axes_update(short)
    assert all("sectionKey" not in s for s in u["REPORT"]["sections"])
    assert SIGNALS_KEY not in json.dumps(u["CONDITIONS"])
    assert dict(_clause_keys(u)["TC_CTX_UP"])["mktBreadth_all"] == "market-breadth"


def test_every_carried_key_is_schema_legal():
    u = plan(PRESETS["trend-continuation"]).axes_update(CURRENT)
    for s in u["REPORT"]["sections"]:
        if s["kind"] == "custom":
            assert CUSTOM_KEY.match(s["sectionKey"])
    for ks in _clause_keys(u).values():
        for _, k in ks:
            assert k is None or (isinstance(k, str) and 1 <= len(k) <= 120)
