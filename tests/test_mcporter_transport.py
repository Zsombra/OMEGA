"""scripts/mcporter_transport.py: one long-lived mcporter runtime instead of a process per call (2026-11-11).

The probing scripts keep their own answer rules; the transport only has to answer in the CLI process's terms - the
tool's JSON as stdout text, or empty stdout and the reason as stderr text. Nothing here calls the platform: the helper
is a stand-in speaking the same line protocol as scripts/mcporter_runtime.mjs.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRANSPORT = ROOT / "scripts" / "mcporter_transport.py"
SWEEP = ROOT / "scripts" / "sweep_render_coverage.py"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="the runtime transport starts `node`")

# answers by `args.case`: ok -> the value; refuse -> ok false; silent -> no answer (a timeout); wrong_id -> another id
STUB = """\
import { appendFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
const say = (o) => process.stdout.write(JSON.stringify(o) + '\\n');
appendFileSync(process.env.STUB_LOG, 'start\\n');
if (process.env.STUB_READY === 'no') { say({ ready: false, error: 'no server named battlegrid-anbu' }); process.exit(2); }
say({ ready: true, server: 'stub' });
for await (const line of createInterface({ input: process.stdin })) {
  const req = JSON.parse(line);
  const kind = req.args.case;
  if (kind === 'ok') say({ id: req.id, ok: true, value: { tool: req.tool, echoed: req.args, timeoutMs: req.timeoutMs } });
  else if (kind === 'refuse') say({ id: req.id, ok: false, error: 'Unauthorized: the cached token was refused' });
  else if (kind === 'wrong_id') say({ id: req.id + 100, ok: true, value: {} });
}
"""
RENDER = {"budgetUsage": {}, "authoring": {"conditionColumns": [
    {"title": "sweep 1", "outputs": [{"header": "ADX_value"}]}]}}


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    helper = tmp_path / "stub.mjs"
    helper.write_text(STUB, encoding="utf-8")
    monkeypatch.setenv("STUB_LOG", str(tmp_path / "log.txt"))
    mod = _module(TRANSPORT, "mcporter_transport_under_test")
    rt = mod.Runtime(str(helper))
    yield rt, tmp_path / "log.txt"
    rt.stop()


@needs_node
def test_an_answer_comes_back_as_the_clis_stdout_text_and_one_process_serves_every_call(runtime):
    rt, log = runtime
    out, err = rt.send("get_metric_construction_hints", {"case": "ok", "metric": "EMA20"}, 30)
    assert err == "" and json.loads(out) == {"tool": "get_metric_construction_hints",
                                             "echoed": {"case": "ok", "metric": "EMA20"}, "timeoutMs": 30000}
    for _ in range(3):
        assert rt.send("preview_strategy_report", {"case": "ok"}, 30)[1] == ""
    assert log.read_text().count("start") == 1


@needs_node
def test_a_failed_call_is_empty_stdout_and_the_reason_as_stderr(runtime):
    rt, _ = runtime
    assert rt.send("preview_strategy_report", {"case": "refuse"}, 30) == ("", "Unauthorized: the cached token was refused")
    # the process is still the same one, and still answers
    assert json.loads(rt.send("preview_strategy_report", {"case": "ok"}, 30)[0])["tool"] == "preview_strategy_report"


@needs_node
def test_a_timeout_raises_and_the_next_call_starts_a_new_helper(runtime, monkeypatch):
    rt, log = runtime
    real = rt._line
    monkeypatch.setattr(rt, "_line", lambda timeout: real(min(timeout, 1.5)))          # do not wait the real margin
    rt._start()
    with pytest.raises(TimeoutError):
        rt.send("preview_strategy_report", {"case": "silent"}, 0.5)
    assert rt.p is None, "the timed-out helper is killed: its late answer could arrive under the next call's id"
    assert rt.send("preview_strategy_report", {"case": "ok"}, 30)[1] == ""
    assert log.read_text().count("start") == 2


@needs_node
def test_an_answer_to_another_call_is_not_taken_for_this_one(runtime):
    rt, _ = runtime
    out, err = rt.send("preview_strategy_report", {"case": "wrong_id"}, 30)
    assert out == "" and "answered call" in err
    assert rt.p is None


@needs_node
def test_a_helper_that_does_not_start_is_a_failed_call(runtime, monkeypatch):
    rt, log = runtime
    monkeypatch.setenv("STUB_READY", "no")
    out, err = rt.send("preview_strategy_report", {"case": "ok"}, 30)
    assert out == "" and "did not start" in err and "no server named battlegrid-anbu" in err


def test_the_transport_is_cli_unless_named_and_an_unknown_name_stops_the_import():
    env = {k: v for k, v in os.environ.items() if k != "EXTRACTION_TRANSPORT"}
    show = [sys.executable, "-B", "-c", "import scripts.mcporter_transport as t; print(t.TRANSPORT)"]
    assert subprocess.run(show, cwd=ROOT, env=env, capture_output=True, text=True).stdout.strip() == "cli"
    named = subprocess.run(show, cwd=ROOT, env={**env, "EXTRACTION_TRANSPORT": "runtime"}, capture_output=True, text=True)
    assert named.stdout.strip() == "runtime"
    bad = subprocess.run(show, cwd=ROOT, env={**env, "EXTRACTION_TRANSPORT": "daemon"}, capture_output=True, text=True)
    assert bad.returncode != 0 and "EXTRACTION_TRANSPORT is 'daemon'" in bad.stderr


# --- the sweep reads either transport by the same rules ------------------------------------------------------------

class _Fake:
    def __init__(self, answer):
        self.answer, self.sent = answer, []

    def send(self, tool, args, timeout):
        self.sent.append((tool, timeout))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _sweep(monkeypatch, answer):
    mod = _module(SWEEP, "sweep_render_coverage_runtime_under_test")
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(mod, "SWEEP_CONTRACT", None)
    monkeypatch.setattr(mod, "TRANSPORT", "runtime")
    fake = _Fake(answer)
    monkeypatch.setattr(mod, "RUNTIME", fake)

    def no_process(*a, **k):
        raise AssertionError("the CLI is not started on the runtime transport")

    monkeypatch.setattr(mod.subprocess, "Popen", no_process)
    mod._calls[0] = 0
    return mod, fake


def test_the_sweep_takes_a_render_from_the_runtime(monkeypatch):
    mod, fake = _sweep(monkeypatch, (json.dumps(RENDER), ""))
    d, err = mod.call("preview_strategy_report", {"x": 1})
    assert d == RENDER and err is None and fake.sent == [("preview_strategy_report", 240)]


def test_a_refused_credential_from_the_runtime_stops_the_sweep(monkeypatch):
    mod, _ = _sweep(monkeypatch, ("", "Unauthorized: the cached token was refused"))
    with pytest.raises(mod.SweepStopped, match="no usable credential"):
        mod.call("preview_strategy_report", {})


def test_a_runtime_timeout_is_transient_never_a_refusal(monkeypatch):
    mod, _ = _sweep(monkeypatch, TimeoutError("no answer in 240 s"))
    with pytest.raises(mod.Transient, match="TIMEOUT"):
        mod.call("preview_strategy_report", {})


def test_a_validation_error_body_from_the_runtime_is_a_refusal_the_bisect_attributes(monkeypatch):
    body = {"code": "VALIDATION_ERROR", "message": "REPORT_COLUMN_CONSTRUCTION_FAILED"}
    mod, _ = _sweep(monkeypatch, (json.dumps(body), ""))
    d, err = mod.call("preview_strategy_report", {})
    assert mod.classify(d) == "refusal" and err is None
