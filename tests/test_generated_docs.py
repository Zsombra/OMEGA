"""docs/01-metric-layer.md and docs/02-transform-layer.md are GENERATED from the corpus (scripts/build_docs.py: "do not
hand-edit"), so they must be exactly what the generator writes from the pinned corpus - the ledger's M23 found them
still at 108.4.0 (171 metrics, 10 families) at contract 171.0.0 (581 metrics, 14 families), and the generator itself
no longer ran (a transform the hints serve without `emits`), skipped four families and six transforms, and carried
three hand-written claims the corpus had since made false. Regenerate with `python scripts/build_docs.py`.
"""
from __future__ import annotations

import dataclasses
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
    assert ("`bandTouch` is the mirror case" in doc) == build_docs.band_touch_note_holds(contract, pairs)
    assert ("`CCI20 × classifyZone` is the subtle one" in doc) == build_docs.cci20_zone_note_holds(contract, pairs)
    ratio = [n for n in contract.metrics if contract.metric(n).unit == "ratio"]
    assert ("`RVOL` (unit `ratio`) is the lone numeric metric" in doc) == (
        "RVOL" in graph["metricsWithoutSpread"] and ratio == ["RVOL"]
        and contract.metric("RVOL").native_output["kind"] == "numeric")
    # 171.0.0: RVOL spreads, in a `ratio` pool of three; a fourth `ratio` metric (MKT_VOL_NET) offers no spread
    assert "RVOL" not in graph["metricsWithoutSpread"] and len(graph["unitPools"]["ratio"]) == 3
    assert sorted(ratio) == ["MKT_VOL_NET", "REGIME_VOL_ATR_RATIO", "REGIME_VOL_BBW_RATIO", "RVOL"]
    # what replaced the RVOL line is counted from the graph
    numeric = sorted(m for m in graph["metricsWithoutSpread"] if contract.metric(m).native_output["kind"] == "numeric")
    assert f"{len(numeric)} of them are numeric" in doc
    # 171.0.0: of the CCI20 note only CCI20's missing range still holds, and bandTouch is retired
    assert ("CCI20", "classifyZone") not in pairs and contract.metric("CCI20").offers("classifyZone")
    assert not contract.metric("CCI20").native_output.get("range")
    assert "bandTouch" in contract.retired_transforms


def _first_extraction_like(contract):
    """The pinned corpus changed only where the first extraction (2026-08-24) differed for the two notes: CCI20 not
    offered classifyZone, classifyZone offered only on bounded oscillators, bandTouch served on SMA20 - and the
    privileged pairs with CCI20 x classifyZone."""
    metrics = {}
    for name, m in contract.metrics.items():
        transforms = dict(m.transforms)
        if name == "CCI20" or not (m.native_output.get("unit") == "oscillator" and m.native_output.get("range")):
            transforms.pop("classifyZone", None)
        if name == "SMA20":
            transforms["bandTouch"] = {"id": "bandTouch"}
        metrics[name] = dataclasses.replace(m, transforms=transforms)
    retired = {k: v for k, v in contract.retired_transforms.items() if k != "bandTouch"}
    return (dataclasses.replace(contract, metrics=metrics, retired_transforms=retired),
            {("CCI20", "classifyZone"), ("ADX", "classifyState")})


def _with_metric(corpus, name, **changes):
    return dataclasses.replace(corpus, metrics={**corpus.metrics,
                                                name: dataclasses.replace(corpus.metrics[name], **changes)})


def _with_template_column(corpus, column):
    template = {"sectionKey": "includeProbe", "title": "probe", "columns": [column]}
    return dataclasses.replace(corpus, platform_templates={**corpus.platform_templates, "includeProbe": template})


def test_each_note_is_written_only_while_every_clause_holds(contract):
    """Review 2026-11-13: the two notes' conditions read part of each sentence. Each clause is now checked: on a corpus
    where all hold both notes are written, and each clause made false alone withholds its note (and the bandTouch
    note, the CCI20 note's mirror, with it)."""
    held, pairs = _first_extraction_like(contract)
    assert build_docs.cci20_zone_note_holds(held, pairs) and build_docs.band_touch_note_holds(held, pairs)
    cci20 = held.metrics["CCI20"]
    oscillator = held.metrics["RSI14"]
    cvd, breadth = held.metrics["CVD"], held.metrics["MKT_ABOVE_EMA"]
    cci20_clauses = {
        "the platform reserves the pair": (held, pairs - {("CCI20", "classifyZone")}),
        "CCI20's nativeOutput carries no range": (
            _with_metric(held, "CCI20", native_output={**cci20.native_output, "range": {"min": -200, "max": 200}}), pairs),
        "no zone policy exposed to authors": (
            _with_metric(held, "CCI20", transforms={**cci20.transforms, "classifyZone": {"id": "classifyZone"}}), pairs),
        "classifyZone classifies a bounded reading": (
            _with_metric(held, "CVD", transforms={**cvd.transforms, "classifyZone": {"id": "classifyZone"}}), pairs),
        "classifyZone classifies an oscillator": (
            _with_metric(held, "MKT_ABOVE_EMA", transforms={**breadth.transforms, "classifyZone": {"id": "classifyZone"}}),
            pairs),
        "classifyZone is authorable at all": (
            dataclasses.replace(held, metrics={n: dataclasses.replace(m, transforms={
                k: v for k, v in m.transforms.items() if k != "classifyZone"}) for n, m in held.metrics.items()}), pairs),
    }
    assert breadth.native_output.get("range") and breadth.native_output.get("unit") != "oscillator"
    assert oscillator.offers("classifyZone") and not cvd.native_output.get("range")
    for clause, (corpus, privileged) in cci20_clauses.items():
        assert not build_docs.cci20_zone_note_holds(corpus, privileged), clause
        assert not build_docs.band_touch_note_holds(corpus, privileged), clause
    sma20, retired = held.metrics["SMA20"], contract.retired_transforms["bandTouch"]
    band_touch_clauses = {
        "served: not retired": dataclasses.replace(held, retired_transforms={**held.retired_transforms,
                                                                            "bandTouch": retired}),
        "served: not unmeasured": dataclasses.replace(held, unmeasured_transforms={"bandTouch": {}}),
        "in the catalogue": dataclasses.replace(held, transforms={k: v for k, v in held.transforms.items()
                                                                  if k != "bandTouch"}),
        "fully authorable: offered on a metric": _with_metric(
            held, "SMA20", transforms={k: v for k, v in sma20.transforms.items() if k != "bandTouch"}),
        "used by zero platform templates": _with_template_column(
            held, {"metric": "SMA20", "timeframe": {"rel": "anchor"}, "transformId": "bandTouch"}),
        "used by zero platform templates, chained": _with_template_column(
            held, {"metric": "SMA20", "timeframe": {"rel": "anchor"}, "transformId": "distance",
                   "chainedTransformId": "bandTouch"}),
    }
    for clause, corpus in band_touch_clauses.items():
        assert build_docs.cci20_zone_note_holds(corpus, pairs), clause
        assert not build_docs.band_touch_note_holds(corpus, pairs), clause
    # fully authorable: reserved for the platform on no metric
    assert not build_docs.band_touch_note_holds(held, pairs | {("SMA20", "bandTouch")})
