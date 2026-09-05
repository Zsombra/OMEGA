"""Assemble one re-pull's candles.json from its verbatim raw files, then extend the
funding record (protocol step; written 2026-09-02 from the steps dry-run in runs 1-2).

Run from the repo root, AFTER verify_repull.py has passed (or its problems have been
recorded and accepted):
  python data/research/2026-08-29-deep-tail-fade/repulls/assemble_repull.py <YYYY-MM-DD>

- candles.json: {"_what": ..., "series": {"<TICKER>_<tf>": [<candle objects verbatim>]}} -
  the shape analyze_repull.py globs; a correctly named folder is picked up with no code change.
- funding_raw.json: Hyperliquid public fundingHistory rows for BTC/ETH/SOL, VERBATIM,
  continuing from the latest row held ANYWHERE in the record (the base
  funding_history.json plus every earlier repulls/*/funding_raw.json - the base alone
  ends 2026-08-29 and would re-pull hours already saved). Prints the sign mix: the
  FUNDING-leg confound resolves only in a window containing negative-funding hours.
"""
import glob
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.dirname(HERE)
COINS = ("BTC", "ETH", "SOL")


def assemble_candles(rp, date):
    raw_dir = os.path.join(rp, "raw")
    series = {fn[:-5]: json.load(open(os.path.join(raw_dir, fn), encoding="utf-8"))
              for fn in sorted(os.listdir(raw_dir))
              if fn.endswith(".json") and not fn.startswith("_")}
    # Optional, from run 4 on: raw/_pulled_at.json {"start": "<ISO Z>", "end": "<ISO Z>"} written
    # by the session around the 16 calls. analyze_repull.py SETTLED uses "end" as the exact
    # pull time when present; earlier runs fall back to the last-served-bar proxy.
    marker = os.path.join(raw_dir, "_pulled_at.json")
    pulled_at = json.load(open(marker, encoding="utf-8")) if os.path.exists(marker) else None
    if len(series) != 16:
        print(f"WARNING: {len(series)} series, expected 16 (13 x 1h + 3 x 4h) - a delisted ticker "
              f"must be recorded in the addendum, never substituted")
    out = os.path.join(rp, "candles.json")
    if os.path.exists(out):
        raise SystemExit(f"{out} already exists - refusing to overwrite an irreplaceable file")
    json.dump({"_what": f"Out-of-sample re-pull {date} per the re-pull protocol. Read-only "
                        "get_coin_candles, closed bars, 100-bar cap; 13-coin fixed 1h set + "
                        "BTC/ETH/SOL 4h. Checked against every prior source by verify_repull.py "
                        "(the platform revises served bars - see data/audit/candle_restatement_*.json). "
                        "IRREPLACEABLE once the window scrolls.",
               "pulledAt": pulled_at,
               "series": series},
              open(out, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
    print("candles.json:", os.path.getsize(out), "bytes,", len(series), "series")


def last_funding_times():
    last = {c: 0 for c in COINS}
    base = json.load(open(os.path.join(CORPUS, "funding_history.json"), encoding="utf-8"))
    for c in COINS:
        last[c] = max(last[c], max(r["time"] for r in base[c]))
    for p in sorted(glob.glob(os.path.join(HERE, "*", "funding_raw.json"))):
        coins = json.load(open(p, encoding="utf-8"))["coins"]
        for c in COINS:
            if coins.get(c):
                last[c] = max(last[c], max(r["time"] for r in coins[c]))
    return last


def fetch_funding(rp):
    out_path = os.path.join(rp, "funding_raw.json")
    if os.path.exists(out_path):
        raise SystemExit(f"{out_path} already exists - refusing to overwrite")
    last = last_funding_times()
    print("continuing funding from:", last)
    out = {}
    for coin in COINS:
        start, rows, seen = last[coin] + 1, [], set()
        for _ in range(40):
            req = urllib.request.Request(
                "https://api.hyperliquid.xyz/info",
                data=json.dumps({"type": "fundingHistory", "coin": coin, "startTime": start}).encode(),
                headers={"Content-Type": "application/json"})
            page = json.loads(urllib.request.urlopen(req, timeout=30).read())
            new = [r for r in page if r["time"] not in seen]
            if not new:
                break
            rows += new
            seen |= {r["time"] for r in new}
            start = max(r["time"] for r in new) + 1
            if len(page) < 20:
                break
        rows.sort(key=lambda r: r["time"])
        out[coin] = rows
        rates = [float(r["fundingRate"]) for r in rows]
        neg = sum(1 for x in rates if x < 0)
        print(f"{coin}: {len(rows)} new hours, negative {neg}/{len(rates)}"
              + (f", min {min(rates)} max {max(rates)}" if rates else ""))
    json.dump({"_what": "Hyperliquid public fundingHistory rows, VERBATIM, continuing the prior funding record.",
               "coins": out},
              open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    date = sys.argv[1]
    rp = os.path.join(HERE, date)
    if not os.path.isdir(os.path.join(rp, "raw")):
        raise SystemExit(f"no raw directory at {rp}/raw")
    assemble_candles(rp, date)
    fetch_funding(rp)
