"""Preview every TPO suite payload against the live connector. READ-ONLY.

WHY THIS EXISTS SEPARATELY FROM tpo_suite_build.py
    Offline validation is the repo's MODEL of the contract. The server is the
    authority. A payload that passes validate_report + validate_conditions can still
    be refused - the clock rules, the exit rules and the operand rules are all
    server-side. This script asks the server.

    preview_strategy_report renders "without saving or mutating strategy state". It is
    the only tool this script may call, and the allowlist is enforced.

USAGE
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", default="BTC,ETH,SOL,DOGE,PEPE,HYPE")
    a = ap.parse_args()
    coins = [x.strip().upper() for x in a.coins.split(",") if x.strip()]
    os.makedirs(RAW, exist_ok=True)

    man = json.load(open(os.path.join(SUITE, "_manifest.json"), encoding="utf-8"))
    print("previewing %d payloads against %d coins\n" % (len(man["suite"]), len(coins)))
    print("%-4s %-22s %8s %7s  %-28s %s" % ("id", "name", "verdict", "clocks", "fired (of %d coins)" % len(coins), "result"))
    print("-" * 108)

    failures = []
    for entry in man["suite"]:
        payload = json.load(open(os.path.join(SUITE, entry["file"]), encoding="utf-8"))
        req = {
            "timeframe": payload["anchor"],
            "coinSelection": {"mode": "explicit", "tickers": coins},
            "sections": payload["sections"],
            "conditions": payload["conditions"],
        }
        raw, err, el = call("preview_strategy_report", req)
        if raw is None:
            print("%-4s %-22s %8s %7s  %-28s REFUSED (%ss)" % (
                entry["id"], entry["name"], "-", "-", "-", el))
            # print the refusal verbatim - it is the most valuable output there is
            for line in err.splitlines():
                if line.strip():
                    print("        | " + line.strip()[:150])
            failures.append((entry["id"], err))
            continue

        with open(os.path.join(RAW, entry["id"] + ".json"), "w", encoding="utf-8") as f:
            f.write(raw)
        d = json.loads(raw)
        tally = d.get("conditionVerdictTally", {})
        outcomes = d.get("conditionOutcomes", [])

        fired = {}
        closeclocks = 0
        for o in outcomes:
            for c in o.get("outcomes", []):
                if c.get("outcome") == "TRUE":
                    fired[c["conditionKey"]] = fired.get(c["conditionKey"], 0) + 1
                if c.get("closeClock"):
                    closeclocks += 1
        top = sorted(fired.items(), key=lambda kv: -kv[1])[:2]
        firedstr = ", ".join("%s:%d" % (k, v) for k, v in top) or "none"
        vstr = "U%d D%d N%d" % (tally.get("UP", 0), tally.get("DOWN", 0), tally.get("NEITHER", 0))
        print("%-4s %-22s %8s %7d  %-28s OK (%ss)" % (
            entry["id"], entry["name"], vstr, closeclocks, firedstr[:28], el))

    print("-" * 108)
    if failures:
        print("REFUSED: %s" % ", ".join(f[0] for f in failures))
        print("A refused payload must not be compiled. Fix the refusal first.")
        return 1
    print("all %d payloads accepted and evaluated by the server" % len(man["suite"]))
    print("raw -> %s" % RAW)
    return 0


if __name__ == "__main__":
    sys.exit(main())
