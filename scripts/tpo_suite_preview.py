"""Preview every TPO suite payload against the live connector. READ-ONLY.

WHY THIS EXISTS SEPARATELY FROM tpo_suite_build.py
    Offline validation is the repo's MODEL of the contract. The server is the
    authority. A payload that passes validate_report + validate_conditions can still
    be refused - the per-column conditionHold ceilings, the verdict read rules and
    the operand rules are all server-side. This script asks the server.

    preview_strategy_report renders "without saving or mutating strategy state". It is
    the only tool this script may call, and the allowlist is enforced. It judges the
    report and the conditions with the v84/v88 grammar - NOT signal rules, gates or
    dials; only a stage does, and a stage is a write (plan 2026-10-06).

PORTED 2026-10-10 to the v85+ preview body. The builder now writes <id>.preview.json, the
    exact preview_strategy_report arguments {coinSelection, source: {kind: FIELDS, timeframe,
    sections, conditions, marketReadText}}; this script sends that file verbatim, swapping
    only the tickers when --coins is given. The pre-v85 flat {timeframe, coinSelection,
    sections, conditions} body it used to assemble is refused since 85.0.0. Condition
    evidence is read in its v84 shape: each clause entry carries `hold`, `counts
    {trueCount, total, unresolvedCount}` and `decidedBar`; the `closeClock` this script
    once counted no longer exists (README "Contract history - v84").

USAGE
    python scripts/tpo_suite_build.py                   # first: writes out/tpo_suite/
    python scripts/tpo_suite_preview.py [--coins BTC,ETH,SOL,DOGE]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE = os.path.join(ROOT, "out", "tpo_suite")
RAW = os.path.join(SUITE, "preview_raw")

SERVER = "battlegrid-anbu"
ALLOWED_TOOLS = {"preview_strategy_report"}


def call(tool, args, timeout=240):
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
        msg = (err.decode(errors="replace") or out.decode(errors="replace"))
        return None, msg.strip()[:900], round(time.time() - t0, 1)
    return out.decode(errors="replace"), None, round(time.time() - t0, 1)


def preview_request(entry: dict, coins: list[str] | None) -> dict:
    """The builder's <id>.preview.json verbatim; only the explicit ticker list is swapped
    when --coins names one. Nothing else is assembled here - the body is the builder's."""
    req = json.load(open(os.path.join(SUITE, entry["preview"]), encoding="utf-8"))
    if coins:
        req = dict(req, coinSelection={"mode": "explicit", "tickers": coins})
    return req


def tally(d: dict) -> tuple[str, int, str, int]:
    """(verdict tally, clause reads held above one bar, top fired conditions, missing columns)
    from a v84+ preview response."""
    verdicts = d.get("conditionVerdictTally", {}) or {}
    fired: dict[str, int] = {}
    held = 0
    for o in d.get("conditionOutcomes", []) or []:
        for c in o.get("outcomes", []) or []:
            if c.get("outcome") == "TRUE":
                fired[c["conditionKey"]] = fired.get(c["conditionKey"], 0) + 1
            for ev in c.get("evidence", []) or []:
                h = ev.get("hold") or {}
                if h.get("of", 1) > 1:
                    held += 1
    top = sorted(fired.items(), key=lambda kv: -kv[1])[:2]
    firedstr = ", ".join("%s:%d" % (k, v) for k, v in top) or "none"
    vstr = "U%d D%d N%d" % (verdicts.get("UP", 0), verdicts.get("DOWN", 0), verdicts.get("NEITHER", 0))
    return vstr, held, firedstr, len(d.get("missingConditionColumns", []) or [])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="",
                    help="explicit tickers to preview on; default: the builder's COINS as written in <id>.preview.json")
    a = ap.parse_args(argv)
    coins = [x.strip().upper() for x in a.coins.split(",") if x.strip()] or None
    os.makedirs(RAW, exist_ok=True)

    man = json.load(open(os.path.join(SUITE, "_manifest.json"), encoding="utf-8"))
    n_coins = len(coins or man["coinSelection"]["tickers"])
    print("previewing %d payloads against %d coins\n" % (len(man["suite"]), n_coins))
    print("%-4s %-22s %8s %5s %7s  %-28s %s" % ("id", "name", "verdict", "held", "missing",
                                                  "fired (of %d coins)" % n_coins, "result"))
    print("-" * 112)

    failures = []
    for entry in man["suite"]:
        if entry["errors"]:
            print("%-4s %-22s %8s %5s %7s  %-28s SKIPPED (offline errors)" % (
                entry["id"], entry["name"], "-", "-", "-", "-"))
            continue
        req = preview_request(entry, coins)
        raw, err, el = call("preview_strategy_report", req)
        if raw is None:
            print("%-4s %-22s %8s %5s %7s  %-28s REFUSED (%ss)" % (
                entry["id"], entry["name"], "-", "-", "-", "-", el))
            # print the refusal verbatim - it is the most valuable output there is
            for line in err.splitlines():
                if line.strip():
                    print("        | " + line.strip()[:150])
            failures.append((entry["id"], err))
            continue

        with open(os.path.join(RAW, entry["id"] + ".json"), "w", encoding="utf-8") as f:
            f.write(raw)
        vstr, held, firedstr, missing = tally(json.loads(raw))
        print("%-4s %-22s %8s %5d %7d  %-28s OK (%ss)" % (
            entry["id"], entry["name"], vstr, held, missing, firedstr[:28], el))

    print("-" * 112)
    if failures:
        print("REFUSED: %s" % ", ".join(f[0] for f in failures))
        print("A refused payload must not be staged. Fix the refusal first.")
        return 1
    print("all %d payloads accepted and evaluated by the server" % len(man["suite"]))
    print("raw -> %s" % RAW)
    return 0


if __name__ == "__main__":
    sys.exit(main())
