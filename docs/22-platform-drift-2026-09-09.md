# 22 · Platform drift, measured 2026-09-09 (contract 54.1.0)

What changed between the 2026-09-05 sweep (doc 21) and today, what it broke in this
repository, and what was done about it. Everything below was measured with read-only calls;
nothing was compiled, applied, forked, bound or deployed.

**The deployed contract moved 51.0.0 → 54.1.0 in three days.** `GET https://mcp.battlegrid.trade/mcp/version`
answered `51.0.0` on 2026-09-06T03:38Z and `54.1.0` on 2026-09-09T08:03Z (build `37cb29b6`).

## 1. The change that broke us: `entry.levelSource` is gone

Removed from the entry object on all three arms (CREATE, UPDATE, RESTORE); the vendor README
dates it to contract 52.0.0. `omega.generate` had emitted a seven-key entry since 2026-08-30,
so **every compile this repository could have produced would have been refused as an unknown
key.** The platform now derives the level from the trigger and the trade's direction.

Fixed in `omega/generate.py` (six keys) and `omega/preflight.py` (`MIRROR_ENTRY_FIELDS` no
longer mirrors it). The gap that let it through is closed by
`tests/test_write_surface.py::test_wire_entry_keys_match_the_live_schema_capture`, which pins
the emitted entry object against the captured schema in both directions — nothing had ever
compared them, so a removed key could only have surfaced as a rejected compile.

## 2. `SWING_HIGH` / `SWING_LOW` were renamed, not removed

To `DONCHIAN_UPPER` / `DONCHIAN_LOWER` at contract 53.0.0. Measured as a pure rename: identical
`nativeOutput`, `timeframeMode` and transform set. What moves with it is the **header stem** —
`swingHi` → `donchianHi`, `swingLo` → `donchianLo` — so a condition matching the old header is
dead. The label changed from "Swing high" to "20-bar high", which is what the indicator always
was: the highest high of the last 20 closed bars.

The platform's own `includeSupportResistance` template now names the new metrics. Renamed here
in the generator's `SUPPORT_RESISTANCE` recipe, `scripts/build_corpus.py`, the signal-module
map, the indicator-family census and the tier-C verdict record. Historical audit records that
name the old metrics were **not** rewritten — they record what was sent or measured on a date.

## 3. Nine market-profile (TPO) metrics, undocumented by the vendor

| metric | header | what the platform's own glossary says |
|---|---|---|
| `TPO_POC` | `tpoPOC` | price bin holding the most time in the current UTC session, 5-bps bins; absent for the session's first 60 minutes |
| `TPO_VAH` / `TPO_VAL` | `tpoVAH` / `tpoVAL` | edges of the 70 % value area around that point of control |
| `TPO_IB_HIGH` / `TPO_IB_LOW` | `tpoIBH` / `tpoIBL` | high and low of the session's first 60 minutes; absent until that opening range closes |
| `TPO_SHAPE` | `tpoShape` | where the point of control sits in the value area — `p-shape` at or above 0.67 of its span, `b-shape` at the mirror, else `balanced` |
| `PRIOR_TPO_POC` / `VAH` / `VAL` | `pTpoPOC` / `pTpoVAH` / `pTpoVAL` | the same three reads for the previous completed UTC session |

All are timeless and price-unit except `TPO_SHAPE`, which is a classification. **The vendor's
own documentation does not mention them at all** — no `TPO`, no "value area", no "point of
control" anywhere in the installed package, and no 54.1.0 entry in its contract history. We
have them only by extraction, which is the case the repository exists to make.

**Rendered live** (`data/contract/columns/new_metrics_54_1_0_probe_2026-09-09.json`): all eleven
new metrics compile and are gateable. The current-session reads and both Donchian edges returned
real values on BTC and ETH. **The three prior-session reads returned the null sentinel on both
coins.** The cause was not determined and is not guessed at here — the glossary says "previous
completed UTC session", which existed at call time. It is one observation at one timestamp.

## 4. Two new tools

- **`scan_agent_coins`** (54.0.0) — read-only. Every active coin evaluated against one agent's
  gates in a single call, returned server-ranked as `qualified` / `rejected` / `unscorable`,
  each rejection naming the first gate that failed.
- **`propose_entry_decision`** — **not read-only.** It runs the app's trade turn and stages a
  PENDING decision row for approval. Nothing executes without a separate accept, but it writes.
  It is listed here so nobody reaches for it thinking it is a preview.

## 5. What was wrong in this repository, beyond the compile break

- **`omega/contract.py` hard-asserted exactly 86 metrics** and raised otherwise, so the loader
  would have crashed the moment the corpus was refreshed. It now checks the corpus against its
  own `_index.json`, which still catches a half-written refresh without pinning a number the
  platform owns.
- **The loader's shared vocabulary block still held the August budgets.** `estimatedTokens` was
  16 000 against a live cap of 32 000, and the two newer caps (`conditionFrameReads`,
  `reportNoteChars`) were absent — so the tool was refusing reports the platform accepts.
- **Three metric annotations had been falsified by the platform and were still asserted.** All
  three limitations are lifted: `CCI20` now offers `classifyZone` (and the pair is no longer
  platform-privileged), `RVOL` now offers `spread`, `STOCH_D` now offers `classifyZone`. Each
  note is replaced by one recording what was lifted and when, rather than deleted.
- **A first refresh attempt silently dropped two per-transform fields**, `chainedRankOrderings`
  and `rankableSpreadOperands`. The suite caught it. The extraction now takes every flag the
  platform actually returns, enumerated from the responses rather than assumed.

## 6. A new field we do not yet enforce

`get_metric_construction_hints` now returns **`anchor: "1d"`** on nine metrics — `PDH`, `PDL`
and the seven pivots. It is the platform declaring in the metric contract what the vendor's
authoring skill states in prose: those metrics bind to the daily timeframe and `{abs: "1d"}` is
the only reference the save path accepts. The field is **captured in the corpus and not yet
enforced by `omega/validate.py`**. Enforcing it needs the refusal measured, not inferred.

## 7. How the corpus was refreshed

Through the repository's own pipeline, not by hand. 144 `get_metric_construction_hints` calls
→ `data/contract/metrics/_batch*.json` → `scripts/build_corpus.py` → the per-metric files, the
index, the composability matrix, the spread-operand graph, the privileged-pair set and the type
system. The 2026-08-24 batches are kept under
`data/contract/metrics/archive_20260824_extraction/` because every August measurement was built
from them.

The transform-authoring invariance claim was **re-verified rather than carried over**: across
all 663 metric × transform pairs, every transform's `authoring` block has exactly one variant.

Counts, all recomputed:

| | 2026-08-24 | 2026-09-09 |
|---|---|---|
| metrics | 86 | 144 |
| legal metric × transform cells | 322 / 1376 (23.4 %) | 663 / 2304 (28.8 %) |
| structural shapes | 488 | 1018 |
| operand-expanded shapes | 1779 | 8999 |
| platform-privileged pairs | 4 | 3 |

## 8. The gap, and closing it

The August **live** sweeps — render coverage, signal-module probes, tier-C verdicts, the
timeless column-timeframe audit — ran against the 86-metric roster. Extending them to the 58
metrics added since would have been assumption, so the gap was first given a name and a file
(`data/derived/unmeasured_metrics.json`) and then **measured**. All four dimensions are now
closed. Every call below was read-only.

**Render coverage — complete again.** 7,840 shapes the caches had never seen were rendered
through `preview_strategy_report`, 32 columns per custom section, up to 8 sections per call,
with any refused batch bisected down to the offending column so a refusal would be attributed
rather than written off.

| | result |
|---|---|
| shapes rendered | 7,840 |
| distinct headers minted | 13,572 |
| refusals | **0** |
| omega predicted a header that did not render | **0** |

Zero refusals means the platform accepted every shape omega's enumerator claims is legal, and
zero misses means every header `omega.fanout.outputs_for` predicts is the header the platform
actually mints. That is the strongest agreement between this tool and the platform measured so
far, and it now holds over 675 structural and 8,979 operand-expanded shapes with nothing
uncovered. Headers: `data/contract/columns/_coverage_sweep_2026-09-09.json`. Run record:
`data/audit/coverage_sweep_2026-09-09.json`.

**Signal-module membership — measured, and it changes what the new metrics are for.** Each of
the 58 was probed alone in one custom section with `derive_strategy_rule_view` (reads no
persisted strategy, writes nothing). The control matters: a section carrying only `CLOSE`
returns **zero** signals in report, so a non-empty result is attributable to the metric under
test rather than to the section existing.

- **31 feed a signal module.** The nine pivots plus PDH/PDL feed the support-and-resistance
  signals; EMA9/21/50 and HMA20 feed the moving-average signals; DI+/DI− feed trend strength;
  BB_UPPER/BB_LOWER feed Bollinger; RSI2 feeds RSI; the thirteen regime keys feed regime.
- **27 feed nothing.** All nine TPO metrics, all five Ichimoku lines, all four Keltner keys,
  Supertrend (both), PSAR, QQE (both), WaveTrend (both), Williams %R and Stochastic RSI.

That second list is the practically important finding, and nobody documents it: **those 27 can
be put in a report and conditioned on, but they cannot be weighted in the aggregate score,
because no signal reads them.** A strategy that leans on TPO or Ichimoku has to express it
through conditions, not allocations. `DONCHIAN_UPPER`/`DONCHIAN_LOWER` were probed separately —
they are the rename, not new — and feed the same four support-and-resistance signals the old
names did, which is what makes the rename safe rather than merely plausible. That first pass probed one transform per metric and said so. **The caveat is now closed:**
every legal metric × transform cell was probed — **663 cells, zero failures** — and
membership is **not** transform-dependent. For every metric, all of its non-spread
transforms return the same signal set, and the full probe reproduces the single-transform
result exactly: 83 feed a module, 61 feed none, zero disagreements either way.

The 108 **spread** cells are excluded from attribution deliberately. A spread column puts
the base *and* its operand in the report, so it cannot isolate the base — and subtracting
the operand's own signals is not a fix, because where base and operand feed the same module
it removes the base's contribution too. Measured: `PPO × spread` with operand `ROC12` reads
empty under subtraction, while PPO's four other transforms each return the same four
relative-strength signals. Every metric has at least one non-spread cell, so nothing is
attributed from a spread cell alone. Records:
`data/audit/module_membership_full_2026-09-09.json` (full) and
`data/audit/module_membership_new_metrics_2026-09-09.json` (the first pass).

**The timeless rule — measured, not generalised.** All 22 newly-timeless metrics were probed
with a pinned `{abs: "4h"}` against a 1h anchor. The platform **refused every one**, so the rule
now rests on measurement across the whole corpus rather than on the original 40 plus an
assumption. Record: `data/audit/timeless_rule_new_metrics_2026-09-09.json`.

**Tier-C coherence — not applicable.** No member of the tier-C set is among the metrics added
since, so that set needed no extension. Saying so is better than inventing verdicts for it.

## 9. Still outstanding

- **Doc 18's "cannot build" verdicts.** Families it declares unbuildable — Keltner, Supertrend,
  Ichimoku, pivots, Williams %R — the platform now serves, and the TPO family is one it has
  never considered. Re-deciding that census is its own piece of work. The membership result
  above is the input it needs: most of those families feed no signal, so "buildable" and
  "scoreable" are different questions for them.
- **`entry.anchor` is captured but not enforced.** See section 6.
- **`data/contract/_manifest.json` still describes the August extraction.**
- **The three prior-session TPO reads returned null** in the one render that observed them. Not
  diagnosed.

## 10. The endpoint rate-limits, and says so

Found while running the full membership probe: an unthrottled four-worker run failed 162 of
663 cells with

> `Rate limited: 3 requests/second sustained, up to 120 banked. Retry after 1s, or wait 40s
> for full capacity.`

A token bucket: 3 requests per second sustained, a burst bank of 120 that refills at the
sustained rate. The first ~65 probes succeeded because they spent the bank; everything after
it failed. Re-running the same cells with call starts spaced 0.45 s apart produced **zero**
errors. The limiter is never silent — it returns JSON-RPC `-32000` with that message — so a
sweep that fails quietly is failing for some other reason.

One thing measured, one not. Measured: the limit, its shape, and that throttling fixes it.
Not measured: why ~0.67 *logical probes* per second tripped a 3-requests-per-second limit. The
likely explanation is that one `mcporter call` costs more than one HTTP request, because a
fresh CLI invocation performs an MCP handshake before the tool call. That is a hypothesis
consistent with the observation, not a measurement.

**This does not overturn the 2026-09-06 Hermes diagnosis.** Those failures were client-side
timeouts at roughly one call every 5–15 seconds, nowhere near 3/s, and the limiter would have
said so out loud rather than returning empty bodies. What it corrects is the broader
impression that this endpoint has no rate limit. It has one, and any batch or parallel sweep
must respect it. Record: `data/audit/rate_limit_2026-09-09.json`.
