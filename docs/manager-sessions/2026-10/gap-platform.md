# Gap analysis: battlegrid-manager logic vs BattleGrid 111-123 (platform semantics)

Written 2026-10-20T10:53Z. Read-only: no BattleGrid call, no Docker, no repo edit. Strategy and condition
authoring and officers are out of scope here (other reviewers have them).

**Sources read**
- `C:/tmp-bg-gap/README.md`, v111 to v123, plus the older sections the answers depend on (v26, v30, v52, v71, v77,
  v81, v99, v102.1).
- The vendor skills in `C:/tmp-bg-gap/repo/skills/`, word-diffed against the vendored 110.10.0 pack in
  `battlegrid-manager/.agents/skills/battlegrid/skills/`.
- battlegrid-manager `main` at `efa7589`: `manager/`, `hermes/`, `docs/status/`, and the fixtures under
  `tests/fixtures/`.
- Tool schemas visible in this session's BattleGrid MCP catalog. I loaded the schemas only and called no tool.

**Bottom line**
- Nothing is broken at 122.0.0 today. The 111-119 wire changes are handled, and the manager does not call the
  v120/v122 tools.
- The real gaps are in meaning, not wire shape:
  - expired entries are invisible to the manager;
  - the pool sums notional where the platform caps margin;
  - the Commander is taught stale rules (daily-trades counting, the close-decision paging, scores).

---

## 1. The entry-order question (ON_CANDLE_CLOSE "at market" vs a resting 15-min limit)

**What the vendor documents**
- **The entry is "at market".** `battlegrid-strategy-examples/SKILL.md` ("Entry") says `ON_CANDLE_CLOSE` takes the
  entry at the qualifying close, at market. It also says "the fill lands at the next tick, and the platform refuses it
  if the market has already run past its own drift budget from that close." Nothing in v111-v123 revises this. No
  newer statement says that `ON_CANDLE_CLOSE` rests as a limit.
- **No per-agent or per-strategy control exists.**
  - v26.0.0 removed `tradingConfig.signalTimeoutMinutes` and `tradingConfig.maxEntryDeviationAtrMultiple` from the
    agent, with "no replacement key on any surface" (README ~3369-3374, 3430-3443, 3878).
  - `ON_CANDLE_CLOSE` takes no `levelOffsetAtrMultiple` or `validForBars`. Sending either is refused as an
    unrecognised key.
  - `validForBars` (1-24 strategy bars) exists only for `STOP_THROUGH_LEVEL` and `ON_RETEST`.
- **Both guards are platform constants.** Each is a `platform_config` value, readable through
  `get_trading_config_catalog`:
  - `defaultMaxEntryDeviationAtrMultiple` is the drift budget. It is read at evaluation time.
  - `defaultTtlMinutes` is how long an entry may stay unfilled. It is "snapshotted onto the position at creation, so
    an edit can never cancel an order already resting on the book" (README 3878).
  - v26 also notes that a "hardcoded 15-minute resting window" became this value.
  - The manager's own fixtures record `defaultTtlMinutes: 15` and `defaultMaxEntryDeviationAtrMultiple: 1.5`
    (`tests/fixtures/2026-09-14`, `2026-10-02-surface-77.1.0`, `2026-10-02-surface-80.0.0`
    `get_trading_config_catalog.json`).
  - So the 15-minute TTL you see live is the documented platform TTL, and it cannot be changed by configuration.
- **The agent dial nearest to it is `maxSlippageBps`** (at most 300, v77: "the entry slippage ceiling"). It is
  agent-owned and the manager copies it through unchanged (`CARRIED_KEYS`, `manager/actions/agent_config.py:83`).
  - The README does not say whether the limit price of an ON_CANDLE_CLOSE order is close ± `maxSlippageBps`.
  - That is the one lever that might widen the limit. It is **unverified**. Check it against a live entry order with
    `list_agent_open_orders` (price vs decided close) before anyone touches it.
- **The expiry reason is served, and the manager does not read it.** The 119.0.0 output schema of `get_signal_log`
  `log.pipeline.execution` has:
  - `expiryReason` ∈ {`TIME`, `PRICE_DEVIATION`, `PRICE_BREACH_WORKING`, `SETUP_DECAY`, `INDICATOR_FLIP`,
    `ENTRY_ORDER_CANCELLED`, `ENTRY_ORDER_REJECTED`, `SESSION_ENDED`, `BAR_VALIDITY_ELAPSED`,
    `STRUCTURAL_INVALIDATION`};
  - and a `status` that includes `EXPIRED`.
  - `list_signal_logs` takes `filter.expiryReason` (README v71).
- **The gap.** The docs say "market" and live behaviour is a resting limit with a TTL. That is a vendor-doc
  discrepancy to report upstream, with an example decision id and the order's `orderType`/`timeInForce` from
  `get_open_orders`.

## 2. Prioritized findings

### BLOCKING (none today; one is scheduled)

**B1. v123 will block writes when it deploys. Expected, not a defect.**
- What v123 changes:
  - it renames 18 header stems;
  - it refuses the old names in condition columns and `{…}` Market Read markers;
  - it adds 7 metric keys;
  - it adds the required `marketReadChars` to `list_strategy_vocabulary.budgets`.
- `stage_strategy_draft` is a manager write tool (`manager/actions/strategy_send.py`), so the watch will classify this
  as unsafe and hold writes until `manager contract ack 123.x`.
- Outside authoring, the manager has no dependence on header text:
  - `manager/panel/columns.py` authors by metric key;
  - triage reads condition keys (`failedKeys`), not headers.
- The ack review only needs to confirm that OMEGA / the strategist (other reviewers) are ready.
- Note: `docs/status/` has no review record for 121.x or 122.0.0. The newest is the 120.3.0 entry in
  `2026-10-18-verification-and-halt-watch.md`. If those were acked, the record is missing.

### HIGH: stale logic that misleads on the live fleet

**H1. Expired entries are invisible.** This is the live entry-order symptom.
- `manager/inventory/entry_failures.py:18`: a streak counts only `FAILED`. `EXPIRED` and `CANCELLED` "neither count
  nor end it".
- `manager/inventory/agent_status.py:29,70`: the entry outcome is `OUTCOMES = ("EXECUTED", "FAILED")`, so the status
  line never reports an expired entry.
- `manager/inventory/normalize.py:196` (`normalize_execution`) reads only `failureReason` / `executionMessage`, never
  `expiryReason`.
- The effect: an agent whose ON_CANDLE_CLOSE limits all time out (`TIME`) or are cancelled for drift
  (`PRICE_DEVIATION` / `PRICE_BREACH_WORKING`) reads "running" with no alert. That is the same blindness the 10-16
  BELOW_EXCHANGE_MINIMUM incident had.
- The fix, as detection only, in the same shape as the entry-fail watch:
  - store `expiryReason`;
  - show "last entry EXPIRED TIME" in the agent status;
  - add an `AGENT_ENTRIES_EXPIRING` streak, or count EXPIRED in a separate streak.

**H2. The shared pool subtracts notional while the platform caps margin.** Dormant with one deployed agent; wrong
with two or more.
- `manager/risk/pool.py:93-116`: `pool_shares` subtracts every other open position's `size_usd`, which is the
  platform's `currentNotionalUsd` (docstring line 96-97), from `max_gross_exposure_usd`.
- But the platform says otherwise:
  - v77: "Max exposure caps margin open at once";
  - your own 10-19 measurement: "$15.53 notional, its $7.77 margin left $5.23 of headroom" at a $13 cap.
- At policy v7's 3x leverage, a second agent's share is understated by about 3x the other positions' margin. The pool
  would starve or halt it (pool HALT) when the platform would let it trade.
- Related: `fits` (`cap_usd >= min_notional_usd`, `pool.py` `PoolShare`) compares a margin cap with a notional
  minimum. That is conservative at leverage above 1 and is not the real gate.
- The real gate is "preset% x free headroom / hard stop >= $10". The platform already computes it:
  - the agent draft's `impact.smallestOrderUsd` against `impact.orderFloorUsd`, with `feasible`
    (battlegrid-agent-management step 4);
  - `get_agent_budget.effectiveNotionalUsd`.
- `manager/actions/pipeline.py:926` stores `impact` but nothing reads `feasible`.
- Recommendation:
  - decide with the user whether the gross line means margin or notional;
  - gate SYNC_LIMITS on `impact.feasible`.

**H3. The Commander is taught that the daily-trade cap counts attempts.** Wrong since 77.1.0.
- `hermes/skills/battlegrid-manager/SKILL.md:136`: "`maxDailyTrades` counts attempts, not fills. EXPIRED and FAILED
  entry decisions count".
- `manager/mcp/native.py:101` (the `manager_radar_decisions` description): "DAILY_TRADE_LIMIT_REACHED, which counts
  attempts, not fills".
- README v77: `tradesToday` counts "entries filled since 00:00 UTC plus entries still waiting to fill. Refused and
  expired entries no longer count." Your memory file says the same.
- With resting limits, a waiting entry counts until it expires, then stops counting. Rewrite both lines.

**H4. The Commander's vendored pack (110.10.0) breaks on its one paged radar read.**
- `hermes/install_commander.py:92` points the Commander at `.agents/skills/battlegrid/skills`.
- The radar-deployment skill there (`SKILL.md:355-356`) says to page `get_radar_close_decisions` with `before` /
  `nextBefore`.
- Since v114 `before` is refused as an unrecognised key, and the answer carries `nextCursor`. The Commander can call
  this tool (`manager/proxy/policy.py` allowlist), so following its skill fails.
- Upstream's refresh also brings:
  - the `get_radar_market_hours` session guidance and `ruleCloseCoverage`;
  - the arena `lockAt` "closed even though PENDING" rule;
  - flat draft examples (v111);
  - the new `battlegrid-officers` skill.
- Refresh the pack to the current export, as the last one was for 31.2.108.

### STALE: wrong text or dead code, low risk

- **S1. The gate-block total prints "None" since v113.**
  - `manager/inventory/snapshot.py:381` stores `payload.get("total")`, and `manager/inventory/decisions.py:100,176`
    renders "Gate blocks (None total on the platform)".
  - v113 replaced `total` with `nextCursor`. `manager/platform/reads.py:59` already notes the field is not served.
  - Drop the total, or say "first page of N".
- **S2. Score fields left from 108.**
  - `hermes/plugin/battlegrid-manager/desktop/plugin.js:549` renders "score / min" in the Radar table.
  - `hermes/skills/battlegrid-manager/SKILL.md:272` lists "(bar, outcome, gate, score / min)".
  - `manager/mcp/native.py:99-100` says "its score against the minimum".
  - `manager/inventory/normalize.py:260-261`, `decisions.py:75-76,132-135` and `report.py:37` still carry it, and
    `models.py:181-182` keeps the columns.
  - All of them are always null since 108.0.0. The same skill says so at line 126-128, so the two texts contradict
    each other.
- **S3. The close outcomes are incomplete.**
  - `manager/mcp/native.py:99` says "outcome (FIRED or NOT_QUALIFIED)".
  - The radar skill documents `FIRED`, `NOT_QUALIFIED`, `CLAIMED`, `MISSED`, and `fireDisposition` (e.g.
    `EDGE_PRESERVED_ENTRIES_PAUSED`: "FIRED" with nothing traded).
  - The manager neither stores nor shows `fireDisposition` (`normalize.py:256-261`).
- **S4. Removed tools are still on the proxy allowlist.**
  - `manager/proxy/policy.py:22,28,29,36` lists `get_agent_game_history`, `get_mcp_reasoning_journal`,
    `get_public_agent_game_history` and `get_user_agent_game_history`, all removed at v99.
  - They are harmless, because the "exists in the latest watched surface" condition withholds them, but the "89
    names" header comment is wrong.
  - The comment at `policy.py:47` still describes `get_radar_close_decisions` as taking `before` (v114: `cursor`).
- **S5. "One position per agent in practice" is no longer what you observe.**
  - `hermes/skills/battlegrid-manager/SKILL.md:142` says it.
  - 10-19 shows a second concurrent entry attempted (HIMS while USAR was open), and policy v7 at 3x is built so that
    one succeeds.
  - Restate it as "margin headroom decides; one at a time below ~$20 at 2x" or drop it.
- **S6. The documented `RESULT_TOO_LARGE` code is not matched.**
  - `manager/platform/cap.py:48-57` matches only the measured wording, the `RESULT_OVER_CAP` tag or
    `nextAct: narrow`. It does not match the documented code `RESULT_TOO_LARGE` with `details.limit: "result_chars"`
    (v111.1).
  - A no-input read refused with the documented envelope and no `nextAct` would be classed as a plain TOOL_ERROR.
  - Add the code to `is_over_cap`.
- **S7. Reads ignore `details.retryable`.**
  - The write path uses v118.1 correctly (`manager/actions/pipeline.py:689-713`: SERVICE_UNAVAILABLE and
    INTERNAL_ERROR are UNKNOWN).
  - Read retries still key only on rate limits (`manager/platform/client.py:228-240`).
  - `retryable: true` on a SERVICE_UNAVAILABLE read is a free safe retry. `correlationId` is not logged, though the
    README asks callers to quote it.

### Checked and fine (no action)

- **v111 flat draft tools.** Every stage, commit and discard call is flat. `request` stays only on the two previews,
  as documented (`arena_describe.py:348`, `radar_describe.py:277`).
- **v112 input names.** `get_regime_snapshot` sends `coinTicker` (`triage/inputs.py:121`). The manager calls no
  `ticker` or `symbol` input, and no `list_session_agent_positions`.
- **v113/v114 cursors.** `list_trade_outcomes` pages by `nextCursor` (`allocation/performance.py:85`).
  `list_gate_blocks` and `list_entry_decisions` read the first page only, with no `page`.
- **v116 JSON-RPC codes.** -31401/-31403/-31405/-31429 and -32602 are mapped (`platform/client.py:71-201`).
- **v118 VALIDATION_ERROR envelope.** It is in `DRAFT_REFUSAL_CODES`, and nothing parses the old sentence.
- **v119 row trims.** `list_entry_decisions` and `list_gate_blocks` take the agent id from the loop, not from the row.
  `list_trade_outcomes` reads `closedAt`, not `createdAt`.
- **Halts and resume.** The manager follows `haltResumeEligibility` exactly (`agent_config.py:674-720`), as the
  agent-management step 5 requires.
- **Sizing semantics.** "Preset = % of headroom at risk" (v30) matches `allocation/rank.py:15` and
  `agent_config.py:19`.
- **v120 onboarding and v122 officer tools.** Neither is called.

### OPPORTUNITY: platform reads that replace manager workarounds

- **O1. `list_agent_open_orders` (v102.1, read).** It lists each agent's live entry orders (PENDING, ACKED or WORKING)
  with `signalLogId`. The manager watches the resting ON_CANDLE_CLOSE limit through `get_open_orders` only.
  - It shows a resting entry, its price against the decided close, and its age against `defaultTtlMinutes`.
  - It is not on the proxy allowlist.
- **O2. `get_agent_entry_discipline` (read; in this session's live catalog, absent from the README, the skills and
  the 119.0.0 fixture).** Over a window of up to 90 days it serves the confirmation tax (signed slippage from the
  decision anchor to the fill), fast stop-outs, adverse-before-favourable excursions and holds.
  - It is the platform's own measure of what waiting for the close costs, and the right evidence for the
    entry-order question. It complements the reversed-signal study, which was done by hand.
- **O3. Expiry analytics without new code paths.**
  - `list_signal_logs` with `filter.expiryReason`, or `get_signal_log` `execution.expiryReason`, per agent, feeding H1.
  - `get_trading_config_catalog.defaultTtlMinutes` and `defaultMaxEntryDeviationAtrMultiple` are worth recording in
    each snapshot, so a platform TTL change is seen. It is snapshotted per position, so it changes silently.
- **O4. Platform feasibility in place of the manager's $10 arithmetic.** Use the agent draft's
  `impact.smallestOrderUsd` / `orderFloorUsd` / `feasible`, and `get_agent_budget.effectiveNotionalUsd`, in SYNC_LIMITS
  and the pool (see H2).
- **O5. Radar hours.** `preview_radar_resolution` `ruleCloseCoverage.decidableCloses` and `get_radar_market_hours`.
  The 114.2.0 review already noted them as "not needed now". They matter only if the manager ever stages hours rules.
- **O6. Proxy coverage.** None of these reads is exposed to the Commander:
  - `list_agent_trades` and `get_agents_portfolio_pnl` (v102.1);
  - `list_my_market_grid_entries` and `get_my_market_grid_entry` (v99, the replacements for the removed
    game-history tools);
  - `get_trade_conversation` and `get_entry_request`.
  - Add any of them after review, as the allowlist's rule requires.
