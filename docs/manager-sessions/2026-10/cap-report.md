# BattleGrid 150k response cap: every platform read the manager makes

Branch `fix/response-cap` in worktree `C:/tmp-bgm-cap`, cut from main dd07c89. Nothing is merged, pushed or deployed, and BattleGrid was not called.

## What the cap is (measured 2026-10-19)

When a result is too big, BattleGrid returns an `isError` result instead: kind TOOL_ERROR, no error code, and the message "The result is N characters, over the 150000-character cap; ask for less". The tool has already run when this happens; only its answer is thrown away.

The live descriptions at contract 120.3.0 show one more form. `list_gate_blocks` says "A page over the configured result cap is refused with `nextAct: narrow`". `preview_strategy_report` uses the same `nextAct` for both its cap refusal and its deadline refusal.

## How the fix works (new file `manager/platform/cap.py`)

- **Tagging:** `parse_call_result` adds the code `RESULT_OVER_CAP` to the measured refusal when the platform sent no code of its own. Every printer that writes `e.code or e.kind` now names the refusal, including the scan and the MCP gateway.
- **Recognition:** `is_over_cap(e)` is true for a TOOL_ERROR or RPC error that has the tag, the measured words, or `details.nextAct == "narrow"`. A transport, auth, HTTP or rate-limit error never counts.
- **Narrowing paged reads:** `call_narrowing(client, tool, args, key="limit", floor)` halves the page size after each over-cap refusal. If the read is still over the cap at the floor, it raises, so the read stays unread rather than empty.
- **Writes:** `pipeline._send_status` now treats an over-cap answer to a write as UNKNOWN, never FAILED, because the write may have landed. The draft writes were already UNKNOWN, since they had no code.
- **Snapshot records:** a failed snapshot read now stores `overCap {resultChars, capChars}` alongside the usual UNDETERMINED status.

## Every read

Sizes come from the captured fixtures in `tests/fixtures/` and from read-only psql on the live database (snapshot 9675, 2026-10-19).

| Tool | Where it is read | How it grows / measured size | Bounded under 150k? | Fix |
|---|---|---|---|---|
| `list_intelligence_agents {}` (ACTIVE only) | snapshot core read every 5 min; scan cycle; `strategy_describe` exposure check; `roster.locate_agent` / `roster_view`; lifecycle propose/describe | Each row carries the agent's realized PnL curve, which gets longer with every closed trade. The number of rows is capped by the slot limit (24 at Commander III, and it rises with level). Measured 49k for 13 agents (~3.8k each) on 09-27. ACTIVE+ARCHIVED was 197k on 10-19, for 16+ agents (up to ~12k each). | **No.** The tool takes no page or field argument. | It already failed closed everywhere: the snapshot read is UNDETERMINED and stores no agent rows, the scan run is UNDETERMINED, and describe/propose refuse. Now it also records `overCap`, and the scan's error names `RESULT_OVER_CAP`. No narrowing is possible. **Concern 1.** |
| `list_intelligence_agents {statuses:[ARCHIVED]}` and the per-agent fallback | `roster.py`, `lifecycle_propose.roster_view` | Every agent ever archived | No | Already fixed on main (per-agent fallback). Left as is. |
| `get_agents_hub {}` | `lifecycle_describe._exposure` (ARCHIVE/ACTIVATE/REBIND/REMODEL) | Every owned agent including ARCHIVED, plus platform agents with their footprint. It grows like the 197k combined roster. | **No.** It takes no argument, and no narrower read gives its server-computed counts. | It already refused. Now it refuses **by name** ("get_agents_hub answered N characters, over the platform's 150000-character cap: unread, not empty"). Test added. **Concern 2.** |
| `list_gate_blocks {agentId, limit 20}` | snapshot, one page per ACTIVE agent; `manager fixtures` | About 3.7k per row because `reasonDetail` is kept whole: 9 rows were 34k on 09-18, so a page of 20 is ~73k. The maximum limit of 100 would be ~370k. | Paged, but one page can outgrow the cap | **Fixed:** `call_narrowing` (20, 10, 5, then floor 2). The read records the `limit` actually served. Over the cap at the floor gives UNDETERMINED plus `overCap`. Two tests. |
| `list_trade_outcomes {agentId, limit 50, cursor}` | `allocation.performance.read_outcomes`, used by the allocator and review | About 1,050 per row (10-01), so a page of 50 is ~52k. The number of pages grows with trades. | Paged; there is room now, but rows could grow | **Fixed:** an over-cap page is narrowed (floor 5), and later pages keep the smaller size. The guard is now 2,000 rows rather than 40 pages. Over the cap at the floor raises, so the agent's record is unread rather than short. Two tests. |
| `list_entry_decisions {agentId, ENTER, limit 10}` | snapshot entry-fail watch | 10 small rows | Yes (fixed page of 10) | Over the cap gives UNDETERMINED plus `overCap`. Deliberately not narrowed, because a shorter page would shorten the streak window. |
| `get_signal_log {agentId, logId}` | snapshot (at most one per agent); triage dossier | One decision's log, 42–45k measured (09-18). It scales with the strategy's size, not the account's. | Yes per log (~3x room) | Over the cap gives UNDETERMINED plus `overCap`, and the log is marked UNREADABLE after 3 attempts. The tool has no narrowing argument. |
| `list_strategies {}` | snapshot; `strategy_describe` quota/name check; Strategy tab `/api/strategy/strategies` | About 640 per row (27 rows were 19k on 09-27); there are 30 rows now (12 SYSTEM, 18 PRIVATE). Private rows are capped by the strategy quota (limit 25). `includeInactive` is never passed. | Yes (quota-bound, ~4x room) | Already failed closed in the snapshot and describe. **Fixed** in the Strategy tab route: an over-cap answer, or an answer with no `strategies` list, used to show `[]`. It now refuses. Test added. |
| `list_radar_deployments {}` | snapshot; lifecycle/strategy/radar describe | About 1.7k per coin (19 coins were 40k on 09-27); 11 coins now | Yes (`summary.coinCap` 20) | Already fails closed. Left as is. |
| `list_user_active_positions {}` | snapshot; CLOSE propose/describe/verify; `deploy check` | Open positions only (0 on 10-19), small rows | Yes | Already fails closed. Left as is. |
| `list_deployment_policies {}` / `get_deployment_policy` (at most 5) | snapshot (Arena) | 304 characters; the account has no deployment | Yes | Left as is. |
| `get_agent_budget {agentId}` | snapshot (at most 10); triage; describe; verify | One agent's meters | Yes | Left as is. |
| `get_strategy {strategyId}` | snapshot (at most 5 new revisions); strategy describe; authoring | One strategy, 15–22k measured; at most 6.7k of conditions+sections is stored | Yes in practice. Authoring would allow staged axes up to 256 KB. | Fails closed. Left as is. |
| `get_strategy_draft`, `list_strategy_drafts {cursor}` | strategy describe/send/verify; authoring/current | One draft; the list is paged by cursor (loop guard already present) | Yes | Left as is. |
| `get_intelligence_agent {agentId}` | lifecycle propose/describe/verify; `agent_config`; roster fallback | One agent, 2.7–5.3k (09-20). Its PnL curve grows slowly with trades. | Yes | Left as is. |
| `get_agent_draft`, `get_radar_deployment(_draft)`, `get_deployment_policy_draft`, `preview_radar_resolution`, `preview_deployment_resolution` | describe/propose/send/verify | One coin or one preset | Yes | Left as is. |
| `get_agent_coin_qualification {coinTickers:[1]}` | triage; radar describe | One coin (the maximum is 12) | Yes | Left as is. |
| `get_regime_snapshot`, `get_position_audit_history` | triage; TIGHTEN/CLOSE describe and verify | One coin, or one position's events | Yes | Left as is. |
| `scan_agent_coins {agentId}` | scan cycle | The coin universe: 78 × ~130 characters, ~12k (stored at most 7.3k) | Yes (sized by the platform's coin list) | Left as is. |
| `get_coin_metadata {}` | `tape/symbols`; `radar_propose`; `measure` | The coin universe: 78 coins, 21–38k | Yes (sized by the platform; it would take roughly 375+ coins to overflow) | Left as is. An unread answer keeps the old symbol map, and radar propose refuses. |
| `get_trading_config_catalog`, `list_approved_models`, `get_account_state` | measure/auth; lifecycle; snapshot | Platform catalogs and account fields, 1.7k for the account | Yes | Left as is. |
| `preview_strategy_report` | panel (ranked limit 50, concise); Strategy tab preview | Panel answer is 17.5k on 10-19. The tool enforces its own budget (`budgetUsage.resultChars`, `nextAct: narrow`). | Yes (the panel's request is fixed) | **Fixed:** the panel no longer retries an over-cap or deadline refusal. It records the failure and stores no data. Test added. |
| `get_strategy_signal_definition` | `authoring/definitions.refresh` | — | — | Retired 10-11 and unreachable. |
| Commander proxy calls (`mcp/gateway.py`) | the model builds them | — | Not a manager consumer | The refusal reaches the model with code `RESULT_OVER_CAP`, so it can ask for less. |
| `manager fixtures record` / `manager measure` | capture commands | — | Not consumers | Left as is. |
| Write answers (stage/commit drafts, close, pause and so on) | pipeline / `*_send` | `STAGE_STRATEGY` answered 64k for a 14k-parameter strategy; `COMMIT_STRATEGY` 16k; `SYNC_LIMITS` 8.8k; the rest under 1.4k | A stage answer grows with strategy size (~4.5x) | **Fixed:** an over-cap answer is UNKNOWN, never FAILED. Test added. **Concern 3.** |

## Commits on fix/response-cap

1. 38d5136 – Recognise the over-cap refusal: the `RESULT_OVER_CAP` tag, `is_over_cap`, `call_narrowing`
2. 1cfc7c3 – A write answered over the cap is UNKNOWN, never FAILED
3. 96c6350 – Snapshot `overCap` recording, gate-block narrowing, recognition of `nextAct: narrow`
4. 3e026f2 – Narrowing for `list_trade_outcomes`
5. af2705b – Panel does not retry an over-cap or deadline refusal
6. 1cedaaf – `get_agents_hub` over the cap refuses by name
7. 04539dd – Strategy tab `list_strategies` refuses when the answer is over the cap or unreadable

## Concerns

1. **The ACTIVE agent list is the core snapshot read, and nothing can narrow it.** Each row embeds a PnL curve that keeps growing. With the slot limit at 24 and per-agent rows of ~8–12k, a full fleet would go over 150k. When that happens, every snapshot leaves the roster UNDETERMINED: the system fails closed, but the fleet views go dark, and so do the halt and status watches, the scan and the exposure checks. The only escape would be per-agent `get_intelligence_agent` reads of ids the manager already knows, and those cannot prove the roster is complete. That needs a design decision, or a page/field argument from BattleGrid. Worth asking the vendor for one.
2. **`get_agents_hub` includes ARCHIVED agents**, so it grows like the combined roster that broke on 10-19. When it goes over the cap, every ARCHIVE, ACTIVATE, REBIND and REMODEL refuses. That is safe, but it blocks those actions, and there is no narrower source for its counts.
3. **The `stage_strategy_draft` answer is ~4.5x the strategy's size.** A strategy of roughly 33k would produce an answer over the cap. Such a write is now UNKNOWN and left to verify, but every stage of a strategy that size would need a manual settle.
4. **The refusal's words were measured only on `list_intelligence_agents`.** Whether `list_gate_blocks`' "nextAct: narrow" refusal carries a code or those same words is unmeasured. Both forms are recognised.
5. **Not measured live:** the current ACTIVE list size, the hub size, and per-row sizes at 120.x. No platform call was made; the estimates come from fixtures (09-14 to 10-15) and stored rows.

## Addendum: result sizes and an early warning for the reads that cannot page

This addresses concerns 1 and 2.

### What was added

- **Every answer is measured.** `PlatformClient.call` measures the size of every result: the characters of the text content the server serialized, or the structured content as JSON when no text came. The figure is kept in a context variable for the calling task. `cap.measured_call(client, tool, args)` returns the answer together with its size. For a client that does not measure (a test double, or a call made from the gateway's worker task), it falls back to the answer's JSON length. Any answer at 60% of the cap or more is logged as a warning.
- **The snapshot records sizes.** Every OK snapshot read stores `resultChars`: the core reads, the gate blocks, budgets, entry decisions, signal logs, strategies and the Arena reads. An over-cap refusal keeps `overCap.resultChars`, which is the size the refusal itself names.
- **The hub's size is recorded where it is read.** Lifecycle describe stores the `get_agents_hub` size in its notes as `life.hubResultChars`, including the size an over-cap refusal names, and passes it through the watch.
- **New `READ_NEARING_CAP` watch** (`manager/inventory/cap_watch.py`), covering `list_intelligence_agents` and `get_agents_hub`:
  - **When it files:** one alert per tool when the read crosses 60% of the cap (90,000 characters), and one more when it crosses 80%. The 80% alert supersedes the open 60% one, so each tool has at most one open alert.
  - **No repeats:** nothing new is filed while the read stays at or above the threshold already alerted.
  - **Auto-resolve:** the open alert resolves itself (ledgered `read_size.resolved`, "back under 50% of the cap") once the read drops under 50%. Between 50% and 60% nothing is filed or resolved, so a read hovering near 60% does not alert every snapshot.
  - **Edge cases:** an answer refused over the cap counts as the size it names, so it lands on the 80% threshold. A read that could not be measured files nothing and resolves nothing.
  - **Alert detail:** the tool, `resultChars`, `capChars`, `percentOfCap`, the threshold, `activeAgents` (the snapshot's ACTIVE count, or the hub's `summary.activeAgents`), the source, and the advice "archive or delete unused agents, or ask BattleGrid for a paged read".
  - **When it runs:** after each snapshot (in `jobs.py`, beside the halt and entry-fail watches) and on every hub read during lifecycle describe.
- **Where the alert shows up:**
  - `GET /api/read-size-alerts` serves the alerts.
  - The Hermes halt-watch script reads that route as a fourth source and posts each new open alert once. An alert already resolved before the script sees it is never posted.
  - The sentinel poll leaves these alerts out, as it does the halt, entry-fail and status alerts.
  - `manager alerts ack` acknowledges one alert by id.
- **Daily report:** a new `## Read sizes` section shows each core read of the latest snapshot as characters and as a % of the 150,000 cap ("OVER the cap, refused" when it was refused), followed by the open alerts with the advice.

### Tests

- `tests/inventory/test_cap_watch.py`: the 60% crossing; no re-alert while the read stays above it or sits in the 50–60% band; the 80% crossing superseding the 60% alert; a read going straight to 80%; resolution under 50% (50% itself still holds) followed by a new crossing that alerts again; separate alerts per tool; an unmeasured size doing nothing; the snapshot recording `resultChars` and filing the alert with its active agent count; a roster refused over the cap alerting at 80% with the named size; the daily lines; the API view; the client measurement and its fallback.
- `tests/actions/test_lifecycle_describe.py`: a hub refused over the cap files the 80% alert from lifecycle describe.
- `tests/hermes/test_halt_watch.py`: the alert is posted once (with size, agent count and advice); a later 80% alert is posted once; an alert resolved before it was seen is never posted.

### Commits added

- 8020ff4 – the client measures sizes; the snapshot records `resultChars`
- 12afb3c – the `READ_NEARING_CAP` watch, the API route, the daily `Read sizes` section, the poll and ack scope
- cff44ba – lifecycle describe measures and watches `get_agents_hub`
- cfeccf3 – the Hermes halt watch posts `READ_NEARING_CAP` once

### Remaining concerns

- **The hub is not read on a schedule.** It is read only when a lifecycle action is described, so its warning only refreshes then. A scheduled read in the snapshot (for example once an hour) would cost one platform call each time. It was not added, because that changes the snapshot's read set.
- **The roster used by the scan cycle is not measured.** The scan cycle's own `list_intelligence_agents` read records no size, because `ScanRun` has no column for it. The snapshot's roster read covers the same tool every 5 minutes.
- **The size counts characters, not bytes.** The client counts characters of the text it received, and the server's exact count method is not measured. The over-cap refusal's own figure is used wherever there is one.

### Suite

The full suite passes on cfeccf3: 4717 passed, 5 skipped (run without -x). Before the addendum, on 04539dd, it was 4708 passed, 5 skipped.

## Review round

The review returned FIX FIRST with five findings. All five are fixed, each with tests.

1. **MEDIUM: a manual ack was re-filed on the next snapshot and re-posted every 5 minutes** (`cap_watch.py`).
   - **Fix:** the watch now checks the tool's newest alert, whether open or acknowledged. When the watch resolves or supersedes an alert itself, it records `resolvedBy: "watch"` in the detail. Any other acknowledgement counts as a person's. After a person's ack, nothing is filed while the ack's threshold is at or above the current level. The watch files again only when the read crosses a higher threshold, or when it drops under 50% (recorded as `rearmedAt`) and then rises again.
   - **Hermes wording** (`battlegrid_halt_watch.py`): the post now says exactly what an ack does — "closes this alert and keeps the watch quiet for this read at this threshold: no new alert until it crosses a higher one (80%), or drops under 50% and rises again".
   - **Tests:**
     - acked at 65%, three more snapshots at 65% file nothing; 85% files exactly one 80% alert, and no second one after that
     - a person's ack re-arms only after a drop under 50%
     - the watch's own resolutions are marked and never hold the watch back
     - end to end through the Hermes script: posted once, nothing after the ack plus a 65% snapshot, then one 80% post with the new wording
2. **LOW: write outcome mapping** (`pipeline.py`). In `_send_status` and `_draft_send_status`, a refusal code in `codes` (default `DRAFT_REFUSAL_CODES`; the Arena send passes `ARENA_REFUSAL_CODES`) now beats a bare `nextAct: narrow`, so it stays FAILED. Only the measured over-cap wording, or the `RESULT_OVER_CAP` tag that is set from it, makes the outcome UNKNOWN. An untyped code with `narrow` is still UNKNOWN. Tests cover all three cases.
3. **LOW: measurement isolation** (`client.py`). The size measurement now sits in its own try/except that falls back to `note_result_chars(None)`. A test where the measurement raises shows the call still returns its answer, with the size left unread.
4. **LOW: refusals without figures** (`cap.py`). A new `over_cap_chars()` counts an over-cap refusal recognised only by its code or `nextAct` (no figures) as the cap itself, i.e. 100%. `cap_watch.read_chars` does the same for a snapshot read: it uses `overCap.capChars`, or 150,000 when that is missing. Lifecycle describe's hub path uses `over_cap_chars`. Tests added.
5. **LOW: cursor reuse after narrowing** (`performance.py`). When `list_trade_outcomes` narrows after page 1, the read now restarts from cursor None at the smaller size instead of reusing a cursor that may encode the old page size. Rows are de-duplicated by outcome id, which also covers a page boundary moving mid-read. A test pins the exact call sequence `(50,None) (50,"50") (25,"50") (25,None) (25,"25") (25,"50")` and checks 60 distinct outcomes.

**Commits:** 5c533b0 (finding 1, plus the read-side half of 4), d8e1834 (findings 2–4), 7d79a74 (finding 5).

**Suite after the review round** (7d79a74): 4726 passed, 5 skipped, run once without -x.
