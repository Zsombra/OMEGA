"""End-to-end CLI in tmp_path: recipe text, run -> receipt, gate exit codes."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

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
    assert "YYYY-MM-DDTHH:MM:SSZ" in out and "fractional seconds" in out.lower()


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


def test_run_refuses_a_capture_missing_how_or_request(tmp_path):
    body = tmp_path / "body.json"; body.write_text(json.dumps(V5), encoding="utf-8")
    out = tmp_path / "receipt.json"

    sp, rp = _captures(tmp_path)
    doc = json.loads(sp.read_text(encoding="utf-8"))
    del doc["how"]
    sp.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                  "--now", "2026-09-04T09:00:00Z"])
    assert "how" in str(excinfo.value)

    sp, rp = _captures(tmp_path)
    doc = json.loads(rp.read_text(encoding="utf-8"))
    del doc["request"]
    rp.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                  "--now", "2026-09-04T09:00:00Z"])
    assert "request" in str(excinfo.value)

    # a schema capture with "request": null (already the case in _captures()) is accepted
    sp, rp = _captures(tmp_path)
    assert json.loads(sp.read_text(encoding="utf-8"))["request"] is None
    fixed = json.loads(json.dumps(V5))
    for c in fixed["conditions"]:
        c["exit"] = False
    fixed_body = tmp_path / "fixed_body.json"; fixed_body.write_text(json.dumps(fixed), encoding="utf-8")
    rc = cli.main(["run", str(fixed_body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                   "--now", "2026-09-04T09:00:00Z"])
    assert rc == 0


def test_run_falls_back_to_the_record_id_and_records_meta_fingerprints(tmp_path, capsys):
    sp, rp = _captures(tmp_path)
    doc = json.loads(rp.read_text(encoding="utf-8"))
    doc["request"] = {}
    rp.write_text(json.dumps(doc), encoding="utf-8")

    fixed = json.loads(json.dumps(V5))
    for c in fixed["conditions"]:
        c["exit"] = False
    body = tmp_path / "body.json"; body.write_text(json.dumps(fixed), encoding="utf-8")
    out = tmp_path / "receipt.json"
    rc = cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                   "--now", "2026-09-04T09:00:00Z"])
    assert rc == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["captures"]["readback"]["strategyId"] == "6a8bca67-45a3-428e-85ba-71ec2cd2218e"
    assert receipt["captures"]["readback"]["fingerprint"] == "ok"
    assert receipt["captures"]["schema"]["fingerprint"] == "ok"

    sp2, rp2 = _captures(tmp_path)
    doc2 = json.loads(rp2.read_text(encoding="utf-8"))
    doc2["request"] = {}
    rp2.write_text(json.dumps(doc2), encoding="utf-8")
    doc3 = json.loads(sp2.read_text(encoding="utf-8"))
    doc3["response"]["parameters"]["properties"]["request"]["anyOf"][0]["properties"]["rules"]["items"]["properties"]["signalId"]["enum"].pop()
    sp2.write_text(json.dumps(doc3), encoding="utf-8")
    out2 = tmp_path / "receipt2.json"
    rc2 = cli.main(["run", str(body), "--schema", str(sp2), "--readback", str(rp2), "--out", str(out2),
                    "--now", "2026-09-04T09:00:00Z"])
    assert rc2 == 1
    receipt2 = json.loads(out2.read_text(encoding="utf-8"))
    assert receipt2["captures"]["schema"]["fingerprint"] == "suspect"
    assert receipt2["captures"]["readback"]["fingerprint"] == "ok"


def _fixed_body(tmp_path, name="body.json"):
    fixed = json.loads(json.dumps(V5))
    for c in fixed["conditions"]:
        c["exit"] = False
    body = tmp_path / name
    body.write_text(json.dumps(fixed), encoding="utf-8")
    return body


def test_run_refuses_to_overwrite_an_existing_receipt_without_force(tmp_path, capsys):
    """A same-day default receipt path (or any repeated --out) used to be silently
    overwritten, so a FAIL run followed by a PASS run on the same day destroyed the FAIL
    evidence. `run` must refuse a pre-existing receipt path unless --force is given."""
    sp, rp = _captures(tmp_path)
    body = _fixed_body(tmp_path)
    out = tmp_path / "receipt.json"
    rc = cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                   "--now", "2026-09-04T09:00:00Z"])
    assert rc == 0 and out.exists()
    first_contents = out.read_text(encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                  "--now", "2026-09-04T09:05:00Z"])
    assert str(out) in str(excinfo.value) or "force" in str(excinfo.value).lower()
    assert out.read_text(encoding="utf-8") == first_contents        # untouched by the refusal

    rc2 = cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                    "--now", "2026-09-04T09:05:00Z", "--force"])
    assert rc2 == 0


def test_run_default_receipt_path_appends_the_slug(tmp_path, monkeypatch):
    sp, rp = _captures(tmp_path)
    body = _fixed_body(tmp_path)
    monkeypatch.setattr(cli, "AUDIT_DIR", tmp_path)
    rc = cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp),
                   "--now", "2026-09-04T09:00:00Z", "--slug", "test-slug"])
    assert rc == 0
    assert (tmp_path / "compile_preflight_2026-09-04-test-slug.json").exists()


def test_run_writes_a_gate_line_into_the_receipt_and_gate_prints_the_disclaimer_note_on_pass(tmp_path, capsys):
    """(1) The receipt's gateLine must reflect the actual --out path (so it can be copied
    straight from the JSON). (2) `gate` on a PASS must print the same 'note: <DISCLAIMER>'
    line `run` already prints on PASS - the house rule is verbatim on every PASS, not just
    the first one."""
    sp, rp = _captures(tmp_path)
    body = _fixed_body(tmp_path)
    out = tmp_path / "receipt.json"
    rc = cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                   "--now", "2026-09-04T09:00:00Z"])
    assert rc == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["gateLine"].startswith("PREFLIGHT PASS") and str(out) in receipt["gateLine"]

    capsys.readouterr()
    rc2 = cli.main(["gate", str(out), "--body", str(body), "--now", "2026-09-04T09:05:00Z"])
    printed = capsys.readouterr().out
    assert rc2 == 0 and "runtime validator" in printed
