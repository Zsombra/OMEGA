"""End-to-end CLI in tmp_path at contract 91: recipe text, run -> receipt, gate exit codes.

The capture is the saved 91.0.0 stage_strategy_draft definition wrapped in the capture
envelope a session writes; the body is a generated CREATE stage request. The compile-era
CLI (and its V5 / read-back replays) is in the repository history; its receipts stay
under data/audit/compile_preflight_*.json."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from omega.contract import stage_schema
from omega.generate import PRESETS, emit_plan, plan

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preflight_cli", ROOT / "scripts" / "preflight.py")
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)  # type: ignore[union-attr]

CAPTURED_AT = "2026-10-06T09:00:00Z"


def _capture(tmp_path, definition=None, name="schema_20261006T090000Z.json") -> Path:
    definition = definition if definition is not None else copy.deepcopy(stage_schema()["stage_strategy_draft"])
    sp = tmp_path / name
    sp.write_text(json.dumps({"capturedAt": CAPTURED_AT, "how": "ToolSearch (test)", "request": None,
                              "response": definition}), encoding="utf-8")
    return sp


def _body(tmp_path, axes=None, name="body.json", **extra) -> Path:
    req = {"draftVersion": 0, "axes": axes if axes is not None else plan(PRESETS["trend-continuation"]).axes()}
    req.update(extra)
    bp = tmp_path / name
    bp.write_text(json.dumps({"request": req}), encoding="utf-8")
    return bp


def _run(*args) -> int:
    return cli.main(["run", *map(str, args), "--now", "2026-10-06T09:05:00Z"])


def test_recipe_prints_numbered_steps_with_the_capture_path(tmp_path, capsys):
    assert cli.main(["recipe", str(_body(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert "ToolSearch" in out and "stage_strategy_draft" in out
    assert "data/contract/stage_strategy_draft/" in out
    assert "CREATE stage, 8 axes, 7 conditions" in out          # contract 108: eight axes
    assert "6 KB" in out and "never" in out.lower() and "read-back" in out
    assert "YYYY-MM-DDTHH:MM:SSZ" in out and "fractional seconds" in out.lower()
    assert "compile_strategy_plan" not in out


def test_run_passes_a_generated_create_and_gate_admits_then_expires(tmp_path, capsys):
    sp, body, out = _capture(tmp_path), _body(tmp_path), tmp_path / "receipt.json"
    rc = _run(body, "--schema", sp, "--out", out)
    printed = capsys.readouterr().out
    assert rc == 0 and "PREFLIGHT PASS" in printed and "ref none (read-back retired)" in printed
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["body"]["operation"] == "CREATE" and receipt["captures"]["readback"] is None
    assert receipt["captures"]["schema"]["fingerprint"] == "ok"
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-10-06T09:30:00Z"]) == 0
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-10-06T11:00:00Z"]) == 1


def test_an_update_stage_is_named_and_walks_clean(tmp_path, capsys):
    p = plan(PRESETS["trend-continuation"])
    axes = p.axes_update(p.axes())      # the untouched dials read from the strategy
    body = _body(tmp_path, axes, strategyId="00000000-0000-4000-8000-000000000000", draftVersion=3)
    out = tmp_path / "receipt.json"
    assert _run(body, "--schema", _capture(tmp_path), "--out", out) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["body"]["operation"] == "UPDATE"


def test_run_fails_a_body_carrying_the_retired_condition_keys_and_gate_refuses(tmp_path, capsys):
    axes = plan(PRESETS["trend-continuation"]).axes()
    for c in axes["CONDITIONS"]["conditions"]:
        c["exit"] = False                   # v88: refused as an unknown key
        del c["exitSide"]                   # v88: required, nullable
    body, out = _body(tmp_path, axes), tmp_path / "receipt.json"
    assert _run(body, "--schema", _capture(tmp_path), "--out", out) == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    paths = {(f["cls"], f["path"]) for f in receipt["findings"] if f["verdict"] == "FAIL"}
    assert ("UNDECLARED", "axes.CONDITIONS.conditions[0].exit") in paths
    assert ("MISSING_REQUIRED", "axes.CONDITIONS.conditions[0].exitSide") in paths
    assert receipt["gateLine"] is None and "PREFLIGHT PASS" not in out.read_text(encoding="utf-8")
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-10-06T09:06:00Z"]) == 1


def test_run_refuses_a_transcription_suspect_schema(tmp_path, capsys):
    definition = copy.deepcopy(stage_schema()["stage_strategy_draft"])
    axes = definition["inputSchema"]["properties"]["request"]["properties"]["axes"]["properties"]
    # a truncated platform sectionKey enum on the REPORT axis (the signalId enum went with SIGNAL_RULES at 108)
    axes["REPORT"]["properties"]["sections"]["items"]["anyOf"][0]["properties"]["sectionKey"]["enum"].pop()
    out = tmp_path / "receipt.json"
    assert _run(_body(tmp_path), "--schema", _capture(tmp_path, definition), "--out", out) == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert any(f["cls"] == "TRANSCRIPTION_SUSPECT" for f in receipt["findings"])
    assert receipt["captures"]["schema"]["fingerprint"] == "suspect"


def test_run_refuses_a_capture_missing_how(tmp_path):
    sp = _capture(tmp_path)
    doc = json.loads(sp.read_text(encoding="utf-8")); del doc["how"]
    sp.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        _run(_body(tmp_path), "--schema", sp, "--out", tmp_path / "r.json")
    assert "how" in str(excinfo.value)


def test_run_takes_no_readback(tmp_path):
    with pytest.raises(SystemExit):
        _run(_body(tmp_path), "--schema", _capture(tmp_path), "--readback", "x.json")


def test_an_emitted_plan_file_is_a_body_and_its_metadata_is_stripped(tmp_path, capsys):
    """emit_plan writes the stage request plus "_"-prefixed local metadata; the walk and
    the sha see only what goes to the API."""
    path = Path(emit_plan(plan(PRESETS["mean-reversion"]), "mr", out_dir=tmp_path))
    assert cli._load_body(str(path)) == {"draftVersion": 0, "axes": plan(PRESETS["mean-reversion"]).axes()}
    assert _run(path, "--schema", _capture(tmp_path), "--out", tmp_path / "r.json") == 0


def test_previous_schema_adds_changelog_info_only(tmp_path, capsys):
    prev = copy.deepcopy(stage_schema()["stage_strategy_draft"])
    ax = prev["inputSchema"]["properties"]["request"]["properties"]["axes"]["properties"]
    ax["TIMEFRAME_PROFILE"]["properties"]["timeframe"]["enum"].remove("1w")
    out = tmp_path / "receipt.json"
    assert _run(_body(tmp_path), "--schema", _capture(tmp_path), "--previous-schema",
                _capture(tmp_path, prev, "prev.json"), "--out", out) == 0
    log = [f for f in json.loads(out.read_text(encoding="utf-8"))["findings"] if f["cls"] == "CHANGELOG"]
    assert log and all(f["verdict"] == "INFO" for f in log)
    assert any("1w" in f["detail"] for f in log)


def test_run_refuses_to_overwrite_an_existing_receipt_without_force(tmp_path, capsys):
    """A same-day default receipt path (or any repeated --out) used to be silently
    overwritten, so a FAIL run followed by a PASS run on the same day destroyed the FAIL
    evidence. `run` must refuse a pre-existing receipt path unless --force is given."""
    sp, body, out = _capture(tmp_path), _body(tmp_path), tmp_path / "receipt.json"
    assert _run(body, "--schema", sp, "--out", out) == 0
    first = out.read_text(encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        _run(body, "--schema", sp, "--out", out)
    # both halves of the refusal: which receipt, and how to proceed (the old `or` passed on either alone)
    assert str(out) in str(excinfo.value) and "--force" in str(excinfo.value)
    assert out.read_text(encoding="utf-8") == first
    assert _run(body, "--schema", sp, "--out", out, "--force") == 0


def test_run_default_receipt_path_appends_the_slug(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "AUDIT_DIR", tmp_path)
    assert _run(_body(tmp_path), "--schema", _capture(tmp_path), "--slug", "test-slug") == 0
    assert (tmp_path / "stage_preflight_2026-10-06-test-slug.json").exists()


def test_run_rejects_a_path_escaping_slug_before_touching_any_file(tmp_path, monkeypatch):
    """--slug is spliced straight into the default receipt filename; an unvalidated value
    like '../../escaped' could write outside data/audit/. It must be rejected before any
    file - including the receipt - is written."""
    audit_dir = tmp_path / "audit"
    monkeypatch.setattr(cli, "AUDIT_DIR", audit_dir)
    with pytest.raises(SystemExit) as excinfo:
        _run(_body(tmp_path), "--schema", _capture(tmp_path), "--slug", "../../escaped")
    assert "--slug" in str(excinfo.value)
    assert not audit_dir.exists()


def test_gate_prints_the_disclaimer_note_on_pass(tmp_path, capsys):
    sp, body, out = _capture(tmp_path), _body(tmp_path), tmp_path / "receipt.json"
    assert _run(body, "--schema", sp, "--out", out) == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["gateLine"].startswith("PREFLIGHT PASS") and str(out) in receipt["gateLine"]
    capsys.readouterr()
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-10-06T09:10:00Z"]) == 0
    assert "runtime validator" in capsys.readouterr().out


def test_receipt_gate_line_records_a_repo_relative_path_under_the_repo(tmp_path):
    """A committed receipt must not embed the machine's absolute path (2026-09-05 live run)."""
    inside = ROOT / "data" / "audit" / "_tmp_test_receipt_do_not_commit.json"
    try:
        assert _run(_body(tmp_path), "--schema", _capture(tmp_path), "--out", inside) == 0
        receipt = json.loads(inside.read_text(encoding="utf-8"))
        assert "data/audit/_tmp_test_receipt_do_not_commit.json" in receipt["gateLine"]
        assert str(ROOT) not in receipt["gateLine"]
    finally:
        if inside.exists():
            inside.unlink()


@pytest.mark.parametrize("which", ["body", "schema", "previous", "receipt"])
def test_a_missing_or_corrupt_input_is_refused_cleanly_not_a_traceback(tmp_path, which):
    """Deferred minor (2026-09-04 final review): a missing or corrupt input file surfaced as a raw traceback.
    It now refuses with SystemExit naming the file and what it should be."""
    missing, corrupt = tmp_path / "nope.json", tmp_path / "bad.json"
    corrupt.write_text("{not json", encoding="utf-8")
    for bad in (missing, corrupt):
        args = {"body": (bad, "--schema", _capture(tmp_path)),
                "schema": (_body(tmp_path), "--schema", bad),
                "previous": (_body(tmp_path), "--schema", _capture(tmp_path), "--previous-schema", bad),
                }.get(which)
        with pytest.raises(SystemExit) as excinfo:
            if which == "receipt":
                cli.main(["gate", str(bad), "--body", str(_body(tmp_path))])
            else:
                _run(*args, "--out", tmp_path / f"r-{which}.json", "--force")
        assert str(bad) in str(excinfo.value), excinfo.value
