"""OMEGA read-only authoring probe at contract 161.0.0 (2026-11-09): what 150 - 161 added or moved on the custom column.

161.0.0 is undocumented past v156 (README "Contract history" at 2026-11-09T16:10Z); the served schema and the 534 raw
hints read at 161.0.0 are the source of every value below. Groups:

- K  `roc` as a column transform (window default 9, served maximum per metric);
- L  `roc` as a chain outer after spread / distance / relativeTo (windowParameter `window`);
- M  `levelInteraction` as a chain outer after rollingMax / rollingMin, with `buffer` (bps) or `touchAtr`;
- N  the rolling-inner chains 161 opened (aggregate / ema / rma / wma / rsi / cci / roc -> 13 outers), whose outer
     window is the new `chainedWindow` field and whose inner keeps `window`;
- O  the window maxima that moved (aggregate 936 -> 2436 on RSI14 ...), at the served maximum and one past;
- P  a spread operand read off the anchor (`spreadOperandsOffAnchor` is served beside `spreadOperands`; a day /
     session level is in the second only);
- Q  every (metric, knob) cell served at 161 that omega.fanout.KNOB_SPELLING_RENDERED has no render of, one step off
     its default;
- R  the three metric keys 161 added, every served transform;
- S  BB_TOUCH, which 161 removed;
- T  `levelInteraction`'s buffer above its served 500 (the schema's column maximum rose to 2^53-1) and `touchAtr`;
- U  which crowd headers `authoring.conditionColumns` offers at each strategy timeframe (v156 drops the eight `...Live`
     headers and any crowd header on a main candle no Market Grid time range settles on).

Read-only: preview_strategy_report over mcporter (battlegrid-anbu), the machinery and rules of probe_authoring_148
(main(extra_groups)). Writes data/audit/authoring_probe_161_<PROBE_DATE>.json and
data/contract/columns/_probe_161_<PROBE_DATE>.json.

    PATH=<npx shim>:$PATH PROBE_CONTRACT=161.0.0 PROBE_DATE=2026-11-09 PROBE_HINTS=<hints_20261109> \
        python -m scripts.probe_authoring_161
"""
from __future__ import annotations

import os
import sys

from scripts import probe_authoring_148 as P
from scripts.probe_authoring_148 import C, hint, served_transforms, section

ROLLING_INNERS = ("aggregate", "ema", "rma", "wma", "rsi", "cci", "roc")
NEW_METRICS = ("VWMA20", "DONCHIAN_BROKEN_HI_PRIOR", "DONCHIAN_BROKEN_LO_PRIOR")
TIMEFRAMES = ("15m", "1h", "4h", "1d")
CROWD = ("CROWD_PICK", "CROWD_PICK_LIVE", "CROWD_UPBIAS", "CROWD_UPBIAS_LIVE", "CROWD_ACC", "CROWD_ACC_LIVE",
         "CROWD_UP_LEAN_Z", "CROWD_UP_LEAN_Z_LIVE")


def transform(metric, tid):
    return next((t for t in hint(metric)["transforms"] if t["id"] == tid), None)


def wmax(metric, tid):
    t = transform(metric, tid) or {}
    return ((t.get("authoring") or {}).get("parameters") or {}).get("window", {}).get("maximum")


def outer(metric, inner, out):
    return ((transform(metric, inner) or {}).get("chainedOuters") or {}).get(out) or {}


def off_default(spec):
    """One served step off the knob's default, inside its bounds (None when the knob has no room)."""
    d, step = spec.get("defaultValue"), spec.get("step") or 1
    lo, hi = spec.get("minimum"), spec.get("maximum")
    if isinstance(d, bool):
        return not d
    if not isinstance(d, (int, float)):
        return None
    for v in (d + step, d - step):
        v = round(v, 6) if isinstance(step, float) or isinstance(d, float) else v
        if (lo is None or v >= lo) and (hi is None or v <= hi):
            return v
    return None


def new_knob_cells():
    from omega.fanout import KNOB_SPELLING_RENDERED
    cells = []
    for name in sorted(os.listdir(P.HINTS)):
        if not name.endswith(".json") or name.startswith("_"):
            continue
        m = hint(name[:-5])
        for knob, spec in sorted((m.get("parameters") or {}).items()):
            if knob in KNOB_SPELLING_RENDERED.get(m["metric"], frozenset()):
                continue
            v = off_default(spec)
            cells.append((m["metric"], knob, v, spec))
    return cells


def groups(batch, one, probe):
    print("K. roc as a transform")
    rmax = wmax("RSI14", "roc")
    batch("K.accept", [C("CLOSE", "roc"), C("CLOSE", "roc", window=5), C("RSI14", "roc", window=3),
                       C("QUOTE_VOL", "roc", window=9), C("CLOSE", "roc", window=5, bars="closed"),
                       C("CLOSE", "roc", window=5, timeframe={"abs": "4h"}), C("RSI14", "roc", window=1)])
    one("K.RSI14.roc.max", C("RSI14", "roc", window=rmax))
    one("K.RSI14.roc.over", C("RSI14", "roc", window=rmax + 1))
    one("K.RSI14.roc.offset1", C("RSI14", "roc", window=5, offset=1))
    one("K.PIVOT_WEEK_P.roc", C("PIVOT_WEEK_P", "roc", window=5))

    print("L. roc as a chain outer")
    batch("L.accept", [C("CLOSE", "distance", chainedTransformId="roc", window=5),
                       C("RSI14", "spread", inputs=[{"metric": "RSI7"}], chainedTransformId="roc", window=5),
                       C("CLOSE", "relativeTo", chainedTransformId="roc", window=5),
                       C("EMA20", "distance", chainedTransformId="roc")])
    lmax = outer("CLOSE", "distance", "roc").get("windowMaximum")
    if lmax:
        one("L.CLOSE.distance.roc.max", C("CLOSE", "distance", chainedTransformId="roc", window=lmax))
        one("L.CLOSE.distance.roc.over", C("CLOSE", "distance", chainedTransformId="roc", window=lmax + 1))

    print("M. levelInteraction as a chain outer")
    batch("M.accept", [C("HIGH", "rollingMax", window=20, offset=1, chainedTransformId="levelInteraction"),
                       C("LOW", "rollingMin", window=20, offset=1, chainedTransformId="levelInteraction"),
                       C("HIGH", "rollingMax", window=20, offset=1, chainedTransformId="levelInteraction", buffer=10),
                       C("HIGH", "rollingMax", window=20, offset=1, chainedTransformId="levelInteraction",
                         touchAtr=0.5)])
    one("M.both.buffer.touchAtr", C("HIGH", "rollingMax", window=20, offset=1, chainedTransformId="levelInteraction",
                                    buffer=10, touchAtr=0.5))
    one("M.offset0", C("HIGH", "rollingMax", window=20, offset=0, chainedTransformId="levelInteraction"))
    one("M.buffer501", C("HIGH", "rollingMax", window=20, offset=1, chainedTransformId="levelInteraction", buffer=501))

    print("N. rolling-inner chains (chainedWindow)")
    batch("N.accept", [C("CLOSE", "ema", window=20, chainedTransformId="aggregate", chainedWindow=5),
                       C("RSI14", "rma", window=14, chainedTransformId="roc", chainedWindow=3),
                       C("CLOSE", "aggregate", window=10, chainedTransformId="zscore", chainedWindow=20),
                       C("RSI14", "roc", window=5, chainedTransformId="ema", chainedWindow=10),
                       C("CLOSE", "wma", window=10, chainedTransformId="rollingMax", chainedWindow=20)])
    one("N.no.chainedWindow", C("CLOSE", "ema", window=20, chainedTransformId="aggregate"))
    one("N.no.window", C("CLOSE", "ema", chainedTransformId="aggregate", chainedWindow=5))
    nmax = outer("RSI14", "ema", "aggregate")
    if nmax.get("windowMaximum"):
        one("N.chainedWindow.max", C("RSI14", "ema", window=14, chainedTransformId="aggregate",
                                     chainedWindow=nmax["windowMaximum"]))
        one("N.chainedWindow.over", C("RSI14", "ema", window=14, chainedTransformId="aggregate",
                                      chainedWindow=nmax["windowMaximum"] + 1))
    if nmax.get("innerWindowMaximum"):
        one("N.innerWindow.max", C("RSI14", "ema", window=nmax["innerWindowMaximum"], chainedTransformId="aggregate",
                                   chainedWindow=5))
        one("N.innerWindow.over", C("RSI14", "ema", window=nmax["innerWindowMaximum"] + 1,
                                    chainedTransformId="aggregate", chainedWindow=5))
    one("N.spread.chainedWindow", C("RSI14", "spread", inputs=[{"metric": "RSI7"}], chainedTransformId="ema",
                                    window=10, chainedWindow=5))

    print("O. moved window maxima")
    for metric, tid in (("RSI14", "aggregate"), ("CLOSE", "ema"), ("RSI14", "rma"), ("RSI14", "zscore"),
                        ("RSI14", "pctl"), ("CLOSE", "rollingMax")):
        m = wmax(metric, tid)
        if m:
            one(f"O.{metric}.{tid}.max{m}", C(metric, tid, window=m))
            one(f"O.{metric}.{tid}.over", C(metric, tid, window=m + 1))
    dmax = outer("HIGH", "distance", "ema").get("windowMaximum")
    if dmax:
        one(f"O.HIGH.distance.ema.max{dmax}", C("HIGH", "distance", chainedTransformId="ema", window=dmax))
        one("O.HIGH.distance.ema.over", C("HIGH", "distance", chainedTransformId="ema", window=dmax + 1))

    print("P. spread operands off the anchor")
    batch("P.anchor", [C("CLOSE", "spread", inputs=[{"metric": "ASIA_HIGH"}]),
                       C("CLOSE", "spread", inputs=[{"metric": "PIVOT_WEEK_P"}]),
                       C("CLOSE", "spread", inputs=[{"metric": "EMA20"}])])
    for name, kw in (("abs4h", {"timeframe": {"abs": "4h"}}), ("lower", {"timeframe": {"rel": "lower"}}),
                     ("offset1", {"offset": 1}), ("closed", {"bars": "closed"})):
        one(f"P.ASIA_HIGH.{name}", C("CLOSE", "spread", inputs=[{"metric": "ASIA_HIGH"}], **kw))
        one(f"P.EMA20.{name}", C("CLOSE", "spread", inputs=[{"metric": "EMA20"}], **kw))
    one("P.ASIA_HIGH.chain.aggregate", C("CLOSE", "spread", inputs=[{"metric": "ASIA_HIGH"}],
                                         chainedTransformId="aggregate", window=10))

    print("Q. knob cells never rendered")
    cells = new_knob_cells()
    print(f"   {len(cells)} cells")
    cols = [C(m, **{k: v}) for m, k, v, _ in cells if v is not None]
    for i in range(0, len(cols), 8):
        batch(f"Q.cells.{i // 8}", cols[i:i + 8])
    # two knobs of one family off together (the SET regime: the whole set spelled once any is off), and all four
    batch("Q.ichimoku.sets", [C("ICHI_BASE", conversionPeriod=10, basePeriod=27),
                              C("ICHI_SPAN_B", conversionPeriod=10, basePeriod=27, spanBPeriod=53, displacement=27),
                              C("ICHI_CONV", conversionPeriod=9, basePeriod=26, spanBPeriod=52, displacement=26),
                              C("ADX", "trajectory", window=4, period=15)])
    for m, k, v, spec in cells:
        if v is None:
            print(f"   no room off default: {m}.{k} {spec}")

    print("R. the three metric keys 161 added")
    for m in NEW_METRICS:
        tcols = []
        for tid in served_transforms(m):
            kw = {}
            if tid == "spread":
                ops = hint(m).get("spreadOperands") or []
                if not ops:
                    continue
                kw["inputs"] = [{"metric": "CLOSE" if "CLOSE" in ops else ops[0]}]
            if tid in ("aggregate", "ema", "rma", "wma", "rsi", "cci", "roc", "zscore", "stddev", "linregSlope", "pctl",
                       "rollingMin", "rollingMax", "trajectory", "efficiency"):
                kw["window"] = 10
            tcols.append(C(m, tid, **kw))
        batch(f"R.{m}.served", tcols)

    print("S. BB_TOUCH (removed)")
    one("S.BB_TOUCH", C("BB_TOUCH"))

    print("T. levelInteraction buffer / touchAtr on a level")
    batch("T.accept", [C("BB_UPPER", "levelInteraction", buffer=500), C("BB_UPPER", "levelInteraction", touchAtr=0.5),
                       C("BB_UPPER", "levelInteraction"), C("BB_LOWER", "levelInteraction")])
    one("T.BB_UPPER.buffer501", C("BB_UPPER", "levelInteraction", buffer=501))
    one("T.BB_UPPER.both", C("BB_UPPER", "levelInteraction", buffer=10, touchAtr=0.5))
    one("T.BB_UPPER.touchAtr.on.value", C("BB_UPPER", touchAtr=0.5))

    print("U. crowd condition columns by timeframe")
    for tf in TIMEFRAMES:
        probe(f"U.crowd.{tf}", [section([C(m) for m in CROWD], f"U.crowd.{tf}")], timeframe=tf)


if __name__ == "__main__":
    if P.CONTRACT != "161.0.0":
        sys.exit("run with PROBE_CONTRACT=161.0.0")
    sys.exit(P.main(groups, what=__doc__.strip().splitlines()[0]))
