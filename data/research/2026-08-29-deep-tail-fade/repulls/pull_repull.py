"""Re-pull fetcher: 16 get_coin_candles calls via the mcporter CLI, saved verbatim.

Usage: python pull_repull.py <YYYY-MM-DD>   (prescribed from run 5 on; see the protocol).

Method note (adopted run 5, 2026-09-09): runs 1-4 had the agent transcribe each MCP response into a file
by hand. This run fetches the SAME tool on the SAME server/account through the mcporter CLI
and writes the bytes directly, which removes transcription risk entirely. Equality was
verified for BTC_1h against the connector response held in the session context before this
script was written (same 100 bars, same first/last OHLCV). Verify equality once per run.

Retry a failed call once, record the error verbatim, never fabricate rows.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = sys.argv[1] if len(sys.argv) > 1 else None
if not RUN:
    sys.exit("usage: python pull_repull.py <YYYY-MM-DD>   (the run folder; create it first)")
RAW = os.path.join(HERE, RUN, "raw")
if not os.path.isdir(RAW):
    sys.exit(f"{RAW} does not exist - create it and write raw/_pulled_at.json with the start time first")
COINS_1H = ["BTC", "ETH", "SOL", "PEPE", "POPCAT", "MET", "MELANIA", "TRUMP",
            "HYPE", "MOODENG", "AIXBT", "CAKE", "LDO"]
COINS_4H = ["BTC", "ETH", "SOL"]


def call(tool, args, timeout=120):
    t0 = time.time()
    p = subprocess.Popen(
        ["cmd", "/c", "npx", "mcporter", "call", f"battlegrid-anbu.{tool}",
         "--output", "json", "--args", "-"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(json.dumps(args).encode(), timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        return None, "TIMEOUT", round(time.time() - t0, 1)
    if p.returncode != 0 or not out.strip():
        return None, (err.decode(errors="replace") or out.decode(errors="replace"))[:500], round(time.time() - t0, 1)
    return out.decode(errors="replace"), None, round(time.time() - t0, 1)


def fetch(ticker, tf):
    for attempt in (1, 2):
        raw, err, el = call("get_coin_candles", {"ticker": ticker, "interval": tf, "limit": 100})
        if raw is None:
            print(f"  {ticker}_{tf} attempt {attempt} FAILED ({el}s): {err}")
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(f"  {ticker}_{tf} attempt {attempt} UNPARSEABLE ({el}s): {raw[:300]}")
            continue
        candles = data["candles"] if isinstance(data, dict) and "candles" in data else data
        if not isinstance(candles, list) or not candles:
            print(f"  {ticker}_{tf} attempt {attempt} NO ROWS ({el}s): {raw[:300]}")
            continue
        return candles, el
    return None, None


errors = []
summary = []
for tf, coins in (("1h", COINS_1H), ("4h", COINS_4H)):
    for ticker in coins:
        candles, el = fetch(ticker, tf)
        if candles is None:
            errors.append(f"{ticker}_{tf}")
            continue
        path = os.path.join(RAW, f"{ticker}_{tf}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(candles, f, separators=(",", ":"))
        summary.append((f"{ticker}_{tf}", len(candles), candles[0]["timestamp"], candles[-1]["timestamp"], el))
        print(f"  {ticker}_{tf}: {len(candles)} bars {candles[0]['timestamp']} -> {candles[-1]['timestamp']} ({el}s)")

print("\nwritten:", len(summary), "files; errors:", errors or "none")
end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
marker = os.path.join(RAW, "_pulled_at.json")
m = json.load(open(marker, encoding="utf-8"))
m["end"] = end
json.dump(m, open(marker, "w", encoding="utf-8"))
print("pulled_at:", json.dumps(m))
if errors:
    sys.exit(1)
