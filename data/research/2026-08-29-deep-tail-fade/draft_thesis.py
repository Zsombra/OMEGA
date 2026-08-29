"""Draft the research-derived thesis and run it through the doc-20 offline loop:
validate_thesis -> plan -> brief. Zero live calls."""
import json
import os
import sys

sys.path.insert(0, r"C:\Users\rafae\Documents\GitHub\OMEGA\.claude\worktrees\vwap-strategy-dev-c75dc9")

from omega.authoring import brief, validate_thesis
from omega.generate import Thesis, plan

thesis = Thesis(
    name="Deep-Tail Fade",
    tagline="Fade only the extreme stretch",
    description=(
        "1h contrarian reversion on majors. Research-derived (2026-08-29, 13-coin "
        "candle study): stretch reversion at 1h concentrates in the deep tail "
        "(>90th pct stretch: 61.5% hit, +13 bps/bar) and is strongest on majors; "
        "volume-weighted references added nothing over plain means, so the native "
        "Bollinger machinery carries the thesis. Wins are small and losses are "
        "big when stretches continue - selectivity is the whole game."
    ),
    anchor="1h",
    stance="FADE",
    gate=0.65,
    weights={
        "BOLLINGER": 3,   # the measured effect: deep %B extremes revert (native deep-tail clauses)
        "RSI": 2,         # 43% co-fire with stretch events; clause constants exact (35/65)
    },
    # MFI demoted (14% co-fire). CVD & FUNDING deliberately VISIBLE but UNWEIGHTED:
    # the OBV analog of the CVD confirmation leg fired on only 6/72 deep-tail events
    # and lost when it fired (timing mismatch: a 4-bar flow trend cannot have turned
    # at a fresh deep stretch); funding alignment looked helpful (+12.8 vs +2.3 bps)
    # but funding was positive 94-100% of the window, so the split is confounded
    # with fade side - unproven. The agent sees both and judges; neither gates.
    context=["MFI", "REGIME", "CVD", "FUNDING"],
    required=[],                 # no measured basis for vetoes
    coin_selection={"mode": "explicit", "tickers": ["BTC", "ETH", "SOL"]},
    execution=None,              # measured platform defaults; no research basis to override
)

findings = validate_thesis(thesis)
print("validate_thesis findings:", "none" if not findings else "")
for f in findings:
    print(f"  [{f.severity}] {f.code} {f.path}: {f.message}")

p = plan(thesis)
b = brief(p)
print()
print("=" * 72)
print(b)
print("=" * 72)

sim = p.simulate(0.75)
print()
print("aggregate simulation (every weighted signal at 0.75):", sim)

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "deep_tail_fade_thesis.json"), "w", encoding="utf-8") as f:
    json.dump({
        "name": thesis.name, "tagline": thesis.tagline, "description": thesis.description,
        "anchor": thesis.anchor, "stance": thesis.stance, "gate": thesis.gate,
        "weights": thesis.weights, "context": thesis.context, "required": thesis.required,
        "coin_selection": thesis.coin_selection, "execution": thesis.execution,
    }, f, indent=2)
with open(os.path.join(here, "deep_tail_fade_brief.txt"), "w", encoding="utf-8") as f:
    f.write(b)
print("saved: deep_tail_fade_thesis.json, deep_tail_fade_brief.txt")
