"""scripts/build_corpus.py reconciles while the write surface is ahead of the corpus.

At 148.1.0 (2026-11-05) the derived roster serves 532 keys, the batches hold the 326 measured at 146.0.1 and the 206
added are known by name only (data/contract/metrics/_unmeasured_108.json); categories.json declares structure 362.
build_corpus exited "roster mismatch" before writing anything, so no derived artefact could be regenerated on the
branch until the full re-extraction landed. Only verify() runs here: nothing is written.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_corpus_under_test", ROOT / "scripts" / "build_corpus.py")
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)
CATEGORIES = json.loads((ROOT / "data" / "contract" / "categories.json").read_text(encoding="utf-8"))


def test_the_stored_batches_reconcile_with_the_served_roster(capsys):
    records = bc.merge_metrics()
    bc.verify(records, CATEGORIES)
    assert (len(bc.METRIC_ENUM), len(bc.UNMEASURED), len(bc.MEASURED)) == (532, 206, 326)
    assert "326/532 metrics measured (206 known by name only)" in capsys.readouterr().out


def test_a_missing_measured_metric_still_fails():
    records = bc.merge_metrics()
    records.pop("RSI14")
    with pytest.raises(SystemExit, match="roster mismatch"):
        bc.verify(records, CATEGORIES)


def test_a_family_shortfall_the_unmeasured_do_not_explain_fails():
    records = bc.merge_metrics()
    categories = json.loads(json.dumps(CATEGORIES))
    for c in categories["categories"]:
        if c["category"] == "momentum":
            c["metricCount"] += 1                  # a shortfall no listed unmeasured key accounts for
    with pytest.raises(SystemExit, match="families short"):
        bc.verify(records, categories)


def test_a_measured_metric_listed_unmeasured_fails():
    records = bc.merge_metrics()
    with pytest.raises(SystemExit, match="measured AND listed unmeasured"):
        bc.verify(records, CATEGORIES, set(bc.UNMEASURED) | {"RSI14"})


def test_the_matrix_has_no_column_for_a_served_but_unextracted_transform():
    """`ema` is in the served catalogue (vocabulary/_shared.json) at 148.1.0 and in no metric record: a column for it
    would read legal "no" on all 326 metrics, a false refusal. The matrix stays the extraction's 23 transforms."""
    shared = json.loads((ROOT / "data" / "contract" / "vocabulary" / "_shared.json").read_text(encoding="utf-8"))
    assert "ema" in [t["id"] for t in shared["transforms"]]
    rows = bc.build_composability(bc.merge_metrics(), shared)
    assert "ema" not in {r["transform"] for r in rows} and len(rows) == 326 * 23
