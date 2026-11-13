"""Item '149 Open 6' (battlegrid-manager docs/status/2026-11-05-contract-149.md): does a staged draft echo default knobs
back into its content? Checked offline, 2026-11-13: no.

The manager settles a stage whose answer was lost (manager/actions/strategy_verify.py, _verify_stage) by matching the
re-read draft's content_sha against content_sha(the axes it sent), in its canonical form (manager.risk.radar.canonical:
sorted keys, numbers as normalised decimal strings, null kept). An echoed default would make them differ and leave the
row waiting for the user. data/audit/draft_echo_2026-11-13.json compares every stored stage whose whole sent body and
whole read-back are on disk - 15 CREATE drafts (14 at 168.2.0, the v0.14.3 probe B1 at 171.0.0) and 11 reads of the 4
UPDATE drafts at 171.0.0 - and finds no key added, none dropped and no value changed: the only raw difference is a
number's spelling (10.0 sent, 10 read back), which the canonical form already normalises. So the manager's recovery
needs no normalising helper; none is added. B1's whole sent body and read-back are in
data/audit/stop_band_171_2026-11-12.json, so the comparison replays here on a real pair.

For an UPDATE row the record's `sent` is the union of every stage into the draft, while _verify_stage compares the
whole re-read draft with the axes of the ONE stage it settles (review 2026-11-13). So the manager's match holds only on
a stage that is its draft's only stage, or one that restages every axis the draft holds: 24 of the 26. The 2 others -
the reads after v171/calls.jsonl line 20 staged POSITION_MANAGEMENT over a held TRADE_LEVEL_POLICY draft - are the
manager's to fix (compare against the composed draft); the record's `managerRecovery` says so.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from omega import trade_levels as tl
from omega.generate import PRESETS, plan
from omega.types import KNOBS

ROOT = Path(__file__).resolve().parents[1]
ECHO = json.loads((ROOT / "data/audit/draft_echo_2026-11-13.json").read_text(encoding="utf-8"))
B1 = json.loads((ROOT / tl.STOP_BAND_PROBES).read_text(encoding="utf-8"))["probes"]["B1.range_0_8_1_8"]


def _normalised(value):
    """battlegrid-manager's manager.risk.radar._normalised, as read at manager main d64308d."""
    if isinstance(value, dict):
        return {k: _normalised(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalised(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    return format(Decimal(str(value)).normalize(), "f")


def content_sha(content) -> str:
    return hashlib.sha256(json.dumps(_normalised(content), sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def test_no_stored_read_back_echoes_anything_into_the_draft():
    rows = ECHO["readBacks"]
    assert ECHO["counts"] == {"readBacks": 26, "create": 15, "update": 11, "canonicalEqual": 26, "keysAdded": 0,
                              "keysDropped": 0, "valuesChanged": 0, "numberSpelling": 30, "managerMatch": 24}
    assert len(rows) == ECHO["counts"]["readBacks"]
    for row in rows:
        assert row["canonicalEqual"] and row["sentSha256"] == row["readSha256"], row["source"]
        assert row["keysAdded"] == row["keysDropped"] == row["valuesChanged"] == [], row["source"]
        # the only raw difference: a number spelled another way, equal once normalised
        for spelled in row["numberSpelling"]:
            assert _normalised(spelled["sent"]) == _normalised(spelled["read"]), row["source"]
    assert {r["contractVersion"] for r in rows} == {"168.2.0", "171.0.0"}
    assert ECHO["answer"].startswith("No echo.")


def test_the_managers_lost_answer_match_holds_only_where_the_latest_stage_restages_every_held_axis():
    """_verify_stage (manager/actions/strategy_verify.py, lines 160 - 161 at manager main d64308d) matches the WHOLE
    re-read draft against the axes the stage it settles sent, at a draftVersion above the one it was sent over. A row's
    own `sent` is the union of the draft's stages, so its canonical equality alone does not say the manager matches."""
    rows = ECHO["readBacks"]
    for row in rows:
        latest = row["latestStage"]
        assert row["draftVersionRead"] > latest["draftVersionSent"], row["source"]
        assert row["managerMatch"] == (row["readSha256"] == latest["sha256"]), row["source"]
        # only stage, or every held axis restaged: the manager matches exactly there (no echo makes the difference)
        restaged = row["stagesIntoDraft"] == 1 or set(latest["axes"]) == set(row["axes"])
        assert row["managerMatch"] == restaged, row["source"]
        if row["kind"] == "CREATE":
            assert row["stagesIntoDraft"] == 1 and latest["sha256"] == row["sentSha256"], row["source"]
    missed = [(r["source"], r["latestStage"]["source"], r["latestStage"]["axes"], r["latestStage"]["draftVersionSent"],
               r["axes"]) for r in rows if not r["managerMatch"]]
    assert missed == [(f"v171/calls.jsonl line {n}", "v171/calls.jsonl line 20", ["POSITION_MANAGEMENT"], 4,
                       ["POSITION_MANAGEMENT", "TRADE_LEVEL_POLICY"]) for n in (21, 23)]
    assert all(r["canonicalEqual"] for r in rows if not r["managerMatch"])       # not an echo: the union matches
    # a draft staged more than once still matches where each stage restaged the one axis it holds (lines 33, 35, 36)
    assert [r["source"] for r in rows if r["stagesIntoDraft"] > 1 and r["managerMatch"]] == [
        "v171/calls.jsonl line 33", "v171/calls.jsonl line 35", "v171/calls.jsonl line 36"]
    note = ECHO["managerRecovery"]
    assert note.startswith("For whoever pins v0.14.3 in battlegrid-manager:")
    assert "compare against the composed draft" in note and "manager/actions/strategy_verify.py" in note
    assert "holds only for a stage that is its draft's only stage, or one that restages every axis" in ECHO["answer"]


def test_the_bodies_compared_left_knobs_out_and_sent_nulls():
    """What an echo could fill in was there to fill: 177 columns (counted per read-back) with no knob key, and keys
    holding null on sections, clauses and level references - each came back as sent."""
    rows = ECHO["readBacks"]
    assert sum(r["columnsSent"] for r in rows) == 177
    assert sum(r["knobKeysSent"] for r in rows) == 0
    nulls = {k for r in rows for k in r["nullKeysSent"]}
    assert {"benchmarkTicker", "marketScope", "sectionKey", "verdict", "exitSide", "bars", "windowExtreme"} <= nulls
    assert "knob key" in ECHO["notCovered"]      # a column sent WITH a knob was never read back: said, not assumed


def test_the_comparison_replays_on_b1s_whole_pair():
    sent, read = B1["sent"]["axes"], B1["readBack"]["content"]
    assert content_sha(sent) == content_sha(read)
    assert json.dumps(sent, sort_keys=True) != json.dumps(read, sort_keys=True)      # raw, they differ ...
    assert B1["readBack"]["comparedWithSent"]["numberSpelling"] == [                   # ... in spelling only
        {"path": "CONDITIONS.conditions[1].definition.value", "sent": 10.0, "read": 10},
        {"path": "CONDITIONS.conditions[2].definition.value", "sent": -10.0, "read": -10}]
    b1_row = next(r for r in ECHO["readBacks"] if r["probe"] == "B1.range_0_8_1_8")
    assert b1_row["sentSha256"] == content_sha(sent) and b1_row["readSha256"] == content_sha(read)
    columns = [c for s in read["REPORT"]["sections"] for c in s["columns"]]
    assert columns and not [k for c in columns for k in KNOBS if k in c]


def test_omega_never_sends_a_knob_it_leaves_unset():
    """omega.types.Column.wire() drops a knob left None, so an omega body names a knob only when the thesis sets it:
    the platform has no knob of omega's to echo."""
    for name, thesis in PRESETS.items():
        for section in plan(thesis).axes()["REPORT"]["sections"]:
            for column in section.get("columns") or []:
                assert all(column[k] is not None for k in KNOBS if k in column), name
