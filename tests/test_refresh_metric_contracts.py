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


def _tree(tmp_path: Path, roster: list[str], raw: list[str], stub_stderr: str) -> dict:
    tree = tmp_path / "repo"
    (tree / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, tree / "scripts" / SCRIPT.name)
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
    proc = subprocess.run([sys.executable, str(tree / "scripts" / SCRIPT.name)], cwd=tree, env=env,
                          capture_output=True, text=True, timeout=120)
    calls = (shim / "calls.log").read_text().count("call") if (shim / "calls.log").exists() else 0
    return {"proc": proc, "metrics": metrics, "calls": calls}


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
