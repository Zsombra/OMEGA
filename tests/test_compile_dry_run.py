"""The first-ever compile of a GENERATED plan, 2026-08-28: refused, twice, informatively.

Two calls, the plan's hard cap, each on a materially different payload:

  1. sections carried omega's deterministic custom:<uuid5> sectionKeys
     -> REPORT_CUSTOM_SECTION_NOT_OWNED, allowedDomain enum [].
     A CREATE cannot claim section identities; the server mints them. Omega gap, fixed.
  2. sectionKeys stripped (12,210-byte plan)
     -> "Strategy report preview mcp_result_bytes limit exceeded: 395404 > 256000".
     The 256,000-byte cap the tool doc attaches to THE SERIALIZED PLAN was enforced
     against the compile's internal report preview across coinSelection ranked/ALL/30.
     A rule nobody published -> BG-14.

Neither refusal was the schema-derived keyMismatch this dry-run set out to test: the
reshaped CREATE body itself drew no unrecognized_keys and no missing-required either
time. These tests pin the records so drift in wire() or a quiet edit to the audit files
fails loudly.

Later the same day, with the user's explicit go-ahead for one more call, the SAME plan
was compiled with an explicit 3-ticker selection - the only fields changed from the
refused payload were coinSelection and its assumption string - and came back
**viable: true**: the first generated plan ever to compile viable. That record
(compile_dry_run_2026-08-28-small.json) is pinned below too. The token was left to
expire; apply_strategy_plan was never called.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from omega.generate import CADENCE_FOR_ANCHOR, PRESETS, REGIME_TF_FOR_ANCHOR, plan
from scripts.compile_dry_run import PRESET, SMALL_TICKERS, request

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads(
    (ROOT / "data/audit/compile_dry_run_2026-08-28.json").read_text(encoding="utf-8"))
ATTEMPT1 = json.loads(
    (ROOT / "data/audit/compile_dry_run_2026-08-28-refusal.json").read_text(encoding="utf-8"))
SMALL = json.loads(
    (ROOT / "data/audit/compile_dry_run_2026-08-28-small.json").read_text(encoding="utf-8"))


def test_the_record_exists_and_is_interpreted():
    for rec in (RECORD, ATTEMPT1):
        assert rec["verdict"] == "refused"
        assert "FILL IN" not in rec["_interpretation"]


def test_request_keys_match_current_wire_output():
    """If wire() gains or loses a top-level key, the recorded measurement no longer
    describes the current generator - this failing is the reminder to re-measure."""
    assert RECORD["requestKeys"] == sorted(request()["request"].keys())
    assert RECORD["preset"] == PRESET


def test_attempt_1_pinned_the_section_ownership_rule():
    d = ATTEMPT1["responseVerbatim"]["details"]
    assert d["authoringCode"] == "REPORT_CUSTOM_SECTION_NOT_OWNED"
    assert d["path"] == ["sections", 0, "sectionKey"]
    assert d["allowedDomain"] == {"kind": "enum", "values": []}, (
        "the empty enum is the finding: on CREATE, no client sectionKey is legal")


def test_attempt_2_pinned_the_preview_byte_cap():
    msg = RECORD["responseVerbatim"]["message"]
    assert "395404 > 256000" in msg and "mcp_result_bytes" in msg
    # The plan itself was 20x under the cap - the cap bit the PREVIEW, not the plan.
    body = json.dumps(request()["request"], separators=(",", ":")).encode("utf-8")
    assert len(body) < 256_000 // 20


def test_the_fix_reached_the_wire():
    """Attempt 2 got past section validation because wire() stopped emitting the keys."""
    for preset in PRESETS:
        for s in plan(PRESETS[preset]).wire()["sections"]:
            if s["kind"] == "custom":
                assert "sectionKey" not in s


# --- the small-selection compile: viable ------------------------------------

def test_the_small_selection_compile_is_viable():
    ap = SMALL["responseVerbatim"]["approvedPlan"]
    assert ap["viability"]["viable"] is True
    assert ap["operation"] == "CREATE" and ap["proposedRevision"] == 1
    assert SMALL["verdict"] == "viable"
    assert "FILL IN" not in SMALL["_interpretation"]


def test_small_request_keys_match_current_wire():
    assert SMALL["requestKeys"] == sorted(request(small=True)["request"].keys())
    assert SMALL["coinSelection"] == {"mode": "explicit", "tickers": SMALL_TICKERS}
    assert SMALL["responseVerbatim"]["reviewContext"]["resolvedCoinTickers"] == SMALL_TICKERS


def test_the_server_minted_the_section_keys():
    """Constructive confirmation of the attempt-1 rule: the CREATE carried no client
    sectionKeys and the postState carries server-minted ones - not omega's uuid5s."""
    keys = [s["sectionKey"]
            for s in SMALL["responseVerbatim"]["approvedPlan"]["postState"]["sections"]]
    ours = {s.sectionKey for s in plan(PRESETS[PRESET]).report.sections}
    assert len(keys) == 2 and all(k.startswith("custom:") for k in keys)
    assert not set(keys) & ours


def test_the_token_is_redacted_not_committed():
    """The planToken is a credential-bound 5-minute token; the record keeps its length
    and sha256 so the redaction is checkable, and never the token itself."""
    tok = SMALL["responseVerbatim"]["planToken"]
    assert set(tok) == {"_redacted", "length", "sha256"}
    assert tok["length"] == 686 and len(tok["sha256"]) == 64


def test_the_mismatches_are_the_two_advisory_classes():
    """16 non-blocking advisories. The 12 ACTIVE_SIGNAL_DATA_NOT_IN_REPORT entries are
    the finding: membership (IN_REPORT) is not the same relation as 'all scoring inputs
    rendered' - omega's membership model captures only the first. The 4
    REPORT_DATA_SIGNAL_OFF entries are the context-module-weighted-0 design working."""
    codes = Counter(
        m["code"] for m in SMALL["responseVerbatim"]["approvedPlan"]["mismatches"])
    assert codes == {"ACTIVE_SIGNAL_DATA_NOT_IN_REPORT": 12, "REPORT_DATA_SIGNAL_OFF": 4}


def test_the_server_derives_cadence_the_way_omega_predicted():
    """We sent neither cadence nor regimeTimeframe (the CREATE schema has no such
    fields); postState carries both, matching omega's anchor mapping. One data point -
    confirmed at the 1h anchor only."""
    ps = SMALL["responseVerbatim"]["approvedPlan"]["postState"]
    assert ps["cadence"] == CADENCE_FOR_ANCHOR["1h"] == "INTRADAY"
    assert ps["regimeTimeframe"] == REGIME_TF_FOR_ANCHOR["1h"] == "4h"
    assert ps["timeframe"] == "1h"


def test_the_read_back_name_is_still_signalRules():
    """The write API takes `rules`; the persisted shape answers `signalRules` - the
    rename is a write-surface convention, and both carry the dense 84."""
    ps = SMALL["responseVerbatim"]["approvedPlan"]["postState"]
    assert "signalRules" in ps and "rules" not in ps
    assert len(ps["signalRules"]) == 84


# --- Probe A (2026-08-28 finalize plan, Task 3): which R:R bound is enforced --

BOUNDS = json.loads(
    (ROOT / "data/audit/bounds_probe_2026-08-28.json").read_text(encoding="utf-8"))


def test_the_bounds_probe_is_recorded_and_interpreted():
    assert BOUNDS["verdict"].startswith("CATALOG BOUND ENFORCED")
    assert "FILL IN" not in BOUNDS["verdict"]
    assert BOUNDS["request"]["delta"] == {"minRiskRewardRatio": 5.0}


def test_the_catalog_upper_edge_is_what_refused_us():
    """One changed field (minRiskRewardRatio 5.0) against the known-viable small
    CREATE. Refused at the connector's input-validation layer with a message naming
    the agent catalog's upper edge (must be <= 3) - the published CREATE schema
    leaves the field unbounded, so enforcement lives BELOW the declared schema. No
    compile record or token was minted. Only the upper edge was probed; the lower
    edge (0.5) and minAtrPct's catalog-vs-schema conflict stay unmeasured."""
    err = BOUNDS["responseVerbatim"]["errorText"]
    assert "minRiskRewardRatio (5) must be <= 3" in err and "-32602" in err
    assert "no compile record" in BOUNDS["responseVerbatim"]["transport"]


# --- Probe B (2026-08-28 finalize plan, Task 4): defaults at a 4h anchor ------

TF4H = json.loads(
    (ROOT / "data/audit/defaults_4h_probe_2026-08-28.json").read_text(encoding="utf-8"))


def test_the_4h_compile_is_viable_and_recorded():
    assert TF4H["measured"]["viable"] is True
    assert TF4H["verdict"].startswith("IDENTICAL")
    assert TF4H["responseVerbatim"]["approvedPlan"]["postState"]["timeframe"] == "4h"
    tok = TF4H["responseVerbatim"]["planToken"]
    assert set(tok) == {"_redacted", "length", "sha256"}, "token must never be committed"


def test_the_defaults_are_anchor_independent_as_measured():
    """All 16 execution defaults at 4h equal the 1h measurement. 'Anchor-independent'
    means exactly that: identical at the two anchors measured, nothing more."""
    params = TF4H["measured"]["executionDefaultsAt4h"]
    ps4h = TF4H["responseVerbatim"]["approvedPlan"]["postState"]
    ps1h = SMALL["responseVerbatim"]["approvedPlan"]["postState"]
    assert len(params) == 16
    assert {k: ps4h[k] for k in params} == {k: ps1h[k] for k in params}


def test_the_cadence_prediction_outcome_is_pinned():
    """Stated before measuring: cadence INTRADAY (omega's then-current mapping) and
    regimeTimeframe 1d. Measured: SWING and 1d - the cadence prediction FAILED and
    CADENCE_FOR_ANCHOR['4h'] was corrected to the measured value in the same commit
    as the record; the regime prediction held."""
    ps = TF4H["responseVerbatim"]["approvedPlan"]["postState"]
    assert TF4H["predictionStatedBeforeMeasuring"]["cadence"].startswith("INTRADAY")
    assert ps["cadence"] == CADENCE_FOR_ANCHOR["4h"] == "SWING"
    assert ps["regimeTimeframe"] == REGIME_TF_FOR_ANCHOR["4h"] == "1d"
