"""Systematic rule search for REGIME_MOM, OI_VELOCITY and CONFIDENCE.

In an earlier message I wrote that these three "would need the same search against
operands that aren't exposed" - having never run it. That was an assertion dressed as a
conclusion. This runs it, against the operands that ARE exposed.

Method is the one that cracked PRICE_ZONE and produced a clean negative for REGIME_TREND:
enumerate every candidate the exposed columns can express, score all of them, and report
the winner TOGETHER WITH its margin over the mode baseline - so a weak winner reads as
weak. See scripts/regime_rule_search.py for the REGIME_TREND run.

Input is data/samples/tier_c_drivers_1h.md, the verbatim render, parsed rather than
re-keyed. Every label sits beside its drivers in that one table, so nothing is compared
across sampling instants.

    python -m scripts.tier_c_rule_search
"""
from __future__ import annotations

import itertools
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data/samples/tier_c_drivers_1h.md"
UNITS = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def parse():
    """Read the rendered markdown table into dicts. '-' becomes None."""
    lines = [l for l in SAMPLE.read_text(encoding="utf-8").splitlines()
             if l.startswith("|")]
    head = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:                                   # skip the |---| rule
        cells = [c.strip() for c in line.strip("|").split("|")]
        r = {k: (None if v == "—" else v) for k, v in zip(head, cells)}
        for k in ("ROC", "PPO", "MACD", "RSI14", "chg4h", "chg24h"):
            r[k] = float(r[k].rstrip("%"))
        # "$545.0K" -> 545000.0, and keep the display quantum (0.1 * unit) so a
        # second difference that is zero only because of rounding stays visible.
        oi, quanta = [], []
        for k in ("OI_t3", "OI_t2", "OI_t1", "OI_now"):
            m = re.fullmatch(r"\$([\d.]+)([KMBT])", r[k])
            mult = UNITS[m.group(2)]
            oi.append(float(m.group(1)) * mult)
            digits = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
            quanta.append(10 ** -digits * mult)
        r["OI"] = oi
        r["quantum"] = max(quanta)
        rows.append(r)
    return rows


ROWS = parse()


def report(name, key, cands, rows=None, note=None):
    rows = [r for r in (rows if rows is not None else ROWS) if r[key] is not None]
    counts = Counter(r[key] for r in rows)
    mode, hits = counts.most_common(1)[0]
    base = hits / len(rows)
    scored = sorted(((sum(f(r) == r[key] for r in rows) / len(rows), lbl)
                     for lbl, f in cands), reverse=True)
    top, best = scored[0]
    print(f"\n=== {name}  ({len(rows)} rows) ===")
    print(f"  distribution {dict(counts)}")
    print(f"  baseline, always {mode!r}: {base:.0%}")
    for s, lbl in scored[:4]:
        print(f"    {s:>6.0%}  {lbl}")
    verdict = ("IDENTIFIED" if top >= 0.95 else
               "PARTIAL" if top >= base + 0.15 else "NOT identified")
    print(f"  best {top:.0%} vs baseline {base:.0%}  (margin {top - base:+.0%})"
          f"  ->  {verdict}")
    if note:
        print(f"  note: {note}")
    return {"metric": name, "rows": len(rows), "distribution": dict(counts),
            "baseline": round(base, 3), "baselineLabel": mode,
            "best": round(top, 3), "bestRule": best,
            "margin": round(top - base, 3), "verdict": verdict,
            "runnerUp": round(scored[1][0], 3) if len(scored) > 1 else None}


def regime_mom():
    cands = []
    for k in ("ROC", "PPO", "MACD", "chg4h", "chg24h"):
        for t in (0.0, 0.005, 0.01, 0.05, 0.1, 0.3):
            cands.append((f"sign({k}), |x|<{t} -> neutral",
                          lambda r, k=k, t=t: "neutral" if abs(r[k]) < t else
                          ("bullish" if r[k] > 0 else "bearish")))
    for lo, hi in ((45, 55), (40, 60), (35, 65), (30, 70), (50, 50)):
        cands.append((f"RSI14 <{lo} bearish, >{hi} bullish, else neutral",
                      lambda r, lo=lo, hi=hi: "bearish" if r["RSI14"] < lo else
                      ("bullish" if r["RSI14"] > hi else "neutral")))
    # "diverging" ought to mean price and momentum disagree - test that directly
    for k in ("ROC", "PPO", "MACD"):
        cands.append((f"{k} vs chg24h disagree -> diverging, else sign(chg24h)",
                      lambda r, k=k: "diverging" if r[k] * r["chg24h"] < 0 else
                      ("bullish" if r["chg24h"] > 0 else "bearish")))
    return report("REGIME_MOM", "regMom", cands)


def oi_velocity():
    """The pace of OI change = whether |last delta| grew or shrank."""
    def deltas(r):
        a, b, c, d = r["OI"]
        return abs(c - b), abs(d - c)                        # previous, latest
    cands = []
    for mult in (0.0, 0.5, 1.0):                             # tolerance in display quanta
        cands.append((f"|d_last| vs |d_prev|, tie band {mult} quantum",
                      lambda r, m=mult: (
                          "steady" if abs(deltas(r)[1] - deltas(r)[0]) <= m * r["quantum"]
                          else "accelerating" if deltas(r)[1] > deltas(r)[0]
                          else "decelerating")))
    cands.append(("sign of last delta (up=accel, down=decel)",
                  lambda r: "accelerating" if r["OI"][3] > r["OI"][2] else
                  "decelerating" if r["OI"][3] < r["OI"][2] else "steady"))
    cands.append(("OI_trend rising=accelerating / falling=decelerating",
                  lambda r: {"rising": "accelerating", "falling": "decelerating",
                             "flat": "steady"}[r["OI_trend"]]))
    full = report("OI_VELOCITY", "oiVel", cands)

    # Diagnostic, NOT the headline. Where all four displayed values are identical the
    # second difference is 0-0 and undefined at display precision - the rule cannot be
    # tested there. Reported separately, and the full-sample number above stands.
    resolvable = [r for r in ROWS if len(set(r["OI"])) > 1]
    sub = report("OI_VELOCITY (resolvable subset)", "oiVel", cands, rows=resolvable,
                 note="rows whose four displayed OI values are not all identical; "
                      "excluded rows have an undefined second difference at display "
                      "precision, not a wrong one")
    full["resolvableSubset"] = sub
    return full


def confidence():
    cands = [("== PERP_SPOT_STRENGTH", lambda r: r["perpSpotStr"])]
    fa = ["aligned bullish", "aligned bearish", "divergent", "neutral"]
    for perm in set(itertools.permutations(["high", "moderate", "low", "moderate"])):
        m = dict(zip(fa, perm))
        cands.append((f"FLOW_ALIGN -> {'/'.join(perm)}", lambda r, m=m: m[r["flowAlign"]]))
    sr = ["confirmed", "hidden distribution", "hidden accumulation", None]
    for perm in set(itertools.permutations(["high", "moderate", "moderate", "moderate"])):
        m = dict(zip(sr, perm))
        cands.append((f"SMART_RETAIL -> {'/'.join(str(p) for p in perm)}",
                      lambda r, m=m: m.get(r["smartRetail"], "moderate")))
    # the two together: does a confirmed read plus a decisive flow lift it to high?
    for need in (True, False):
        cands.append((f"confirmed AND flow{'' if need else ' not'} divergent -> high",
                      lambda r, n=need: "high" if (
                          r["smartRetail"] == "confirmed" and
                          ((r["flowAlign"] == "divergent") == n)) else "moderate"))
    return report("CONFIDENCE", "conf", cands)


def main() -> int:
    print(f"{len(ROWS)} coins, 1h anchor, from {SAMPLE.relative_to(ROOT).as_posix()}")
    out = [regime_mom(), oi_velocity(), confidence()]
    dest = ROOT / "data/audit/tier_c_rule_search.json"
    dest.write_text(json.dumps(
        {"_source": SAMPLE.relative_to(ROOT).as_posix(), "rows": len(ROWS),
         "anchor": "1h", "results": out}, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {dest.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
