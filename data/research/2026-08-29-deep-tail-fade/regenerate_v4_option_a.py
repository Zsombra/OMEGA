"""Option A of the plan's Step 3 decision space (user-chosen, 2026-08-30):
drop the universe from BTC/ETH/SOL to BTC/ETH, keep every context column.

The ONE compile of the v3 body was refused by BG-14's preview byte cap
(262,935 > 256,000 at explicit-3 tickers, 15 custom columns). This rebuilds
the body from the SAME preserved thesis with only the ticker list overridden -
the research record (deep_tail_fade_thesis.json, 3 majors) stays untouched,
following the request(small=True) precedent in scripts/compile_dry_run.py.

Whether 2 tickers fits under the cap is deliberately NOT predicted here: the
byte curve was measured concave with fixed overhead (cap_boundary_2026-08-28),
so only a compile can measure it.

Run from the repo root: python data/research/2026-08-29-deep-tail-fade/regenerate_v4_option_a.py
"""
import sys as _sys

# RETIRED 2026-10-06. This rebuilt a compile_strategy_plan CREATE body with
# StrategyPlan.wire(); contract 85.0.0 removed the compile and omega removed wire() (no
# alias). The bodies beside this file are frozen records that tests read as fixtures, so a
# re-run must never overwrite them with a different shape. A v91 equivalent is
# plan(thesis).axes() / .preview_request() (docs/plans/2026-10-06-omega-draft-lifecycle-re-extraction.md).
if __name__ == "__main__":
    _sys.exit("retired: compile_strategy_plan was removed at contract 85.0.0 and "
              "StrategyPlan.wire() with it; the compile bodies here are frozen records")

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

from omega.authoring import brief, validate_thesis
from omega.generate import Thesis, plan

HERE = os.path.dirname(os.path.abspath(__file__))
OPTION_A_TICKERS = ["BTC", "ETH"]

with open(os.path.join(HERE, "deep_tail_fade_thesis.json"), encoding="utf-8") as f:
    record = json.load(f)
record["coin_selection"] = {"mode": "explicit", "tickers": OPTION_A_TICKERS}
thesis = Thesis(**record)

findings = validate_thesis(thesis)
print("validate_thesis findings:", "none" if not findings else "")
for f in findings:
    print(f"  [{f.severity}] {f.code} {f.path}: {f.message}")

p = plan(thesis)
errors = [str(f) for f in p.condition_findings() if f.severity == "error"]
errors += [str(f) for f in p.validation().errors]
print("plan errors:", "none" if not errors else errors)

b = brief(p)
body = p.wire()  # removed 2026-10-06; unreachable behind the guard above

with open(os.path.join(HERE, "compile_body_deep_tail_fade_v4.json"), "w", encoding="utf-8") as f:
    json.dump(body, f, indent=2, ensure_ascii=False)
with open(os.path.join(HERE, "deep_tail_fade_brief_v4.txt"), "w", encoding="utf-8") as f:
    f.write(b)

# --- the diff against v3: only coinSelection and its assumption line ---------
with open(os.path.join(HERE, "compile_body_deep_tail_fade_v3.json"), encoding="utf-8") as f:
    v3 = json.load(f)


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
        yield (path, repr(a)[:70], repr(b)[:70])


print()
print("v3 -> v4 diff:")
for path, old, new in walk(v3, body):
    print(f"  {path}: {old} -> {new}")

compact = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
print()
print(f"compact v4 body bytes: {len(compact)} (the CAP bites the server-side "
      f"preview, not this body - recorded for scale only)")
