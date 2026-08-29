"""Measure the rolling-VWAP proxy's trend and reversion reads per anchor.

Data: the 12 get_coin_candles pulls from this session (BTC/ETH/SOL x 5m/15m/1h/4h),
recovered from the session transcript so nothing is retyped by hand.
Proxy: sum(close*vol)/sum(vol) over the last 4 CLOSED bars - the exact Path B formula.
"""
import json
import glob
import math
import os
import re

BASE = r"C:\Users\rafae\.claude\projects\C--Users-rafae-Documents-GitHub-OMEGA--claude-worktrees-vwap-strategy-dev-c75dc9"
dec = json.JSONDecoder()
series = {}  # (symbol, tf) -> list of (ts, close, vol)

for path in glob.glob(os.path.join(BASE, "**", "*.jsonl"), recursive=True):
    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    for m in re.finditer(r'\{\\"candles\\":\[\{|\{"candles":\[\{', text):
        start = m.start()
        chunk = text[start:start + 400000]
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
        sym = cands[0].get("symbol")
        tf = cands[0].get("timeframe")
        rows = [(c["timestamp"], float(c["close"]), float(c["volume"])) for c in cands]
        rows.sort()
        key = (sym, tf)
        if key not in series or len(rows) > len(series[key]):
            series[key] = rows

print("recovered series:", sorted((k, len(v)) for k, v in series.items()))

W = 4
TFS = ["5m", "15m", "1h", "4h"]
COINS = ["BTC", "ETH", "SOL"]


def proxy_series(rows):
    out = [None] * len(rows)
    for i in range(W - 1, len(rows)):
        pv = sum(rows[j][1] * rows[j][2] for j in range(i - W + 1, i + 1))
        vv = sum(rows[j][2] for j in range(i - W + 1, i + 1))
        out[i] = pv / vv if vv else None
    return out


def ci(p, n):
    if n == 0:
        return 0.0
    return 1.96 * math.sqrt(p * (1 - p) / n)


print()
print(f"{'tf':<5}{'read':<11}{'n':>5}  {'hit%':>6}  {'95% CI':>12}  {'edge bps/bar':>13}")
for tf in TFS:
    for mode in ("trend", "revert"):
        hits = tot = 0
        edge = []
        for coin in COINS:
            rows = series.get((coin, tf))
            if not rows:
                continue
            px = proxy_series(rows)
            closes = [r[1] for r in rows]
            devs = [abs((closes[i] - px[i]) / px[i]) for i in range(len(rows)) if px[i]]
            devs.sort()
            thr = devs[int(0.75 * len(devs))] if devs else 0
            for i in range(W - 1, len(rows) - 1):
                if px[i] is None:
                    continue
                d = (closes[i] - px[i]) / px[i]
                if d == 0:
                    continue
                r1 = closes[i + 1] / closes[i] - 1
                if r1 == 0:
                    continue
                if mode == "trend":
                    s = 1 if d > 0 else -1
                else:
                    if abs(d) <= thr:
                        continue
                    s = -1 if d > 0 else 1  # bet on snap-back toward the proxy
                tot += 1
                if s * r1 > 0:
                    hits += 1
                edge.append(s * r1 * 10000)
        p = hits / tot if tot else 0
        e = sum(edge) / len(edge) if edge else 0
        print(f"{tf:<5}{mode:<11}{tot:>5}  {100*p:>5.1f}%  ±{100*ci(p,tot):>4.1f}pp      {e:>+8.1f}")

print()
print("4-bar horizon (overlapping, weaker independence):")
print(f"{'tf':<5}{'read':<11}{'n':>5}  {'hit%':>6}  {'edge bps/4bar':>14}")
for tf in TFS:
    for mode in ("trend", "revert"):
        hits = tot = 0
        edge = []
        for coin in COINS:
            rows = series.get((coin, tf))
            if not rows:
                continue
            px = proxy_series(rows)
            closes = [r[1] for r in rows]
            devs = [abs((closes[i] - px[i]) / px[i]) for i in range(len(rows)) if px[i]]
            devs.sort()
            thr = devs[int(0.75 * len(devs))] if devs else 0
            for i in range(W - 1, len(rows) - 4):
                if px[i] is None:
                    continue
                d = (closes[i] - px[i]) / px[i]
                if d == 0:
                    continue
                r4 = closes[i + 4] / closes[i] - 1
                if r4 == 0:
                    continue
                if mode == "trend":
                    s = 1 if d > 0 else -1
                else:
                    if abs(d) <= thr:
                        continue
                    s = -1 if d > 0 else 1
                tot += 1
                if s * r4 > 0:
                    hits += 1
                edge.append(s * r4 * 10000)
        p = hits / tot if tot else 0
        e = sum(edge) / len(edge) if edge else 0
        print(f"{tf:<5}{mode:<11}{tot:>5}  {100*p:>5.1f}%  {e:>+9.1f}")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "candles_by_tf.json")
json.dump({f"{k[0]}_{k[1]}": v for k, v in series.items()}, open(out, "w"), indent=0)
print()
print("raw series saved:", out)
