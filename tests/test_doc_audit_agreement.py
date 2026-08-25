"""The prose must not drift from the audit record, and neither may contradict a sample.

Written because all three drifted at once and nothing noticed:

  - docs/19 printed "REGIME_VOL normal 30/30, expanding never seen" long after the audit
    JSON had moved `expanding` to seen. I then re-observed `expanding` at a 4h anchor and
    reported it as a discovery. It was a third sighting of an already-recorded fact.
  - the JSON, docs/19 and docs/06 ALL claimed `OI_VELOCITY` never reads `steady`, while
    data/samples/tier_c_drivers_1h.md - committed to this repo the same day - contains
    nine of them. A claim invalidated by a commit to the same repository.

data/audit/tier_c_coherence.json['unobservedLabels'] is the source of truth. These tests
bind the docs to it, and bind it to the samples.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from omega import contract as C
from scripts.unobserved_table import NO_VOCABULARY, render, still_unobserved, tracked

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["docs/19-is-the-data-correct.md", "docs/06-cookbook.md"]

# Which column of data/samples/tier_c_drivers_1h.md carries which metric. Explicit rather
# than inferred: a wrong guess here would make the test pass for the wrong reason.
SAMPLE_COLUMNS = {
    "regMom": "REGIME_MOM",
    "oiVel": "OI_VELOCITY",
    "conf": "CONFIDENCE",
    "flowAlign": "FLOW_ALIGN",
    "smartRetail": "SMART_RETAIL",
    "perpSpotStr": "PERP_SPOT_STRENGTH",
}


@pytest.fixture(scope="module")
def contract():
    return C.load()


def _sample_observations() -> dict[str, Counter]:
    """metric -> Counter of the label values actually rendered, per markdown sample."""
    out: dict[str, Counter] = {}
    for path in sorted((ROOT / "data/samples").glob("*.md")):
        lines = [l for l in path.read_text(encoding="utf-8").splitlines()
                 if l.startswith("|")]
        head = [c.strip() for c in lines[0].strip("|").split("|")]
        for line in lines[2:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            for col, val in zip(head, cells):
                metric = SAMPLE_COLUMNS.get(col)
                if metric and val != "—":
                    out.setdefault(metric, Counter())[val] += 1
    return out


@pytest.mark.parametrize("rel", DOCS)
def test_doc_table_matches_the_audit_record(rel):
    """The rendered table must appear verbatim. Regenerate with scripts.unobserved_table."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert render() in text, (
        f"{rel} has drifted from data/audit/tier_c_coherence.json. "
        f"Run `python -m scripts.unobserved_table` and paste the result in.")


@pytest.mark.parametrize("rel", DOCS)
def test_doc_has_exactly_one_such_table(rel):
    """A second copy would drift the moment the first is regenerated."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert len(re.findall(r"\| metric \| seen \| never seen \|", text)) == 1


def test_no_unseen_label_appears_in_a_stored_sample():
    """The claim that has actually broken. A sample in this repo is the counter-example."""
    observed = _sample_observations()
    violations = [
        f"{metric}.{label!r} is recorded unseen but appears "
        f"{observed[metric][label]}x in data/samples/"
        for metric, label in still_unobserved()
        if metric in observed and observed[metric][label]
    ]
    assert not violations, "\n".join(violations)


def test_seen_labels_are_actually_in_the_contract_vocabulary(contract):
    """A typo in `seen` would silently shrink the unobserved list."""
    for name, rec in tracked().items():
        if name in NO_VOCABULARY:
            continue
        vocab = set(contract.metric(name).vocab or [])
        assert vocab, f"{name} has no conditionVocabulary; add it to NO_VOCABULARY"
        assert set(rec["seen"]) | set(rec["unseen"]) == vocab, (
            f"{name}: seen+unseen does not partition the contract vocabulary")


def test_no_vocabulary_exceptions_are_genuine(contract):
    """NO_VOCABULARY must stay an accurate list, not a place to hide failures."""
    for name in NO_VOCABULARY:
        assert not contract.metric(name).vocab, (
            f"{name} now has a conditionVocabulary; remove it from NO_VOCABULARY "
            f"so the partition check covers it")


def test_recorded_distributions_do_not_contradict_the_record():
    """tier_c_rule_search.json carries measured distributions; they must agree too."""
    search = json.loads((ROOT / "data/audit/tier_c_rule_search.json").read_text(
        encoding="utf-8"))
    unseen = {(m, l) for m, l in still_unobserved()}
    for result in search["results"]:
        metric = result["metric"].split(" ")[0]
        for label in result["distribution"]:
            assert (metric, label) not in unseen, (
                f"{metric}.{label!r} is recorded unseen but the rule search measured "
                f"{result['distribution'][label]} of them")


def test_the_remaining_gap_is_stated_accurately():
    """Guards the count quoted in prose - it has been misstated in conversation."""
    remaining = still_unobserved()
    assert len(remaining) == 6, "8 before the 2026-08-26 anchor sweep closed two"
    assert len({m for m, _ in remaining}) == 4
    # the two the sweep closed, pinned so a regression is visible
    closed = {(m, l) for m, l in remaining}
    assert ("PERP_SPOT_CONFIRMS", "true") not in closed
    assert ("PERP_SPOT_FLOW", "confirmed_bear") not in closed
