"""OMEGA read-only authoring probe of what contract 168 added and OMEGA v0.13.0 left unmeasured (2026-11-12).

168 is undocumented past v156; the served schema and the raw hints are the source of every value below. Groups:

- V  `spread` as a chain outer after the four averages (aggregate / ema / rma / wma): the inner keeps `window` (its
     served maximum: 2436 aggregate and wma, 704 ema, 308 rma), the outer takes `inputs` (one operand, from the inner's
     `chainedOuters.spread.operands`, `operandsOffAnchor` off the anchor rung) and `bars`;
- W  a spread operand under an average, `inputs[]` = {metric, transformId, window}: transformId one of aggregate /
     ema / rma / wma, window at least 2, the metric the base itself or one of its operands with a per-bar candle value
     (`spreadAverageOperands`, `spreadAverageOperandsOffAnchor`); the bounds, the header, and it beside a chain outer.

The `SEQUENCE` condition group is scripts/probe_sequence_168.py (it needs conditions in the preview).

Read-only: preview_strategy_report over mcporter (battlegrid-anbu), the machinery and rules of probe_authoring_148
(main(extra_groups)). Writes data/audit/authoring_probe_<MAJOR>_<PROBE_DATE>.json and
data/contract/columns/_probe_<MAJOR>_<PROBE_DATE>.json.

    EXTRACTION_TRANSPORT=runtime MCPORTER_DIST=<...> PROBE_CONTRACT=169.4.0 PROBE_DATE=2026-11-12 \
        PROBE_HINTS=<hints dir> python -m scripts.probe_authoring_168
"""
from __future__ import annotations

import sys

from scripts import probe_authoring_148 as P
from scripts.probe_authoring_148 import C, hint

AVERAGES = ("aggregate", "ema", "rma", "wma")


def transform(metric, tid):
    return next((t for t in hint(metric)["transforms"] if t["id"] == tid), None)


def outer(metric, inner, out):
    return ((transform(metric, inner) or {}).get("chainedOuters") or {}).get(out) or {}


def avg(metric, tid, window):
    return {"metric": metric, "transformId": tid, "window": window}


def groups(batch, one, probe):
    print("V. spread as a chain outer after an average")
    batch("V.accept", [C("CLOSE", "ema", window=20, chainedTransformId="spread", inputs=[{"metric": "EMA50"}]),
                       C("CLOSE", "aggregate", window=20, chainedTransformId="spread", inputs=[{"metric": "CLOSE"}]),
                       C("CLOSE", "wma", window=10, chainedTransformId="spread", inputs=[{"metric": "SMA50"}]),
                       C("CLOSE", "rma", window=14, chainedTransformId="spread", inputs=[{"metric": "EMA20"}]),
                       C("RSI14", "aggregate", window=14, chainedTransformId="spread", inputs=[{"metric": "RSI7"}]),
                       C("QUOTE_VOL", "aggregate", window=20, chainedTransformId="spread",
                         inputs=[{"metric": "BUY_QUOTE_VOL"}])])
    for tid in AVERAGES:
        spec = outer("CLOSE", tid, "spread")
        top = spec.get("innerWindowMaximum")
        if top:
            one(f"V.CLOSE.{tid}.spread.inner.max{top}",
                C("CLOSE", tid, window=top, chainedTransformId="spread", inputs=[{"metric": "SMA20"}]))
            one(f"V.CLOSE.{tid}.spread.inner.over",
                C("CLOSE", tid, window=top + 1, chainedTransformId="spread", inputs=[{"metric": "SMA20"}]))
    one("V.no.inner.window", C("CLOSE", "ema", chainedTransformId="spread", inputs=[{"metric": "EMA50"}]))
    one("V.no.inputs", C("CLOSE", "ema", window=20, chainedTransformId="spread"))
    one("V.chainedWindow", C("CLOSE", "ema", window=20, chainedTransformId="spread", chainedWindow=5,
                             inputs=[{"metric": "EMA50"}]))
    one("V.operand.other.unit", C("CLOSE", "ema", window=20, chainedTransformId="spread", inputs=[{"metric": "RSI14"}]))
    one("V.operand.timeless", C("CLOSE", "ema", window=20, chainedTransformId="spread", inputs=[{"metric": "ASIA_HIGH"}]))
    one("V.abs4h.offanchor.operand", C("CLOSE", "ema", window=20, timeframe={"abs": "4h"}, chainedTransformId="spread",
                                       inputs=[{"metric": "SMA20"}]))
    one("V.abs4h.anchor.only.operand", C("CLOSE", "ema", window=20, timeframe={"abs": "4h"},
                                         chainedTransformId="spread", inputs=[{"metric": "PIVOT_WEEK_P"}]))
    one("V.bars.closed", C("CLOSE", "ema", window=20, chainedTransformId="spread", bars="closed",
                           inputs=[{"metric": "EMA50"}]))
    one("V.bars.all", C("CLOSE", "ema", window=20, chainedTransformId="spread", bars="all",
                        inputs=[{"metric": "EMA50"}]))
    one("V.offset1", C("CLOSE", "ema", window=20, chainedTransformId="spread", offset=1, inputs=[{"metric": "EMA50"}]))
    one("V.averaged.operand", C("CLOSE", "ema", window=20, chainedTransformId="spread",
                                inputs=[avg("CLOSE", "aggregate", 50)]))
    one("V.after.distance", C("CLOSE", "distance", chainedTransformId="spread", inputs=[{"metric": "EMA50"}]))
    one("V.after.zscore", C("RSI14", "zscore", window=20, chainedTransformId="spread", inputs=[{"metric": "RSI7"}]))

    print("W. a spread operand under an average")
    batch("W.accept", [C("CLOSE", "spread", inputs=[avg("CLOSE", "ema", 20)]),
                       C("CLOSE", "spread", inputs=[avg("CLOSE", "aggregate", 50)]),
                       C("CLOSE", "spread", inputs=[avg("HIGH", "wma", 10)]),
                       C("CLOSE", "spread", inputs=[avg("SMA50", "rma", 14)]),
                       C("RSI14", "spread", inputs=[avg("RSI14", "ema", 9)]),
                       C("QUOTE_VOL", "spread", inputs=[avg("QUOTE_VOL", "aggregate", 20)]),
                       C("CLOSE", "spread", inputs=[avg("CLOSE", "ema", 2)])])
    one("W.window1", C("CLOSE", "spread", inputs=[avg("CLOSE", "ema", 1)]))
    one("W.no.window", C("CLOSE", "spread", inputs=[{"metric": "CLOSE", "transformId": "ema"}]))
    one("W.window.no.transform", C("CLOSE", "spread", inputs=[{"metric": "CLOSE", "window": 20}]))
    for tid in ("rsi", "zscore", "trajectory"):
        one(f"W.transform.{tid}", C("CLOSE", "spread", inputs=[avg("CLOSE", tid, 14)]))
    for tid, top in (("aggregate", 2436), ("ema", 704), ("rma", 308), ("wma", 2436)):
        one(f"W.{tid}.window.{top}", C("CLOSE", "spread", inputs=[avg("CLOSE", tid, top)]))
        one(f"W.{tid}.window.over", C("CLOSE", "spread", inputs=[avg("CLOSE", tid, top + 1)]))
    one("W.operand.timeless", C("CLOSE", "spread", inputs=[avg("ASIA_HIGH", "ema", 20)]))
    one("W.operand.other.unit", C("CLOSE", "spread", inputs=[avg("RSI14", "ema", 20)]))
    one("W.operand.not.averageable", C("CLOSE", "spread", inputs=[avg("MARK", "ema", 20)]))
    one("W.abs4h", C("CLOSE", "spread", timeframe={"abs": "4h"}, inputs=[avg("CLOSE", "ema", 20)]))
    one("W.lower", C("CLOSE", "spread", timeframe={"rel": "lower"}, inputs=[avg("CLOSE", "ema", 20)]))
    one("W.offset1", C("CLOSE", "spread", offset=1, inputs=[avg("CLOSE", "ema", 20)]))
    one("W.bars.all", C("CLOSE", "spread", bars="all", inputs=[avg("CLOSE", "ema", 20)]))
    one("W.chain.trajectory", C("CLOSE", "spread", inputs=[avg("CLOSE", "ema", 20)], chainedTransformId="trajectory",
                                window=4))
    one("W.chain.aggregate", C("CLOSE", "spread", inputs=[avg("CLOSE", "ema", 20)], chainedTransformId="aggregate",
                               window=10))
    one("W.chain.rank", C("CLOSE", "spread", inputs=[avg("CLOSE", "ema", 20)], chainedTransformId="rank",
                          ordering="hi"))
    one("W.two.inputs", C("CLOSE", "spread", inputs=[avg("CLOSE", "ema", 20), {"metric": "EMA50"}]))


def groups_round3(batch, one, probe):
    """PROBE_ROUND=3 (after V and W answered): is depth judged per side or jointly when BOTH sides average - a chained
    spread whose inner and operand each sit at their own maximum - and does an operand with its own lookback (SMA200)
    shorten the averaged operand's window maximum."""
    print("J. joint depth when both sides average")
    one("J.inner.ema704.op.agg2436", C("CLOSE", "ema", window=704, chainedTransformId="spread",
                                       inputs=[avg("CLOSE", "aggregate", 2436)]))
    one("J.inner.agg2436.op.ema704", C("CLOSE", "aggregate", window=2436, chainedTransformId="spread",
                                       inputs=[avg("CLOSE", "ema", 704)]))
    one("J.inner.rma308.op.rma308", C("CLOSE", "rma", window=308, chainedTransformId="spread",
                                      inputs=[avg("CLOSE", "rma", 308)]))
    one("J.op.SMA200.agg2436", C("CLOSE", "spread", inputs=[avg("SMA200", "aggregate", 2436)]))
    one("J.op.SMA200.ema704", C("CLOSE", "spread", inputs=[avg("SMA200", "ema", 704)]))
    one("J.base.SMA200.op.close.agg2436", C("SMA200", "spread", inputs=[avg("CLOSE", "aggregate", 2436)]))
    one("J.abs4h.op.agg2436", C("CLOSE", "spread", timeframe={"abs": "4h"}, inputs=[avg("CLOSE", "aggregate", 2436)]))


if __name__ == "__main__":
    import os
    if not P.CONTRACT.startswith(("168.", "169.")):
        sys.exit("run with PROBE_CONTRACT set to the served 168.x / 169.x contract")
    chosen = groups_round3 if os.environ.get("PROBE_ROUND") == "3" else groups
    sys.exit(P.main(chosen, what=__doc__.strip().splitlines()[0]))
