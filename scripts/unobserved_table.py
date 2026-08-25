"""Render the unobserved-label table from the audit record, so prose cannot drift from it.

The table appeared by hand in docs/19 and docs/06 and in the audit JSON. Three copies, no
check between them, and they diverged: docs/19 still printed "REGIME_VOL normal 30/30,
expanding never seen" long after the JSON had moved `expanding` to seen, and BOTH docs and
the JSON claimed `OI_VELOCITY` never reads `steady` while a sample committed to this repo
contained nine of them.

data/audit/tier_c_coherence.json['unobservedLabels'] is the source of truth. This renders
it; tests/test_doc_audit_agreement.py asserts the docs contain what it renders.

    python -m scripts.unobserved_table          # print the table, for pasting into a doc
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data/audit/tier_c_coherence.json"

# PERP_SPOT_CONFIRMS renders a boolean and so carries no conditionVocabulary. Every other
# tracked metric must partition its contract vocabulary exactly.
NO_VOCABULARY = {"PERP_SPOT_CONFIRMS"}


def tracked() -> dict[str, dict]:
    rec = json.loads(AUDIT.read_text(encoding="utf-8"))["unobservedLabels"]
    return {k: v for k, v in rec.items() if not k.startswith("_")}


def render() -> str:
    """The canonical markdown table. Sorted, so the output is stable."""
    lines = ["| metric | seen | never seen |", "|---|---|---|"]
    for name, rec in sorted(tracked().items()):
        seen = ", ".join(rec["seen"]) or "—"
        unseen = ", ".join(rec["unseen"]) or "— *(all observed)*"
        lines.append(f"| `{name}` | {seen} | {unseen} |")
    return "\n".join(lines)


def still_unobserved() -> list[tuple[str, str]]:
    return [(m, lbl) for m, rec in sorted(tracked().items()) for lbl in rec["unseen"]]


if __name__ == "__main__":
    print(render())
    print()
    print(f"{len(still_unobserved())} label values still unobserved:")
    for metric, label in still_unobserved():
        print(f"  {metric}.{label}")
