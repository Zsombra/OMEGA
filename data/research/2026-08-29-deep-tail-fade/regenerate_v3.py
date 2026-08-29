"""Step 2 of the condition-clock migration (2026-08-30): rebuild the Deep-Tail
Fade compile body from the preserved thesis via the PATCHED generator, run the
doc-20 offline loop (validate_thesis -> plan -> brief), and diff against the
refused v2 body. Zero live calls.

Expected deltas v2 -> v3, and nothing else:
  - conditions[].clock: v2 was CLOSE-everywhere (refused with
    CONDITION_CLOCK_OPERAND_ILLEGAL); v3 carries the plan's clock policy
    (ambient + verdicts LIVE, candle-only CORE checklists CLOSE).
  - sections[].notes: v2's hand-written amendment vs v3's generator provenance.
  - entry: absent in v2; REQUIRED on CREATE since the schema published it
    (2026-08-30) - v3 mirrors the platform migration default.

Run from the repo root: python data/research/2026-08-29-deep-tail-fade/regenerate_v3.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

from omega.authoring import brief, validate_thesis
from omega.generate import Thesis, plan

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "deep_tail_fade_thesis.json"), encoding="utf-8") as f:
    thesis = Thesis(**json.load(f))

findings = validate_thesis(thesis)
print("validate_thesis findings:", "none" if not findings else "")
for f in findings:
    print(f"  [{f.severity}] {f.code} {f.path}: {f.message}")

p = plan(thesis)
errors = [str(f) for f in p.condition_findings() if f.severity == "error"]
errors += [str(f) for f in p.validation().errors]
print("plan errors:", "none" if not errors else errors)

b = brief(p)
body = p.wire()

with open(os.path.join(HERE, "compile_body_deep_tail_fade_v3.json"), "w", encoding="utf-8") as f:
    json.dump(body, f, indent=2, ensure_ascii=False)
with open(os.path.join(HERE, "deep_tail_fade_brief_v3.txt"), "w", encoding="utf-8") as f:
    f.write(b)

# --- the diff against the refused v2 body -----------------------------------
with open(os.path.join(HERE, "compile_body_deep_tail_fade_v2.json"), encoding="utf-8") as f:
    v2 = json.load(f)
v2 = v2.get("request", v2)      # v2 was recorded as the full tool argument


def walk(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                yield (f"{path}.{k}", "<absent>", "<present>")
            elif k not in b:
                yield (f"{path}.{k}", "<present>", "<absent>")
            else:
                yield from walk(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield (path, f"len {len(a)}", f"len {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            yield from walk(x, y, f"{path}[{i}]")
    elif a != b:
        yield (path, repr(a)[:60], repr(b)[:60])


print()
print("v2 -> v3 diff:")
for path, old, new in walk(v2, body):
    print(f"  {path}: {old} -> {new}")
