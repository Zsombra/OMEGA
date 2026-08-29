"""Test A: is the volume-weighting load-bearing? (VWAP4 vs plain SMA4)
Test B: gate agreement - would the in-lane FADE/ALIGN modules have been 'on'
        at the moments the proxy fired?

Offline, zero live calls. Candles recovered from this session's transcript.
Unpinned conventions used and labeled: MFI zones 20/80, Bollinger (20, 2sd),
MA stack = EMA5>EMA13>EMA20, OBV rising = OBV[i] > OBV[i-3].
RSI fade thresholds 35/65 are the thesis's own clause constants (exact).
"""
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
        chunk = text[m.start():m.start() + 400000]
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
        rows = sorted(
            {c["timestamp"]: (float(c["open"]), float(c["high"]), float(c["low"]),
                              float(c["close"]), float(c["volume"]))
             for c in cands}.items())
        rows = [dict(ts=t, o=x[0], h=x[1], l=x[2], c=x[3], v=x[4]) for t, x in rows]
        if key not in series or len(rows) > len(series[key]):
            series[key] = rows

print("series:", sorted((k, len(v)) for k, v in series.items()))
W = 4
COINS = ["BTC", "ETH", "SOL"]
TFS = ["5m", "15m", "1h", "4h"]


def ref_series(rows, weighted):
    out = [None] * len(rows)
    for i in range(W - 1, len(rows)):
        if weighted:
            vv = sum(rows[j]["v"] for j in range(i - W + 1, i + 1))
            out[i] = (sum(rows[j]["c"] * rows[j]["v"] for j in range(i - W + 1, i + 1)) / vv
                      if vv else None)
        else:
            out[i] = sum(rows[j]["c"] for j in range(i - W + 1, i + 1)) / W
    return out


def run_tests(ref_fn_weighted):
    res = {}
    for tf in TFS:
        for mode in ("trend", "revert"):
            hits = tot = 0
            edge = []
            for coin in COINS:
                rows = series.get((coin, tf))
                if not rows:
                    continue
                px = ref_series(rows, ref_fn_weighted)
                devs = sorted(abs((rows[i]["c"] - px[i]) / px[i])
                              for i in range(len(rows)) if px[i])
                thr = devs[int(0.75 * len(devs))] if devs else 0
                for i in range(W - 1, len(rows) - 1):
                    if px[i] is None:
                        continue
                    d = (rows[i]["c"] - px[i]) / px[i]
                    r1 = rows[i + 1]["c"] / rows[i]["c"] - 1
                    if d == 0 or r1 == 0:
                        continue
                    if mode == "trend":
                        s = 1 if d > 0 else -1
                    else:
                        if abs(d) <= thr:
                            continue
                        s = -1 if d > 0 else 1
                    tot += 1
                    if s * r1 > 0:
                        hits += 1
                    edge.append(s * r1 * 10000)
            res[(tf, mode)] = (tot, hits / tot if tot else 0,
                              sum(edge) / len(edge) if edge else 0)
    return res


print()
print("TEST A - ablation: rolling VWAP4 vs plain SMA4")
vw = run_tests(True)
sm = run_tests(False)
print(f"{'tf':<5}{'mode':<9}{'n(vw/sma)':>10}  {'vwap hit%':>9}  {'sma hit%':>9}  "
      f"{'vwap bps':>9}  {'sma bps':>9}")
for tf in TFS:
    for mode in ("trend", "revert"):
        a, b = vw[(tf, mode)], sm[(tf, mode)]
        print(f"{tf:<5}{mode:<9}{a[0]:>4}/{b[0]:<4}  {100*a[1]:>8.1f}%  {100*b[1]:>8.1f}%  "
              f"{a[2]:>+9.1f}  {b[2]:>+9.1f}")

agree = tot_a = 0
for coin in COINS:
    for tf in TFS:
        rows = series.get((coin, tf))
        if not rows:
            continue
        pv = ref_series(rows, True)
        ps = ref_series(rows, False)
        for i in range(W - 1, len(rows)):
            if pv[i] is None or ps[i] is None:
                continue
            dv, ds = rows[i]["c"] - pv[i], rows[i]["c"] - ps[i]
            if dv == 0 or ds == 0:
                continue
            tot_a += 1
            if (dv > 0) == (ds > 0):
                agree += 1
print(f"sign agreement of (close - reference), all series pooled: "
      f"{agree}/{tot_a} = {100*agree/tot_a:.1f}%")


def rsi14(rows):
    cs = [r["c"] for r in rows]
    out = [None] * len(rows)
    if len(cs) < 15:
        return out
    gains = [max(cs[i] - cs[i - 1], 0) for i in range(1, 15)]
    losses = [max(cs[i - 1] - cs[i], 0) for i in range(1, 15)]
    ag, al = sum(gains) / 14, sum(losses) / 14
    out[14] = 100 - 100 / (1 + (ag / al if al else float("inf")))
    for i in range(15, len(cs)):
        ch = cs[i] - cs[i - 1]
        ag = (ag * 13 + max(ch, 0)) / 14
        al = (al * 13 + max(-ch, 0)) / 14
        out[i] = 100 - 100 / (1 + (ag / al if al else float("inf")))
    return out


def mfi14(rows):
    out = [None] * len(rows)
    tps = [(r["h"] + r["l"] + r["c"]) / 3 for r in rows]
    for i in range(14, len(rows)):
        pos = neg = 0.0
        for j in range(i - 13, i + 1):
            flow = tps[j] * rows[j]["v"]
            if tps[j] > tps[j - 1]:
                pos += flow
            elif tps[j] < tps[j - 1]:
                neg += flow
        out[i] = 100 - 100 / (1 + (pos / neg if neg else float("inf")))
    return out


def pctb(rows):
    out = [None] * len(rows)
    cs = [r["c"] for r in rows]
    for i in range(19, len(rows)):
        win = cs[i - 19:i + 1]
        mid = sum(win) / 20
        sd = math.sqrt(sum((x - mid) ** 2 for x in win) / 20)
        if sd == 0:
            continue
        out[i] = (cs[i] - (mid - 2 * sd)) / (4 * sd)
    return out


def ema(rows, n):
    out = [None] * len(rows)
    k = 2 / (n + 1)
    e = rows[0]["c"]
    for i, r in enumerate(rows):
        e = r["c"] * k + e * (1 - k)
        out[i] = e
    return out


def obv(rows):
    out = [0.0] * len(rows)
    for i in range(1, len(rows)):
        step = rows[i]["v"] if rows[i]["c"] > rows[i - 1]["c"] else (
            -rows[i]["v"] if rows[i]["c"] < rows[i - 1]["c"] else 0)
        out[i] = out[i - 1] + step
    return out


print()
print("TEST B1 - gate agreement, 1h FADE (reversion) stretch events, warmup i>=40")
tot = on_rsi = on_mfi = on_bb = on2 = 0
hit_g = n_g = hit_ng = n_ng = 0
for coin in COINS:
    rows = series.get((coin, "1h"))
    if not rows:
        continue
    px = ref_series(rows, True)
    rsi, mfi, bb = rsi14(rows), mfi14(rows), pctb(rows)
    idx = [i for i in range(40, len(rows) - 1) if px[i]]
    devs = sorted(abs((rows[i]["c"] - px[i]) / px[i]) for i in idx)
    thr = devs[int(0.75 * len(devs))] if devs else 0
    for i in idx:
        d = (rows[i]["c"] - px[i]) / px[i]
        if abs(d) <= thr or d == 0:
            continue
        long_side = d < 0
        r = (rsi[i] < 35) if long_side else (rsi[i] > 65)
        mf = (mfi[i] < 20) if long_side else (mfi[i] > 80)
        b = (bb[i] < 0.05) if long_side else (bb[i] > 0.95)
        tot += 1
        on_rsi += r
        on_mfi += mf
        on_bb += b
        k = r + mf + b
        on2 += k >= 2
        r1 = rows[i + 1]["c"] / rows[i]["c"] - 1
        if r1 == 0:
            continue
        hit = (r1 > 0) == long_side
        if k >= 2:
            n_g += 1
            hit_g += hit
        else:
            n_ng += 1
            hit_ng += hit
print(f"stretch events: {tot}")
print(f"  RSI14 fade clause on (35/65, exact thesis constants): {on_rsi}/{tot} = {100*on_rsi/tot:.0f}%")
print(f"  MFI14 zone on (20/80, textbook - not platform-pinned): {on_mfi}/{tot} = {100*on_mfi/tot:.0f}%")
print(f"  Bollinger %B on (0.05/0.95; BB(20,2) textbook):        {on_bb}/{tot} = {100*on_bb/tot:.0f}%")
print(f"  >=2 of 3 modules on (gate-open proxy):                 {on2}/{tot} = {100*on2/tot:.0f}%")
if n_g:
    print(f"  reversion hit rate WHEN gate-open : {hit_g}/{n_g} = {100*hit_g/n_g:.0f}%")
if n_ng:
    print(f"  reversion hit rate when gate-shut : {hit_ng}/{n_ng} = {100*hit_ng/n_ng:.0f}%")

print()
print("TEST B2 - gate agreement, 4h ALIGN (trend) side, warmup i>=60")
tot = on_stack = on_obv = on_both = 0
hit_g = n_g = hit_ng = n_ng = 0
e_g, e_ng = [], []
for coin in COINS:
    rows = series.get((coin, "4h"))
    if not rows:
        continue
    px = ref_series(rows, True)
    e5, e13, e20 = ema(rows, 5), ema(rows, 13), ema(rows, 20)
    ob = obv(rows)
    for i in range(60, len(rows) - 1):
        if px[i] is None:
            continue
        d = (rows[i]["c"] - px[i]) / px[i]
        if d == 0:
            continue
        long_side = d > 0
        stack = (e5[i] > e13[i] > e20[i]) if long_side else (e5[i] < e13[i] < e20[i])
        obv_on = (ob[i] > ob[i - 3]) if long_side else (ob[i] < ob[i - 3])
        tot += 1
        on_stack += stack
        on_obv += obv_on
        on_both += stack and obv_on
        r1 = rows[i + 1]["c"] / rows[i]["c"] - 1
        if r1 == 0:
            continue
        hit = (r1 > 0) == long_side
        ed = (r1 if long_side else -r1) * 10000
        if stack and obv_on:
            n_g += 1
            hit_g += hit
            e_g.append(ed)
        else:
            n_ng += 1
            hit_ng += hit
            e_ng.append(ed)
print(f"proxy-side observations: {tot}")
print(f"  MA stack agrees (EMA5>13>20 approx of MAalign): {on_stack}/{tot} = {100*on_stack/tot:.0f}%")
print(f"  OBV trend agrees (4-bar diff approx):           {on_obv}/{tot} = {100*on_obv/tot:.0f}%")
print(f"  both agree (ALIGN gate-open proxy):             {on_both}/{tot} = {100*on_both/tot:.0f}%")
if n_g:
    print(f"  trend hit rate WHEN gate-open : {hit_g}/{n_g} = {100*hit_g/n_g:.0f}%  edge {sum(e_g)/len(e_g):+.1f} bps/bar")
if n_ng:
    print(f"  trend hit rate when gate-shut : {hit_ng}/{n_ng} = {100*hit_ng/n_ng:.0f}%  edge {sum(e_ng)/len(e_ng):+.1f} bps/bar")
