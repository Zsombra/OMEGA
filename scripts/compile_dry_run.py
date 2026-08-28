"""Build, print, and record the first-ever compile of a GENERATED plan.

Print mode emits the exact request body; the executor pastes it into ONE
mcp compile_strategy_plan call. Record mode reads the (possibly file-overflowed)
response, checks it is for OUR payload, and writes it VERBATIM to
data/audit/compile_dry_run_<date>.json with an interpretation stub.

HARD RULES: compile once; never call apply_strategy_plan; a refusal is recorded
exactly like a success. The minted token is left to expire.
"""
from __future__ import annotations
import hashlib, json, sys
from dataclasses import replace
from pathlib import Path
from omega.generate import PRESETS, plan

ROOT = Path(__file__).resolve().parents[1]
PRESET = "trend-continuation"   # audit-clean (see scripts/audit_generated_plans.py)
# BG-14 workaround probe: the ranked/ALL/30 preview measured 395,404 bytes against the
# 256,000 cap. Three explicit tickers shrink the preview footprint; whether that is
# enough is the measurement, not an assumption.
SMALL_TICKERS = ["BTC", "ETH", "SOL"]

def request(*, small: bool = False, rr: float | None = None,
            anchor: str | None = None) -> dict:
    thesis = PRESETS[PRESET]
    if small or rr is not None or anchor is not None:
        thesis = replace(thesis, coin_selection={"mode": "explicit",
                                                 "tickers": SMALL_TICKERS})
    if anchor is not None:
        thesis = replace(thesis, anchor=anchor)
    req = plan(thesis).wire()
    if rr is not None:
        # Probe: catalog says R:R 0.5-3, schema says unbounded. One changed field.
        req["minRiskRewardRatio"] = rr
    return {"request": req}

def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "small":
        print(json.dumps(request(small=True), separators=(",", ":")))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "bounds":
        print(json.dumps(request(small=True, rr=5.0), separators=(",", ":")))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "tf4h":
        print(json.dumps(request(small=True, anchor="4h"), separators=(",", ":")))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        raw = Path(sys.argv[2]).read_text(encoding="utf-8")
        resp = json.loads(raw)
        if isinstance(resp.get("planToken"), str):
            t = resp["planToken"]
            resp["planToken"] = {"_redacted": "credential-bound 5-minute token, left to "
                                              "expire; never applied",
                                 "length": len(t),
                                 "sha256": hashlib.sha256(t.encode()).hexdigest()}
        out = ROOT / "data/audit" / f"compile_dry_run_{sys.argv[3]}.json"
        out.write_text(json.dumps({
            "_what": "First compile of an omega-GENERATED plan. Dry-run: no apply.",
            "preset": PRESET,
            "requestKeys": sorted(request()["request"].keys()),
            "responseVerbatim": resp,
            "_interpretation": "FILL IN: viable? refused? which rule? next action?",
        }, indent=2) + "\n", encoding="utf-8")
        print(f"recorded {out}")
        return 0
    print(json.dumps(request(), separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
