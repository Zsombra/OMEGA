"""scripts/probe_authoring_148.py stops on a transport failure instead of recording it as a platform refusal.

2026-11-05 from ~10:18Z every mcporter call printed "If the browser did not open, visit .../authorize?...", took
minutes and registered a new OAuth client. The probe as first written turned each such call into a probe with
accepted=False and a null refusal, counted it under `refused`, re-probed every column of a "refused" batch alone and
carried on: 247 calls, exit 0, a record that read as 247 platform refusals. Nothing here calls the platform:
subprocess.Popen and the version GET are stubbed.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "probe_authoring_148.py"
OAUTH = (b"If the browser did not open, visit https://mcp.battlegrid.trade/authorize?response_type=code&client_id=x "
         b"to continue.\n")


def _load(monkeypatch, tmp_path, contract="148.1.0"):
    monkeypatch.setenv("PROBE_HINTS", str(tmp_path / "hints"))
    monkeypatch.setenv("PROBE_DATE", "2099-01-01")
    if contract is None:
        monkeypatch.delenv("PROBE_CONTRACT", raising=False)
    else:
        monkeypatch.setenv("PROBE_CONTRACT", contract)
    spec = importlib.util.spec_from_file_location("probe_authoring_148_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "RECORD_OUT", str(tmp_path / "record.json"))
    monkeypatch.setattr(mod, "HEADERS_OUT", str(tmp_path / "headers.json"))
    monkeypatch.setattr(mod, "_MIN_INTERVAL", 0.0)
    monkeypatch.setattr(mod, "version", lambda: {"contractVersion": "148.1.0", "buildSha": "d02121ec"})
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return mod


class _Proc:
    calls = 0

    def __init__(self, stdout: bytes, stderr: bytes):
        type(self).calls += 1
        self._out, self._err = stdout, stderr
        self.returncode = 1 if not stdout else 0

    def communicate(self, data=None, timeout=None):
        return self._out, self._err

    def kill(self):
        pass


def _popen(stdout: bytes, stderr: bytes):
    _Proc.calls = 0
    return lambda *a, **k: _Proc(stdout, stderr)


def test_an_oauth_prompt_aborts_the_run_after_one_call(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(b"", OAUTH))
    assert mod.main() == 3
    assert _Proc.calls == 1, "an OAuth prompt is never retried and nothing after it is sent"
    record = json.loads((tmp_path / "record.json").read_text(encoding="utf-8"))
    assert record["complete"] is False and record["aborted"]["reason"] == "TransportFailure"
    assert record["aborted"]["afterProbes"] == 0 and "authorize" in record["aborted"]["message"]
    assert record["counts"] == {"probes": 0, "accepted": 0, "refused": 0, "headersMinted": 0}


def test_an_empty_or_non_json_answer_is_not_a_refusal(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(b"", b"connect ECONNRESET"))
    with pytest.raises(mod.TransportFailure):
        mod.call("preview_strategy_report", {})
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(b"<html>502 Bad Gateway</html>", b""))
    with pytest.raises(mod.TransportFailure):
        mod.call("preview_strategy_report", {})
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(json.dumps({"ok": True}).encode(), b""))
    with pytest.raises(mod.TransportFailure):
        mod.preview([])


def test_a_rate_limit_is_retried_then_aborts(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(b"", b"Rate limited (429)"))
    with pytest.raises(mod.TransportFailure):
        mod.call("preview_strategy_report", {}, attempts=3)
    assert _Proc.calls == 3


def test_a_platform_refusal_is_still_recorded_verbatim(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    body = {"code": "VALIDATION_ERROR", "message": "transform 'ema' window 270 exceeds 269",
            "details": {"authoringCode": "REPORT_COLUMN_DEPTH_EXCEEDED", "path": "columns[0].window"}}
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(json.dumps(body).encode(), b""))
    req, d, e = mod.preview([])
    assert d is None and mod.refusal(e)["authoringCode"] == "REPORT_COLUMN_DEPTH_EXCEEDED"
    assert "transport" not in mod.refusal(e)


def test_a_contract_move_mid_run_aborts(monkeypatch, tmp_path):
    mod = _load(monkeypatch, tmp_path)
    body = {"code": "VALIDATION_ERROR", "message": "refused", "details": {"authoringCode": "X"}}
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(json.dumps(body).encode(), b""))
    versions = iter([{"contractVersion": "148.1.0"}] + [{"contractVersion": "149.0.0"}] * 10)
    monkeypatch.setattr(mod, "version", lambda: next(versions))
    hints = tmp_path / "hints"
    hints.mkdir()
    for name in ("SWING_FRACTAL_HIGH", "EQH"):
        (hints / f"{name}.json").write_text(json.dumps({"metric": {"transforms": [{"id": "value"}], "parameters": {
            "leftBars": {"maximum": 9}, "rightBars": {"maximum": 9}, "equalBars": {"maximum": 9}}}}), encoding="utf-8")
    assert mod.main() == 3
    record = json.loads((tmp_path / "record.json").read_text(encoding="utf-8"))
    assert record["aborted"]["reason"] == "ContractMoved" and record["aborted"]["afterProbes"] == mod.VERSION_EVERY
    assert record["counts"]["probes"] == mod.VERSION_EVERY


# --- 2026-11-07: re-targeted to contract 149.1.0, group J (the four smoothers and the thirteen knobs) ---------------

VOCAB = json.loads((ROOT / "data" / "derived" / "condition_vocabulary_108.json").read_text(encoding="utf-8"))
COLUMN = VOCAB["reportColumn"]
KNOBS = ("accelerationIncrement", "accelerationMaximum", "accelerationStart", "atrPeriod", "dSmoothing", "fast",
         "kSmoothing", "multiplier", "period", "rsiPeriod", "signal", "slow", "stdDev")


def _dry_run(monkeypatch, tmp_path, maximum=50, step=None):
    """Every group sent against stubs: no platform call, every preview 'rendered' empty. Returns the columns sent."""
    mod = _load(monkeypatch, tmp_path, contract=None)
    monkeypatch.setattr(mod, "version", lambda: {"contractVersion": "149.1.0", "buildSha": "aa4ab640"})
    sent = []

    def preview(sections, tickers=("BTC",), timeframe="1h"):
        for s in sections:
            sent.extend(s["columns"])
        return {}, {"budgetUsage": {}, "authoring": {"conditionColumns": []}, "renderedSections": []}, None

    def hint(metric):
        transforms = [{"id": t, "authoring": {"parameters": {"window": {"maximum": maximum}}}}
                      for t in COLUMN["transformId"]["enum"]]
        params = {k: {"defaultValue": 5, "minimum": 2, "maximum": maximum, "step": step}
                  for k in KNOBS + ("leftBars", "rightBars", "equalBars")}
        return {"transforms": transforms, "parameters": params, "spreadOperands": ["CLOSE"]}

    monkeypatch.setattr(mod, "preview", preview)
    monkeypatch.setattr(mod, "hint", hint)
    assert mod.main() == 0
    return mod, sent


def test_the_probe_targets_149_1_0_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("PROBE_CONTRACT", raising=False)
    monkeypatch.setenv("PROBE_DATE", "2099-01-01")
    spec = importlib.util.spec_from_file_location("probe_default_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.CONTRACT == "149.1.0"
    assert mod.RECORD_OUT == "data/audit/authoring_probe_149_2099-01-01.json"
    assert mod.HEADERS_OUT == "data/contract/columns/_probe_149_2099-01-01.json"


def test_every_column_the_probe_sends_is_a_149_column(monkeypatch, tmp_path):
    """A field, metric or transform the 149.1.0 schema does not serve would be a schema refusal of the probe's own
    making, read later as a platform fact."""
    _, sent = _dry_run(monkeypatch, tmp_path)
    assert len(sent) > 300
    fields = set(COLUMN["fields"])
    metrics = set(COLUMN["metric"]["enum"])
    for col in sent:
        assert set(col) <= fields, col
        assert col["metric"] in metrics, col
        assert col["transformId"] in COLUMN["transformId"]["enum"], col
        if "chainedTransformId" in col:
            assert col["chainedTransformId"] in COLUMN["chainedTransformId"]["enum"], col
        for operand in col.get("inputs") or []:
            assert operand["metric"] in metrics, col


def test_group_j_sends_every_smoother_and_every_knob(monkeypatch, tmp_path):
    _, sent = _dry_run(monkeypatch, tmp_path)
    for tid in ("rma", "wma", "rsi", "cci"):
        assert any(c["transformId"] == tid for c in sent), tid
        assert any(c.get("chainedTransformId") == tid for c in sent), tid
    for k in KNOBS:
        assert any(k in c for c in sent), k


def test_group_j_reads_every_bound_from_the_hints(monkeypatch, tmp_path):
    """Maxima are the served ones (here a stub's 77), never constants: max accepted, one step past refused."""
    _, sent = _dry_run(monkeypatch, tmp_path, maximum=77)
    assert any(c["metric"] == "MACD_LINE" and c.get("fast") == 77 for c in sent)
    assert any(c["metric"] == "MACD_LINE" and c.get("fast") == 78 for c in sent)
    assert any(c["metric"] == "RSI14" and c["transformId"] == "rma" and c.get("window") == 78 for c in sent)
    assert any(c["metric"] == "BB_UPPER" and c.get("period") == 1 for c in sent), "the minimum 2 minus one step"
