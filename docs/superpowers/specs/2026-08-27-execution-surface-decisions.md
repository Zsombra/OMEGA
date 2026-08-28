# Execution Surface — Decisions Needed Before Planning

This is **not** an implementation plan. It is the list of design decisions the user has
to make before the 16 execution parameters can be modelled. Writing a plan first would
mean guessing strategy decisions on the user's behalf, which is exactly what this repo's
working rules forbid. When these are answered, feed this document plus the answers into
the writing-plans flow.

## What this is about

`compile_strategy_plan` accepts 16 parameters `omega.generate` never emits. Five of the
six probed appear **nowhere** in `omega/` or `docs/` (`data/audit/write_surface_gap.json`).
They control how a strategy *trades*, not what it *looks at*:

| group | parameters | published bounds |
|---|---|---|
| risk gates | `minAtrPct`, `minRiskRewardRatio`, `minStopLossAtrMultiple`, `maxStopLossAtrMultiple` | minAtrPct 0.01–50; others unbounded in schema |
| trailing stop | `trailingEnabled`, `trailingTriggerR` (0–2, step .01), `trailingGivebackPct` (25–55), `trailingBufferPct` (0.01–1) | |
| break-even | `breakEvenEnabled`, `breakEvenTriggerR` (0.5–2) | |
| time decay | `timeDecayEnabled`, `Interval` (1–480 min), `GracePeriod` (1–1440 min), `TightenPct` (0.1–50), `MaxTightenPct` (1–100), `StaleThresholdTpProgressPct` (0–100) | |

Omitting them all is legal — the platform applies its own defaults. ~~What those defaults
are is unknown and unmeasured.~~ **Update 2026-08-28: measured.** The viable compile of a
generated plan sent none of the 16 and its `postState` shows what the platform fills in
(`data/audit/execution_surface_ownership_2026-08-28.json`):

> minAtrPct 0.5 · minRiskRewardRatio 1.5 · stop-loss 1–2×ATR · trailing ON (trigger 1R,
> giveback 45%, buffer 0.25) · break-even ON at 1.08R · time decay ON (15 min interval,
> 60 min grace, 5% tighten, 50% max, stale at 25% TP progress)

One data point (one CREATE, 1h anchor). A default-configured strategy is **not** flat-
passive: trailing, break-even and decay are all on by default.

## Measured 2026-08-28 — where these parameters live (asked by the user)

The user recalled risk/reward being set at **agent creation**. Checked against every
MCP-visible surface, read-only (`execution_surface_ownership_2026-08-28.json`):

- **All 16 are strategy-owned.** The compile schemas take them, a live tuned strategy
  (TRAJ-03: R:R 1.5, minAtrPct 0.8, giveback 25) stores them, and no agent surface
  accepts or returns any of them.
- **Agent creation owns the capital block**: exposure/drawdown/daily-loss caps in USD,
  leverage, slippage, position-size presets, min allocation, daily trade cap, balance
  threshold. These are genuinely risk settings — the likely source of the recollection —
  but they are *capital* risk, not trade-shape risk.
- Deployment policies (game slots) and radar deployments (per-coin trade authority)
  carry neither group.
- **Residue observed**: the agent-facing catalog still publishes ATR/R:R *bounds*
  (0.1–10, 0.5–3) that disagree with the strategy schema's own bounds, and the agent
  create prose mentions "ATR preferences / nested positionManagement" its schema
  rejects. Its own note says signal presets were retired in favour of setting these
  fields directly. Which bounds the validator enforces on a strategy write is unmeasured.

Consequence for the decisions below: "emit nothing" (1a) no longer means "invisible risk
settings" — it means the measured defaults above, which can be stated in the critique.

## Decision 1 — What should omega do when a thesis says nothing about execution?

- **(a) Emit nothing; surface a critique line.** Honest, zero invented numbers; strategy
  runs on unknown platform defaults. *Recommended as the starting point* — it matches the
  repo's extract-never-infer rule.
- **(b) Emit conservative explicit defaults** (e.g. `breakEvenEnabled: true` at 1R).
  Visible and reproducible — but the numbers would be omega's invention, and every one is
  a trading opinion nobody has validated (no outcome data exists; 23 of 24 agents have
  zero evaluations).
- **(c) Require every `Thesis` to state an `execution` block; refuse to plan without one.**
  Maximally explicit, but breaks all five presets until someone writes numbers with no
  evidence behind them.

## Decision 2 — Should the platform's actual defaults be measured first?

**ANSWERED 2026-08-28.** The compile echo did reveal them (see the measured section
above). The "unknown defaults" problem is now "documented defaults", which makes 1(a)
materially safer: omega can emit nothing and still *tell the user exactly what the
strategy will trade on*. Decisions 1, 3 and 4 remain open and remain the user's.

## Decision 3 — Per-thesis or per-stance execution profiles?

If (b) or (c): do FADE theses (mean-reversion) share stop/trailing numbers with ALIGN
theses (trend-continuation)? A reversion trade and a breakout trade have opposite
relationships to giveback. Someone with a trading opinion must answer; the toolkit cannot.

## Decision 4 (separate, small) — the `flow-divergence` preset

`SA_CORE_DOWN` counts `PERP_SPOT_FLOW is 'perp_led_fragile'` among its 2-of-4 members,
and that label has never been observed (78 coins × 4 anchors), so the gate is silently
2-of-3. Options: leave as designed (the label is *possible*, just unseen — the platform
lists it in the vocabulary); replace with an observed label (changes what the thesis
believes); or drop to a declared 2-of-3. **User's call; deliberately not auto-fixed.**
Pinned in `tests/test_generated_plans_audit.py` either way.

## Standing constraints that survive into any resulting plan

Never `apply_strategy_plan` without explicit per-instance user approval; never bind
strategies to agents; no outcome data exists, so every execution number is untestable
against results today — say so wherever one is written down.
