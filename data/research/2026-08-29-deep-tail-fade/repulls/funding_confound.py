"""The FUNDING-leg confound test (Deep-Tail Fade), run on the on-disk repulls.

THE QUESTION. Since run 1 the study has carried: "funding was positive 94-100% of hours, so 'aligned' ~ 'fade-short':
confounded with side, unproven" - and "the FUNDING-leg confound resolves only in a window containing negative-funding
hours". Runs 5 and 6 (2026-09-09, 2026-09-12) are the first such windows. This script answers it.

A fade event is analyze_repull.py's own (VWAP4 stretch, base-calibrated threshold, next-bar reversion); it executes that
script and takes its merged `series`, `base_max`, `event_cut` and `ref` rather than copying them. Funding is
Hyperliquid's hourly record: data/research/2026-08-29-deep-tail-fade/funding_history.json plus every repull's
funding_raw.json, merged by hour (a later pull wins). "Aligned" is the preset's FADE fallback clause: a long fade with
rate < 0, a short fade with rate > 0 - the fade is paid funding.

The confound is SIDE. So events are stratified side x alignment, and alignment is judged only WITHIN a side.

PRE-REGISTERED READING (written and committed before any number below was computed, 2026-10-12):
  - Majors only (BTC, ETH, SOL - the only coins with a funding record), stretch > 75th and > 90th, on the COMBINED
    corpus and on the NEW-ONLY slice (analyze_repull's definitions).
  - A side is TESTABLE when both its aligned and its opposed cell hold >= 10 events.
  - The FUNDING leg is SHOWN at a stretch level only if: at least one side is testable, on EVERY testable side the
    aligned cell's mean edge exceeds the opposed cell's, and the side-stratified pooled difference (aligned - opposed
    mean edge, each side weighted by min(n_aligned, n_opposed)) has a 95% interval (Welch, per side, combined by those
    weights) that excludes 0.
  - Otherwise NOT SHOWN - which includes "not testable". A not-shown leg stays context; it is never a condition clause.
The combined-corpus >75th reading is the primary one (largest n); the others are reported, not decisive.

Run from the repo root:  python data/research/2026-08-29-deep-tail-fade/repulls/funding_confound.py
"""
from __future__ import annotations

import contextlib
import glob
import io
import json
import math
import os
import runpy
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.dirname(HERE)
MAJORS = ("BTC", "ETH", "SOL")
MIN_CELL = 10

with contextlib.redirect_stdout(io.StringIO()):
    G = runpy.run_path(os.path.join(HERE, "analyze_repull.py"), run_name="analyze_repull")
series, base_max, event_cut, ref = G["series"], G["base_max"], G["event_cut"], G["ref"]


def _hour(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(
        minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00.000Z")


funding: dict[str, dict[str, float]] = {c: {} for c in MAJORS}
sources = [os.path.join(CORPUS, "funding_history.json")] + sorted(glob.glob(os.path.join(HERE, "*", "funding_raw.json")))
for path in sources:
    doc = json.load(open(path, encoding="utf-8"))
    coins = doc.get("coins", doc)
    for coin in MAJORS:
        for row in coins.get(coin, []):
            funding[coin][_hour(row["time"])] = float(row["rate"])


def events(pct: float, new_only: bool) -> list[dict]:
    out = []
    for coin in MAJORS:
        rows = series[(coin, "1h")]
        cut = base_max[(coin, "1h")]
        px = ref(rows, 4, True)
        pool = [i for i in range(len(rows)) if px[i] and (not new_only or rows[i][0] <= cut)]
        devs = sorted(abs((rows[i][1] - px[i]) / px[i]) for i in pool)
        thr = devs[int(pct * len(devs))]
        for i in range(3, len(rows) - 1):
            if px[i] is None or (new_only and rows[i][0] <= event_cut[(coin, "1h")]):
                continue
            d = (rows[i][1] - px[i]) / px[i]
            if d == 0 or abs(d) <= thr:
                continue
            r1 = rows[i + 1][1] / rows[i][1] - 1
            if r1 == 0:
                continue
            long_side = d < 0
            rate = funding[coin].get(rows[i][0])
            out.append({"coin": coin, "t": rows[i][0], "side": "long" if long_side else "short",
                        "rate": rate, "edge": (r1 if long_side else -r1) * 10000,
                        "hit": (r1 > 0) == long_side,
                        "aligned": None if rate is None or rate == 0 else ((rate < 0) if long_side else (rate > 0))})
    return out


def cell(evs: list[dict]) -> dict:
    n = len(evs)
    if not n:
        return {"n": 0}
    e = [x["edge"] for x in evs]
    m = sum(e) / n
    var = sum((x - m) ** 2 for x in e) / (n - 1) if n > 1 else 0.0
    return {"n": n, "hit": sum(x["hit"] for x in evs) / n, "edge": m, "var": var}


def reading(evs: list[dict]) -> dict:
    sides = {}
    num = den = var = 0.0
    for side in ("long", "short"):
        a = cell([x for x in evs if x["side"] == side and x["aligned"] is True])
        o = cell([x for x in evs if x["side"] == side and x["aligned"] is False])
        testable = a["n"] >= MIN_CELL and o["n"] >= MIN_CELL
        sides[side] = {"aligned": a, "opposed": o, "testable": testable}
        if testable:
            w = min(a["n"], o["n"])
            num += w * (a["edge"] - o["edge"])
            den += w
            var += w * w * (a["var"] / a["n"] + o["var"] / o["n"])
    testable = [s for s in sides if sides[s]["testable"]]
    if not testable:
        return {"sides": sides, "verdict": "NOT SHOWN (not testable)"}
    diff = num / den
    ci = 1.96 * math.sqrt(var) / den
    every = all(sides[s]["aligned"]["edge"] > sides[s]["opposed"]["edge"] for s in testable)
    shown = every and diff - ci > 0
    return {"sides": sides, "pooledDiff": diff, "ci95": ci,
            "verdict": "SHOWN" if shown else "NOT SHOWN"}


def fmt(c: dict) -> str:
    if not c["n"]:
        return "n=  0"
    return f"n={c['n']:>3}  hit {100 * c['hit']:5.1f}%  edge {c['edge']:+7.1f} bps"


def main() -> dict:
    record = {}
    for label, new_only in (("COMBINED", False), ("NEW-ONLY", True)):
        for pct in (0.75, 0.90):
            evs = events(pct, new_only)
            missing = sum(1 for x in evs if x["rate"] is None)
            r = reading(evs)
            key = f"{label} >{int(pct * 100)}th"
            print(f"===== {key}: {len(evs)} events, funding missing on {missing}, "
                  f"negative-funding events {sum(1 for x in evs if x['rate'] is not None and x['rate'] < 0)} =====")
            for side in ("long", "short"):
                s = r["sides"][side]
                print(f"  {side:<5} aligned  {fmt(s['aligned'])}")
                print(f"  {side:<5} opposed  {fmt(s['opposed'])}   testable={s['testable']}")
            if "pooledDiff" in r:
                print(f"  side-stratified aligned - opposed: {r['pooledDiff']:+.1f} bps +/- {r['ci95']:.1f}")
            print(f"  -> {r['verdict']}")
            record[key] = {"events": len(evs), "fundingMissing": missing, **{
                k: v for k, v in r.items() if k != "sides"},
                "sides": {s: {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "var"})
                              for k, v in d.items()} for s, d in r["sides"].items()}}
    return record


if __name__ == "__main__":
    main()
