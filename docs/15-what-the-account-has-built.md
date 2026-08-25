# 15 · What the account has actually built

Doc 14 counts what the column space *permits*: 322 legal atoms, 488 structural
shapes, 1779 once operands and rank orderings expand. It also counts what the
platform's own templates use — leaving 349 shapes no template has ever touched.

This doc answers the other half of that question. Of the shapes the design space
permits, how many has **this account** ever used?

**Zero.**

Data: `data/audit/private_strategy_sections.json` — every private strategy read
back from the connector on 2026-08-25 and recorded verbatim.

## The count

| | |
|---|---|
| Private strategies | 25 (quota 25/25, none left) |
| Sections across all of them | 95 |
| Sections with `kind: "custom"` | **0** |
| Conditions across all of them | **0** |
| Strategies with `forkedFromStrategyId` | 1 (the OMEGA-TEST fork, made yesterday) |

Every one of the 95 sections is `{"kind": "platform", "sectionKey": "includeX"}`.
Not one carries a `columns` array.

## What the strategies vary instead

They are not identical — they differ along three axes, all of which are
*selection*, not *authorship*:

1. **Which platform sections to include.** Between 2 and 6 of them, chosen to
   match the thesis. `MATH-C8: Perp-Spot Basis` takes `includePriceAction` +
   `includePerpSpotFlow` and nothing else.
2. **Signal allocations.** Every strategy carries the full ~86-signal scorecard
   with most at `0` and a handful raised. `MATH-C5` puts
   `structure_zone_confluence` at 3 and `structure_fvg_approach` at 2.
3. **Gates and prose.** `minAggregateScore` 0.65 or 0.7, `minAtrPct` 0.5 or 0.8,
   and `marketReadText` — substantial on the July cohort, empty on the August one.

## Two cohorts, one method

| | July 2026-07-29 (16 strategies) | August 2026-08-17 (8 strategies) |
|---|---|---|
| `marketReadText` | written, 4–10 lines | empty |
| Gates | 0.7 / 0.8 | 0.65 / 0.5 |
| Revisions since | 4–14 | 1–2 |
| Custom sections | 0 | 0 |

The July cohort was tended — revision 14 on `DIST-01` means it was edited a dozen
times. The August cohort was created and left alone. Neither reached for a custom
column.

## Why this matters to OMEGA

Three consequences follow, and they cut in different directions.

**The 349 unused shapes are unused, full stop.** Doc 14 called them "never used by
a platform template." They are also never used by anyone here. There is no prior
art to copy from, which is exactly why `omega.probe` compiles a shape against the
live connector before `omega.explain` will report a number for it.

**`apply_strategy_plan` CREATE demonstrably worked on 2026-07-29 and 2026-08-17.**
Twenty-four strategies exist with chosen sections, tuned allocations, custom gates
and — for the July cohort — authored market-read text. They were created, not
forked (`forkedFromStrategyId: null` on all 24). Whatever broke, broke after
2026-08-17. That pins the regression window and is the strongest evidence in the
defect report.

**Nothing tests the custom-section write path, because nothing has used it.** The
account's whole history exercises platform sections only. `apply_strategy_plan`
failing on a custom-column payload today is not a regression of something that
used to work here — it is a path that has never been exercised on this account at
all. Grid-Commander's `openspec/backlog/the-write-paths-are-unverified-at-v19.md`
says the same thing from their side: their `custom-table-probe` has never executed
against v19.

## How to re-run this

There is no script. It is 25 `get_strategy` calls read by eye, which is the
honest cost of an extraction rule that forbids inference. If the roster changes,
re-read it and rewrite the JSON — do not patch the summary block by hand, since
`summary.privateStrategies` is asserted against the platform's own `quota.used`.
