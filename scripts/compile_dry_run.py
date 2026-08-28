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
# The compile CREATE timeframe enum, re-verified live at the 2026-08-28 campaign
# preflight (zero drift against the pinned sets).
ALL_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "3d", "1w"]


def _redact(resp: dict) -> dict:
    if isinstance(resp.get("planToken"), str):
        t = resp["planToken"]
        resp["planToken"] = {"_redacted": "credential-bound 5-minute token, left to "
                                          "expire; never applied",
                             "length": len(t),
                             "sha256": hashlib.sha256(t.encode()).hexdigest()}
    return resp


def probe(field: str, value, base: str = "small") -> dict:
    """A known body with exactly ONE top-level field replaced - one variable per
    compile keeps every verdict attributable. base="small": the viable explicit
    BTC/ETH/SOL body. base="full": the ranked/ALL/30 body (the BG-14 refusal's
    payload - the cap family's own baseline)."""
    req = request(small=(base == "small"))["request"]
    req[field] = value
    return {"request": req}

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
    if len(sys.argv) > 2 and sys.argv[1] == "tf":
        assert sys.argv[2] in ALL_TIMEFRAMES, f"not a platform timeframe: {sys.argv[2]}"
        print(json.dumps(probe("timeframe", sys.argv[2]), separators=(",", ":")))
        return 0
    if len(sys.argv) > 2 and sys.argv[1] == "ranked":
        sel = {"mode": "ranked",
               "category": sys.argv[3] if len(sys.argv) > 3 else "ALL",
               "limit": int(sys.argv[2])}
        print(json.dumps(probe("coinSelection", sel, base="full"), separators=(",", ":")))
        return 0
    if len(sys.argv) > 2 and sys.argv[1] == "rrlow":
        print(json.dumps(probe("minRiskRewardRatio", float(sys.argv[2])), separators=(",", ":")))
        return 0
    if len(sys.argv) > 2 and sys.argv[1] == "atr":
        print(json.dumps(probe("minAtrPct", float(sys.argv[2])), separators=(",", ":")))
        return 0
    if len(sys.argv) > 4 and sys.argv[1] == "record-into":
        # record-into <respfile> <key> <auditfile>: redact and append one probe
        # response under "probes"[key] in data/audit/<auditfile>, creating the file
        # with an empty scaffold if absent. Verbatim-before-interpretation.
        resp = _redact(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
        out = ROOT / "data/audit" / sys.argv[4]
        doc = (json.loads(out.read_text(encoding="utf-8")) if out.exists()
               else {"_what": "FILL IN", "probes": {}, "_interpretation": "FILL IN"})
        doc["probes"][sys.argv[3]] = resp
        out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"recorded probes[{sys.argv[3]}] -> {out}")
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        raw = Path(sys.argv[2]).read_text(encoding="utf-8")
        resp = _redact(json.loads(raw))
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
