"""Test C: 1h reversion on a 13-coin cross-section, plus threshold and window sweeps
and the VWAP-vs-SMA ablation on the wide set. Offline; candles recovered from the
session transcript."""
import glob
import json
import math
import os
import re

BASE = r"C:\Users\rafae\.claude\projects\C--Users-rafae-Documents-GitHub-OMEGA--claude-worktrees-vwap-strategy-dev-c75dc9"
dec = json.JSONDecoder()
series = {}

for path in glob.glob(os.path.join(BASE, "**", "*.jsonl"), recursive=True):
    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    for m in re.finditer(r'\{\\"candles\\":\[\{|\{"candles":\[\{', text):
        chunk = text[m.start():m.start() + 500000]
        if chunk.startswith('{\\"'):
            end = chunk.find(']}')
            if end == -1:
                continue
            chunk = chunk[:end + 2].replace('\\"', '"')
        try:
            obj, _ = dec.raw_decode(chunk)
        except json.JSONDecodeError:
            continue
        cands = obj.get("candles", [])
        if len(cands) < 50:
            continue
        key = (cands[0]["symbol"], cands[0]["timeframe"])
        rows = sorted({c["timestamp"]: (float(c["close"]), float(c["volume"]))
                       for c in cands}.items())
        rows = [(t, x[0], x[1]) for t, x in rows]
        if key not in series or len(rows) > len(series[key]):
            series[key] = rows

coins_1h = sorted(sym for sym, tf in series if tf == "1h")
print("1h coins:", coins_1h)


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


def revert_test(coins, W=4, pct=0.75, weighted=True):
    hits = tot = 0
    edge = []
    per = {}
    for coin in coins:
        rows = series[(coin, "1h")]
        px = ref(rows, W, weighted)
        devs = sorted(abs((rows[i][1] - px[i]) / px[i])
                      for i in range(len(rows)) if px[i])
        thr = devs[int(pct * len(devs))] if devs else 0
        h = t = 0
        for i in range(W - 1, len(rows) - 1):
            if px[i] is None:
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


print()
print("TEST C - 1h reversion, VWAP4, top-quartile stretch, 13 coins")
tot, p, ci, e, per = revert_test(coins_1h)
print(f"pooled: n={tot}  hit {100*p:.1f}% +/- {100*ci:.1f}pp  edge {e:+.1f} bps/bar")
print("per coin:", "  ".join(f"{c}:{h}/{t}" for c, (h, t) in sorted(per.items())))

old = [c for c in ("BTC", "ETH", "SOL") if (c, "1h") in series]
new = [c for c in coins_1h if c not in old]
t1, p1, c1, e1, _ = revert_test(old)
t2, p2, c2, e2, _ = revert_test(new)
print(f"original 3 coins : n={t1}  hit {100*p1:.1f}% +/- {100*c1:.1f}pp  edge {e1:+.1f}")
print(f"new 10 coins     : n={t2}  hit {100*p2:.1f}% +/- {100*c2:.1f}pp  edge {e2:+.1f}")

print()
print("ablation on the wide set (same events construction, SMA4 reference):")
ts, ps, cs, es, _ = revert_test(coins_1h, weighted=False)
print(f"SMA4 : n={ts}  hit {100*ps:.1f}% +/- {100*cs:.1f}pp  edge {es:+.1f} bps/bar")

print()
print("threshold sweep (VWAP4, 13 coins) - a real stretch effect should deepen:")
for pct in (0.50, 0.75, 0.90):
    t_, p_, c_, e_, _ = revert_test(coins_1h, pct=pct)
    print(f"  >{int(pct*100)}th pctile stretch: n={t_:>4}  hit {100*p_:.1f}% +/- {100*c_:.1f}pp  edge {e_:+.1f}")

print()
print("window sweep (75th pctile, 13 coins) - is W=4 special?")
for W in (3, 4, 6, 8):
    t_, p_, c_, e_, _ = revert_test(coins_1h, W=W)
    print(f"  W={W}: n={t_:>4}  hit {100*p_:.1f}% +/- {100*c_:.1f}pp  edge {e_:+.1f}")
