"""The 2026-11-07 coverage sweep at contract 149.1.0, as recorded, and the served-subject reader it ran on.

The sweep rendered the structural shapes of the 206 keys v146.5 / .8 / .10 / .11 added, on evaluated-coin sections,
against the corpus refreshed from the 532 hints read at 149.1.0 on 2026-11-06 (the refresh itself lands with the model
changes; docs/plans/2026-11-05-omega-reextraction-148.md, stage 2). These pins hold the evidence as written.
"""
import json
from pathlib import Path

from omega.contract import _primary_subject
from scripts.render_coverage import CACHE, SEEN_FILES, _walk

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "data" / "audit" / "coverage_sweep_2026-11-07-structural.json"
HEADERS = CACHE / "_coverage_sweep_2026-11-07-structural.json"


def _record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_the_sweep_ran_complete_with_no_refusal_and_no_misprediction():
    r = _record()
    assert r["complete"] is True and r["aborted"] is None
    assert r["scope"] == "structural" and r["marketScope"] is None and r["benchmarkTicker"] is None
    assert (r["shapesTargeted"], r["shapesRequested"], r["headersMinted"]) == (557, 557, 565)
    assert r["refusalCount"] == 0 and r["refusals"] == []
    assert r["predictedButNotRenderedCount"] == 0 and r["predictedButNotRendered"] == []
    assert [b["columns"] for b in r["batches"]] == [128, 128, 128, 128, 45]


def test_the_sweep_was_restricted_to_the_206_added_keys():
    r = _record()
    unmeasured = json.loads((ROOT / "data" / "contract" / "metrics" / "_unmeasured_108.json")
                            .read_text(encoding="utf-8"))
    assert sorted(r["metricsRestrictedTo"]) == sorted(unmeasured["metrics"])
    assert len(r["metricsRestrictedTo"]) == 206


def test_the_headers_cache_carries_the_new_families_and_is_read_as_rendered():
    doc = json.loads(HEADERS.read_text(encoding="utf-8"))
    assert set(doc) == {"_what", "headers"} and len(doc["headers"]) == 565 == len(set(doc["headers"]))
    hs = set(doc["headers"])
    assert {"eqh", "dist_pivotCamR2", "dist_iStructLvl_now"} <= hs
    assert "_coverage_sweep_2026-11-07-structural.json" in SEEN_FILES
    assert "_probe_149_2026-11-07.json" in SEEN_FILES
    seen = set()
    _walk(doc, seen)
    assert hs <= seen


def test_the_primary_subject_is_read_from_the_served_subject_kinds():
    # The five served combinations at 149.1.0 (data/audit/hints_149_1_0_2026-11-06.json subjectKinds).
    assert _primary_subject(["benchmark", "evaluated-coin"]) == "evaluated-coin"
    assert _primary_subject(["evaluated-coin"]) == "evaluated-coin"
    assert _primary_subject(["market"]) == "market"
    assert _primary_subject(["benchmark", "evaluated-coin", "reference"]) == "evaluated-coin"
    assert _primary_subject(["reference"]) == "reference"
    # A pre-148 record serves none: the 146 measurement (_subjects_146.json) applies instead.
    assert _primary_subject(None) is None and _primary_subject([]) is None
