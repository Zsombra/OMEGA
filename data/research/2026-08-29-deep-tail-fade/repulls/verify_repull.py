"""Integrity check for one out-of-sample re-pull (protocol step; written 2026-09-02).

Run from the repo root, after the 16 raw files are saved:
  python data/research/2026-08-29-deep-tail-fade/repulls/verify_repull.py <YYYY-MM-DD>

Reads repulls/<date>/raw/*.json (each a verbatim 100-row candles array, named
<TICKER>_<tf>.json) and compares every bar against EVERY prior source - the base
corpus plus every earlier repulls/*/candles.json - never the base corpus alone,
which by run 2 no longer overlapped the 100-bar window and would have made the
check vacuous.

FAILS (exit 1) on any of:
  - a file that is not a 100-row list;
  - a timestamp gap or duplicate inside a file;
  - zero overlap with the prior record (more than 100 bars elapsed since the last
    pull: a permanent hole - keep the pull, state the hole in the addendum, and
    never interpolate across it; the battery computes reference windows from
    adjacent rows and would be corrupted at the seam);
  - a PRICE field (open/high/low/close) that differs from the prior record by more
    than PRICE_TOL - a real restatement, not tick noise.

RECORDS but does not fail: every other difference on a previously served bar.
Since 2026-09-02 the platform is known to revise closed bars after serving them
(volume upward, prices by ticks - data/audit/candle_restatement_2026-09-02.json).
Every differing field is written verbatim, old and new, to
data/audit/candle_restatement_<date>.json so nothing is absorbed silently, and a
summary line per series is printed for the addendum.

PRICE_TOL = 0.01 was chosen on 2026-09-02 after observing a maximum price
revision of 0.23% (MELANIA open) across 35 restated price fields.
"""
import glob
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CORPUS)))   # repo root
FIELDS = ("open", "high", "low", "close", "volume")
PRICE_FIELDS = ("open", "high", "low", "close")
PRICE_TOL = 0.01


def main(date):
    rp = os.path.join(HERE, date)
    raw_dir = os.path.join(rp, "raw")
    if not os.path.isdir(raw_dir):
        raise SystemExit(f"no raw directory at {raw_dir}")

    # comparison pool: every prior source, excluding this pull. normpath is REQUIRED on
    # Windows (glob mixes separators) or the exclusion silently fails and the file is
    # compared against itself.
    prev = {}      # key -> ts -> (source_name, row); later sources override earlier ones
    used = []
    for src in [os.path.join(CORPUS, "candles.json")] + sorted(glob.glob(os.path.join(HERE, "*", "candles.json"))):
        if os.path.normpath(os.path.dirname(src)) == os.path.normpath(rp):
            continue
        name = os.path.relpath(src, CORPUS).replace("\\", "/")
        used.append(name)
        for key, rows in json.load(open(src, encoding="utf-8"))["series"].items():
            prev.setdefault(key, {}).update({r["timestamp"]: (name, r) for r in rows})
    print("comparison pool sources:", used)

    problems, diffs, per_series = [], [], {}
    tot_fields = Counter()
    vol_up = vol_dn = 0
    for fn in sorted(os.listdir(raw_dir)):
        if not fn.endswith(".json"):
            continue
        key = fn[:-5]
        sym, tf = key.rsplit("_", 1)
        rows = json.load(open(os.path.join(raw_dir, fn), encoding="utf-8"))
        if not isinstance(rows, list) or len(rows) != 100:
            problems.append(f"{fn}: expected a 100-row list")
            continue
        ts = [datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")) for r in rows]
        step = timedelta(hours={"1h": 1, "4h": 4}.get(tf, 1))
        gaps = sum(1 for a, b in zip(ts, ts[1:]) if b - a != step)
        dupes = len(ts) - len(set(ts))
        pool = prev.get(key, {})
        overlap = [r for r in rows if r["timestamp"] in pool]
        new = len(rows) - len(overlap)
        fc, first, max_rel = Counter(), None, {f: 0.0 for f in FIELDS}
        for r in overlap:
            name, old = pool[r["timestamp"]]
            d = {f: {"old": old[f], "new": r[f]} for f in FIELDS if old[f] != r[f]}
            if not d:
                continue
            first = first or r["timestamp"]
            for f in d:
                fc[f] += 1
                tot_fields[f] += 1
                o, n = float(old[f]), float(r[f])
                rel = abs(n - o) / abs(o) if o else float("inf")
                max_rel[f] = max(max_rel[f], rel)
                if f == "volume":
                    if n > o:
                        vol_up += 1
                    else:
                        vol_dn += 1
                elif rel > PRICE_TOL:
                    problems.append(f"{fn}: PRICE RESTATEMENT {f} {old[f]} -> {r[f]} at {r['timestamp']} ({rel:.2%} > {PRICE_TOL:.0%})")
            diffs.append({"series": key, "timestamp": r["timestamp"], "previously_served_by": name, "fields": d})
        matched_before = sum(1 for r in overlap if first and r["timestamp"] < first)
        price_n = sum(fc[f] for f in PRICE_FIELDS)
        print(f"{key:>11}  gaps={gaps} dupes={dupes} overlap={len(overlap):>2} new={new:>2}  "
              f"restated: price_fields={price_n} (max {max(max_rel[f] for f in PRICE_FIELDS):.2e})  "
              f"volume={fc['volume']} (max {max_rel['volume']:.2e})  first_changed={first}")
        per_series[key] = {"overlap_bars": len(overlap), "new_bars": new, "gaps": gaps, "dupes": dupes,
                           "bars_changed": sum(1 for x in diffs if x["series"] == key),
                           "first_changed_bar": first, "bars_matched_before_first_change": matched_before,
                           "fields_changed": dict(fc), "max_relative_change": {f: v for f, v in max_rel.items() if v}}
        if gaps or dupes:
            problems.append(f"{fn}: gaps={gaps} dupes={dupes}")
        if not overlap:
            problems.append(f"{fn}: ZERO overlap with prior data - a permanent hole in the record")

    print()
    print(f"restated fields total: {dict(tot_fields)}  (volume up={vol_up} down={vol_dn});"
          f" bars changed: {len(diffs)}")
    if diffs:
        out = os.path.join(ROOT, "data", "audit", f"candle_restatement_{date}.json")
        record = {
            "_what": (f"Re-pull {date}: every field on which the candle endpoint now disagrees with what it "
                      f"served earlier (old = the latest prior source that held the bar; new = this pull). "
                      f"Written by verify_repull.py; nothing here was interpreted."),
            "when": date,
            "comparison_pool_sources": used,
            "summary": {"bars_changed": len(diffs), "fields_changed": dict(tot_fields),
                        "volume_direction": {"up": vol_up, "down": vol_dn}, "price_tolerance": PRICE_TOL,
                        "price_tolerance_breached": [p for p in problems if "PRICE RESTATEMENT" in p]},
            "per_series": per_series,
            "differences_verbatim": diffs,
        }
        if os.path.exists(out):
            print(f"NOTE: {out} already exists - not overwriting; writing .rerun.json beside it")
            out = out[:-5] + ".rerun.json"
        json.dump(record, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print("restatement record written:", os.path.relpath(out, ROOT).replace("\\", "/"))
    print("problems:", problems or "none")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
