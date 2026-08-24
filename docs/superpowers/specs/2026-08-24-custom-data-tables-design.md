# Custom Data Tables — Design

**Date:** 2026-08-24
**Status:** approved, pending implementation plan

## Goal

One loop for working with BattleGrid custom report columns:

1. **Explore** — see what tables are possible, not just the eight the cookbook happens to document.
2. **Explain** — for any column, the exact mathematical transformation and the real numbers it produces.
3. **Author** — emit a validated column.

Driven from a Python API with a CLI over it. No browser artifact.

## Governing principle: extract, never compute

Every formula and every number comes from BattleGrid verbatim. OMEGA enumerates, caches,
and organises — it does not evaluate and it does not infer.

This is the project's founding rule (doc 00: *"the corpus is extracted rather than
inferred"*), and it is load-bearing here for a specific reason: the platform's own formula
text contains at least one known error, and the parameter defaults are not guessable. Both
are recorded below.

An earlier draft of this design proposed reimplementing the 16 transform formulas in
Python from doc 02's prose. That was wrong on both counts — the math is already extracted,
and prose is exactly the wrong source.

## What already exists — do not rebuild

| asset | contents |
|---|---|
| `data/contract/transforms/_authoring.json` | **all 16** transform authoring contracts — `parameters` (with defaults), `calculationSummary`, `formula`, `operandOrder`, `nullBehavior`. Extracted verbatim. |
| `data/contract/metrics/*.json` | 86 metric contracts — family, `nativeOutput`, `timeframeMode`, offered transforms, `spreadOperands`, `rankOrderings` |
| `data/derived/composability_matrix.csv` | all 1376 metric × transform pairs scored; **322 legal** |
| `data/derived/composition_rules.json` | chaining (2 stages), fan-out, header naming, rank universes, null sentinel |
| `data/derived/compiler_probes.json` | 20 legality/header cases captured from the live compiler |
| `omega/validate.py`, `fanout.py`, `emit.py` | legality checking, header/cost prediction, payload emission |

**Verified invariant** (recorded in `_authoring.json`): for a given `transformId`, the
`authoring` block is byte-identical regardless of which metric it is attached to. This is
why authoring contracts are stored once rather than per-metric. Re-confirmed against the
live connector on 2026-08-24 — the stored `trajectory` formula matches byte-for-byte.

## The space

| level | count |
|---|---|
| metric × transform pairs | 1376 |
| **legal atoms** | **322** |
| atoms accepting a chained stage | 52 (42 × 3 successors, 10 × 4 including `rank`) |
| **structural shapes** (atom + chain) | **488** |
| expanded by spread operand and rank ordering | **2200** |
| documented in the cookbook | **8** |

`data/contract/templates/platform/_all.json` holds the platform's own **25** templates,
carrying **124** column definitions between them. That makes "unused region of the space"
computable against what BattleGrid itself ships, rather than against the 8 cookbook
recipes — a far stronger signal for the *what haven't I thought of* question, and it costs
nothing because the data is already extracted.

Chaining is capped at **2 stages** (`composition_rules.chaining.stages`), which is what
makes the space finite and enumerable rather than open-ended.

Parameters are **not** included in the 2200 and must not be: `window` is 1–64, `offset`
0–64, `bars` is one of `closed` or `all`, and `inputs` takes up to 4 metrics. Materialising
that cross-product would produce millions of rows of no value.

**Design consequence:** enumerate *shapes*; treat parameters as axes varied on a chosen
shape. `space.py` returns shapes; `probe.py` resolves a shape plus concrete parameters into
a compiled contract.

## Architecture

Three new modules, each with one job.

### `omega/space.py` — enumeration and query

Builds `ColumnSpec` objects from the existing contract corpus. No network.

- `enumerate_shapes(expand_operands: bool = False)` returns the 488 structural shapes;
  with `expand_operands=True` it returns the 2200 forms with spread operands and rank
  orderings enumerated. One function, one flag — not two entry points.
- `query(...)` filters by family, output kind, unit, timeframe mode, header cost, chain
  depth, and platform-template usage.

Depends on `contract.py`. Tested by count invariants and by agreeing with `validate.py` on
the legality of all 322 atoms.

### `omega/probe.py` — the one-to-one bridge

The only module that talks to BattleGrid. Both calls are read-only.

- `column_contract(spec)` calls `get_strategy_column_contract`. Returns
  `effectiveParameters`, resolved output headers with types and `meaning`, `operandOrder`,
  `formula`, `calculationSummary`, `glossary`, `nullBehavior`, and timeframe resolution. It
  reads no market values.
- `render(specs, coins, timeframe)` calls `preview_strategy_report`. Returns live computed
  values. Documented as rendering *"without saving or mutating strategy state"* — no write,
  no strategy slot, no quota.

Both responses are cached verbatim to `data/contract/columns/`. Nothing is normalised on
the way in; interpretation happens at read time.

### `omega/explain.py` — the trace

Assembles, for one spec, a readable account from three stored sources:

1. the transform authoring contract (formula, parameters, `nullBehavior`),
2. the compiled column contract (effective parameters, headers, glossary),
3. rendered live values, where a render exists.

Computes nothing. Where a piece is missing it says so rather than filling the gap.

### Authoring

No new module. A `ColumnSpec` goes through the existing
`validate.py` to `fanout.py` to `emit.py` path.

### CLI

```
python -m omega.table explore  --family volumeFlow --max-headers 1
python -m omega.table explain  EMA5 spread:EMA13 --chain trajectory --window 4
python -m omega.table author   EMA5 spread:EMA13 --chain trajectory --out out/
```

## Two facts that force design decisions

### Defaults are not guessable

A contract request passing neither `window` nor `bars` came back with
`effectiveParameters: {window: 4, bars: "all", offset: null, ...}`. `trajectory` defaults to
window **4**; `efficiency` to **21**; `bars` defaults to **`all`**, which includes the live
forming bar — the cookbook's trap #1.

`explain` must therefore always report **effective** parameters from the compiled contract,
never the parameters the caller supplied.

### The platform's formula text contains a known error

For a chained `spread` into `trajectory`, the live contract returns:

```
output = (EMA5 - EMA13) / EMA13 × 100; slots = last 4 non-null EMA5 values; trend = compare(first, last)
```

The slots hold the **spread** series, not raw EMA5 values. This is recorded in
`composition_rules.chaining.knownDocDefect` and was re-confirmed live on 2026-08-24.

**Policy:** store the platform's text verbatim and attach the correction as a separate
annotation. Never silently repair it. One-to-one means the stored text is what BattleGrid
says; the annotation is what we know about it. A reader must be able to see both.

The same policy covers `classifyState`, already recorded as `PLATFORM_ONLY` — used by five
platform templates but rejected for authoring with `REPORT_COLUMN_PAIR_UNSUPPORTED`.

## The one real gap

Nothing in the repo holds a **rendered column value**. `compiler_probes.json` stores
legality verdicts and header names; the scorecard captures store signal scores. No file
anywhere holds a number produced by a custom column.

`preview_strategy_report` closes this for free. Landing the first real rendered values is
the highest-value single step in this design.

## Testing

- **Enumeration** — counts pinned (1376 / 322 / 488 / 2200); `space.py` legality agrees
  with `validate.py` on every atom.
- **Drift** — stored authoring contracts re-verified against the live connector, the way
  `_authoring.json`'s invariant was established. A failing drift test is a signal the
  platform changed, not a bug.
- **Probe fixtures** — every cached contract replays offline; `explain` output is asserted
  against stored fixtures, not live calls.
- **Honesty** — `explain` on a spec with no render must report the absence, and a test
  asserts it does not fabricate a value.

## Scope of the first cut

`space.py` and `probe.py`, exercised on a handful of shapes chosen to span the interesting
cases: an atom, a chained shape, a fan-out (`trajectory`), and one of the 10 `rank`-chain
shapes. Enough to prove the round-trip and land the repo's first rendered column values.

`explain.py`, the CLI, and full enumeration follow once the round-trip is proven.

## Out of scope

- Any local evaluation of transform math. The platform computes; we cache.
- Intent-driven semantic search over the space. Deferred until the space has been browsed.
- The browser artifact. `matrix.html` stays as-is.
- Any write to BattleGrid. Strategy quota stays at 24/25, agent slots at 24/24.
