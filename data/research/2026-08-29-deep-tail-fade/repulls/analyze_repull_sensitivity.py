"""SENSITIVITY copy of analyze_repull.py (2026-09-02). Identical math; two knobs only:

  POLICY=first|latest   how a (close, volume) collision between sources is resolved.
                        The canonical script refuses to run once sources disagree
                        (COLLISION DISAGREES) - which they do since the platform restated
                        history on 2026-09-02, see data/audit/candle_restatement_2026-09-02.json.
                        first  = the earliest source wins (base > repull 1 > repull 2 ...);
                                 reproduces every earlier run's pool exactly.
                        latest = the most recent pull wins (the platform's current view).
  CUTOFF=base|run1      base  = the pre-registered NEW-ONLY slice: events strictly after
                                the base window, CUMULATIVE across all repulls.
                        run1  = supplementary: events strictly after re-pull 1's last bar
                                (this window only). Thresholds are STILL calibrated on the
                                base window in both cases - only the event cutoff moves.

Also prints the per-coin and majors/alts split AT the >90th cell (the canonical script
prints that split only at >75th). Run from the repo root:
  POLICY=first CUTOFF=base python data/research/2026-08-29-deep-tail-fade/repulls/analyze_repull_sensitivity.py
"""
import glob
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.dirname(HERE)

# --- rebuild the combined series --------------------------------------------
def load_series(path):
    return json.load(open(path, encoding="utf-8"))["series"]

POLICY = os.environ.get("POLICY", "first")
CUTOFF = os.environ.get("CUTOFF", "base")
COLLISIONS = [0]
merged = {}          # key -> {timestamp: (close, volume)}
sources = [os.path.join(CORPUS, "candles.json")] + sorted(
    glob.glob(os.path.join(HERE, "*", "candles.json")))
for src in sources:
    for key, rows in load_series(src).items():
        bucket = merged.setdefault(key, {})
        for r in rows:
            t = r["timestamp"]
            val = (float(r["close"]), float(r["volume"]))
            if t in bucket and bucket[t] != val:
                COLLISIONS[0] += 1
                if POLICY == "first":
                    continue          # first-seen source wins (base > run1 > run2)
            bucket[t] = val           # POLICY == "latest": later source wins

series = {}
for key, bucket in merged.items():
    sym, tf = key.rsplit("_", 1)
    series[(sym, tf)] = [(t, c, v) for t, (c, v) in sorted(bucket.items())]

base = load_series(os.path.join(CORPUS, "candles.json"))
base_max = {}        # per (sym, tf): last base-corpus timestamp
for key, rows in base.items():
    sym, tf = key.rsplit("_", 1)
    base_max[(sym, tf)] = max(r["timestamp"] for r in rows)

event_cut = dict(base_max)
if CUTOFF == "run1":   # supplementary: events strictly after re-pull 1's last bar; thresholds STILL base-calibrated
    for key, rows in load_series(os.path.join(HERE, "2026-08-30", "candles.json")).items():
        sym, tf = key.rsplit("_", 1)
        event_cut[(sym, tf)] = max(event_cut[(sym, tf)], max(r["timestamp"] for r in rows))
print(f"[sensitivity] POLICY={POLICY} CUTOFF={CUTOFF} collisions_resolved={COLLISIONS[0]}")
coins_1h = sorted(sym for sym, tf in series if tf == "1h")
print("1h coins:", coins_1h)
for c in coins_1h:
    rows = series[(c, "1h")]
    new = sum(1 for t, _, _ in rows if t > base_max[(c, "1h")])
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
    """new_only: threshold from base-window deviations; events only on new bars."""
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


def battery(label, new_only):
    print()
    print(f"===== {label} =====")
    tot, p, ci, e, per = revert_test(coins_1h, new_only=new_only)
    print(f"VWAP4 >75th: n={tot}  hit {100*p:.1f}% +/- {100*ci:.1f}pp  edge {e:+.1f} bps/bar")
    print("per coin:", "  ".join(f"{c}:{h}/{t}" for c, (h, t) in sorted(per.items())))
    old = [c for c in ("BTC", "ETH", "SOL") if (c, "1h") in series]
    new = [c for c in coins_1h if c not in old]
    t1, p1, c1, e1, _ = revert_test(old, new_only=new_only)
    t2, p2, c2, e2, _ = revert_test(new, new_only=new_only)
    print(f"majors (3): n={t1}  hit {100*p1:.1f}% +/- {100*c1:.1f}pp  edge {e1:+.1f}")
    print(f"alts  (10): n={t2}  hit {100*p2:.1f}% +/- {100*c2:.1f}pp  edge {e2:+.1f}")
    ts, ps, cs, es, _ = revert_test(coins_1h, weighted=False, new_only=new_only)
    print(f"SMA4 ablation >75th: n={ts}  hit {100*ps:.1f}% +/- {100*cs:.1f}pp  edge {es:+.1f}")
    print("threshold sweep (VWAP4):")
    for pct in (0.50, 0.75, 0.90):
        t_, p_, c_, e_, _ = revert_test(coins_1h, pct=pct, new_only=new_only)
        marker = "  <-- THE CELL" if new_only and pct == 0.90 else ""
        print(f"  >{int(pct*100)}th: n={t_:>4}  hit {100*p_:.1f}% +/- {100*c_:.1f}pp  edge {e_:+.1f}{marker}")
        if new_only and pct == 0.90:
            _, _, _, _, per90 = revert_test(coins_1h, pct=0.90, new_only=True)
            print("    per coin @>90th:", "  ".join(f"{c}:{h}/{t}" for c, (h, t) in sorted(per90.items())))
            tm, pm, cm, em, _ = revert_test(old, pct=0.90, new_only=True)
            ta, pa, ca, ea, _ = revert_test(new, pct=0.90, new_only=True)
            print(f"    majors @>90th: n={tm}  hit {100*pm:.1f}% +/- {100*cm:.1f}pp  edge {em:+.1f}")
            print(f"    alts   @>90th: n={ta}  hit {100*pa:.1f}% +/- {100*ca:.1f}pp  edge {ea:+.1f}")
            tb, pb, cb, eb, _ = revert_test([c for c in ("BTC", "ETH") if (c, "1h") in series], pct=0.90, new_only=True)
            print(f"    BTC+ETH only (the created strategy's universe) @>90th: n={tb}  hit {100*pb:.1f}% +/- {100*cb:.1f}pp  edge {eb:+.1f}")
    print("window sweep (>75th):")
    for W in (3, 4, 6, 8):
        t_, p_, c_, e_, _ = revert_test(coins_1h, W=W, new_only=new_only)
        print(f"  W={W}: n={t_:>4}  hit {100*p_:.1f}% +/- {100*c_:.1f}pp  edge {e_:+.1f}")


battery("COMBINED corpus (base + repulls)", new_only=False)
battery("NEW-ONLY slice (base-calibrated thresholds, events after base window)",
        new_only=True)
