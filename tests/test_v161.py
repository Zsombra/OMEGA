"""OMEGA v0.12 at contract 161.0.0 (2026-11-09): what 150 - 161 moved for the authoring surface.

The README's "Contract history" documents v150 - v156; 157 - 161 are undocumented, so the served write schema
(data/contract/stage_strategy_draft/schema_20261109T162100Z.json), the 534 raw hints read at 161.0.0 and the probe
(data/audit/authoring_probe_161_2026-11-09.json) are the sources.
"""
from __future__ import annotations

import json

import pytest

from omega.conditions import LIVE_CROWD_METRICS, condition, num, validate_conditions
from omega.contract import CONTRACT_DIR
from omega.fanout import outputs_for
from omega.types import Column, CustomSection, Report

SECTION_KEY = "custom:18c11ae8-bb26-5025-a01c-957043d42445"


def _report(*specs, anchor="1h") -> Report:
    return Report(anchor=anchor, sections=[CustomSection(
        title="T", sectionKey=SECTION_KEY, benchmarkTicker=None,
        columns=[Column.model_validate(s) for s in specs])])


def _col(metric, **kw):
    return {"metric": metric, "transformId": "value", "timeframe": {"rel": "anchor"}, **kw}


# --- v156: a condition on a live crowd reading is refused -----------------------------------------------------------

def test_the_eight_live_crowd_metrics_are_the_readmes_eight_codes():
    codes = {json.loads((CONTRACT_DIR / "metrics" / f"{m}.json").read_text(encoding="utf-8"))["code"]
             for m in LIVE_CROWD_METRICS}
    assert codes == {"pickLive", "upBiasLive", "crowdAccLive", "captRateLive", "upLeanZLive", "upExcessZLive",
                     "captExcessZLive", "accEdgeZLive"}


@pytest.mark.parametrize("metric", sorted(LIVE_CROWD_METRICS))
def test_a_condition_on_a_live_crowd_header_is_refused(metric):
    report = _report(_col(metric))
    header = outputs_for(Column.model_validate(_col(metric)))[0].header
    found = validate_conditions(report, [condition("LIVE_ONE", "on the live crowd", num(header, "gt", 0.5),
                                                   verdict="LONG")])
    errors = [f for f in found if f.severity == "error"]
    assert any("CONDITION_OPERAND_UNSERVABLE" in f.message for f in errors), found


def test_the_settled_twin_and_the_live_column_itself_are_not_refused():
    report = _report(_col("CROWD_PICK"), _col("CROWD_PICK_LIVE"))
    header = outputs_for(Column.model_validate(_col("CROWD_PICK")))[0].header
    found = validate_conditions(report, [condition("SETTLED", "on the settled crowd", num(header, "gt", 0.5),
                                                   verdict="LONG")])
    assert not any("CONDITION_OPERAND_UNSERVABLE" in f.message for f in found)


# --- the depth probes at 161.0.0 (2026-11-09): omega agrees with the platform's own maxima ---------------------------

def test_omega_agrees_with_the_161_depth_probes():
    """The readable depth is 2500 bars (2436 less the 64-bar lookback budget): the K.RSI14.roc.* and O.* probes sit on
    each served maximum (accepted) and one past it (refused REPORT_COLUMN_DEPTH_EXCEEDED). omega judges both sides the same
    way, from the corpus's served maxima. (The N.* chained-window probes rendered one past the served maximum: see
    test_omega_agrees_with_every_answer_of_the_161_probe, and tests/test_v0_12_2.py for the joint bound they sit in.)"""
    from pathlib import Path

    from omega.contract import load
    from omega.validate import validate_section
    ROOT = Path(__file__).resolve().parents[1]
    contract = load()
    probes = [p for p in json.loads((ROOT / "data/audit/authoring_probe_161_2026-11-09.json").read_text(encoding="utf-8"))["probes"]
              if p["probe"].startswith("O.") or p["probe"] in ("K.RSI14.roc.max", "K.RSI14.roc.over")]
    assert len(probes) == 16
    for p in probes:
        errors = []
        for sent in p["sections"]:
            section = CustomSection(title="t", benchmarkTicker=sent.get("benchmarkTicker"),
                                    marketScope=sent.get("marketScope"), columns=sent["columns"])
            errors += [f.code for f in validate_section(section, contract=contract) if f.severity == "error"]
        if p["accepted"]:
            assert errors == [], p["probe"]
        else:
            assert p["refusal"]["authoringCode"] == "REPORT_COLUMN_DEPTH_EXCEEDED"
            assert errors == ["DEPTH_EXCEEDED"], (p["probe"], errors)


# --- every answer of the 161.0.0 probe, replayed through omega (2026-11-10, review of the 161 step) ------------------

# Each refused probe -> the omega finding that refuses it. "TYPE" = the column / report type refuses it at construction
# (pydantic: `buffer` <= 500, the four authorable anchors).
REFUSED_161 = {
    "K.RSI14.roc.over": ["DEPTH_EXCEEDED"], "K.RSI14.roc.offset1": ["OFFSET_REFUSED"],
    "K.PIVOT_WEEK_P.roc": ["REPORT_COLUMN_PAIR_UNSUPPORTED"], "L.accept": ["REPORT_COLUMN_PAIR_UNSUPPORTED"],
    "L.accept#0": ["REPORT_COLUMN_PAIR_UNSUPPORTED"],
    "M.both.buffer.touchAtr": ["TOUCH_ATR_AND_BUFFER"], "M.offset0": ["OFFSET_BELOW_MINIMUM"], "M.buffer501": "TYPE",
    "N.spread.chainedWindow": ["CHAINED_WINDOW_REFUSED"],
    **{f"O.{k}.over": ["DEPTH_EXCEEDED"] for k in ("RSI14.aggregate", "CLOSE.ema", "RSI14.rma", "RSI14.zscore",
                                                   "RSI14.pctl", "CLOSE.rollingMax", "HIGH.distance.ema")},
    "P.ASIA_HIGH.abs4h": ["REPORT_COLUMN_OPERAND_UNSUPPORTED"], "P.ASIA_HIGH.lower": ["REPORT_COLUMN_OPERAND_UNSUPPORTED"],
    "P.ASIA_HIGH.offset1": ["OFFSET_REFUSED"], "P.EMA20.offset1": ["OFFSET_REFUSED"],
    "P.ASIA_HIGH.chain.aggregate": ["REPORT_COLUMN_CHAIN_UNSUPPORTED"],
    "S.BB_TOUCH": ["METRIC_RETIRED"],
    "T.BB_UPPER.buffer501": "TYPE", "T.BB_UPPER.both": ["TOUCH_ATR_AND_BUFFER"],
    "T.BB_UPPER.touchAtr.on.value": ["TOUCH_ATR_UNDECLARED"],
    "U.crowd.1d": "TYPE",
}


def _rendered_names(render) -> set:
    out = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("header", "key") and isinstance(v, str):
                    out.add(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(render)
    return out


def test_omega_agrees_with_every_answer_of_the_161_probe():
    """63 previews at 161.0.0: every accepted one validates with no error (bar the duplicate header the platform itself
    flags in `duplicateHeaders`) and renders every header omega.fanout predicts; every refused one is refused by omega
    with the finding above. N.chainedWindow.over / N.innerWindow.over rendered one past the served maximum, and omega
    has no finding there (see the end of the test)."""
    from pathlib import Path

    from pydantic import ValidationError

    from omega.contract import load
    from omega.validate import validate_section
    contract = load()
    root = Path(__file__).resolve().parents[1]
    probes = json.loads((root / "data/audit/authoring_probe_161_2026-11-09.json").read_text(encoding="utf-8"))["probes"]
    assert len(probes) == 63
    refused_seen, warned = set(), {}
    for p in probes:
        expect = REFUSED_161.get(p["probe"])
        if expect == "TYPE":
            assert not p["accepted"]
            with pytest.raises(ValidationError):
                Report(anchor=p["timeframe"], sections=[CustomSection(
                    title="t", benchmarkTicker=s.get("benchmarkTicker"), marketScope=s.get("marketScope"),
                    columns=s["columns"]) for s in p["sections"]])
            refused_seen.add(p["probe"])
            continue
        errors, predicted = [], set()
        for s in p["sections"]:
            section = CustomSection(title="t", benchmarkTicker=s.get("benchmarkTicker"),
                                    marketScope=s.get("marketScope"), columns=s["columns"])
            for f in validate_section(section, contract=contract):
                if f.severity == "error":
                    errors.append(f.code)
                else:
                    warned.setdefault(p["probe"], []).append(f.code)
            if p["accepted"]:      # a refused column has no header to predict (BB_TOUCH is not in the corpus)
                for col in section.columns:
                    predicted |= {o.header for o in outputs_for(col, contract)}
        if p["accepted"]:
            flagged = bool((p["render"] or {}).get("duplicateHeaders"))
            assert errors == (["DUPLICATE_HEADER"] if flagged else []), p["probe"]
            assert predicted <= _rendered_names(p["render"]), (p["probe"], sorted(predicted - _rendered_names(p["render"])))
        else:
            assert errors == expect, (p["probe"], errors)
            refused_seen.add(p["probe"])
    assert refused_seen == set(REFUSED_161), "every refused probe is listed, and every listed one was refused"
    # Re-pinned at v0.12.2 (2026-11-11): these two were asserted to WARN, on the reading that one past a served maximum
    # is past a limit whose real place was unmeasured. Measured since (data/audit/authoring_limits_161_2026-11-11.json):
    # the limit is one joint bar count, need(inner, window) + need(outer, chainedWindow) - 1 <= 2436, and both cases sit
    # inside it (window 14 + chainedWindow 2365 reads 2416 bars, window 698 + chainedWindow 5 reads 2419), which is why
    # they rendered. Inside the bound omega has no finding at all, so the per-window warning is gone.
    for inside in ("N.chainedWindow.max", "N.chainedWindow.over", "N.innerWindow.max", "N.innerWindow.over"):
        assert inside not in warned, (inside, warned[inside])


def test_the_manifest_records_the_161_extraction():
    """The top-level extraction block moved to 161.0.0 on 2026-11-10 (it had stayed at 146.0.1 through the 149.1.0 model
    step); its counts are measured on the corpus, the 146.0.1 block sits under `supersedes`."""
    from omega import space
    from omega.contract import load
    current = json.loads((CONTRACT_DIR / "_manifest.json").read_text(encoding="utf-8"))
    # 2026-11-11, contract 168.3.0 (extraction 20261111): the top-level block is the 168.3.0 extraction now and the
    # 161.0.0 block is its `supersedes` (146.0.1 one level deeper than it was). The live corpus is the 168 one, so the
    # 161 block's counts are re-measured on the 161.0.0 batches the refresh archived (archive_20261109_extraction);
    # its structuralShapes (25,915, enumerated on the corpus until 2026-11-11) stays as recorded - no loader reads an
    # archive. The measured-on-the-live-corpus check moves to the 168.3.0 block, below.
    # 2026-11-12, contract 169.4.0 (extraction 20261112): one level deeper again - the 169.4.0 re-read on top (the corpus
    # did not move), 168.3.0 its `supersedes`, the 161.0.0 block below that; tests/test_v169.py pins the top block
    # (171.0.0 on top later that morning: by version from here on, tests/manifest_chain.py)
    from tests.manifest_chain import extraction
    assert current["servedContractVersion"] == "171.0.0"
    current = extraction("168.3.0", current)
    assert current["extractedOn"] == "2026-11-11"
    m = current["supersedes"]
    assert (m["servedContractVersion"], m["extractedOn"]) == ("161.0.0", "2026-11-09")
    assert "ab5b62526574ed62c7c3f5d2d1865f882e37b1a7" in m["contractVersionSource"]
    assert m["supersedes"]["servedContractVersion"] == "146.0.1"
    archive = CONTRACT_DIR / "metrics" / "archive_20261109_extraction"
    archived = [r for p in sorted(archive.glob("_batch*.json")) for r in json.loads(p.read_text(encoding="utf-8"))]
    n = m["counts"]
    assert (n["metrics"], n["families"], n["authorableTransforms"]) == (
        len({r["metric"] for r in archived}), len({r["family"] for r in archived}), 30) == (534, 11, 30)
    assert (n["composabilityCells"], n["composabilityLegal"]) == (
        534 * 30, sum(len(r["transforms"]) for r in archived)) == (16020, 4493)
    assert n["structuralShapes"] == 25915
    # the 168.3.0 block: every count measured on the live corpus, as the 161 block's were until 2026-11-11. 47 keys
    # added and none retired (_moves_168.json) -> 581; three categories split out of structure -> 14 families; the
    # chained `spread` 168 serves is unmeasured and in no shape (the block's own _note)
    c = load()
    assert "af8b2c9632fa71620e9dcc1802904ee963d305a4" in current["contractVersionSource"]
    moves = json.loads((CONTRACT_DIR / "metrics" / "_moves_168.json").read_text(encoding="utf-8"))
    assert set(c.metrics) - {r["metric"] for r in archived} == set(moves["added"]) and len(moves["added"]) == 47
    assert {r["metric"] for r in archived} <= set(c.metrics) and moves["retired"] == []
    legal = sum(len(x.transforms) for x in c.metrics.values())
    n = current["counts"]
    assert (n["metrics"], n["families"], n["authorableTransforms"]) == (
        len(c.metrics), len({x.family for x in c.metrics.values()}), len(c.transforms)) == (581, 14, 30)
    assert (n["composabilityCells"], n["composabilityLegal"]) == (len(c.metrics) * len(c.transforms), legal) == (17430, 4735)
    # the 168.3.0 block's structuralShapes stays as recorded: the space has held the chained spread's 660 shapes since
    # 2026-11-12 (OMEGA v0.13.1), when nothing was unmeasured any more
    assert n["structuralShapes"] == 26584 == sum(1 for _ in space.enumerate_shapes(expand_operands=False, contract=c)) - 660
    assert c.unmeasured_chain_outers == {}
