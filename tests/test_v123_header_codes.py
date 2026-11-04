"""Contract v123: a metric's code states its indicator's length (2026-10-20).

README v123, "Rejected input": "A condition column or a `{…}` Market Read marker naming a retired header is refused.
A metric's code now ends with its indicator's single length". Eighteen codes moved; data/contract/metrics/_moves_123.json
records them verbatim. Until v0.8.3 three of OMEGA's condition clauses typed a retired header by hand (`ADX_now`,
`pctB_now`, `ATR_trend`), so 3 of the 5 presets would have been refused at stage while OMEGA's own check passed.
"""
from __future__ import annotations

import ast
import inspect
import json
from dataclasses import replace
from pathlib import Path

import pytest

import omega.contract as contract_mod
import omega.generate as generate_mod
from omega.authoring import vocabulary
from omega.contract import header_code_moves, header_since_123, load
from omega.fanout import outputs_for
from omega.generate import MODULE_CLAUSES, MODULE_RECIPES, PRESETS, plan, recipe_header

ROOT = Path(__file__).resolve().parents[1]

# The README v123 table, typed a second time on purpose: the data file and this pin must agree.
README_V123 = {
    "CCI": "CCI20", "ADX": "ADX14", "ATR": "ATR14", "BBwidth": "BBwidth20", "pctB": "pctB20",
    "donchianHi": "donchianHi20", "donchianLo": "donchianLo20",
    "donchianHiPrior": "donchianHiPrior20", "donchianLoPrior": "donchianLoPrior20",
    "donchianBrkHi": "donchianBrkHi20", "donchianBrkLo": "donchianBrkLo20",
    "bbUpper": "bbUpper20", "bbLower": "bbLower20", "willR": "willR14", "stochRSI": "stochRSI14",
    "DIplus": "DIplus14", "DIminus": "DIminus14", "RVOL": "RVOL20",
}
RETIRED = set(README_V123)


def _tokens(header: str) -> set[str]:
    return set(header.split("_"))


def test_the_moves_file_is_the_readme_table():
    moves = header_code_moves()
    assert len(moves) == 18
    assert {m["before"]: m["since"] for m in moves.values()} == README_V123
    raw = json.loads((ROOT / "data/contract/metrics/_moves_123.json").read_text(encoding="utf-8"))
    assert "A metric's code now ends with its indicator's single length" in raw["quote"]


def test_the_corpus_carries_every_new_code_and_no_retired_one():
    c = load()
    for key, move in header_code_moves().items():
        if key in c.retired_metrics:        # STOCH_RSI14 (v137) and BB_WIDTH (v138) left the roster after v123
            continue
        assert c.metric(key).code == move["since"], key
    assert not {m.code for m in c.metrics.values()} & RETIRED


def test_a_half_applied_rename_cannot_load(monkeypatch):
    """The loader fails closed: a corpus whose code disagrees with the changelog would predict refused headers."""
    monkeypatch.setattr(contract_mod, "header_code_moves", lambda: {"ADX": {"before": "ADX14", "since": "ADX99"}})
    with pytest.raises(RuntimeError, match="v123 header codes not applied"):
        load.__wrapped__()


@pytest.mark.parametrize("old,new", [
    ("ADX_now", "ADX14_now"), ("ADX_state", "ADX14_state"), ("dist_donchianLo", "dist_donchianLo20"),
    ("RVOL_rank_hi", "RVOL20_rank_hi"), ("bbUpper_4h_lvl_b25", "bbUpper20_4h_lvl_b25"),
    ("donchianHiPrior_lvl", "donchianHiPrior20_lvl"), ("buyPres_pctB_spread", "buyPres_pctB20_spread"),
    ("DIplus_DIminus_spread", "DIplus14_DIminus14_spread"), ("RSI14_now", "RSI14_now"), ("ADX14_now", "ADX14_now"),
])
def test_an_old_header_is_rewritten_token_by_token(old, new):
    """README v123: "Every suffix and prefix is kept (`ADX14_state`, `dist_donchianLo20`, `RVOL20_rank_hi`)"."""
    assert header_since_123(old) == new


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_every_preset_emits_only_new_style_codes(name):
    p = plan(PRESETS[name])
    report_headers = [o.header for s in p.report.sections if getattr(s, "columns", None)
                      for col in s.columns for o in outputs_for(col)]
    clause_headers = []

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("column"), dict) and "header" in x["column"]:
                clause_headers.append(x["column"]["header"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(p.axes())
    assert clause_headers, "every preset gates on clauses"
    for h in report_headers + clause_headers:
        assert not _tokens(h) & RETIRED, f"{name}: {h} names a header retired at v123"
    assert not _tokens(p.market_read_text.replace(" ", "_")) & RETIRED
    assert not [f for f in p.condition_findings() if f.severity == "error"]


def test_the_three_clauses_that_were_typed_by_hand_now_read_the_v123_headers():
    assert MODULE_CLAUSES["TREND_STRENGTH"]["filter"]()["column"]["header"] == "ADX14_now"
    assert {MODULE_CLAUSES["BOLLINGER"][k]()["column"]["header"] for k in MODULE_CLAUSES["BOLLINGER"]} == {"pctB20_now"}
    assert MODULE_CLAUSES["VOLATILITY"]["filter"]()["column"]["header"] == "ATR14_trend"


def test_the_assistant_menu_names_no_retired_header():
    """omega.authoring.vocabulary() is what the strategist model reads (battlegrid-manager turn.py `_menu`)."""
    text = json.dumps(vocabulary()["modules"])
    for module in vocabulary()["modules"].values():
        for reading in module["readings"].values():
            assert not _tokens(reading.split(" ")[0]) & RETIRED, reading
    assert "ADX14_now" in text and "pctB20_now" in text and "ATR14_trend" in text


# --- the clause header is derived from the column builder -----------------------------------------------------

def test_no_clause_header_is_a_string_literal():
    """Every num/is_/in_ inside MODULE_CLAUSES takes its header from recipe_header, never a typed string."""
    tree = ast.parse(inspect.getsource(generate_mod))
    clauses = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", None) == "MODULE_CLAUSES")
    calls = [n for n in ast.walk(clauses.value)
             if isinstance(n, ast.Call) and getattr(n.func, "id", None) in ("num", "is_", "in_")]
    assert len(calls) >= 40
    literal = [ast.unparse(c) for c in calls if isinstance(c.args[0], ast.Constant)]
    assert literal == []


def test_every_clause_header_is_one_its_module_recipe_emits():
    for module, spec in MODULE_CLAUSES.items():
        emitted = {o.header for col in MODULE_RECIPES[module]
                   for o in outputs_for(generate_mod.Column(**col))}
        for reading, factory in spec.items():
            assert factory()["column"]["header"] in emitted, (module, reading)


def test_a_renamed_code_moves_the_clause_header_with_it():
    """The next rename cannot strand a clause: change the code and the derived header follows."""
    c = load()
    fake = replace(c, metrics=c.metrics | {"ADX": replace(c.metric("ADX"), code="ADX99")})
    assert recipe_header("TREND_STRENGTH", "now", contract=fake, metric="ADX") == "ADX99_now"
    assert recipe_header("TREND_STRENGTH", "now", metric="ADX") == "ADX14_now"


def test_an_ambiguous_or_missing_recipe_header_raises():
    with pytest.raises(LookupError):
        recipe_header("PRICE_STRUCTURE", metric="STRUCT_ZONES")             # three columns answer
    with pytest.raises(LookupError):
        recipe_header("TREND_STRENGTH", "zone", metric="ADX")               # the recipe has no zone column
