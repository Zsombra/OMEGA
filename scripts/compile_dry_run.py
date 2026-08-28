"""Build, print, and record the first-ever compile of a GENERATED plan.

Print mode emits the exact request body; the executor pastes it into ONE
mcp compile_strategy_plan call. Record mode reads the (possibly file-overflowed)
response, checks it is for OUR payload, and writes it VERBATIM to
data/audit/compile_dry_run_<date>.json with an interpretation stub.

HARD RULES: compile once; never call apply_strategy_plan; a refusal is recorded
exactly like a success. The minted token is left to expire.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from omega.generate import PRESETS, plan

ROOT = Path(__file__).resolve().parents[1]
PRESET = "trend-continuation"   # audit-clean (see scripts/audit_generated_plans.py)

def request() -> dict:
    return {"request": plan(PRESETS[PRESET]).wire()}

def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        raw = Path(sys.argv[2]).read_text(encoding="utf-8")
        resp = json.loads(raw)
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
