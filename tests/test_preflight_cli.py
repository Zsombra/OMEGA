"""End-to-end CLI in tmp_path: recipe text, run -> receipt, gate exit codes."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preflight_cli", ROOT / "scripts" / "preflight.py")
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)  # type: ignore[union-attr]

MINI = json.loads((ROOT / "tests/fixtures/preflight/schema_walker_min.json").read_text(encoding="utf-8"))
V5 = json.loads((ROOT / "data/research/2026-08-29-deep-tail-fade/compile_body_deep_tail_fade_v5.json").read_text(encoding="utf-8"))
PRESTATE = json.loads((ROOT / "data/audit/first_generated_update_2026-08-29.json").read_text(encoding="utf-8"))["probes"]["preState"]["strategy"]


def _captures(tmp_path):
    """A schema capture whose fingerprint enums are REPLACED by the repo's real sets, so the
    fingerprint passes; still the walker miniature otherwise."""
    schema = json.loads(json.dumps(MINI))
    arm = schema["parameters"]["properties"]["request"]["anyOf"][0]["properties"]
    arm["rules"]["items"]["properties"]["signalId"]["enum"] = sorted(cli.repo_signal_ids())
    arm["sections"]["items"]["anyOf"][0]["properties"]["sectionKey"]["enum"] = sorted(cli.repo_template_keys())
    arm["timeframe"]["enum"] = cli.repo_timeframes()
    arm["entry"]["properties"]["trigger"]["enum"] = ["AT_SIGNAL", "ON_CANDLE_CLOSE", "STOP_THROUGH_LEVEL", "ON_RETEST"]
    arm["entry"]["properties"]["levelSource"]["enum"] = ["SWING_HIGH", "SWING_LOW", "BOLLINGER_UPPER", "BOLLINGER_LOWER"]
    arm["sections"]["items"]["anyOf"][1]["properties"]["columns"]["items"]["properties"]["metric"] = {"type": "string"}
    arm["sections"]["items"]["anyOf"][1]["properties"]["columns"]["items"]["additionalProperties"] = True
    arm["conditions"]["items"]["properties"]["definition"] = {"type": "object"}
    for k in V5:                      # the miniature models a subset; admit the body's other top-level keys permissively
        arm.setdefault(k, {})
    sp = tmp_path / "schema_20260904T085500Z.json"
    sp.write_text(json.dumps({"capturedAt": "2026-09-04T08:55:00Z", "how": "ToolSearch (test)", "request": None,
                              "response": schema}), encoding="utf-8")
    rec = json.loads(json.dumps(PRESTATE))
    rec["conditions"] = [dict(c, exit=False, clock="LIVE", closes=1) for c in rec["conditions"]]
    rec["entry"] = {"trigger": "AT_SIGNAL", "confirmTf": "1h", "closes": 1, "bandAtrMultiple": 1,
                    "levelSource": "SWING_HIGH", "levelOffsetAtrMultiple": 0, "validForBars": 4}
    rp = tmp_path / "6a8bca67-45a3-428e-85ba-71ec2cd2218e_20260904T085800Z.json"
    rp.write_text(json.dumps({"capturedAt": "2026-09-04T08:58:00Z", "how": "get_strategy (test)",
                              "request": {"strategyId": rec["id"], "includeInactive": True},
                              "response": {"strategy": rec}}), encoding="utf-8")
    return sp, rp


def test_recipe_prints_numbered_steps_with_the_capture_paths(tmp_path, capsys):
    body = tmp_path / "body.json"; body.write_text(json.dumps(V5), encoding="utf-8")
    assert cli.main(["recipe", str(body), "--reference", "b9438519-8223-4ef1-a3c3-6f4592bb823d"]) == 0
    out = capsys.readouterr().out
    assert "ToolSearch" in out and "get_strategy" in out and "data/contract/compile_strategy_plan/" in out
    assert "includeInactive" in out and "6 KB" in out and "never" in out.lower()


def test_run_fails_the_v5_body_on_missing_exit_and_gate_refuses(tmp_path, capsys):
    sp, rp = _captures(tmp_path)
    body = tmp_path / "body.json"; body.write_text(json.dumps(V5), encoding="utf-8")
    out = tmp_path / "receipt.json"
    rc = cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                   "--now", "2026-09-04T09:00:00Z"])
    assert rc == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["verdict"] == "FAIL"
    paths = {f["path"] for f in receipt["findings"] if f["verdict"] == "FAIL"}
    assert "conditions[0].exit" in paths and "conditions[*].exit" in paths
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-09-04T09:01:00Z"]) == 1


def test_run_passes_once_exit_is_mirrored_and_gate_admits_then_expires(tmp_path, capsys):
    sp, rp = _captures(tmp_path)
    fixed = json.loads(json.dumps(V5))
    for c in fixed["conditions"]:
        c["exit"] = False
    body = tmp_path / "body.json"; body.write_text(json.dumps(fixed), encoding="utf-8")
    out = tmp_path / "receipt.json"
    rc = cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                   "--now", "2026-09-04T09:00:00Z"])
    printed = capsys.readouterr().out
    assert rc == 0 and "PREFLIGHT PASS" in printed and "runtime validator" in printed
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-09-04T09:30:00Z"]) == 0
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-09-04T11:00:00Z"]) == 1


def test_run_refuses_a_transcription_suspect_schema(tmp_path, capsys):
    sp, rp = _captures(tmp_path)
    doc = json.loads(sp.read_text(encoding="utf-8"))
    doc["response"]["parameters"]["properties"]["request"]["anyOf"][0]["properties"]["rules"]["items"]["properties"]["signalId"]["enum"].pop()
    sp.write_text(json.dumps(doc), encoding="utf-8")
    body = tmp_path / "body.json"; body.write_text(json.dumps(V5), encoding="utf-8")
    out = tmp_path / "receipt.json"
    assert cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                     "--now", "2026-09-04T09:00:00Z"]) == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert any(f["cls"] == "TRANSCRIPTION_SUSPECT" for f in receipt["findings"])
