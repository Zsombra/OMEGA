"""The 2026-08-28 anchor sweep. Planned as 11 blind probes; the first call's typed
refusal named the complete authorable set (allowedDomain ['5m','15m','1h','4h']), so
the family closed in 4 compiles: two refusals that revealed and confirmed the enum,
two viable compiles at the authorable-but-unmeasured anchors. The other 7 anchors are
ATTRIBUTED to the enum, not probed - the record says which is which, and this file
pins both the record and the code the measurements corrected."""
import json
from pathlib import Path

from omega.execution import PLATFORM_EXECUTION_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
SWEEP = json.loads(
    (ROOT / "data/audit/anchor_sweep_2026-08-28.json").read_text(encoding="utf-8"))
PLANNED = ["1m", "3m", "5m", "15m", "30m", "2h", "8h", "12h", "1d", "3d", "1w"]
PROBED = ["1m", "1d", "5m", "15m"]


def test_all_eleven_planned_anchors_are_accounted_for():
    assert sorted(SWEEP["extract"]) == sorted(PLANNED)
    assert sorted(SWEEP["probes"]) == sorted(PROBED), (
        "exactly the 4 probed anchors carry verbatim responses; the rest are attributed")
    assert "FILL IN" not in SWEEP["_what"] and "FILL IN" not in SWEEP["_interpretation"]
    for a, ex in SWEEP["extract"].items():
        assert ex["how"].startswith("probed" if a in PROBED else "attributed")


def test_the_revealing_refusals_name_the_enum():
    for a in ("1m", "1d"):
        details = SWEEP["probes"][a]["error"]["details"]
        assert details["authoringCode"] == "REPORT_TIMEFRAME_NOT_AUTHORABLE"
        assert details["receivedValue"] == a
        assert details["allowedDomain"] == {
            "kind": "enum", "values": ["5m", "15m", "1h", "4h"]}


def test_the_extract_matches_the_verbatim_probes():
    for a in ("5m", "15m"):
        ex = SWEEP["extract"][a]
        ap = SWEEP["probes"][a]["approvedPlan"]
        ps = ap["postState"]
        assert ap["viability"]["viable"] is True and ex["viable"] is True
        assert ps["timeframe"] == a
        assert ex["cadence"] == ps["cadence"]
        assert ex["regimeTimeframe"] == ps["regimeTimeframe"]
        assert ex["defaultsIdentical"] is True
        assert {k: ps[k] for k in PLATFORM_EXECUTION_DEFAULTS} == PLATFORM_EXECUTION_DEFAULTS


def test_every_viable_probe_has_a_redacted_token():
    for resp in SWEEP["probes"].values():
        tok = resp.get("planToken")
        if tok is not None:
            assert set(tok) == {"_redacted", "length", "sha256"}


def test_the_5m_regime_prediction_failed_and_was_recorded():
    """The map said 5m -> regime 1h; the server derives 15m. The record must carry
    both the prior and the failure - and the map correction lives in the same commit
    (pinned by test_the_maps_carry_only_measured_values below)."""
    assert SWEEP["_predictionsStatedBeforeMeasuring"]["5m"]["regimeTimeframe"].startswith("1h")
    assert SWEEP["extract"]["5m"]["regimeTimeframe"] == "15m"
    assert "FAILED" in SWEEP["_interpretation"]


# --- what the sweep proved about the code (the collapsed Task 3) ---------------

def test_the_anchor_literal_is_exactly_the_measured_authorable_set():
    """ANCHOR_TIMEFRAMES was right all along - and as of this sweep it is MEASURED,
    not assumed: the platform's authorable set has exactly these four members."""
    from typing import get_args
    from omega.types import ANCHOR_TIMEFRAMES
    assert set(get_args(ANCHOR_TIMEFRAMES)) == set(SWEEP["authorableAnchorSet"]["measured"])


def test_the_maps_carry_only_measured_values():
    from typing import get_args
    from omega.generate import CADENCE_FOR_ANCHOR, REGIME_TF_FOR_ANCHOR
    from omega.types import ANCHOR_TIMEFRAMES
    anchors = set(get_args(ANCHOR_TIMEFRAMES))
    assert set(CADENCE_FOR_ANCHOR) == set(REGIME_TF_FOR_ANCHOR) == anchors
    for a in ("5m", "15m"):
        assert CADENCE_FOR_ANCHOR[a] == SWEEP["extract"][a]["cadence"]
        assert REGIME_TF_FOR_ANCHOR[a] == SWEEP["extract"][a]["regimeTimeframe"]
    # 1h and 4h are pinned against their own probe records in test_compile_dry_run.py


def test_emit_plan_works_at_every_measured_anchor(tmp_path):
    from dataclasses import replace
    from typing import get_args
    from omega.generate import PRESETS, emit_plan, plan
    from omega.types import ANCHOR_TIMEFRAMES
    for a in get_args(ANCHOR_TIMEFRAMES):
        t = replace(PRESETS["trend-continuation"], anchor=a,
                    coin_selection={"mode": "explicit", "tickers": ["BTC"]})
        emit_plan(plan(t), f"sweep-{a}", out_dir=tmp_path)
