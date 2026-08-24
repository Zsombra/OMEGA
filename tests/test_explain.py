"""Explaining one column, from three stored sources and nothing else.

`explain` computes NOTHING. Every formula, effective parameter and value it prints
came from BattleGrid verbatim. Where a piece was never captured it says so, because
the alternative - filling the gap - is indistinguishable from a measurement once it
is rendered as text.
"""
from __future__ import annotations

import inspect

from omega.explain import Explanation, explain, render_text
from omega.space import ColumnShape
from omega.types import Column, Operand, RelTimeframe


def _col(metric, transform, **kw):
    return Column(metric=metric, transformId=transform,
                  timeframe=RelTimeframe(rel=kw.pop("rel", "anchor")), **kw)


# --- the honesty rule -------------------------------------------------------

def test_explain_computes_nothing():
    """No arithmetic on market values may appear in this module."""
    import omega.explain as mod
    src = inspect.getsource(mod)
    for banned in ("sum(", "mean", "/ len(", "* 100", "round("):
        assert banned not in src, f"explain.py must not compute: found {banned!r}"


def test_a_column_never_captured_reports_the_absence():
    """The most important case: say so, do not invent.

    SMA20 is deliberately a metric no capture has touched. An earlier version used
    RVOL, which turned out to HAVE been rendered - the test was wrong, not the code.
    """
    e = explain(_col("SMA20", "value"))
    assert e.formula is not None, "the transform formula is always known"
    assert e.effective_parameters is None
    assert e.headers is None
    assert e.values == {}
    text = render_text(e)
    assert "not captured" in text.lower()
    assert "run the calls in omega.probe.FETCH_RECIPE" in text


def test_the_transform_formula_comes_from_the_stored_authoring_contract():
    e = explain(_col("EMA5", "spread", inputs=[Operand(metric="EMA13")]))
    assert e.formula == "output = (base - inputs[0]) / inputs[0] × 100"
    assert e.operand_order == ["base", "inputs[0]"]
    assert "null" in e.null_behavior.lower()


def test_a_chained_column_carries_both_stages():
    e = explain(_col("EMA5", "spread", chainedTransformId="trajectory",
                     inputs=[Operand(metric="EMA13")]))
    assert e.chained_formula is not None
    assert e.chained_formula != e.formula
    text = render_text(e)
    assert "stage 1" in text.lower() and "stage 2" in text.lower()


# --- what the captures supply ----------------------------------------------

def test_a_captured_column_reports_effective_parameters_not_requested_ones():
    """CCI20 x trajectory was requested with no window; the platform applied 4."""
    e = explain(_col("CCI20", "trajectory"))
    assert e.effective_parameters is not None
    assert e.effective_parameters["window"] == 4
    assert e.effective_parameters["bars"] == "all"
    text = render_text(e)
    assert "effective" in text.lower()


def test_a_captured_column_reports_its_real_headers():
    e = explain(_col("CCI20", "trajectory"))
    assert e.headers == ["CCI_t3", "CCI_t2", "CCI_t1", "CCI_now", "CCI_trend"]


def test_rendered_values_are_attached_where_a_render_exists():
    e = explain(_col("RSI14", "value"))
    assert e.values, "RSI14 x value was rendered against BTC and GOOGL"
    assert "BTC" in e.values
    text = render_text(e)
    assert "BTC" in text


def test_the_platforms_known_defect_is_shown_with_its_correction():
    """One-to-one: print the wrong text AND the annotation, never one alone."""
    e = explain(_col("EMA5", "spread", chainedTransformId="trajectory",
                     inputs=[Operand(metric="EMA13")]))
    text = render_text(e)
    assert "non-null EMA5 values" in text, "the platform's own wording, verbatim"
    assert e.defect_note is not None
    assert "spread" in e.defect_note.lower()
    assert "KNOWN DEFECT" in text


def test_explanation_accepts_a_column_shape_too():
    a = explain(ColumnShape("CCI20", "trajectory"))
    b = explain(_col("CCI20", "trajectory"))
    assert isinstance(a, Explanation)
    assert a.headers == b.headers


def test_render_text_is_plain_and_names_its_sources():
    e = explain(_col("CCI20", "trajectory"))
    text = render_text(e)
    assert "CCI20" in text and "trajectory" in text
    assert "data/contract" in text, "a reader must be able to check the source"
