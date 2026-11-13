"""docs/01-metric-layer.md and docs/02-transform-layer.md are GENERATED from the corpus (scripts/build_docs.py: "do not
hand-edit"), so they must be exactly what the generator writes from the pinned corpus - the ledger's M23 found them
still at 108.4.0 (171 metrics, 10 families) at contract 171.0.0 (581 metrics, 14 families), and the generator itself
no longer ran (a transform the hints serve without `emits`), skipped four families and six transforms, and carried
three hand-written claims the corpus had since made false. Regenerate with `python scripts/build_docs.py`.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from omega.contract import CONTRACT_DIR, load

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("build_docs", ROOT / "scripts" / "build_docs.py")
build_docs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_docs)


@pytest.fixture(scope="module")
def contract():
    return load()


@pytest.fixture(scope="module")
def generated(contract):
    return {"01-metric-layer.md": build_docs.metric_layer(contract),
            "02-transform-layer.md": build_docs.transform_layer(contract)}


@pytest.mark.parametrize("name", ["01-metric-layer.md", "02-transform-layer.md"])
def test_the_committed_doc_is_what_the_generator_writes(name, generated):
    assert (ROOT / "docs" / name).read_text(encoding="utf-8") == generated[name], (
        f"docs/{name} is not the generator's output for the pinned corpus: run `python scripts/build_docs.py`")


def test_every_metric_and_family_has_its_row(contract, generated):
    doc = generated["01-metric-layer.md"]
    rows = re.findall(r"^\| `([A-Z0-9_]+)` \| `", doc, flags=re.M)
    assert sorted(rows) == sorted(contract.metrics)
    categories = [c["category"] for c in
                  json.loads((CONTRACT_DIR / "categories.json").read_text(encoding="utf-8"))["categories"]]
    assert {m.family for m in contract.metrics.values()} <= set(categories)
    for family in {m.family for m in contract.metrics.values()}:
        assert f"— `{family}` (" in doc, family
    assert f"{len(contract.metrics)} metrics across {len({m.family for m in contract.metrics.values()})} families" in doc


def test_every_transform_has_its_reference_entry(contract, generated):
    doc = generated["02-transform-layer.md"]
    entries = re.findall(r"^### `([A-Za-z]+)` — ", doc, flags=re.M)
    assert sorted(entries) == sorted(contract.transforms)
    # a transform every metric's own list names is in doc 01's Transforms column order
    assert set(build_docs.transform_order(contract)) == set(contract.transforms)


def test_no_hand_written_claim_outlives_the_corpus(contract, generated):
    """The three paragraphs build_docs.py once hard-coded, each now written only while the corpus says it."""
    doc = generated["02-transform-layer.md"]
    graph = json.loads((ROOT / "data/derived/spread_operand_graph.json").read_text(encoding="utf-8"))
    pairs = {(p["metric"], p["transform"]) for p in
             json.loads((ROOT / "data/derived/platform_privileged.json").read_text(encoding="utf-8"))["pairs"]}
    assert ("`bandTouch` is the mirror case" in doc) == ("bandTouch" not in contract.retired_transforms)
    assert ("`CCI20 × classifyZone` is the subtle one" in doc) == (("CCI20", "classifyZone") in pairs)
    ratio = [n for n in contract.metrics if contract.metric(n).unit == "ratio"]
    assert ("`RVOL` (unit `ratio`) is the lone numeric metric" in doc) == (
        "RVOL" in graph["metricsWithoutSpread"] and ratio == ["RVOL"])
    # 171.0.0: RVOL spreads, in a `ratio` pool of three; a fourth `ratio` metric (MKT_VOL_NET) offers no spread
    assert "RVOL" not in graph["metricsWithoutSpread"] and len(graph["unitPools"]["ratio"]) == 3
    assert sorted(ratio) == ["MKT_VOL_NET", "REGIME_VOL_ATR_RATIO", "REGIME_VOL_BBW_RATIO", "RVOL"]
    # what replaced the RVOL line is counted from the graph
    numeric = sorted(m for m in graph["metricsWithoutSpread"] if contract.metric(m).native_output["kind"] == "numeric")
    assert f"{len(numeric)} of them are numeric" in doc
