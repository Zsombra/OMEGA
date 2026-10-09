"""TPO panel: one read-only forward-logging pull.

WHY THIS EXISTS
    BattleGrid exposes no TPO history and no candle history beyond the most recent
    100 bars (get_coin_candles takes {ticker, interval, limit<=100} and has no start
    time parameter). TPO also feeds zero signal modules, so the platform keeps no
    performance record for it. Every hour not captured is therefore permanently lost.
    This script captures; it does not score. Scoring can be written any day against
    rows already on disk. The data cannot be recovered retroactively.

WHAT IT CAPTURES
    Continuous COLUMN VALUES, never condition booleans. A boolean is one bit and locks
    in a threshold guess on day one; the raw distance/spread lets any threshold be
    computed later, forever.

READ-ONLY BY CONSTRUCTION
    The only tool this script may call is preview_strategy_report, which the vendor
    documents as rendering "without saving or mutating strategy state". The allowlist
    below is enforced, not advisory. Nothing here creates, compiles, applies, binds or
    deploys anything, and nothing here spends capital.

CONVENTIONS INHERITED FROM data/research/2026-08-29-deep-tail-fade/repulls/
    Retry a failed call once. Record the error verbatim. Never fabricate rows.
    Write the raw response bytes before parsing anything.

USAGE
    python scripts/tpo_panel_pull.py [--limit N] [--category CRYPTO] [--timeframe 1h]
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PANEL_DIR = os.path.join(ROOT, "data", "panel")
RAW_DIR = os.path.join(PANEL_DIR, "raw")
JSONL = os.path.join(PANEL_DIR, "tpo_panel.jsonl")

SERVER = "battlegrid-anbu"
ALLOWED_TOOLS = {"preview_strategy_report"}  # enforced below; do not widen

# Columns. Header names are NOT hardcoded anywhere - they are read back off the
# rendered table, so a vendor rename surfaces as a new key rather than a silent
# mismatch. Every entry is a metric x transform combination measured legal 2026-09-10.
COLUMNS = [
    # --- absolute prior levels (needed to reconstruct price; never null) ---
    ("PRIOR_TPO_POC", "value", None),
    ("PRIOR_TPO_VAH", "value", None),
    ("PRIOR_TPO_VAL", "value", None),
    # --- price vs prior levels, signed % (never null) ---
    ("PRIOR_TPO_POC", "distance", None),
    ("PRIOR_TPO_VAH", "distance", None),
    ("PRIOR_TPO_VAL", "distance", None),
    # --- ORIGIN: where the bar opened. The only lawful "came from" read on TPO. ---
    ("PRIOR_TPO_VAL", "spread", "OPEN"),
    ("PRIOR_TPO_VAH", "spread", "OPEN"),
    # --- ENDPOINT: where the bar currently closes ---
    ("PRIOR_TPO_VAL", "spread", "CLOSE"),
    ("PRIOR_TPO_VAH", "spread", "CLOSE"),
    ("PRIOR_TPO_POC", "spread", "CLOSE"),
    # --- EXTREMES: proves the level was actually reached inside the bar ---
    ("PRIOR_TPO_VAL", "spread", "LOW"),
    ("PRIOR_TPO_VAH", "spread", "HIGH"),
    # --- rotation room: prior value-area width. Two never-null legs. ---
    ("PRIOR_TPO_VAH", "spread", "PRIOR_TPO_VAL"),
    # --- developing session. NULL for the first 60 min of each UTC day, and
    #     structurally narrow early in the session - captured precisely so that
    #     time-of-day bias can be MEASURED rather than assumed away. ---
    ("TPO_POC", "spread", "PRIOR_TPO_POC"),
    ("TPO_VAH", "spread", "TPO_VAL"),
    ("TPO_SHAPE", "value", None),
]

NULL_SENTINEL = "—"  # em dash - the platform's rendered null


def build_request(timeframe, category, limit):
    cols = []
    for metric, transform, operand in COLUMNS:
        col = {"metric": metric, "transformId": transform, "timeframe": {"rel": "anchor"}}
        if operand:
            col["inputs"] = [{"metric": operand}]
        cols.append(col)
    return {
        "timeframe": timeframe,
        "coinSelection": {"mode": "ranked", "limit": limit, "category": category},
        "sections": [{
            "kind": "custom",
            "title": "TPO PANEL",
            "benchmarkTicker": None,
            "notes": "read-only forward panel; columns only, no conditions",
            "columns": cols,
        }],
    }


def call(tool, args, timeout=180):
    if tool not in ALLOWED_TOOLS:
        raise RuntimeError("refusing to call non-allowlisted tool: " + tool)
    t0 = time.time()
    p = subprocess.Popen(
        ["cmd", "/c", "npx", "--no-install", "mcporter", "call",
         SERVER + "." + tool, "--output", "json", "--args", "-"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(json.dumps(args).encode(), timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        return None, "TIMEOUT", round(time.time() - t0, 1)
    if p.returncode != 0 or not out.strip():
        msg = (err.decode(errors="replace") or out.decode(errors="replace"))[:800]
        return None, msg, round(time.time() - t0, 1)
    return out.decode(errors="replace"), None, round(time.time() - t0, 1)


def parse_table(text):
    """Pull the markdown table out of a rendered section. Header names come from the
    table itself - nothing about column naming is assumed."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        return None, []
    headers = [h.strip() for h in lines[0].strip("|").split("|")]
    rows = []
    for ln in lines[2:]:  # skip the |---|---| separator row
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return headers, rows


def to_number(cell):
    """Return a float, or None for the null sentinel, or the raw string for a label."""
    if cell is None:
        return None
    s = cell.strip()
    if not s or s == NULL_SENTINEL:
        return None
    cleaned = s.replace("$", "").replace("%", "").replace(",", "").replace("+", "")
    try:
        return float(cleaned)
    except ValueError:
        return s  # a classification label such as p-shape


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--category", default="CRYPTO")
    ap.add_argument("--timeframe", default="1h")
    a = ap.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fstamp = stamp.replace(":", "").replace("-", "")
    req = build_request(a.timeframe, a.category, a.limit)

    raw, err, elapsed = call("preview_strategy_report", req)
    if raw is None:
        print("attempt 1 FAILED (" + str(elapsed) + "s): " + str(err))
        raw, err, elapsed = call("preview_strategy_report", req)
    if raw is None:
        print("attempt 2 FAILED (" + str(elapsed) + "s): " + str(err))
        print("NO ROWS WRITTEN - a failed pull is recorded as a failure, never as data.")
        sys.exit(1)

    raw_path = os.path.join(RAW_DIR, fstamp + ".json")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw)

    data = json.loads(raw)
    sections = data.get("renderedSections") or []
    if not sections:
        print("NO ROWS WRITTEN - response carried no renderedSections.")
        sys.exit(1)

    headers, rows = parse_table(sections[0]["section"]["text"])
    if not rows:
        print("NO ROWS WRITTEN - could not parse a table out of the rendered section.")
        sys.exit(1)

    budget = data.get("budgetUsage", {})
    written = 0
    with open(JSONL, "a", encoding="utf-8") as f:
        for r in rows:
            coin = r.get("coin")
            if not coin:
                continue
            rec = {
                "capturedAt": stamp,
                "coin": coin,
                "timeframe": a.timeframe,
                "category": a.category,
                "cohortLimit": a.limit,
                "rawFile": os.path.basename(raw_path),
            }
            for h in headers:
                if h == "coin":
                    continue
                rec[h] = to_number(r.get(h))
            # Price reconstructed from two verified columns; no CLOSE header assumed.
            #
            # MEASURED CAVEAT (2026-09-10): the ABSOLUTE level columns are rendered
            # with limited significant figures - PUMP's pTpoPOC prints as 0.0044, two
            # sig figs, one ULP of which is 2.3% relative. Cross-checking price three
            # ways (via POC, VAH and VAL) disagreed by >5bps on 14 of 36 coins, and
            # the failures correlate exactly with sig figs (failing median 3, passing
            # median 4) - display rounding, not a parse error. The PERCENT columns are
            # computed server-side and are unaffected.
            #
            # SO: do NOT score forward returns off px_derived. Because pTpoPOC is
            # frozen for the whole UTC session, the level cancels out of a ratio of
            # two dist_pTpoPOC readings on the same coin in the same session:
            #     ret(t1 -> t2) = (1 + d2/100) / (1 + d1/100) - 1
            # That is exact at any price. px_derived is kept only for eyeballing, and
            # carries its own uncertainty so nobody has to rediscover this.
            poc = rec.get("pTpoPOC")
            dist = rec.get("dist_pTpoPOC")
            if isinstance(poc, float) and isinstance(dist, float):
                rec["px_derived"] = round(poc * (1 + dist / 100.0), 8)
                digits = len(repr(poc).replace(".", "").replace("-", "").lstrip("0"))
                rec["levelSigFigs"] = digits
                # half an ULP at the last rendered significant figure
                rec["pxRelUncertainty"] = round(0.5 * 10 ** (-(digits - 1)), 8)
            else:
                rec["px_derived"] = None
                rec["levelSigFigs"] = None
                rec["pxRelUncertainty"] = None
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")
            written += 1

    nulls = {}
    for h in headers:
        if h == "coin":
            continue
        n = sum(1 for r in rows if (r.get(h) or "").strip() == NULL_SENTINEL)
        if n:
            nulls[h] = n

    sc = budget.get("sectionColumns", {})
    lb = budget.get("columnLookback", {})
    tk = budget.get("estimatedTokens", {})
    print("pulled_at   " + stamp + "  (" + str(elapsed) + "s)")
    print("coins       " + str(written) + "  (requested " + str(a.limit)
          + ", category " + a.category + ", tf " + a.timeframe + ")")
    print("columns     " + str(len(headers) - 1))
    print("raw         " + raw_path)
    print("appended    " + JSONL)
    print("budget      columns " + str(sc.get("used")) + "/" + str(sc.get("cap"))
          + "  lookback " + str(lb.get("used")) + "/" + str(lb.get("cap"))
          + "  tokens " + str(tk.get("used")) + "/" + str(tk.get("cap")))
    print("nulls       " + (str(nulls) if nulls else "none"))
    print("headers     " + str([h for h in headers if h != "coin"]))


if __name__ == "__main__":
    main()
