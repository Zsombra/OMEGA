# OMEGA

**The BattleGrid Strategy Builder column system: extracted, classified, documented, and
made buildable offline.**

The Strategy Builder lets you define custom report columns — your own data points — that
feed the Strategy Report an intelligence agent reads before it makes a pick. The rules
governing which columns are *legal*, what *maths* each performs, how many *values* one
column actually produces, and how those roll up into a routing decision were scattered
across ten MCP discovery tools and written down nowhere.

This repository extracts the whole contract from the live connector, classifies every
dimension of it, documents the underlying maths, and ships a Python toolkit that validates
a proposed column **before** it touches your account — and a generator that composes whole
strategies from a thesis.

> **Read-only by construction.** Nothing here calls a BattleGrid write tool. The toolkit
> emits a submit-ready payload to `out/`; submitting stays a separate, human-initiated act.
> Private-strategy quota at extraction: **24/25 used, untouched**.

---

## Start here

**[docs/00-mental-model.md](docs/00-mental-model.md)** — the seven layers, end to end.

| | |
|---|---|
| [01 · Metric Layer](docs/01-metric-layer.md) | all 86 metrics, classified by family, kind, unit, timeframe mode |
| [02 · Transform Layer](docs/02-transform-layer.md) | all 16 transforms: formulas, parameters, null behaviour, spread pools, privilege |
| [03 · Column Compilation](docs/03-column-compilation.md) | how a column becomes output headers; fan-out; chaining; naming |
| [04 · Sections & Budgets](docs/04-section-report-budget.md) | composition rules, timeframe resolution, what actually costs you |
| [05 · Aggregation Math](docs/05-signal-aggregation-math.md) | the scoring derivation and what follows from it |
| [06 · Cookbook](docs/06-cookbook.md) | recipes that compile, and ten traps |
| [07 · Signal Membership](docs/07-signal-membership.md) | which of the 84 signals your report can actually feed — offline |
| [08 · Strategy Generation](docs/08-strategy-generation.md) | compose a complete validated strategy from a thesis |
| [09 · Conditions](docs/09-conditions.md) | the condition DSL, ambient headers, and offline type-checking |
| [10 · Outcome Feedback](docs/10-outcome-feedback.md) | which signals earned their allocation — and when to refuse to say |
| [11 · Signal Scoring](docs/11-signal-scoring.md) | how a raw indicator reading becomes the 0–1 number that gets aggregated |
| [12 · Routing Feasibility](docs/12-routing-feasibility.md) | would this strategy route — and which signals are holding it back |
| [13 · Temporal Spread](docs/13-temporal-spread.md) | the second axis: what survives across time, and what was one instant |

## What the extraction found

| | |
|---|---|
| Metrics | **86** across 10 families |
| Authorable transforms | **16** |
| Composability matrix | **322 / 1,376 cells legal — 23.4% density** |
| Platform-privileged pairs | **4** (used by preset sections, denied to authors) |
| Platform section templates | 25, spanning 124 columns over 74 metrics |
| Compiler probes | 20, all matching the derived matrix |
| Membership probes | 24, mapping 52 metrics to 17 signal modules |

Seven findings that shape everything:

1. **The metric×transform matrix is a sparse partial function.** `ADX × classifyState` is
   rejected — yet `includeTrendStrength` uses exactly that pair. Some pairs are reserved
   for the platform.
2. **One column ≠ one data point.** `RSI14 × trajectory × window:4` compiles to **5**
   headers. Fan-out, not column count, spends the ~16,000-token report budget.
3. **The aggregation math is an allocation-weighted mean**, reverse-engineered by probe and
   confirmed exactly: `Σ(score×alloc)/Σ(alloc) ≥ gate`. **Tier 0 carries zero weight.**
4. **Timeframe-inert metrics can't sit in a section with a timeframe override** — a
   section-level rule invisible from metric contracts alone.
5. **Signal membership is module-level, and 34 of 86 metrics feed no signal at all** —
   including `VWAP`, `CLOSE_CHANGE`, `TRADES` and every crowd and derived metric. Weighting
   a signal your report can't feed adds to the aggregation denominator and *suppresses*
   your score.
6. **Conditions are advisory, not a gate** — *"they may make you more selective, never
   less."* And three ambient sections (`session-field`, `market-breadth`,
   `reference-pairs`) are referenceable for free, costing nothing against your budget.
7. **There is no realised outcome data to learn from yet.** 23 of 24 agents have never
   evaluated anything; the one with history has 18 closed trades against a platform
   minimum sample of 20. `omega/performance.py` is built and gated accordingly — it
   returns *no* recommendation rather than a confident one drawn from noise.

## Toolkit

```bash
pip install -e ".[dev]"
PYTHONPATH=. python examples/build_section.py
```

```python
from omega.types import Column, CustomSection, Report
from omega.validate import validate_report
from omega.fanout import cost_report, outputs_for
from omega.emit import emit

panel = CustomSection(title="MR Stretch Panel", benchmarkTicker=None, columns=[
    Column(metric="VWAP", transformId="distance", timeframe={"rel": "anchor"}),
    Column(metric="RSI14", transformId="trajectory",
           timeframe={"rel": "anchor"}, window=4, bars="closed"),
])
report = Report(anchor="1h", sections=[panel])

print(validate_report(report).report())   # composability, operands, orderings, chains, budgets
print(cost_report(report).render())       # headers + token cost vs all 7 budgets
emit(report, "mr-panel")                  # -> out/mr-panel.json  (NOT submitted)
```

| Module | Responsibility |
|---|---|
| `omega/contract.py` | load the corpus snapshot |
| `omega/types.py` | pydantic models mirroring the MCP JSON Schemas |
| `omega/validate.py` | offline pre-flight — catches errors without a round-trip |
| `omega/fanout.py` | predict headers, cost the report against every budget |
| `omega/aggregate.py` | the scoring math, `minimum_score_to_route` inversion |
| `omega/membership.py` | predict signal membership offline; flag allocation that can't be fed |
| `omega/conditions.py` | condition DSL builders; type-check clauses against real headers |
| `omega/generate.py` | compose a whole strategy from a thesis; critique it |
| `omega/performance.py` | per-signal edge from realised trades; refuses to rate a small sample |
| `omega/emit.py` | write a validated payload to `out/` — never submits |

## Layout

```
data/contract/     raw extraction (metrics, transforms, templates, categories) + _manifest.json
data/performance/  one real signal-log/outcome pair (parser fixture)
data/derived/      composability matrix, spread graph, type system, privileged pairs,
                   composition rules, compiler probes, aggregate oracle,
                   signal module map
docs/              00–13
omega/             the toolkit
scripts/           build_corpus.py, build_docs.py, write_manifest.py
examples/          build_section.py, build_strategy.py
tests/             305 tests, incl. 20 compiler + 22 membership probes replayed
```

`data/contract/` is raw extracted fact. `data/derived/` is analysis computed from it.
Docs 01 and 02 are **generated** — regenerate rather than hand-editing:

```bash
PYTHONPATH=. python scripts/build_corpus.py && PYTHONPATH=. python scripts/build_docs.py
```

## Verification

```bash
python -m pytest tests/ -q     # 305 passed
```

- 86/86 metrics; all 10 family counts reconcile with the connector
- 20/20 compiler probes: the validator's verdict matches the live compiler
- every predicted header string matches the compiler's `outputs[]` exactly
- aggregation matches `simulate_aggregate_score` to the last digit
- spread pools verified symmetric and self-excluding
- all 22 membership probes replay against the offline predictor, module-for-module
- the generated `squeeze-breakout` strategy's predicted membership matches the live
  connector exactly — 18 signals, signal for signal
- the membership map independently reproduces two production strategies' scorecards:
  `EL_ALAMEIN` (32 non-zero allocations) and `MATH-C3` (15)
- generated conditions and `marketReadText` verified against a live
  `preview_strategy_report` render: every clause resolved, both markers referenceable
- the generated condition DAG resolves live — `conditionRef` composes, and the ambient
  context layers cost zero columns

## Caveat

The corpus is a **dated snapshot of a live system** (`data/contract/_manifest.json`). The
connector's own instructions warn that cached capability lists stop being authoritative
after a deployment. Re-run `scripts/build_corpus.py` against a fresh extraction before
trusting the matrix on a changed platform.
