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

## 8. What is NOT done, and is not pretended to be

The August **live** sweeps — render coverage, signal-module probes, tier-C render verdicts, the
timeless column-timeframe audit — ran against the 86-metric roster. Extending them to the 58
metrics added since would be assumption, so instead the gap has a name and a file:
`data/derived/unmeasured_metrics.json` lists them, plus the 322 metric × transform mechanisms
the sweep actually rendered. Every affected test now asserts

> measured ∪ unmeasured == the corpus

so the suite stays honest and the outstanding work stays countable. Live-render coverage is
still complete **over the rendered roster** and is asserted that way; the uncovered remainder
is asserted to be non-empty rather than dropped from the denominator.

Also outstanding: **doc 18's "cannot build" verdicts**. Families it declares unbuildable —
Keltner, Supertrend, Ichimoku, pivots, Williams %R — the platform now serves, and the TPO family
is a new one it has never considered. Re-deciding that census is its own piece of work and has
not been done. `data/contract/_manifest.json` still describes the August extraction.
