"""OMEGA v0.12.1 (2026-11-10): no generated condition reads a retired ambient header.

Every v0.12.0 preset named headers the platform retired at contract 146 - `usdtUsdDev_market` / `usdcUsdtDev_market`
in `{P}_RISK_ON` and `mktBreadth_all` in the non-FADE `{P}_CTX_*` - and preview_strategy_report refused all five at
161.0.0 with CONDITION_COLUMN_UNKNOWN: "a condition may only read the strategy's own report columns" (measured
2026-11-10, battlegrid-manager docs/status/2026-11-10-contract-149-rereview.md). The refusal's allowed domain was the
report's own headers plus four session headers. The same day, a preview with a market section (MKT_NET ->
`mktBreadth`, net breadth in %) and a USDT_USD reference section (PAR_DEV -> `parDev`, deviation from par in %) was
accepted, each condition resolved to its section; two `parDev` sections were refused CONDITION_COLUMN_AMBIGUOUS.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega import preflight as P
from omega.conditions import CONTEXT_SECTIONS, ambient_headers, report_headers
from omega.generate import PRESETS, emit_plan, plan

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_161 = "data/contract/stage_strategy_draft/schema_20261109T162100Z.json"
SESSION = {"captConc_session", "fieldBiasDir_session", "fieldPlayers_session", "fieldUpBias_session"}
RETIRED = {"mktBreadth_all", "mktUp_all", "mktDown_all", "mktAvgChg_all", "usdtUsdDev_market", "usdcUsdtDev_market",
           "picksSpread_session"}


def _headers_read(conditions) -> set:
    out = set()

    def walk(node):
        if isinstance(node, dict):
            if node.get("kind") == "clause":
                out.add(node["column"]["header"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk([c["definition"] for c in conditions])
    return out


def test_the_ambient_set_is_the_four_measured_session_headers():
    assert set(ambient_headers()) == SESSION


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_every_condition_reads_a_header_the_report_renders_or_a_session_header(preset):
    p = plan(PRESETS[preset])
    read = _headers_read(p.conditions)
    rendered = set(report_headers(p.report)) - set(ambient_headers())
    assert read <= rendered | SESSION, sorted(read - rendered - SESSION)
    assert not read & RETIRED
    assert not [f for f in p.condition_findings() if f.severity == "error"]


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_the_emitted_body_names_no_retired_header_and_walks_the_161_schema_clean(tmp_path, preset):
    doc = json.loads(Path(emit_plan(plan(PRESETS[preset]), preset, out_dir=tmp_path)).read_text(encoding="utf-8"))
    body = {k: v for k, v in doc.items() if not k.startswith("_")}
    text = json.dumps(body)
    assert not [h for h in RETIRED if h in text]
    root = json.loads((ROOT / SCHEMA_161).read_text(encoding="utf-8"))["stage_strategy_draft"]["inputSchema"]
    # 2026-11-11, contract 168.3.0: the emitted body carries `tradeLevelMenu`, which the 161 capture's closed
    # TRADE_LEVEL_POLICY reads as UNDECLARED - exactly that one key. Without it the body walks 161 clean, as before.
    as_emitted = [(f.cls, f.path) for f in P.diff_schema(body, root, root)
                  if f.verdict == "FAIL" or f.cls == "UNSUPPORTED"]
    assert as_emitted == [("UNDECLARED", "axes.TRADE_LEVEL_POLICY.tradeLevelMenu")]
    before_168 = json.loads(text)
    del before_168["axes"]["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]
    assert [(f.cls, f.path) for f in P.diff_schema(before_168, root, root)
            if f.verdict == "FAIL" or f.cls == "UNSUPPORTED"] == []


def test_each_context_section_is_added_only_when_a_condition_reads_it():
    for name, thesis in PRESETS.items():
        p = plan(thesis)
        read = _headers_read(p.conditions)
        titles = {s.title for s in p.report.sections}
        for header, spec in CONTEXT_SECTIONS.items():
            assert (spec["title"] in titles) == (header in read), (name, header)
    # FADE reads the crowd (session, free); ALIGN reads the tape
    assert "Market Tape" not in {s.title for s in plan(PRESETS["mean-reversion"]).report.sections}
    assert "Market Tape" in {s.title for s in plan(PRESETS["trend-continuation"]).report.sections}


def test_a_context_header_cannot_hold_or_exit():
    """A market or reference section reads another series, not this coin's candles: no hold above 1, no exit role -
    as the session headers (omega.conditions.report_headers)."""
    p = plan(PRESETS["trend-continuation"])
    hs = report_headers(p.report)
    for h in ("mktBreadth", "parDev"):
        assert hs[h]["moved"] is False and hs[h]["candle"] is False
