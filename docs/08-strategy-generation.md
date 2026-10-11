# 08 · Strategy Generation

Compose a complete, validated strategy from a thesis — offline.

Everything in docs 00–07 was about *understanding* the system. This is the part that
uses it: `omega.generate` turns a statement of what a strategy believes into a legal
report, an honest scorecard, and a submit-ready payload.

---

## The real strategy shape

Read back from two live strategies (`EL_ALAMEIN`, `MATH-C3`), a strategy is:

```jsonc
{
  "name": "...", "tagline": "...", "description": "...",
  "timeframe": "1h",            // the anchor
  "cadence": "INTRADAY",        // SCALPER at 5m/15m
  "regimeTimeframe": "4h",      // what rel:regime resolves to - strategy config, not anchor-derived
  "marketReadText": "...",      // agent prompt; interpolates {CONDITION_KEY} and {header}
  "sections": [ ... ],
  "conditions": [ ... ],        // the 16-condition DSL
  "signalRules": [ ... ],       // DENSE - all 84, unused ones at allocation 0
                                // (read-back name; the WRITE API calls this array `rules`)
  "minAggregateScore": 0.65,    // THE GATE
  "minRequiredCount": 0,
  // risk block: minAtrPct, stop-loss ATR multiples, R:R, break-even, trailing, time-decay
}
```

Two things worth pinning down:

**`minAggregateScore` is the gate** from [05](05-signal-aggregation-math.md). El Alamein runs
`0.25`; MATH-C3 runs `0.65`. Same maths, very different posture.

**The scorecard is dense.** All 84 signals are always listed; the ones you don't use sit at
`allocation: 0`. So `mtf_*` and `comparison_*` *appear* in every strategy — being listed is
not being fed.

### The condition DSL

Conditions are the 16-condition / 16-clause budget made concrete. From El Alamein:

```jsonc
{
  "conditionKey": "CONFLUENCE_UP",
  "name": "Three of four filters agree - up",
  "definition": {
    "kind": "group", "op": "N_OF", "n": 3,
    "members": [
      {"kind": "clause", "column": {"sectionKey": "includeMacd", "header": "MACD_trend"},
       "op": "is", "label": "rising"},
      {"kind": "clause", "column": {"sectionKey": "includeRsi", "header": "RSI14_now"},
       "op": "gt", "value": 50}
    ]
  },
  "verdict": "UP", "required": false
}
```

Clauses reference `{sectionKey, header}` — which is exactly why the header names in
[03](03-column-compilation.md) matter. The condition key is then interpolated into
`marketReadText` as `{CONFLUENCE_UP}`, so the agent reads the *verdict*, not the raw filters.

`omega.generate` emits `conditions: []`. Conditions are a deliberate authoring act, not
something to synthesise.

## Two entry points

### Forward: from a thesis

```python
from omega.generate import PRESETS, plan
print(plan(PRESETS["mean-reversion"]).render())
```

```
Mean Reversion at Extremes  --  Fade the stretch, only with flow agreeing
anchor 1h | gate 0.65 | 2 sections | 15 columns | 37 headers

weighted signals   22 of 26 in report
  tier 3  (5)  bollinger_cci_overbought, bollinger_cci_oversold, ...
  tier 2  (12)  cvd_bear_divergence, cvd_bearish, ...
  tier 1  (5)  funding_extreme_negative, funding_extreme_positive, ...

all-signals-at-0.75 -> aggregate 75% vs gate 65% -> ROUTES
```

A `Thesis` is modules and weights, nothing more:

```python
Thesis(
    name="Mean Reversion at Extremes",
    gate=0.65,
    weights={"BOLLINGER": 3, "RSI": 2, "CVD": 2, "FUNDING": 1, "VOLATILITY": 1},
    context=["REGIME"],   # reading material, weighted 0 - BattleGrid lists each of its signals
                          # as REPORT_DATA_SIGNAL_OFF; no preset carries one since 2026-10-10 (11)
)
```

Five presets ship: `mean-reversion`, `trend-continuation`, `squeeze-breakout`,
`flow-divergence`, `structure-reversal`.

### Backward: from the signals you want

```python
plan_for_signals(["cvd_bull_divergence", "oi_surge", "mtf_aligned_bull"], name="Demo")
# thesis.description: "unreachable and therefore unallocated: mtf_aligned_bull"
```

It resolves each signal to its module, builds the report that feeds it, and **refuses to
allocate what it cannot feed**.

## What the generator guarantees

Because it composes the rest of the toolkit, every plan is:

- **legal** — columns come from recipes validated against the composability matrix
- **section-clean** — candle and timeframe-inert metrics go in *separate* sections, so the
  candle section stays free to take a timeframe override later ([04](04-section-report-budget.md))
- **honestly allocated** — allocation only goes to signals `membership.py` says are fed
- **in budget** — checked against all seven budgets
- **gate-consistent** — if every weighted signal scored 0.75 and it still wouldn't route,
  the critique says so
- **submit-shaped and compile-viable** — `wire()` is the exact `compile_strategy_plan`
  CREATE request body. Compiled live on 2026-08-28: first refused at ranked/ALL/30 by
  the preview byte cap (BG-14, see [16](16-the-write-path.md)), then **`viable: true`**
  the same day at an explicit 3-ticker selection — the first generated plan ever to
  compile viable. 16 non-blocking advisories; never applied.
- **execution-transparent** — every plan's critique states the effective
  trade-management profile; presets emit no execution parameters, so the MEASURED
  platform defaults apply and are said out loud rather than run on silently
  (Decision 1a, 2026-08-28; `omega/execution.py`). Explicit `Thesis.execution`
  overrides are validated against the measured bounds — with the measured *asymmetry*:
  R:R's catalog bound is enforced on both edges (violations are errors), while
  minAtrPct's is not (0.05 persisted un-clamped; outside-catalog values warn only) —
  see [`bounds_edges_2026-08-28.json`](../data/audit/bounds_edges_2026-08-28.json).
- **anchor-complete** — the four authorable anchors (5m/15m/1h/4h — the platform's
  complete set, measured 2026-08-28) all carry measured cadence, regime timeframe,
  and identical execution defaults; the model refuses to express anything else
  because nothing else can exist.
- **revisable** — `wire_update` re-targets the full body at
  `strategyId`/`expectedRevision`; the Thesis stays the single source of truth and
  the server computes the diff (proven live 2026-08-29: one override in, nothing
  else moved — with the measured caveat that full-body UPDATEs re-mint custom
  section identities in lockstep, see [16](16-the-write-path.md)).

**`coinSelection` defaults class-aware.** Explicit `Thesis.coin_selection` wins;
otherwise ranked at the measured BG-14 boundary (`RANKED_LIMIT_MEASURED_MAX`,
currently **4** — the limit-30 default it replaced could never compile) with category
**CRYPTO** when the thesis weights a crypto-only
module (`CVD`, `FLOW_DIVERGENCE`), else **ALL**. The rationale is trap 11 × trap 21:
crypto-only columns render null off-crypto and null reads FALSE, so a CVD-weighted
thesis defaulted onto stocks would silently never fire. `FUNDING` and `OPEN_INTEREST`
are deliberately *not* crypto-only — synthetic perps carry both everywhere.

None of that answers whether the plan is *worth* accepting.

## Legal is not the same as sound

`omega.validate` answers *"will the platform accept this"*. It cannot answer *"does this
mean what its author thinks"*, and the extraction work has turned up four ways a plan can
pass validation and still be quietly wrong:

| trap | what it does |
|---|---|
| a gate on a label never observed | in an `ALL`, the condition can never fire; in an `N_OF`, the **threshold silently moves**; under a `NOT`, the clause fires *always* |
| `ROC12` | renders a **fraction** while labelled `(%)` — a threshold written as a percent is 100× off ([BG-11](19-is-the-data-correct.md)) |
| `rank_lo` / `rank_near` on a non-negative metric | the **same column** under two names — two of your 32 section slots for one measurement |
| two columns compiling to one header | the platform renders both, then drops the **whole section** from `conditionColumns` |

```bash
python -m scripts.audit_generated_plans
```

Run against the five presets, this finds exactly one: `flow-divergence` gates on
`PERP_SPOT_FLOW is 'perp_led_fragile'`, a label 78 coins × 4 anchors never produced.

**The effect is not what "inert" suggests, and stating it precisely is the point.** The
clause sits inside an `N_OF` needing 2 of 4 members. The condition still fires — what
moves is the threshold. The gate is really **2-of-3**, tighter than the 2-of-4 the thesis
declares. An earlier version of this audit reported it as "reads FALSE forever", which is
true only for a bare clause or an `ALL` member. Same input, three different bugs
depending on where it sits.

It is **not** auto-substituted. Every observed alternative — `neutral`,
`spot_led_accumulation`, `confirmed_bear` — means something materially different from
"perp-led and fragile", so swapping one in would change what the strategy *believes*.
That is the author's call, not the toolkit's. The finding is pinned in
`tests/test_generated_plans_audit.py` so a **new** one fails the suite.

## The critique

```python
plan(thesis).critique()
```

Reports invalid columns, wasted allocation, context-only metrics, budget breaches, token
headroom, an unreachable gate — and one judgement call:

> **correlated oscillators weighted together: BOLLINGER, MFI, RSI, STOCHASTIC — largely one
> piece of evidence counted 4 times**

The platform warns against *"stacking several correlated oscillators as independent
evidence."* Weighting three or more oscillator modules doesn't just cost tokens; because the
aggregate is a weighted **mean**, it triple-counts one observation and crowds out
independent axes — flow, derivatives, structure.

## A limit worth knowing

`simulate_aggregate_score` accepts **at most 20 signals per call**. Real strategies exceed
that — El Alamein weights **32**. So the platform's own what-if tool cannot evaluate a full
production scorecard in one call. `omega.aggregate` has no such limit, and its output is
verified identical to the platform's, so local aggregation is the way to evaluate one.

## Emitting

```python
from omega.generate import emit_plan
emit_plan(plan(PRESETS["squeeze-breakout"]), "squeeze")
# -> out/squeeze.strategy.json   (dense 84-signal scorecard, critique attached)
```

**Nothing is submitted.** The payload is ready; submitting it stays a separate, deliberate
act — and with quota at 24/25, a considered one.

## Verification

All five presets are tested for validity, budget, allocation honesty, gate reachability and
section separation. Every recipe column is checked legal against the composability matrix
and confirmed to actually feed its module. The `squeeze-breakout` plan was submitted to the
live `derive_strategy_rule_view`: **the connector returned exactly the 18 signals the
generator predicted**, signal for signal.

## At contract 91 (2026-10-06): the draft lifecycle

Everything above about `wire()`, `wire_update()`, `operation`, `intentSummary`,
`assumptions` and a compile dry run is history. Contract 85.0.0 removed
`compile_strategy_plan` with no alias: a strategy is created and changed only through its
draft, `get_strategy_draft` → `stage_strategy_draft {strategyId?, draftVersion, axes}` →
`commit_strategy_draft` (README "Contract history — v85"). The input schemas are saved at
[`schema_20261005T194629Z.json`](../data/contract/stage_strategy_draft/schema_20261005T194629Z.json)
(91.0.0); the plan is [`2026-10-06-omega-draft-lifecycle-re-extraction.md`](plans/2026-10-06-omega-draft-lifecycle-re-extraction.md).

| omega | what it is now |
|---|---|
| `plan(t).axes()` | the ten axes of a CREATE stage (no `strategyId`, `draftVersion: 0`), each written WHOLE: `IDENTITY`, `TIMEFRAME_PROFILE`, `REPORT`, `MARKET_READ`, `CONDITIONS`, `ENTRY`, `SETUP_GATES`, `TRADE_LEVEL_POLICY`, `POSITION_MANAGEMENT`, `SIGNAL_RULES` |
| `plan(t).axes_update(current)` | the same without `ENTRY` — an axis a stage omits keeps the draft's value, so an existing strategy's entry is never touched (the 2026-08-29 rule); the dial axes come from `current` unless the thesis names a dial, and the current section keys are carried forward (below, 2026-10-10) |
| `plan(t).preview_request()` | the read-only dry run, `preview_strategy_report {coinSelection, source: {kind: "FIELDS", timeframe, sections, conditions, marketReadText}}` — it judges the report and the conditions, **not** rules, gates or dials; only a stage does, and a stage is a write |
| `emit_plan(...)` | writes the stage request `{draftVersion: 0, axes}` plus `_`-prefixed local metadata, the preview body among it |
| `scripts/preview_dry_run.py` | prints those bodies; `--live` is refused — omega holds no MCP client |

What moved with it, each from the changelog or the schema:

- **`ENTRY` is `{trigger: "ON_CANDLE_CLOSE"}` alone.** v85 refuses either dial on that
  trigger; the server stamps the seeds.
- **`SIGNAL_RULES` allocations are integers 0..3**, and `allocation` and `required` are
  required on every row. The axis replaces only the rows for the signals it names; omega
  still sends the dense 84.
- **Whole axes send every dial.** Decision 1(a) emitted none; the v91 schema requires all
  three `SETUP_GATES`, all three `TRADE_LEVEL_POLICY` and all thirteen `POSITION_MANAGEMENT`
  fields. omega sends the 08-28 measured defaults, plus `decisionInvalidationExitEnabled:
  true`, the value every record on disk carries. What a create draft seeds is unmeasured
  (measurement M1 of the plan), and since v89 a create is judged at the operator bounds
  configured now — so `SCHEMA_BOUNDS` (the retired compile's bounds) only warns.
- **`coinSelection` is no part of a strategy**; it is an input of the preview only.
- **`Thesis.exits`** names condition roles (`UP`, `CORE_DOWN`, …) whose v88 exit rule
  `CLOSE_ON_<key>` is appended after the seven — see [09](09-conditions.md).
- **The preflight** (`scripts/preflight.py`) walks a stage request axis by axis against a
  fresh `stage_strategy_draft` capture; the read-back mirror is retired until a v91
  read-back exists, because every `get_strategy` record on disk predates v84.

Nothing here has been staged, previewed or committed. Measurements M1–M3 in the plan are
each a platform call, and so each is the user's word.

## 2026-10-10: an UPDATE carries the current section keys

The first live UPDATE of a strategy omega had created the day before (battlegrid-manager
`tests/fixtures/2026-10-09-strategy-first-live/action_62_update_stage.json`, staged
2026-10-10 06:33Z) returned a `review.diff` of 14 changes that were not changes:
`REPORT.sections[0].sectionKey: "custom:854d0e89-…" → null`, `sections[1].sectionKey:
"custom:1035fbda-…" → null`, and twelve clause `column.sectionKey`s → null
(`reference-pairs` ×2, `market-breadth` ×2, the strategy's own `custom:854d0e89-…` ×8). A
CREATE sends no key — the server mints a custom section's key and derives a clause's at
commit — and the UPDATE re-sent the same nulls. The commit (`action_63_update_commit.json`,
revision 2) kept every live key, so the diff was cosmetic; but a player approving the card
sees 14 phantom changes, and the manager's rule is that the card is the approval.

`axes_update(current)` now carries the keys forward; `axes()` (a CREATE) is unchanged:

- **REPORT.** A generated custom section takes the `sectionKey` of the current custom
  section with the same `title` (omega writes titles deterministically). When no title
  matches, the counts are equal and the titles are unique on both sides, by position; a
  partial title match carries only what matched. A current section the thesis no longer
  generates is not carried — the platform drops it at commit. Only a key matching the
  schema's `^custom:[0-9a-fA-F-]{36}$` is sent.
- **CONDITIONS.** A generated clause whose `column.sectionKey` is null takes the key of
  the current clause with the same `conditionKey` and the same `header`, when that key names
  where this plan's report resolves the header: an ambient (`reference-pairs`,
  `market-breadth`, `session-field`) or platform section's own key, or — for a custom key —
  the live key of the section carried above, whose current columns must hold a column of
  the same identity (`metric`, `transformId`, `chainedTransformId`, `timeframe`) as the
  generated column that emits the header. A header two sections emit, a key the schema
  refuses (a clause's `column.sectionKey` is a free string of 1–120 characters or null — no
  enum), a differing or missing key: left null, as a CREATE sends it. A key is never
  invented and never copied across conditions.

The committed body read back, `current_7534b2ee_from_get_strategy.json` (manager commit
8450268), sits at
[`data/contract/stage_strategy_draft/current_7534b2ee_from_get_strategy_20261010T0634Z.json`](../data/contract/stage_strategy_draft/current_7534b2ee_from_get_strategy_20261010T0634Z.json);
`tests/test_axes_update_section_keys.py` re-stages the `trend-continuation` preset against
it and asserts `REPORT` and `CONDITIONS` come back identical — the 14 lines collapse to
nothing. Unmeasured: whether the server honours a key sent back on an UPDATE rather than
re-deriving it. The 2026-08-29 compile-path UPDATE re-minted custom keys sent
byte-identical (`LOCKSTEP_REMINT`, [`first_generated_update_2026-08-29.json`](../data/audit/first_generated_update_2026-08-29.json));
the v91 commit of 2026-10-10 kept them through nulls. The next live UPDATE is the
measurement, and it is the user's word.

## 2026-10-11: contract 108 — conditions are the only entry gate

Contract 108.0.0 (live 2026-10-10 21:53Z; README "Contract history — v108", vendored at
`.agents/skills/battlegrid/README.md`, pack 31.2.94) removed signal rules, the aggregate-score
gate and the required-count gate. "A strategy's deterministic entry gate is its conditions: a
required condition, or a condition that carries a verdict. A strategy that declares neither never
trades, and its draft says so with the warning `NO_ENTRY_CONDITION`." The write surface is saved at
[`schema_20261010T215326Z.json`](../data/contract/stage_strategy_draft/schema_20261010T215326Z.json)
(input and output schemas of the six draft tools, from battlegrid-manager's 108 fixture) and the
manifest's `writeSurface` names it; the 91.0.0 capture stays as its `supersedes`. The plan is
[`2026-10-11-omega-v108-conditions-only.md`](plans/2026-10-11-omega-v108-conditions-only.md).
Everything above about `SETUP_GATES`, `SIGNAL_RULES`, the gate, allocations, the dense scorecard
and the scoring-data columns is history.

| omega | at 108 |
|---|---|
| `plan(t).axes()` | **eight** axes: `IDENTITY`, `TIMEFRAME_PROFILE`, `REPORT`, `MARKET_READ`, `CONDITIONS`, `ENTRY`, `TRADE_LEVEL_POLICY`, `POSITION_MANAGEMENT`. v108 refuses `SIGNAL_RULES` and `SETUP_GATES` "as unrecognized keys" |
| `TRADE_LEVEL_POLICY` | `{minAtrPct, minStopLossAtrMultiple, maxStopLossAtrMultiple, minRiskRewardRatio}`, all four required (the ATR floor moved here from `SETUP_GATES`; "a `TRADE_LEVEL_POLICY` stage without it is refused") |
| `plan(t).axes_update(current)` | the axes without `ENTRY`; a dial axis only when the thesis names one of its dials, the rest from `current`. Nothing forces a dial axis any more (`SETUP_GATES` was always staged because it carried the gate). A `current` read before 108 is accepted: its `SETUP_GATES` / `SIGNAL_RULES` are never staged, and `minAtrPct` is taken from the old `SETUP_GATES` when its `TRADE_LEVEL_POLICY` lacks it |
| `plan(t).preview_request()` | unchanged; `preview_strategy_report`'s input schema is identical at 106 and 108 |
| `plan(t).condition_findings()` | adds `NO_ENTRY_CONDITION` as an **error** when no entry condition is `required` or carries a verdict — the platform only warns, but a strategy that can never trade is not a plan |
| `plan(t).entry_gates()` | the conditionKeys that gate entry; `render()` and `authoring.brief()` print them |

**The thesis.** `Thesis` is now, in order: `name, tagline, description, anchor, weights, stance,
context, coin_selection, execution, exits`. Three fields are retired — removed, not aliased; passing
one is a `TypeError`:

- `gate` was `SETUP_GATES.minAggregateScore`; there is no gate to set.
- `required` named signal ids counted into `minRequiredCount`; there are no signal rules
  (`THESIS_UNFEEDABLE_REQUIRED` retired with it).
- `show_scoring_data` added the 2026-10-10 columns showing each weighted signal's data at its rung;
  with no signals they fed nothing.

`weights` keeps its role and its name. **Its keys choose the modules whose recipe columns the REPORT
shows** — the agent's model reads the report — **and the modules whose readings the condition
checklist reads** (directional modules give the `up`/`down` clauses, `TREND_STRENGTH` and
`VOLATILITY` the filters). The tier number (0–3) was also the allocation of every signal in the
module; at 108 it has no platform meaning, is still validated 0–3 so existing theses stay legal, and
is only rendered. `context` keeps its role too: modules whose columns the report shows and the
checklist does not read.

**The presets' entry gates.** Every preset weights at least two directional modules, so
`_build_conditions` already emitted two verdict carriers; nothing in any preset had to change, and
none declares a required condition.

| preset | entry gate | columns 10-10 → 108 | dropped (they only fed signals) |
|---|---|---|---|
| mean-reversion | `MR_UP` (UP), `MR_DOWN` (DOWN) | 17 → 12 | `CCI20`, `BB_WIDTH` @anchor; `RSI14` @regime, @lower; `FUNDING_ANN` @anchor |
| trend-continuation | `TC_UP`, `TC_DOWN` | 14 → 8 | `MA_ALIGN` @regime, @lower; `EMA20`, `EMA_CROSS` @anchor; `ADX` @regime, @lower |
| squeeze-breakout | `SB_UP`, `SB_DOWN` | 12 → 10 | `CCI20`, `BB_WIDTH` @anchor |
| flow-divergence | `SA_UP`, `SA_DOWN` | 11 → 10 | `FUNDING_ANN` @anchor |
| structure-reversal | `SR_UP`, `SR_DOWN` | 13 → 10 | `STRUCT_ZONES` count @regime; `RSI14` @regime, @lower |

The REPORT keeps every module-recipe column (the weighted modules the agent reads and the columns the
conditions read — `tests/test_recipes_rung_gap.py` checks no condition header went with the drop).
Each preset now reads its anchor alone (one distinct timeframe; three before for mean-reversion,
trend-continuation and structure-reversal), and trend-continuation's agent-token estimate falls from
~918 to ~756.

**The critique** lost every signal line: no `wasted allocation`, no `context-only metrics (feed no
signal)`, no `scoring` prediction, no all-signals-at-0.75 aggregate. It gained the entry gate. The
correlated-oscillator warning stays: two oscillators in the `N_OF` checklist still count one piece
of evidence twice.

**History, kept importable, called by nothing on the generation path:** `StrategyPlan._rules()`
(the dense 84-row scorecard), `StrategyPlan.rules` (empty from `plan()`), `signal_rules(thesis)`,
`plan_pre_108(thesis, show_scoring_data=True)` (the v0.3.2 plan, for the measured pre-108
diagnostics), `_scoring_data_columns`, `StrategyPlan.simulate(score, gate=…)`, `membership()`,
`allocation_findings()` (always `[]` now; battlegrid-manager still calls it), `plan_for_signals`,
`AXES_91`, `execution.SETUP_GATE_DIALS`, and the modules `omega.membership`, `omega.scoring`,
`omega.aggregate`. `scripts/compare_vocabulary.py` compares metrics and section keys only (no
`signalId` enum is served), and the preflight fingerprints the eight axes with no signal check.

Nothing here was staged, previewed or committed; no platform call was made.
