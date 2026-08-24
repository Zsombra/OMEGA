"""Request builders for the two read-only column tools.

omega cannot call MCP tools (see omega/performance.py:244). These build the exact
payloads the agent hands to the connector, and nothing here opens a socket.
"""
from __future__ import annotations

import ast
import inspect

from omega.probe import (
    FETCH_RECIPE, FIRST_CUT, contract_request, effective_parameters, headers,
    load_contracts, load_renders, render_request,
)
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


# --- the captured responses -------------------------------------------------

def test_every_first_cut_shape_was_captured():
    assert len(load_contracts()) == len(FIRST_CUT)


def test_effective_parameters_are_read_not_assumed():
    """The platform fills in defaults we never sent."""
    for case in load_contracts():
        eff = effective_parameters(case)
        assert "bars" in eff and "window" in eff and "ordering" in eff


def test_trajectory_default_window_is_four_not_eight():
    """A guessed default would have been wrong; this pins the measured one."""
    case = next(c for c in load_contracts()
                if c["request"]["column"]["metric"] == "CCI20"
                and c["request"]["column"]["transformId"] == "trajectory")
    assert "window" not in case["request"]["column"], "the request must not have sent one"
    assert effective_parameters(case)["window"] == 4


def test_rank_ordering_defaults_to_hi():
    """Another non-guessable default: an unset chained-rank ordering becomes 'hi'."""
    case = next(c for c in load_contracts()
                if c["request"]["column"].get("chainedTransformId") == "rank")
    assert "ordering" not in case["request"]["column"]
    assert effective_parameters(case)["ordering"] == "hi"
    assert headers(case) == ["dist_VWAP_rank_hi"]


def test_bars_defaults_to_all_on_every_windowed_transform():
    """bars='all' includes the LIVE FORMING BAR - cookbook trap #1, on by default."""
    windowed = [c for c in load_contracts()
                if effective_parameters(c)["window"] is not None]
    assert windowed
    assert all(effective_parameters(c)["bars"] == "all" for c in windowed)


def test_fan_out_headers_are_window_plus_trend():
    case = next(c for c in load_contracts()
                if c["request"]["column"].get("chainedTransformId") == "trajectory")
    hs = headers(case)
    assert len(hs) == effective_parameters(case)["window"] + 1
    assert hs[-1].endswith("_trend")


def test_the_known_formula_defect_is_stored_verbatim():
    """One-to-one means we keep the platform's wrong text, not a repaired one."""
    case = next(c for c in load_contracts()
                if c["request"]["column"].get("chainedTransformId") == "trajectory"
                and c["request"]["column"]["transformId"] == "spread")
    formula = case["response"]["contract"]["formula"]
    assert "non-null EMA5 values" in formula, (
        "the platform names the base series where the slots hold the spread series; "
        "storing a corrected string here would break the one-to-one guarantee")


def test_headers_use_the_metric_code_not_its_key():
    """CCI20 renders as CCI_*. The header stem is the metric's `code`, not its key."""
    case = next(c for c in load_contracts()
                if c["request"]["column"]["metric"] == "CCI20")
    assert all(h.startswith("CCI_") for h in headers(case))
    assert not any(h.startswith("CCI20") for h in headers(case))


def test_omega_fanout_predicts_the_live_headers_exactly():
    """Cross-check the offline predictor against ground truth, header for header."""
    from omega.fanout import outputs_for
    from omega.types import Column

    for case in load_contracts():
        normalized = case["response"]["contract"]["normalizedColumn"]
        predicted = [o.header for o in outputs_for(Column(**normalized))]
        assert predicted == headers(case), (
            f"{normalized['metric']} x {normalized['transformId']}: "
            f"predicted {predicted}, live {headers(case)}")


def test_renders_carry_real_values():
    """The repo's first numbers produced by a custom column."""
    payload = load_renders()
    text = payload["response"]["renderedSections"][0]["section"]["text"]
    assert "| BTC |" in text and "| GOOGL |" in text
    assert "64.9" in text, "BTC RSI14 as rendered"
    assert "14/78" in text, "rank renders as ordinal/universe-size, not a bare integer"


def test_bars_all_makes_now_duplicate_the_last_closed_slot():
    """Trap #1, visible in real data: the forming bar means now == t1 until it closes."""
    payload = load_renders()
    text = payload["response"]["renderedSections"][0]["section"]["text"]
    rows = [r for r in text.splitlines() if r.startswith("| BTC |")]
    assert len(rows) == 1
    cells = [c.strip() for c in rows[0].strip("|").split("|")]
    header_row = next(r for r in text.splitlines() if r.startswith("| coin |"))
    names = [c.strip() for c in header_row.strip("|").split("|")]
    by_name = dict(zip(names, cells))
    assert by_name["CCI_t1"] == by_name["CCI_now"], (
        "with bars='all' the forming bar occupies `now`, so it repeats the last "
        "closed observation until that bar closes")
