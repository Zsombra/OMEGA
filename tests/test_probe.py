"""Request builders for the two read-only column tools.

omega cannot call MCP tools (see omega/performance.py:244). These build the exact
payloads the agent hands to the connector, and nothing here opens a socket.
"""
from __future__ import annotations

import ast
import inspect

from omega.probe import FETCH_RECIPE, FIRST_CUT, contract_request, render_request
from omega.space import ColumnShape
from omega.validate import validate_column

BANNED_IMPORTS = {"requests", "httpx", "urllib", "socket", "aiohttp", "http"}


def test_module_imports_no_network_client():
    """The house rule, enforced against the import graph rather than the prose.

    Checking source text for the word 'socket' would fail on the docstring that
    promises not to open one, so parse the AST and look at real imports.
    """
    import omega.probe as probe

    tree = ast.parse(inspect.getsource(probe))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & BANNED_IMPORTS), f"probe.py must not import {imported & BANNED_IMPORTS}"


def test_first_cut_spans_the_interesting_cases():
    """An atom, a chain, a trajectory fan-out, and a rank-chain."""
    assert len(FIRST_CUT) == 4
    assert any(s.chained is None and s.transform != "trajectory" for s in FIRST_CUT)
    assert any(s.chained is not None for s in FIRST_CUT)
    assert any("trajectory" in (s.transform, s.chained) for s in FIRST_CUT)
    assert any(s.chained == "rank" for s in FIRST_CUT)


def test_every_first_cut_shape_is_legal_before_we_spend_a_call():
    for shape in FIRST_CUT:
        findings = validate_column(shape.to_column(), section_timeframe="1h")
        errors = [f for f in findings if f.level == "error"]
        assert not errors, f"{shape} -> {errors}"


def test_contract_request_is_the_wire_shape():
    shape = ColumnShape("EMA5", "spread", "trajectory", "EMA13", None)
    req = contract_request(shape, window=4)
    assert req["sectionTimeframe"] == "1h"
    col = req["column"]
    assert col["metric"] == "EMA5"
    assert col["transformId"] == "spread"
    assert col["chainedTransformId"] == "trajectory"
    assert col["window"] == 4
    assert col["inputs"] == [{"metric": "EMA13"}]
    assert None not in col.values(), "wire payload must omit unset fields, not send null"


def test_render_request_wraps_columns_in_one_custom_section():
    req = render_request(FIRST_CUT, ["BTC", "GOOGL"])
    assert req["timeframe"] == "1h"
    assert req["coinSelection"] == {"mode": "explicit", "tickers": ["BTC", "GOOGL"]}
    assert len(req["sections"]) == 1
    section = req["sections"][0]
    assert section["kind"] == "custom"
    assert section["benchmarkTicker"] is None
    assert len(section["columns"]) == 4


def test_fetch_recipe_names_both_tools_and_the_read_only_guarantee():
    assert "get_strategy_column_contract" in FETCH_RECIPE
    assert "preview_strategy_report" in FETCH_RECIPE
    assert "read-only" in FETCH_RECIPE
