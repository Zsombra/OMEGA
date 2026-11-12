"""scripts/refresh_metric_contracts.py writes nothing under data/ unless every raw hint was read.

The first version rewrote each metric file as it read it and wrote data/contract/metrics/_index.json with
metricCount = the records of THIS run before it checked for failures. A partial run (2026-11-05 at 148.1.0: 170 of
532 read, then the mcporter OAuth credential was lost) therefore left _index.json at 170 beside 326 metric files and
omega.contract.load() raised "corpus incomplete" for the suite and every consumer. Each test runs a copy of the script
in a throwaway tree with a stub `npx` first on PATH: no platform call is made.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "refresh_metric_contracts.py"
OAUTH = "If the browser did not open, visit https://mcp.battlegrid.trade/authorize?response_type=code to continue."

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the script shells out through `cmd /c npx`")


def _hint(name: str) -> dict:
    return {"metric": {"metric": name, "label": name, "code": name.lower(), "family": "structure",
                       "nativeOutput": {"kind": "numeric", "unit": "price"}, "timeframeMode": "series",
                       "transforms": [{"id": "value", "label": "Value", "authoring": {"parameters": {}}}]}}


# A stand-in for scripts/mcporter_runtime.mjs (EXTRACTION_TRANSPORT=runtime): the same line protocol, answers from a
# table {metric: {ok, value | error}}, and a log of its starts and calls. `{"__ready": false}` makes it refuse to start.
STUB_RUNTIME = """\
import { appendFileSync, readFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
const table = JSON.parse(readFileSync(process.env.STUB_TABLE, 'utf8'));
const say = (o) => process.stdout.write(JSON.stringify(o) + '\\n');
appendFileSync(process.env.STUB_LOG, 'start\\n');
if (table.__ready === false) { say({ ready: false, error: 'no server named battlegrid-anbu' }); process.exit(2); }
say({ ready: true, server: 'stub' });
for await (const line of createInterface({ input: process.stdin })) {
  const req = JSON.parse(line);
  appendFileSync(process.env.STUB_LOG, 'call ' + req.tool + ' ' + req.args.metric + '\\n');
  say({ id: req.id, ...table[req.args.metric] });
}
"""
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="the runtime transport starts `node`")


def _tree(tmp_path: Path, roster: list[str], raw: list[str], stub_stderr: str, runtime: dict | None = None,
          transport: str | None = None) -> dict:
    tree = tmp_path / "repo"
    (tree / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, tree / "scripts" / SCRIPT.name)
    if runtime is not None:
        (tree / "scripts" / "mcporter_runtime.mjs").write_text(STUB_RUNTIME, encoding="utf-8")
        (tmp_path / "table.json").write_text(json.dumps(runtime), encoding="utf-8")
    metrics = tree / "data" / "contract" / "metrics"
    metrics.mkdir(parents=True)
    (tree / "data" / "contract" / "transforms").mkdir()
    (tree / "data" / "contract" / "transforms" / "_authoring.json").write_text('{"transforms": {}}', encoding="utf-8")
    # the stored corpus before the run: two metric files and their index
    for name in ("A", "B"):
        (metrics / f"{name}.json").write_text(json.dumps({"metric": name, "stored": True}), encoding="utf-8")
    (metrics / "_index.json").write_text(json.dumps({"metricCount": 2, "byFamily": {"f": ["A", "B"]}}),
                                         encoding="utf-8")
    scratch = tmp_path / "scratch"
    hints = scratch / "hints_29990101"
    hints.mkdir(parents=True)
    (scratch / "vocab_live_flat.json").write_text(json.dumps(roster), encoding="utf-8")
    for name in raw:
        (hints / f"{name}.json").write_text(json.dumps(_hint(name)), encoding="utf-8")
    # 2026-11-08 (review pass 2, finding 9): the raw dir names the contract its hints were read at, and GET
    # /mcp/version is a local file - never the network
    served = {"contractVersion": "149.1.0", "buildSha": "aa4ab640"}
    (hints / "_version.json").write_text(json.dumps({**served, "readAt": "2999-01-01T00:00:00Z"}), encoding="utf-8")
    (tmp_path / "served_version.json").write_text(json.dumps(served), encoding="utf-8")
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "npx.cmd").write_text(
        "@echo off\r\n"
        f'echo call>>"{shim / "calls.log"}"\r\n'
        f"echo {stub_stderr.replace('&', '^&')} 1>&2\r\n"
        "exit /b 1\r\n", encoding="utf-8")
    env = {**os.environ, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}", "EXTRACTION_STAMP": "29990101",
           "EXTRACTION_SCRATCH": str(scratch), "EXTRACTION_ARCHIVE": "29990100",
           "EXTRACTION_VERSION_URL": (tmp_path / "served_version.json").as_uri()}
    env.pop("EXTRACTION_CONTRACT", None)
    env.pop("EXTRACTION_TRANSPORT", None)
    if runtime is not None:
        env |= {"EXTRACTION_TRANSPORT": "runtime", "EXTRACTION_MIN_INTERVAL_S": "0.01",
                "STUB_TABLE": str(tmp_path / "table.json"), "STUB_LOG": str(tmp_path / "runtime.log")}
    if transport is not None:
        env["EXTRACTION_TRANSPORT"] = transport
    proc = subprocess.run([sys.executable, str(tree / "scripts" / SCRIPT.name)], cwd=tree, env=env,
                          capture_output=True, text=True, timeout=120)
    calls = (shim / "calls.log").read_text().count("call") if (shim / "calls.log").exists() else 0
    log = (tmp_path / "runtime.log").read_text().splitlines() if (tmp_path / "runtime.log").exists() else []
    return {"proc": proc, "metrics": metrics, "calls": calls, "hints": hints,
            "runtime_starts": log.count("start"), "runtime_calls": [ln for ln in log if ln.startswith("call ")]}


def _corpus(metrics: Path) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(metrics.glob("*.json"))}


def test_a_lost_credential_writes_nothing_and_stops_the_fetch(tmp_path):
    run = _tree(tmp_path, roster=["A", "B", "C", "D"], raw=["A", "B"], stub_stderr=OAUTH)
    assert run["proc"].returncode == 1, run["proc"].stdout + run["proc"].stderr
    assert run["calls"] == 1, "an OAuth prompt stops the fetch: no second authorization is started"
    assert json.loads((run["metrics"] / "_index.json").read_text(encoding="utf-8"))["metricCount"] == 2
    assert json.loads((run["metrics"] / "A.json").read_text(encoding="utf-8")) == {"metric": "A", "stored": True}
    assert "Nothing under data/ was written" in run["proc"].stdout


def test_one_failed_call_in_a_full_run_writes_nothing(tmp_path):
    run = _tree(tmp_path, roster=["A", "B", "C"], raw=["A", "B"], stub_stderr="TIMEOUT")
    assert run["proc"].returncode == 1
    assert run["calls"] == 1
    assert _corpus(run["metrics"]) == {
        "A.json": json.dumps({"metric": "A", "stored": True}), "B.json": json.dumps({"metric": "B", "stored": True}),
        "_index.json": json.dumps({"metricCount": 2, "byFamily": {"f": ["A", "B"]}})}


def test_a_complete_run_still_writes_the_corpus_and_its_index(tmp_path):
    run = _tree(tmp_path, roster=["A", "B", "C"], raw=["A", "B", "C"], stub_stderr=OAUTH)
    assert run["proc"].returncode == 0, run["proc"].stdout + run["proc"].stderr
    assert run["calls"] == 0
    index = json.loads((run["metrics"] / "_index.json").read_text(encoding="utf-8"))
    assert index["metricCount"] == 3 == len([p for p in run["metrics"].glob("*.json") if not p.name.startswith("_")])
    assert json.loads((run["metrics"] / "A.json").read_text(encoding="utf-8"))["code"] == "a"


# --- EXTRACTION_TRANSPORT=runtime (2026-11-11): one long-lived mcporter runtime instead of a process per call -------

@needs_node
def test_the_runtime_transport_reads_every_missing_hint_through_one_process(tmp_path):
    table = {"B": {"ok": True, "value": _hint("B")}, "C": {"ok": True, "value": _hint("C")}}
    run = _tree(tmp_path, roster=["A", "B", "C"], raw=["A"], stub_stderr=OAUTH, runtime=table)
    assert run["proc"].returncode == 0, run["proc"].stdout + run["proc"].stderr
    assert run["runtime_starts"] == 1, "one helper, one session: not a process per call"
    assert run["runtime_calls"] == ["call get_metric_construction_hints B", "call get_metric_construction_hints C"]
    assert run["calls"] == 0, "the CLI is never started on the runtime transport"
    assert json.loads((run["hints"] / "B.json").read_text(encoding="utf-8")) == _hint("B")
    assert json.loads((run["metrics"] / "_index.json").read_text(encoding="utf-8"))["metricCount"] == 3


@needs_node
def test_a_runtime_answer_that_is_an_error_is_a_failed_read_and_an_auth_error_stops_the_fetch(tmp_path):
    table = {"B": {"ok": False, "error": "Unauthorized: the cached token was refused"},
             "C": {"ok": True, "value": _hint("C")}}
    run = _tree(tmp_path, roster=["A", "B", "C"], raw=["A"], stub_stderr=OAUTH, runtime=table)
    assert run["proc"].returncode == 1
    assert run["runtime_calls"] == ["call get_metric_construction_hints B"], "no call after a refused credential"
    assert not (run["hints"] / "B.json").exists() and not (run["hints"] / "C.json").exists()
    assert json.loads((run["metrics"] / "_index.json").read_text(encoding="utf-8"))["metricCount"] == 2
    assert "Nothing under data/ was written" in run["proc"].stdout


@needs_node
def test_a_platform_error_body_from_the_runtime_is_never_cached(tmp_path):
    table = {"B": {"ok": True, "value": {"code": "INTERNAL_ERROR", "message": "try again"}},
             "C": {"ok": True, "value": _hint("C")}}
    run = _tree(tmp_path, roster=["A", "B", "C"], raw=["A"], stub_stderr=OAUTH, runtime=table)
    assert run["proc"].returncode == 1
    assert len(run["runtime_calls"]) == 2, "one bad answer does not stop the fetch: C is still read and cached"
    assert not (run["hints"] / "B.json").exists() and (run["hints"] / "C.json").exists()
    assert "INTERNAL_ERROR" in run["proc"].stdout
    assert json.loads((run["metrics"] / "_index.json").read_text(encoding="utf-8"))["metricCount"] == 2


@needs_node
def test_a_runtime_that_does_not_start_is_a_failed_read(tmp_path):
    run = _tree(tmp_path, roster=["A", "B"], raw=["A"], stub_stderr=OAUTH, runtime={"__ready": False})
    assert run["proc"].returncode == 1
    assert "did not start" in run["proc"].stdout and "no server named battlegrid-anbu" in run["proc"].stdout
    assert run["runtime_calls"] == [] and not (run["hints"] / "B.json").exists()


def test_an_unknown_transport_stops_the_run_before_any_call(tmp_path):
    run = _tree(tmp_path, roster=["A", "B"], raw=["A"], stub_stderr=OAUTH, transport="daemon")
    assert run["proc"].returncode != 0 and "EXTRACTION_TRANSPORT is 'daemon'" in run["proc"].stderr
    assert run["calls"] == 0 and run["runtime_starts"] == 0


# --- 168 (2026-11-11): operand lists are served once per response and named by id -------------------------------

def _hint_168(name: str, *, sets: dict | None = None) -> dict:
    """A 168-shaped hint: `spreadOperands` and a chained outer's `operands` name an operand set by id."""
    hint = _hint(name)
    metric = hint["metric"]
    metric.update(spreadOperands="operands-1", spreadOperandsOffAnchor="operands-2",
                  spreadAverageOperands="operands-1", spreadAverageOperandsOffAnchor=None)
    metric["transforms"].append({
        "id": "spread", "label": "Spread", "authoring": {"parameters": {}}, "chainSuccessors": ["rank"],
        "chainedOuters": {"rank": {"windowMaximum": None, "operands": "operands-2", "operandsOffAnchor": "operands-2",
                                   "offsetMinimum": None, "metricParametersAccepted": False}}})
    hint["operandSets"] = {"operands-1": ["CLOSE", "OPEN"], "operands-2": ["CLOSE"]} if sets is None else sets
    return hint


@needs_node
def test_a_168_hint_is_stored_with_its_operand_lists_not_their_ids(tmp_path):
    table = {"B": {"ok": True, "value": _hint_168("B")}}
    run = _tree(tmp_path, roster=["A", "B"], raw=["A"], stub_stderr=OAUTH, runtime=table)
    assert run["proc"].returncode == 0, run["proc"].stdout + run["proc"].stderr
    record = json.loads((run["metrics"] / "B.json").read_text(encoding="utf-8"))
    assert record["spreadOperands"] == ["CLOSE", "OPEN"] and record["spreadOperandsOffAnchor"] == ["CLOSE"]
    assert record["spreadAverageOperands"] == ["CLOSE", "OPEN"]
    assert "spreadAverageOperandsOffAnchor" not in record          # served null: not recorded, as before
    outer = next(t for t in record["transforms"] if t["id"] == "spread")["chainedOuters"]["rank"]
    assert outer["operands"] == ["CLOSE"] and outer["operandsOffAnchor"] == ["CLOSE"]
    assert outer["offsetMinimum"] is None and outer["metricParametersAccepted"] is False          # recorded as served
    # the raw hint on disk is the served answer, ids and all
    assert json.loads((run["hints"] / "B.json").read_text(encoding="utf-8"))["metric"]["spreadOperands"] == "operands-1"


@needs_node
def test_an_operand_set_the_response_does_not_define_stops_the_build_with_nothing_written(tmp_path):
    table = {"B": {"ok": True, "value": _hint_168("B", sets={"operands-1": ["CLOSE"]})}}          # operands-2 missing
    run = _tree(tmp_path, roster=["A", "B"], raw=["A"], stub_stderr=OAUTH, runtime=table)
    assert run["proc"].returncode != 0
    assert "operands-2" in run["proc"].stderr + run["proc"].stdout
    assert "nothing under data/ was written" in run["proc"].stderr + run["proc"].stdout
    assert json.loads((run["metrics"] / "_index.json").read_text(encoding="utf-8"))["metricCount"] == 2
    # the stored record of B (the tree's corpus before the run) is untouched
    assert json.loads((run["metrics"] / "B.json").read_text(encoding="utf-8")) == {"metric": "B", "stored": True}
