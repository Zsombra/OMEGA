# @battlegrid/mcp-server

[![npm version](https://img.shields.io/npm/v/@battlegrid/mcp-server)](https://www.npmjs.com/package/@battlegrid/mcp-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP server for [BattleGrid](https://battlegrid.trade) — play crypto prediction games, author trading strategies, and manage intelligence agents from AI agents.

It is a thin, authenticated **stdio proxy** to BattleGrid's remote MCP server (Stripe `@stripe/mcp` pattern — no business logic). It discovers tools, prompts, and resources live from the server and re-exposes them to local MCP clients (Claude Desktop, Claude Code, Cursor). Capabilities are always **discovered live** — this package never hardcodes the tool catalog.

## v31 — the announced contract is read from the server, not declared here

**The package version no longer tracks the server's contract, and no longer claims to.** Through v30 it did: the proxy announced `battlegrid@<package version>` downstream, so the published number was read as the contract a client would reach, and keeping the two in step was a manual release chore. It did not hold — the package sat at `11.0.0` against a deployed contract of `19.3.0` for ten days, `5.1.0` was declared here and never published at all, and four of the last five releases were version bumps carrying no code change.

From v31 the proxy reads the contract version out of the upstream handshake at connect time and relays it verbatim. What a local client reads is therefore what the connected server just announced — correct by construction, on every connection, with no release involved.

**Two versions, two meanings, and they are expected to differ:**

| | What it describes | Where to read it |
|---|---|---|
| Package version | This proxy's own code — a fix here, a dependency bump, a docs correction | `npm view @battlegrid/mcp-server version` |
| Contract version | The server's wire contract, live | The stdio handshake (`battlegrid@<contract>`), or `GET /mcp/version` |

Seeing package `31.x` alongside handshake `battlegrid@33.x` — the package **behind** the contract — is the system working, not a missed release. That is the pair that looks alarming and is not: the contract moved, and no release here was needed. Both numbers are printed to stderr at startup, labelled.

**What this changes for you:** nothing about how you call anything. Upgrading the package no longer waits on a server deploy, and a server deploy no longer strands you on a package that names the wrong contract — reconnect and the announcement follows. **Contract breaking-change notes are no longer keyed to package versions**, since a contract move is no longer a release here; the v11-and-earlier notes below are kept as history, and the live vocabulary is always discovery.

## Contract history — v37 → v53

Eleven majors reached authors while this section stopped at v36. That gap is the mechanism, not an
oversight: since v31 a contract move needs no release here, so nothing forced a note to be written —
and the documentation ships inside the tarball, so a note written but unpublished reaches nobody.
Both halves are now closed by a rule keyed to the *served* contract rather than to a release of this
package.

**50.0.0 and 51.0.0 arrived late, and the reason is worth naming.** The re-vendoring errand that
used to carry these notes is now a generated export
(`battlegrid-app/server/scripts/export-mcp-skills.mjs`), and it owns three paths — `skills/`,
`skills/EXPORT.json`, and the vendored digest. It deliberately does not touch this file. So the
digest kept arriving on time while the note stopped travelling with it, and this section sat at
v49.5 against a served contract of 51.0.0. Nothing a client could observe was wrong; what was
missing was the sentence telling them so. **A contract move still needs a human-authored entry
here, and the export lane will not remind you.**

### Accepted again — input that was rejected now compiles

Nothing to migrate. This is the one direction that cannot break a client: a body the server used to
refuse is now stored. Listed because a client that special-cased the refusal can delete that branch.

- **A signal rule patch no longer forces you to restate `allocation` and `required`** (51.0.0,
  `fix-signal-rule-patch-semantics`). On `update_strategy_signal_rule`, and on the `rules` element
  of `compile_strategy_plan`, both fields become optional and join `params` under ONE omission
  rule: **an omitted mutable field preserves the stored value for that signal.** "Raise this
  signal's weight" is now expressible.

  ```jsonc
  { "strategyId": "…", "expectedRevision": 7, "signalId": "volume_surge",
    "allocation": 3 }               // `required` and `params` keep exactly what is stored
  ```

  **Every existing client keeps working** — a complete payload is still a valid patch — so this is
  listed for what you can now STOP sending. Before it, both fields were mandatory on every rule
  surface, so a caller that had not first read the current rule had to invent a value it was never
  asked about. That is not hypothetical: revision 5 of a production strategy flipped `required`
  false → true unasked while moving a weight 2 → 3, turning a scoring signal into a **mandatory
  gate** — which changes whether the agent takes trades at all.

  One boundary on the newly legal ground, and it breaks nothing: a patch carrying **no** mutable
  field is refused — *"A rule patch must change something: supply at least one of allocation,
  required or params."* — rather than minting a no-op revision. Under 50.0.0 that request could not
  be formed at all, so nothing that used to work is now refused.

- **An arming trigger no longer constrains its required conditions' clock** (49.4.0,
  `restore-arming-trigger-authoring`). `compile_strategy_plan`, `apply_strategy_plan` and
  `fork_strategy` accept a strategy whose entry trigger is `ON_CANDLE_CLOSE`, `STOP_THROUGH_LEVEL`
  or `ON_RETEST` **while a required condition reads the `LIVE` clock**. v48.1 announced that pairing
  as rejected, naming the offending condition key on `VALIDATION_ERROR`; that refusal is gone.

  Why it was withdrawn, since the reasoning matters more than the rule: it ran against the whole
  assembled strategy, so it refused *every* edit to a strategy in that shape — a rename, one report
  column, one signal weight — plus restore and fork. For a strategy whose required conditions read
  columns that can never carry a `CLOSE` clock (zone distances, perp/spot flow), there was no legal
  shape to move to at all. And its premise — that the pairing can never fire — was measured before
  the arming lifecycle was corrected, and no longer holds.

  The underlying question, *should an entry that waits for a close be decided on a forming bar*, is
  now settled where the decision is made rather than by refusing the author's declaration.

### Changed meaning, unchanged shape

- **`blocksScanGate` reads `true` for a class it did not** (50.0.0, `own-scan-served-set-once`), on
  `preview_radar_resolution`. Blocking is now derived from the lane's **served set** rather than
  switched over the reach reason, so a `FEED`-reason refusal on an operand no reader in the lane
  serves BLOCKS instead of deferring. No field changes shape, and a client that already renders the
  key renders the new answer — but a client that treated `blocksScanGate: false` as "this will
  resolve once data arrives" now sees a deployment that will not fire. Nothing in the payload tells
  you this moved.

- **Three tools serve different values for identical input** (47.3.0, `derive-scan-fetch-from-report`).
  The radar scan leg now derives its timeframe fetch from the strategy's **report** rather than the
  on-duty agent's three perception rungs, so a required condition addressing an absolute timeframe
  outside those rungs — never evaluated at scan before — now is. No field moves; the values do:

  | Tool | What moves |
  |---|---|
  | `preview_radar_resolution` | `conditionReach[].reachReason` goes `AGENT_TIMEFRAME` → `null` |
  | `get_radar_activity` | `scanReachReason` moves the same way, **on new rows only** — rows already written keep what they were recorded with |
  | `get_agent_coin_qualification` | `reachReason` moves the same way; its sibling `verdict` moves `UNMEASURABLE` → a decided verdict |

  **Read the last one carefully:** a client treating `UNMEASURABLE` as "this gate is switched off"
  will now see that gate **BLOCK**. `AGENT_TIMEFRAME` keeps its member and narrows to the one cause
  no fetch can discharge. Nothing in the payload tells you this moved.

### Rejected input — something you author is no longer accepted

- **A condition naming a `swingHi` / `swingLo` header is refused — the indicator is a Donchian
  channel** (53.0.0, `rename-donchian-channel`). The rolling-window extremes indicator computed the
  highest high and lowest low of the trailing 20 closed bars — a Donchian channel — under a swing
  point's name, and the name asserted a property the value does not have (a swing high survives being
  broken; a channel edge re-anchors the instant it is). Every layer of the vocabulary moves at once,
  with no alias: a clause on `compile_strategy_plan`, `apply_strategy_plan` or `fork_strategy` naming
  a header on the old stems — `dist_swingLo`, `dist_swingHi_4h`, `dist_swingLo_rank_near`, any
  timeframe- or rank-suffixed form — is refused as `CONDITION_COLUMN_UNKNOWN` where 52.0.0 accepted
  it. The same shapes exist on the `donchianHi` / `donchianLo` stems, which
  `get_strategy_column_contract` lists with the labels *20-bar high* / *20-bar low*. Every value is
  the same number under its new name.

  **Rename the stems** (`swingHi` → `donchianHi`, `swingLo` → `donchianLo`, suffixes unchanged) in
  every condition and Market Read marker you author. That is the whole migration for what you send.

- **`entry.levelSource` is refused — the level is derived, never authored** (52.0.0,
  `derive-entry-level`). The strict `entry` object on `compile_strategy_plan`, `apply_strategy_plan`
  and `fork_strategy` is six keys — `trigger`, `confirmTf`, `closes`, `bandAtrMultiple`,
  `levelOffsetAtrMultiple`, `validForBars` — and a body carrying `levelSource` is refused naming
  the key where 51.0.0 accepted it. `STOP_THROUGH_LEVEL` rests a stop past the swing channel's
  CURRENT edge in the trade's direction (the 20-bar high for a long, the 20-bar low for a short);
  `ON_RETEST` rests a limit in front of the edge a close most recently BROKE. Your two dials are the
  unsigned distance from that edge (`levelOffsetAtrMultiple`, 0–2 ATR; a long adds, a short
  subtracts) and the bar validity (`validForBars`, 1–24). A meaningful `validForBars` under
  `AT_SIGNAL` or `ON_CANDLE_CLOSE` is now refused as `PARAMETER_NOT_HONOURED` like the other level
  dials.

  **Drop the key.** That is the whole migration for what you send; the six-key example below is
  the current shape.

- **`update_strategy_signal_rule` requires `confirm: true` when the strategy has bound agents**
  (51.0.0, `fix-signal-rule-patch-semantics`). The write re-materializes scoring configuration onto
  every bound agent immediately — including agents holding open USDC positions — and until now
  nothing on the server asked. A rule edit on a strategy with one or more bound agents is refused
  without the flag, and the message names the count. An edit on a strategy with **nothing bound is
  unaffected**, and so is every path through the web editor.

  **Send `confirm: true`.** That is the whole migration, and `confirm` is published on the input
  schema — but nothing in the schema says WHEN it becomes mandatory, because the condition is the
  bound-agent count rather than the shape of your body. The refusal rides the existing
  `VALIDATION_ERROR` code, so a client that omits it discovers the rule at the refusal.

  Why it moved to the server: the guard existed, but only as served prose the calling model could
  decline — and did, twice in production on 2026-08-24. `archive_strategy` and
  `rebind_intelligence_agent` have taken a server-enforced `confirm` all along; single-rule tuning
  was the outlier among its own siblings, and it is the one that writes to scoring.

- **A radar deployment is refused when its strategy reads a session-field scalar** (50.0.0,
  `own-scan-served-set-once`). `upsert_radar_deployment` refuses a deployment whose slot agents'
  bound strategy carries a condition reading one of five SESSION-FIELD scalars — `fieldPlayers`,
  `fieldUpBias`, `fieldBiasDir`, `captConc`, `picksSpread` — with
  `CONDITION_OPERAND_UNSERVED_IN_LANE`. A body accepted under 49.5.0 is refused under 50.0.0
  without one byte of it changing.

  **Why a refusal and not a warning.** Those five describe a game SESSION, and radar runs outside a
  session at BOTH its stages — so such a condition can never resolve there. The deployment formed
  no fire edge and the agent did nothing on that coin, silently, forever. The refusal converts a
  permanent silence into an error at the moment you author it.

  **Migrate** by moving the clause to a scalar radar reads — the Market Breadth or Reference Pairs
  families, which are market-wide reads with no session dimension — or by binding the strategy to
  an arena agent instead. The error carries both halves: `allowedDomain` enumerates every servable
  header, and the message names the sections.

  **Strategy authoring is untouched by this bump.** The same strategy is legal, and reads those
  scalars correctly, on an arena agent — which is why the refusal is on the DEPLOYMENT and not on
  `compile_strategy_plan` / `apply_strategy_plan`.

- **A benchmark-bound section no longer accepts crowd metrics or rank transforms** (49.0.0,
  `fix-benchmark-legality-save-path`). On a custom section carrying a non-null `benchmarkTicker`, a
  column whose metric is enrichment-stage (the `CROWD_*` family, `FLOW_ALIGN`, `SMART_RETAIL`,
  `CAPTAIN_CONF`, `CONFIDENCE`, `SETTLED_AT`, the `PERP_SPOT_*` trio) is refused with
  `REPORT_COLUMN_BENCHMARK_METRIC_UNSUPPORTED`, and one carrying a `rank` transform in either the
  direct or the chained position with `REPORT_COLUMN_BENCHMARK_TRANSFORM_UNSUPPORTED`. Every tool
  accepting a section array is affected, and no other byte of your body changes.

  **Fix it by moving the column, not by retrying.** Both readings are defined *relative to the
  cohort being evaluated* — a crowd reading is what this session's players did, a rank is a position
  among the coins under evaluation — and a benchmark is deliberately outside that cohort. Neither
  has a value there, which is why such a column could never render. Put it on an ordinary section
  (`benchmarkTicker: null`), or drop it.

  **This is a fix, not a new rule.** The restriction shipped with benchmark sections and was already
  enforced by the column builder, by report materialization, and by `get_strategy_column_contract` —
  so an author who checked a column against discovery first has been seeing this refusal all along.
  What changed is that the SAVE path now asks the same question. Previously it did not, so such a
  section persisted and then failed at every evaluation instead of at authoring.

- **A custom report section no longer accepts `timeframe`** (48.0.0,
  `remove-section-anchor-override`). The per-section anchor override is gone. Every tool accepting a
  section array — `compile_strategy_plan`, `preview_strategy_report`, `derive_strategy_rule_view`,
  and `apply_strategy_plan` — refuses a section carrying it: `sections[N]: Unrecognized key(s)`,
  with no other byte of your body changing. Drop the key. A section's columns resolve against the
  **strategy** timeframe, and a column reaches any other timeframe by pinning it on the column
  (`timeframe: { abs: '4h' }`) — which it could always do. Relative column references
  (`anchor`/`lower`/`regime`) are untouched, and are the point: they track the strategy.

- **A custom report section requires `notes`** (43.0.0, `add-authored-section-notes`). Every tool
  accepting a section array — `compile_strategy_plan`, `preview_strategy_report`,
  `derive_strategy_rule_view` — refuses a section without it: `sections[N].notes: Required`, with no
  byte of your body changing. Send explicit `null` for "no note". It is required rather than optional
  because these payloads are a FULL REPLACE: an omitted key and an explicit `null` would be the same
  request on the wire, so every rebuild site would silently clear a note its author wrote.
  `benchmarkTicker` carries the same required-nullable discipline for the same reason.

- **Every condition requires `clock` and `closes`** (44.0.0, `add-condition-clock`), and **`exit`**
  arrives with them. A condition entry now carries eight keys, not five. `clock` is `"LIVE"` (the
  previous behaviour — the forming bar) or `"CLOSE"` (settled bars); `closes` is how many consecutive
  closed bars must read true, 1–5, and is always `1` under LIVE. No wire default, for the same
  whole-set-replacement reason as `notes`: a defaulted key would let an unrelated re-save silently
  un-clock an enforced money gate back to forming-bar evidence.

  A `CLOSE` clock is accepted only where a closed frame can change the reading — the clause must
  resolve from the coin's own candle series at offset 0. Frame-inert operands (perp-payload scalars,
  published rolling changes, ranks, zone entities, regime labels, enrichment metrics, session
  scalars) are refused with `CONDITION_CLOCK_OPERAND_ILLEGAL` naming the header and the remedy: split
  that clause into its own LIVE condition and `conditionRef` it. `exit: true` is legal only under
  `clock: "CLOSE"` — an exit fired on a forming bar is an intrabar exit.

- **A strategy requires a six-key `entry` object** (44.0.0 for four keys, 47.0.0 for three more —
  `add-entry-on-close`, `add-level-trigger-execution` — and 52.0.0 removed `levelSource`,
  `derive-entry-level`). Required on every CREATE, on `compile_strategy_plan`, `apply_strategy_plan`
  and `update_intelligence_agent`. A client sending 44.0.0's four-key object is refused with
  `entry.levelOffsetAtrMultiple: Required` without one byte of it changing.

  ```jsonc
  "entry": {
    "trigger": "AT_SIGNAL",          // | ON_CANDLE_CLOSE | STOP_THROUGH_LEVEL | ON_RETEST
    "confirmTf": "4h",               // the strategy timeframe or the rung below it — nothing else
    "closes": 1,                     // 1–5; must be 1 unless ON_CANDLE_CLOSE
    "bandAtrMultiple": 1.0,          // > 0, and <= the platform's entry-deviation gate
    "levelOffsetAtrMultiple": 0,     // 0–2, UNSIGNED distance from the derived edge; 0 unless a level trigger
    "validForBars": 4                // 1–24 of the strategy's own bars; 4 unless a level trigger
  }
  ```

  `AT_SIGNAL` with those values is byte-identical to pre-44 behaviour. The legality matrix runs one
  way: all six keys are always present, so a MEANINGFUL value under a trigger that ignores it is
  refused rather than accepted-and-dropped — a dial never silently does nothing.

- **A `strategyTimeframe` the platform does not ingest is refused** (39.0.0,
  `move-renderer-to-rendered-section`) on `get_coin_market_context`, where it was previously
  accepted. The number is the only signal a client gets.

- **`eventType` gains `ENTRY_EXPIRED_UNCONFIRMED`** (48.1.0, `fix-entry-arming-lifecycle`) on
  `get_radar_activity` and `get_radar_activity_summary` — an armed entry that reached its episode
  lifetime without ever receiving a confirming close. A client holding its own closed copy of that
  enum rejects the new member; one that switches exhaustively on it needs the branch.

  `entryVoidCause` is deliberately **unchanged** and still carries exactly `BAND`, `CONDITIONS`,
  `STRUCTURAL`. Each of those is a measurement taken *at* a close, so an episode that reached no
  close gets its own event type rather than a fourth cause — `ENTRY_VOIDED` means "called off at the
  close", a claim this outcome must not make.

  The authoring boundary also gains a refusal with **no schema change**: a strategy declaring an
  arming trigger whose `required` conditions read the `LIVE` clock is rejected on the existing
  `VALIDATION_ERROR` code, naming the offending condition key. Same code, same shape, new reason —
  so nothing in the published schema tells you it can now happen.

### Removed — no alias exists

- **`SWING_LOW` / `SWING_HIGH` leave the stop and take-profit method enums, and the four S/R
  indicator keys leave the signal vocabulary** (53.0.0, `rename-donchian-channel`). `DONCHIAN_LOWER`
  / `DONCHIAN_UPPER` and `donchian_upper` / `donchian_lower` / `prev_donchian_upper` /
  `prev_donchian_lower` carry the same values; nothing answers to the old names.

- **`get_coin_market_context` is REMOVED** (40.0.0, `retire-get-coin-market-context`). Calling it
  returns an unknown-tool error. There is deliberately **no alias**: a silent redirect would hide a
  payload shape change from a client that never asked for one. Use `get_market_context`.

- **`get_macd_heatmap` leaves the published surface** (41.0.0). Same shape of break, same absence of
  an alias.

- **`isPrimary` is removed from every published `EvaluatedSignal`** (38.0.0) — `get_signal_log`,
  `get_public_agent_signal_log_detail`, and every other tool returning a signal scorecard. Reading it
  now finds the key absent rather than false.

### Reshaped output — the same call returns a different shape

- **Report headers, glosses and signal indicator keys are renamed for the Donchian channel**
  (53.0.0, `rename-donchian-channel`). Every report surface — `preview_strategy_report`,
  `get_strategy_section_template`, the agent prompt previews — renders `donchianHi` / `donchianLo`
  and their `dist_…` / `…_rank_near` forms where it rendered `swingHi` / `swingLo`, with the labels
  *20-bar high* / *20-bar low* and glosses that say what the number is (the highest high / lowest low
  of the last 20 closed bars — the channel's edges). Signal definitions
  (`get_strategy_signal_definition`, `list_strategy_signals`) and signal-log `indicatorValues`
  carry `donchian_upper` / `donchian_lower` / `prev_donchian_upper` / `prev_donchian_lower` for the
  four S/R signals. Signal ids, the `SUPPORT_RESISTANCE` module and its display names are unchanged.

  **Read the new keys.** A reader keyed on `swing_high` / `swing_low` finds nothing; the values are
  the same numbers under the new keys.

- **The stored entry discipline no longer names a level source** (52.0.0, `derive-entry-level`).
  `StrategyDTO.entry` (`get_strategy`, `list_strategies`, the `fork_strategy` / `archive_strategy` /
  `restore_strategy` envelopes) and the apply envelope's `postState.entry` lose `levelSource`.
  `TradeOutcomeDTO.entryDiscipline` (`get_trade_outcome_by_decision`, `list_trade_outcomes`) loses
  it and gains `levelOffsetAtrMultiple: number | null` — the offset in force at the fire, `null` on
  rows written before its column existed. A reader that rendered the level source renders the
  geometry from `trigger` and the outcome's `direction` instead: which edge and which order shape
  are a pure function of those two fields, so no stored copy is served.

- **`update_strategy_signal_rule` gains its own response envelope** (51.0.0,
  `fix-signal-rule-patch-semantics`). It no longer shares `{ strategy }` with its siblings. The
  response is `{ strategy, ruleChanges }`, where `ruleChanges` is the server's own before/after
  pair for the edited signal — `[{ signalId, before, after }]`, each side a full rule object. It is
  `null` when the mutation changed no rule, **never `[]`**.

  **Report the change from that pair, not from memory.** The planner always computed the diff and
  the tool discarded it, so a caller narrating what it just did had only its own recollection of
  the before-value. One production edit shipped a wrong receipt on top of a wrong write that way,
  and the write was unreconstructable from the audit trail afterwards.

  Additive, but published on a `.strict()` shape — a decoder pinned to the old two-key object
  rejects the new key. `fork_strategy`, `archive_strategy` and `restore_strategy` keep the shared
  `StrategyResponseSchema` and publish exactly what they did; it was deliberately NOT widened for
  them, so this reshape reaches one tool only.

- **An entry void now names the gate that refused it** (49.5.0,
  `fix-arming-trigger-clock-authority`), on `get_radar_activity_summary`. In the cause rollup, the
  `ENTRY_VOID` group's `gateCode` widens from always-`null` to `QualificationGateCode | null`: a
  conditions-side void carries the gate that blocked — `AGGREGATE_BELOW_MIN`,
  `REQUIRED_COUNT_BELOW_MIN`, `REQUIRED_CONDITION_FALSE` — while a band void stays `null`, because
  that void happens on a reading that qualified and has no failing gate to name.

  A client that renders the field through the same enum the response already uses on four other
  cause arms needs no change. One that treated it as a literal `null` — a strict decoder pinning the
  type, or a branch keyed to its absence — sees a value it did not expect. That is the whole
  migration.

  Why it moved: the group previously collapsed every conditions-side void under one label. The
  first 26 in production carried that label while two different gates had produced them, and none of
  them was a required condition being false. The rollup ships counts rather than rows, so the gate
  could not be recovered client-side.

- **The normalized report section loses `timeframe`** (48.0.0, `remove-section-anchor-override`), on
  every tool that publishes a strategy: `get_strategy`, `fork_strategy`, `archive_strategy`,
  `restore_strategy`, `update_strategy_signal_rule`, `apply_strategy_plan`, and
  `compile_strategy_plan`'s post-state. A strict parser rejects the shorter object; a lenient one
  reads a section whose anchor is the strategy timeframe, which it now always is.

- **`get_strategy_column_contract` renames its anchor, both ways** (48.0.0). The request field
  `sectionTimeframe` becomes `anchorTimeframe` — same meaning, and still optional. On the response,
  `timeframe.requiresSectionTimeframe` becomes `requiresAnchorTimeframe`, and
  `timeframe.sectionTimeframeOverrideAllowed` is **removed**: it published whether a column could go
  in an anchor-overridden section, and no section can be overridden. One call also stops being
  refused — a timeframe-inert metric supplied with an anchor now compiles.
  `REPORT_COLUMN_SECTION_TIMEFRAME_UNSUPPORTED` leaves the `authoringCode` vocabulary.

- **`RenderedSection.notes` stops carrying provenance** (42.0.0, `separate-section-facts-from-read`),
  on `preview_strategy_report`, `compile_strategy_plan` and `get_market_context`. A new REQUIRED
  `provenance: string[]` carries it instead. A client reading provenance out of `notes` now reads an
  author's prose, or nothing — which is a silent misread, not an error.

- **`preview_strategy_report.renderedSections[]` gains `authoredNote`** (43.0.0), the author's read
  for a custom row and `null` on a platform row. Additive, but published on a `.strict()` shape.

- **`get_radar_activity` serves its evaluation curve on the FIRST PAGE ONLY** (37.0.0), and
  `get_radar_activity_summary` is added. A client reading the curve off a later page finds it absent.

### Widened enum — new members your own copy rejects

- **The stop and take-profit method enums gain `DONCHIAN_LOWER` / `DONCHIAN_UPPER`** (53.0.0,
  `rename-donchian-channel`), replacing `SWING_LOW` / `SWING_HIGH` on the signal-pipeline detail
  schemas — trade-setup options, R:R-rejected pairs and candidate levels. A copy of either enum that
  rejects unknown members must add the two new ones; the two old ones never appear again.

- **`TradeExecutionFailureReason` gains `LEVEL_NOT_RESTABLE`** (52.0.0, `derive-entry-level`): a
  level entry refused at placement because its resting price sat on the wrong side of the exchange
  mid — a buy stop at or below it, a buy limit at or above it, and the mirror for a sell. It appears
  on the `list_signal_logs` failure-reason filter input and on the signal-pipeline execution
  summary's `failureReason`, with origin `CLIENT_GATE`. There is no distance limit: a level far from
  the mark rests until its bar validity expires.

- **The authorable metric vocabulary widens by 29 keys** (46.1.0, `add-indicator-catalog-coverage`):
  Keltner (`KC_UPPER`/`KC_MID`/`KC_LOWER`), Supertrend (`ST_LINE`/`ST_DIR`), Hull (`HMA20`),
  WaveTrend (`WT1`/`WT2`), QQE (`QQE_RSI_MA`/`QQE_STOP`), Parabolic SAR (`PSAR`), Ichimoku
  (`ICHI_CONV`/`ICHI_BASE`/`ICHI_SPAN_A`/`ICHI_SPAN_B`/`ICHI_LAG`), Williams %R (`WILLR14`),
  Stochastic RSI (`STOCH_RSI14`), session pivots (`PIVOT_P`/`PIVOT_R1`–`R3`/`PIVOT_S1`–`S3`), plus
  four already-published fields that became addressable: `BB_UPPER`, `BB_LOWER`, `DI_PLUS`,
  `DI_MINUS`.

  Additive on the wire — every request you can send today is still accepted. It is called out here
  because a client holding its own closed copy of the metric enum rejects the new members, and
  because **an agent holding a cached belief that these are inexpressible will substitute for a
  primitive the platform now serves**. That failure raises no error at all: the author is simply told
  a strategy cannot be built.

- **`EntryTrigger` gains `STOP_THROUGH_LEVEL` and `ON_RETEST`, and `EntryLevelSource` is published
  for the first time** with four members (47.0.0). Additive on their own; the required keys above are
  what make that bump a major.

- **Each signal-checklist item's `measured` object gains a required `triggered` boolean** (47.2.0,
  `fix-entry-prompt-signal-evidence`) on `get_signal_log` and `get_public_agent_signal_log_detail`,
  on the `numeric` and `categorical` arms. Additive and MINOR — a client ignoring it is unaffected —
  but it is named here because a client parsing that output strictly rejects the new key, and because
  leaving 47.2 unlisted would make a reader wonder what happened to it.

  The `unavailable` arm deliberately does **not** carry `triggered`: "the claim could not be joined to
  a stored result" and "the signal did not fire" are different states, and leaving the key off that
  arm makes conflating them a type error rather than a convention.

## Contract history — v12 → v36

> **The number in this heading is a CONTRACT version, not this package's version.** The npm badge at the top
> tracks the proxy's own code; this section tracks the server's wire contract. They move independently **by
> design**: a contract move needs no release here, because a connected proxy relays the contract out of the
> upstream handshake rather than declaring it. So a package on `31.x` listing contract history up to `36.x` is
> correct — not a version someone forgot to bump. Read the live pair from the startup stderr lines or
> `GET /mcp/version`; see [Rediscovery & versioning](#rediscovery--versioning) for why.

These are the server contract breaks between contract 12 and contract 36. Most of the span shipped while the package sat at `11.0.0`; contract 31 landed after this package reached `31.0.0`, and the two numbers matching is coincidence — since v31 the announced contract is relayed from the server, so a package version says nothing about a contract version. They are **contract** history, not package releases: from v31 the announced contract is relayed live and a contract move is no longer a release here. Grouped by what a client observes, with the contract version that introduced each.

**The proxy itself is unchanged.** It embeds no schemas, pins no contract version, and forwards `{ request }` verbatim. Every break below lands on whatever *authors* the payload or *reads* the result, never on the proxy.

### Changed meaning, unchanged shape — the one to read first

- **`compile_strategy_plan` is no longer read-only or idempotent** (33.0.0, `rehydrate-approved-plan-on-apply`). Its input, its output and its behaviour toward your strategy are unchanged — it still changes no strategy, agent or revision — but it now parks the plan it approved for its own apply to read, and **each call mints a distinct record and a distinct token**. `readOnlyHint` and `idempotentHint` are published as `false` accordingly. A client that retried a compile that had already succeeded, or fanned two out in parallel for one edit, was doing so on the strength of the old annotation: **do neither.** Compile once per reviewed payload. Nothing in the payload tells you this moved.

- **Position-size presets are now a RISK BUDGET** (30.0.0, `split-stop-geometry-from-risk`). `smallPct` / `mediumPct` / `largePct` stop denoting a share of the ORDER (`notional = pct / 100 × headroom × leverage`) and start denoting the share of headroom placed **at risk** (`notional = headroom × riskPct / stopDistancePct`, capped at the margin headroom can post). Same keys, same types, same accepted range: **nothing in the payload tells you the meaning moved.** A client still sending `22.0` for MEDIUM is asking to risk 22% of its budget on one trade rather than roughly 2%. Typical risk budgets are `0.5`–`3`; the platform defaults moved to `1 / 2 / 3`. Leverage stops multiplying order size and becomes a constraint only.

### Rejected input — something you author is no longer accepted

- **`upsert_deployment_policy` requires `enabled`** (35.0.0, `add-arena-deployment-pause`). The arena deployment gains an owner-owned pause, and the flag that carries it is **required, not optional** — a body accepted under contract 34 is refused under 35 without one byte of it changing. Required is the whole point: this call replaces the entire policy, so an omitted key and an explicit `true` would be the same request on the wire, and every client that rebuilt a policy without the flag would silently resume a deployment its owner had paused. Read the value from `get_deployment_policy` and send it back. **There is no separate pause verb** — pausing and resuming are this same call with the flag flipped.

  Do not reach for `enabled: false` to un-deploy. It keeps every slot and stops play, which is the opposite of withdrawing: `delete_deployment_policy` is the withdrawal verb, and it discards the rules permanently. `upsert_deployment_policy` refuses an empty slot set, and its rejection names both routes.

- **A signal rule flagged `required` at allocation Off is rejected** (34.0.0, `enforce-required-allocation-invariant`). `required` and `allocation` are two independently editable fields encoding one thing — whether and how a signal participates — so `{ required: true, allocation: 0 }` was representable and meant nothing: the scorecard's triggered set already excludes Off, so such a rule could neither satisfy `minRequiredCount` nor block a trade. It is now refused on **every** rule-writing surface — `compile_strategy_plan`, `apply_strategy_plan` and `update_strategy_signal_rule` alike.

  Three things make this one easy to trip over. It is an **input-acceptance narrowing**: a payload accepted under contract 33 is refused under 34 without one byte of it changing. It is **invisible in the published schema** — `zod-to-json-schema` drops effects by construction — so you cannot pre-validate it from `tools/list`, and the typed error IS the contract: read `details.inertRequiredSignalIds`, which carries the complete sorted list of offending signals, rather than the message, which names a bounded prefix. And **nothing is repaired for you**: the server will not raise the allocation (that would invent a scoring weight you never chose) nor clear the flag (that would discard your intent silently). Pick one and resend; either satisfies the boundary.

- **`apply_strategy_plan` no longer accepts the plan** (33.0.0, `rehydrate-approved-plan-on-apply`). Its input narrows to `{ planToken, confirm }`. A `plan` member is **rejected as an unknown key** — not accepted, not ignored, and with no transitional dual shape — so every client that built the payload breaks on the next connection, which before this is what every published surface told it to do. The server keeps the plan its own compile approved and reads it back, so **you copy nothing out of the compile response**: forward `planToken` byte-for-byte and confirm.

  Three consequences worth knowing. The 256,000-byte cap on the apply payload is **gone with the payload**, so a large authored surface no longer becomes impossible to apply through a conversational client; the compiled plan is still capped and compile still enforces it. `PLAN_APPROVAL_NOT_FOUND` joins the error vocabulary for a token no approved plan answers to — already applied, lapsed, or never issued, all one code, because the recovery is the same in each case: compile again. And a validation refusal (a quota, a name collision, a bound agent that changed, a moved catalog) now **leaves the approved plan applicable** — clear the cause and confirm again with the same token while it lives, rather than recompiling.

- **The agent brain is no longer a preset union** (32.0.0, `remove-agent-presets`). `create_intelligence_agent` stops taking the `brain` discriminated union: `modelId` and `behavior` become required top-level fields and the `{ kind: 'PRESET' | 'CUSTOM' }` wrapper is gone, so the old shape fails on the unknown key **and** on two now-missing required fields. `update_intelligence_agent` drops `brainPreset`; `modelId` and `behavior` stay independently optional and are now **always honoured**, closing an accept-and-ignore where a named preset silently discarded a model sent beside it.

- **`apply_strategy_plan` now publishes the same bounds as `compile_strategy_plan`** (31.0.0, resolving #4495). Eleven position-management dials were declared three times server-side and two copies had drifted, so apply advertised `trailingGivebackPct` as a bare number where compile advertised 25–55, and dropped `trailingTriggerR`'s `multipleOf 0.01` — the constraint pinning storage precision so a sub-precision value is rejected rather than rounded onto the trail-from-entry sentinel `0`. Nothing bad could ever commit (the digest would not match), but the refusal you got was a binding mismatch, which arrived as a bare `INTERNAL_ERROR`. Apply's published bounds only **narrow** to compile's; a client that copies values from `approvedPlan.postState`, as it should, is unaffected. Separately the trio `minStopLossAtrMultiple` / `maxStopLossAtrMultiple` / `minRiskRewardRatio` is published as a bare declaration by both tools, its real bounds being runtime-tunable and inexpressible in JSON Schema.

- **The stop-loss ceiling changed unit** (30.0.0). `maxStopLossPct` (a percent of entry) becomes `maxStopLossAtrMultiple` (a multiple of ATR), and the accepted range narrows from `(0, 100]` to `(0, 3]`. It is a rename **and** a re-denomination — mapping the old value onto the new key sends a number one to two orders of magnitude too large. The objects are `.strict()`, so a 29.x client sending `maxStopLossPct` is rejected with an unknown-key error. A new cross-field rule comes with it: `minStopLossAtrMultiple < maxStopLossAtrMultiple` is now a real comparison and is enforced.
- **The grid-confidence and trade-conviction bars left the agent** (28.0.0, `remove-agent-rule-defaults`). `tradingConfig.gridMinConfidence` and `minTradeConviction` are removed from the shared `.strict()` config; a bar is declared on the arena slot or radar slot that fires.
- **The agent no longer carries either entry guard** (26.0.0). `create_agent` and `update_agent` stop
  accepting `tradingConfig.signalTimeoutMinutes` and `tradingConfig.maxEntryDeviationAtrMultiple`.
  The schema is `.strict()`, so a client still sending either is **rejected**, not silently ignored.
  Neither has a replacement key on any surface: unlike the strategy-owned fields below, these have no
  owning surface at all beneath the platform. One `platform_config` value governs the entry-price
  drift budget for every decision, read at evaluation time; one governs how long an entry may stay
  unfilled, snapshotted onto the position at creation. **Remove both keys and send nothing in their
  place.**
- **The arena stopped granting trade authority** (25.0.0, `remove-arena-trade-permissions`). `upsert_deployment_policy` and `preview_deployment_resolution` stop accepting `tradingEnabled`, `minConviction` and `coinRules[]` on a slot.
- **The agent no longer carries an exit policy** (24.0.0). `create_agent` and `update_agent` stop
  accepting `tradingConfig.positionManagement`. The schema is `.strict()`, so a client still sending
  it is **rejected**, not silently ignored. The twelve dials that decide how a stop MOVES after entry
  — break-even arming, trailing engagement and giveback, time-decay tightening — are denominated in
  the setup's own payoff shape (multiples of the trade's initial risk, fractions of take-profit
  distance, minutes since entry) and read no balance, leverage or exposure, so they belong to the
  thesis rather than to the account running it. **Author them on the strategy instead**, through
  `compile_strategy_plan` / `apply_strategy_plan`: the post-state gains the same twelve keys beside
  the trade-level trio, and the plan diff gains a `positionManagement` axis. An agent inherits the
  policy from the strategy it binds. **The umbrella `enabled` flag is deleted rather than moved** —
  each mechanism's toggle is now the whole truth for that mechanism, so "trailing on, management
  off" is no longer expressible, a state the server's own monitor and boot recovery already
  disagreed about.
- **The agent-level trading mode is gone** (23.0.0). `create_agent` and `update_agent` stop
  accepting `tradingConfig.tradingMode`. The schema is `.strict()`, so a client still sending it is
  **rejected**, not silently ignored. Trading on/off is now scoped per deployment — a radar policy's
  `enabled`, an arena slot's `tradingEnabled`, a per-coin `tradeEnabled` — and approval-before-
  execution is the conversational surface's own contract, so the account-level switch that sat above
  both is removed rather than renamed. To stop an agent trading, turn its deployment off (or halt
  the agent); to make one trade autonomously, arm a radar coin or switch trading on for an arena
  slot. **A newly authored arena slot now starts with trading off.**
- **Trailing gained a required threshold** (22.0.0, `add-trailing-trigger-r`). `positionManagement` gains `trailingTriggerR` as REQUIRED (`0`–`2.0`, `0.01` precision, `0` = trail from entry); the object is `.strict()` all-required, so sending `positionManagement` without it is rejected.
- **The strategy regime timeframe became derived** (19.0.0, `remove-strategy-regime-override`). It stops being an authored axis anywhere on the contract and is served read-only.
- **Conditions gained a required `required`** (16.0.0, `add-condition-enforcement-gate`). A condition entry omitting the boolean is REJECTED rather than defaulted.
- **The trade-level policy moved to the strategy** (15.0.0, `move-trade-level-policy-to-strategy`). It leaves the agent authoring surface and joins the setup gates on the strategy.
- **The agent's ATR timeframe axis is gone** (14.0.0, `remove-agent-atr-timeframe-axis`). ATR is sampled on the strategy timeframe, always.
- **Radar's wall-clock condition changed shape** (12.0.0, `unify-deployment-hours-as-sets`).

### Moved or reshaped output — a field you read is somewhere else

- **The signal scorecard stops serializing its entries three times over** (36.0.0, `mcp-signal-log-contents`). `get_signal_log` and `get_public_agent_signal_log_detail` drop `scorecard.triggeredSignals`, `scorecard.primarySignals` and `scorecard.supportingSignals`. Every one held the **same entry objects** `allEvaluatedSignals` already carried, so each is one filter over flags every entry still publishes:

  | Removed | Read instead |
  |---|---|
  | `triggeredSignals` | `allEvaluatedSignals.filter(s => s.triggered)` |
  | `primarySignals` | `allEvaluatedSignals.filter(s => s.triggered && s.isPrimary)` |
  | `supportingSignals` | `allEvaluatedSignals.filter(s => s.triggered && !s.isPrimary)` |

  **Keep the `triggered` half of those last two predicates.** Both collections were triggered-only by construction, so filtering on `isPrimary` alone surfaces signals that never fired — a silent widening, not an error. No field is removed from an entry: the key set on an `allEvaluatedSignals` member is unchanged, every evaluated signal is still returned whether or not it triggered, and `details` prose and `indicatorValues` are intact. There is no opt-in to get the three back and no default filter. Breaking only if you read one of the three names; on an 84-signal / 16-triggered log the duplication was 10,682 bytes, 28% of the scorecard, carrying no information.

- **The fleet roll-up on `list_deployment_policies` drops `unconfigured` and gains `paused`** (35.0.0, `add-arena-deployment-pause`, `fix-arena-deployment-undeploy`). `unconfigured` counted a deployment holding zero slots — a state that can no longer exist, because a stored policy now carries at least one slot and the withdrawn state is the **absence** of a policy rather than an empty one. The bucket was constant `0` at the moment of removal, so no number you read was wrong; a client reading the key still breaks on it, which is why this is a break and not a cleanup. `paused` is the owner's own switch, counted separately from `retired` — an administrator disabling the arena — because conflating them tells an owner to wait for something that will not happen. Every policy lands in exactly one bucket, so the buckets sum to `arenas`: worth asserting if you reconcile these counts.

- **`AdminApprovedModelDTO.isActive` became `lifecycle`** (32.0.0, `remove-agent-presets`) — `AVAILABLE` / `DEPRECATED` / `RETIRED`. The boolean conflated "offered in the picker" with "bound agents may run", so there was no way to stop offering a model without hard-blocking every agent already on it. A client switching on `isActive` must switch on `lifecycle`, and **must not treat `DEPRECATED` as blocked**: that is the state which keeps bound agents running. The agent read DTO drops `brainPreset` in the same move — the marker recorded which named bundle an owner clicked, never a value the runtime read, and the model and soul it stamped are unchanged on every agent.

- **`approvedPlan` is one object, not an operation union** (31.0.0, resolving #4495). It was published as a discriminated union whose discriminator does not survive JSON-Schema conversion, so what actually shipped was a bare `anyOf`: validating a failing compile response gave you every arm's errors with empty instance paths, and the top one typically complained that an UPDATE was missing `creationSeed` — a CREATE-only key — while the field that really failed went unnamed. It is now one object with a literal `operation` discriminator, and `creationSeed`, `expectedRevision` and `bindingImpact` are **required and nullable on every operation**: a CREATE plan carries a seed and `expectedRevision: null`, an UPDATE/RESTORE plan the reverse. **If you narrowed on the union arms, read `operation` instead and expect explicit `null`s rather than absent keys.** If you read those fields without narrowing, nothing changes except that they may now be null.

- **`get_radar_activity` gained an `EDGE_REARM` variant** (29.0.0, `add-radar-anchor-rearm`), and every member gained five `rearm*` margin keys plus a `rearmReasons` discriminator. Breaking on both counts if you parse the union strictly.
- **`get_trading_config_catalog` drops four trade-default seeds** (27.0.0) — `defaultMinAtrPct`,
  `defaultMinStopLossPct`, `defaultMaxStopLossPct` and `defaultMinRiskRewardRatio` leave `defaults`.
  Each seeded a per-agent field that is now **strategy-owned**: the shared `.strict()`
  `TradingConfigSchema` already rejected all four as unknown keys, so the catalog was advertising
  defaults no request could apply. A client that wants the stop-loss band, the ATR floor or the
  risk-reward minimum reads them from the bound **strategy**, which owns and materializes them.
  Nothing is added in their place. `defaultMaxEntryDeviationAtrMultiple` and `defaultTtlMinutes` are
  untouched — those are not seeds but the platform values that govern.
- **`get_radar_activity` gained `blockReasonCode` on every member** (21.0.0, `fix-block-reason-attribution`) — non-null only on `BLOCKED_BEFORE_EVALUATION` rows written after 2026-08-17.
- **`signal_pipeline`'s decision became a discriminated union** (20.0.0, `add-decision-skip-attribution`). `ENTER`/`GATED` carry the seven level fields as REQUIRED; `SKIP` omits them entirely rather than sending nulls, so reading `entryPrice` without narrowing the verdict finds the key absent.
- **`get_radar_activity` gained an `EVALUATION_OUTCOME` member** (18.0.0, `add-radar-fire-outcome-journal`), and every existing member gained `evaluationOutcome` + `screenReason`.
- **Scalar families became placeable modules** (13.0.0, `add-scalar-family-modules`); six opt-in scalar headers moved off the shared `session-field` section key.
- **Both entry guards leave every agent-returning shape** (26.0.0) — the read side of the input
  removal above. `AgentTradingConfigDTO` drops `signalTimeoutMinutes` and
  `maxEntryDeviationAtrMultiple` on every tool that serves an agent, and the explorer trading spec
  and the agent-review payload drop them too. `get_trading_config_catalog` drops
  `defaultSignalTimeoutMinutes` from its defaults and the
  `minimumMaxEntryDeviationAtrMultiple` / `maximumMaxEntryDeviationAtrMultiple` pair from its bounds —
  a bound pair that constrained a per-agent field which no longer exists.
  `defaultMaxEntryDeviationAtrMultiple` and `defaultTtlMinutes` **stay**, and are now the values that
  actually govern rather than seeds a new agent copies. A client reading these objects strictly must
  drop the removed keys.
- **`positionManagement` leaves every agent-returning shape** (24.0.0) — the read side of the input
  removal above. `AgentTradingConfigDTO` drops the nested block on every tool that serves an agent,
  and the explorer trading spec drops it too. A client reading these objects strictly must drop the
  key; one that wants the policy reads it from the bound strategy.
- **`get_trading_config_catalog` drops `positionManagementPresets`** (24.0.0) — the pistol ladder
  (COLT / WEBLEY / BERETTA / LUGER / WALTHER) is **retired, not renamed**. Once the values live on
  the strategy, the strategy IS the named bundle, with its own name, description and revision
  history; a parallel vocabulary of anonymous bundles beside it would be a second name for the same
  thing. There is no replacement enum to migrate to — list strategies instead. The catalog's
  `defaultPositionMgmt*` trading defaults go with it, for the same reason: nothing seeds an agent's
  exit policy any more.
- **`tradingMode` leaves every agent-returning shape** (23.0.0) — the read side of the input
  removal above. `AgentTradingConfigDTO` drops it on every tool that serves an agent, and so do the
  agents-hub permission envelope, the explorer entry, and both public-profile shapes. A client
  reading these objects strictly must drop the key.
- **`DeploymentResolvedResolutionDTO` drops `agentTradingMode`** (23.0.0) — the field 10.0.0 added,
  now unnecessary: with no account layer to overlay, the resolved `tradingEnabled` is the whole
  answer about whether the previewed deployment trades.

### Widened enum — new members your own copy rejects

- **`DeploymentResolutionStatus` gains `PAUSED`** (35.0.0, `add-arena-deployment-pause`), returned by `get_deployment_policy`, `list_deployment_policies` and `preview_deployment_resolution`. A client switching exhaustively on the status must add the branch. Two properties are not obvious from the name: it is answered **before any slot is resolved**, so a paused deployment discloses no agent identity and carries `regimeUsed: null`; and its `targetSession` is nullable, because a deployment can be paused on an arena with no upcoming session and the pause is still the true answer. Do not re-derive the pause from the `enabled` flag beside it — the served status is the answer on every path, and those two disagreeing is the defect this closed.

- **Seven plan-token failures became their own error codes** (31.0.0, resolving #4495). `TOKEN_EXPIRED`, `TOKEN_BINDING_MISMATCH`, `INVALID_TOKEN_SIGNATURE`, `INVALID_TOKEN_FORMAT`, `INVALID_TOKEN_CLAIMS`, `INVALID_DIGEST_MATERIAL` and `INVALID_MATERIALIZATION_FENCE` all used to arrive as a bare `INTERNAL_ERROR` — the server wrote the true reason to its own audit log and discarded it at the boundary, so a refused apply told you nothing. They now arrive as themselves, over MCP and HTTP alike, with 409-class status for the two state-conflict codes and 400-class for the five malformed-material codes. A client switching exhaustively on error codes must add the branches; one rendering unknown codes generically is unaffected. Two are worth handling by name: `TOKEN_EXPIRED` means recompile (the token lives five minutes), and `INVALID_TOKEN_SIGNATURE` usually means the token was not forwarded verbatim — it is opaque, so copy it byte-for-byte and never retype or reconstruct it.

- `TradeEvaluationAttemptReasonCode` gains `OPEN_POSITION_CHECK_UNAVAILABLE` (19.4.0), splitting a code that previously reported a platform fault as a fact about your account.
- `QualificationGateCode` gains `REQUIRED_CONDITION_FALSE` (19.3.0), from the SCAN-stage gate that now evaluates required conditions before a fire edge is spent.
- `TradingPipelineGateStage` gains `EVALUATION` and `TradeEvaluationAttemptReasonCode` gains `EVALUATION_FAULTED` (18.2.0).

### What you do NOT need to do

Nothing in the proxy changes. No configuration, no environment variable, no call-shape change on this package's own surface. If your client discovers tools live and reads results generically, `npm i @battlegrid/mcp-server@30` is the whole upgrade.

### Additive in the same span

- **`get_regime_snapshot` publishes the evidence behind the verdict** (47.1.0,
  `publish-regime-classification-evidence`). The snapshot gains `evidence`: the quantities the
  classifier read, the gates it tested them against, the signed margin to the gate deciding whether
  the current label survives, and the two decision facts only the classifier holds — `gateState`
  (`cleared` / `held` / `dropped`) and `directionSource` (`di` / `ema`). Nothing narrows; a client
  that ignores the field is unaffected.

  Read `gateState` before you trust a trend label: **`held` means the ADX hysteresis buffer is
  carrying the PREVIOUS bar's label rather than this bar re-confirming it** — a materially weaker
  claim wearing the same word, and one no client could previously detect. `directionSource: 'ema'`
  is the same shape of warning: the direction came from the fallback that fires precisely when the
  DI spread is indecisive. The margin is signed so **positive always means "the current label
  survives by this much"**, in every gate state, so it is safe to branch on its sign.

  `conviction` is a BRANCH DISCRIMINATOR, not a confidence: it encodes *which* rule in the priority
  ladder matched, not how comfortably it matched. The margins carry comfort. A client reading
  conviction as a strength score is reading it wrong, and always was — this release just makes the
  alternative available.

- **Thirteen metric keys join the catalog** (47.1.0) — the `regime` family gains `REGIME_STATE`,
  `REGIME_CONVICTION`, `REGIME_RUN_BARS`, `REGIME_TREND_GATE`, `REGIME_TREND_MARGIN`,
  `REGIME_TREND_SOURCE`, `REGIME_DI_SPREAD`, `REGIME_VOL_ATR_RATIO`, `REGIME_VOL_BBW_RATIO`,
  `REGIME_MOM_BULL_VOTES`, `REGIME_MOM_BEAR_VOTES`, `REGIME_CRASH_MARGIN` and `REGIME_CRASH_LATCH`,
  making the composite regime and its evidence addressable in a report column or condition for the
  first time. Only a client that switches exhaustively on `MetricKey` needs new branches.

  Not a contract change, but worth knowing if you author conditions: the report grammar's regime
  metrics now resolve from the **confirmed close** on every path. They previously resolved from the
  forming bar when a report was rendered and the confirmed close when the scan swept, so the same
  condition could read differently in preview than in production. Same wire shape; same bar
  everywhere now.

`27.1.0` exit-policy authoring input on `compile_strategy_plan` · `19.2.0` `get_account_state` account identity · `19.1.0` Standing Orders marker authoring · `18.4.0` `list_gate_blocks` summary groups · `18.3.0` radar maintenance pause · `18.1.0` protection geometry · `17.2.0` break-even/trailing status · `17.1.0` `get_signal_log` condition evaluation · `13.1.0` four owner-scoped read tools · `12.1.0` cross-venue spot price metrics · `11.1.0` discoverable rate limit.

## v11 and earlier — contract history (v6 → v11)

> **Historical.** These notes are keyed to the package versions that once paired with contract versions. That pairing ended at v31 (above); the breaks themselves are still real, and still describe the server's contract as it moved from 6.0.0 to 11.0.0.

**v11 paired with the BattleGrid server's MCP contract v11.x.** Under the pairing rule then in force, the package version tracked the server's wire contract because the proxy announced `battlegrid@<package version>` in its own stdio handshake.

This release absorbs **six** breaking contract majors at once. The published package went from `5.0.0` straight to `11.0.0`, so no `6.x` through `10.x` client exists to upgrade from — the breaks are therefore grouped by **what you will observe**, with the contract version that introduced each, so a client hitting a specific rejection can find it here.

**The proxy itself is unchanged.** It embeds no schemas, pins no contract version, and forwards `{ request }` verbatim. Every break below lands on whatever *authors* the payload or *reads* the result, never on the proxy.

### Rejected input — something you author is no longer accepted

- **Challenge participation is no longer a field you set** (10.0.0). `create_agent` and `update_agent` stop accepting `arenaChallengeEnabled`, and a deployment policy's slot rules and per-coin rules stop accepting `challengeEnabled`. All four schemas are `.strict()`, so a client still sending any of them is **rejected**, not silently ignored. Challenge participation is now *identical* to effective trade permission, resolved per coin: to stop an agent taking challenges at a venue, turn that venue's trading off — at the slot, or per coin for finer grain — using fields you already have.
- **`VOLUME_RATIO` is retired and replaced by `RVOL`** (6.0.0). `MetricKeySchema` auto-derives from the server's metric catalog, so the published enum simply stops accepting the old key: a column authored with `metric: 'VOLUME_RATIO'` is rejected against the enum. **No alias exists** — deliberately. The catalog audit adjudicated the old name as a name-level lie (the value is current volume ÷ its 20-period average, a *multiple*), and the correction was made at the root rather than grandfathered. If you hit an enum rejection naming `VOLUME_RATIO`, this note is the match.
- **`BB_WIDTH` can no longer be ranked** (8.0.0). `{ metric: 'BB_WIDTH', transformId: 'rank' }` is now rejected. `BBwidth` is a price-unit spread (`upper − lower`) that had falsely declared `percent`, and that declaration was the only thing admitting it to exchange-wide ranking — the ordinal it produced sorted by token denomination rather than by compression. It re-declares `signedPrice` and leaves the ranked contract. **Rank `BB_WIDTH_PCT` (`bbWidthPct`) instead**, which ships in the same release: the capability moved, it was not removed.

### Silently non-matching — a generated header you match on moved

This is the failure mode with no error attached to it. Nothing is rejected; your matcher simply stops finding the column.

- **`vol` → `RVOL`** (6.0.0), and with it **`vol_trend` → `RVOL_trend`** and **`vol_rank_hi` → `RVOL_rank_hi`**. The header code moves with the metric key, because every generated header over that metric derives from the code alone.
- **`BBwidth_rank_lo` no longer exists** (8.0.0) — it was the header of the ranked pairing retired above.

### Moved or reshaped output — a field you read is somewhere else

- **`estimatedTokenCount` is gone** (7.0.0). `preview_strategy_report` and `compile_strategy_plan` no longer carry it; the same number now sits one level deeper as **`budgetUsage.estimatedTokens.used`**, paired with the `cap` that governs it — so a client reading the count changes one path and gains the ceiling it was never told. `tokenCountModel` is unchanged. Discovery grows to match: `list_strategy_vocabulary` and the report catalog add `budgets.estimatedTokens` and a `previewExecutionLimits` object carrying the serialized-result byte cap and the preview deadline. Those two are published **cap-only** and deliberately have no `used` companion.
- **`approvedPlan.mismatches` changed on both axes** (9.0.0). Both report-coverage codes are renamed off "module", because the module is no longer the unit of coverage:

  | Was | Is now |
  |---|---|
  | `ACTIVE_SIGNAL_MODULE_NOT_IN_REPORT` | `ACTIVE_SIGNAL_DATA_NOT_IN_REPORT` |
  | `REPORT_MODULE_SIGNAL_OFF` | `REPORT_DATA_SIGNAL_OFF` |

  Each mismatch also carries a **required** `data: CoverageDatum[]` — the `(metric, rung)` pairs the mismatch is about: every MISSING datum for the not-in-report code, the PRESENT data for the signal-off code, empty for `REQUIRED_SIGNAL_UNAVAILABLE`. A client switching exhaustively on the old code strings stops matching. Behaviourally, coverage is now decided by whether the report renders a signal's declared metrics at the **rung** that signal reads, not by whether its module appears anywhere — so expect warnings you never saw before, and the disappearance of warnings no composition could clear. Mismatches remain advisory and non-blocking; nothing about apply gates on them.
- **`IntelligenceAgentDTO` drops `arenaChallengeEnabled`** (10.0.0) — the read side of the input removal above. `ResolvedSlotRulesDTO.challengeEnabled` **stays and keeps its shape**; it is now derived server-side, carrying the same value and provenance as `tradingEnabled`, so a client reading the resolved bundle needs no change.
- **`range` is no longer a tuple** (11.0.0). The closed positional pair `[min, max]` becomes the half-open object **`{ min: number; max?: number }`**. It travels through `ScalarSchema`, so this lands on `list_strategy_vocabulary`, `query_report_catalog`, and `get_metric_construction_hints` alike.

  **This one fails silently.** A client reading `range[0]` / `range[1]` gets `undefined` with no error raised — read `range.min` / `range.max` instead, and treat a missing `max` as unbounded above. The tuple could not state the truth about the volume/trade-count family, which is non-negative and unbounded above, and `Infinity` serializes to `null` on the wire. Those six metrics now declare `{ min: 0 }`, and as a consequence their **`far`/`near` rank orderings are no longer offered** — on a non-negative value that pair is a synonym pair under the magnitude gate's documented semantics.

### Widened enum — new members your own copy rejects

- **The published `unit` enum gains `ratio` and `fraction`** (8.0.0), and `RVOL`, `BUY_PRESSURE`, `BB_PCT_B` now emit them instead of `percent` — none of the three is a percentage, and `percent` appended a false `%`. This is a break in the opposite direction from the others: nothing you send is rejected, but a client holding **its own closed copy** of the unit enum rejects the new members. Easy to mistake for a purely additive change. Values are **not** rescaled — `buyPres` and `pctB` stay 0–1, so persisted thresholds comparing against `0.5` keep their meaning.

### What you do NOT need to do

- **No stored strategy needs client action.** Every persisted reference of both kinds — metric keys in section-column rows and revision snapshots, and everything addressing a column by its generated header — was migrated server-side by `20260805120000_rename_volume_ratio_to_rvol.sql`. This is a **client-literal problem only**; there is no stored record to repair.

### Additive in the same span

Nothing here is a break, but a client that enumerates these vocabularies will want them:

- **Four metric keys** join the catalog — `SPOT_CVD`, `PERP_SPOT_FLOW`, `PERP_SPOT_STRENGTH`, `PERP_SPOT_CONFIRMS` — and `includePerpSpotFlow` joins the context-source key set as its 23rd member, opt-in (5.2.0).
- **Two prompt-section `kind`s** join the union: `perp-spot-flow` (5.2.0) and `session-field` (5.1.0). Only a client that switches exhaustively on `kind` needs a default branch; one that renders `content` generically needs nothing.
- **The transform vocabulary grows 15 → 17** (11.0.0) — `efficiency` and `maxShare` join, and both join the chain-outer enum that `chainSuccessors` is served as. Only a client that switches exhaustively on `transformId` needs new branches; one that renders the served labels generically needs nothing.
- **The deployment-policy resolution DTO gains `agentTradingMode`** (10.0.0) — the preview previously reported trade rules for an agent whose *account-level* trading was off, and the account gate is not part of rule resolution. Read it to tell "this rule permits the trade" from "this account can trade at all".
- **`PlatformSectionDTO` gains `columns`** (6.1.0) — a platform section's composition in the same wire shape a custom section's columns already travel in, empty for a registry-declared special. **Not a copy source**, which is where it differs from the identically-shaped `CustomSectionTemplateDTO.columns`: six platform columns pair a metric with `classifyState`, a deliberate composability exclusion that authoring rejects at construction. A client that round-trips these into a custom section will be refused, and that refusal is correct.

## v5 — breaking major (conditions/verdicts fusion)

Retained for authors upgrading from 4.x. Everything below still describes the current contract.

- **`conditionVerdicts` no longer exists.** The verdict now rides the condition that decides it, and precedence is the conditions' own declaration order rather than a separate ordered map:

  ```jsonc
  // v4 — two parallel arrays joined by string key
  {
    "conditions":        [ { "conditionKey": "UP_FADE", "name": "…", "definition": { /* … */ } } ],
    "conditionVerdicts": [ { "when": "UP_FADE", "then": "UP" } ]
  }

  // v5 — one array; the verdict rides its condition
  {
    "conditions": [ { "conditionKey": "UP_FADE", "name": "…", "definition": { /* … */ }, "verdict": "UP" } ]
  }
  ```

  `verdict` is **required and nullable**, never optional: a building block that decides nothing spells its absence as an explicit `null`, never by omitting the key. An omitted `verdict` is a rejected payload, not a defaulted one.

- **A submitted `conditionVerdicts` is REJECTED, not ignored.** Deliberately — a v4 client that forwards the retired field is told what replaced it instead of getting an anonymous unrecognized-key rejection:

  > `conditionVerdicts` was retired in contract 5.0.0 — a condition now carries its own `verdict` (`UP` | `DOWN` | `NEITHER`, or `null` for a building block). Move each mapping onto the condition it named and resubmit.

- **The authorable verdict domain narrowed to three.** `conditionGrammar.verdicts` advertised `['UP','DOWN','NEITHER','UNRESOLVED']` and now advertises `['UP','DOWN','NEITHER']`. `UNRESOLVED` is an *evaluation outcome* — "a deciding condition could not be evaluated" — never an authored intent, so advertising it offered a value the schema then rejected. Any client mirroring the advertised enum into its own validation must narrow with it.

- **The evaluated per-coin verdict is nullable.** Resolution is first-TRUE-decides over the verdict-carrying conditions in declaration order, and its four outcomes are all distinct claims — collapsing any pair loses information a reader needs:

  | Evaluated verdict | Means |
  |---|---|
  | `UP` / `DOWN` / `NEITHER` as a **decision** | The first verdict-carrying condition that resolved TRUE declared it |
  | `NEITHER` as a **fallthrough** | Every verdict-carrying condition resolved FALSE |
  | `UNRESOLVED` | No carrier fired and at least one could not be evaluated — "could not be read", not "read as no setup" |
  | `null` | The strategy declares no verdict-carrying condition at all — it expresses no direction |

  `null` is new in v5; it previously surfaced as `NEITHER`. A client that renders the verdict must handle it without collapsing it into `NEITHER`.

- **The proxy itself is unchanged.** It embeds no schemas, pins no contract version, and forwards `{ request }` verbatim, so the whole break lands on whatever builds the apply projection. Apply takes an allowlisted projection of `approvedPlan`, never the object itself (`diff`, `viability`, `mismatches`, `signalRules`, `creationSeed`, `proposedRevision`, `bindingImpact`, `authoringCatalogDigest` are rejected as unknown keys, and so are the `postState` fields apply does not accept: `id`, `scope`, `systemKey`, `visibility`, `cadence`, `isActive`, `forkedFromStrategyId`). The exact field list is step 5 of **Strategy authoring (compile → review → apply)** below. A client that forwards post-state fields generically — stripping the derived keys rather than enumerating the kept ones — picks the fusion up without an edit; one that enumerates the fields it copies must drop `conditionVerdicts` from that list.

The v3 authoring contract below is unchanged and still current:

- **Strict authoring envelopes.** `get_strategy_section_template`, `update_strategy_signal_rule`, `compile_strategy_plan`, and `apply_strategy_plan` publish one strict server-owned object, `{ request: canonicalPayload }`. In multi-account mode the proxy adds `account` **only** as a sibling of `request`, producing exactly `{ account, request }`; on a call it strips only `account` and forwards the unchanged `{ request }`. It never descends into, flattens, or reconstructs the nested request.
- **`create_strategy` is retired.** Direct strategy creation no longer exists. Author strategies with the compile → review → apply workflow below, and bind them to agents at agent-creation time (`create_intelligence_agent({ …, strategyId })`). There is no alias, shim, or flat-payload fallback.
- **Rediscover after deployment.** Publishing the package does **not** refresh a running proxy's cached capability snapshot. After the server cutover, restart/reconnect the proxy process and re-run `tools/list`, `prompts/list`, and `resources/list`.

> Earlier majors: **v1.x** single/multi-account stdio proxy; **v2.0.0** moved the default `BATTLEGRID_API_URL` to the `/mcp` suffix; **v3.0.0** the strategy-authoring major; **v4.0.0** made `conditions` and `conditionVerdicts` required on the apply post-state; **v5.0.0** fused the conditions/verdicts split (section above). **v6.0.0** through **v11.0.0** were never published as separate package versions — they are absorbed by the v11 cutover at the top. See [Rediscovery & versioning](#rediscovery--versioning).

## Quick Start

### Single account (stdio transport)

```bash
BATTLEGRID_API_KEY=bg_live_xxx npx @battlegrid/mcp-server
```

### Multiple accounts (stdio transport)

```bash
BATTLEGRID_API_KEYS=bg_live_alice_key,bg_live_bob_key npx @battlegrid/mcp-server
```

When multiple keys are provided, the server discovers each account's identity and injects a required `account` parameter into every tool so the AI agent can choose which account to act as.

### Remote server (streamable-http transport)

```
https://mcp.battlegrid.trade/mcp
```

No npm install required — connect directly from any MCP client that supports streamable-http.

## Configuration

### Claude Desktop

**Single account:**

```json
{
  "mcpServers": {
    "battlegrid": {
      "command": "npx",
      "args": ["@battlegrid/mcp-server"],
      "env": {
        "BATTLEGRID_API_KEY": "bg_live_xxx"
      }
    }
  }
}
```

**Multiple accounts:**

```json
{
  "mcpServers": {
    "battlegrid": {
      "command": "npx",
      "args": ["@battlegrid/mcp-server"],
      "env": {
        "BATTLEGRID_API_KEYS": "bg_live_alice_key,bg_live_bob_key"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add battlegrid -- npx @battlegrid/mcp-server
```

Set your API key(s):

```bash
# Single account
export BATTLEGRID_API_KEY=bg_live_xxx

# Multiple accounts
export BATTLEGRID_API_KEYS=bg_live_alice_key,bg_live_bob_key
```

### Cursor

```json
{
  "mcpServers": {
    "battlegrid": {
      "command": "npx",
      "args": ["@battlegrid/mcp-server"],
      "env": {
        "BATTLEGRID_API_KEY": "bg_live_xxx"
      }
    }
  }
}
```

Use `BATTLEGRID_API_KEYS` (comma-separated) for multiple accounts.

### ChatGPT Desktop

ChatGPT Desktop connects via **OAuth 2.1** — no npm package or API key needed. ChatGPT handles the OAuth flow automatically.

1. Open ChatGPT Desktop → **Settings** → **MCP Servers** → **Add Server**
2. Enter the MCP endpoint URL: `https://mcp.battlegrid.trade/mcp`
3. Select **OAuth** as the authentication method
4. ChatGPT discovers OAuth endpoints, registers as a client (Dynamic Client Registration), and opens BattleGrid's consent page
5. Log in to BattleGrid and click **Authorize**

| | Claude Desktop / Cursor | ChatGPT Desktop |
|---|---|---|
| **Transport** | stdio proxy (`@battlegrid/mcp-server`) | Direct HTTPS |
| **Auth** | API key (`bg_live_*`) | OAuth 2.1 (Bearer token) |
| **Setup** | npm package + env vars | URL + OAuth consent |
| **Multi-account** | `BATTLEGRID_API_KEYS` env var | One OAuth grant per account |

## Account management

### Single account

Set `BATTLEGRID_API_KEY` with one API key. All tool calls use that account, and the tools are exactly the server-native shapes — the authoring tools take the strict `{ request }` envelope with no `account` field.

### Multiple accounts

Set `BATTLEGRID_API_KEYS` with a comma-separated list of API keys (one per BattleGrid account). On startup the proxy:

1. Calls `GET /mcp/identity` for each key to discover the account username
2. Injects a required `account` enum parameter into every tool — as a **sibling** of the existing input, never nested inside it
3. Routes each tool call to the correct account using the matching Bearer token, stripping only `account` before forwarding

For the strict authoring tools, the multi-account input is exactly `{ account, request }`:

```json
{
  "name": "compile_strategy_plan",
  "inputSchema": {
    "type": "object",
    "properties": {
      "account": {
        "type": "string",
        "enum": ["alice", "bob"],
        "description": "Which BattleGrid account to use for this action"
      },
      "request": {
        "oneOf": [
          { "properties": { "operation": { "const": "CREATE" } } },
          { "properties": { "operation": { "const": "UPDATE" } } },
          { "properties": { "operation": { "const": "RESTORE" } } }
        ]
      }
    },
    "required": ["account", "request"],
    "additionalProperties": false
  }
}
```

The proxy consumes only the outer `account` and forwards the unchanged `{ request }` upstream. Never put `account` inside `request`, and never flatten request fields beside it.

If a key fails identity discovery (revoked, invalid), it is skipped with a warning. If all keys fail, the process exits. `BATTLEGRID_API_KEYS` takes precedence over `BATTLEGRID_API_KEY` when both are set.

### Getting an API key

1. Go to [battlegrid.trade](https://battlegrid.trade) → **Profile** → **MCP** tab
2. Generate an API key (format: `bg_live_*`)
3. Copy the key immediately — it is shown only once

Each account supports one active key at a time. Generating a new key automatically revokes the previous one — restart any running proxy process afterward, since keys are read once at startup.

For paid games and autonomous wagering, enable **Server-Signed Wagers** in the MCP tab (`mcp:wager` scope). Strategy discovery and non-financial configuration writes only need `mcp:read`.

## Strategy authoring (compile → review → apply)

Strategies are authored through one strict, whole-plan workflow. **Compilation changes no strategy, agent or revision; `apply_strategy_plan` is the only write to the strategy itself** — but compile is not read-only either: it parks the plan its own apply reads, and each call mints a distinct record and token, so compile once per reviewed payload and never retry or parallelise it. Always review the exact returned plan before confirming.

1. **Choose the operation and revision.** `list_strategies` (add `includeInactive:true` when preparing a RESTORE) and `get_strategy` return the current `revision`; thread it into the next revisioned call.
2. **Discover the report vocabulary live.** Walk `list_strategy_categories` → `list_strategy_vocabulary` → `get_metric_construction_hints` → `get_strategy_column_contract`, and use `get_strategy_section_template` / `preview_strategy_report`. Do not guess metric, transform, parameter, template, or enabled-timeframe facts — they are server-discovered.
3. **Compile one complete plan.** Call `compile_strategy_plan({ request })` where the nested request is exactly one strict branch plus a bounded `coinSelection`, `intentSummary`, and `assumptions`:
   - **CREATE** supplies the full new strategy.
   - **UPDATE** supplies at least one changed axis and `expectedRevision`.
   - **RESTORE** targets an owned inactive revision (with any repair axes).
4. **Review before confirming.** Inspect the returned `approvedPlan` (complete post-state, proposed revision, diff, bound-agent impact, expiry) and `reviewContext` (column contracts, point-in-time report preview, open positions, quota/name admission). The plan token expires after five minutes; recompile after expiry or drift.
5. **Apply the plan the server already holds.** After explicit user approval, call `apply_strategy_plan({ request: { planToken, confirm: true } })`. **There is no `plan` member** — one is rejected as an unknown key. The server keeps the plan its own compile approved and reads it back, so nothing is copied out of the compile response and nothing can be mistyped or truncated in transit. Forward `planToken` byte-for-byte exactly as received: it is an opaque signed value, never retyped, paraphrased or rebuilt from memory, and a mangled one addresses no approved plan and is refused. `PLAN_APPROVAL_NOT_FOUND` means no approved plan answers to this token — already applied, lapsed, or never issued — and the recovery is to compile again; so is `TOKEN_EXPIRED` once the five minutes run out. Any other refusal (quota, name collision, a bound agent that changed, a moved catalog) **leaves the plan applicable**: clear the cause and confirm again with the same token while it lives. Changed configuration propagates to every bound agent immediately.

   The authored axes — including normalized `sections` and `conditions`, each condition carrying its own required, nullable `verdict` — belong on the **compile** request. Every derived field (`diff`, `viability`, `mismatches`, `signalRules`, `creationSeed`, `proposedRevision`, `bindingImpact`, `authoringCatalogDigest`, `reviewContext`) is re-derived server-side and rejected as an unknown key if resubmitted, and `conditionVerdicts` is rejected with a message naming its replacement — the verdict belongs on the condition.

`update_strategy_signal_rule({ request })` is the thin, focused one-rule edit. In multi-account mode every one of these calls uses the `{ account, request }` sibling envelope.

**Strategy-bound agents.** Bind a strategy to an intelligence agent at creation time — `create_intelligence_agent({ …, strategyId })` (discover `strategyId` via `list_strategies`). Rebinding via `update_intelligence_agent` requires `confirm:true`. There is no direct `create_strategy` operation.

## Capabilities

Tools, prompts, and resources are **discovered live** from the connected server via `tools/list`, `prompts/list`, and `resources/list`. This package intentionally does not copy the server's catalog, formulas, signal IDs, or defaults — inspect the live connection for the authoritative, current surface. Broadly, the server exposes game play (Market Grid), market context, account state, leaderboards, intelligence agents and automation, strategy discovery/authoring, and trading signals/decisions.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BATTLEGRID_API_KEYS` | One of these | Comma-separated API keys for multiple accounts |
| `BATTLEGRID_API_KEY` | One of these | Single API key (fallback if `BATTLEGRID_API_KEYS` not set) |
| `BATTLEGRID_API_URL` | No | Override server URL (default: `https://mcp.battlegrid.trade/mcp`) |

## Rediscovery & versioning

- **The announced contract is relayed, not declared.** The proxy reads the upstream server's identity from the handshake it just completed and re-announces it verbatim to the local client. A local client therefore always reads the contract it will actually reach, and the package version is free to mean only what it should: this proxy's own code. **There is no pairing rule to keep, and no publish-time deploy gate** — a released package makes no claim about the server, so there is no ordering between a release here and a deploy there. This replaces the `MAJOR.MINOR` pairing that held through v11; see [v12](#v12--the-announced-contract-is-read-from-the-server-not-declared-here).
- **Fails closed, never falls back.** If a connected server announced no `serverInfo` — a protocol violation, since it is required in a successful `initialize` result — the proxy refuses to start rather than substituting its own version. There is no honest number to announce in that case, and announcing a dishonest one silently is the failure this design removes.
- **Rediscover after a server cutover.** The proxy resolves its catalog on first use and then caches it for the life of the process; a resolution that *failed* is retried on the next request, but a server deploy is never noticed. Package publication does not refresh it either. Restart/reconnect the proxy and re-run `tools/list`, `prompts/list`, and `resources/list` after the server deploys.
- **Restart after key rotation.** API keys are read once at process startup; rotate a key, then restart the proxy.

| Version | Changes |
|---------|---------|
| 1.x | Single/multi-account stdio proxy, identity discovery, connection retry, capability discovery |
| 2.0.0 | Default `BATTLEGRID_API_URL` moved to the `/mcp` suffix |
| 3.0.0 | Strategy-authoring major: strict `{ account, request }` authoring envelopes with strip-only-account routing, compile → review → apply workflow, strategy-bound agent creation, and removal of the retired `create_strategy` operation |
| 3.0.1 | Docs only — `apply_strategy_plan` now takes `{ plan, planToken, confirm }` instead of `{ approvedPlan, … }`; the server re-derives every planner-derived field and rejects resubmitted ones as unknown keys. No proxy behavior change |
| 4.0.0 | Realigns the package major with the server's MCP contract v4.0.0, which broke on the conditions axis: `apply_strategy_plan` requires `conditions` and `conditionVerdicts` on the plan post-state. No proxy code change — the version is the client-facing signal, and the proxy's handshake carries it |
| 5.0.0 | Pairs with the server's MCP contract v5.0.0, the conditions/verdicts fusion: `conditionVerdicts` is retired and rejected with a message naming its replacement, each condition carries a required nullable `verdict`, precedence is the conditions' declaration order, the advertised authorable verdict domain narrows to `UP`/`DOWN`/`NEITHER`, and the evaluated per-coin verdict is nullable. No proxy code change — the version is the client-facing signal, and the proxy's handshake carries it |
| **5.1.0** | Pairs with the server's MCP contract v5.1.0, which is **additive**: `session-field` joins the prompt-section `kind` union — a section whose rows are not coins, carrying facts about the field as a whole. Nothing is removed and nothing previously accepted is rejected, so a 5.0.x client keeps working for every call it already makes; only a client that switches exhaustively on section `kind` needs a default branch, while one that renders `content` generically needs nothing. No proxy code change — the proxy copies `sections` opaquely and never enumerates kinds |
| 5.2.0 | Server contract v5.2.0, **additive**: four `MetricKey`s join the published catalog vocabulary (`SPOT_CVD`, `PERP_SPOT_FLOW`, `PERP_SPOT_STRENGTH`, `PERP_SPOT_CONFIRMS`), `includePerpSpotFlow` joins the context-source key set as its 23rd member (opt-in — no existing agent's report changes), and `perp-spot-flow` joins the prompt-section `kind` union. Same client impact as 5.1.0: only an exhaustive switch on `kind` needs a default branch. Never published as a package version |
| 6.0.0 | Server contract v6.0.0, **breaking**: `VOLUME_RATIO` is retired and replaced by `RVOL`, and its generated header code moves `vol` → `RVOL` at the same time. `MetricKeySchema` auto-derives from the catalog, so the published enum simply stops accepting the old key — an input-acceptance narrowing, the same shape as the v4 and v5 breaks. Two distinct failure modes: authoring a column with `metric: 'VOLUME_RATIO'` is rejected against the enum, and matching rendered headers on `vol` (or `vol_trend` / `vol_rank_hi`) silently stops matching. No alias survives, deliberately. Every persisted reference was migrated server-side, so only client-side literals need action. Never published as a package version |
| 6.1.0 | Server contract v6.1.0, **additive**: `PlatformSectionDTO` gains `columns` — a platform section's composition in the same wire shape a custom section's columns already travel in, empty for a registry-declared special. **Not a copy source**: six platform columns pair a metric with `classifyState`, a deliberate composability exclusion that authoring rejects at construction, so a client that round-trips these into a custom section is refused — correctly. Never published as a package version |
| 7.0.0 | Server contract v7.0.0, **breaking**: the strategy-report preview limits became discoverable and the bare token count was removed. `preview_strategy_report` and `compile_strategy_plan` no longer carry `estimatedTokenCount`; the same number sits one level deeper as `budgetUsage.estimatedTokens.used`, paired with the `cap` that governs it — so a client reading the count changes one path and gains the ceiling it was never told. `tokenCountModel` is unchanged. Discovery adds `budgets.estimatedTokens` and a `previewExecutionLimits` object (serialized-result byte cap, preview deadline), both published cap-only. Never published as a package version |
| 8.0.0 | Server contract v8.0.0, **breaking**, on two axes. `BB_WIDTH × rank` is no longer authorable: `BBwidth` is a price-unit spread that falsely declared `percent`, which was the only thing admitting it to exchange-wide ranking, so it re-declares `signedPrice` and leaves the ranked contract — `{metric: 'BB_WIDTH', transformId: 'rank'}` is rejected and `BBwidth_rank_lo` stops matching, with `BB_WIDTH_PCT` (`bbWidthPct`) shipping as the comparable replacement. Separately the published `unit` enum **widens** with `ratio` and `fraction`, and `RVOL`, `BUY_PRESSURE`, `BB_PCT_B` emit them instead of `percent` — a break for a client holding its own closed copy of that enum, which is the opposite direction from an input narrowing. Values are not rescaled: `buyPres` and `pctB` stay 0–1. Never published as a package version |
| **9.0.0** | Server contract v9.0.0, **breaking**: `compile_strategy_plan`'s `approvedPlan.mismatches` changes on both axes. Both report-coverage codes are renamed off "module" (`ACTIVE_SIGNAL_MODULE_NOT_IN_REPORT` → `ACTIVE_SIGNAL_DATA_NOT_IN_REPORT`, `REPORT_MODULE_SIGNAL_OFF` → `REPORT_DATA_SIGNAL_OFF`), and each mismatch carries a required `data: CoverageDatum[]` — the `(metric, rung)` pairs it is about. A client switching exhaustively on the old code strings stops matching. Coverage is now decided by whether the report renders a signal's declared metrics at the rung that signal reads, so expect warnings never seen before and the disappearance of warnings no composition could clear; mismatches stay advisory and non-blocking. Never published as a package version |
| 10.0.0 | Server contract v10.0.0, **breaking**: challenge participation stops being a declared setting anywhere and becomes identical to effective trade permission, resolved per coin. `create_agent`/`update_agent` stop accepting `arenaChallengeEnabled`, and a deployment policy's slot and per-coin rule shapes stop accepting `challengeEnabled` — all four are `.strict()`, so a client still sending them is rejected rather than ignored, the same input-acceptance narrowing that made v4, v5, v6 and v8 majors. `IntelligenceAgentDTO` drops `arenaChallengeEnabled`; `ResolvedSlotRulesDTO.challengeEnabled` stays and keeps its shape, now derived server-side with the same value and provenance as `tradingEnabled`. The resolution DTO also gains `agentTradingMode` — the preview previously reported trade rules for an agent whose account-level trading was off. Never published as a package version |
| **11.0.0** | Server contract v11.0.0, **breaking**: a catalogued numeric output's `range` changes shape — the closed positional tuple `[min, max]` becomes the half-open object `{ min: number; max?: number }`, travelling through `ScalarSchema` into `list_strategy_vocabulary`, `query_report_catalog` and `get_metric_construction_hints`. A client reading `range[0]`/`range[1]` gets `undefined` **with no error**, which is the silent failure mode a version exists to prevent. The driver: the tuple could not state the truth about the volume/trade-count family — non-negative and unbounded above — and `Infinity` serializes to `null` on the wire; those six metrics now declare `{ min: 0 }` and no longer offer `far`/`near` rank orderings, which on a non-negative value are a synonym pair. Additive alongside it: the transform vocabulary grows 15 → 17 (`efficiency`, `maxShare`), both joining the chain-outer enum served as `chainSuccessors`. **The last version published under the pairing rule.** No proxy code change — the version was the client-facing signal, and the proxy's handshake carried it |
| 12.0.0 | Server contract v12.0.0, **breaking**: radar's wall-clock condition changes shape (`unify-deployment-hours-as-sets`) |
| 12.1.0 | Server contract v12.1.0, **additive**: `SPOT_CLOSE_CB` / `SPOT_CLOSE_BN` join the metric catalog |
| 13.0.0 | Server contract v13.0.0, **breaking**: scalar families become placeable modules; six scalar headers leave the `session-field` key |
| 13.1.0 | Server contract v13.1.0, **additive**: four owner-scoped read tools join the catalog, closing web-client parity gaps |
| 14.0.0 | Server contract v14.0.0, **breaking**: the agent's ATR timeframe axis is removed — ATR samples on the strategy timeframe |
| 15.0.0 | Server contract v15.0.0, **breaking**: the trade-level policy moves off the agent onto the strategy |
| 16.0.0 | Server contract v16.0.0, **breaking**: a strategy condition gains a REQUIRED `required` boolean; omitting it is rejected |
| 17.1.0 | Server contract v17.1.0, **additive**: `get_signal_log` gains `log.conditionEvaluation` |
| 17.2.0 | Server contract v17.2.0, **additive**: position rows gain `breakEvenStatus` / `trailingStatus` |
| 18.0.0 | Server contract v18.0.0, **breaking**: `get_radar_activity` gains an `EVALUATION_OUTCOME` member and two keys on every member |
| 18.1.0 | Server contract v18.1.0, **additive**: protection geometry behind the v17.2.0 verdicts |
| 18.2.0 | Server contract v18.2.0, **additive**: `TradingPipelineGateStage` gains `EVALUATION`; reason codes gain `EVALUATION_FAULTED` |
| 18.3.0 | Server contract v18.3.0, **additive**: the platform maintenance pause reaches the radar surfaces |
| 18.4.0 | Server contract v18.4.0, **additive**: `list_gate_blocks` gains `summary` groups |
| 19.0.0 | Server contract v19.0.0, **breaking**: the strategy regime timeframe becomes derived and read-only |
| 19.1.0 | Server contract v19.1.0, **additive**: Standing Orders markers become authorable and resolvable before save |
| 19.2.0 | Server contract v19.2.0, **additive**: `get_account_state` gains account-identity fields |
| 19.3.0 | Server contract v19.3.0, **additive**: `QualificationGateCode` gains `REQUIRED_CONDITION_FALSE` |
| 19.4.0 | Server contract v19.4.0, **additive**: reason codes gain `OPEN_POSITION_CHECK_UNAVAILABLE` |
| 20.0.0 | Server contract v20.0.0, **breaking**: the `signal_pipeline` decision becomes a union discriminated on the verdict; `GATED` joins it |
| 21.0.0 | Server contract v21.0.0, **breaking**: `get_radar_activity` gains `blockReasonCode` on every member |
| 22.0.0 | Server contract v22.0.0, **breaking**: `positionManagement` gains REQUIRED `trailingTriggerR` |
| 23.0.0 | Server contract v23.0.0, **breaking**: `tradingConfig.tradingMode` is removed — trading is scoped per deployment |
| 24.0.0 | Server contract v24.0.0, **breaking**: `positionManagement` leaves the agent for the strategy |
| 25.0.0 | Server contract v25.0.0, **breaking**: the arena stops granting trade authority; slot trade fields are rejected |
| 26.0.0 | Server contract v26.0.0, **breaking**: both entry-lifecycle guards leave the agent for platform config |
| 27.0.0 | Server contract v27.0.0, **breaking**: the trade-defaults catalog drops four unauthorable seeds |
| 27.1.0 | Server contract v27.1.0, **additive**: `compile_strategy_plan` accepts the twelve exit-policy keys |
| 28.0.0 | Server contract v28.0.0, **breaking**: grid-confidence and trade-conviction bars become deployment declarations |
| 29.0.0 | Server contract v29.0.0, **breaking**: `get_radar_activity` gains an `EDGE_REARM` variant and six keys on every member |
| **30.0.0** | Server contract v30.0.0, **breaking**: the stop-loss ceiling changes unit (`maxStopLossPct` → `maxStopLossAtrMultiple`, range `(0,3]`), a `floor < ceiling` rule is enforced, and **the position-size presets change meaning without changing shape** — they denote a risk budget, not a share of the order |
| 23.0.0 | Server contract v23.0.0, **breaking**: the agent-level trading mode is retired. `create_agent`/`update_agent` stop accepting `tradingConfig.tradingMode` on the shared `.strict()` `TradingConfigSchema`, so a client still sending it is rejected rather than ignored — the same input-acceptance narrowing that made v4, v5, v6, v8 and v10 majors. On the read side `AgentTradingConfigDTO` drops `tradingMode` on every agent-returning tool, and so do the agents-hub permission envelope, the explorer entry and both public-profile shapes; `DeploymentResolvedResolutionDTO` drops `agentTradingMode`, the field v10.0.0 added, because with no account layer to overlay the resolved `tradingEnabled` is the whole answer. Trading on/off is now scoped per deployment (radar policy `enabled`, arena slot `tradingEnabled`, per-coin `tradeEnabled`) and a newly authored arena slot starts with trading **off**; approval-before-execution is the conversational surface's own contract, so `accept_entry_decision` / `cancel_entry_decision` / `list_pending_approvals` are unchanged on the wire but now carry conversational proposals exclusively — a deployed agent never queues for approval. Never published as a package version |
| 24.0.0 | Server contract v24.0.0, **breaking**: the post-entry exit policy moves from the agent to the strategy. `create_agent`/`update_agent` stop accepting `tradingConfig.positionManagement` on the shared `.strict()` `TradingConfigSchema`, so a client still sending it is rejected rather than ignored — the same input-acceptance narrowing that made v4, v5, v6, v8, v10 and v23 majors. On the read side `AgentTradingConfigDTO` drops the nested block on every agent-returning tool and the explorer trading spec drops it too; `get_trading_config_catalog` drops `positionManagementPresets` and the `defaultPositionMgmt*` trading defaults. The pistol-preset ladder (COLT / WEBLEY / BERETTA / LUGER / WALTHER) is **retired, not renamed** — once the values live on the strategy, the strategy is the named bundle. Additive on the authoring surface in the same bump: `compile_strategy_plan`/`apply_strategy_plan` post-state gains the twelve authored keys beside the trade-level trio, and the plan diff gains a `positionManagement` axis. Behaviourally the umbrella `enabled` flag is **deleted** rather than moved: each mechanism toggle is the whole truth for that mechanism, so a client can no longer express "trailing on, management off". Never published as a package version |
| 26.0.0 | Server contract v26.0.0, **breaking**: both entry-lifecycle guards stop being agent configuration. `create_agent`/`update_agent` stop accepting `tradingConfig.signalTimeoutMinutes` and `tradingConfig.maxEntryDeviationAtrMultiple` on the shared `.strict()` `TradingConfigSchema`, so a client still sending either is rejected rather than ignored — the same input-acceptance narrowing that made v4, v5, v6, v8, v10, v23 and v24 majors. Neither has a replacement key: one `platform_config` value governs the entry-price drift budget for every decision (read at evaluation time, so an admin edit applies to the next evaluation), and one governs how long an entry may stay unfilled (snapshotted onto the position at creation, so an edit can never cancel an order already resting on the book). On the read side `AgentTradingConfigDTO` drops both fields on every agent-returning tool, and so do the explorer trading spec and the agent-review payload; `get_trading_config_catalog` drops `defaultSignalTimeoutMinutes` and the `minimum_`/`maximum_maxEntryDeviationAtrMultiple` bound pair, while `defaultMaxEntryDeviationAtrMultiple` and `defaultTtlMinutes` stay and become the values that actually govern. Behaviourally a conversational entry and an autonomous entry on the same setup now receive the **identical** unfilled lifetime — the mode-selecting fallback that chose between a per-agent timeout and a hardcoded 15-minute resting window is gone, and the three-way timeout enum with it. Never published as a package version |
| **31.0.0** | **Proxy change, and the end of the pairing rule.** The version announced downstream is now read from the upstream handshake at connect time and relayed verbatim, instead of being a constant compiled into this package. A local client reads the contract it will actually reach, on every connection, with no release involved. Breaking because the package number now means something different — this proxy's own code, not the server's contract — so `npm view` and the handshake legitimately differ, and code keyed to them being equal is wrong. Retired with it: the publish-time deploy gate (`scripts/assert-deployed-contract.mjs`) and the `MAJOR.MINOR` pairing rule, both of which existed only because the two numbers could disagree. Fails closed if a connected server announces no `serverInfo` rather than substituting its own version. Contract moves no longer produce a release here |

## Maintainer release procedure

> [`.github/workflows/publish.yml`](.github/workflows/publish.yml) is the executable release authority. If this recipe and the workflow diverge, correct them together before merging a version change.

Publishing runs only in GitHub-hosted Actions. Never run `npm publish` from the BattleGrid application VM or a maintainer workstation.

**A version change on `main` is the release.** Merge a pull request that changes `package.json`'s version and the workflow does the rest: it confirms that version is not already on the registry, verifies every value expressing it agrees, tests, builds, packs, publishes with npm provenance, and tags what shipped. There is no manual tag step — the tag is an output of a successful publish, not its prerequisite.

**Release whenever this package's code is ready.** Since v12 the package makes no claim about the server's contract, so there is no deploy to sequence against and no gate asserting one. Publishing before, during, or after a server deploy is equally correct.

That inversion is deliberate. Publication used to be triggered by a tag, which meant a version bump with no tag published nothing **and reported nothing** — how `5.1.0` came to be declared in this repository and absent from the registry, caught by no check at all.

### Release environments and prerequisites

| Responsibility | Environment |
|---|---|
| Confirm npm publishing trust | npmjs.com package settings |
| Prepare and merge the version change | Pull request against `main` |
| Check, build, publish, and tag | GitHub-hosted `ubuntu-latest`, Node 24 |
| Verify registry publication | Any shell |

**The workflow needs no BattleGrid credential.** It never contacts the BattleGrid server at all. The deploy gate that used to (reading `GET /mcp/version`, unauthenticated by design) was retired in v12 along with the pairing rule that motivated it. Its no-credential property is worth keeping in mind if a future check ever needs the contract version: every BattleGrid MCP API key carries `mcp:wager` and there is no read-only variant, so a credentialed check would mean this workflow holding authority to submit wagers and close live positions in order to read a version number. `GET /mcp/version` exists precisely so that trade never has to be made.

Also confirm npm's Trusted Publisher for `@battlegrid/mcp-server` is GitHub Actions with organization `playbattlegrid`, repository `battlegrid-mcp`, workflow filename `publish.yml`, no environment name, and `npm publish` allowed. The workflow uses short-lived OIDC credentials; do not add a long-lived `NPM_TOKEN`.

### Preparing the version change

- **Version this package's own code, and nothing else.** Since v12 the number describes this proxy's build — a fix here, a dependency bump, a documentation correction — and makes no statement about the server. **Do not move it because the server's contract moved**; that used to be the whole job and is now a category error. Ordinary semver against the proxy's own surface: MAJOR for a break in how the proxy behaves or what its number means, MINOR for proxy features, PATCH for fixes and docs.
- **Move all three values together** — `package.json`, both `package-lock.json` version fields (the root `version` and the self-referencing `packages[""].version`), and `PACKAGE_VERSION` in `src/index.ts`. The workflow compares all of them and fails closed on any disagreement.
- **No deploy to wait for.** A release here is independent of the server's deploy schedule in both directions.

### What a server contract move needs from this package

**Nothing.** That is the point of v12. When the server's contract moves, connected proxies announce the new version on their next connection, with no publish, no version bump, and no coordination.

Two things do still need doing, neither of them a release:

- **Reconnect** to pick up the new contract — the announcement is read once from the handshake at startup, and the capability snapshot is resolved on first use and cached thereafter (see [Rediscovery & versioning](#rediscovery--versioning)).
- **Document the break** where the contract is documented, in `battlegrid-app`. Contract breaking-change notes are no longer keyed to package versions in this README, because a contract move is no longer a release here.

### Verify publication

The workflow publishes and tags on its own; these confirm what landed.

```bash
release_version="$(node -p "require('./package.json').version")"

npm view "@battlegrid/mcp-server@${release_version}" version dist.integrity \
  --json --registry=https://registry.npmjs.org/

npm view @battlegrid/mcp-server dist-tags \
  --json --registry=https://registry.npmjs.org/

npm view "@battlegrid/mcp-server@${release_version}" dist.attestations \
  --json --registry=https://registry.npmjs.org/
```

Require the exact version, `latest` pointing at that version, and a provenance attestation. Confirm the workflow created `mcp-server@${release_version}` and that `gitHead` on the published version is the merge commit. Restart/reconnect running proxies and rediscover `tools/list`, `prompts/list`, and `resources/list`; publication alone does not refresh their startup cache.

There is no separate registry-reconciliation step to remember. "Is this version already published?" is the workflow's own first question — it decides whether the run publishes at all — so a bump can no longer sit in the repository unpublished and unreported the way `5.1.0` did.

**The server-side release canary is not evidence about this package.** `battlegrid-app`'s `server/scripts/release-canary-mcp.ts` connects to the deployed endpoint and compares `client.getServerVersion()` against the server's own imported `MCP_CONTRACT_VERSION` — **both sides are server-side, and it never queries npm.** It passes with this package at any version, including one that was never published. Package-side evidence is exactly two things: the workflow's version-integrity gate, and the registry checks above with `gitHead` matching the release commit.

**A reconnect no longer proves which package version is running**, and this is the one verification v12 took away rather than improved. The stdio handshake now shows `battlegrid@<contract>` — the *server's* number — so it is identical whether the local proxy is 12.0.0 or a stale 11.0.0 from a cached `npx`. Read `PACKAGE_VERSION` from the installed `dist/index.js`, or the trailing `proxy <version>` field in the startup stderr line, to confirm which build is running.

If a run fails, inspect it before taking action. An `ENEEDAUTH` failure means the npm Trusted Publisher fields do not match the workflow — fix the publisher configuration and re-run the job; nothing was published and no tag was created, so there is nothing to move or reuse. Never mutate a published release with `npm audit fix`; dependency remediation goes through a new reviewed commit and version.

## Skills

Install the BattleGrid skills for AI agent instructions:

```bash
npx skills add playbattlegrid/battlegrid-mcp
```

Nine skills ship from this repo, all inside the npm tarball (`SKILL.md`, `skills/`).

**`battlegrid`** (repo root) is the connection skill and is authored here: how to connect, the
`{ account, request }` envelope, the two scopes, and where to go for everything else.

The nine `skills/battlegrid-*` are **exported from BattleGrid's server repository** — they are the
same instructions BattleGrid's own in-app Commander runs on, which is why they name the same tools
you reach over MCP:

| Skill | Teaches |
|---|---|
| `battlegrid-agent-management` | Commission and govern intelligence agents: interview and create one against a committed strategy and an approved model, change configuration and risk limits, rebind, halt, resume, archive, and act on live positions |
| `battlegrid-arena-play` | Enter Market Grid sessions: find an open session, read its coin pool and live market context, compose a grid with real per-coin reasoning or have an agent generate it, submit, then read results and the reasoning journal |
| `battlegrid-market-analysis` | Read the current crypto market — regime, funding and open interest, leaders and laggards, a deep-dive on any named coin — and close with the levels worth watching |
| `battlegrid-radar-deployment` | Put agents on standing duty: per-coin Radar policies that fire on confirmed regime flips, and per-preset Arena deployment policies, previewed before they are written and un-deployed with the blast radius stated |
| `battlegrid-strategy-authoring` | Build a strategy from a plain-English idea: gather evidence, lock the spec, compile against the platform grammar, review exactly what will run, apply only on confirmation. Also fork, tune, restore, archive, preview |
| `battlegrid-strategy-doctor` | Diagnose an agent that is not doing what was expected — why it has not traded, why it stopped, whether it is healthy — from typed fields, then rank the fixes with the exact lever each needs |
| `battlegrid-strategy-examples` | Full-surface composition patterns: custom report sections and header grammar, benchmark sections, condition trees with verdicts and enforcement gates, tiered signal weights and the aggregate gate math, routing gates, ATR trade levels, position management, plus validated desk-grade playbooks and TradingView process ports |
| `battlegrid-trade-analysis` | Read your own trading position: where the money is, whether each agent is doing its job, what is open and how close it sits to its protections, and whether the automation is actually running |
| `battlegrid-trade-proposal` | Find and stage a trade for one of your agents: check what is already held, scan every active coin against the agent's own gates, propose on one through the agent's own conversational turn, present the outcome with its conviction, and approve or decline only on your word |

> **`skills/battlegrid-*` is generated — do not edit it here.** It is written by
> `server/scripts/export-mcp-skills.mjs` in `playbattlegrid/battlegrid-app` and arrives by pull
> request; `skills/EXPORT.json` records a hash per file and `src/__tests__/skill-provenance.test.ts`
> fails CI on a hand edit. Change the skill upstream and let the export lane bring it here.

## License

[MIT](LICENSE)
