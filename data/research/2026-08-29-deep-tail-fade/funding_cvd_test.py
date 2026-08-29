"""Do the mean-reversion preset's confirmation legs earn their weights?

FUNDING leg (real data): fade is 'paid' when funding sign opposes the fade side
(long fade with rate<0, short fade with rate>0) - exactly the clause _clause_for
falls back to under FADE.
CVD-analog leg (OBV 4-bar trend): flow turning with the fade - an ANALOG for
'CVD_trend rising', since true aggressor CVD history is unreachable.

Events: 1h stretch events on BTC/ETH/SOL (the majors, where the effect lives),
at 75th and 90th percentile stretch. Offline except the already-fetched funding file.
"""
import glob
import json
import math
import os
import re
from datetime import datetime, timezone

here = os.path.dirname(os.path.abspath(__file__))
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

funding = json.load(open(os.path.join(here, "funding_history.json"), encoding="utf-8"))
frate = {}
for coin, rows in funding.items():
    frate[coin] = {}
    for x in rows:
        hour = datetime.fromtimestamp(x["time"] / 1000, tz=timezone.utc).replace(
            minute=0, second=0, microsecond=0)
        frate[coin][hour.strftime("%Y-%m-%dT%H:00:00.000Z")] = x["rate"]

W = 4
COINS = ["BTC", "ETH", "SOL"]


def vwap4(rows):
    out = [None] * len(rows)
    for i in range(W - 1, len(rows)):
        vv = sum(rows[j][2] for j in range(i - W + 1, i + 1))
        out[i] = (sum(rows[j][1] * rows[j][2] for j in range(i - W + 1, i + 1)) / vv
                  if vv else None)
    return out


def obv(rows):
    out = [0.0] * len(rows)
    for i in range(1, len(rows)):
        d = rows[i][1] - rows[i - 1][1]
        out[i] = out[i - 1] + (rows[i][2] if d > 0 else (-rows[i][2] if d < 0 else 0))
    return out


def stats(events):
    n = len(events)
    if n == 0:
        return "n=0"
    hits = sum(1 for h, _ in events if h)
    p = hits / n
    ci = 1.96 * math.sqrt(p * (1 - p) / n)
    e = sum(x for _, x in events) / n
    return f"n={n:>3}  hit {100*p:5.1f}% +/- {100*ci:4.1f}pp  edge {e:+7.1f} bps"


for pct in (0.75, 0.90):
    groups = {"all": [], "funding aligned": [], "funding not": [],
              "flow aligned": [], "flow not": [], "both legs on": [], "either off": []}
    fund_missing = 0
    for coin in COINS:
        rows = series[(coin, "1h")]
        px = vwap4(rows)
        ob = obv(rows)
        devs = sorted(abs((rows[i][1] - px[i]) / px[i])
                      for i in range(len(rows)) if px[i])
        thr = devs[int(pct * len(devs))]
        for i in range(W - 1, len(rows) - 1):
            if px[i] is None:
                continue
            d = (rows[i][1] - px[i]) / px[i]
            if d == 0 or abs(d) <= thr:
                continue
            long_side = d < 0
            r1 = rows[i + 1][1] / rows[i][1] - 1
            if r1 == 0:
                continue
            hit = (r1 > 0) == long_side
            ebps = (r1 if long_side else -r1) * 10000
            ev = (hit, ebps)
            groups["all"].append(ev)
            rate = frate.get(coin, {}).get(rows[i][0])
            if rate is None:
                fund_missing += 1
                f_ok = None
            else:
                f_ok = (rate < 0) if long_side else (rate > 0)
            flow_ok = (ob[i] > ob[i - 3]) if long_side else (ob[i] < ob[i - 3])
            if f_ok is True:
                groups["funding aligned"].append(ev)
            elif f_ok is False:
                groups["funding not"].append(ev)
            groups["flow aligned" if flow_ok else "flow not"].append(ev)
            if f_ok is True and flow_ok:
                groups["both legs on"].append(ev)
            elif f_ok is not None:
                groups["either off"].append(ev)
    print(f"--- stretch > {int(pct*100)}th percentile (majors, 1h) ---")
    for k in ("all", "funding aligned", "funding not", "flow aligned", "flow not",
              "both legs on", "either off"):
        print(f"  {k:<16} {stats(groups[k])}")
    if fund_missing:
        print(f"  (funding lookup missing on {fund_missing} events)")
    print()

pos = {c: sum(1 for x in funding[c] if x["rate"] > 0) / len(funding[c]) for c in funding}
print("funding sign base rates over the window (share of hours positive):",
      {c: f"{100*v:.0f}%" for c, v in pos.items()})
