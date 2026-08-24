"""The explore → explain → author loop, driven from one command.

Each verb is a thin shell over an existing module: `explore` over omega.space,
`explain` over omega.explain, `author` over validate → fanout → emit. The CLI owns
argument parsing and nothing else, so these tests check wiring and refusals rather
than re-testing the layers underneath.
"""
from __future__ import annotations

import pytest

from omega.table import main, parse_spec
from omega.types import Column


# --- the spec mini-language -------------------------------------------------

def test_parse_a_bare_atom():
    col = parse_spec("RSI14", "value")
    assert isinstance(col, Column)
    assert col.metric == "RSI14" and col.transformId == "value"
    assert col.timeframe.rel == "anchor"


def test_parse_an_operand_with_colon_syntax():
    col = parse_spec("EMA5", "spread:EMA13")
    assert col.transformId == "spread"
    assert col.inputs is not None and col.inputs[0].metric == "EMA13"


def test_parse_a_chain_and_parameters():
    col = parse_spec("EMA5", "spread:EMA13", chain="trajectory", window=4, rel="lower")
    assert col.chainedTransformId == "trajectory"
    assert col.window == 4
    assert col.timeframe.rel == "lower"


def test_parse_rejects_an_unknown_metric():
    with pytest.raises(SystemExit):
        parse_spec("NOT_A_METRIC", "value")


# --- explore ----------------------------------------------------------------

def test_explore_lists_shapes_and_counts_them(capsys):
    assert main(["explore", "--family", "volumeFlow", "--max-headers", "1"]) == 0
    out = capsys.readouterr().out
    assert "shapes" in out.lower()
    assert "volumeFlow" in out or "VOLUME" in out or "OBV" in out


def test_explore_can_isolate_what_the_platform_never_uses(capsys):
    assert main(["explore", "--unused", "--limit", "5"]) == 0
    out = capsys.readouterr().out
    assert "never used by a platform template" in out.lower()


def test_explore_limit_is_honoured_and_the_truncation_is_stated(capsys):
    main(["explore", "--limit", "3"])
    out = capsys.readouterr().out
    assert "showing 3 of" in out.lower(), "a silent cap would misread as full coverage"


# --- explain ----------------------------------------------------------------

def test_explain_prints_the_math_and_the_values(capsys):
    assert main(["explain", "CCI20", "trajectory"]) == 0
    out = capsys.readouterr().out
    assert "THE MATH" in out and "EFFECTIVE" in out and "VALUES" in out
    assert "window" in out


def test_explain_on_an_uncaptured_column_says_so(capsys):
    assert main(["explain", "SMA20", "value"]) == 0
    out = capsys.readouterr().out
    assert "not captured" in out.lower()


# --- author -----------------------------------------------------------------

def test_author_refuses_an_illegal_column(capsys):
    """Raw VOLUME must not rank - the CLI must not emit it."""
    assert main(["author", "VOLUME", "rank"]) == 1
    err = capsys.readouterr().out
    assert "refus" in err.lower() or "error" in err.lower()


def test_author_reports_cost_before_emitting(capsys, tmp_path):
    assert main(["author", "CCI20", "trajectory", "--window", "4",
                 "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "5 header" in out, "trajectory at window 4 emits 4 slots plus _trend"
    assert list(tmp_path.glob("*.json")), "a payload must land on disk"


def test_author_emits_nothing_when_it_refuses(capsys, tmp_path):
    main(["author", "VOLUME", "rank", "--out", str(tmp_path)])
    assert not list(tmp_path.glob("*.json")), "a refused column must leave no file"
