# OMEGA v0.13.1 at contract 169.4.0: what 168 served and v0.13.0 left unmeasured

**Record, 2026-11-12.** Contract 169.4.0, build `c9703bf9` (`GET /mcp/version` before and after every live step; it did
not move). Previous pin: v0.13.0 at 168.3.0. Contracts 157 - 169 are not in the vendor README (newest entry v156): the
served schemas, the hints and the platform's own refusals are the source throughout.

v0.13.0 recorded three things 168 served as unmeasured and refused each offline: `spread` as a chain outer after an
average, a spread operand under an average, and the condition group op `SEQUENCE`. This release measures all three on
the live preview and models them. No draft was staged: `preview_strategy_report` shares the stage's condition grammar,
so every probe is a read.

## The platform between 168.3.0 and 169.4.0

- 169.0.0 (02:45Z) added `get_agents_hub`; 169.1.0 (03:25Z) moved `get_agent_coin_qualification`; 169.4.0 (06:15Z)
  reworded descriptions. The manager's watch acknowledged each (no write was blocked).
- The six draft tools are byte-identical to 168.3.0's (`schema_20261112T070510Z.json` against
  `schema_20261111T213257Z.json`); the manager's stored 169.4.0 row agrees on all six.
- All 581 hints re-read at 169.4.0 (extraction 20261112) are identical to 168.3.0's. The corpus did not move; the
  manifest's top block is the 169.4.0 re-read and 168.3.0 is its `supersedes`.

## What was measured

| Probe | Record | Previews |
| --- | --- | --- |
| `spread` after aggregate / ema / rma / wma (group V) and the averaged operand (group W) | `data/audit/authoring_probe_169_2026-11-12.json` | 54 |
| joint depth when both sides average (group J) | `data/audit/authoring_probe_169_2026-11-12-c.json` | 7 |
| `SEQUENCE`, rounds 1 - 7: the rule, exits, references, the frame-read count | `data/audit/sequence_probe_169_2026-11-12{,-b..-g}.json` | 57 |
| the 660 chained-spread shapes, coin and market sections | `data/audit/coverage_sweep_2026-11-12{,-market}.json` | 6 |

### Spread after an average (`<metric> x aggregate|ema|rma|wma -> spread`)

- One operand, at the column's own timeframe, from the inner's served `chainedOuters.spread.operands` (off the anchor
  rung `operandsOffAnchor`). The base itself is not one: "spread operand 'CLOSE' is not a legal relational operand".
  A level read per anchor bar meets it only at the anchor.
- The inner keeps its standalone window maximum (2436 aggregate and wma, 704 ema, 308 rma). No `chainedWindow`, no
  `offset`. Both `bars` values render (`_dev` in the base).
- Header: the inner's header, the operand, `_spread` - `close_ema20_EMA50_spread`, `RSI14_mean14_RSI7_spread`,
  `close_4h_ema20_SMA20_spread`; an omitted inner window spells the catalogue default.
- An averaged operand works here too, except the chain's own average: "a spread against itself is identically zero".
- Not after distance or zscore (not in their successors).

### A spread operand under an average (`inputs[]` `{metric, transformId, window}`)

- `transformId` and `window` both or neither; `transformId` one of aggregate / ema / rma / wma; `window` at least 2.
- The window's maximum is the depth of a standalone column (2436 / 704 / 2436 / 308). Depth is judged per side, never
  jointly: `close_ema704_close_mean2436_spread` renders, and an operand's own lookback does not shorten it (SMA200 under
  aggregate 2436).
- The operand must be in the base's served `spreadAverageOperands` (off the anchor, `...OffAnchor`): the base and its
  per-bar candle-valued operands, no timeless level, no MARK.
- Header: `<operand code>_<mean|ema|rma|wma><window>` in the operand place - `close_close_ema20_spread`.
- No outer chains over it: "the comparison is read frame by frame, and no rank or series outer chains over it".
- As a trade level: not counted. An averaged operand, or the operand of a chained spread, stays unmeasured as a
  level reading (`omega/trade_levels.py`).

### `SEQUENCE`

The platform states the rule itself (`CONDITION_SEQUENCE_INVALID`): "a SEQUENCE is a condition's whole definition, holds
Once, carries a window 'within' of at least 2, and orders at least 2 steps - each a clause, a group of clauses, or a
reference to a condition that reads one bar - every step and row held Once". Measured around it:

- `within` is required; above it, the bound is each step column's stored history - its served
  `conditionHold.maxWindow` (2449 for `MACDhist_trend` at 1h, 2499 for `MAalign`). OMEGA refuses `within` past 2499,
  the longest history measured behind any column (the readable depth is 2500 bars), and leaves a step column's own
  bound below that to the builder, as it does a hold's `of`.
- No `n` ("belongs to N_OF only"); only a sequence carries `within`; a sequence nested in any group is refused with
  "make it its own condition and reference it from this group" - and that reference renders.
- Steps: clauses, ALL / ANY / N_OF / NOT groups of clauses, or a reference to a condition that reads one bar (no group
  in a group, nothing held). A reference inside a step group is refused.
- Entry only: an exit rule can neither be a sequence nor read one (`CONDITION_EXIT_SEQUENCE_UNSUPPORTED`). Any
  verdict, `required` either way.
- The preview's evidence for a sequence: `{within, timeframe, outcome, steps[{outcome, matchedBar{timeframe,
  closesBack} | null, reference}], memberCount}`.

### The condition frame-read budget (5048)

"the closes each clause's hold counts, plus the bar before for a prior-bar operator, summed". From the counts the
refusals state, over the preset's 11 one-bar clauses:

- each clause counts the `of` of the outermost hold above Once on its path, else its own (a group held above Once
  requires its rows held Once anyway);
- a prior-bar operator adds one close in total, not one per bar;
- a sequence's `within` is the window of every clause of its steps; a reference step reads the referenced condition
  on every bar of the window; a reference member of a plain group costs nothing.

OMEGA did not count frame reads before this release. `validate_conditions` now refuses a set over the served budget.

## Where OMEGA holds it

| Rule | Code |
| --- | --- |
| averaged operand type | `omega/types.py` `Operand.transformId` / `window` / `averaged` |
| its lists | `omega/contract.py` `Metric.spread_average_operands` / `_off_anchor` |
| the column rules | `omega/validate.py` `_averaged_operand`, `_chained_spread_operand` |
| the headers | `omega/fanout.py` `operand_token`, the `spread` chain outer in `outputs_for` |
| the space | `omega/space.py`: the 660 chained-spread shapes (first served operand; every operand when expanded) |
| `SEQUENCE` | `omega/conditions.py` `sequence`, `_step_problem`, `_walk_sequence`, the exit check |
| frame reads | `omega/conditions.py` `frame_reads` |
| replay of every probe | `tests/test_v169.py` |

## Coverage

Structural coverage 24,239 / 24,239 (23,579 before + the 660 chained-spread shapes, all rendered: 620 coin, 40 market,
0 refusals, 0 mispredicted). The expanded space grows by 161,516 chained-spread operand pairs; like the plain spread's
operand pairs, they re-mint a rendered pattern with another operand code and stay outside the sweep (the deliberate
stop, `tests/test_render_coverage.py`).

## Reviewed

An independent review of the diff (2026-11-12) found no fail-open hole in the measured rules and four points, all
fixed: `within` past every measured history was accepted offline (now refused past 2499); a member that is not an
object crashed the condition walker (now a finding, in a sequence and in a plain group); an operand carrying only a
`window` counted as a plain level reading (now unmeasured); an averaged operand on a transform that takes no operand
was only a warning (now refused: it was measured on `spread` only). Each is pinned at the end of `tests/test_v169.py`.
Suite: 2344 passed, 1 skipped.

## Not done here

- The per-column bounds a preview serves (`conditionHold.maxWindow`) are still not stored offline; the builder judges a
  hold's `of` and a sequence's `within` against them.
- A reference step to a condition of more than one row is counted `within` x rows; only one row was measured.
- No preset uses `SEQUENCE` or an averaged operand yet: this release makes them authorable and judged.
