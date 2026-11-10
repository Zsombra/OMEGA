"""The 2026-11-09/10 coverage sweep at contract 161.0.0, as recorded.

The structural sweep over the 15,876 shapes the 161.0.0 refresh opened ran on evaluated-coin sections with no metric
restriction (31,620 s, 125 batches). Every shape on a metric a coin section reads rendered as omega.fanout predicted.
The 1,289 refusals are the thirteen MKT_* (92 shapes each) and PAR_DEV (93) sent on a coin section, which reads none of
them; the sweep had no subject filter until 2026-11-10 (scripts/sweep_render_coverage.collect_targets). These pins hold
the evidence as written, and prove the refusals are exactly the subject refusals omega.validate predicts.
"""
import json
from collections import Counter
from pathlib import Path

from omega.contract import load
from scripts.render_coverage import CACHE, SEEN_FILES

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "data" / "audit" / "coverage_sweep_2026-11-09.json"
HEADERS = CACHE / "_coverage_sweep_2026-11-09.json"
MKT = {"MKT_ABOVE_EMA", "MKT_AVG_CHG", "MKT_AVG_PPO", "MKT_DISPERSION", "MKT_DOWN", "MKT_NET", "MKT_PPO_DOWN",
       "MKT_PPO_NET", "MKT_PPO_UP", "MKT_STRETCH", "MKT_UNIVERSE", "MKT_UP", "MKT_VOL_NET"}


def _record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_the_sweep_ran_complete_at_161_on_coin_sections():
    r = _record()
    assert r["complete"] is True and r["aborted"] is None and r["contractMoved"] is False
    assert r["contractVersion"] == r["versionAtEnd"] == "161.0.0"
    assert r["scope"] == "structural" and r["marketScope"] is None and r["benchmarkTicker"] is None
    assert r["metricsRestrictedTo"] is None
    assert (r["shapesTargeted"], r["shapesRequested"], r["headersMinted"]) == (15876, 15876, 14623)
    assert len(r["batches"]) == 125 and sum(b["columns"] for b in r["batches"]) == 15876


def test_every_refusal_is_a_subject_refusal_omega_predicts():
    r = _record()
    c = load()
    assert r["refusalCount"] == len(r["refusals"]) == 1289
    by_metric = Counter(x["column"]["metric"] for x in r["refusals"])
    assert by_metric == {**{m: 92 for m in MKT}, "PAR_DEV": 93}
    assert all("evaluated-coin section cannot carry this column" in x["error"] for x in r["refusals"])
    # the platform refused exactly the metrics no coin section reads, and none that one does
    assert not any(c.metric(m).reads_on("evaluated-coin") for m in by_metric)
    # predicted-but-not-rendered is the same refused set (the list is capped at 200 in the record)
    assert r["predictedButNotRenderedCount"] == 1289
    assert {x["shape"].split("|")[0] for x in r["predictedButNotRendered"]} <= set(by_metric)


def test_the_headers_cache_is_read_as_rendered():
    doc = json.loads(HEADERS.read_text(encoding="utf-8"))
    assert set(doc) == {"_what", "headers"} and len(doc["headers"]) == 14623 == len(set(doc["headers"]))
    hs = set(doc["headers"])
    assert {"VWMA20", "ADX14_cci20_roc9"} <= hs
    assert "_coverage_sweep_2026-11-09.json" in SEEN_FILES
