"""VWAP Reject 4h, the corrected revision 3 draft (2026-11-14). OFFLINE: writes stage bodies, submits nothing.

Why: live revision 2 (strategy 5b2406f7, read 2026-11-14) marks VWAP_REJECT_LONG and VWAP_REJECT_SHORT both
`required: true`. One levelInteraction column carries one label per bar, so the two are never TRUE together and
the strategy qualified 0 of 291,018 coin checks since 2026-10-30 (battlegrid-manager
docs/status/2026-11-14-exit-study.md). Revision 2's own notes state the intent: "A rejection from above with a
strong close is the long; a rejection from below with a weak close is the short."

Variant A (the fix): the four existing conditions become building blocks (verdict null, required false, their
definitions untouched) and two ALL groups carry the verdicts - LONG_SETUP (UP) and SHORT_SETUP (DOWN).
CONDITIONS is the only axis sent.

Variant B (A + the strategy's own regime rule as a gate): the market read says "ranging and volatile regimes
only"; B reads REGIME_STATE in the VWAP section and requires a range. It sends REPORT, CONDITIONS and
MARKET_READ (the live text names bear_expansion / bull_expansion, labels contract 146 retired on 2026-11-01).

Run:  PYTHONPATH=. python scripts/build_vwap_reject_rev3.py <live_strategy.json>
      (the file is the `strategy` object get_strategy returned)
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from omega import conditions as C
from omega.types import Report
from omega.validate import validate_report

OUT = Path(__file__).resolve().parents[1] / "out" / "vwap_reject_rev3"
VWAP_SECTION = "custom:73f5a330-7e57-839c-8f94-04f9209e580a"
RANGE_LABELS = ["bull range", "bear range"]


def building_block(cond: dict) -> dict:
    """The live condition with its entry role taken away: definition, key and name untouched."""
    return {**cond, "verdict": None, "required": False}


def conditions_a(live: list[dict]) -> list[dict]:
    by_key = {c["conditionKey"]: c for c in live}
    blocks = [building_block(by_key[k]) for k in
              ("VWAP_REJECT_LONG", "VWAP_REJECT_SHORT", "STRONG_CLOSE_LONG", "WEAK_CLOSE_SHORT")]
    return blocks + [
        C.condition("LONG_SETUP", "VWAP rejected from above and the bar closed strong",
                    C.all_of(C.ref("VWAP_REJECT_LONG"), C.ref("STRONG_CLOSE_LONG")), verdict="UP"),
        C.condition("SHORT_SETUP", "VWAP rejected from below and the bar closed weak",
                    C.all_of(C.ref("VWAP_REJECT_SHORT"), C.ref("WEAK_CLOSE_SHORT")), verdict="DOWN"),
    ]


def sections_b(live: list[dict]) -> list[dict]:
    out = copy.deepcopy(live)
    vwap = next(s for s in out if s.get("sectionKey") == VWAP_SECTION)
    vwap["columns"].append({"metric": "REGIME_STATE", "transformId": "value", "timeframe": {"rel": "anchor"}})
    vwap["notes"] = ("Session VWAP context: value, distance, bar interaction, close location and the daily regime "
                     "state. A rejection from above with a strong close is the long; a rejection from below with a "
                     "weak close is the short; both only in a range.")
    return out


def conditions_b(live: list[dict]) -> list[dict]:
    return conditions_a(live) + [
        C.condition("RANGE_REGIME", "Daily regime is a range (no trend)",
                    C.in_("regState", RANGE_LABELS, section_key=VWAP_SECTION), required=True),
    ]


def market_read_b(live: str) -> str:
    old = ("DO NOT ENTER when the regime is bear_expansion or bull_expansion. Trending markets break through VWAP "
           "and do not mean-revert. This strategy belongs in ranging and volatile regimes only.")
    new = ("DO NOT ENTER when the daily regime state is bull trend or bear trend. Trending markets break through "
           "VWAP and do not mean-revert. This strategy belongs in range regimes only; the RANGE_REGIME condition "
           "enforces it.")
    if old not in live:
        raise SystemExit("the live market read no longer carries the regime sentence this draft replaces")
    return live.replace(old, new)


def check(sections: list[dict], conds: list[dict], anchor: str, label: str) -> None:
    report = Report.model_validate({"anchor": anchor, "sections": sections})
    result = validate_report(report)
    findings = [str(f) for f in result.findings]
    findings += [str(f) for f in C.validate_conditions(report, conds)]
    findings += [str(f) for f in C.validate_entry_gate(conds)]
    print(f"[{label}] entry gates: {C.entry_gates(conds)} | findings: {len(findings)}")
    for f in findings:
        print("   ", f)


def main() -> None:
    live = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if live["revision"] != 2:
        raise SystemExit(f"built against revision 2; the live strategy is at revision {live['revision']}")
    OUT.mkdir(parents=True, exist_ok=True)
    anchor = live["timeframe"]

    a = {"CONDITIONS": {"conditions": conditions_a(live["conditions"])}}
    check(live["sections"], a["CONDITIONS"]["conditions"], anchor, "A")

    b = {"REPORT": {"sections": sections_b(live["sections"])},
         "CONDITIONS": {"conditions": conditions_b(live["conditions"])},
         "MARKET_READ": {"marketReadText": market_read_b(live["marketReadText"])}}
    check(b["REPORT"]["sections"], b["CONDITIONS"]["conditions"], anchor, "B")

    for name, axes in (("a", a), ("b", b)):
        body = {"_strategyId": live["id"], "_builtAgainstRevision": live["revision"], "draftVersion": 0, "axes": axes}
        path = OUT / f"variant_{name}.stage.json"
        path.write_text(json.dumps(body, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print("written", path.relative_to(OUT.parents[1]))


if __name__ == "__main__":
    main()
