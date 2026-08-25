"""Which convention does BattleGrid implement for ADX, CCI and Stochastic?

Most indicators have one definition. These three do not:

  ADX   Wilder's own smoothing, or a plain moving average of DX?
  CCI   the 0.015 constant with MEAN ABSOLUTE DEVIATION, or with standard deviation?
  %K    (14,3,3) "slow" - raw %K smoothed once, then %D smoothed again - or "fast",
        where %K is raw and only %D is smoothed?

Verifying that BattleGrid's SMA is a mean proves little; everyone's SMA is a mean. These
three are where two reasonable implementations disagree by enough to flip a gate, so
knowing WHICH one ships is real information rather than a formality.

Method: render each metric at `offset: 1` so it reads the last CLOSED bar (these metrics
reject `bars`, and an offset of 1 or more is the documented escape from the forming bar).
Identify that exact bar by rendering a closed CLOSE trajectory beside it, then recompute
from the Hyperliquid tape up to and including it.

    python -m scripts.verify_conventions
"""
from __future__ import annotations

# Rendered 2026-08-25, BTC 1h, offset=1. The closed trajectory beside these read
# 79170 / 79289 / 79108, which pins the anchor bar to 2026-08-25T11:00Z.
RENDERED = {"ADX": 24.9, "CCI": -39.3, "K": 22.0, "D": 31.0}
ANCHOR_CLOSE = 79108.0
PRECISION = {"ADX": 0.05, "CCI": 0.05, "K": 0.5, "D": 0.5}   # rendered dp


def wilder(seq, n):
    """Wilder's smoothing: seed on the sum of the first n, then prev - prev/n + x."""
    out, acc = [], sum(seq[:n])
    out.append(acc)
    for x in seq[n:]:
        acc = acc - acc / n + x
        out.append(acc)
    return out


def sma_series(seq, n):
    return [sum(seq[i - n + 1:i + 1]) / n for i in range(n - 1, len(seq))]


# --- ADX --------------------------------------------------------------------

def adx(h, l, c, n=14, smoothing="wilder"):
    tr, pdm, ndm = [], [], []
    for i in range(1, len(c)):
        tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
        up, dn = h[i] - h[i - 1], l[i - 1] - l[i]
        pdm.append(up if (up > dn and up > 0) else 0.0)
        ndm.append(dn if (dn > up and dn > 0) else 0.0)

    if smoothing == "wilder":
        str_, spd, snd = wilder(tr, n), wilder(pdm, n), wilder(ndm, n)
    else:
        str_, spd, snd = sma_series(tr, n), sma_series(pdm, n), sma_series(ndm, n)

    dx = []
    for t, p, m in zip(str_, spd, snd):
        if t == 0:
            dx.append(0.0); continue
        pdi, ndi = 100 * p / t, 100 * m / t
        dx.append(0.0 if pdi + ndi == 0 else 100 * abs(pdi - ndi) / (pdi + ndi))

    if smoothing == "wilder":
        a = sum(dx[:n]) / n
        for x in dx[n:]:
            a = (a * (n - 1) + x) / n
        return a
    return sma_series(dx, n)[-1]


# --- CCI --------------------------------------------------------------------

def cci(h, l, c, n=20, const=0.015, dev="mad"):
    tp = [(hi + lo + cl) / 3 for hi, lo, cl in zip(h, l, c)]
    win = tp[-n:]
    mean = sum(win) / n
    if dev == "mad":
        d = sum(abs(x - mean) for x in win) / n
    else:                                     # population standard deviation
        d = (sum((x - mean) ** 2 for x in win) / n) ** 0.5
    return 0.0 if d == 0 else (tp[-1] - mean) / (const * d)


# --- Stochastic -------------------------------------------------------------

def stoch(h, l, c, n=14, k_smooth=3, d_smooth=3):
    raw = []
    for i in range(n - 1, len(c)):
        hh, ll = max(h[i - n + 1:i + 1]), min(l[i - n + 1:i + 1])
        raw.append(50.0 if hh == ll else 100 * (c[i] - ll) / (hh - ll))
    k = raw if k_smooth == 1 else sma_series(raw, k_smooth)
    d = sma_series(k, d_smooth)
    return k[-1], d[-1]


def main() -> int:
    import json
    from pathlib import Path
    p = Path("data/audit/candles_btc_1h_conventions.json")
    if not p.exists():
        print(f"missing {p} - see the module docstring for how it was captured")
        return 1
    bars = json.loads(p.read_text(encoding="utf-8"))["bars"]
    h = [b["h"] for b in bars]; l = [b["l"] for b in bars]; c = [b["c"] for b in bars]
    assert c[-1] == ANCHOR_CLOSE, f"tape does not end on the anchor bar: {c[-1]}"
    print(f"{len(c)} bars, ending on the rendered closed bar (close {c[-1]:,.0f})\n")

    print(f"{'indicator / convention':<44} {'computed':>10} {'rendered':>10}  verdict")
    rows = [
        ("ADX  Wilder smoothing (standard)", adx(h, l, c, 14, "wilder"), "ADX"),
        ("ADX  plain moving average of DX", adx(h, l, c, 14, "sma"), "ADX"),
        ("CCI  0.015 x mean absolute deviation", cci(h, l, c, 20, 0.015, "mad"), "CCI"),
        ("CCI  0.015 x standard deviation", cci(h, l, c, 20, 0.015, "std"), "CCI"),
    ]
    for label, got, key in rows:
        ok = abs(got - RENDERED[key]) <= PRECISION[key]
        print(f"  {label:<42} {got:>10.2f} {RENDERED[key]:>10.2f}  {'MATCH' if ok else '-'}")

    for kk, dd, name in ((3, 3, "slow (14,3,3) - as the header declares"),
                         (1, 3, "fast (14,1,3)"),
                         (3, 1, "(14,3,1)")):
        k, d = stoch(h, l, c, 14, kk, dd)
        ok_k = abs(k - RENDERED["K"]) <= PRECISION["K"]
        ok_d = abs(d - RENDERED["D"]) <= PRECISION["D"]
        print(f"  %K   {name:<37} {k:>10.2f} {RENDERED['K']:>10.2f}  "
              f"{'MATCH' if ok_k else '-'}")
        print(f"  %D   {name:<37} {d:>10.2f} {RENDERED['D']:>10.2f}  "
              f"{'MATCH' if ok_d else '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
