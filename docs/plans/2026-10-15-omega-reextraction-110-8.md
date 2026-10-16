# The metric corpus re-extracted at contract 110.8.0 — record

**Status: DONE 2026-10-15** on branch `feat/reextract-110-8`. Baseline main (v0.7.1): 1459 passed; after: **1462 passed**.

## Why

BattleGrid moved 110.2.0 → 110.3.0 (2026-10-14 09:22Z) → 110.4.0 → 110.7.0 → 110.8.0 (18:42Z), then three build-only
redeploys (last `6cf1bd70`, 2026-10-15 01:52Z). The battlegrid-manager watch acknowledged each step itself (nothing it
calls moved unsafely), so writes never blocked - but `manager strategy status` read six VOCABULARY_MOVED warnings: the
platform served metric keys omega v0.7.1 had never extracted. The manager's review: its
`docs/status/2026-10-15-battlegrid-110-8-0-review.md`. The vendor changelog documents only v110.6 ("the Donchian channel
as of the bar before").

## Route

Every call read-only, over the `mcporter` CLI to `battlegrid-anbu` through the allowlisted `bg.py`. No stage, commit,
bind or trade.

1. The write surface: the 110.8.0 `stage_strategy_draft` family copied from the manager's stored surface (its fixture
   `tests/fixtures/2026-10-15-surface-110.8.0/manager_schemas.json`, manager commit 2825893) to
   `data/contract/stage_strategy_draft/schema_20261015T015244Z.json`; the manifest names it, the 110.2.0 capture nested
   under `supersedes`; the condition vocabulary re-derived: **183** column metrics.
2. `get_metric_construction_hints` × 183 (two workers, 0 failed), then `scripts/refresh_metric_contracts.py`
   (EXTRACTION_STAMP 20261015, archive 20261014): **retired none, six added**; every transform's authoring block
   invariant; the catalogue's `levelInteraction` authoring text changed (README v110.6: the level in force when the bar
   opened), its schema did not.
3. `list_strategy_categories` + `list_strategy_vocabulary` × 10 (saved to `data/contract/vocabulary/20261015T0412Z/`):
   only `structure` moved, 48 → 54 (the six keys, a new `singlePrints` study, the Donchian study's gloss); no platform or
   custom template moved; **no `kind: "saved"` template** - the account holds no saved section.
4. `scripts/build_corpus.py` (183/183 reconcile; 731/2,928 cells legal); the render-coverage sweep
   (`SWEEP_DATE=2026-10-15`): **1,154 shapes, 1,738 headers, 0 refusals, 0 predicted-but-not-rendered** - omega.fanout named
   every new header (`donchianHiPrior_lvl`, `dist_tpoSpAbove`, ...) right on the first pass.
5. The vendored skill pack refreshed 31.2.98 → **31.2.103** (battlegrid-mcp `f23f7f8`, skills exported at 110.4.0):
   documentation only (MACD_HIST/PPO_HIST in the examples, the Market Grid entry draft, the Radar summary's `agentId`, a
   building block gates nothing unless itself `required`); the proxy changed only its version string. `skills-lock.json`
   hash = the skills CLI's `computeSkillFolderHash` over this machine's checkout (as for 31.2.98), equal to a fresh clone
   of `f23f7f8`.

## What moved (measured)

- **Added** (none retired - `data/contract/metrics/_moves_110_8.json`, glosses verbatim from the hints):
  `DONCHIAN_UPPER_PRIOR` / `DONCHIAN_LOWER_PRIOR` (`donchianHiPrior` / `donchianLoPrior`, candle; Pine
  `ta.highest(high,20)[1]` / `ta.lowest(low,20)[1]`; value, trajectory, distance, spread, aggregate, efficiency,
  levelInteraction) and the four single-print zone edges `TPO_SINGLE_PRINT_ABOVE/BELOW` (`tpoSpAbove/Below`, the
  current UTC session's letter profile) and `NAKED_SINGLE_PRINT_ABOVE/BELOW` (`nSpAbove/Below`, an earlier session's zone
  no later trading touched) - timeless; value, distance, spread only.
- **Cells** 705 → **731** (+26). **Structural shapes** 947 → **981** (atoms 731, chained 250: the Donchian edges'
  distance and spread chains). **Operand-expanded** 9,103 → **10,257**. **Timeless** 83 → **87**.
- **`levelInteraction`** on 44 → **46** levels (the two prior-bar Donchian edges, as v110.6 says).

## What omega does about it

- Nothing is refused that was allowed: no new `METRIC_RETIRED`. The history tests read `_moves_110_8.json`'s `added` as
  never probed (no signal module exists since 108).
- `tests/test_saved_sections_110.py`: a player's saved section (`kind: "saved"`, account state since 110.x) never enters a
  stored vocabulary snapshot or the platform templates.
- The battlegrid-manager re-pins to this tag; its preflight then reads `pin drift: none` at 110.8.0.

## After: contract 110.9-110.11 (reviewed 2026-10-16 by battlegrid-manager, `docs/status/2026-10-16-battlegrid-110-11-0-review.md`)

No enum moved (`pin drift: none`), so no re-extraction. One served meaning moved, behind an unchanged schema (README
"Contract history - v110.9"): `PRICE_ZONE` classifies against the channel of the 20 bars BEFORE the classified one
(`DONCHIAN_UPPER_PRIOR`/`LOWER_PRIOR`); `breakout high`/`breakdown low` can now hold (a close beyond that channel);
`near high`/`near low` are the outer fifth of the channel by position (before: within 1 % of price of an edge). The
hints' gloss read 2026-10-16: "price location against the channel of the 20 bars before this one, near an edge in its
outer 20%". omega stores no gloss for the metric and its vocabulary is unchanged, but `omega.generate`'s
SUPPORT_RESISTANCE module reads `zone is "near low"` (up) / `"near high"` (down): a body that weights that module now
fires on the outer fifth of the prior channel - a wider trigger than when it was written. No live strategy weights it
(10-16: VWAP Reject 4h, Trend Continuation, VWAP Reject 15m carry no PRICE_ZONE column).

## After: contract v111 / 110.13.0 (2026-10-16)

Served as 110.13.0 (build `86df42d3`) since 2026-10-16 03:18Z. README "Contract history - v111": every draft-lifecycle
tool takes its id, `draftVersion` and payload as top-level arguments; a call that still wraps them in `request` is
refused, and a refusal's path into the payload loses its leading `request`. `request` stays only on
get_strategy_section_template, preview_radar_resolution, preview_deployment_resolution and test_generate_deployment_grid.

**Measured against the 110.8.0 capture** (`schema_20261016T031811Z.json`, read from battlegrid-manager's stored
surface, observed 2026-10-16T03:18:11Z; no platform call by omega):

- `stage_strategy_draft` input: `{strategyId?, draftVersion, axes}` at the root, `required [draftVersion, axes]`,
  `additionalProperties: false`. With the 110.8.0 local `$ref`s re-rooted (`#/properties/request/...` → `#/...`) the
  110.8.0 `request` object and the 110.13.0 input are identical: no axis, enum or bound moved
  (`tests/test_condition_vocabulary_108.py::test_v111_moved_no_column_enum_only_the_envelope`). get_strategy_draft,
  commit_strategy_draft and list_strategy_drafts lost the envelope the same way; preview_strategy_report and
  get_strategy never had one and did not move. No output schema moved.
- No vocabulary moved, so no re-extraction: 183 metrics, the same transform enums, 25 platform sections.

**What omega changed** (branch `fix/v111-flat-write-surface`):

- The manifest's `writeSurface` names the 110.13.0 capture; 110.8.0 → 110.2.0 → 108.0.0 → 91.0.0 are kept under
  `supersedes`, each still read through its own envelope.
- `omega.preflight.resolve_request` and `omega.condition_vocabulary` read both shapes (the envelope when the schema has
  one, else the root); `data/derived/condition_vocabulary_108.json` re-derived (its pointers lost `/properties/request`).
- The body omega emits was already the stage's arguments: `emit_plan` writes `{draftVersion: 0, axes}` (plus
  `_`-prefixed local metadata, never sent), `scripts/tpo_suite_build.py` writes `{draftVersion: 0, axes}`.
  `scripts/preview_dry_run.py stage` printed `{request: {...}}` and now prints the flat arguments.
  `scripts/preflight.py` still unwraps a pre-v111 body file.
- Tests walk the flat body against the 110.13.0 schema and pin that the 110.8.0 envelope is refused by it
  (`UNDECLARED request`, `MISSING_REQUIRED draftVersion/axes`) while the flat body is refused by the 110.8.0 one
  (`MISSING_REQUIRED request`).

**What a consumer must change** (battlegrid-manager): send the stage, get, commit, discard and list draft calls with
flat arguments, `stage_strategy_draft {strategyId?, draftVersion, axes}` (`omega.generate.StrategyPlan.axes()` /
`axes_update()` unchanged); read the axis schemas through `omega.preflight.resolve_axes` (or the flat
`properties.axes.properties`) rather than `properties.request.properties.axes.properties`; and re-pin to an omega tag
that carries this change - the earlier `resolve_request` raises `KeyError: 'request'` on a 110.13.0 surface, which
breaks the manager's pin-drift check (`scripts/compare_vocabulary.py`).
