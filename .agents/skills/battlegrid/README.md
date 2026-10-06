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

## Contract history — v91 (every data block an agent reads is one JSON object)

**Breaking at v91: one output field is removed, and the published text that is the agent's prompt carries JSON.**
v91 is the contract on top of v90. Every data block BattleGrid's trading agents read — the strategy's resolved
conditions, fact sections, and the trade-decision blocks — is one JSON object naming itself with `id` and `title`.
Instructions stay prose under their `## Title`. The tools that show you the prompt therefore show that JSON.

### Removed output — something you read is gone

- **`promptDataSerialization`** leaves `get_signal_log`'s owner detail. There is one serialization, so a trade
  record stores none. `reportSections` and `missingData` are unchanged, and a trade recorded before capture still
  serves both as `null`.

### Reshaped output — the same fields, carrying JSON

- **`preview_strategy_report.conditionsTableText`** is the conditions glossary as a `## Strategy Conditions
  Glossary` instruction, then the conditions register as one JSON line: `surface: "GRID"`, and `coins[]` each with
  `outcomes` keyed by condition and `verdict` by display name (`null` when the strategy declares no verdict). It was a
  markdown table followed by the glossary.
- **`preview_strategy_report.tradeConditionsBlockText`** is the trade glossary, a blank line, then the target coin's
  register as one JSON line: `surface: "TRADE"`, `verdict` as `{ name, description }`, and `conditions[]` each with
  `outcome`, `required`, `provisional`, `counts`, `exitRule` and the evaluator's `evidence`. It was a
  `## STRATEGY CONDITIONS` heading, a table and evidence bullets.
- **A fact section's text is its JSON**, `{ id, title, facts, glossary }` with `facts` keyed by label, in
  `get_market_context.sections[].content`, `get_context_source_full_preview.content`,
  `preview_strategy_report.renderedSections[].section.text`, and the `get_signal_log` report of trades recorded
  from v91 on. The session field is a fact section. A table section's text is still its markdown.
- **`get_agent_prompt_context_preview.promptSections[].content`** is each section as the agent reads it: a data
  section's JSON, a table's included, and an instruction's prose.

### Widened enum

- **`get_agent_prompt_context_preview.promptSections[].kind`** gains `strategy-conditions-glossary`, the instruction
  read before the conditions register. The market-context reads exclude it, as they exclude the register.

Something read at v90 is gone or reshaped at v91 — hence the MAJOR.

## Contract history — v90 (Arena and radar deployments join the draft lifecycle)

**Breaking at v90: input is refused and reshaped, output is reshaped, five error codes are removed.** v90 is the
contract on top of v89. The Arena and radar deployment drafts now run the same five-tool lifecycle as agents and
strategies, and the preview token is retired: a deployment commits on the draft version and the revision you read.

### Rejected input — something you send is no longer accepted

- **`previewToken` and `confirm`** leave `commit_deployment_policy_draft`, `commit_radar_deployment_draft`,
  `resume_deployment_policy` and `resume_radar_deployment`.
- **`confirm`** leaves `delete_deployment_policy`, `delete_radar_deployment`, `discard_deployment_policy_draft` and
  `discard_radar_deployment_draft`.
- Every input is strict, so a call naming either key is refused as an unrecognised key.

### Reshaped input

- **The commits** take `{ request: { presetId | coinId, draftVersion, expectedRevision } }`: exactly the
  `draftVersion` and `committedRevision` the kind's `get_*_draft` returned (`expectedRevision: null` for a first
  deployment).
- **The resumes** take `{ presetId | coinId, expectedPolicyId, expectedRevision }`: the `policyId` and `revision` a
  `COMMITTED` preview returned. Any other deployment or revision is a `CONFLICT`, and nothing is armed.
- **`delete_radar_deployment`** gains `expectedPolicyId` beside `expectedRevision`, as `delete_deployment_policy`
  already took. A delete naming a policy since removed and redeployed matches nothing.
- **The discards** take `{ request: { presetId | coinId, draftVersion } }` with no dry run. A draft that moved, or
  none, is `DRAFT_VERSION_MOVED`.

### Reshaped output — something you read has a new shape

- **`stage_deployment_policy_draft` and `stage_radar_deployment_draft`** gain `diagnostics`.
- **`get_deployment_policy_draft` and `get_radar_deployment_draft`** answer the lifecycle read
  `{ draft, draftVersion, committedRevision, diff, diagnostics, impact }`, where they answered `{ draft }`. `impact`
  is the resolution the commit would arm and whether it plays (`enabledAfterCommit`), plus a radar first
  deployment's coin-cap reading (`admission`); it is null when a diagnostic refuses.
- **The commits** answer `{ presetId | coinId, revision, draftVersion }`. The radar commit answered `{ revision }`.
- **The discards** answer `discarded: true`, never `false`.
- **`preview_deployment_resolution` and `preview_radar_resolution`** lose `previewToken` and gain `policyId` and
  `revision`: the deployment the preview resolved over, null for `SLOTS` and a first deployment.

### Removed error codes

`TOKEN_EXPIRED`, `TOKEN_BINDING_MISMATCH`, `INVALID_TOKEN_SIGNATURE`, `INVALID_TOKEN_FORMAT` and `INVALID_TOKEN_CLAIMS`
leave the error vocabulary and every draft diagnostic's code enum — so the stage and get outputs of the agent and
strategy drafts move too.

### Behaviour behind the new schemas

- **A retried commit replays its receipt.** Both commits are destructive and idempotent on
  `<presetId | coinId>:<draftVersion>`, as the agent and strategy commits are.
- **Refusals name the next act.** A moved draft or revision carries `details.nextAct: "get_draft"`; a refusal the
  draft can repair (`INVALID_DEPLOYMENT_POLICY`, or the radar's `VALIDATION_ERROR`) carries `"stage"`; a retired arena
  carries none and names the remedy.
- **A revision conflict names the revision that won** in `details.actualRevision`, null when no deployment remains.
- **A `DRAFT` preview at a version the draft is not at** is `DRAFT_VERSION_MOVED`.
- **A draft whose arena or coin can no longer be deployed is still served**, with the refusal in its diagnostics and
  a null impact, so you can show it and discard it.
- **A radar resume of a policy already trading** answers its revision and changes nothing.
- **The radar per-user coin cap is `FORBIDDEN`**, with no `nextAct`, where it was `VALIDATION_ERROR`.

Something accepted at v89 is refused at v90 — hence the MAJOR.

## Contract history — v89 (a new strategy is held to today's operator bounds)

**Breaking at v89: acceptance narrows behind unchanged schemas.** v89 is the contract on top of v88.1.

### Narrowed acceptance — `commit_strategy_draft`, `preview_strategy_report` (`DRAFT` source)

- **A create judges every dial of the new strategy at the operator bounds configured now.** That includes a dial
  the author typed, one a fork copied from its source, and one left at the creation default. The operator bounds
  are the platform's ATR %, stop-loss ATR-multiple and risk:reward limits.
- At v88.1 a create judged only the dials that differed from the fork's source or the creation default. So a copied
  dial outside a bound tightened since the source stored it was committed.
- At v89 `commit_strategy_draft` (`expectedRevision: null`) refuses that create with `VALIDATION_ERROR`, naming the
  dial and the bound, for example `minAtrPct (0.1) must be >= 0.15`. Nothing is created and the draft is unchanged:
  stage the dial inside the bound and commit again.
- `preview_strategy_report` with `source: { kind: "DRAFT", … }` composes the draft exactly as the commit does, so it
  refuses the same draft with the same error where v88.1 rendered it.
- `stage_strategy_draft` and `get_strategy_draft` report the error in their diagnostics before the commit.
- `fork_strategy`'s description now says this, so its description hash moves.

### Behaviour behind unchanged schemas

- **An edit still judges only what it moves.** An update or a restore carries a dial it leaves unchanged, so a stored
  value outside a since-tightened bound stays readable and saveable on its own strategy.
- **The platform keeps its defaults creatable.** An operator cannot set a bound that would put a creation default
  outside it, so a create that leaves a dial untouched is never refused for a value the platform seeded.

Something accepted at v88.1 is refused at v89 — hence the MAJOR.

## Contract history — v88.1 (an open position keeps the exit rules it opened under)

**Additive at v88.1: acceptance widens and one served value narrows; no input or output schema
changes.** v88.1 is the contract on top of v88.

### Widened acceptance — `commit_strategy_draft`, `restore_strategy`, `commit_agent_draft`

- **An open position no longer refuses a strategy commit, a restore or a rebind.** At v88 a write that
  would leave an exit rule unreadable on a coin a bound agent held an open position on was refused with
  `CONDITION_UNREADABLE_BY_RADAR_SCAN` or `CONDITION_OPERAND_UNSERVED_IN_LANE`. At v88.1 it commits. A radar
  slot's coin and a pending manual request's coin are still checked, and refused exactly as before.
- The three tools' descriptions now say this, so their description hashes move.

### Narrowed served value — the readability refusal's `coinRole`

- The refusal's error context serves `coinRole` as `SLOT` or `MANUAL_REQUEST` only. `OPEN_POSITION` is no
  longer emitted. A client switching on it loses a member it can no longer receive.

### Behaviour behind unchanged schemas

- **An open position keeps what it opened with.** An agent position records the exit rules it opened
  under, with the report and timeframes they read, and its exit rules are evaluated from that record for
  the life of the trade. An exit-rule, exit-policy or level edit reaches only positions opened after it;
  a revision, rebind, SYSTEM update or timeframe change after the open never reaches an open trade.

Nothing accepted at v88 is refused at v88.1.

## Contract history — v88 (an exit rule names the side it closes)

**Breaking at v88: a condition body accepted at v87 is refused, and condition and chart output is
reshaped.** v88 is the contract on top of v87.

A condition is an entry condition or an exit rule, never both. An exit rule names the side it closes,
where `exit: true` read that side from the condition's verdict.

### Rejected input — `stage_strategy_draft`, `preview_strategy_report`

- **A condition no longer carries `exit`.** A condition entry naming it is refused with the unknown-key
  error, on the `CONDITIONS` axis of `stage_strategy_draft` and in the conditions of
  `preview_strategy_report`'s `source: { kind: 'FIELDS', … }`.
- **Every condition requires `exitSide`**: `LONG`, `SHORT` or `BOTH` for an exit rule, `null` for an
  entry condition. It is nullable, never optional; a condition without it is refused.
- **An exit rule carries `verdict: null` and `required: false`, and an entry condition cannot reference
  an exit rule.** The builder refuses each with a typed remediation error —
  `CONDITION_EXIT_RULE_CARRIES_VERDICT`, `CONDITION_EXIT_RULE_REQUIRED`,
  `CONDITION_ENTRY_REFERENCES_EXIT_RULE` — in a staged draft's `diagnostics`, and as the refusal of its
  `commit_strategy_draft`. An exit rule may reference anything: "exit when the entry setup stops holding"
  is an exit rule whose definition is `NOT` a `conditionRef` to the entry condition.

### Reshaped output

- **Every condition a strategy read or commit returns carries `exitSide` and no `exit`**:
  `get_strategy`, `archive_strategy`, `restore_strategy` and `commit_strategy_draft`.
- **`get_agent_coin_qualification`'s chart names the side each exit rule closes.** Every served level
  gains `referrers`, `{ conditionKey, conditionName, exitSide }` for each of its set's declared
  conditions that reach it. Every series clause referrer and every `conditionsWithoutLevels` entry gains
  `exitSide`, `null` on every entry-set referrer. The `ENTRY` set no longer lists exit rules; they are
  listed under `EXIT`.

### Widened enums

- **`CONDITION_EXIT_RULE_CLOSES_DIRECTION`** joins the qualification gate code, the trade evaluation
  attempt reason, the trade gate reason and the trade screen reason. It can appear in the output of
  `get_agent_coin_qualification`, `scan_agent_coins`, `scan_coin_agents`, `list_gate_blocks`,
  `get_signal_log`, `get_public_agent_signal_log_detail`, `get_radar_activity`,
  `get_radar_activity_summary`, `get_radar_close_decisions`, `get_radar_deployment`,
  `list_radar_deployments`, `preview_radar_resolution`, `propose_entry_decision`,
  `get_trade_conversation`, `get_agent_budget` and `reset_agent_drawdown_baseline`. A gate block under it
  names the refusing exit rule in `decidedBy`.
- **`BLOCKED_BY_CONDITION_EXIT_RULE`** joins the radar evaluation outcome, on `get_radar_activity` and
  `get_radar_activity_summary`.

A client switching exhaustively on any of them meets a member it has not seen.

### Behaviour

- **An exit rule closes exactly the side it names.** A settled TRUE on a completed bar closes the
  agent's open position on that side. No verdict chooses it; `exit: true` closed the side its verdict
  opposed, and both sides for a `NEITHER` or `null` verdict.
- **While an exit rule reads TRUE, its side is not offered for entry.** Scan qualification and compose
  refuse that side under `CONDITION_EXIT_RULE_CLOSES_DIRECTION`, after any verdict refusal of the same
  side.
- **A stored `exit: true` condition is split and closes what it closed.** It keeps its verdict as an
  entry condition, and its strategy gains an exit rule `CLOSE_ON_<conditionKey>`, a `conditionRef` to
  it closing the side its verdict opposed (`UP` → `SHORT`, `DOWN` → `LONG`, `NEITHER` → `BOTH`). A
  strategy read returns both.
- **Unchanged names keep their place.** `list_strategies`' `conditionTally.exit` now counts exit rules,
  and a decision record's condition `declaration` keeps `exit: boolean`, true for an exit rule.

A strict client that rejects unknown keys fails to parse every condition and every chart level at v88;
list the tools again after the server deploys.

## Contract history — v87 (a fork's create resolves its source again)

**Breaking at v87: a fork's create can now be refused where it committed.** v87 is the contract on top of
v86. No schema, description or tool changes.

### Narrowed acceptance

A create draft that `fork_strategy` opened is committed by `commit_strategy_draft` with
`expectedRevision: null`, or by the builder's Create. That create now resolves the strategy it copied
again. It uses only the source id and revision in the draft's `ORIGIN`, by the same rule the fork applied:

- **A source that moved past the forked revision** refuses the create with `CONFLICT` and **no
  `details.nextAct`**. Reading the draft again cannot cure it; the message says to discard the draft and
  fork again. `get_strategy_draft` and `stage_strategy_draft` report the same refusal in the draft's
  diagnostics.
- **A source you can no longer see** — archived, or neither yours nor SYSTEM — answers `NOT_FOUND`.

### Widened acceptance

- **Neither `fork_strategy` nor the create reads the source's stored revision snapshot.** A strategy whose
  stored snapshot predates the current shape — every SYSTEM template among them — now forks and creates
  from its live state, where both were refused.

## Contract history — v86 (a refusal hint belongs to the operation that can act on it)

**Breaking at v86: refusals on most tools lose `details.nextAct`, two refusals change code, and one
draft read is reshaped.** v86 is the contract on top of v85.

### Narrowed refusal details

- **`details.nextAct` follows the refusal's meaning.** `DRAFT_VERSION_MOVED` and `DRAFT_AXIS_CONTESTED`
  still carry `get_draft` from every tool. A revision `CONFLICT` and the in-flight commit refusal
  (`get_draft`) and a validation refusal (`stage`) now carry a hint only from `stage_<kind>_draft` and
  `commit_<kind>_draft` of the strategy and agent kinds.
- **Removed from every other tool's validation refusal and revision `CONFLICT`**: `submit_market_grid`,
  `fork_strategy`, `archive_strategy`, `restore_strategy`, and the arena and radar commit, pause, resume
  and delete tools, and from the malformed-cursor refusal of `list_agent_drafts` and
  `list_strategy_drafts`. The arena and radar `commit_*_draft` stale-revision refusals lose `get_draft`
  too. A client that branched on `nextAct` from those tools reads the code instead.

### Changed error codes

- **The strategy active-quota refusal is `FORBIDDEN`**, as the agent slot quota is, where it was
  `VALIDATION_ERROR` with `nextAct: 'stage'`: on `commit_strategy_draft` and `restore_strategy`.
- **A create naming an id that is already the caller's strategy or agent is `DRAFT_VERSION_MOVED`**,
  carrying the caller's draft version at that id, where it was `NOT_FOUND`. An agent create naming a
  SYSTEM agent is `FORBIDDEN`, where it was `NOT_FOUND`.
- **The moved-draft refusals end "Read the draft again and show the player what it now holds before
  committing."**, where they said to commit what it now holds. Read the draft again and show the player
  before committing; never commit the re-read draft on your own.

### Reshaped output

- **`get_agent_draft.impact` is a union on `operation`**: `{ operation: 'CREATE', capital }` for a create
  draft, where it was `null`, and `{ operation: 'UPDATE', deployedPresetCount, openPositionCount,
  radarArmedCoinCount, capital, rebind }` for an edit draft, where the counts sat at the top level. A
  create draft's `capital` reads its trading configuration — drafted, or the platform's seed — over the
  bound strategy's band, as the commit's capital check reads it.

### Widened read

- **`get_strategy` with `includeInactive: true`** serves your own strategy in any state, and otherwise
  the visible set the default read serves — every SYSTEM strategy among it — where it answered
  `NOT_FOUND` for anything but an owned PRIVATE strategy. Another user's PRIVATE strategy is still
  `NOT_FOUND`.

### Behaviour behind unchanged schemas

- **The stage and commit descriptions** state the draft content cap (256,000 UTF-8 bytes) and its
  refusal, what a commit reaches — it closes no position, and the one refusal an open position can cause
  — and that a moved draft is shown to the player before any commit.
- **A stage's `DRAFT_VERSION_MOVED`** fires only for a version the draft never reached — read from a draft
  since committed or discarded. A stage naming an older version than the draft holds is composed over the
  newer draft.

A strict client re-reads the `get_agent_draft` output schema; list the tools again after the server
deploys.

## Contract history — v85 (agents and strategies change only through their drafts)

**Breaking at v85: seven tools are retired, and a surviving tool refuses an input it accepted at v84.**
v85 is the contract on top of v84.

Every agent and strategy is now created and changed the same way: stage the change into the
entity's draft, read the draft back with its diff, diagnostics and impact, and commit exactly the
draft version and the live revision that read returned.

### Removed tools

- **`compile_strategy_plan`, `stage_strategy_plan`, `apply_strategy_plan`, `update_strategy_signal_rule`,
  `create_intelligence_agent`, `update_intelligence_agent`, `rebind_intelligence_agent`** are gone, with
  no alias; a call gets an unknown-tool error. The replacements: `get_strategy_draft` →
  `stage_strategy_draft` → `commit_strategy_draft` for a strategy (a signal rule is a row of the draft's
  `SIGNAL_RULES` axis), and `stage_agent_draft` → `get_agent_draft` → `commit_agent_draft` for an agent
  (a rebind is the draft's `STRATEGY_BINDING` axis).

### Added tools

- **`stage_strategy_draft { strategyId?, draftVersion, axes }`**, **`commit_strategy_draft`** and
  **`commit_agent_draft`** (`{ <id>, draftVersion, expectedRevision }`, `expectedRevision` null for a
  create). A commit publishes exactly the draft version and the live revision the caller read, is
  idempotent on `{ id, draftVersion }`, and returns the kind's committer response plus the draft's
  `draftVersion` after its clear (null when the commit emptied it).

### Rejected input

- **`archive_strategy` no longer takes `confirm`.** A request carrying it is refused with the
  unknown-key error — a break on a surviving tool.
- **`discard_agent_draft` and `discard_strategy_draft` take `draftVersion`** (the version
  `get_<kind>_draft` returned) in place of `confirm`; `confirm` is refused as an unknown key, and a
  version the draft moved past is refused `DRAFT_VERSION_MOVED`.
- **`preview_strategy_report` takes `{ coinSelection, source }`.** The report fields move under
  `source: { kind: 'FIELDS', … }`, and `source: { kind: 'DRAFT', strategyId, draftVersion }` previews the
  owner's draft as a commit would compose it. A body with the fields at the top level is refused.
- **A strategy's ENTRY axis is a union discriminated by `trigger`**: `{ trigger: 'ON_CANDLE_CLOSE' }`
  alone, or a level trigger with `levelOffsetAtrMultiple` and `validForBars`. `ON_CANDLE_CLOSE` naming
  either dial is refused, which the retired compile accepted; the server stamps the seed values.

### Widened input

- **`stage_agent_draft` accepts `STRATEGY_BINDING` on an edit draft**, where v84 refused it: a staged
  binding commits as the agent's rebind. Its TRADING_CONFIG axis now describes each size preset as the
  risk budget lost at the hard stop.

### Reshaped output

- **`fork_strategy` returns `{ strategyId, draftVersion }`** — the create draft it wrote, holding a copy
  of the source — in place of `{ strategy }`. No strategy exists until that draft commits.
- **`get_agent_draft` and `get_strategy_draft` gain `draftVersion`** (0 when no draft is held, beside a
  null `draft`), **`committedRevision`, a per-axis `diff` against live, `diagnostics` and `impact`.**
- **`stage_agent_draft` gains `diagnostics`**, the composed draft's errors and warnings.
- **`discard_agent_draft` and `discard_strategy_draft` return `discarded: true` only**; a discard that
  finds nothing is refused rather than answered `false`.

### Widened enum

- **Strategy draft axes gain `ORIGIN`**, the create-only axis a fork writes, on `list_strategy_drafts`
  and every strategy draft read. A client switching exhaustively on a strategy draft axis must add the
  branch.
- **Error codes gain `DRAFT_VERSION_MOVED`** (details `draftVersion`, null when no draft is held) **and
  `DRAFT_AXIS_CONTESTED`** (details `contestedAxes` and `draftVersion`), both 409.
- **Refusal details gain `nextAct`.** Every draft-specific refusal, the revision `CONFLICT` and the
  in-flight commit refusal carry `nextAct: 'get_draft'`; a commit's validation refusal carries
  `nextAct: 'stage'`; every other refusal carries none. `details.expectedRevision` widens to
  `number | null`.

### Removed error code

- **`PLAN_APPROVAL_NOT_FOUND`**, with the plan path that raised it.

### Behaviour behind unchanged schemas

- **`archive_strategy` and `restore_strategy` no longer refuse around the owner's unsaved draft**: they
  re-base it onto the revision they write. `restore_strategy`'s description drops the compile route — a
  repair is staged into the draft and committed, which restores the strategy.
- **The `author-strategy` prompt** reads "Discover, stage, review, and commit a BattleGrid strategy
  through its draft".
- **The server's manifest records a description hash per tool** (manifest format 4), and the tool count
  moves 142 → 138.

A strict client that rejects unknown keys fails to parse `fork_strategy` and the draft reads at v85;
list the tools again after the server deploys.

## Contract history — v84 (the hold moves from the condition to each clause and group)

**Breaking at v84: a condition body accepted at v83 is refused, and condition evidence is reshaped.**
v84 is the contract on top of v83.

How many completed bars a reading must hold is no longer one number on the condition. Each clause
holds its own reading, counted on its own column's timeframe, and a group can hold its members'
same-bar reading.

### Rejected input — `compile_strategy_plan`, `apply_strategy_plan`

- **A condition no longer carries `closes`.** A condition entry naming it is refused with the
  unknown-key error, in a plan body and in every normalized post-state and strategy draft those tools
  carry.
- **Every clause and every group requires `hold: { atLeast, of }`**, whole numbers of at least 1.
  `{ "atLeast": 1, "of": 1 }` is one read (what every v83 condition did), `{n, n}` is "n closes in a
  row", `{1, n}` is "within n closes", and anything else is "at least m of n closes". A clause or group
  without `hold` is refused. A plan staged under v83 must be recompiled.
- **What a header admits is refused by the builder, never by the schema.** `atLeast` above `of`, a
  window above the header's maximum, or a group hold over members that hold their own bars is a typed
  remediation error.

### Replaced output — `preview_strategy_report`, `list_strategy_vocabulary`

- **`closesReadable: boolean` is replaced by `conditionHold: { timeframe, maxWindow, maxAtLeast,
  refusal }`** on each report condition column and each scalar metric. It names the timeframe a
  clause counts on, the largest `of` and `atLeast` it admits (`maxAtLeast` is 1 for a cross or other
  event, so an event can only be held "within n closes"), and why it admits one bar when it does:
  `NOT_REWINDABLE`, `DEVELOPING`, `OFFSET`, `BAR_STATE` or `HISTORY`. Read the window from here
  rather than assuming a ceiling; there is no longer a fixed 1–5 limit.

### Reshaped output — condition evidence

- **Every clause-evidence entry gains `hold`, `counts` and `decidedBar`**, on `preview_strategy_report`,
  `list_gate_blocks`, `get_radar_close_decisions`, `get_agent_coin_qualification`,
  `preview_radar_resolution` and `get_signal_log`. `counts` is `{ trueCount, total, unresolvedCount }`
  over the clause's own bars. `decidedBar` is `{ timeframe, closesBack }`, the bar its operand was read
  on, or `null` when the hold that counts it reads one bar.
- **A condition outcome loses `hold`** (`closesHeld`, `closesRequired`, `liveOutcome`, `nextCloseAt`):
  the counted outcome is the clause's own, on its evidence. A decision record's condition
  `declaration` loses `closes`.
- **Every strategy read returns `hold` on each clause and group** and no `closes` on the condition.

### Widened enum — the evidence union

- **The evidence union gains a `group` arm**, `{ kind: 'group', op, hold, counts, decidedBar, outcome,
  memberCount }`, emitted only for a group holding more than one bar, just before the `memberCount`
  entries that belong to it. A client switching exhaustively on `kind` must add the branch. A strategy
  without group holds serves no new arm.

A strict client that rejects unknown keys fails to parse condition evidence at v84; list the tools
again after the server deploys.

## Contract history — v70.1 (budget run-state)

**Additive at v70.1: one output field added to the risk budget.**

### Added output — `get_agent_budget`, `reset_agent_drawdown_baseline`

- **`budget.runStatus`** is your run-state for the agent: `blocked`, `paused` or `active`, already
  ranked by the server. `blocked` means the admission gate is refusing the agent for a reason other
  than its halt (`blockedReason` names it). A halted agent reads `paused`, even while its own
  `AGENT_HALTED` block stands. Read it rather than re-deriving it from `blockedReason` and `haltedAt`.
- A client that ignores the field is unaffected. A client that validates results against a cached,
  closed output schema should list the tools again after the server deploys.

## Contract history — v83 (a model's vendor is its vendor slug)

**Breaking at v83: four output fields renamed and retyped, one aggregation regrouped.** v83 is the
contract on top of v82.

Wherever a model's vendor is published, it is now the router vendor slug of the model's id — the part
before the `/` (`anthropic`, `z-ai`, `moonshotai`, …). It is never the BYOK provider enum, and never the
catalogue's display label, which sometimes named a hosting provider rather than the model's maker.

### Reshaped output — the agent

- **Every agent loses `provider` and gains `modelVendorSlug: string`**, on `list_intelligence_agents`,
  `get_intelligence_agent`, `create_intelligence_agent`, `update_intelligence_agent`,
  `rebind_intelligence_agent`, `archive_intelligence_agent` and `activate_intelligence_agent`.
  `provider` was the BYOK enum and was `null` for every agent; `modelVendorSlug` is never null. A
  client reading `provider` reads nothing at v83.

### Renamed output — `list_approved_models`

- **Each model's `provider` is renamed `vendorSlug`**, and its value changes: the vendor slug
  (`z-ai`) where v82 served a display label that could name a host (`StreamLake`).

### Renamed output, regrouped rows — `get_agent_explorer`

- **Each `modelVendors[]` row's `provider` / `providerImageUrl` are renamed `vendorSlug` /
  `vendorImageUrl`.**
- **Rows group by vendor slug**, so every model one vendor makes shares a row whatever its display
  label: three GLM labels that were three rows at v82 are one `z-ai` row at v83. Counts and sums add;
  each mean is the merged total over the merged trade count.

### Renamed output — the `ownerView` LLM-call envelope

- **The envelope's `provider` is renamed `modelVendorSlug`**, on `get_agent_journal`, `get_signal_log`,
  `get_agent_game_history`, `get_user_agent_game_history`, `get_public_agent_signal_log_detail` and
  `get_public_agent_game_history`. It is `null` exactly when `modelDisplayName` is — a call whose model
  has left the catalogue.

## Contract history — v82 (approved models lose their pin flag)

**Breaking at v82: one output field removed.** v82 is the contract on top of v81.

### Removed output — `list_approved_models`

- **`pinProvider` is gone from every model** `list_approved_models` returns. A model is now served
  only by an ordered list of verified hosts that the server keeps to itself, so a pin flag no longer
  describes anything. There is no alias. A client that reads `pinProvider` reads nothing at v82, and
  a strict client that requires it fails to parse the response.

## Contract history — v81 (the allocation's committed figure removed, the hub names Max exposure)

**Breaking at v81: one output field removed and one renamed.** v81 is the contract on top of v80.

### Removed output — the agent fund allocation

- **`committedUsd` is gone from the allocation** that `get_agent_fund_allocation`,
  `halt_intelligence_agent`, `resume_intelligence_agent` and `set_agent_per_trade_push` return. It
  measured a custody ledger whose allocate and recall routes are retired. The figure that bounds an
  entry is capital at risk, on `get_agent_budget`. A client reading `committedUsd` reads nothing at
  v81.

### Renamed output — `get_agents_hub`

- **Each agent's `envelope` names the exposure ceiling `maxConcurrentExposureUsd`**, the trading
  config's own name for it, where v80 called it `budgetUsd`. The value is unchanged. A client reading
  `budgetUsd` reads nothing at v81.

### Corrected reason behind an unchanged schema

- **An agent entry refused because its Max exposure is fully committed is recorded as
  `INSUFFICIENT_BALANCE`**, where it was recorded as `BELOW_EXCHANGE_MINIMUM` with a $0.00 risk
  budget. Its detail names Max exposure and the capital at risk. It reaches `get_signal_log` and
  `get_public_agent_signal_log_detail`.

## Contract history — v79 (the agent's account reading, an exhausted budget, accept below the Balance floor)

**Breaking at v79: the agent budget's account fields move into one object.**

### Reshaped output — the agent budget

- **`get_agent_budget` and `reset_agent_drawdown_baseline` replace `accountEquityUsd`,
  `budgetOverSubscribed` and `openUnrealizedPnlUsd` with one `account` object** carrying the same three
  fields, or `null` when the server holds no cached reading of the account. At v78 an unread account
  read `0`, `false` and `0`, which looked like a real empty account. A client reading the three
  top-level fields reads nothing at v79.

### Widened enum

- **The block reason gains `EXPOSURE_BUDGET_EXHAUSTED`** (owner-private): an agent whose capital at
  risk has reached its Max exposure is blocked once at the account stage, where v78 blocked it per
  coin as `EXCHANGE_MIN_NOTIONAL_UNREACHABLE`. It reaches every output that carries a block reason:
  `list_gate_blocks`, `get_signal_log`, `get_public_agent_signal_log_detail`, `get_radar_activity`,
  `get_radar_close_decisions`, `get_radar_deployment`, `list_radar_deployments`,
  `preview_radar_resolution`, `get_agent_coin_qualification`, `get_trade_conversation` and
  `propose_entry_decision`.

### Refused behind an unchanged schema

- **`accept_entry_decision` refuses with `CONFLICT` while your account equity is below the agent's
  Balance floor (`balanceThresholdUsd`) or cannot be read.** The decision stays pending and can be
  accepted once the equity is back at or above the floor.

## Contract history — v78 (a new agent's risk policy from one seed)

**Breaking at v78: `get_trading_config_catalog` serves a new agent's risk policy as one object.**

### Reshaped output

- **`tradingDefaults.defaults` replaces ten per-field seed values** — `defaultMaxDailyTrades`,
  `defaultMaxLeverage`, `defaultSmallPct`, `defaultMediumPct`, `defaultLargePct`,
  `defaultEntrySlippageBps`, `defaultMaxConcurrentExposureUsd`, `defaultBalanceThresholdUsd`,
  `defaultMaxCumulativeDrawdownUsd` and `defaultMaxDailyLossUsd` — **with one `agentTradingConfig`**,
  request-shaped, so it passes to `create_intelligence_agent` verbatim. A client reading the ten fields
  reads nothing at v78.

### Input schema

- **`tradingConfig.maxLeverage` loses its published `minimum: 1`** on `create_intelligence_agent` and
  `update_intelligence_agent`. Acceptance is unchanged: the platform's minimum leverage is the bound.

### Wider input

- **Both tools accept a strategy whose stored dials sit outside today's operator bounds.** An agent
  write never re-judges a strategy dial.

### Served values

- **A `create_intelligence_agent` call without `tradingConfig` is seeded from the same object the
  catalog serves**, never from column defaults, with Min order size from the platform minimum.

## Contract history — v77 (agent risk rules: each loss stop on its own rail)

**Breaking at v77: an agent's `tradingConfig` accepts less.** `create_intelligence_agent` and
`update_intelligence_agent` refuse values v76 stored, and one loss stop moves to a different bound.

### Rejected input — `tradingConfig`

- **`maxLeverage` must be a whole number.** `1.5` was stored and executed at `1`; it is now refused.
- **`maxSlippageBps` is at most `300`**, the entry slippage ceiling no fill could exceed anyway.
- **USD fields and the three size presets take at most 2 decimals.**
- **`maxDailyLossUsd` must be at or below `maxCumulativeDrawdownUsd`.**
- **A body accepted at v76 can be refused at v77 without one byte of it changing.** Each refusal
  names its field in a plain sentence, such as `Whole numbers only.` or
  `Can’t exceed the drawdown stop ($20.00).`

### Wider input — the drawdown stop

- **`maxCumulativeDrawdownUsd` is bounded by the platform's drawdown maximum, not by
  `maxConcurrentExposureUsd`.** Max exposure caps margin open at once; the drawdown stop caps loss
  over time. A `$150` drawdown stop on a `$100` max exposure is accepted.

### Wider output

- **`get_trading_config_catalog` gains `maximumMaxCumulativeDrawdownUsd`**, the drawdown stop's
  upper bound.
- **The execution-failure reason gains `BELOW_AGENT_MIN_ORDER`** (owner-private) on `get_signal_log`
  and `get_public_agent_signal_log_detail`: an order sized under the agent's own `minAllocationUsd`,
  which was reported as `BELOW_EXCHANGE_MINIMUM`.

### Served values

- **`get_agent_budget`'s `tradesToday` counts entries filled since 00:00 UTC plus entries still
  waiting to fill.** Refused and expired entries no longer count, and the cap is enforced where an
  entry is created. `DAILY_LIMIT_RESERVED` is no longer emitted.
- **A daily-loss halt whose drawdown stop is also breached becomes a drawdown halt** when the day
  rolls over, rather than lifting.
- **A capital-feasibility refusal names what clears it**: the `maxConcurrentExposureUsd` that would,
  and, when one at or above the platform minimum would, a lower `minAllocationUsd`.

## Contract history — v76 (the extreme funding signals in percent a year)

**Breaking at v76: `funding_extreme_positive` and `funding_extreme_negative` take their threshold in
percent a year.** Their parameter is `thresholdAnnualizedPct`, the unit of the strategy grammar's
`ann` column, where it was `thresholdPct`, a fraction of one hourly funding settlement.

### Rejected input — the retired `thresholdPct`

- **Both signals take `thresholdAnnualizedPct`**, bounded 1–43,800 and defaulting to 100 — the
  funding label's crypto `extreme` band, so `100` means 100% a year, and the negative signal fires
  below -100%.
- **`thresholdPct` on either signal is refused as `VALIDATION_ERROR`** wherever a rule's parameters
  are authored: `compile_strategy_plan`, `update_strategy_signal_rule`, `derive_strategy_rule_view`
  and a strategy draft's `SIGNAL_RULES` axis. `oi_surge` keeps its own `thresholdPct`.
- **A body accepted at v75 can be refused at v76 without one byte of it changing.** A rate per hourly
  settlement converts to percent a year by × 8,760 × 100: `0.0002` is `175.2`.

### Stale plans

- **A plan token compiled before the deploy fails as a stale plan** at `stage_strategy_plan` and
  `apply_strategy_plan`, because the authoring catalog digest covers each signal's parameters,
  defaults and explanation: compile again. The strategy preview's `vocabularyDigest` moves too.

### Served values

- **`get_strategy_signal_definition` and `list_strategy_signals` serve the new parameter**, its
  default and its explanation.
- **Each signal's indicator values gain `funding_annualized_pct`**, the annualized rate the signal
  compared, beside `funding_rate`.
- **Stored rules move to the new key after the deploy**: a rule at the retired default takes `100`,
  and any other converts exactly. `get_coin_signal_preview` and every stored rule then score at the
  new threshold.
- **No schema hash moves.** Signal parameters are published as a JSON object on every input and
  output, so the change is in the values accepted and served, and `toolCount` is unchanged.

## Contract history — v75 (readability from each coin's data profile)

**Breaking at v75: the seven tools v73 narrowed refuse by the coin's market-data profile, and one
output vocabulary gains a member.** Which data a coin carries is now the profile the market-data
service publishes for that coin, no longer the coin's asset class.

### Rejected input — the seven tools v73 narrowed

- **A condition reading a kind of data the coin's profile does not serve is refused as
  `INSTRUMENT`**, on the coin or on a benchmark section's own instrument: a spot read on a crypto
  coin no spot venue lists is refused as one on a TradFi coin always was.
- **A coin the market-data service publishes no profile for refuses every condition that reads
  market data**: a coin enabled since the service's last boot, a roster coin whose candle stream it
  did not subscribe, a ticker with no catalog row.
- **The tools, codes and `details.context` are v73's**: `preview_radar_resolution` (every kind,
  issuing no `previewToken`); `commit_radar_deployment_draft`, `rebind_intelligence_agent`,
  `compile_strategy_plan` and `restore_strategy` (`VALIDATION_ERROR` with
  `CONDITION_UNREADABLE_BY_RADAR_SCAN`); `apply_strategy_plan`, which applies only what its compile
  checked; and `propose_entry_decision` (`CONDITION_UNREADABLE_ON_COIN`).
- **A body accepted at v74.1.1 can be refused at v75 without one byte of it changing.** A write whose
  read of the published profiles fails is refused, never admitted unchecked.

### Reclassified reason — `FEED` becomes `INSTRUMENT`

- **A spot read for a ticker with no catalog row is `INSTRUMENT`, where it was `FEED`**, and an
  uncatalogued benchmark refuses every market-data read, where only its spot reads refused before.
- **The `INSTRUMENT` message names what the profile lacks**: "`<instrument>`'s market-data profile
  carries no `<kind>` data", or "the market-data service publishes no data profile for
  `<instrument>`, so it carries no market data", where it read "`<instrument>` has no spot tape".
- **The readings v74 added report it as the sweep does**: `preview_radar_resolution`'s `readings`
  and `get_agent_coin_qualification`'s `reading` mark a condition on a kind the coin's profile lacks
  `INSTRUMENT`.

### Wider output — `BarFamily` gains `MARKET_STATS`

- **The market-stats snapshot is a per-bar value**: a decision reads the snapshot fetched inside the
  `1m` bar ending at its close. A snapshot missing there is a per-bar shortfall, a `families` entry or
  a MISSED close's `INPUTS_OFF_BAR` `lacking` entry naming `MARKET_STATS` at `1m` with its
  `dueBarStart`, `ABSENT` or `GONE`, and the decision waits or misses as for any per-bar family.
- **A decided close records no `MARKET_STATS` stale sample.** A reading at the latest values still
  does, and its `boundMs` is the coin's market-stats freshness target, never below 300,000 ms.
- **Five outputs publish the member**: `get_agent_coin_qualification`, `get_radar_close_decisions`,
  `get_signal_log`, `list_gate_blocks` and `preview_radar_resolution`. No input takes the vocabulary.
  A client that validates results against a cached output schema should list the tools again after
  the server deploys.

## Contract history — v74.1.1 (a same-agent request answered from what stopped the fire)

**Not breaking: one answer corrected behind unchanged schemas.**

- **A request on a pair your own radar policy decides with the same agent** is answered from that
  policy's decision. When the policy's fire enqueued no trade decision and no admission gate refused
  it — a coin cooldown, the hourly fire cap, post-close suppression, a decision already running on the
  coin, a deduplicated fire, or a fire aborted at its re-read — the conversation gains the card the
  request's own unfired fire gets: `close_claimed_by_radar` when another agent's fire holds the coin,
  otherwise `close_refused` with the reading's score against its minimum. It gained
  `close_fired_by_radar` before, though no trade was taken.
- **Both cards are already in `get_trade_conversation`'s vocabulary**, so no served shape moves.

## Contract history — v74.1 (missed-bar alerts and the entry pause)

**Not breaking: four output vocabularies gain a member, and `propose_entry_decision` refuses while an
entry pause is open.** While bars missed for lack of market data span many coins, the platform pauses
every new entry the radar decides, a radar fire and a manual request alike, and the pause lifts by
itself after a quiet period.

### Refused while a pause is open — `propose_entry_decision`

- **A request is refused after its own checks and before a watch is registered**, whatever the agent
  or coin: `type: "error"` with `{ origin: "ENGINE", reasonCode: "ENTRIES_PAUSED" }`. The same
  `idempotencyKey` replays the refusal for five minutes; ask again under a fresh key once the pause
  lifts.
- **A request queued before the pause** whose close qualifies while it is open gets the same ENGINE
  error card in its conversation, and no decision is proposed. `accept_entry_decision` on a decision
  already proposed, and every exit, run as without a pause.

### Wider output — four vocabularies

- **`TradeEvaluationAttemptReasonCode` gains `ENTRIES_PAUSED`**: the refusal's `reasonCode`,
  `list_gate_blocks`' `reasonCode`, and the `scanBlockReason` of a refused fire's close record and
  journal row.
- **`TradingPipelineGateStage` gains `PLATFORM`**: a `list_gate_blocks` entry for each fire the pause
  refused, with no coin, no detail and no decision record.
- **`RadarFireDisposition` gains `EDGE_PRESERVED_ENTRIES_PAUSED`**: the refused fire keeps its edge,
  so the pair fires at a later close only if that close qualifies on its own data. It is served on
  `get_radar_activity` and `get_radar_activity_summary`, and as a close record's
  `outcome.fireDisposition` beside `outcome.scanBlockReason: "ENTRIES_PAUSED"`, with
  `outcome.outcome` staying `FIRED`.
- **`RadarIdleReason` gains `ENTRIES_PAUSED`**: the `resolvesNow.reason` of every `SCANNING` card on
  `get_radar_deployment` and `list_radar_deployments` while a pause is open. The section stays
  `SCANNING`, because closes are still decided and recorded.

### Answer corrected — a same-agent request

- **When an admission gate refused your own policy's fire** — an entry pause, an account block, a
  position already held on the coin — the request's conversation gains that block's ENGINE error card
  instead of `close_fired_by_radar`.

## Contract history — v74 (preview `conditionReach` replaced by `readings`)

**Breaking at v74: one required output field replaced on one tool, and an opt-in reading added to
another.** Both now serve what an agent reads on a coin, in the decision-record format v73.3
introduced.

### Reshaped output — `preview_radar_resolution`

- **`conditionReach` is gone, replaced by `readings`**: one entry per on-duty agent, in on-duty order,
  each naming `agentId` and `agentDisplayName`. A `kind: "READ"` entry carries the agent's `reading`,
  the one `get_agent_coin_qualification` serves (below). A `kind: "UNSCORABLE"` entry, an agent whose
  evaluation was rejected, carries `coinDataStopped` instead: the coin's stopped-data reading, or
  null. One agent's rejection is its own entry, never a failed preview. The tool always asks for
  readings, so `readings` is null only under a `simulatedRegime`.
- **`blocksScanGate` has no successor.** Since v73 the preview refuses a slot agent with a condition
  the radar scan cannot read on the coin, so no previewed pair holds a permanently blocking
  condition. Whether the conditions hold the coin is the reading's own gate,
  `reading.live.reading.qualification.gates.requiredConditions`.
- **Read `reachReason` from the reading.** Each `READ` entry's
  `reading.live.reading.conditions.entries[]` lists the conditions: a `kind: "UNEVALUATED"` entry
  carries the condition's `conditionKey`, `name` and `reachReason`, and a `kind: "EVALUATED"` entry,
  the counterpart of a null `reachReason`, carries its outcome with its clause values.
  `declaration.required` marks the required ones, the set `conditionReach` covered.
- **A client that validates results against a cached output schema** fails the call until it lists
  the tools again, because the old schema required `conditionReach`. Reconnect, or re-list, after the
  server deploys.

### Wider input and output — `get_agent_coin_qualification`

- **`reading` (boolean, default false) asks for the pair's reading**, and each verdict gains the
  required-nullable `reading`, null unless asked. A call without the flag is answered as before, with
  `reading: null`.
- **`reading.live`** is the reading the verdict was built from, with `anchorBarStatus` (`live` while
  the anchor bar still forms), `scoredBarStart` (the bar the signals and gates were scored on) and
  `observedAt`. It is what the agent reads now, not a decision: the radar decides at the close.
- **`reading.lastClose`** is the deciding reading of the bar the agent's on-duty row names as its
  last close decision: `state: "RECORDED"` with that bar's close-decision `record`,
  `state: "PENDING"` with its `barStart` while that record is being written, or `state: "NONE"`.
  `get_radar_close_decisions` holds the decisions before it.

## Contract history — v73.3 (decision records)

Purely additive: **one read tool, one evaluation-attempt reason and four output fields added.** What
a decision read is now served: the radar's close decisions on a coin, the report behind a trade, and
the compose decision behind a gate block.

### Wider surface — one tool added

- **`get_radar_close_decisions`** (`coinId`; optional `agentId`, `before`, `limit`; `mcp:read`) — one
  coin's radar close-decision records, newest decided bar first: every bar an agent decided —
  `FIRED`, `CLAIMED`, `NOT_QUALIFIED` or `MISSED` — with the reading it was decided on (a miss's
  answer instead), its fire disposition and its versions. Your own records only: a SYSTEM agent's
  records on a coin belong to every user who deployed it. A page never splits a bar, so it can run
  past `limit`; to page back, pass the oldest record's `bar.barStart` as `before`. `toolCount` goes
  141 → 142.

### Wider output — the risk budget, Radar reads, the trade conversation, gate blocks and signal logs

- **`TradeEvaluationAttemptReasonCode` may read `SCREENED_OUT`** on `get_agent_budget`,
  `reset_agent_drawdown_baseline`, `get_radar_activity`, `get_radar_deployment`,
  `list_radar_deployments`, `preview_radar_resolution`, `get_trade_conversation`,
  `propose_entry_decision`, `list_gate_blocks`, `get_signal_log` and
  `get_public_agent_signal_log_detail`: compose's deterministic pre-model screen found no routable
  direction. That refusal now writes a gate block. It is public: the public profile carries it as is.
  A client holding its own closed copy of the enum rejects the new member; one that renders unknown
  reasons generically is unaffected.
- **`get_signal_log`'s `log` gains `reportSections`** (the report the model read, section by section,
  in the shape of `preview_strategy_report`'s `renderedSections`), **`promptDataSerialization`** (the
  serialization it was rendered under) and **`missingData`** (the data compose lacked), each null for
  a trade recorded before capture. `get_public_agent_signal_log_detail` carries none of them.
- **Each `list_gate_blocks` entry gains `decisionRecord`**: the compose decision record written with
  the block — its outcome, its evidence (the reading compose computed, the per-bar values a refused
  decided bar lacked, or none), its missing data and its versions. It is null for a block written
  before capture and for a block raised before compose.

## Contract history — v73.2 (decided-bar refusal)

**One member added to the evaluation-attempt reason**, published as output only, and two detail
fields added to gate blocks. A confirming-close fire now names the bar it decided, and compose reads
that bar or refuses with the new reason, instead of reading the newest completed bar at its own
instant.

### Wider output — the risk budget, Radar reads, the trade conversation, gate blocks and signal logs

- **`TradeEvaluationAttemptReasonCode` may read `DECIDED_BAR_UNAVAILABLE`** on `get_agent_budget`,
  `reset_agent_drawdown_baseline`, `get_radar_activity`, `get_radar_deployment`,
  `list_radar_deployments`, `preview_radar_resolution`, `get_trade_conversation`,
  `propose_entry_decision`, `list_gate_blocks`, `get_signal_log` and
  `get_public_agent_signal_log_detail`: compose refused a radar fire at the conditions stage, before
  any LLM call, because a per-bar value its conditions gate reads was not on its due bar for the bar
  the radar decided — its entry had not landed, or had gone. It is public: the public profile carries
  it as is. A client holding its own closed copy of the enum rejects the new member; one that renders
  unknown reasons generically is unaffected.
- **`list_gate_blocks`' `reasonDetail` gains `decidedBarStart`** (ISO 8601, the decided bar's open)
  **and `decidedBarTimeframe`** (the strategy timeframe), present on that reason alone.

## Contract history — v73.1 (strategy card fields)

Purely additive: **thirteen read-only fields added to every `list_strategies` row.** The input is
unchanged, and a client that ignores the fields is unaffected.

### Wider output — `list_strategies`

- **The strategy card:** `regimeTimeframe` and `lowerTimeframe` (the derived ladder rungs
  `get_strategy` already serves); `conditionTally`, `signalRuleTally` and `exitTally` (`armed` out of
  `total`, the four exit mechanisms); and `minRequiredCount`, `entryTrigger`, `minRiskRewardRatio` and
  `maxStopLossAtrMultiple`.
- **`forkedFromStrategyName`**, null when the strategy is not a fork or its source is neither yours
  nor a SYSTEM strategy.
- **`viewerBoundAgentCount` and `viewerOpenPositionCount`**, your own agents on the strategy and their
  open positions. `boundAgentCount` still counts every user's agents; read the viewer fields for
  yours.
- **`viewerPerformance`**, your own all-time results on the strategy, null when you never traded it.
  A trade counts toward the strategy recorded on the signal log that opened it, so rebinding an agent
  never moves it.

## Contract history — v73 (unreadable radar conditions refused)

**Breaking at v73: seven tools refuse bodies they used to accept, behind unchanged input schemas.**
A condition the radar acts on — a required one, a direction-setting one (a verdict carrier), an exit
one, and every condition they reference — must be readable by the radar scan on every coin the radar
acts on for its agent: each coin a Radar policy slots it on, enabled or paused; each coin it holds an
open position on, for its exit conditions; and each coin it has a pending manual request on.

### Rejected input — refused behind unchanged schemas

- **`VALIDATION_ERROR` with the authoring code `CONDITION_UNREADABLE_BY_RADAR_SCAN`** from
  `preview_radar_resolution` (every kind, for every slot agent whether on duty now or not, issuing no
  `previewToken`), `commit_radar_deployment_draft`, `rebind_intelligence_agent`, and
  `compile_strategy_plan` and `restore_strategy` on behalf of the bound agents the radar acts on (a
  strategy none of whose agents holds a slot, an open position or a pending request is never
  checked). `details.context.reachReason` says why: `INSTRUMENT` (the coin, or a benchmark section's
  own instrument, has no such data), `AGENT_TIMEFRAME` (the agent has no such rung) or `FEED` (the
  radar scan never reads that data: crowd reads, a spot read for an uncatalogued ticker, a timeframe
  the agent's plan does not load).
- **The message names the first conflicting agent, the condition, the column, the coin and the
  fixes**: stop the radar acting on the condition, make it read a column the scan has on that coin,
  or free the coin — take the agent off that coin's policy, close the position, or cancel the pending
  request. It is a fact about the pair, which no later sweep changes.
- **A refused compile issues no plan token**, so `stage_strategy_plan` cannot stage that content, and
  **`apply_strategy_plan` applies only a plan whose bound agents still hold the radar slot coins its
  compile checked**: a plan compiled before a deploy moved them fails verification. Compile again.
- **A condition reading a Session Field scalar** keeps `CONDITION_OPERAND_UNSERVED_IN_LANE`, now
  refused at the rebind and every strategy revision too, not only at the deploy.
- `stage_radar_deployment_draft` is unchanged: a draft holds no slot, and the preview its commit
  needs refuses. A body accepted under v72 is refused under v73 without one byte of it changing.

### Wider output — `propose_entry_decision`, `get_trade_conversation`

- **`propose_entry_decision` refuses a request whose agent the radar scan cannot read on the
  requested coin**, before its watch is registered, and releases its idempotency claim. It returns
  `type: "error"` with `error: { reasonCode: "CONDITION_UNREADABLE_ON_COIN", unreadable: {
  conditionKey, conditionName, column, coinTicker, reachReason } }`: facts only, no prose. Choose
  another coin, another agent, or a condition reading a column the radar reads on that coin, and
  send it again. `get_trade_conversation`'s error card carries the same `reasonCode` and
  `unreadable`.
- **A client that validates results against a cached output schema** fails a call that returns the
  new error until it lists the tools again, because the old schema has no such member. Reconnect, or
  re-list, after the server deploys.

### Refusals worth knowing before you apply, restore or rebind

- **`CONFLICT` with `details.reason: "RADAR_DEPLOYMENT_MOVED"`** from `apply_strategy_plan`,
  `restore_strategy` and `rebind_intelligence_agent`: the agents' radar slot coins moved after the
  write's check. Re-read and retry, so the retry's check covers the moved deployment; for a plan,
  compile again.
- **`commit_radar_deployment_draft` is a `CONFLICT`** when a slot agent's strategy or timeframes
  changed after its check. Preview again.

## Contract history — v72.0.1 (account read faults withheld on the public profile)

**No schema change: one value reclassified on one public read.**

### Reclassified output — `get_public_agent_signal_log_detail`

- **`pipeline.attempt.reasonCodes` carries `OWNER_PRIVATE`, with its detail omitted, where it would
  have carried `EQUITY_CHECK_UNAVAILABLE`, `ALLOCATION_CHECK_UNAVAILABLE`,
  `DAILY_COUNT_CHECK_UNAVAILABLE` or `APPROVAL_CHECK_UNAVAILABLE`.** Each says the account has an open
  block, which the public profile withholds. This supersedes the v71.1 note below that the public
  detail carries the two faults v71.1 added. `OWNER_PRIVATE` has been in that field's schema since
  v71, so a client validating against a cached output schema accepts it. `get_signal_log` still
  carries every precise code on your own agents.

## Contract history — v72 (public decision `userId` removed)

**Breaking at v72: one output field removed from one public read.**

### Removed output — `get_public_agent_signal_log_detail`

- **`log.linkedEntryDecision.userId` is gone.** It was the user the agent acted for. On a SYSTEM
  agent, which has no author and which any user may deploy, that named whoever deployed it, and the
  public profile deliberately shows no owner for a SYSTEM agent. There is **no replacement path** on
  the public read. A PRIVATE agent's author is `ownerUserId` on the agent's public profile, and the
  owner tool `get_signal_log` still carries `linkedEntryDecision.userId` on your own agents.
- **A client that validates results against a cached output schema** fails the call until it lists
  the tools again, because the old schema required the field. Reconnect, or re-list, after the server
  deploys.

## Contract history — v71.1 (two read-fault refusals)

**Two members added to the evaluation-attempt reason**, published as output only. When the server
cannot read an agent's daily trade count or its trading account's approval, the admission is blocked
with its own reason instead of borrowing the verdict it could not reach.

### Wider output — the risk budget, Radar reads, the trade conversation, gate blocks and signal logs

- **`TradeEvaluationAttemptReasonCode` may read `DAILY_COUNT_CHECK_UNAVAILABLE` or
  `APPROVAL_CHECK_UNAVAILABLE`** on `get_agent_budget`, `reset_agent_drawdown_baseline`,
  `get_radar_activity`, `get_radar_deployment`, `list_radar_deployments`, `preview_radar_resolution`,
  `get_trade_conversation`, `propose_entry_decision`, `list_gate_blocks`, `get_signal_log` and
  `get_public_agent_signal_log_detail`. `DAILY_TRADE_LIMIT_REACHED` and `AGENT_APPROVAL_EXPIRED` still
  mean what they say. A client holding its own closed copy of the enum rejects the new members; one
  that renders unknown reasons generically is unaffected.

## Contract history — v71 (owner-private reasons on the public profile)

**Breaking at v71: two public inputs narrow, and one public output widens.**

### Rejected input — `get_public_agent_signal_logs`, `get_public_agent_realized_trades`

- **`filter.rejectionReason` refuses the six owner-private failure reasons** —
  `BELOW_EXCHANGE_MINIMUM`, `INSUFFICIENT_BALANCE`, `INSUFFICIENT_MARGIN`,
  `AGENT_APPROVAL_EXPIRED`, `SIGNING_KEY_UNAVAILABLE`, `AGENT_HALTED` — with a validation error,
  where they used to filter. These tools read another user's agent, and a private reason answered a
  question about that user's budget, margin, approval, key or halt. No alias exists; filter by a
  public reason. `filter.expiryReason` still accepts every member.

### Wider output — `get_public_agent_signal_log_detail`

- **`pipeline.attempt.reasonCodes`, `pipeline.execution.failureReason` and `.expiryReason` may read
  `OWNER_PRIVATE`** in place of an owner-private reason, whose detail is then omitted. A client
  holding its own closed copy of these enums rejects the new member; one that renders unknown
  reasons generically is unaffected. A failed execution's `executionMessage` is now always null.
- **`get_signal_log` is unchanged**: on your own agents it still carries every precise code, its
  detail and the narrative.

## Contract history — v70.2 (allocation-check refusal)

**One member added to the evaluation-attempt reason**, published as output only. An admission the
server blocked because it could not read the account's allocation now carries
`ALLOCATION_CHECK_UNAVAILABLE`; `NO_AGENT_ALLOCATION` survives only on historical rows.

### Wider output — the risk budget, Radar reads, the trade conversation and gate blocks

- **`TradeEvaluationAttemptReasonCode` may read `ALLOCATION_CHECK_UNAVAILABLE`** on
  `get_agent_budget`, `reset_agent_drawdown_baseline`, `get_radar_activity`, `get_radar_deployment`,
  `list_radar_deployments`, `preview_radar_resolution`, `get_trade_conversation`,
  `propose_entry_decision` and `list_gate_blocks`. A client holding its own closed copy of the enum
  rejects the new member; one that renders unknown reasons generically is unaffected.
- **The reason detail no longer declares `availableUsd` or `requiredUsd`** (`get_signal_log`,
  `get_public_agent_signal_log_detail`). No response ever carried them.

## Contract history — v70 (risk-gauge `configured` removed)

**Breaking at v70: one output field removed from every risk-budget gauge.**

### Reshaped output — `get_agent_budget`, `reset_agent_drawdown_baseline`

- **`budget.gauges.<gauge>.configured` is gone** from all four gauges (`dailyTrades`, `exposure`,
  `drawdown`, `dailyLoss`). It could only read `true`: the daily-trades cap is at least 1, and an
  agent's exposure ceiling, drawdown stop and daily-loss stop are all required and strictly positive.
  Every gauge has a limit, so read `fill`, `remaining` and `breached` and render every meter enabled.
- **A client that validates results against a cached output schema** fails the call until it lists
  the tools again, because the old schema required the field. Reconnect, or re-list, after the server
  deploys.

## Contract history — v69.7 (insufficient-margin refusal)

Purely additive: **one member added to the trade-failure reason**, in both directions. An agent entry
the shared trading account cannot post the isolated margin for is now refused before any order is
sent, with its own reason. The same reason replaces `EXCHANGE_ERROR` when the exchange refuses an
order for margin first.

### Wider input — `get_public_agent_signal_logs`, `get_public_agent_realized_trades`

- **`filter.rejectionReason` accepts `INSUFFICIENT_MARGIN`**, where it used to refuse it.

### Wider output — `get_signal_log`, `get_public_agent_signal_log_detail`

- **`failureReason` may read `INSUFFICIENT_MARGIN`.** A client that switches exhaustively on the
  reason needs one more arm; one that renders unknown reasons generically is unaffected.

## Contract history — v69.5 (liquidation-buffer refusal)

Purely additive: **one member added to the trade-failure reason**, in both directions. An agent entry
whose hard stop no whole leverage can keep clear of liquidation is now refused before any order is
sent, with its own reason. Below that, an agent order's reported effective leverage may sit under the
agent's bound: it is lowered until the isolated liquidation is at least twice as far from the fill as
the hard stop.

### Wider input — `get_public_agent_signal_logs`, `get_public_agent_realized_trades`

- **`filter.rejectionReason` accepts `LIQUIDATION_BUFFER_UNREACHABLE`**, where it used to refuse it.

### Wider output — `get_signal_log`, `get_public_agent_signal_log_detail`

- **`failureReason` may read `LIQUIDATION_BUFFER_UNREACHABLE`.** A client that switches exhaustively on
  the reason needs one more arm; one that renders unknown reasons generically is unaffected.

## Contract history — v69 (Radar multi-agent duty)

**Breaking: one input removed from two tools, three outputs reshaped.** A Radar policy carries no
timeframe. Every rule whose conditions match puts its agent on duty at once, and each rule's regime
condition is read at that agent's own regime timeframe. A coin still holds one position at a time: at
most one fire per coin per pass, offered in rule priority.

### Rejected input — something you send is no longer accepted

- **`preview_radar_resolution`'s `SLOTS` request refuses `deploymentTimeframe`** as an unrecognized key.
  Send `{ kind: "SLOTS", slots }`.
- **`stage_radar_deployment_draft` refuses the `DEPLOYMENT_TIMEFRAME` axis** the same way. Stage only
  `RULES` and `DEFAULT_SLOT`.

### Reshaped output — something you read has a new shape

- **`resolvesNow`** on `get_radar_deployment`, `list_radar_deployments` and `preview_radar_resolution` is
  the coin's state (`section`, `isIdle`, `rotating`, one `reason`, the open-position owner) plus
  **`onDuty`**: one row per agent on duty, in priority order. Each row carries its slot, its regime reading
  at its own regime timeframe, its qualification verdict and gate, cooldown, block, `edgeSpent`, last flip
  and fire, and its own `closeDecision`. The single-winner fields (`onDutyAgentId` and its display pair,
  `matchedSlot*`, `regimeUsed`, and the per-agent fields the rows now carry) are gone. Render every row in
  the order served, and never pick one yourself.
- **`preview_radar_resolution`'s `conditionReach`** is one flat list, each entry naming its `agentId` and
  `agentDisplayName`.
- **Each deployment slot gains `agentRegimeTimeframe`**, the timeframe its rule's regime is read at.

### Removed output — a field you read is gone

- **`deploymentTimeframe`** on a Radar policy, and the **`DEPLOYMENT_TIMEFRAME`** axis in the radar
  draft's `content` and `axesMeta` on `get_radar_deployment_draft`, `list_radar_deployment_drafts` and the
  stage result.

### Wider enums — a value you may now receive

- **`closeDecision.outcome` gains `CLAIMED`**: the agent's close qualified, but a higher-priority agent
  took the coin's one fire that pass. Its edge is preserved, and it fires at a later close only if it
  still qualifies there.
- **`get_radar_activity` and `get_radar_activity_summary`** gain the events `ON_DUTY_JOINED` and
  `ON_DUTY_LEFT` (duty is journaled per agent) and the fire disposition `EDGE_PRESERVED_COIN_CLAIMED`.
  `curveDigest` describes the first agent on duty, named in `curveAgentName`.
- **`get_trade_conversation`** may carry the `close_claimed_by_radar` card.

The exported `battlegrid-radar-deployment` skill describes the v69 flow.

## Contract history — v68.1 (Arena regime sets)

Purely additive in schema, with **one refusal behind unchanged ones.** An Arena rule's regime condition
is a SET in the draft, as it always was in the committed deployment: one rule can fire in several
regimes, instead of one rule per regime.

### Wider input — `stage_deployment_policy_draft`

- **A rule's `regimes` may name several regimes**, where the draft capped it at one. The set is stored in
  the selectable-regime order, so a staged `[VOLATILE, BULL_EXPANSION]` reads back
  `[BULL_EXPANSION, VOLATILE]`. A regime named twice is refused.

### Wider output — `get_deployment_policy_draft`

- **The draft may return such a set.** `get_deployment_policy` has served sets all along, so a client that
  reads a committed deployment already handles them.

### Refusals behind unchanged schemas

- **`preview_deployment_resolution` (SLOTS), `preview_radar_resolution` (SLOTS) and
  `test_generate_deployment_grid` refuse a regime condition naming one regime twice**, as
  `VALIDATION_ERROR` at its `regimes` field, where they used to resolve or generate over it. The stage tools
  already refused a repeat, so no commit changes; a repeated member is a malformed set.

## Contract history — v68 (Arena drafts)

**Breaking: one tool retired, two inputs reshaped.** Arena deployment content now commits only as a
draft the player was shown a live preview of, as radar content has since v66. The player's deploy
editor and every conversation share one unsaved draft per arena.

### Removed tool — something you call no longer exists

- **`upsert_deployment_policy` is retired**, with no alias. Calling it is an unknown-tool error. To
  deploy or change an arena's deployment:
  1. `stage_deployment_policy_draft` the axes you are changing (`RULES`, `DEFAULT_SLOT`,
     `REGIME_ANCHOR`), with the `draftVersion` your last read returned;
  2. `preview_deployment_resolution` with `request: { kind: "DRAFT", draftVersion }` at the version
     staging returned;
  3. show the player the resolution and whether it will play (`enabledAfterCommit`), and on their word
     call `commit_deployment_policy_draft` with the `previewToken` that preview returned and
     `confirm: true`.

  Pausing is no longer a flag on the write: use `pause_deployment_policy`. **A first deployment always
  plays**; a replacement keeps its pause.

### Rejected input — something you send is no longer accepted

- **`preview_deployment_resolution`'s `request` needs a `kind`.** `{ kind: "SLOTS", slots, … }` is the
  old request. `{ kind: "DRAFT", draftVersion }` previews the player's draft of the arena at that
  version, composed over the deployed policy exactly as the commit writes it. `{ kind: "COMMITTED" }`
  previews the deployed policy a resume would arm. A request without `kind` is refused.
- **`delete_deployment_policy` requires `expectedPolicyId`** beside `expectedRevision`: a revision
  restarts at 1 when an arena is redeployed, so only the pair names the deployment you read.
- **A regime anchor override names its coin and timeframe together, or neither**, on every path
  including `test_generate_deployment_grid` and the SLOTS preview.

### Wider surface — eight tools added

- **`stage_deployment_policy_draft`**, **`get_deployment_policy_draft`**,
  **`list_deployment_policy_drafts`** and **`discard_deployment_policy_draft`** (`mcp:read`). None of
  them commits or arms anything.
- **`commit_deployment_policy_draft`** (`presetId`, `previewToken`, `confirm: true`; `mcp:wager`) — the
  only MCP committer of Arena content.
- **`pause_deployment_policy`** (`presetId`; `mcp:wager`) — no revision and no certificate.
- **`resume_deployment_policy`** (`presetId`, `previewToken`, `confirm: true`; `mcp:wager`) — needs the
  certificate a live `COMMITTED` preview returned.
- **`cancel_market_grid_submission`** (`sessionId`, `confirm: true`; `mcp:wager`) — the player's own
  cancellation and refund of one entry.

### Reshaped and wider output

- **`preview_deployment_resolution`** nests the resolution under `resolution` and gains
  **`previewToken`** (the certificate a live DRAFT or COMMITTED preview earns, null otherwise, good for
  five minutes) and **`enabledAfterCommit`**.
- **`pause_deployment_policy` and `delete_deployment_policy` return `openEntries`**: the entries the
  player's agent already made in the arena's pending sessions, each with its lock time and entry fee.
  They play out unless the player cancels them — tell the player and ask, then call
  `cancel_market_grid_submission` only for the entries they pick.
- **`get_deployment_policy`'s `authoringContext`** gains the arena's header facts
  (`regimeReferenceTicker`, `presetBadgeImageUrl`, `entryFee`, and `playerCount` — null when the arena
  has no pending session to count).
- The thought-log **`outcome`** gains **`SKIPPED_DEPLOYMENT_DISARMED`**: an entry job that found its
  deployment withdrawn, paused or no longer slotting its agent stood down before paying.

### Refusals worth knowing before you commit or resume

- **The certificate is bound to what you previewed**: your credential, the player, the arena, the
  subject, the deployment and its revision, the draft version and the composed content. Anything that
  moves is a `CONFLICT` and nothing is written. Preview again; never reuse the old certificate.
- **A commit never withdraws**: a draft with no rule and no catch-all is refused, naming
  `delete_deployment_policy`.
- **Resume is refused on a retired arena and on one the player's access was revoked from**; pausing and
  withdrawing stay open.
- **Deployment refusals answer `INVALID_DEPLOYMENT_POLICY`.**
- **`delete_deployment_policy` also ends the player's draft of the arena.**

### Vocabulary

`toolCount` goes 134 → 141 (eight added, one retired). `preview_deployment_resolution`'s input and
output, `delete_deployment_policy`'s input and output, `get_deployment_policy`'s and
`list_deployment_policies`' outputs, the three journal outputs and `test_generate_deployment_grid`'s
input (a session start now accepts up to 288 times a day) move; `upsert_deployment_policy`'s are
removed.

## Contract history — v66.1 → v67

**Breaking at v67: four output fields removed.** v66.1 and v66.2 were additive and are recorded here
with it.

### Reshaped output — `get_agents_hub` (v67, breaking)

- **`summary` loses `messagesUsedToday`, `dailyLimit`, `messagesUsedPercent` and
  `avgCostPerMessageUsd`.** They reported the in-app arena chat's daily message quota, and that chat
  is retired, so every value would have read zero. A strict client that reads them fails to parse the
  summary. The rest of the summary is unchanged; per-agent spend stays on each row's `cost24hUsd`.

### Wider surface — two tools added (v66.2)

- **`scan_coin_agents`** (`coinTicker`; `mcp:read`) — one coin evaluated against every one of the
  caller's own agents, ranked in four arrays: `qualified` by score, `rejected` with the first failing
  gate, `unscorable`, and `ineligible` with the code `propose_entry_decision` would refuse the agent
  with (`AGENT_NOT_ACTIVE`, `MODEL_INACTIVE`, `AGENT_HALTED`). `rank` is global across the four.
  Rate-limited per user: a refusal is `RATE_LIMITED` with `retryAfterSeconds`.
- **`get_onboarding_requirements`** (no input; `mcp:read`) — the caller's readiness ladder: every
  rung, the spine counts and the next rung.

### Reshaped output — `get_strategy_draft` (v66.1)

- **`draft` gains `lastSource`** — the surface of the draft's latest write (`form`, `commander`,
  `telegram` or `mcp`), as the agent and radar draft reads already publish. Before v66.1 every read of
  an existing strategy draft failed its output check with `INTERNAL_ERROR`; it now succeeds.

### Vocabulary

`toolCount` goes 132 → 134. The added tools' schemas are new; `get_strategy_draft`'s and
`get_agents_hub`'s output schemas move. Descriptions that named the app's retired Agent Toolbox trade
tab now name Commander.

## Contract history — v66

**Breaking: one tool retired and one input reshaped.** Radar content now commits only as a draft the
player was shown a live preview of. The player's radar builder and every conversation share one
unsaved draft per coin.

### Removed tool — something you call no longer exists

- **`upsert_radar_deployment` is retired**, with no alias. Calling it is an unknown-tool error. To
  deploy or change a coin's Radar policy:
  1. `stage_radar_deployment_draft` the axes you are changing;
  2. `preview_radar_resolution` with `request: { kind: "DRAFT", draftVersion }` at the version staging
     returned;
  3. show the player the resolution, and on their word call `commit_radar_deployment_draft` with the
     `previewToken` that preview returned and `confirm: true`.

  Pausing is no longer a flag on the write: use `pause_radar_deployment`.

### Rejected input — something you send is no longer accepted

- **`preview_radar_resolution`'s `request` needs a `kind`.** `{ kind: "SLOTS", deploymentTimeframe,
  slots, simulatedRegime? }` is the old request. `{ kind: "DRAFT", draftVersion }` previews the
  player's draft of the coin at that version, composed over the deployed policy exactly as the commit
  writes it. `{ kind: "COMMITTED" }` previews the deployed policy a resume would arm. A request
  without `kind` is refused.

### Wider surface — seven tools added

- **`stage_radar_deployment_draft`**, **`get_radar_deployment_draft`**,
  **`list_radar_deployment_drafts`** and **`discard_radar_deployment_draft`** (`mcp:read`). The draft
  axes are `DEPLOYMENT_TIMEFRAME`, `RULES` (the complete ordered rule list, first = highest priority)
  and `DEFAULT_SLOT`, each written whole. None of them commits or arms anything.
- **`commit_radar_deployment_draft`** (`coinId`, `previewToken`, `confirm: true`; `mcp:wager`) — the
  only MCP committer of radar content.
- **`pause_radar_deployment`** (`coinId`; `mcp:wager`) — no revision and no certificate: a disarm never
  waits on a read.
- **`resume_radar_deployment`** (`coinId`, `previewToken`, `confirm: true`; `mcp:wager`) — needs the
  certificate a live `COMMITTED` preview returned.

### Reshaped output — `preview_radar_resolution`

- Gains **`previewToken`**, the certificate a LIVE preview (no `simulatedRegime`) of `DRAFT` or
  `COMMITTED` earns — null otherwise, and good for five minutes. It also gains
  **`enabledAfterCommit`**: whether the policy trades once the previewed write lands. A paused
  policy's draft stays paused.

### Refusals worth knowing before you commit or resume

- **The certificate is bound to what you previewed**: your credential, the player, the coin, the
  subject, the deployment and its revision, the draft version and the composed content. If the
  player edits the draft, another commit lands, the coin is redeployed, or an agent in it is deleted,
  the commit or resume is a `CONFLICT` and nothing is written. Preview again; never reuse the old
  certificate.
- **`commit_radar_deployment_draft` takes only a draft certificate**, and `resume_radar_deployment`
  only a committed-policy one.
- **`discard_radar_deployment_draft` with `confirm: true` requires `expectedVersion`**: the version the
  unconfirmed call named and the player was shown. A draft that moved since is answered again, and
  nothing is removed.
- **`delete_radar_deployment` also ends the player's radar draft of the coin.**

### Vocabulary

`toolCount` goes 126 → 132. `preview_radar_resolution`'s input and output schemas move, and
`upsert_radar_deployment`'s are removed.

## Contract history — v65

**Breaking on one input, and four refusals behind unchanged schemas.** Agent staging now names the
draft version its proposal was read against, and three commits and one stage step aside where they
would otherwise land around the player's open draft or on a strategy that moved.

### Rejected input — something you send is no longer accepted

- **`stage_agent_draft` requires `draftVersion`**, an integer ≥ 0: the `version` the
  `get_agent_draft` read you proposed against returned, or `0` when it returned `{ draft: null }`.
  A call that omits it, or sends a negative or fractional number, is refused at the boundary. On a
  new create draft send `0`, then reuse the `version` each accepted call returns.

### Refusals worth knowing before you stage or commit

- **A `draftVersion` above the draft's own is refused.** A draft's version only grows, so no read
  ever returned it: the draft you read was saved or discarded since. Read again — never raise the
  number to get past the refusal.

- **The contested-axis refusal is measured from your `draftVersion`**, not from a read the call
  makes for itself, so an edit the player made between your read and your stage is refused by name
  rather than silently overwritten.

- **`update_strategy_signal_rule` and `restore_strategy` answer `CONFLICT` while the player holds a
  draft of that strategy.** Compile the tune and stage it with `stage_strategy_plan`; for a restore,
  ask the player to save or discard their draft first. A caller whose player holds no draft is
  unaffected.

- **`stage_strategy_plan` refuses a plan the strategy committed past** after the plan compiled,
  with the same answer `apply_strategy_plan` gives: compile again against what is committed now.

- **Every refusal around an open draft names its version** in `details.draftVersion` — the
  committers above, the agent committers, and a stage refused for a version above the draft's own —
  so you can read the draft the player holds and propose against it.

### Changed meaning, unchanged shape

- **A draft axis's `source` names the door it came through.** A Telegram Commander turn stamps
  `telegram` and a connected client stamps `mcp`, where every staging call used to stamp
  `commander`. Both values were already in the enum.

- **A draft's `version` keeps counting after a save or discard empties it.** The next draft for the
  same agent or strategy starts above the last version rather than at `1`, so a version you read is
  never reissued to a different draft.

### Vocabulary

`toolCount` stays 126. One input schema moves, `stage_agent_draft`'s; no output schema moves.

## Contract history — v64.1

Purely additive in schema, with **one refusal behind an unchanged one.** An agent's unsaved
configuration now has a server home — the same owner-scoped *draft* strategies gained in v63.1 — so
the agent form, Telegram and a connected client all see one set of unsaved values. These tools are
how a conversation reaches it, and the two agent committers now step aside while it is open.

### Wider surface — four tools added

- **`stage_agent_draft({ request: { agentId?, axes } })`** writes proposed axes into the player's
  draft for an agent and commits **nothing**: the values become the agent's configuration only when
  the player saves. Unlike `stage_strategy_plan` it takes the axis *values* — `IDENTITY`,
  `BEHAVIOR`, `MODEL`, `TRADING_CONFIG`, and for an agent not yet created `STRATEGY_BINDING` — each
  written **whole**, so `BEHAVIOR` carries all three of risk, outlook and conviction and
  `TRADING_CONFIG` the complete agent-owned configuration. Axes you omit keep their values.
  Structure is checked on the way in; ranges are checked only when the player saves.

- **Omit `agentId` to open a create draft.** The server mints the id and the response carries it;
  name that id on every later call so one draft accumulates rather than a second opening beside it.

- **`get_agent_draft({ request: { agentId } })`** reads one draft, or answers `{ draft: null }` —
  not part-way through that agent is a value, not an error. `baseRevision` is `null` for an agent not
  yet created, and `baseMoved` reports an agent committed past the revision the draft was written
  against.

- **`list_agent_drafts({ request: { cursor? } })`** answers "what am I part-way through?" for a
  conversation holding no agent id, newest first. Offer to continue one of these before starting a
  second.

- **`discard_agent_draft({ request: { agentId, confirm } })`** destroys one draft on the player's
  word. Called with `confirm: false` it destroys nothing and is refused with when the draft was last
  written and which surface wrote it — tell the player that, then ask.

### Refusals worth knowing before you stage or save

- **A staged proposal refuses the axes the player typed after your call read the draft.** The
  refusal names the axes; read the draft again and propose against what they now have. Another
  surface's write to a *different* axis is retried once for you, then reported as a conflict.

- **`STRATEGY_BINDING` is refused on an agent that exists.** Rebinding replaces an agent's
  configuration and stays its own confirmed call, `rebind_intelligence_agent`.

- **`update_intelligence_agent` and `rebind_intelligence_agent` answer `CONFLICT` while the player
  holds a draft for that agent**, naming staging as the act available. Nothing about their input or
  output changed, and a caller whose player holds no draft is unaffected — this is the one change
  existing code can observe.

### Vocabulary

`toolCount` 122 → 126. No input or output schema of an existing tool moves.

## Contract history — v64

**Breaking, and it is a removal you will feel on two tools.** A vocabulary that never depended on
your draft was being re-serialized into every preview result; it now lives on discovery and the
preview names it.

### Reshaped output — `preview_strategy_report`

- **`conditionColumns` covers only the sections your report RENDERS.** It used to cover every
  section the server's header inventory holds, which meant every report-level scalar on every
  preview whether or not its module was placed — 36,652 bytes of payload, with each metric's gloss
  repeated once per scope (11 market-breadth sentences published as 99). If you read
  `session-field`, `market-breadth` or `reference-pairs` groups off a preview, they are gone.

- **Nothing stopped resolving.** The header inventory is unchanged, so a condition naming
  `mktBreadth_crypto` resolves exactly as it did. What changed is where you read its prose from.

- **`vocabularyDigest` is new** — the sha256 identity of the authoring catalog that render described
  its columns against, and the same digest a plan token binds as `authoringCatalogDigest`. Resolve
  the vocabulary once, cache it against this string, and re-resolve when it moves.

- **`structure.columns[].meaning` is gone.** It was a positional per-header string that neither
  serialization ever rendered — the glossary paragraph in `section.text` is built from
  `spanFragments`, and the structured arm always omitted `meaning`. `spanFragments` is unchanged.

- **`budgetUsage.estimatedTokens` now measures the whole served payload**, not the rendered module
  text inside it. Existing drafts read several times higher against the same cap. That is the fix,
  not a regression: the byte cap is measured on the serialized result and cannot be reported inside
  it, so this is the only meter that can warn you before a refusal — and it was counting about a
  tenth of what actually refuses.

### Wider output — `list_strategy_vocabulary`

- **`scalarFamilies` is where the vocabulary went.** Every report-level scalar family with its
  section, and one entry per METRIC carrying its gloss, legal condition operators, closed label
  vocabulary, read contract (`closesReadable` / `developingRead`; v84 replaces `closesReadable` with
  `conditionHold`) and the scopes it is measured at.
  One gloss per metric with its scopes named against it, never one per pair.

- **Served whole under every category.** A scalar describes the report, not a metric family, so it
  is not filtered by the `category` you asked for. The ambient session family carries
  `moduleKey: null` — it places no module and its operands are nameable all the same.

### Reshaped output — `compile_strategy_plan`

- **`reviewContext.columns` is gone.** It recompiled a full column contract per authored custom
  column — about 2,100 bytes for a five-header trajectory — describing columns the embedded
  `reportPreview.conditionColumns` already describes per rendered header. Ask
  `get_strategy_column_contract` when you want a column's exact normalized contract.

- **`approvedPlan.creationSeed` is gone.** It was the dense 84-rule scorecard *before* the
  overrides, published beside a `postState.signalRules` that is the same list *after* them and an
  `explicitRuleOverrides` naming exactly what differs. Apply never saw it either.

### Wider input acceptance

- **The section array and a custom section's column array lose their `maxItems: 64`.** That bound
  restated a configured cap of 32 as a looser 64 that never refused anything. `budgets.sections` and
  `budgets.sectionColumns` from discovery are the published values, and the server enforces them
  before it reads any market data.

### What to do

Call `list_strategy_vocabulary` once for the scalar vocabulary, key your cache on the preview's
`vocabularyDigest`, and drop any code that reads scalar groups off `conditionColumns`,
`structure.columns[].meaning`, `reviewContext.columns` or `approvedPlan.creationSeed`. A preview's
size now tracks the report and cohort you composed rather than the size of the platform's catalog.

## Contract history — v63.2

Purely additive again, and smaller: **one optional input field.** Drafts now cover a strategy that
does not exist yet, so a playbook you author in chat survives between compiles instead of starting
over each time.

### Wider input — one optional field on one tool

- **`compile_strategy_plan`'s CREATE arm gains an optional `strategyId`**, naming the create draft
  this compile continues. Omit it and the server mints an id exactly as it always has, so nothing
  you send today breaks.

- **Send it to accumulate; omit it to start fresh.** A first CREATE names nothing and mints; stage
  that plan and the draft opens at the minted id, which `list_strategy_drafts` and the plan itself
  both report. Name that id on the next CREATE and the second plan carries the same identity, so the
  one draft accumulates rather than a second opening beside it.

- **WHY YOU HAVE TO SAY IT.** The server will not choose for you. A compile knows only who you are —
  it has no conversation id — and you may hold several create drafts, so picking one could write this
  playbook's values over another's. A compile that names none mints a third id rather than guessing.

- **It names a draft; it does not choose an id.** It is accepted only as the identity of a create
  draft you own. An id naming no such draft is refused, as is one naming a draft for a strategy that
  already exists.

### Behaviour changes behind unchanged schemas

- **`stage_strategy_plan` admits a CREATE plan**, opening the create draft at the plan's own id when
  none exists yet. Its input is still `{ planToken }` alone, and the contested-axis refusal applies
  identically.

- **`list_strategy_drafts` rows gain `baseRevision`.** It is `null` for a create draft — a strategy
  that does not exist has no committed revision to be based on — and that null is the only thing that
  distinguishes one. There is no `kind`, `isNew` or `status` field beside it.

- **A create draft reserves nothing.** It consumes no quota and holds no name, so both are decided
  when the strategy is actually created. Holding drafts past your limit is legal; creating past it is
  not.

### Vocabulary

`axes.create` gains `strategyId`. No domain gains a value, and `toolCount` stays 122.

## Contract history — v63.1

Purely additive: **four new tools, nothing you send today changes.** A strategy now has an
owner-scoped *draft* — the unsaved authored values a player is part-way through — and these are how
an agent reads it, writes a compiled plan into it, and destroys one. The canonical record for every
contract move is `docs/architecture/MCP_CONTRACT_HISTORY.md` in `battlegrid-app`; the served version
is what the handshake announces.

### Wider surface — four tools added

- **`stage_strategy_plan({ request: { planToken } })`** writes a compiled plan's own changed axes
  into the owner's draft. It commits nothing and does **not** spend the plan, so the same token is
  still directly applicable afterwards. `planToken` is the only member the request accepts.

- **`get_strategy_draft({ request: { strategyId } })`** reads one draft, or answers `{ draft: null }`
  — "you are not part-way through this one" is a value, not an error. It reports `baseMoved` when the
  strategy has been committed past the revision the draft was written against.

- **`list_strategy_drafts({ request: { cursor? } })`** answers "what am I part-way through?" for a
  conversation holding no id. It includes a draft whose strategy you can no longer see, marked
  `strategyExists: false`, because that is exactly the work a player has lost track of.

- **`discard_strategy_draft({ request: { strategyId, confirm: true } })`** destroys one draft. The
  confirmation is required and unsaved values have no other copy; the strategy, its revisions and
  your other drafts are untouched.

### Refusals worth knowing before you stage

- **A staged plan refuses the axes you typed after it compiled.** `stage_strategy_plan` answers
  `CONFLICT` naming `contestedAxes`, the version the plan compiled over and the draft's own version
  per axis. Compile again so the plan absorbs those edits, then stage. A *previous staging* on the
  same axis is not a contest — only the owner's own hand is.

- **An apply refuses a plan whose draft has moved since.** Moved, discarded and
  already-committed-by-a-sibling are one answer with one recovery: compile again.

### Vocabulary

`toolCount` 118 → 122. No input or output schema of an existing tool moves — the draft version a
plan was compiled over rides inside the opaque plan token, which no schema declares.

## Contract history — v61

One part to read first: **the per-condition evidence clock is gone**, and what replaced it is not a
rename. Which bar a condition reads is now decided by the surface asking — a decision reads completed
strategy bars, a display read shows the forming one — and by each candle column's own Confirmed /
Developing selector. `closes` survives and changes meaning. The canonical record for every contract
move is `docs/architecture/MCP_CONTRACT_HISTORY.md` in `battlegrid-app`; the served version is what
the handshake announces.

### Rejected input — something you author is no longer accepted

- **A condition entry carrying `clock` is REFUSED** (61.0.0, `read-higher-timeframes-per-column`).
  The authoring schemas are `.strict()`, so `compile_strategy_plan`, `apply_strategy_plan`,
  `fork_strategy` and the HTTP save alike fail the body with the unknown-key error. There is no
  replacement key to send: the decision instant belongs to the caller, not to the condition. Two
  input hashes move, `compile_strategy_plan`'s and `preview_strategy_report`'s — the two tools that
  accept a condition entry.

- **`closes` stays mandatory and means something new.** It is now *held for N completed strategy
  bars* (1–5). Above `1` it is legal only over a header a completed bar actually moves, at or above
  the strategy timeframe, never over a developing read, and only where the condition carries a clause
  of its own — a referenced condition resolves once and contributes the same answer to every bar, so
  a hold reached only through a reference would count reads that never happened.

### Changed shape — what you receive moves

- **`ConditionOutcome.closeClock` becomes `hold`, and it is NON-NULL for every condition.** A
  one-close condition reads `0 or 1 of 1` rather than serving an absence, so a client no longer
  branches on whether the reading exists. The count is taken from completed strategy bars whatever
  basis the surface evaluated on.

- **`ReportConditionColumnDTO.closeClockReadable` becomes `closesReadable`, beside a new
  `developingRead`.** The first answers whether a condition addressing that header may hold more than
  one completed bar; the second states whether the header reads the bar still in progress at the
  decision instant. Both are server-supplied — derive neither. Eight output hashes move, covering
  every tool that serves a strategy's conditions or a report's addressable columns.

### Wider input — nothing you send today breaks

- **The `bars` selector is declared on eleven candle-series transforms, not four.** `value`,
  `classifyZone`, `classifyState`, `distance`, `spread`, `crossDetect` and `bandTouch` join
  `trajectory`, `aggregate`, `efficiency` and `maxShare`. It carries **no default value**, because
  the default is a rule rather than a constant: Confirmed (`"closed"`) above the strategy timeframe,
  and at or below it the series as the frame carries it. The resolved answer is served per column on
  `effectiveParameters.bars` — `null` where discovery has no anchor to resolve a rung against.

- **A higher-timeframe level is measured from the current strategy-bar price.** Distances and the
  candle label classifiers compare against the frame's current price rather than the higher-timeframe
  bar's own close, which could be a full higher-timeframe bar stale. A distance chained into a series
  keeps every slot on its own bar's close.

### Vocabulary

`domains.conditionClock` is removed; `domains.columnBars: ["all", "closed"]` takes its place, and
`axes.condition` loses `clock`. `toolCount` stays 117.

## Contract history — v60

One release train, four numbers, and two parts to read first: **`propose_entry_decision` no longer
decides in the call**, and **a closed trade's `tradeStatus` now follows its net P&L**. v55 through v59 are not written up here; the canonical record for
every contract move is `docs/architecture/MCP_CONTRACT_HISTORY.md` in `battlegrid-app`, and the
served version is what the handshake announces.

### Rejected input — something you author is no longer accepted

- **The entry axis names no bar but the strategy's own, and three of its keys are gone** (60.0.0,
  `decide-entry-on-strategy-close`). The authoring schemas are `.strict()`, so `compile_strategy_plan`,
  `apply_strategy_plan`, `fork_strategy` and `restore_strategy` REFUSE a body carrying
  `entry.confirmTf` (the deciding bar is the strategy's own timeframe, so a required input whose only
  legal value was another field of the same strategy is absent rather than mirrored), `entry.closes`
  and `entry.bandAtrMultiple` (a multi-bar hold is declared on the condition that needs it; the
  displacement band is replaced by the platform's own entry-deviation gate, measured against the
  decided close), and the whole `exit` object (the open-position exit lane judges one closed candle
  of the position's strategy timeframe). Exactly one input hash moves, `compile_strategy_plan`'s.

- **`entry.trigger: AT_SIGNAL` is retired for authoring** (60.0.0, `retire-at-signal-trigger`, riding
  the same number). Refused on every authoring surface and on a RESTORE, which rebuilds a stored
  revision through the same value object. The enum member stays READABLE on every strategy read and
  on a fired decision's provenance, so a pre-retirement revision is still legible — it just cannot be
  re-authored. The three that remain are `ON_CANDLE_CLOSE`, `STOP_THROUGH_LEVEL` and `ON_RETEST`.

### Changed meaning, unchanged shape

- **`tradeStatus` follows NET P&L on every closed trade** (60.3.0, `label-trade-outcome-by-pnl`).
  No schema hash moves for this and the values you receive change anyway. It used to map the close
  REASON onto a verdict — every `TAKE_PROFIT` was `WON`, every `STOP_LOSS` was `LOST`, and a
  `MARKET_CLOSE` of either sign was the neutral `CLOSED` — so a stop that filled after a break-even
  reprice was reported as a loss and a take-profit eaten by fees as a win. `LIQUIDATED` still
  outranks the number, because a force-close is not a verdict about the trade; `CLOSED` now means
  only that there is no outcome row to judge. A client that counted `WON` rows was counting
  take-profits.

- **A proposal is QUEUED, not decided** (60.2.0, `queue-manual-entry-for-close`). This is the entry in
  this section to act on. `propose_entry_decision` registers a request against the agent's next
  strategy-bar close and returns immediately: no model runs, nothing is spent, and the call carries
  `type: "queued"` with `request` — `requestId`, the bar (`barStart`), when the answer is due
  (`decidesBy`) and the last instant that bar may still be decided (`windowEndsAt`). The answer
  arrives later, in the agent's conversation and, when it proposes a trade, in
  `list_pending_approvals`. A close that does not qualify, a window that passes with no sweep, and a
  bar the agent's own radar deployment decided first are each recorded in the conversation instead.

  `recommendation` and `no_trade` REMAIN in the union: the idempotency registrar replays results
  recorded before this release for their TTL, so a client that dropped those members would fail on
  its own retry. **A client written against 60.2 handles `queued` and `error`**; one that must also
  replay handles all four.

### Reshaped output — the same call returns a different shape

- **The four retired entry keys leave every strategy read** (60.0.0) — `get_strategy`,
  `list_strategies`, `fork_strategy` and both plan envelopes — and `confirmTimeframesByMainCandle`
  leaves `list_strategy_vocabulary`, because there is no confirm set left to publish.

- **`entryDiscipline.closes` and `.bandAtrMultiple` go `number` → `number | null`** (60.0.0) on
  `get_trade_outcome_by_decision` and `list_trade_outcomes`. Null on every decision fired after this
  release, which authors neither; a non-null pair dates the row to the arming era.

### Widened enum — new members your own copy rejects

- **`TradeConvErrorCode` gains `REQUEST_PENDING`** (60.2.0), on the SURFACE arm of
  `propose_entry_decision`'s error: one pending request per user and coin, so a second is refused. A
  coin already carrying a pending or live position is refused before anything is queued, as an
  ENGINE-origin `OPEN_POSITION_CONFLICT` — a member that was already published, reaching this surface
  for the first time.

### Additive in the same span

- **The exit names the leg that filled** (60.3.0, `label-trade-outcome-by-pnl`). `TradeOutcomeDTO`
  and the pipeline outcome summary gain `exitRepriceSource`: the reprice that placed the protection
  leg which actually closed the position — `BREAK_EVEN`, `TRAILING`, `TIME_DECAY`,
  `MANUAL_OVERRIDE`, `UPDATED` — or null on every close no protection leg filled and on a leg that
  was never repriced. It is the mechanism behind the verdict above, so read it beside `closeReason`
  before calling a stopped-out trade a failure. The enum is the one `get_position_audit_history`
  already publishes. Four output hashes move; no input schema does.

- **Two tools join the catalog for the request lifecycle** (60.2.0, `queue-manual-entry-for-close`).
  `get_entry_request` (read scope) reads a request that is still pending and is `NOT_FOUND` once it
  has been answered, cancelled or expired — the answer is in the conversation, not there.
  `cancel_entry_request` (`mcp:wager`) withdraws one before its bar is decided. `toolCount` 115 → 117.

- **Three radar reads publish the close decision** (60.1.0, `add-radar-close-decision-state`).
  `get_radar_deployment`, `list_radar_deployments` and `preview_radar_resolution` carry one further
  key on `resolvesNow`: `closeDecision`, non-null whenever an agent is on duty for the pair. It
  carries the deciding `timeframe`, the `nextCloseAt` instant, a `state` of `WAITING` or `DEFERRED`
  (a bar has closed and no sweep has decided it yet), and `last` — the bar, the instant, the outcome
  (`FIRED` / `NOT_QUALIFIED` / `MISSED`), the gate and the closed reading's score against its
  minimum — or null before the pair's first close decision.

  **Read it first on a close-deciding pair.** The sibling `qualified` and `qualificationBlock` fields
  are the per-minute DISPLAY reading there and decide nothing, so an agent ranking them reports
  "qualified — watching for a setup" about a pair whose last three closes were each refused. Neither
  field is removed or reshaped. A `NOT_QUALIFIED` outcome with a NULL gate beside a score at or above
  the minimum is the consumed edge — the close qualified and the baseline was already spent — stated
  by the server so no client compares the two numbers.

## Contract history — v37 → v54

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

- **`scan_agent_coins` returns the ranking, not an explanation of every coin** (54.0.0,
  `fix-mcp-scan-row-altitude`). The scan used to wrap the app's full per-coin qualification verdict
  in every row — two directions with candidate-level construction and a stop-loss policy band, four
  gates each with its own measurement, condition reach reasons, the ATR corridor. For a 78-coin
  catalog that was **82,147 characters, ~1,053 per row**, which is past the tool-result cap of every
  client we know of: the calling model received a file path instead of an answer, so the tool did not
  deliver its result even when the scan succeeded.

  `rows` is gone. Three ranked arrays replace it, and `rank` is **global across all three**, so
  reading them in this order reproduces the server's own sequence:

  ```
  qualified[]   { rank, coinTicker, scorePercent, coinDataStopped }
  rejected[]    { rank, coinTicker, scorePercent, firstFailReason, scoreShortfallPercent }
  unscorable[]  { rank, coinTicker, coinDataStopped }
  ```

  Array membership now carries what the row `kind` discriminator and the `qualifies` flag used to,
  and both are gone with them; `firstFailReason` is non-nullable on a rejected row, because a
  non-qualifying verdict always names the gate that blocked it. Rows also lose `long`, `short`,
  `gates`, `tradeableAtrRange`, `evaluatedAt`, `coinName`, `assetClass` and `category`.

  Two things are new. The agent's `agentId`, `agentName`, `strategyTimeframe` and `minScorePercent`
  move to an `agent` object carried **once** instead of on all 78 rows — `null` when the scan scored
  nothing at all. And `scoreShortfallPercent` is server-computed: how far below the minimum the score
  fell, non-null exactly when the aggregate score is what blocked, so you never subtract a published
  threshold from a published reading yourself.

  `scanStartedAt`, `coinsScanned` and `qualifiedCount` are unchanged, and so is every coin: same
  rows, same order, same ranks, same verdicts, same rate buckets, same evaluator. Only the fields
  moved — about 8.8 KB for the same 78-coin scan.

  **Migration.** Read `qualified` / `rejected` / `unscorable` instead of `rows`, and take the agent's
  thresholds from `agent` rather than from the first row. For a shortlisted coin's full per-direction
  and per-gate detail, call `get_agent_coin_qualification` on up to 12 tickers — it carries every
  dropped field and costs no second scan (the scan is rate-limited to 3 per agent and 10 per user a
  minute; the probe is not).


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

### Additive in the same span

- **Two tools join the catalog for the agent trade flow** (52.1.0, `add-mcp-agent-trade-flow`).
  `scan_agent_coins` evaluates every active coin against one of your agents in a single call and
  returns them server-ranked, on the same use case, buckets and ranking the app's own TRADE-tab scan
  serves. `propose_entry_decision` runs the conversational trade turn headlessly for one (agent,
  coin) and returns its terminal in the stream's own vocabulary: `type: recommendation` carrying the
  PROPOSED `TradingEntryDecisionDTO` row that `get_entry_decision` and `list_pending_approvals`
  already publish, `type: no_trade`, or `type: error` carrying the turn's `TradeConvError` verbatim.
  Nothing narrows and no existing schema hash moves; the 12-ticker `get_agent_coin_qualification`
  stays as the spot-check probe.

  **`idempotencyKey` is REQUIRED on `propose_entry_decision`** — it is the turn's own key, and a
  same-key retry replays the recorded terminal rather than paying for a second inference. That
  includes a post-billing `LLM_FAILURE`, which is returned as a value for precisely that reason.
  Pre-engine faults are typed errors instead: `RATE_LIMITED`, `NOT_FOUND`, `CONFLICT` for a same-key
  call still in flight, and `SERVICE_UNAVAILABLE` when the surface is switched off. Both tools
  refuse with `RATE_LIMITED` carrying `retryAfterSeconds` under the same per-(user, agent) limit the
  app itself enforces, so a scan is never served stale or partial.

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

- **Strict authoring envelopes.** `get_strategy_section_template` and every draft lifecycle tool (`stage_<kind>_draft`, `get_<kind>_draft`, `commit_<kind>_draft`, `discard_<kind>_draft`, `list_<kind>_drafts`) publish one strict server-owned object, `{ request: canonicalPayload }`. In multi-account mode the proxy adds `account` **only** as a sibling of `request`, producing exactly `{ account, request }`; on a call it strips only `account` and forwards the unchanged `{ request }`. It never descends into, flattens, or reconstructs the nested request.
- **`create_strategy` is retired.** Direct strategy creation no longer exists. Author strategies through the strategy draft lifecycle below, and bind an agent to one through its draft's `STRATEGY_BINDING` axis. There is no alias, shim, or flat-payload fallback.
- **Rediscover after deployment.** Publishing the package does **not** refresh a running proxy's cached capability snapshot. After the server cutover, restart/reconnect the proxy process and re-run `tools/list`, `prompts/list`, and `resources/list`.

> Earlier majors: **v1.x** single/multi-account stdio proxy; **v2.0.0** moved the default `BATTLEGRID_API_URL` to the `/mcp` suffix; **v3.0.0** the strategy-authoring major; **v4.0.0** made `conditions` and `conditionVerdicts` required on the apply post-state; **v5.0.0** fused the conditions/verdicts split (section above). **v6.0.0** through **v11.0.0** were never published as separate package versions — they are absorbed by the v11 cutover at the top. See [Rediscovery & versioning](#rediscovery--versioning).

## Quick Start

### Remote server, OAuth — start here

```
https://mcp.battlegrid.trade/mcp
```

Give that URL to your MCP client over its streamable-http (remote) transport and authorize: the
client registers itself by Dynamic Client Registration, BattleGrid's consent page opens in your
browser, and you sign in and click **Authorize**. No npm install, no API key. The grant is listed —
and revocable — under **Profile → MCP → OAuth Sessions**.

### API key and the stdio proxy — the fallback

Reach for a key when your client has no remote transport at all, when your agent runs headless or in
CI and cannot open a browser to consent, or when one process drives several BattleGrid accounts. It
is fully supported for each of those, and nothing about it is deprecated.

**Single account (stdio transport):**

```bash
BATTLEGRID_API_KEY=bg_live_xxx npx @battlegrid/mcp-server
```

**Multiple accounts (stdio transport):**

```bash
BATTLEGRID_API_KEYS=bg_live_alice_key,bg_live_bob_key npx @battlegrid/mcp-server
```

When multiple keys are provided, the server discovers each account's identity and injects a required `account` parameter into every tool so the AI agent can choose which account to act as. OAuth has no equivalent — one grant authorizes one account.

## Configuration

### Claude Desktop

**OAuth (no key):** Settings → **Connectors** → **Add custom connector**. Paste
`https://mcp.battlegrid.trade/mcp`, save, and authorize on the consent page Claude opens.

**API key (fallback) — single account:**

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

**API key (fallback) — multiple accounts:**

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

**OAuth (no key):**

```bash
claude mcp add --transport http battlegrid https://mcp.battlegrid.trade/mcp
```

Then start `claude`, run `/mcp`, select **battlegrid** and choose **Authenticate** — the consent page
opens in your browser and the entry reads connected once you authorize.

**API key (fallback):**

```bash
# Single account
claude mcp add battlegrid -e BATTLEGRID_API_KEY=bg_live_xxx -- npx @battlegrid/mcp-server

# Multiple accounts
claude mcp add battlegrid -e BATTLEGRID_API_KEYS=bg_live_alice_key,bg_live_bob_key -- npx @battlegrid/mcp-server
```

### Cursor

**OAuth (no key):** Settings → **MCP** → **Add new global MCP server** opens `~/.cursor/mcp.json`.

```json
{
  "mcpServers": {
    "battlegrid": {
      "url": "https://mcp.battlegrid.trade/mcp"
    }
  }
}
```

Back in Settings → MCP, click **Needs login** on `battlegrid` and authorize on BattleGrid's consent
page; the entry turns green once its tools load.

**API key (fallback):** the same file, with the stdio proxy in place of the remote entry.

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

Authentication is a property of the **path**, not of the client — every client above reaches
BattleGrid either way, so pick the row that matches your runtime rather than your client:

| | Remote + OAuth | API key |
|---|---|---|
| **Transport** | streamable-http, direct to `mcp.battlegrid.trade` | stdio proxy (`@battlegrid/mcp-server`), or the same URL with a Bearer header |
| **Auth** | OAuth 2.1 with Dynamic Client Registration | API key (`bg_live_*`) as a Bearer token |
| **Setup** | paste the URL, authorize in the browser | npm package + env vars |
| **Needs a browser** | yes, once, to consent | no — works headless and in CI |
| **Multi-account** | one grant per account | `BATTLEGRID_API_KEYS`, several accounts through one proxy |

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
  "name": "commit_strategy_draft",
  "inputSchema": {
    "type": "object",
    "properties": {
      "account": {
        "type": "string",
        "enum": ["alice", "bob"],
        "description": "Which BattleGrid account to use for this action"
      },
      "request": {
        "type": "object",
        "properties": {
          "strategyId": { "type": "string", "format": "uuid" },
          "draftVersion": { "type": "integer", "minimum": 1 },
          "expectedRevision": { "anyOf": [{ "type": "integer", "minimum": 1 }, { "type": "null" }] }
        },
        "required": ["strategyId", "draftVersion", "expectedRevision"],
        "additionalProperties": false
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

## Strategy and agent authoring (stage → read → commit)

Strategies and intelligence agents change only through their drafts, with one tool family per kind (`<kind>` is `strategy` or `agent`): `stage_<kind>_draft`, `get_<kind>_draft`, `commit_<kind>_draft`, `discard_<kind>_draft` and `list_<kind>_drafts`. **A stage writes the player's unsaved draft and commits nothing; `commit_<kind>_draft` is the only write to the entity itself**, and it publishes exactly the draft the caller read.

1. **Choose the entity.** `list_strategies` (add `includeInactive:true` when repairing an archived strategy) and `get_strategy`, or `list_intelligence_agents` and `get_intelligence_agent`. `fork_strategy({ strategyId, sourceRevision })` copies a visible revision into a new create draft and returns its `strategyId` and `draftVersion`; it creates nothing.
2. **Discover the report vocabulary live.** Walk `list_strategy_categories` → `list_strategy_vocabulary` → `get_metric_construction_hints` → `get_strategy_column_contract`, and use `get_strategy_section_template` / `preview_strategy_report`. Do not guess metric, transform, parameter, template, or enabled-timeframe facts — they are server-discovered.
3. **Read the draft.** `get_<kind>_draft({ request: { <id> } })` returns the draft (or `null`), its `draftVersion` (0 when none is held), the live `committedRevision` (null for an entity not created yet), a per-axis `diff` against live, `diagnostics` and `impact`.
4. **Stage the change.** `stage_<kind>_draft({ request: { <id>?, draftVersion, axes } })` names the version you read. Each axis is whole, except a strategy's `SIGNAL_RULES`, whose rows replace the drafted rows for the same signals and keep every other one. Omit the id to open a new create draft; the response carries the minted id. A stage that has written never refuses: the composed draft's errors and warnings come back as `diagnostics`. It is refused only when the version is one the draft never reached (`DRAFT_VERSION_MOVED`) or when the player's own form changed an axis you are staging after that version (`DRAFT_AXIS_CONTESTED`, naming `contestedAxes`).
5. **Review with the player, then commit.** Read the draft again, show the player its diff and impact, and on their explicit word call `commit_<kind>_draft({ request: { <id>, draftVersion, expectedRevision } })` with exactly the two numbers that read returned — `expectedRevision: null` creates the entity at revision 1. A draft that moved is refused `DRAFT_VERSION_MOVED`, a moved revision `CONFLICT`, and an invalid draft with the same code its diagnostics carried; nothing is written. Each refusal's `details.nextAct` says what to do next (`get_draft` or `stage`). The commit is idempotent on `{ id, draftVersion }`: a retried commit replays its outcome. Changed strategy configuration propagates to every bound agent immediately; committing a draft of an archived strategy restores it.

`discard_<kind>_draft({ request: { <id>, draftVersion } })` removes the draft at the version you read and never one that moved since. `preview_strategy_report({ coinSelection, source: { kind: 'DRAFT', strategyId, draftVersion } })` previews a draft as a commit would compose it. In multi-account mode the lifecycle tools use the `{ account, request }` sibling envelope; `preview_strategy_report` keeps its own flat input and takes `account` beside `coinSelection` and `source`.

**Strategy-bound agents.** An agent binds to a strategy through its draft's `STRATEGY_BINDING` axis — on a create draft, or on an edit draft as a rebind that commits through the same `commit_agent_draft` (discover `strategyId` via `list_strategies`). The plan tools, `update_strategy_signal_rule` and the direct agent writers are retired, and so is `create_strategy`.

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
| `battlegrid-strategy-authoring` | Build a strategy from a plain-English idea: gather evidence, lock the spec, stage it into the strategy's draft, review the diff, diagnostics and impact, commit only on confirmation. Also fork, tune, restore, archive, preview |
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
