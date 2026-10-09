"""Build, print and record the read-only dry run of a GENERATED plan at contract 91.

compile_strategy_plan was removed at contract 85.0.0 with no alias (README "Contract
history - v85"), and with it the compile dry run this script used to build (its 2026-08-28
form, scripts/compile_dry_run.py, is in git history; its records stay under data/audit/).
The dry run is now `preview_strategy_report {coinSelection, source: {kind: "FIELDS", ...}}`:
read-only, and it judges the report and the conditions with the v84/v88 grammar. It does
NOT judge signal rules, gates or dials - only a stage does, and a stage is a write.

Print mode emits the exact body. omega opens no sockets and holds no MCP client
(omega/probe.py:3): the session pastes the printed body into ONE preview_strategy_report
call, on the user's word, exactly as before. `--live` exists only to refuse: nothing here
can make that call. Record mode writes a saved response VERBATIM to
data/audit/preview_dry_run_<date>.json with an interpretation stub.

  python scripts/preview_dry_run.py              ranked preview body (the preset's universe)
  python scripts/preview_dry_run.py small        explicit BTC/ETH/SOL preview body
  python scripts/preview_dry_run.py tf4h         the small body at a 4h anchor
  python scripts/preview_dry_run.py stage        the CREATE stage_strategy_draft request (NOT a dry run)
  python scripts/preview_dry_run.py record <request.json> <response.json> <date>
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omega.generate import PRESETS, plan  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRESET = "trend-continuation"   # audit-clean (see scripts/audit_generated_plans.py)
# The BG-14 workaround measured 2026-08-28: three explicit tickers kept the compile's
# report preview under the 256,000-byte cap where ranked/ALL/30 did not.
SMALL_TICKERS = ["BTC", "ETH", "SOL"]
LIVE_REFUSAL = ("--live refused: omega holds no MCP client and never calls the platform "
                "(omega/probe.py:3). Print the body without --live and make the one "
                "preview_strategy_report call from the session, on the user's word.")


def _thesis(*, small: bool = False, anchor: str | None = None):
    thesis = PRESETS[PRESET]
    if small or anchor is not None:
        thesis = replace(thesis, coin_selection={"mode": "explicit", "tickers": SMALL_TICKERS})
    if anchor is not None:
        thesis = replace(thesis, anchor=anchor)
    return thesis


def preview_request(*, small: bool = False, anchor: str | None = None) -> dict:
    """The preview_strategy_report arguments for the preset: {coinSelection, source}."""
    return plan(_thesis(small=small, anchor=anchor)).preview_request()


def stage_request(*, small: bool = False) -> dict:
    """The CREATE stage_strategy_draft arguments: {request: {draftVersion: 0, axes}}. No
    strategyId - v85: "Omit strategyId to open a NEW create draft". A stage is a WRITE
    into the player's draft; printing it is not making it."""
    return {"request": {"draftVersion": 0, "axes": plan(_thesis(small=small)).axes()}}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--live" in args:
        raise SystemExit(LIVE_REFUSAL)
    mode = args[0] if args else "ranked"
    if mode == "small":
        body = preview_request(small=True)
    elif mode == "tf4h":
        body = preview_request(small=True, anchor="4h")
    elif mode == "stage":
        body = stage_request(small=True)
    elif mode == "record" and len(args) > 3:
        sent = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        resp = json.loads(Path(args[2]).read_text(encoding="utf-8"))
        out = ROOT / "data/audit" / f"preview_dry_run_{args[3]}.json"
        if out.exists():
            raise SystemExit(f"{out} exists; refusing to overwrite a recorded response")
        out.write_text(json.dumps({
            "_what": "preview_strategy_report (FIELDS source) of an omega-GENERATED plan. "
                     "Read-only: judges the report and the conditions, not rules, gates or dials.",
            "preset": PRESET,
            "request": sent,
            "responseVerbatim": resp,
            "_interpretation": "FILL IN: conditions accepted? which refusal? next action?",
        }, indent=2) + "\n", encoding="utf-8")
        print(f"recorded {out}")
        return 0
    elif mode == "ranked":
        body = preview_request()
    else:
        raise SystemExit(__doc__)
    print(json.dumps(body, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
