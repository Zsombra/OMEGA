"""End-to-end demo: author a custom section, validate it locally, cost it, emit the payload.

Run:  python examples/build_section.py
Emits: out/mean-reversion-panel.json   (nothing is submitted to BattleGrid)
"""
from __future__ import annotations

from omega.aggregate import Signal, aggregate, minimum_score_to_route
from omega.emit import emit
from omega.fanout import cost_report, outputs_for
from omega.types import Column, CustomSection, Report
from omega.validate import validate_report

# ---------------------------------------------------------------------------
# A mean-reversion panel: how stretched, how fast, and is flow confirming?
#
# NOTE the section deliberately carries NO `timeframe` override, because
# FUNDING_RATE is timeframe-inert and would be rejected in an overridden section.
# ---------------------------------------------------------------------------
panel = CustomSection(
    title="MR Stretch Panel",
    benchmarkTicker=None,
    columns=[
        # how far price sits from the session VWAP, and how that ranks vs the universe
        Column(metric="VWAP", transformId="distance", timeframe={"rel": "anchor"}),
        Column(metric="VWAP", transformId="distance", chainedTransformId="rank",
               timeframe={"rel": "anchor"}, ordering="far"),
        # is momentum still extending, or rolling over?
        Column(metric="RSI14", transformId="trajectory", timeframe={"rel": "anchor"},
               window=4, bars="closed"),
        Column(metric="RSI14", transformId="classifyZone", timeframe={"rel": "anchor"}),
        # how straight was the move down into the stretch?  (chop vs impulse)
        Column(metric="CLOSE", transformId="efficiency", timeframe={"rel": "lower"},
               window=6, bars="closed"),
        # is positioning paying to hold the move?
        Column(metric="FUNDING_RATE", transformId="aggregate", timeframe={"rel": "anchor"},
               window=24),
        # flow confirmation
        Column(metric="BUY_PRESSURE", transformId="trajectory", timeframe={"rel": "anchor"},
               window=3, bars="closed"),
    ],
)

report = Report(anchor="1h", sections=[panel])


def main() -> None:
    print("=" * 72)
    print("VALIDATION")
    print("=" * 72)
    result = validate_report(report)
    print(result.report())
    print()

    print("=" * 72)
    print("COMPILED OUTPUT HEADERS  (what the agent actually reads)")
    print("=" * 72)
    for col in panel.columns:
        outs = outputs_for(col)
        chain = f" -> {col.chainedTransformId}" if col.chainedTransformId else ""
        print(f"{col.metric} x {col.transformId}{chain}  ({len(outs)} header(s))")
        for o in outs:
            vocab = f"  vocab={list(o.vocabulary)}" if o.vocabulary else ""
            print(f"     {o.header:<28} {o.kind:<15} ops={o.condition_operators}{vocab}")
    print()

    print("=" * 72)
    print("BUDGET")
    print("=" * 72)
    print(cost_report(report).render())
    print()

    print("=" * 72)
    print("SCORECARD WHAT-IF")
    print("=" * 72)
    signals = [
        Signal("rsi_oversold", 0.90, 3),
        Signal("bollinger_lower_touch", 0.70, 2),
        Signal("cvd_bull_divergence", 0.40, 2),
        Signal("funding_extreme_negative", 0.85, 1),
        Signal("regime_alignment", 1.00, 0),   # informational only - zero weight
    ]
    res = aggregate(signals, gate=0.65)
    print(res.render())
    print()
    for label in ("cvd_bull_divergence", "regime_alignment"):
        need = minimum_score_to_route(signals, 0.65, label)
        if need is None:
            print(f"  {label}: cannot change the outcome on its own")
        else:
            print(f"  {label}: would need score >= {need:.3f} to clear the gate alone")
    print()

    path = emit(report, "mean-reversion-panel")
    print(f"emitted -> {path}")
    print("NOT submitted. Quota untouched.")


if __name__ == "__main__":
    main()
