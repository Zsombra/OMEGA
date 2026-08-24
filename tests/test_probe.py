"""Request builders for the two read-only column tools.

omega cannot call MCP tools (see omega/performance.py:244). These build the exact
payloads the agent hands to the connector, and nothing here opens a socket.
"""
from __future__ import annotations

import ast
import inspect

from omega.probe import (
    FETCH_RECIPE, FIRST_CUT, contract_request, effective_parameters, headers,
    load_all_renders, load_contracts, load_renders, render_request,
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
        errors = [f for f in findings if f.severity == "error"]
        assert not errors, f"{shape} -> {errors}"


def test_the_legality_guard_actually_bites():
    """Guard the guard.

    The check above reads `.severity`; an earlier version read `.level`, which does
    not exist on Finding. It passed anyway, because every FIRST_CUT shape returns an
    empty finding list and the comprehension never touched the attribute. A typo in
    the field name would have surfaced as AttributeError on the first real finding
    rather than as a clean failure - so pin an illegal shape here to prove the
    attribute is read on a non-empty list.
    """
    illegal = ColumnShape("VOLUME", "rank").to_column()
    findings = validate_column(illegal, section_timeframe="1h")
    errors = [f for f in findings if f.severity == "error"]
    assert errors, "raw VOLUME must not rank - use RVOL, which is already a ratio"


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


# --- full transform coverage, and the bug it found --------------------------

def test_all_sixteen_transforms_are_exercised_on_live_data():
    """Every transform has now produced a real header from the live compiler."""
    from omega.contract import load
    covered = set()
    for case in load_contracts():
        col = case["request"]["column"]
        covered.add(col["transformId"])
        if col.get("chainedTransformId"):
            covered.add(col["chainedTransformId"])
    for payload in load_all_renders():
        for col in payload["request"]["sections"][0]["columns"]:
            covered.add(col["transformId"])
            if col.get("chainedTransformId"):
                covered.add(col["chainedTransformId"])
    missing = set(load().transform_ids()) - covered
    assert not missing, f"never exercised live: {sorted(missing)}"


def test_fanout_predicts_every_rendered_header_exactly():
    """The predictor against live truth, for every column in every render.

    This is what caught the two nearestZone* bugs: the header carries an `_h`
    unit suffix for age, and side='resistance' is abbreviated to `resist`.
    """
    from omega.fanout import outputs_for
    from omega.types import Column

    for payload in load_all_renders():
        section = payload["request"]["sections"][0]
        predicted = []
        for spec in section["columns"]:
            predicted += [o.header for o in outputs_for(Column(**spec))]

        custom = [cc for cc in payload["response"]["conditionColumns"]
                  if cc["sectionKey"].startswith("custom:")]
        if not custom:
            # The collision capture, and only that one: a duplicate header makes the
            # platform drop the whole section from conditionColumns. Assert that is
            # what we are looking at rather than skipping quietly.
            assert len(predicted) != len(set(predicted)), (
                "a custom section vanished from conditionColumns with no header "
                f"collision to explain it: {payload['capturedAt']}")
            continue

        live = [o["header"] for o in custom[0]["outputs"]]
        assert predicted == live, f"predicted {predicted}\nlive      {live}"


def test_zone_side_resistance_abbreviates_to_resist():
    """side='resistance' renders as `resist`; 'support' stays whole. Asymmetric."""
    from omega.fanout import outputs_for
    from omega.space import ColumnShape

    col = ColumnShape("STRUCT_ZONES", "nearestZoneType").to_column()
    assert [o.header for o in outputs_for(col.model_copy(update={"side": "resistance"}))] \
        == ["zones_resist_type"]
    assert [o.header for o in outputs_for(col.model_copy(update={"side": "support"}))] \
        == ["zones_support_type"]


def test_zone_age_carries_its_hours_unit_in_the_header():
    from omega.fanout import outputs_for
    from omega.space import ColumnShape

    col = ColumnShape("STRUCT_ZONES", "nearestZoneAge").to_column()
    assert [o.header for o in outputs_for(col.model_copy(update={"side": "support"}))] \
        == ["zones_support_age_h"]


# --- the timeframe infix, pinned per transform ------------------------------

def test_every_transform_places_the_timeframe_infix():
    """Four branches silently dropped it until live renders at rel=lower said no.

    Verified against _renders_tfvariants.json and _renders_infix.json. `value` and
    `distance` carry the marker as a trailing SUFFIX; every other transform takes it
    as an INFIX between the code and the suffix.
    """
    from omega.fanout import outputs_for
    from omega.types import Column, Operand, RelTimeframe

    def header(**kw):
        return outputs_for(Column(timeframe=RelTimeframe(rel=kw.pop("rel")), **kw))[0].header

    # suffix-carrying
    assert header(metric="RSI14", transformId="value", rel="lower") == "RSI14_ltf"
    assert header(metric="RSI14", transformId="value", rel="regime") == "RSI14_htf"
    assert header(metric="VWAP", transformId="distance", rel="lower") == "dist_VWAP_ltf"
    assert header(metric="VWAP", transformId="distance", rel="anchor") == "dist_VWAP"

    # infix-carrying - these four were the bugs
    assert header(metric="CLOSE", transformId="bandTouch", rel="lower") == "close_ltf_touch"
    assert header(metric="ADX", transformId="classifyZone", rel="lower") == "ADX_ltf_zone"
    assert header(metric="MACD", transformId="crossDetect", rel="lower") == "MACD_ltf_cross"
    assert header(metric="ADX", transformId="rank", rel="lower") == "ADX_ltf_rank_hi"

    # and unchanged at anchor
    assert header(metric="CLOSE", transformId="bandTouch", rel="anchor") == "close_touch"
    assert header(metric="ADX", transformId="classifyZone", rel="anchor") == "ADX_zone"
    assert header(metric="MACD", transformId="crossDetect", rel="anchor") == "MACD_cross"
    assert header(metric="ADX", transformId="rank", rel="anchor") == "ADX_rank_hi"


def test_rank_denominator_is_the_universe_not_the_report():
    """A platform prose defect, caught by its own numbers.

    The section text for a non-anchor rank claims the ordinal is 'across THIS
    REPORT'S coins ... rank/report-size'. That render previewed ONE coin and the
    values came back 32/78 and 12/78, so the denominator is the tracked universe.
    The conditionColumns `meaning` and the trailing rankScopingNote both say
    universe; the section prose is the outlier. Stored verbatim, recorded here.
    """
    payload = load_renders("_renders_infix.json")
    text = payload["response"]["renderedSections"][0]["section"]["text"]
    assert "rank/report-size" in text, "the misleading prose, kept verbatim"
    assert len(payload["request"]["coinSelection"]["tickers"]) == 1
    row = next(r for r in text.splitlines() if r.startswith("| BTC |"))
    assert "32/78" in row and "12/78" in row, "denominator is 78, not the 1-coin report"
    note = payload["response"]["rankScopingNote"]
    assert "not the previewed coin selection" in note
