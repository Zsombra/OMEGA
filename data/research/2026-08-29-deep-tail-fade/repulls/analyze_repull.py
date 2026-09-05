"""Out-of-sample battery per the re-pull protocol (2026-08-29; amended 2026-09-02):
rebuild the combined per-coin 1h series (base corpus + every repull, deduped by
timestamp), then rerun the test_c_wide.py battery - identical ref()/revert_test()
math - on:

  (1) the COMBINED corpus, and
  (2) the NEW-ONLY slice: events counted only on bars strictly after each
      coin's base-corpus last timestamp, with the stretch threshold CALIBRATED
      ON THE BASE WINDOW (in-sample threshold, out-of-sample events - the
      cleanest reading the tiny slice allows; slice-internal percentiles over
      ~20 bars would be noise dressed as calibration).

THE pre-registered number is the >90th-pct 1h cell (hit%, edge, n) on the
new-only slice. Reading, fixed in advance by the protocol: sustained
out-of-sample hit <= 55% or edge <= 0 at the deep tail = the premise failed.

Collisions - the 2026-09-02 amendment. The platform revises closed bars after
serving them (volume upward, prices by ticks; see
data/audit/candle_restatement_2026-09-02.json), so two sources can disagree on
(close, volume) for the same timestamp. The resolution is explicit:

  POLICY=latest  (default) the most recent pull wins - the platform's current view.
  POLICY=first   the earliest source wins - reproduces every earlier run's pool exactly.
  POLICY=strict  the original behaviour: refuse to merge on ANY disagreement.

A close that differs by more than PRICE_TOL (1%) between sources aborts under
every policy: that is a price restatement, not tick noise, and must be recorded
in data/audit/ before any number is quoted. The amendment was made after re-pull
2, when THE cell had been verified identical under 'latest' and 'first'
(n=58, 58.6% +/-12.7pp, +1.8 bps): the policy does not move the number.

  WINDOW=cumulative (default) the pre-registered NEW-ONLY slice: every bar after
                              the base window, across ALL repulls.
  WINDOW=last                 supplementary only: events strictly after the
                              previous repull's last bar (this pull's window
                              alone). Thresholds are still base-calibrated.

Run from the repo root:
  python data/research/2026-08-29-deep-tail-fade/repulls/analyze_repull.py
"""
import glob
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.dirname(HERE)
POLICY = os.environ.get("POLICY", "latest")
WINDOW = os.environ.get("WINDOW", "cumulative")
PRICE_TOL = 0.01
# SETTLED=<hours> (default 0 = off, the pre-registered reading): drop every bar that was
# younger than <hours> at the time its winning source served it. Measured 2026-09-04: bars
# <=6h old at pull time are served incomplete (18/40 later revised, 0/1040 older), and a
# short volume in a young bar distorts the volume-weighted reference that decides cell
# membership. Pull times are not stored per source; the proxy is the source's latest bar
# open + one bar, which UNDERSTATES age by up to ~1h (run 3 pulled 33-40 min after its last
# close). Supplementary view only - it never replaces the SETTLED=0 reading.
SETTLED = float(os.environ.get("SETTLED", "0"))
if POLICY not in ("latest", "first", "strict"):
    raise SystemExit(f"POLICY must be latest|first|strict, got {POLICY!r}")
if WINDOW not in ("cumulative", "last"):
    raise SystemExit(f"WINDOW must be cumulative|last, got {WINDOW!r}")


# --- rebuild the combined series --------------------------------------------
def load_series(path):
    return json.load(open(path, encoding="utf-8"))["series"]


merged = {}          # key -> {timestamp: (close, volume)}
src_of = {}          # key -> {timestamp: index of the source whose value won}
src_last = []        # per source: key -> latest timestamp it served
sources = [os.path.join(CORPUS, "candles.json")] + sorted(
    glob.glob(os.path.join(HERE, "*", "candles.json")))
collisions = 0
max_dclose = max_dvol = 0.0
for si, src in enumerate(sources):
    src_last.append({})
    for key, rows in load_series(src).items():
        bucket = merged.setdefault(key, {})
        src_last[si][key] = max(r["timestamp"] for r in rows)
        for r in rows:
            t = r["timestamp"]
            val = (float(r["close"]), float(r["volume"]))
            if t in bucket and bucket[t] != val:
                old = bucket[t]
                collisions += 1
                dc = abs(val[0] - old[0]) / old[0] if old[0] else 0.0
                dv = abs(val[1] - old[1]) / old[1] if old[1] else 0.0
                max_dclose = max(max_dclose, dc)
                max_dvol = max(max_dvol, dv)
                if POLICY == "strict":
                    raise SystemExit(f"COLLISION DISAGREES: {key} {t} {old} vs {val}")
                if dc > PRICE_TOL:
                    raise SystemExit(
                        f"PRICE RESTATEMENT > {PRICE_TOL:.0%}: {key} {t} close {old[0]} vs "
                        f"{val[0]} - record it in data/audit/ before quoting any number")
                if POLICY == "first":
                    continue          # first-seen source wins
            if t in bucket and POLICY == "first":
                continue              # identical re-serve: the first source still owns it
            bucket[t] = val           # latest wins (or first write)
            src_of.setdefault(key, {})[t] = si
print(f"sources={len(sources)}  POLICY={POLICY}  WINDOW={WINDOW}  collisions={collisions}"
      f"  max|dclose|={max_dclose:.2e}  max|dvolume|={max_dvol:.2e}")

from datetime import datetime, timedelta


def _iso(t):
    return datetime.strptime(t, "%Y-%m-%dT%H:%M:%S.%fZ")


def _tf_hours(tf):
    n, unit = int(tf[:-1]), tf[-1]
    return n * {"m": 1 / 60, "h": 1, "d": 24}[unit]
dropped_young = 0
series = {}
for key, bucket in merged.items():
    sym, tf = key.rsplit("_", 1)
    rows = []
    for t, (c, v) in sorted(bucket.items()):
        if SETTLED > 0:
            served_at = _iso(src_last[src_of[key][t]][key]) + timedelta(hours=_tf_hours(tf))
            age_h = (served_at - (_iso(t) + timedelta(hours=_tf_hours(tf)))).total_seconds() / 3600
            if age_h < SETTLED:
                dropped_young += 1
                continue
        rows.append((t, c, v))
    series[(sym, tf)] = rows
if SETTLED > 0:
    print(f"SETTLED={SETTLED:g}h: dropped {dropped_young} bars served younger than {SETTLED:g}h "
          f"(age proxy = source's last close; understates by up to ~1h)")

base = load_series(os.path.join(CORPUS, "candles.json"))
base_max = {}        # per (sym, tf): last base-corpus timestamp - the THRESHOLD cutoff, always
for key, rows in base.items():
    sym, tf = key.rsplit("_", 1)
    base_max[(sym, tf)] = max(r["timestamp"] for r in rows)

event_cut = dict(base_max)   # the EVENT cutoff; equals base_max unless WINDOW=last
if WINDOW == "last":
    if len(sources) < 3:
        raise SystemExit("WINDOW=last needs at least two repulls (a previous one to cut at)")
    prior = sources[-2]
    for key, rows in load_series(prior).items():
        sym, tf = key.rsplit("_", 1)
        event_cut[(sym, tf)] = max(event_cut[(sym, tf)], max(r["timestamp"] for r in rows))
    print("WINDOW=last: events strictly after the last bar of", os.path.relpath(prior, CORPUS))

coins_1h = sorted(sym for sym, tf in series if tf == "1h")
print("1h coins:", coins_1h)
for c in coins_1h:
    rows = series[(c, "1h")]
    new = sum(1 for t, _, _ in rows if t > event_cut[(c, "1h")])
    print(f"  {c:>8}: combined n={len(rows)}, new-only n={new}")


# --- identical math to test_c_wide.py ---------------------------------------
def ref(rows, W, weighted=True):
    out = [None] * len(rows)
    for i in range(W - 1, len(rows)):
        if weighted:
            vv = sum(rows[j][2] for j in range(i - W + 1, i + 1))
            out[i] = (sum(rows[j][1] * rows[j][2] for j in range(i - W + 1, i + 1)) / vv
                      if vv else None)
        else:
            out[i] = sum(rows[j][1] for j in range(i - W + 1, i + 1)) / W
    return out


def revert_test(coins, W=4, pct=0.75, weighted=True, new_only=False):
    """new_only: threshold from base-window deviations; events only after event_cut."""
    hits = tot = 0
    edge = []
    per = {}
    for coin in coins:
        rows = series[(coin, "1h")]
        cut = base_max[(coin, "1h")]
        px = ref(rows, W, weighted)
        thr_pool = [i for i in range(len(rows))
                    if px[i] and (not new_only or rows[i][0] <= cut)]
        devs = sorted(abs((rows[i][1] - px[i]) / px[i]) for i in thr_pool)
        thr = devs[int(pct * len(devs))] if devs else 0
        h = t = 0
        for i in range(W - 1, len(rows) - 1):
            if px[i] is None:
                continue
            if new_only and rows[i][0] <= event_cut[(coin, "1h")]:
                continue
            d = (rows[i][1] - px[i]) / px[i]
            if d == 0 or abs(d) <= thr:
                continue
            r1 = rows[i + 1][1] / rows[i][1] - 1
            if r1 == 0:
                continue
            s = -1 if d > 0 else 1
            t += 1
            tot += 1
            if s * r1 > 0:
                h += 1
                hits += 1
            edge.append(s * r1 * 10000)
        per[coin] = (h, t)
    p = hits / tot if tot else 0
    ci = 1.96 * math.sqrt(p * (1 - p) / tot) if tot else 0
    e = sum(edge) / len(edge) if edge else 0
    return tot, p, ci, e, per


def fmt(label, res):
    t_, p_, c_, e_, _ = res
    return f"{label}: n={t_}  hit {100*p_:.1f}% +/- {100*c_:.1f}pp  edge {e_:+.1f}"


def battery(label, new_only):
    print()
    print(f"===== {label} =====")
    tot, p, ci, e, per = revert_test(coins_1h, new_only=new_only)
    print(f"VWAP4 >75th: n={tot}  hit {100*p:.1f}% +/- {100*ci:.1f}pp  edge {e:+.1f} bps/bar")
    print("per coin:", "  ".join(f"{c}:{h}/{t}" for c, (h, t) in sorted(per.items())))
    old = [c for c in ("BTC", "ETH", "SOL") if (c, "1h") in series]
    new = [c for c in coins_1h if c not in old]
    print(fmt("majors (3)", revert_test(old, new_only=new_only)))
    print(fmt("alts  (10)", revert_test(new, new_only=new_only)))
    print(fmt("SMA4 ablation >75th", revert_test(coins_1h, weighted=False, new_only=new_only)))
    print("threshold sweep (VWAP4):")
    for pct in (0.50, 0.75, 0.90):
        t_, p_, c_, e_, per_ = revert_test(coins_1h, pct=pct, new_only=new_only)
        marker = "  <-- THE CELL" if new_only and pct == 0.90 else ""
        print(f"  >{int(pct*100)}th: n={t_:>4}  hit {100*p_:.1f}% +/- {100*c_:.1f}pp  edge {e_:+.1f}{marker}")
        if new_only and pct == 0.90:
            # the per-coin and majors/alts split AT the cell - the pooled number is not
            # evidence for the created strategy's universe unless the majors carry it
            print("    per coin @>90th:", "  ".join(f"{c}:{h}/{t}" for c, (h, t) in sorted(per_.items())))
            print("    " + fmt("majors @>90th", revert_test(old, pct=0.90, new_only=True)))
            print("    " + fmt("alts   @>90th", revert_test(new, pct=0.90, new_only=True)))
            be = [c for c in ("BTC", "ETH") if (c, "1h") in series]
            print("    " + fmt("BTC+ETH only (the created strategy's universe) @>90th",
                               revert_test(be, pct=0.90, new_only=True)))
    print("window sweep (>75th):")
    for W in (3, 4, 6, 8):
        t_, p_, c_, e_, _ = revert_test(coins_1h, W=W, new_only=new_only)
        print(f"  W={W}: n={t_:>4}  hit {100*p_:.1f}% +/- {100*c_:.1f}pp  edge {e_:+.1f}")


battery("COMBINED corpus (base + repulls)", new_only=False)
battery(f"NEW-ONLY slice (base-calibrated thresholds, events after the "
        f"{'base window - CUMULATIVE across repulls' if WINDOW == 'cumulative' else 'previous repull - THIS WINDOW ONLY, supplementary'})",
        new_only=True)
