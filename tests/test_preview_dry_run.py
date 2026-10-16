"""scripts/preview_dry_run.py: the v85 dry run (preview_strategy_report, FIELDS source)
that replaced the compile dry run. Builds bodies only; omega never calls the platform."""
from __future__ import annotations

import json

import pytest

from omega import preflight as P
from omega.contract import stage_schema
from omega.generate import PRESETS, plan
from scripts import preview_dry_run as D


def _fails(body: dict, tool: str) -> list:
    root = stage_schema()[tool]["inputSchema"]
    findings = P.diff_schema(body, root, root)
    return [(f.cls, f.path) for f in findings if f.verdict == "FAIL" or f.cls == "UNSUPPORTED"]


@pytest.mark.parametrize("kw", [{}, {"small": True}, {"small": True, "anchor": "4h"}])
def test_every_preview_body_walks_clean_against_the_v91_preview_schema(kw):
    assert _fails(D.preview_request(**kw), "preview_strategy_report") == []


def test_the_small_body_names_the_three_harness_tickers():
    body = D.preview_request(small=True)
    assert body["coinSelection"] == {"mode": "explicit", "tickers": D.SMALL_TICKERS}
    assert body["source"]["kind"] == "FIELDS"
    assert D.preview_request(small=True, anchor="4h")["source"]["timeframe"] == "4h"


def test_the_stage_body_is_a_create_request_and_walks_clean():
    """No strategyId: v85 "Omit strategyId to open a NEW create draft"; draftVersion 0."""
    body = D.stage_request(small=True)
    assert set(body) == {"draftVersion", "axes"} and body["draftVersion"] == 0     # v111: no `request` envelope
    assert body["axes"] == plan(PRESETS[D.PRESET]).axes()
    assert _fails(body, "stage_strategy_draft") == []


def test_live_is_refused_and_nothing_is_printed(capsys):
    with pytest.raises(SystemExit) as exc:
        D.main(["small", "--live"])
    assert "--live refused" in str(exc.value)
    assert capsys.readouterr().out == ""


def test_print_mode_emits_the_body(capsys):
    assert D.main(["small"]) == 0
    assert json.loads(capsys.readouterr().out) == D.preview_request(small=True)


def test_the_module_opens_no_sockets():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(D))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"requests", "httpx", "urllib", "aiohttp", "socket", "http", "subprocess"}


def test_record_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "ROOT", tmp_path)
    (tmp_path / "data/audit").mkdir(parents=True)
    sent, resp = tmp_path / "sent.json", tmp_path / "resp.json"
    sent.write_text(json.dumps(D.preview_request(small=True)), encoding="utf-8")
    resp.write_text(json.dumps({"ok": True}), encoding="utf-8")
    assert D.main(["record", str(sent), str(resp), "2026-10-06"]) == 0
    doc = json.loads((tmp_path / "data/audit/preview_dry_run_2026-10-06.json").read_text(encoding="utf-8"))
    assert doc["request"] == D.preview_request(small=True) and doc["responseVerbatim"] == {"ok": True}
    with pytest.raises(SystemExit):
        D.main(["record", str(sent), str(resp), "2026-10-06"])
