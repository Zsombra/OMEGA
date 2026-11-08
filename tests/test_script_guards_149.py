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


def _refresh(tmp_path: Path, roster, raw: dict, stub_stdout: str | None = None, old_batches=False,
             pre_archive=False) -> dict:
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
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "npx.cmd").write_text(
        "@echo off\r\n" f'echo call>>"{shim / "calls.log"}"\r\n'
        + (f"echo {stub_stdout}\r\nexit /b 0\r\n" if stub_stdout else "echo TIMEOUT 1>&2\r\nexit /b 1\r\n"),
        encoding="utf-8")
    before = _files(tree / "data")
    env = {**os.environ, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}", "EXTRACTION_STAMP": "29990101",
           "EXTRACTION_SCRATCH": str(scratch), "EXTRACTION_ARCHIVE": "29990100"}
    proc = subprocess.run([sys.executable, str(tree / "scripts" / "refresh_metric_contracts.py")], cwd=tree, env=env,
                          capture_output=True, text=True, timeout=120)
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
    monkeypatch.setattr(pk, "version", lambda: dict(zip(("contractVersion", "buildSha"), next(vs))))
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


def _sweep_main(monkeypatch, tmp_path, versions):
    mod = _sweep(monkeypatch)
    monkeypatch.setattr(mod, "HEADERS_OUT", str(tmp_path / "columns" / "h.json"))
    monkeypatch.setattr(mod, "RECORD_OUT", str(tmp_path / "audit" / "r.json"))
    monkeypatch.delenv("SWEEP_OVERWRITE", raising=False)
    monkeypatch.setattr(mod, "load", lambda: None)
    monkeypatch.setattr(mod, "rendered_headers", lambda: set())
    monkeypatch.setattr(mod, "collect_targets", lambda c: ("structural", _targets("X")))
    monkeypatch.setattr(mod, "outputs_for", lambda col, c: [SimpleNamespace(header=col.metric + "_value")])
    monkeypatch.setattr(mod.subprocess, "Popen", _popen((json.dumps(RENDER).encode(), b"")))
    vs = iter(versions)
    monkeypatch.setattr(mod, "version", lambda: dict(zip(("contractVersion", "buildSha"), next(vs))))
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
