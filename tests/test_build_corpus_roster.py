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
    # (532, 206, 326) from 2026-11-05 until the refresh at 149.1.0 on 2026-11-07 folded the 206 in
    # 161.0.0 (2026-11-09): 534 (BB_TOUCH retired, three added); 168.3.0 (2026-11-11): 581 (47 added, _moves_168.json) -
    # the roster is now the read schema's enum (condition_vocabulary_108.json reportColumn.metric.enumSource)
    assert (len(bc.METRIC_ENUM), len(bc.UNMEASURED), len(bc.MEASURED)) == (581, 0, 581)
    assert "581/581 metrics measured;" in capsys.readouterr().out


def test_a_missing_measured_metric_still_fails():
    records = bc.merge_metrics()
    records.pop("RSI14")
    with pytest.raises(SystemExit, match="roster mismatch"):
        bc.verify(records, CATEGORIES)


def test_a_family_shortfall_the_unmeasured_do_not_explain_fails():
    """Since 2026-11-07 no key is unmeasured, so any shortfall is unexplained; the check still fires."""
    records = bc.merge_metrics()
    categories = json.loads(json.dumps(CATEGORIES))
    for c in categories["categories"]:
        if c["category"] == "momentum":
            c["metricCount"] += 1                  # a shortfall no listed unmeasured key accounts for
    with pytest.raises(SystemExit, match="family 'momentum'"):
        bc.verify(records, categories)


def test_a_family_shortfall_the_listed_unmeasured_do_not_explain_fails():
    """The branch the test above was written for (until 2026-11-07, when UNMEASURED emptied): with a key listed
    unmeasured, a shortfall larger than the unmeasured count is still refused (review 2026-11-08: no test reached it)."""
    records = bc.merge_metrics()
    records.pop("RSI14")
    categories = json.loads(json.dumps(CATEGORIES))
    for c in categories["categories"]:
        if c["category"] == "momentum":
            c["metricCount"] += 1
    with pytest.raises(SystemExit, match="families short"):
        bc.verify(records, categories, {"RSI14"})


def test_a_measured_metric_listed_unmeasured_fails():
    records = bc.merge_metrics()
    with pytest.raises(SystemExit, match="measured AND listed unmeasured"):
        bc.verify(records, CATEGORIES, set(bc.UNMEASURED) | {"RSI14"})


def test_the_matrix_has_no_column_for_a_served_but_unextracted_transform():
    """A transform in the served catalogue (vocabulary/_shared.json) that no extracted record carries would read legal
    "no" on every metric, a false refusal - so the matrix takes only the extraction's catalogue. `ema` was that case
    from 2026-11-05 (148.1.0) until the 2026-11-07 refresh; a served id with no catalogue entry still gets no column."""
    shared = json.loads((ROOT / "data" / "contract" / "vocabulary" / "_shared.json").read_text(encoding="utf-8"))
    ids = [t["id"] for t in shared["transforms"]]
    assert {"ema", "rma", "wma", "rsi", "cci"} <= set(ids) and len(ids) == 29   # 161.0.0 (2026-11-09): roc added (29 catalogue ids)
    rows = bc.build_composability(bc.merge_metrics(), shared)
    assert {"ema", "rma", "wma", "rsi", "cci"} <= {r["transform"] for r in rows} and len(rows) == 581 * 29   # 161.0.0 (2026-11-09): 534 metrics x 29 transforms; 168.3.0 (2026-11-11): 581 x 29
    fake = json.loads(json.dumps(shared))
    fake["transforms"].append({"id": "notExtracted", "label": "x"})
    assert "notExtracted" not in {r["transform"] for r in bc.build_composability(bc.merge_metrics(), fake)}
