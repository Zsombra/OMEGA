"""The two bounds edges Probe A left unprobed, measured 2026-08-28: the R:R lower
edge and minAtrPct's catalog-vs-schema conflict. One changed field per compile.
The answer is ASYMMETRIC: R:R's catalog bound is enforced on both edges; minAtrPct's
is not enforced at all - 0.05 compiled and persisted un-clamped, so the published
schema governs ATR and the catalog's 0.1-10 is agent-surface residue."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDGES = json.loads(
    (ROOT / "data/audit/bounds_edges_2026-08-28.json").read_text(encoding="utf-8"))


def test_both_probes_are_recorded_with_verdicts():
    assert set(EDGES["probes"]) == {"rr-0.3", "atr-0.05"}
    assert "FILL IN" not in EDGES["_interpretation"]
    for key in ("rrLowerEdge", "minAtrPct"):
        assert EDGES["verdicts"][key] in (
            "ENFORCED", "NOT_ENFORCED_SCHEMA_GOVERNS", "SILENT_CLAMP")


def test_the_rr_lower_edge_refusal_names_the_bound():
    assert EDGES["verdicts"]["rrLowerEdge"] == "ENFORCED"
    assert "minRiskRewardRatio (0.3) must be >= 0.5" in EDGES["probes"]["rr-0.3"]["error"]["message"]


def test_the_atr_value_persisted_unclamped():
    assert EDGES["verdicts"]["minAtrPct"] == "NOT_ENFORCED_SCHEMA_GOVERNS"
    ap = EDGES["probes"]["atr-0.05"]["approvedPlan"]
    assert ap["viability"]["viable"] is True
    assert ap["postState"]["minAtrPct"] == 0.05, "a different number here is BG-15"


def test_the_code_severity_matches_the_measured_verdict():
    from omega.execution import validate_execution
    atr = [f for f in validate_execution({"minAtrPct": 0.05})]
    if EDGES["verdicts"]["minAtrPct"] == "NOT_ENFORCED_SCHEMA_GOVERNS":
        assert atr and all(f.severity == "warning" for f in atr)
    else:
        assert any(f.severity == "error" for f in atr)
    rr = [f for f in validate_execution({"minRiskRewardRatio": 0.3})]
    if EDGES["verdicts"]["rrLowerEdge"] == "NOT_ENFORCED_SCHEMA_GOVERNS":
        assert rr and all(f.severity == "warning" for f in rr)
    else:
        assert any(f.severity == "error" for f in rr)
