"""Review pass 1 (2026-11-08), findings 1-7: the extraction / probe / sweep scripts write nothing they did not measure.

1+2 refresh_metric_contracts: a platform error body is never cached as a raw hint, a bad cached one stops a re-run, and
    every phase-2 check runs before the first write under data/.
3   probe_authoring_148: an existing record or header cache is refused before the first call (PROBE_OVERWRITE=1).
4   probe_knob_spelling_149: a deadline answer is re-sent once then stops the run; `agree` is None with nothing rendered;
    a moved contract withholds the header cache; KNOB_COLUMNS / PROBE_DATE re-target it without an edit.
5   snapshot_vocabulary: only a known refusal is stored; anything else stops the run before _shared.json is rewritten.
6   sweep_render_coverage: a deadline body / timeout / negotiation failure is re-sent once, then an outage - never
    bisected into a column's refusal.
7   sweep_render_coverage: the run record names the contract at the start and at the end; a move exits non-zero.

Nothing here calls the platform: `call` / `preview` / `version` / subprocess.Popen are stubbed (the refresh script runs
as a copy in a throwaway tree with a stub `npx` first on PATH), and every output goes to tmp_path.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEADLINE = {"code": "SERVICE_UNAVAILABLE", "message": "Strategy report preview exceeded its 15000ms deadline.",
            "details": {}}


def _module(name: str, script: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _files(top: Path) -> dict[str, bytes]:
    return {str(p.relative_to(top)): p.read_bytes() for p in sorted(top.rglob("*")) if p.is_file()}


# --- findings 1 + 2: refresh_metric_contracts ------------------------------------------------------------------------

win_only = pytest.mark.skipif(sys.platform != "win32", reason="the script shells out through `cmd /c npx`")


def _hint(name: str, desc: str = "w", outer: dict | None = None) -> dict:
    body = {"metric": {"metric": name, "label": name, "code": name.lower(), "family": "structure",
                       "nativeOutput": {"kind": "numeric", "unit": "price"}, "timeframeMode": "series",
                       "transforms": [{"id": "value", "label": "Value",
                                       "authoring": {"parameters": {"x": {"description": desc}}}}]}}
    if outer is not None:
        body["chainOuterParameters"] = outer
    return body


SERVED = {"contractVersion": "149.1.0", "buildSha": "aa4ab640"}


def _refresh(tmp_path: Path, roster, raw: dict, stub_stdout: str | None = None, old_batches=False,
             pre_archive=False, served: dict | None = SERVED, stored: dict | None = SERVED,
             asserted: str | None = None, served_after_call: dict | None = None) -> dict:
    """served: what the stubbed GET /mcp/version answers (a file:// URL; None = the read fails). stored: the raw dir's
    _version.json (None = absent). asserted: EXTRACTION_CONTRACT. served_after_call: the stub npx rewrites the served
    version on every call (a contract that moves mid-fetch)."""
    tree = tmp_path / "repo"
    (tree / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "refresh_metric_contracts.py", tree / "scripts")
    metrics = tree / "data" / "contract" / "metrics"
    metrics.mkdir(parents=True)
    (tree / "data" / "contract" / "transforms").mkdir()
    (tree / "data" / "contract" / "transforms" / "_authoring.json").write_text('{"transforms": {}}', encoding="utf-8")
    for name in ("A", "B", "C"):
        (metrics / f"{name}.json").write_text(json.dumps({"metric": name, "stored": True}), encoding="utf-8")
    (metrics / "_index.json").write_text(json.dumps({"metricCount": 3, "stored": True}), encoding="utf-8")
    if old_batches:
        (metrics / "_batch01.json").write_text(json.dumps([{"metric": "A", "stored": True}]), encoding="utf-8")
    if pre_archive:
        (metrics / "archive_29990100_extraction").mkdir()
    scratch = tmp_path / "scratch"
    hints = scratch / "hints_29990101"
    hints.mkdir(parents=True)
    (scratch / "vocab_live_flat.json").write_text(json.dumps(roster), encoding="utf-8")
    for name, body in raw.items():
        (hints / f"{name}.json").write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    if stored is not None:
        (hints / "_version.json").write_text(json.dumps({**stored, "readAt": "2999-01-01T00:00:00Z"}),
                                             encoding="utf-8")
    served_file = tmp_path / "served_version.json"            # never the network: GET /mcp/version is this file
    if served is not None:
        served_file.write_text(json.dumps(served), encoding="utf-8")
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "npx.cmd").write_text(
        "@echo off\r\n" f'echo call>>"{shim / "calls.log"}"\r\n'
        + (f'echo {json.dumps(served_after_call)}>"{served_file}"\r\n' if served_after_call else "")
        + (f"echo {stub_stdout}\r\nexit /b 0\r\n" if stub_stdout else "echo TIMEOUT 1>&2\r\nexit /b 1\r\n"),
        encoding="utf-8")
    before = _files(tree / "data")
    env = {**os.environ, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}", "EXTRACTION_STAMP": "29990101",
           "EXTRACTION_SCRATCH": str(scratch), "EXTRACTION_ARCHIVE": "29990100",
           "EXTRACTION_VERSION_URL": served_file.as_uri()}
    env.pop("EXTRACTION_CONTRACT", None)
    if asserted is not None:
        env["EXTRACTION_CONTRACT"] = asserted
    proc = subprocess.run([sys.executable, str(tree / "scripts" / "refresh_metric_contracts.py")], cwd=tree, env=env,
                          capture_output=True, text=True, timeout=300)
    calls = (shim / "calls.log").read_text().count("call") if (shim / "calls.log").exists() else 0
    return {"proc": proc, "before": before, "after": _files(tree / "data"), "hints": hints, "calls": calls,
            "metrics": metrics}


@win_only
def test_refresh_never_caches_an_error_body_and_writes_nothing(tmp_path):
    run = _refresh(tmp_path, ["A", "B", "C"], {"A": _hint("A"), "B": _hint("B")},
                   stub_stdout='{"code":"INTERNAL_ERROR","message":"boom"}')
    out = run["proc"].stdout + run["proc"].stderr
    assert run["proc"].returncode == 1, out
    assert run["calls"] == 1
    assert not (run["hints"] / "C.json").exists(), "a {code, message} body is a failed read, never a cached hint"
    assert "INTERNAL_ERROR" in out and "Nothing under data/ was written" in out
    assert run["after"] == run["before"]


@win_only
@pytest.mark.parametrize("bad", [{"code": "SERVICE_UNAVAILABLE", "message": "deadline"}, '{"metric": {"metr'])
def test_refresh_refuses_to_resume_over_a_bad_cached_hint(tmp_path, bad):
    run = _refresh(tmp_path, ["A", "B", "C"], {"A": _hint("A"), "B": bad, "C": _hint("C")})
    out = run["proc"].stdout + run["proc"].stderr
    assert run["proc"].returncode == 1, out
    assert run["calls"] == 0
    assert "B.json" in out and "Nothing under data/ was written" in out
    assert run["after"] == run["before"], "no metric file is half-rewritten"


@win_only
@pytest.mark.parametrize("case", ["authoring", "outer", "archive"])
def test_refresh_runs_every_check_before_the_first_write(tmp_path, case):
    raw = {"A": _hint("A"), "B": _hint("B"), "C": _hint("C")}
    if case == "authoring":
        raw["B"] = _hint("B", desc="other")
    if case == "outer":
        raw = {"A": _hint("A", outer={"distance": 1}), "B": _hint("B", outer={"distance": 2}),
               "C": _hint("C", outer={"distance": 1})}
    run = _refresh(tmp_path, ["A", "B", "C"], raw, old_batches=True, pre_archive=case == "archive")
    out = run["proc"].stdout + run["proc"].stderr
    assert run["proc"].returncode == 1, out
    assert {"authoring": "authoring blocks VARY", "outer": "chainOuterParameters VARY",
            "archive": "already exists"}[case] in out
    assert run["after"] == run["before"], "records, index, batches and catalogue all stay at the old stamp"


@win_only
def test_refresh_complete_run_writes_corpus_batches_and_catalogue(tmp_path):
    run = _refresh(tmp_path, ["A", "B", "C"], {n: _hint(n, outer={"d": 1}) for n in "ABC"}, old_batches=True)
    assert run["proc"].returncode == 0, run["proc"].stdout + run["proc"].stderr
    m = run["metrics"]
    assert json.loads((m / "_index.json").read_text(encoding="utf-8"))["metricCount"] == 3
    assert json.loads((m / "A.json").read_text(encoding="utf-8"))["code"] == "a"
    assert (m / "archive_29990100_extraction" / "_batch01.json").exists()
    assert len(json.loads((m / "_batch01.json").read_text(encoding="utf-8"))) == 3
    cat = json.loads((m.parent / "transforms" / "_authoring.json").read_text(encoding="utf-8"))
    assert "value" in cat["transforms"]
    assert (m.parent / "transforms" / "_chain_outer_parameters.json").exists()


# --- finding 3: probe_authoring_148 refuses an existing output -------------------------------------------------------

def _probe(monkeypatch, tmp_path):
    monkeypatch.setenv("PROBE_HINTS", str(tmp_path / "hints"))
    monkeypatch.setenv("PROBE_DATE", "2099-01-01")
    monkeypatch.delenv("PROBE_CONTRACT", raising=False)
    mod = _module("probe_authoring_148_guard", "probe_authoring_148.py")
    monkeypatch.setattr(mod, "RECORD_OUT", str(tmp_path / "record.json"))
    monkeypatch.setattr(mod, "HEADERS_OUT", str(tmp_path / "headers.json"))
    monkeypatch.setattr(mod, "version", lambda: {"contractVersion": "149.1.0", "buildSha": "x"})

    def lost(*a, **k):
        raise mod.TransportFailure("mcporter has no usable credential for battlegrid-anbu")
    monkeypatch.setattr(mod, "preview", lost)
    return mod


@pytest.mark.parametrize("existing", ["record.json", "headers.json"])
def test_probe_refuses_an_existing_output_before_any_call(monkeypatch, tmp_path, existing):
    mod = _probe(monkeypatch, tmp_path)
    monkeypatch.delenv("PROBE_OVERWRITE", raising=False)
    (tmp_path / existing).write_text('{"headers": ["KEEP_ME"]}', encoding="utf-8")

    def version():
        raise AssertionError("nothing is read or sent before the output check")
    monkeypatch.setattr(mod, "version", version)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code not in (0, None) and "PROBE_OVERWRITE" in str(exc.value.code)
    assert json.loads((tmp_path / existing).read_text(encoding="utf-8")) == {"headers": ["KEEP_ME"]}


def test_probe_overwrite_is_explicit(monkeypatch, tmp_path):
    mod = _probe(monkeypatch, tmp_path)
    monkeypatch.setenv("PROBE_OVERWRITE", "1")
    (tmp_path / "record.json").write_text("{}", encoding="utf-8")
    assert mod.main() == 3                       # past the guard: the stubbed lost credential aborts the run
    assert json.loads((tmp_path / "record.json").read_text(encoding="utf-8"))["aborted"]["reason"] == "TransportFailure"


# --- finding 4: probe_knob_spelling_149 ------------------------------------------------------------------------------

def _knob(monkeypatch, tmp_path, answers, versions=(("149.1.0", "x"), ("149.1.0", "x"))):
    """answers: a list of 'deadline' / 'refuse' / 'render', consumed one per preview (the last one repeats)."""
    import scripts.probe_knob_spelling_149 as pk
    monkeypatch.delenv("KNOB_COLUMNS", raising=False)
    monkeypatch.setattr(pk, "RECORD_OUT", str(tmp_path / "audit" / "knob.json"))
    monkeypatch.setattr(pk, "HEADERS_OUT", str(tmp_path / "columns" / "knob_headers.json"))
    vs = iter(versions)

    def version():
        v = next(vs)
        if v == "FAIL":
            raise OSError("URLError: <urlopen error [Errno 11001] getaddrinfo failed>")
        return dict(zip(("contractVersion", "buildSha"), v))
    monkeypatch.setattr(pk, "version", version)
    monkeypatch.setattr(pk, "OC", SimpleNamespace(load=lambda: None))
    monkeypatch.setattr(pk, "Column", lambda **kw: SimpleNamespace(**kw))
    monkeypatch.setattr(pk, "outputs_for", lambda col, c: [SimpleNamespace(header=col.metric + "_k")])
    monkeypatch.setattr(pk.time, "sleep", lambda s: None)
    sent = []

    def preview(sections):
        cols = [col for s in sections for col in s["columns"]]
        sent.append(cols)
        kind = answers[min(len(sent), len(answers)) - 1]
        if kind == "deadline":
            return {}, None, DEADLINE
        if kind == "refuse":
            return {}, None, {"code": "VALIDATION_ERROR", "message": "refused", "details": {"authoringCode": "X"}}
        if kind in ("RATE_LIMITED", "INTERNAL_ERROR", "UNAUTHORIZED"):
            return {}, None, {"code": kind, "message": "x", "details": {}}
        return {}, {"renderedSections": [{"section": {"columns": [{"key": col["metric"] + "_k"} for col in cols]}}],
                    "authoring": {}}, None
    monkeypatch.setattr(pk, "preview", preview)
    return pk, sent


def _read(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def test_knob_deadline_is_retried_once_then_stops_without_a_header_cache(monkeypatch, tmp_path):
    pk, sent = _knob(monkeypatch, tmp_path, ["deadline"])
    assert pk.main() == 3
    assert len(sent) == 2, "one re-send, then the run stops - no per-column fan-out against a loaded platform"
    assert not Path(pk.HEADERS_OUT).exists()
    rec = _read(pk.RECORD_OUT)
    assert rec["complete"] is False and rec["aborted"]["reason"] == "SERVICE_UNAVAILABLE"
    assert rec["refused"] == 0 and rec["agree"] is None and rec["entries"] == []


def test_knob_one_deadline_then_a_render_is_a_clean_run(monkeypatch, tmp_path):
    pk, sent = _knob(monkeypatch, tmp_path, ["deadline", "render"])
    assert pk.main() == 0
    rec = _read(pk.RECORD_OUT)
    assert rec["agree"] is True and rec["refused"] == 0 and len(rec["transient"]) == 1
    assert len(_read(pk.HEADERS_OUT)["headers"]) == len(pk.COLUMNS)


def test_knob_agree_is_none_when_nothing_rendered(monkeypatch, tmp_path):
    pk, _ = _knob(monkeypatch, tmp_path, ["refuse"])
    assert pk.main() == 0
    rec = _read(pk.RECORD_OUT)
    assert rec["refused"] == len(pk.COLUMNS) and rec["agree"] is None


@pytest.mark.parametrize("end", [("150.0.0", "x"), ("149.1.0", "y")])
def test_knob_contract_move_withholds_the_header_cache(monkeypatch, tmp_path, end):
    pk, _ = _knob(monkeypatch, tmp_path, ["render"], versions=(("149.1.0", "x"), end))
    assert pk.main() == 2
    assert not Path(pk.HEADERS_OUT).exists()
    rec = _read(pk.RECORD_OUT)
    assert rec["contractMoved"] is True and rec["headersWritten"] is False
    assert (rec["versionAtEnd"], rec["buildShaAtEnd"]) == end


def test_knob_columns_and_stamp_come_from_the_environment(monkeypatch, tmp_path):
    cols = [{"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "anchor"}},
            {"metric": "BB_UPPER", "transformId": "value", "timeframe": {"rel": "anchor"}, "stdDev": 3}]
    (tmp_path / "cols.json").write_text(json.dumps(cols), encoding="utf-8")
    pk, sent = _knob(monkeypatch, tmp_path, ["render"])
    monkeypatch.setenv("KNOB_COLUMNS", str(tmp_path / "cols.json"))
    assert pk.main() == 0
    assert sent == [cols]
    assert _read(pk.RECORD_OUT)["columnsFrom"] == str(tmp_path / "cols.json")
    assert _read(pk.HEADERS_OUT)["headers"] == ["BB_UPPER_k", "RSI14_k"]
    monkeypatch.setenv("PROBE_DATE", "2099-01-02")
    fresh = _module("probe_knob_stamp", "probe_knob_spelling_149.py")
    assert fresh.RECORD_OUT == "data/audit/knob_spelling_probe_149_2099-01-02.json"
    assert fresh.HEADERS_OUT == "data/contract/columns/_probe_149_knobs_2099-01-02.json"


def test_knob_defaults_and_overwrite_guard_kept(monkeypatch, tmp_path):
    monkeypatch.delenv("PROBE_DATE", raising=False)
    monkeypatch.delenv("KNOB_COLUMNS", raising=False)
    fresh = _module("probe_knob_default", "probe_knob_spelling_149.py")
    assert fresh.RECORD_OUT == "data/audit/knob_spelling_probe_149_2026-11-07.json"
    assert len(fresh.columns()[0]) == 13 and fresh.columns()[1] == "built-in"
    pk, sent = _knob(monkeypatch, tmp_path, ["render"])
    Path(pk.HEADERS_OUT).parent.mkdir(parents=True)
    Path(pk.HEADERS_OUT).write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="one run per PROBE_DATE"):
        pk.main()
    assert sent == []


# --- finding 5: snapshot_vocabulary ----------------------------------------------------------------------------------

def _vocab(monkeypatch, tmp_path, answer):
    """answer(category) -> the stubbed list_strategy_vocabulary body."""
    import scripts.snapshot_vocabulary as sv
    vocab = tmp_path / "data" / "contract" / "vocabulary"
    vocab.mkdir(parents=True)
    shared = {k: f"stored {k}" for k in sv.INVARIANT}
    shared["_refreshed"] = {"at": "stored"}
    (vocab / "_shared.json").write_text(json.dumps(shared), encoding="utf-8")
    (tmp_path / "data" / "contract" / "categories.json").write_text(
        json.dumps({"categories": [{"category": "x", "metricCount": 1}]}), encoding="utf-8")
    monkeypatch.setattr(sv, "ROOT", tmp_path)
    monkeypatch.setattr(sv, "VOCAB", vocab)
    monkeypatch.setattr(sv, "version", lambda: {"contractVersion": "149.1.0", "buildSha": "x"})
    cats = {"categories": [{"category": c, "metricCount": 2} for c in ("crowd", "momentum", "structure")]}
    monkeypatch.setattr(sv, "call", lambda tool, args, timeout=240: cats if tool == "list_strategy_categories"
                        else answer(args["category"]))
    return sv, vocab


GOOD = {"transforms": ["value"], "timeframeRefs": [], "budgets": {"b": 1}, "previewExecutionLimits": {},
        "timeframes": ["1h"], "rankedTimeframes": [], "conditionGrammar": {}, "metrics": []}


def _stored(tmp_path) -> dict[str, bytes]:
    c = tmp_path / "data" / "contract"
    return {"shared": (c / "vocabulary" / "_shared.json").read_bytes(), "cats": (c / "categories.json").read_bytes()}


@pytest.mark.parametrize("bad", [
    {"code": "SERVICE_UNAVAILABLE", "message": "exceeded its 15000ms deadline"},
    {"code": "RATE_LIMITED", "message": "slow down"},
    {"isError": True, "content": [{"type": "text", "text": "upstream 502"}]},
])
def test_vocab_an_unknown_answer_stops_before_the_shared_blocks_are_rewritten(monkeypatch, tmp_path, bad):
    sv, vocab = _vocab(monkeypatch, tmp_path, lambda c: GOOD if c == "crowd" else bad)
    before = _stored(tmp_path)
    with pytest.raises(SystemExit) as exc:
        sv.main()
    assert "raw kept" in str(exc.value.code)
    assert _stored(tmp_path) == before
    assert [p.name for p in vocab.iterdir() if p.is_dir()], "the raw dir is kept as evidence"


def test_vocab_every_category_unrecognised_never_blanks_the_blocks(monkeypatch, tmp_path):
    sv, _ = _vocab(monkeypatch, tmp_path, lambda c: {"isError": True, "content": []})
    before = _stored(tmp_path)
    with pytest.raises(SystemExit):
        sv.main()
    assert _stored(tmp_path) == before


def test_vocab_a_known_refusal_is_stored_and_the_rest_rewritten(monkeypatch, tmp_path):
    sv, vocab = _vocab(monkeypatch, tmp_path, lambda c: {"code": "RESULT_TOO_LARGE", "message": "too large"}
                       if c == "structure" else GOOD)
    assert sv.main() == 0
    shared = json.loads((vocab / "_shared.json").read_text(encoding="utf-8"))
    assert shared["transforms"] == ["value"] and "RESULT_TOO_LARGE" in shared["_refreshed"]["how"]


# --- findings 6 + 7: sweep_render_coverage ---------------------------------------------------------------------------

RENDER = {"budgetUsage": {}, "authoring": {"conditionColumns": [
    {"title": "sweep 1", "outputs": [{"header": "X_value"}]}]}}


def _sweep(monkeypatch):
    mod = _module("sweep_render_coverage_guard", "sweep_render_coverage.py")
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(mod, "SWEEP_CONTRACT", None)
    mod._calls[0] = 0
    return mod


def _targets(*metrics):
    return [(SimpleNamespace(metric=m, transform="value", chained=None, operand=None, ordering=None,
                             to_column=lambda m=m: SimpleNamespace(metric=m)),
             {"metric": m, "transformId": "value"}) for m in metrics]


class _Proc:
    calls = 0
    plan: list = []

    def __init__(self, *a, **k):
        type(self).calls += 1
        self._step = type(self).plan[min(type(self).calls, len(type(self).plan)) - 1]

    def communicate(self, data=None, timeout=None):
        if self._step == "TIMEOUT":
            raise subprocess.TimeoutExpired("npx", timeout or 1)
        return self._step

    def kill(self):
        pass


def _popen(*plan):
    _Proc.calls, _Proc.plan = 0, list(plan)
    return _Proc


def test_sweep_outage_pattern_covers_the_deadline_and_negotiation(monkeypatch):
    mod = _sweep(monkeypatch)
    assert mod.PLATFORM_DOWN.search(json.dumps(DEADLINE))
    assert mod.PLATFORM_DOWN.search("[mcporter] battlegrid-anbu.preview_strategy_report: Version negotiation failed")


def test_sweep_deadline_body_is_never_bisected_into_a_refusal(monkeypatch):
    """repro_sweep.py: every preview holding RSI14 answers the deadline body."""
    mod = _sweep(monkeypatch)
    sent = []

    def fake_call(tool, args, timeout=240):
        cols = [c for s in args["source"]["sections"] for c in s["columns"]]
        sent.append(cols)
        if any(c["metric"] == "RSI14" for c in cols):
            return DEADLINE, None
        return {"budgetUsage": {}, "authoring": {"conditionColumns": [
            {"title": "sweep 1", "outputs": [{"header": c["metric"].lower()} for c in cols]}]}}, None
    monkeypatch.setattr(mod, "call", fake_call)
    out = mod.run_sweep(_targets("CLOSE", "RSI14", "ADX", "ATR"))
    assert out["refusals"] == []
    assert out["aborted"] is not None and "SERVICE_UNAVAILABLE" in out["aborted"]["message"]
    assert len(sent) == 2, "one re-send of the same batch, then the stop"


@pytest.mark.parametrize("answer", [
    (json.dumps(DEADLINE).encode(), b""),                                                    # deadline body on stdout
    (b"", b"[mcporter] battlegrid-anbu.preview_strategy_report: Version negotiation failed\n"),  # no HTTP code
    "TIMEOUT",
    (b"not json at all", b""),
])
def test_sweep_transport_errors_retry_once_then_stop(monkeypatch, answer):
    mod = _sweep(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(answer))
    out = mod.run_sweep(_targets("A", "B", "C", "D"), per_call=4)
    assert _Proc.calls == 2, "re-sent once, never bisected"
    assert out["refusals"] == [] and out["sent"] == [] and out["aborted"] is not None


def test_sweep_one_transient_then_a_render_completes(monkeypatch):
    mod = _sweep(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen((json.dumps(DEADLINE).encode(), b""),
                                                        (json.dumps(RENDER).encode(), b"")))
    out = mod.run_sweep(_targets("A", "B"), per_call=4)
    assert _Proc.calls == 2 and out["aborted"] is None and out["refusals"] == [] and out["headers"] == ["X_value"]


def test_sweep_a_timeout_from_any_render_fn_is_never_a_refusal(monkeypatch):
    mod = _sweep(monkeypatch)
    out = mod.run_sweep(_targets("A", "B"), lambda cols: (None, "TIMEOUT"), per_call=4)
    assert out["refusals"] == [] and out["aborted"] is not None


def _sweep_main(monkeypatch, tmp_path, versions, plan=None, targets=("X",)):
    """versions: (contractVersion, buildSha) tuples or "FAIL" (the GET raises, as on the 11-05 nginx 502), one per
    read. plan: the Popen answers (default: one render). With more than one target, one column per batch."""
    mod = _sweep(monkeypatch)
    monkeypatch.setattr(mod, "HEADERS_OUT", str(tmp_path / "columns" / "h.json"))
    monkeypatch.setattr(mod, "RECORD_OUT", str(tmp_path / "audit" / "r.json"))
    monkeypatch.delenv("SWEEP_OVERWRITE", raising=False)
    monkeypatch.setattr(mod, "load", lambda: None)
    monkeypatch.setattr(mod, "rendered_headers", lambda: set())
    monkeypatch.setattr(mod, "collect_targets", lambda c: ("structural", _targets(*targets)))
    monkeypatch.setattr(mod, "outputs_for", lambda col, c: [SimpleNamespace(header=col.metric + "_value")])
    monkeypatch.setattr(mod.subprocess, "Popen", _popen(*(plan or [(json.dumps(RENDER).encode(), b"")])))
    if len(targets) > 1:
        monkeypatch.setattr(mod, "run_sweep", lambda t, orig=mod.run_sweep: orig(t, per_call=1))
    vs = iter(versions)

    def version():
        v = next(vs)
        if v == "FAIL":
            raise mod.SweepStopped("GET /mcp/version failed (HTTPError: HTTP Error 502: Bad Gateway)")
        return dict(zip(("contractVersion", "buildSha"), v))
    monkeypatch.setattr(mod, "version", version)
    return mod


def test_sweep_record_names_the_contract_at_start_and_end(monkeypatch, tmp_path):
    mod = _sweep_main(monkeypatch, tmp_path, [("149.1.0", "aa4ab640"), ("149.1.0", "aa4ab640")])
    assert mod.main() == 0
    rec = _read(tmp_path / "audit" / "r.json")
    assert (rec["contractVersion"], rec["buildSha"], rec["versionAtEnd"], rec["buildShaAtEnd"]) == \
        ("149.1.0", "aa4ab640", "149.1.0", "aa4ab640")
    assert rec["contractMoved"] is False and rec["complete"] is True
    assert (tmp_path / "columns" / "h.json").exists()


@pytest.mark.parametrize("end", [("150.0.0", "aa4ab640"), ("149.1.0", "beefcafe")])
def test_sweep_a_contract_move_marks_the_record_and_exits_non_zero(monkeypatch, tmp_path, end):
    mod = _sweep_main(monkeypatch, tmp_path, [("149.1.0", "aa4ab640"), end])
    assert mod.main() == 2
    rec = _read(tmp_path / "audit" / "r.json")
    assert rec["contractMoved"] is True and (rec["versionAtEnd"], rec["buildShaAtEnd"]) == end
    assert not (tmp_path / "columns" / "h.json").exists()     # the seen-header cache is held back
    assert rec["headersWritten"] is False and rec["headersWithheld"] == ["X_value"], "kept in the record instead"


# ======================================================================================================================
# Review pass 2 (2026-11-08), findings 2-9. Each test below fails on the 94027ea scripts.
# ======================================================================================================================

OK = ("149.1.0", "aa4ab640")
STDERR_502 = b"[mcporter] battlegrid-anbu.preview_strategy_report responded with HTTP 502"
RATE_LIMIT = (b"[mcporter] Error POSTing to endpoint: Rate limited: 3 requests/second sustained, up to 120 banked. "
              b"Retry after 1s, or wait 40s for full capacity.")


# --- finding 2: the knob probe predicts before the first call; an unpredictable cell is sent and recorded -----------

def test_knob_an_unpredictable_cell_is_still_sent_and_its_render_recorded(monkeypatch, tmp_path):
    """r_knob.py K2, on the real omega: MACD_SIGNAL out of KNOB_SPELLING_RENDERED (the table before the 11-08 render),
    so fanout raises ValueError for `fast 8` - the cell the probe exists to render."""
    import omega.fanout as F
    from omega import contract as OC
    import scripts.probe_knob_spelling_149 as pk
    monkeypatch.delitem(F.KNOB_SPELLING_RENDERED, "MACD_SIGNAL")
    cols = [{"metric": "MACD_SIGNAL", "transformId": "value", "timeframe": {"rel": "anchor"}, "fast": 8},
            {"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "anchor"}}]
    rsi = [o.header for o in F.outputs_for(pk.Column(**cols[1]), OC.load())]
    (tmp_path / "cols.json").write_text(json.dumps(cols), encoding="utf-8")
    monkeypatch.setenv("KNOB_COLUMNS", str(tmp_path / "cols.json"))
    monkeypatch.setattr(pk, "RECORD_OUT", str(tmp_path / "audit" / "knob.json"))
    monkeypatch.setattr(pk, "HEADERS_OUT", str(tmp_path / "columns" / "knob_headers.json"))
    monkeypatch.setattr(pk, "version", lambda: {"contractVersion": "149.1.0", "buildSha": "x"})
    order = []
    real = pk.outputs_for

    def outputs_for(col, c):
        order.append("predict")
        return real(col, c)
    monkeypatch.setattr(pk, "outputs_for", outputs_for)

    def preview(sections):
        order.append("preview")
        return {}, {"renderedSections": [{"section": {"columns": [{"key": k} for k in
                                                                  ["MACDsig_fast8slow26sig9"] + rsi]}}],
                    "authoring": {}}, None
    monkeypatch.setattr(pk, "preview", preview)
    assert pk.main() == 0
    assert order.index("preview") > max(i for i, x in enumerate(order) if x == "predict"), "predicted before any call"
    rec = _read(pk.RECORD_OUT)
    (entry,) = rec["entries"]
    assert entry["predicted"] is None and "MACD_SIGNAL" in entry["unpredicted"] and entry["agree"] is None
    assert entry["rendered"] == ["MACDsig_fast8slow26sig9"] + rsi, "the live answer is recorded"
    assert rec["unpredicted"] == 1 and rec["agree"] is None
    assert "MACDsig_fast8slow26sig9" in _read(pk.HEADERS_OUT)["headers"]


def test_knob_per_column_entries_mark_only_the_unpredictable_column(monkeypatch, tmp_path):
    pk, _ = _knob(monkeypatch, tmp_path, ["refuse", "render"])

    def outputs_for(col, c):
        if col.metric == "PPO_SIGNAL":
            raise ValueError("PPO_SIGNAL at ['fast'] off its default was never rendered (KNOB_SPELLING_RENDERED)")
        return [SimpleNamespace(header=col.metric + "_k")]
    monkeypatch.setattr(pk, "outputs_for", outputs_for)
    assert pk.main() == 0
    rec = _read(pk.RECORD_OUT)
    assert len(rec["entries"]) == len(pk.COLUMNS) and rec["unpredicted"] == 1
    ppo = [e for e in rec["entries"] if e["columns"][0]["metric"] == "PPO_SIGNAL"][0]
    assert ppo["predicted"] is None and ppo["agree"] is None and ppo["rendered"] == ["PPO_SIGNAL_k"]
    assert all(e["agree"] is True for e in rec["entries"] if e is not ppo) and rec["agree"] is True


# --- finding 3: a sweep stopped by an outage keeps its headers and exits 3 ------------------------------------------

def test_sweep_an_outage_stop_with_an_unreadable_end_keeps_the_headers_and_exits_3(monkeypatch, tmp_path):
    """r_sweep.py S1: batch 1 renders, batch 2 meets a gateway 502, the end read fails the same way (twice)."""
    mod = _sweep_main(monkeypatch, tmp_path, [OK, "FAIL", "FAIL"], targets=("M0", "M1"),
                      plan=[(json.dumps(RENDER).encode(), b""), (b"", STDERR_502)])
    assert mod.main() == 3, "a stop is a stop, whatever the end read said"
    rec = _read(tmp_path / "audit" / "r.json")
    assert rec["complete"] is False and rec["contractMoved"] is None and "end" in rec["versionReadErrors"]
    assert rec["headersWritten"] is False and rec["headersWithheld"] == ["X_value"], "the rendered header is kept"
    assert "version read failed" in rec["headersWithheldBecause"]
    assert not (tmp_path / "columns" / "h.json").exists()


def test_sweep_the_end_read_is_retried_once(monkeypatch, tmp_path):
    mod = _sweep_main(monkeypatch, tmp_path, [OK, "FAIL", OK], targets=("M0", "M1"),
                      plan=[(json.dumps(RENDER).encode(), b""), (b"", STDERR_502)])
    assert mod.main() == 3
    rec = _read(tmp_path / "audit" / "r.json")
    assert rec["contractMoved"] is False and rec["headersWritten"] is True
    assert _read(tmp_path / "columns" / "h.json")["headers"] == ["X_value"]


def test_sweep_a_completed_run_with_an_unreadable_end_exits_2_and_keeps_the_headers(monkeypatch, tmp_path):
    mod = _sweep_main(monkeypatch, tmp_path, [OK, "FAIL", "FAIL"])
    assert mod.main() == 2
    rec = _read(tmp_path / "audit" / "r.json")
    assert rec["complete"] is True and rec["contractMoved"] is None and rec["headersWithheld"] == ["X_value"]


# --- finding 4: empty stdout with a transport error is never bisected into refusals ----------------------------------

def test_sweep_a_rate_limit_backs_off_and_is_never_a_refusal(monkeypatch):
    mod = _sweep(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen((b"", RATE_LIMIT)))
    out = mod.run_sweep(_targets("A", "B"), per_call=2)
    assert out["refusals"] == [] and out["aborted"] is not None and "ate limited" in out["aborted"]["message"]
    assert _Proc.calls == 4, "backed off and re-sent, then the stop - no bisect"


def test_sweep_a_rate_limit_then_a_render_completes(monkeypatch):
    mod = _sweep(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen((b"", RATE_LIMIT), (json.dumps(RENDER).encode(), b"")))
    out = mod.run_sweep(_targets("A", "B"), per_call=2)
    assert out["aborted"] is None and out["refusals"] == [] and out["headers"] == ["X_value"] and _Proc.calls == 2


@pytest.mark.parametrize("stderr", [b"[mcporter] fetch failed: read ECONNRESET", b"",
                                    b"[mcporter] Error POSTing to endpoint: socket hang up"])
def test_sweep_a_transport_error_on_stderr_is_resent_once_then_stops(monkeypatch, stderr):
    mod = _sweep(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen((b"", stderr)))
    out = mod.run_sweep(_targets("A", "B"), per_call=2)
    assert out["refusals"] == [] and out["aborted"] is not None and _Proc.calls == 2


# --- finding 5: a code other than VALIDATION_ERROR is never a refusal, in any of the three scripts -------------------

@pytest.mark.parametrize("body", [{"code": "RATE_LIMITED", "message": "x"}, {"code": "INTERNAL_ERROR", "message": "x"},
                                  {"code": "UNAUTHORIZED", "message": "x"},
                                  {"isError": True, "content": [{"type": "text", "text": "upstream"}]}])
def test_sweep_a_non_validation_body_is_never_bisected(monkeypatch, body):
    mod = _sweep(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "Popen", _popen((json.dumps(body).encode(), b"")))
    out = mod.run_sweep(_targets("A", "B"), per_call=2)
    assert out["refusals"] == [] and out["aborted"] is not None
    assert _Proc.calls == (4 if body.get("code") == "RATE_LIMITED" else 2)


def test_sweep_a_validation_error_body_is_still_bisected_to_its_column(monkeypatch):
    mod = _sweep(monkeypatch)
    refused = {"code": "VALIDATION_ERROR", "message": "no", "details": {"authoringCode": "X"}}
    seen = []

    class Proc:
        def __init__(self, *a, **k):
            pass

        def communicate(self, data=None, timeout=None):
            cols = [c["metric"] for s in json.loads(data)["source"]["sections"] for c in s["columns"]]
            seen.append(cols)
            if "B" in cols:
                return json.dumps(refused).encode(), b""
            return json.dumps(RENDER).encode(), b""

        def kill(self):
            pass
    monkeypatch.setattr(mod.subprocess, "Popen", Proc)
    out = mod.run_sweep(_targets("A", "B"), per_call=2)
    assert out["aborted"] is None and [r["column"]["metric"] for r in out["refusals"]] == ["B"]


@pytest.mark.parametrize("code", ["RATE_LIMITED", "INTERNAL_ERROR", "UNAUTHORIZED"])
def test_knob_a_non_validation_code_stops_the_run_and_is_no_refusal(monkeypatch, tmp_path, code):
    """r_knob.py K4: until pass 2 this was `refused: 13`, a written header cache and exit 0."""
    pk, sent = _knob(monkeypatch, tmp_path, [code])
    assert pk.main() == 3
    assert len(sent) == 2, "re-sent once, then the stop"
    rec = _read(pk.RECORD_OUT)
    assert rec["refused"] == 0 and rec["complete"] is False and rec["aborted"]["reason"] == "TransportFailure"
    assert not Path(pk.HEADERS_OUT).exists()


def _probe_mod(monkeypatch, tmp_path):
    """probe_authoring_148 with its own call() / preview(); only subprocess.Popen is stubbed (by _probe_popen)."""
    monkeypatch.setenv("PROBE_HINTS", str(tmp_path / "hints"))
    monkeypatch.setenv("PROBE_DATE", "2099-01-01")
    monkeypatch.delenv("PROBE_CONTRACT", raising=False)
    return _module("probe_authoring_148_codes", "probe_authoring_148.py")


def _probe_popen(monkeypatch, mod, *answers):
    """Popen for probe_authoring_148.call: each answer is (stdout bytes, stderr bytes), the last one repeats."""
    _Proc.calls, _Proc.plan = 0, list(answers)
    monkeypatch.setattr(mod.subprocess, "Popen", _Proc)
    monkeypatch.setattr(mod, "_MIN_INTERVAL", 0.0)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)


@pytest.mark.parametrize("body", [{"code": "INTERNAL_ERROR", "message": "boom"},
                                  {"code": "UNAUTHORIZED", "message": "no"},
                                  {"code": "NOT_FOUND", "message": "x", "details": {}}])
def test_probe_a_non_validation_code_is_resent_once_then_a_transport_failure(monkeypatch, tmp_path, body):
    mod = _probe_mod(monkeypatch, tmp_path)
    _probe_popen(monkeypatch, mod, (json.dumps(body).encode(), b""))
    with pytest.raises(mod.TransportFailure, match=body["code"]):
        mod.preview([])
    assert _Proc.calls == 2


def test_probe_a_rate_limited_body_backs_off_then_a_render_is_kept(monkeypatch, tmp_path):
    mod = _probe_mod(monkeypatch, tmp_path)
    _probe_popen(monkeypatch, mod, (json.dumps({"code": "RATE_LIMITED", "message": "slow"}).encode(), b""),
                 (json.dumps(RENDER).encode(), b""))
    _, d, e = mod.preview([])
    assert d is not None and e is None and _Proc.calls == 2


def test_probe_validation_and_deadline_bodies_are_still_answers(monkeypatch, tmp_path):
    mod = _probe_mod(monkeypatch, tmp_path)
    _probe_popen(monkeypatch, mod, (json.dumps(DEADLINE).encode(), b""))
    assert mod.preview([])[2]["code"] == "SERVICE_UNAVAILABLE" and _Proc.calls == 1
    _probe_popen(monkeypatch, mod, (json.dumps({"code": "VALIDATION_ERROR", "message": "no"}).encode(), b""))
    assert mod.preview([])[2]["code"] == "VALIDATION_ERROR" and _Proc.calls == 1


def test_probe_an_empty_stdout_transport_error_is_resent_once(monkeypatch, tmp_path):
    mod = _probe_mod(monkeypatch, tmp_path)
    _probe_popen(monkeypatch, mod, (b"", b"[mcporter] fetch failed: read ECONNRESET"), (json.dumps(RENDER).encode(), b""))
    assert mod.call("preview_strategy_report", {}) == RENDER and _Proc.calls == 2


# --- findings 6 + 7: probe_authoring_148's end of run, and every version read wrapped --------------------------------

KNOB_NAMES = ("accelerationIncrement", "accelerationMaximum", "accelerationStart", "atrPeriod", "dSmoothing", "fast",
              "kSmoothing", "multiplier", "period", "rsiPeriod", "signal", "slow", "stdDev", "leftBars", "rightBars",
              "equalBars")


def _probe_run(monkeypatch, tmp_path, version_at):
    """probe_authoring_148.main() with every group sent against stubs (each preview renders one header).
    version_at(previews_sent, total_or_None) -> a version dict, or raises. Returns (exit, record, cache, total)."""
    def setup():
        mod = _module("probe_authoring_148_end", "probe_authoring_148.py")
        monkeypatch.setattr(mod, "RECORD_OUT", str(tmp_path / "audit" / "record.json"))
        monkeypatch.setattr(mod, "HEADERS_OUT", str(tmp_path / "columns" / "headers.json"))
        monkeypatch.setattr(mod.time, "sleep", lambda s: None)
        monkeypatch.setattr(mod, "hint", lambda metric: {
            "transforms": [{"id": t, "authoring": {"parameters": {"window": {"maximum": 50}}}}
                           for t in ("value", "rma", "wma", "rsi", "cci")],
            "parameters": {k: {"defaultValue": 5, "minimum": 2, "maximum": 50} for k in KNOB_NAMES},
            "spreadOperands": ["CLOSE"]})
        n = [0]

        def preview(sections, tickers=("BTC",), timeframe="1h"):
            n[0] += 1
            return {}, {"budgetUsage": {}, "authoring": {"conditionColumns": [
                {"title": "t", "outputs": [{"header": f"h{n[0]}"}]}]}, "renderedSections": []}, None
        monkeypatch.setattr(mod, "preview", preview)
        return mod, n

    monkeypatch.setenv("PROBE_HINTS", str(tmp_path / "hints"))
    monkeypatch.setenv("PROBE_DATE", "2099-01-01")
    monkeypatch.delenv("PROBE_CONTRACT", raising=False)
    monkeypatch.delenv("PROBE_OVERWRITE", raising=False)
    mod, n = setup()                                       # a clean run first: how many previews the groups send
    monkeypatch.setattr(mod, "version", lambda: {"contractVersion": "149.1.0", "buildSha": "aa"})
    assert mod.main() == 0
    total = n[0]
    for p in (mod.RECORD_OUT, mod.HEADERS_OUT):
        os.remove(p)
    mod, n = setup()
    reads = [0]

    def version():
        reads[0] += 1
        return {"contractVersion": "149.1.0", "buildSha": "aa"} if reads[0] == 1 else version_at(n[0], total)
    monkeypatch.setattr(mod, "version", version)
    code = mod.main()
    cache = Path(mod.HEADERS_OUT)
    return code, _read(mod.RECORD_OUT), (_read(cache) if cache.exists() else None), total


def _at_end(end):
    """A version reader answering 149.1.0 / aa mid-run and `end` (a dict, or an exception) after the last preview."""
    def read(sent, total):
        if sent < total:
            return {"contractVersion": "149.1.0", "buildSha": "aa"}
        if isinstance(end, Exception):
            raise end
        return end
    return read


@pytest.mark.parametrize("end", [{"contractVersion": "150.0.0", "buildSha": "aa"},
                                 {"contractVersion": "149.1.0", "buildSha": "bb"}])
def test_probe_a_moved_contract_or_build_withholds_the_cache_and_exits_2(monkeypatch, tmp_path, end):
    """r_probe.py P1: the cache was written on a move, and a moved build exited 0."""
    code, rec, cache, total = _probe_run(monkeypatch, tmp_path, _at_end(end))
    assert code == 2 and cache is None
    assert rec["contractMoved"] is True and (rec["versionAtEnd"], rec["buildShaAtEnd"]) == (end["contractVersion"],
                                                                                            end["buildSha"])
    assert rec["headersWritten"] is False and len(rec["headersWithheld"]) == total == rec["counts"]["probes"]
    assert "moved" in rec["headersWithheldBecause"]


def test_probe_an_unreadable_end_is_worded_unreadable_and_withholds_the_cache(monkeypatch, tmp_path, capsys):
    code, rec, cache, total = _probe_run(monkeypatch, tmp_path, _at_end(OSError("HTTP Error 502: Bad Gateway")))
    assert code == 2 and cache is None and rec["complete"] is True
    assert rec["contractMoved"] is None and "502" in rec["versionReadErrors"]["end"]
    assert len(rec["headersWithheld"]) == total
    out = capsys.readouterr().out
    assert "could not be read" in out and "contract moved during the run" not in out


def test_probe_the_end_read_is_retried_once(monkeypatch, tmp_path):
    fails = [0]

    def read(sent, total):
        if sent >= total and fails[0] == 0:
            fails[0] += 1
            raise OSError("HTTP Error 502: Bad Gateway")
        return {"contractVersion": "149.1.0", "buildSha": "aa"}
    code, rec, cache, total = _probe_run(monkeypatch, tmp_path, read)
    assert code == 0 and rec["contractMoved"] is False and len(cache["headers"]) == total


def test_probe_the_gate_compares_the_build_too(monkeypatch, tmp_path):
    code, rec, cache, _ = _probe_run(monkeypatch, tmp_path, lambda sent, total: {"contractVersion": "149.1.0",
                                                                                 "buildSha": "bb"})
    assert code == 3 and rec["aborted"]["reason"] == "ContractMoved"
    assert rec["counts"]["probes"] == 25 and cache is None


def test_probe_a_failed_gate_read_stops_with_the_partial_record(monkeypatch, tmp_path):
    """r_probe.py P2: the read at probe 25 raised past main() and nothing was written."""
    reads = [0]

    def read(sent, total):
        reads[0] += 1
        if reads[0] == 1:                                  # the first gate read (after 25 probes) fails
            raise OSError("HTTP Error 502: Bad Gateway")
        return {"contractVersion": "149.1.0", "buildSha": "aa"}
    code, rec, cache, _ = _probe_run(monkeypatch, tmp_path, read)
    assert code == 3 and rec["aborted"]["reason"] == "VersionReadFailed" and "502" in rec["aborted"]["message"]
    assert rec["counts"]["probes"] == 25 and rec["complete"] is False
    assert rec["contractMoved"] is False and len(cache["headers"]) == 25, "rendered under a known, unmoved contract"


def test_probe_a_failed_start_read_stops_before_any_call(monkeypatch, tmp_path):
    mod = _probe(monkeypatch, tmp_path)

    def version():
        raise OSError("HTTP Error 502: Bad Gateway")
    monkeypatch.setattr(mod, "version", version)
    with pytest.raises(SystemExit, match="502"):
        mod.main()
    assert not (tmp_path / "record.json").exists()


@pytest.mark.parametrize("end, code, cached", [(["FAIL", "FAIL"], 2, False), (["FAIL", OK], 0, True)])
def test_knob_the_end_read_is_wrapped_and_retried_once(monkeypatch, tmp_path, end, code, cached):
    """r_knob.py K3: an unguarded end read raised after the previews and nothing was written."""
    pk, _ = _knob(monkeypatch, tmp_path, ["render"], versions=[OK] + end)
    assert pk.main() == code
    rec = _read(pk.RECORD_OUT)
    assert Path(pk.HEADERS_OUT).exists() is cached
    if not cached:
        assert rec["contractMoved"] is None and rec["headersWritten"] is False
        assert rec["headersWithheld"] == sorted(c["metric"] + "_k" for c in pk.COLUMNS)


def test_knob_a_failed_start_read_stops_before_any_call(monkeypatch, tmp_path):
    pk, sent = _knob(monkeypatch, tmp_path, ["render"], versions=["FAIL"])
    with pytest.raises(SystemExit, match="getaddrinfo"):
        pk.main()
    assert sent == [] and not Path(pk.RECORD_OUT).exists()


# --- finding 8: a deadline stop during the per-column re-sends keeps the answered entries -----------------------------

def test_knob_a_stop_during_the_resends_keeps_every_answered_entry(monkeypatch, tmp_path):
    """r_knob.py K1: the batch is refused, columns 0-2 render, column 3 meets the deadline twice."""
    pk, sent = _knob(monkeypatch, tmp_path, ["refuse", "render", "render", "render", "deadline"])
    assert pk.main() == 3
    assert len(sent) == 1 + 3 + 2
    rec = _read(pk.RECORD_OUT)
    assert rec["complete"] is False and rec["aborted"]["reason"] == "SERVICE_UNAVAILABLE"
    assert [e["columns"][0]["metric"] for e in rec["entries"]] == [c["metric"] for c in pk.COLUMNS[:3]]
    assert all(e["agree"] is True for e in rec["entries"]) and rec["agree"] is True
    assert not Path(pk.HEADERS_OUT).exists() and rec["headersWritten"] is False
    assert rec["headersWithheld"] == sorted(c["metric"] + "_k" for c in pk.COLUMNS[:3])


# --- finding 9: refresh_metric_contracts reads the contract and refuses a mixed or unknown one ----------------------

ABC = {n: _hint(n) for n in "ABC"}


def _index(run) -> dict:
    return json.loads((run["metrics"] / "_index.json").read_text(encoding="utf-8"))


@win_only
def test_refresh_phase_2_refuses_hints_of_an_unknown_contract(tmp_path):
    run = _refresh(tmp_path, ["A", "B", "C"], ABC, stored=None)
    out = run["proc"].stdout + run["proc"].stderr
    assert run["proc"].returncode != 0 and "_version.json" in out and "EXTRACTION_CONTRACT" in out, out
    assert run["after"] == run["before"] and run["calls"] == 0


@win_only
def test_refresh_an_asserted_contract_is_recorded_as_asserted(tmp_path):
    run = _refresh(tmp_path, ["A", "B", "C"], ABC, stored=None, asserted="149.1.0")
    assert run["proc"].returncode == 0, run["proc"].stdout + run["proc"].stderr
    idx = _index(run)
    assert idx["metricCount"] == 3 and idx["contractVersion"] == "149.1.0" and idx["buildSha"] is None
    assert idx["contractKnownBy"].startswith("asserted")


@win_only
def test_refresh_an_assertion_that_differs_from_the_read_contract_is_refused(tmp_path):
    run = _refresh(tmp_path, ["A", "B", "C"], ABC, asserted="150.0.0")
    out = run["proc"].stdout + run["proc"].stderr
    assert run["proc"].returncode != 0 and "150.0.0" in out and "149.1.0" in out, out
    assert run["after"] == run["before"]


@win_only
def test_refresh_the_index_records_the_contract_read(tmp_path):
    run = _refresh(tmp_path, ["A", "B", "C"], ABC, asserted="149.1.0")
    assert run["proc"].returncode == 0, run["proc"].stdout + run["proc"].stderr
    idx = _index(run)
    assert (idx["contractVersion"], idx["buildSha"]) == ("149.1.0", "aa4ab640")
    assert idx["contractKnownBy"].startswith("read") and "2999-01-01T00:00:00Z" in idx["contractKnownBy"]


@win_only
@pytest.mark.parametrize("served", [{"contractVersion": "150.0.0", "buildSha": "aa4ab640"},
                                    {"contractVersion": "149.1.0", "buildSha": "beefcafe"}])
def test_refresh_a_resume_at_another_contract_stops_before_fetching(tmp_path, served):
    run = _refresh(tmp_path, ["A", "B", "C"], {"A": _hint("A"), "B": _hint("B")}, served=served,
                   stub_stdout=json.dumps(_hint("C")))
    out = run["proc"].stdout + run["proc"].stderr
    assert run["proc"].returncode != 0 and run["calls"] == 0, out
    assert not (run["hints"] / "C.json").exists() and run["after"] == run["before"]


@win_only
def test_refresh_a_partial_raw_dir_without_a_version_is_not_resumed(tmp_path):
    run = _refresh(tmp_path, ["A", "B", "C"], {"A": _hint("A"), "B": _hint("B")}, stored=None,
                   stub_stdout=json.dumps(_hint("C")))
    out = run["proc"].stdout + run["proc"].stderr
    assert run["proc"].returncode != 0 and run["calls"] == 0 and "unknown" in out, out
    assert not (run["hints"] / "_version.json").exists() and run["after"] == run["before"]


@win_only
def test_refresh_a_failed_version_read_stops_before_fetching(tmp_path):
    run = _refresh(tmp_path, ["A", "B", "C"], {"A": _hint("A"), "B": _hint("B")}, served=None,
                   stub_stdout=json.dumps(_hint("C")))
    assert run["proc"].returncode != 0 and run["calls"] == 0, run["proc"].stdout + run["proc"].stderr
    assert run["after"] == run["before"]


@win_only
def test_refresh_a_fresh_fetch_stores_the_contract_it_read(tmp_path):
    run = _refresh(tmp_path, ["A"], {}, stored=None, stub_stdout=json.dumps(_hint("A")))
    assert run["proc"].returncode == 0 and run["calls"] == 1, run["proc"].stdout + run["proc"].stderr
    stored = json.loads((run["hints"] / "_version.json").read_text(encoding="utf-8"))
    assert (stored["contractVersion"], stored["buildSha"]) == ("149.1.0", "aa4ab640") and stored["readAt"]
    assert (_index(run)["contractVersion"], _index(run)["buildSha"]) == ("149.1.0", "aa4ab640")


@win_only
def test_refresh_a_contract_that_moves_mid_fetch_stops_the_fetch(tmp_path):
    """The stub npx serves 150.0.0 from its first call on: the read every 40 fetches sees the move."""
    roster = [f"M{i:02d}" for i in range(45)]
    run = _refresh(tmp_path, roster, {}, stored=None, stub_stdout=json.dumps(_hint("M00")),
                   served_after_call={"contractVersion": "150.0.0", "buildSha": "aa4ab640"})
    out = run["proc"].stdout + run["proc"].stderr
    assert run["proc"].returncode != 0 and run["calls"] == 40 and "150.0.0" in out, out
    assert run["after"] == run["before"]


# --- pass-2 re-review (2026-11-08): a stopped fetch taints its raw dir, so a re-run cannot build a mixed corpus ------

@win_only
def test_refresh_a_mid_fetch_move_taints_the_raw_dir(tmp_path):
    roster = [f"M{i:02d}" for i in range(45)]
    run = _refresh(tmp_path, roster, {}, stored=None, stub_stdout=json.dumps(_hint("M00")),
                   served_after_call={"contractVersion": "150.0.0", "buildSha": "aa4ab640"})
    assert run["proc"].returncode != 0
    stored = json.loads((run["hints"] / "_version.json").read_text(encoding="utf-8"))
    assert stored["contractVersion"] == "149.1.0" and "150.0.0" in stored["tainted"]["reason"]


@win_only
def test_refresh_a_rerun_over_a_tainted_raw_dir_builds_nothing(tmp_path):
    """Every hint cached, nothing left to fetch, so no gate runs: before the taint, phase 2 built the corpus and
    labelled it as read at the old contract."""
    tainted = {**SERVED, "tainted": {"reason": "served 150.0.0 (aa4ab640) after the last fetch", "at": "2999"}}
    run = _refresh(tmp_path, ["A", "B", "C"], ABC, stored=tainted,
                   served={"contractVersion": "150.0.0", "buildSha": "aa4ab640"})
    out = run["proc"].stdout + run["proc"].stderr
    assert run["proc"].returncode != 0 and "tainted" in out and run["calls"] == 0, out
    assert run["after"] == run["before"]
