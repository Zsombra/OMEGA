# OMEGA v0.14.3 at contract 171.0.0: the default menu inside the stop range, the draft echo, the generated docs and the dead anchor block

**Record, 2026-11-13 (written 00:17Z).** Contract 171.0.0, build `588e449a`. Previous pin: v0.14.2 at the same contract.
Four items of the program's pending ledger:

| Item | Ledger entry | Answer |
| --- | --- | --- |
| 1 | 168.4.0, "OMEGA's default menu clipped to the thesis's stop range" (battlegrid-manager `docs/status/2026-11-11-contract-168.md`) | A decision **drops** an ATR stop outside the range: it is not a stage error, and it is not clamped. `default_menu` offers only the default stops inside the thesis's range; `validate_menu` warns, naming the measured verdict |
| 2 | 149 Open 6 (`docs/status/2026-11-05-contract-149.md`): does a staged draft echo default knobs back? | **No.** 26 stored read-backs hold exactly the keys sent. No helper is needed |
| 3 | M23: regenerate docs/01 and docs/02 | The generator no longer ran, and it skipped 4 families and 6 transforms. Fixed, both docs regenerated, and a test holds them to the generator's output |
| 4 | M28: remove the dead anchor block | `validate_column`'s metric-anchor block is removed; every answer it gave over the catalogue is unchanged |

# Item 1: an ATR stop outside the stop range

## What the stored answers settled, and what they did not

Three stored answers bear on it.

- **The stage, at 168.2.0.** Probe V9 (`data/audit/trade_level_menu_168_2026-11-11.json`) staged ATR 5 and ATR 0.5
  against the range 1 - 2, as the menu's only stops. It staged clean: no error and no warning.
- **The decision, at 168.4.0.** `preview_strategy_trade_levels` was read on BTC at 2026-11-12 00:56Z on the three
  strategies whose migrated menus were read on 11-11 (the 168 status note's table). The answers were in that session's
  scratch (`C:/Users/rafae/omega-v012-hints/v168/trade_levels_preview_<id>.json`); this release's record digests them
  and names each file's sha256.

  | Strategy | Range (ATR) | ATR stops | Verdicts |
  | --- | --- | --- | --- |
  | Dunkirk | 1 - 2 | 1, 1.5, 2 | all SURVIVED: 1 on the minimum, 2 on the maximum |
  | VWAP Reject 4h | 1 - 1.8 | 1, 1.5, 2 | ATR 2 `ABOVE_CEILING`, `responsibleBound` `MAX_STOP_LOSS_ATR_MULTIPLE`, both sides |
  | TPO Prior Session Levels LONG | 0.8 - 1.8 | 1, 1.5, 2 | the same |

  A refused stop is in no setup and in no refused pair. On SHORT the same ceiling also refused the Bollinger band stop
  at 1.85 ATR and the Donchian band stop at 2.2 ATR.
- **The preview tool's description** (the 171.0.0 surface listing,
  `C:/Users/rafae/omega-v012-hints/v169/surface_tools_171.0.0.json`) names the verdicts a stop option can read:
  `WRONG_SIDE`, `BELOW_FLOOR` ("min stop"), `ABOVE_CEILING`, `ABOVE_STRUCTURAL_CEILING` (the 5 x ATR cap) and
  `LEVEL_UNREAD`.

They left three things open:

- **The floor.** No stored stop sat below its minimum: `stopsRemovedByFloor` is 0 in every stored preview. The floor
  matters to the default menu: a range of 1.2 - 2 drops ATR 1 only if the floor does what the ceiling does.
- **A bound that is not a whole number.** No stored stop sat on or under a minimum of 0.8, and none sat exactly on a
  maximum of 1.8.
- **Either answer at 171.0.0.**

## What was measured: one CREATE draft, B1

| | |
| --- | --- |
| Measured | 2026-11-12 23:55:06 - 23:56:05Z. `GET /mcp/version` read 171.0.0 / 588e449a before the first call and after the last |
| Record | `data/audit/stop_band_171_2026-11-12.json` |
| Replay | `tests/test_stop_band_171.py` |
| Transport | the mcporter runtime (`scripts/mcporter_runtime.mjs`): one session, one call per 2.1 s or slower |
| Probe script | `C:/Users/rafae/omega-v012-hints/v0143/probe_v0143.py`, with `rt3.py`. Beside it: every call in `calls.jsonl`, the raw run in `run_v0143.json`, and `build_records.py`, which writes this release's two records |

B1 is the v0.14.0 base plan (battlegrid-manager plan 72's request, the base of every earlier trade-level CREATE probe)
with two changes:

- the range 0.8 - 1.8, which is TPO Prior Session Levels LONG's;
- per side, ATR stops 0.5 / 0.8 / 1 / 1.5 / 1.8 / 2, beside the default exit plans (R 1.5 / 2 / 3, each closing 100%;
  minimum 1.5).

The seven calls, in order:

1. `stage_strategy_draft` (23:55:12Z);
2. `get_strategy_draft`;
3. `preview_strategy_trade_levels` on the DRAFT (BTC);
4. `get_strategy_draft`;
5. `discard_strategy_draft`, at the version read;
6. `get_strategy_draft`: `draft: null`, `draftVersion` 0;
7. `list_strategy_drafts` (23:56:00Z): only VWAP Reject 15m, the commander's draft of 2026-10-23, as at the v0.14.2 run.

Nothing was committed. The draft's `impact` read CREATE with no bound agent.

The stage answered clean: no error and no warning. The preview (entry 71,463, ATR 449.03, ATR% 0.6283) read both sides
alike:

| ATR stop | 0.5 | 0.8 | 1 | 1.5 | 1.8 | 2 |
| --- | --- | --- | --- | --- | --- | --- |
| verdict | `BELOW_FLOOR` | SURVIVED | SURVIVED | SURVIVED | SURVIVED | `ABOVE_CEILING` |
| refused by | `MIN_STOP_LOSS_ATR_MULTIPLE` at 0.5027% (0.8 x ATR%) | | | | | `MAX_STOP_LOSS_ATR_MULTIPLE` at 1.1310% (1.8 x ATR%) |

Each side built 12 setups: the four surviving stops times the three plans. No pair was refused. The counters read
`stopsRemovedByFloor` 1 and `stopsRemovedByCeiling` 1.

## What the answers settle

- **It is not a stage error.** The stage accepts an ATR stop outside the range and says nothing (V9 at 168.2.0, B1 at
  171.0.0).
- **Every decision drops it, and does not clamp it.** The decision refuses the stop OPTION before pairing: verdict
  `BELOW_FLOOR` or `ABOVE_CEILING`, at the bound times the coin's ATR%, and the stop is in no setup and no refused pair.
  It is not moved onto the bound: B1's 0.5 and 2 build nothing, while 0.8 and 1.8 build their own setups. An ATR stop's
  distance in ATR is its multiple, so the same stop is dropped on every coin at every decision. It is a dead option.
- **Both bounds are inclusive.** 0.8 and 1.8 survive, and at 168.4.0 so did ATR 1 on a minimum of 1 and ATR 2 on a
  maximum of 2. The preview measured those two at 0.8000000000000002 and 1.7999999999999998 ATR; omega compares the
  numbers as they were written.
- **There is no one-ATR floor of the stop's own.** ATR 0.8 survives a minimum of 0.8.
- **A LEVEL stop is judged the same way, on its distance at that bar** (168.4.0's band stops). That distance is per coin
  and per bar, so omega does not judge it offline.
- **The two range dials take no 0.25 step.** 0.8 and 1.8 staged with no draft error.

Recorded, not modelled: `stopBand.reachableMinPct` read 1 x ATR% (0.6283%) although the 0.8 stop survived, and
`survivingRungPcts` listed only 1 and 1.5 ATR. Neither bears on a menu stop's verdict, and omega models no rung ladder.

So the default menu **drops** a stop outside the range, as the platform does. Snapping it onto the bound would offer a
stop the migration never wrote, and clamping is not what the decision does.

## Where OMEGA holds it

| | v0.14.2 | v0.14.3 |
| --- | --- | --- |
| `default_menu(min_rr, schema=None, *, stop_range=None)` | ATR 1 / 1.5 / 2 whatever the range | only the defaults inside `stop_range` = (minStopLossAtrMultiple, maxStopLossAtrMultiple) (`default_stops`). See the table below |
| `StrategyPlan.trade_level_menu()`, for a thesis naming no menu | `default_menu(minRiskRewardRatio)` | passes the plan's effective range. Every preset runs at the platform default 1 - 2, so every preset's menu is unchanged |
| `validate_menu`, on an ATR stop outside the range | warning `TRADE_MENU_STOP_OUTSIDE_RANGE`: "what a decision does with it is not measured" | the same code and severity, because the stage accepts it. The message names the verdict and bound a decision drops it with (`outside_stop_range`, `STOP_RANGE_VERDICTS`) |
| an UPDATE naming a range dial | the live menu carried verbatim; its stops outside the new range warned | unchanged: omega never rewrites a live strategy's menu |
| `omega/execution.py` `ENFORCED_STEPS` | 0.25 on minRiskRewardRatio | unchanged; its comment records B1's answer on the range dials |

What `default_stops` offers:

| The thesis's range | Default ATR stops |
| --- | --- |
| 1 - 2 (the platform default), and no `stop_range` at all | 1, 1.5, 2: as before |
| 0.8 - 1.8, or 1 - 1.8 | 1, 1.5 |
| 2.5 - 4 (none of the three inside) | 2.5, 4: the range's own bounds, which survive |
| 1.2 - 1.2 | 1.2 |
| 2.5 - 6 | 2.5: the write schema stages an ATR stop only in (0, 5] (`atr_stop_bounds`) |
| 6 - 8, an inverted range, or a bound that is not a finite number | 1, 1.5, 2: not this builder's to judge. Under 6 - 8 or an inverted range, `validate_menu` warns on each of them |

Two more changes in `validate_menu`. It compares each number as the decimal it was written as. A bound that is not a
finite number is no longer judged: v0.14.2 warned on every ATR stop under a NaN bound.

`omega/trade_levels.py`'s module docstring carries these rules under "The stop range".

**For whoever pins v0.14.3 in battlegrid-manager:**

- A CREATE plan whose thesis sets the stop range off 1 - 2 now stages fewer, or other, ATR stops, so its request differs
  from v0.14.2's.
- The manager's own tests that set a range dial are UPDATEs, which carry the live menu: unchanged.
- `default_menu(min_rr)` without `stop_range` is unchanged, so the tests that build a current menu with it hold.

## Not measured

- A PERCENT stop against the range. The decision reads its distance per coin; omega does not judge it offline.
- An inverted range (the minimum above the maximum), and a range reaching past the 5 x ATR structural ceiling. Neither
  was sent.
- A step on the range dials finer than 0.25. 0.8 and 1.8 pass; a 0.1 step is not excluded.
- What `reachableMinPct` and `survivingRungPcts` describe.

# Item 2: does a staged draft echo default knobs back? (149 Open 6)

The manager settles a stage whose answer was lost (`manager/actions/strategy_verify.py`, `_verify_stage`) by matching
the re-read draft's content against what it sent: `content_sha(read) == content_sha(sent)`. If the platform filled a
knob the body left out with its default, the two would differ and the row would wait for the user.

`data/audit/draft_echo_2026-11-13.json` answers it offline, with no platform call. It compares every stored stage whose
whole sent body and whole read-back are on disk, in the manager's canonical form (`manager.risk.radar.canonical`, read
at manager main d64308d: sorted keys, every number a normalised decimal string, null kept):

| Read-backs | The body sent | Contract |
| --- | --- | --- |
| 14 CREATE drafts of the 168 menu probes (`v168/*.read.json`: the tc, V and E probes) | plan 72's request with the probe's menu, added column and entry, as `stage_menu_variants.py` composed it; the two tc probes' own `args.json` | 168.2.0 |
| 11 reads of the 4 UPDATE drafts of the v0.14.2 probe (`v171/calls.jsonl`) | the axes the draft's stages sent | 171.0.0 |
| B1's read-back | the args sent | 171.0.0 |

**There is no echo.** In all 26:

- no key was added, none was dropped and no value changed;
- `content_sha(read) == content_sha(sent)`;
- the only raw difference is how a number is spelled (10.0 sent, 10 read back; -10.0 and -10), which the canonical form
  already normalises.

The bodies gave an echo every chance:

- They left knobs out. The 177 REPORT columns (counted per read-back) carried no knob key, because `Column.wire()` drops
  a knob left None.
- They sent keys holding null: `bars`, `benchmarkTicker`, `exitSide`, `marketScope`, `notes`, `sectionKey`, `verdict`
  and `windowExtreme`.

Each came back exactly as sent: no default was filled in and no null was dropped. So the recovery's sha match holds, and
the manager needs no normalising helper. None is added. `tests/test_draft_echo.py` replays the record and B1's whole
pair.

Not covered:

- A column sent WITH a knob was never read back. L3a and L3b staged one at 168.3.0, but their read-backs were not kept,
  and the knob-spelling probes were previews.
- The read-backs on disk are CREATEs at 168.2.0 and 171.0.0 and UPDATEs at 171.0.0.

# Item 3: docs/01 and docs/02 regenerated (M23)

`scripts/build_docs.py` generates both docs ("do not hand-edit"). Their last commit is f99bf3e (contract 108.4.0, 171
metrics). Run at f99bf3e, in a scratch copy made with `git archive`, the generator writes both byte for byte. So the
committed docs carried no hand edit that regenerating could lose.

At 171.0.0 the generator did not run, and its output would have been incomplete:

- It raised `KeyError: 'emits'`. 13 transforms are served without `emits`: linregSlope, pctl, rollingMax, rollingMin,
  stddev, zscore, relativeTo, cci, ema, rma, rsi, wma and roc. The corpus notes that the hint does not serve it.
- `FAMILY_ORDER` named 10 of the 14 families. channels, vwapProfile, levels and market (382 metrics) would have had no
  table.
- `TRANSFORM_ORDER` lacked cci, ema, rma, roc, rsi and wma, in doc 01's transform column and in doc 02's reference.
- Three hand-written sentences were false:
  - RVOL is no longer the lone `ratio` metric without spread: it spreads, in a pool of three.
  - CCI20 x classifyZone is no longer a privileged pair: every privileged pair is now a classifyState (ADX, MFI14,
    CVD).
  - bandTouch is retired.

The generator now:

- takes the family order from the platform's own `categories.json`, and stops when a family has no category;
- lists every transform of the authoring catalogue (`transform_order`: the old order first, then the rest);
- says so when a transform is served without `emits`;
- writes the three sentences only while the corpus says them;
- counts the line on metrics without spread from the graph.

Regenerated with `PYTHONPATH=. python scripts/build_docs.py`: docs/01 +577 / -117 lines and docs/02 +267 / -77, every
line the generator's. `tests/test_generated_docs.py` holds both docs to the generator's output for the pinned corpus, so
the next re-extraction cannot leave them stale without a failing test.

# Item 4: the dead anchor block removed (M28)

The task's pointer named two candidates.

- **The section anchor override** (`SECTION_TIMEFRAME_RETIRED`) is live code: `validate_section` refuses a section that
  still carries a `timeframe` (`tests/test_report_surface_108.py`). It stays.
- **The metric-declared anchor rule** in `validate_column` (`METRIC_ANCHOR_MISMATCH` and the warning
  `METRIC_ANCHOR_RELATIVE_UNVERIFIED`) is the dead block. It was gated on `m.anchor and not m.is_timeless`. PDH, PDL and
  the seven pivots lost their "1d" anchor at 61.2.0, no metric has declared one since (0 of 581 at 171.0.0), and the
  09-20 session record had flagged it.

The block is removed from `omega/validate.py`; `Metric.anchor` is still read. The behaviour is unchanged:

- A digest of every `validate_column` answer over the catalogue is identical before and after: each metric through each
  transform it offers at six timeframe references, 28,410 columns and 10,517 findings (sha256 `df7e204a…`).
- `tests/test_metric_anchor_rule.py` keeps the removed block verbatim as a reference, and shows it yields nothing on any
  of those columns.
- Its invariant test still fails loudly if a re-extraction brings an anchor back. Its message now says to re-measure the
  rule and re-add it, since omega no longer enforces it.

Tests changed: `tests/test_metric_anchor_rule.py` is rewritten, from 6 tests to 10.

- The two invariant tests stay.
- The four tests that exercised the block on a synthetic anchored metric became one: `validate_column` says neither
  code on that metric now, beside the reference block's 54.1.0 answers.
- Seven tests are new: the reference block yields nothing over the catalogue (one test), and `validate_column` names no
  anchor code at each of six timeframe references (six).

`tests/test_metric_anchor.py` changes in wording only.

# Suite

2522 passed, 1 skipped. The last run took 308 s (00:28:24 - 00:33:42Z on 2026-11-13), after the last change to code,
tests and records. That is v0.14.2's 2491 plus 31:

| File | Tests |
| --- | --- |
| `tests/test_stop_band_171.py` (new) | 18 |
| `tests/test_draft_echo.py` (new) | 4 |
| `tests/test_generated_docs.py` (new) | 5 |
| `tests/test_metric_anchor_rule.py` (rewritten) | 10, was 6 |

The version assertions in `tests/test_v146.py` and `tests/test_v146_1.py` read 0.14.3. No other test's assertion
changed.

Run against v0.14.2's `omega/` and `scripts/` (origin/main 7c0954e, in a scratch copy, with only the record's two
constants added so the new files import), 12 of the new tests fail and the 5 docs tests error. The 20 that pass there
replay the platform's answers and the v0.14.2 behaviour this release keeps:

- the records replay: the stage's and the decision's answers, the thresholds, and the draft echo;
- an UPDATE's carried stops outside a new range are warned;
- the range dials take no step;
- a LEVEL stop is not judged offline;
- the anchor invariant holds, the reference block yields nothing, and `validate_column` names no anchor code on the
  catalogue.
