"""scripts/sweep_render_coverage.py stops on a platform outage and records only what it measured.

2026-11-05 14:43Z - 16:31Z every mcporter call answered "responded with HTTP 502 (Version negotiation failed ...)" and
GET /mcp/version answered nginx 502. The sweep as committed in 3ac741a stopped only on an OAuth prompt: a 502 came
back from render() as an ordinary error, every 128-column batch was bisected to its leaves (~383 previews against a
dead platform) and each column was written to `refusals` with the gateway text as its "refusal", `complete` true. With
SWEEP_CONTRACT set, a 502 on the version GET raised HTTPError past the `except SweepStopped` and the process died
before either output file was written. And an aborted run still walked every target in the header-agreement pass, so
each never-sent shape read as an omega-vs-platform header mismatch. Nothing here calls the platform: subprocess.Popen
and urlopen are stubbed.
"""
from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sweep_render_coverage.py"
# mcporter's stderr at 14:43:32Z (fetch_hints_resume_stdout.txt), verbatim but for the tool name
GATEWAY_502 = (b"[mcporter] battlegrid-anbu.preview_strategy_report responded with HTTP 502 (Version negotiation "
               b"failed: the server answered the probe with HTTP 502).\n")
RENDER = {"budgetUsage": {}, "authoring": {"conditionColumns": [
    {"title": "sweep 1", "outputs": [{"header": "ADX_value"}]}]}}


def _load(monkeypatch):
    spec = importlib.util.spec_from_file_location("sweep_render_coverage_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(mod, "SWEEP_CONTRACT", None)
    mod._calls[0] = 0
    return mod


class _Proc:
    calls = 0

    def __init__(self, stdout: bytes, stderr: bytes):
        type(self).calls += 1
        self._out, self._err = stdout, stderr

    def communicate(self, data=None, timeout=None):
        return self._out, self._err

    def kill(self):
        pass


def _popen(stdout: bytes, stderr: bytes):
    _Proc.calls = 0
    return lambda *a, **k: _Proc(stdout, stderr)


def _shape(i):
    return SimpleNamespace(metric=f"M{i}", transform="value", chained=None, operand=None, ordering=None)


def _targets(n):
    return [(_shape(i), {"metric": f"M{i}", "transformId": "value"}) for i in range(n)]


# --- finding 1: a platform 5xx is an outage, not a column refusal ---------------------------------------------------

def test_a_gateway_5xx_on_stderr_stops_the_call(monkeypatch):
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(b"", GATEWAY_502))
    with pytest.raises(mod.SweepStopped, match="HTTP 502"):
        mod.call("preview_strategy_report", {})


@pytest.mark.parametrize("body", [b"<html><head><title>502 Bad Gateway</title></head></html>",
                                  b"<html><body>503 Service Temporarily Unavailable</body></html>",
                                  b"<html><body>504 Gateway Time-out</body></html>"])
def test_a_gateway_page_on_stdout_stops_the_call(monkeypatch, body):
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(body, b""))
    with pytest.raises(mod.SweepStopped):
        mod.call("preview_strategy_report", {})


def test_a_platform_refusal_is_still_bisected_not_stopped(monkeypatch):
    """The stop is for an outage only: a refusal the platform words is what the bisect exists to attribute."""
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(b"", b"REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED: metric 'MKT_UP'"
                                                            b" is not read on a evaluated-coin section's bars"))
    d, err = mod.call("preview_strategy_report", {})
    assert d is None and "REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED" in err


def test_an_outage_aborts_the_sweep_after_one_preview_and_records_no_refusal(monkeypatch):
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(b"", GATEWAY_502))
    out = mod.run_sweep(_targets(300), per_call=128)
    assert _Proc.calls == 1, "nothing is sent after the first 5xx, least of all a bisect"
    assert out["refusals"] == [] and out["batches"] == [] and out["sent"] == []
    assert out["aborted"]["afterBatches"] == 0 and "HTTP 502" in out["aborted"]["message"]


# --- finding 2: a failing version gate is a clean stop with a record ------------------------------------------------

@pytest.mark.parametrize("exc", [
    urllib.error.HTTPError("https://mcp.battlegrid.trade/mcp/version", 502, "Bad Gateway", {}, io.BytesIO(b"")),
    urllib.error.URLError("timed out"),
    TimeoutError("timed out"),
])
def test_a_failing_version_gate_stops_the_sweep(monkeypatch, exc):
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "SWEEP_CONTRACT", "148.1.0")

    def urlopen(*a, **k):
        raise exc
    monkeypatch.setattr(mod.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(json.dumps(RENDER).encode(), b""))
    with pytest.raises(mod.SweepStopped, match="version"):
        mod.call("preview_strategy_report", {})
    assert _Proc.calls == 0, "no preview is sent when the version cannot be read"
    out = mod.run_sweep(_targets(10), per_call=128)          # caught by the loop like any other stop
    assert out["aborted"] is not None and out["sent"] == []


def test_a_non_json_version_body_stops_the_sweep(monkeypatch):
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "SWEEP_CONTRACT", "148.1.0")

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: _Resp(b"<html>502 Bad Gateway</html>"))
    with pytest.raises(mod.SweepStopped, match="version"):
        mod.call("preview_strategy_report", {})


def test_main_writes_the_partial_record_when_the_gate_fails(monkeypatch, tmp_path):
    mod = _load(monkeypatch)
    monkeypatch.setattr(mod, "SWEEP_CONTRACT", "148.1.0")
    monkeypatch.setattr(mod, "HEADERS_OUT", str(tmp_path / "columns" / "h.json"))
    monkeypatch.setattr(mod, "RECORD_OUT", str(tmp_path / "audit" / "r.json"))
    monkeypatch.setattr(mod, "load", lambda: None)
    monkeypatch.setattr(mod, "rendered_headers", lambda: set())
    monkeypatch.setattr(mod, "collect_targets", lambda c: ("structural", _targets(5)))
    monkeypatch.setattr(mod, "outputs_for", lambda col, c: [SimpleNamespace(header=col.metric + "_value")])

    def urlopen(*a, **k):
        raise urllib.error.HTTPError("u", 502, "Bad Gateway", {}, io.BytesIO(b""))
    monkeypatch.setattr(mod.urllib.request, "urlopen", urlopen)
    mod.main()
    record = json.loads((tmp_path / "audit" / "r.json").read_text(encoding="utf-8"))
    assert record["complete"] is False and "502" in record["aborted"]["message"]
    assert json.loads((tmp_path / "columns" / "h.json").read_text(encoding="utf-8"))["headers"] == []


# --- finding 3: an aborted record measures only what was sent -------------------------------------------------------

def test_an_aborted_sweep_judges_header_agreement_on_the_sent_shapes_only(monkeypatch):
    mod = _load(monkeypatch)
    calls = []

    def render_fn(cols):
        calls.append(len(cols))
        if len(calls) == 2:
            raise mod.SweepStopped("served contract 149.0.0 after 1 previews, not 148.1.0")
        return [c["metric"] + "_value" for c in cols], None

    targets = _targets(10)
    out = mod.run_sweep(targets, render_fn, per_call=4)
    assert [s.metric for s in out["sent"]] == ["M0", "M1", "M2", "M3"]
    mismatches = mod.agreement(out["sent"], out["headers"], set(), lambda s: [s.metric + "_value"])
    assert mismatches == [], "a shape that was never sent is not a header mismatch"
    record = mod.run_record("structural", targets, out, mismatches)
    assert record["complete"] is False
    assert record["shapesTargeted"] == 10 and record["shapesRequested"] == 4
    assert record["predictedButNotRenderedCount"] == 0


def test_headers_rendered_inside_an_interrupted_bisect_are_kept(monkeypatch):
    mod = _load(monkeypatch)
    seen = []

    def render_fn(cols):
        seen.append([c["metric"] for c in cols])
        if len(seen) == 1:
            return None, "REPORT_COLUMN_X: refused"          # the batch is refused -> bisect
        if len(seen) == 2:
            return [c["metric"] + "_value" for c in cols], None   # first half renders
        raise mod.SweepStopped("mcporter has no usable credential")

    out = mod.run_sweep(_targets(4), render_fn, per_call=4)
    assert out["headers"] == ["M0_value", "M1_value"], "a header the platform minted is evidence, stop or not"
    assert out["sent"] == [] and out["batches"] == [], "the interrupted batch is not counted as sent"


def test_a_complete_sweep_is_unchanged(monkeypatch):
    mod = _load(monkeypatch)
    out = mod.run_sweep(_targets(9), lambda cols: ([c["metric"] + "_value" for c in cols], None), per_call=4)
    assert out["aborted"] is None and len(out["sent"]) == 9 and len(out["batches"]) == 3
    record = mod.run_record("all", _targets(9), out, [])
    assert record["complete"] is True and record["shapesRequested"] == record["shapesTargeted"] == 9


# --- finding 8: a second pass under one SWEEP_DATE cannot overwrite the first ---------------------------------------

def test_main_refuses_to_overwrite_an_existing_output(monkeypatch, tmp_path):
    mod = _load(monkeypatch)
    (tmp_path / "h.json").write_text('{"headers": ["KEEP_ME"]}', encoding="utf-8")
    monkeypatch.setattr(mod, "HEADERS_OUT", str(tmp_path / "h.json"))
    monkeypatch.setattr(mod, "RECORD_OUT", str(tmp_path / "r.json"))
    monkeypatch.delenv("SWEEP_OVERWRITE", raising=False)

    def load():
        raise AssertionError("nothing is loaded or sent before the output check")
    monkeypatch.setattr(mod, "load", load)
    with pytest.raises(SystemExit, match="SWEEP_DATE"):
        mod.main()
    assert json.loads((tmp_path / "h.json").read_text(encoding="utf-8"))["headers"] == ["KEEP_ME"]
