"""Generate complete strategies from a thesis, and from a target signal list.

Run:  PYTHONPATH=. python examples/build_strategy.py
Emits: out/*.strategy.json   (nothing is submitted to BattleGrid)
"""
from __future__ import annotations

from omega.generate import PRESETS, Thesis, emit_plan, plan, plan_for_signals

RULE = "=" * 74


def show(p, label):
    print(RULE)
    print(label)
    print(RULE)
    print(p.render())
    print()


def main() -> None:
    # 1. every shipped preset -------------------------------------------------
    for key in PRESETS:
        show(plan(PRESETS[key]), f"PRESET: {key}")

    # 2. a thesis of your own -------------------------------------------------
    mine = Thesis(
        name="Funding Squeeze Fade",
        tagline="Fade crowded leverage into structure",
        description="Extreme funding with OI at a peak, faded into a structural zone.",
        anchor="15m",
        gate=0.70,
        weights={"FUNDING": 3, "OPEN_INTEREST": 3, "PRICE_STRUCTURE": 2, "CVD": 1},
        context=["REGIME"],
    )
    show(plan(mine), "CUSTOM THESIS")

    # 3. work backwards from signals you want to weight ------------------------
    wanted = ["bollinger_lower_touch", "rsi_oversold", "cvd_bull_divergence",
              "mtf_aligned_bull"]          # the last one is unreachable
    back = plan_for_signals(wanted, name="Backwards Build", tier=2, gate=0.65)
    print(RULE)
    print("BACKWARDS: build the report that feeds these signals")
    print(RULE)
    print("wanted:", ", ".join(wanted))
    print("note:  ", back.thesis.description or "all reachable")
    print()
    print(back.membership().render())
    print()

    # 4. emit ------------------------------------------------------------------
    for key in ("mean-reversion", "squeeze-breakout"):
        print("emitted ->", emit_plan(plan(PRESETS[key]), key))
    print("emitted ->", emit_plan(plan(mine), "funding-squeeze-fade"))
    print()
    print("NOT submitted. Quota untouched at 24/25.")


if __name__ == "__main__":
    main()
