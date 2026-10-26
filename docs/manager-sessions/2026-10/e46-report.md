# E4 + E6 report: the margin pool, the infeasible-sync refusal, the officer guard

Date: 2026-10-20, written 12:06Z. Worktree `C:/tmp-bgm-e46`, branch `feat/parity-risk`, from main `b6719d2`.

Nothing was merged, pushed or deployed. No BattleGrid call was made. Docker, `.env` and the Hermes profiles were not
touched. Reads used: read-only psql for the stored shapes, and the stored `manager_schemas` and `surface_tools`.

## Commits

| sha | what |
|---|---|
| d968d6f | E4: the pool subtracts each other agent's open MARGIN, plus the margin resting entry orders reserve |
| e50fd01 | E4: a SYNC_LIMITS whose draft `impact.capital` is infeasible or unread is never committed, and files `SYNC_LIMITS_INFEASIBLE` |
| 4b04b44 | E6: the officer guard (`OFFICER_EDIT_SEEN`, `OFFICER_PROPOSAL_PUSHED`), the reads, MANAGER_TOOLS |
| 64eda5a | Docs: one Commander SKILL.md paragraph, and runbook entries |

## E4: the pool counts margin

**The margin.** The code is in `manager/risk/pool.py`: `position_margin`, `open_position_margin` and `row_margin`.
- It uses the platform's `marginedUsd` when served.
- Otherwise it divides the notional by `effectiveLeverage`. It uses the entry notional when served, which is the base
  `marginedUsd` is computed from. Live SNDK: 17.4317 / 3 = 5.8106.
- If neither can be read, the margin is UNDETERMINED. Every share it feeds is then None: nothing is synced, halted or
  resumed.

**Where it is used.** Both pool paths now count margin:
- `pool_from_db`, which the executor uses;
- `pool_of_state`, which describe and the guard use.

`OpenPosition` gained `margin_usd` and `entry_notional_usd`, read from `raw`.

**The 10-19 numbers, pinned.** These are in `tests/risk/test_pool_margin.py`, plus a stored-row test in
`test_pool_halts.py`:
- 15.53 at 2x gives a margin of 7.765, and floor(13 - 7.765) = 5.23.
- `marginedUsd` 7.77 gives 5.23.
- The old notional rule would have given -2.53.

**Resting entries.** `resting_entries(reads)` reads `reads["list_agent_open_orders"]`. That is E3's key, and main does
not store it yet.
- **Absent:** nothing is counted, and the pool record carries `restingNote`.
- **Failed, or with no list:** the pool is UNDETERMINED.
- **Per ENTRY order:** the margin is `marginUsd` / `marginedUsd` when served. Otherwise it is `requestedQuantity x
  limitPrice`, the notional, which is the upper bound at leverage >= 1. A margin that cannot be read makes the other
  shares UNDETERMINED.

**Impact.** In `_send_agent_draft`, the read-back between the stage and the commit now runs `impact_refusal`
(`manager/actions/agent_config.py`).
- `feasible` false, or unread (absent, null, or not a bool), is a read-back mismatch. The row goes FAILED before the
  commit, so it is never DONE, and the left draft is named.
- One `SYNC_LIMITS_INFEASIBLE` alert is filed per row, carrying `capital` and ledgered `action.sync_infeasible`.
- Stored actions 98-121 all served `capital` with `feasible: true`, so this changes nothing today.

## E6: the officer guard

`manager/risk/officers.py` is new and pure. Attribution runs only when the latest snapshot shows an unrecorded outside
cap edit, in executor step 1b (`_attribute_cap_edits` in `scheduler/jobs.py`). It makes one `list_officer_reviews
{includeClosed: true}` call and one `get_agent_draft` per edited deployed agent. An edit is recorded once, so these
reads do not recur.

**What counts as the officer's.** Either of:
- a draft axis whose `axesMeta.<AXIS>.source` (or `lastSource`) is `officer` (the enum in the stored 123.0.0 schema)
  and that drafts exactly the stored cap;
- an `applied` review of the agent that proposes exactly the stored cap and was applied in (baseline, snapshot].

**What happens to an officer edit.**
- It is recorded under `system_state.cap_officer_edits`, which becomes the baseline, so it is not re-filed.
- `OFFICER_EDIT_SEEN` is filed and ledgered `pool.officer_edit_recorded`.
- The user's ceiling is left untouched, so an officer's raise never erases it. This is tested with the user at 13 and
  an officer applying 20: the 13 stands, and the pool lowers 20 back to 13.
- **Design choice.** Until a person decides, the officer's cap binds the pool only DOWNWARD: effective ceiling =
  min(user ceiling, officer cap). Otherwise the pool would raise a cap an applied proposal lowered.
- `manager pool ceiling clear` clears both, and `manager pool ceilings` lists officer edits separately.

**When attribution cannot be read.** The edit is recorded as the user's ceiling, as before, with `attribution.note`
naming the read that failed. This covers a failed read, an unrecognised shape, and a matching review whose apply time
was not served.

**Pushed proposals.** One `OFFICER_PROPOSAL_PUSHED` alert per review id or draft version (ledgered
`officer.proposal_pushed`) is filed in two places:
- from a `pushed` review of a deployed agent, or an officer-written draft axis, seen during attribution;
- from a SYNC_LIMITS refused at describe on a draft an officer wrote. The verdict also says "written by a Strategy
  Officer". This adds no extra read, because describe already reads the draft.

**Reads and the watch.**
- `read_officer_reviews` and `read_agent_draft` are in `manager/platform/reads.py`. Neither raises.
- `READ_SETS["list_officer_reviews"] = None`: the shape is not measured, so every change blocks.
- `list_officer_reviews` and `list_agent_open_orders` joined MANAGER_TOOLS and WRITE_PIPELINE_READS. The pins moved:
  MANAGER_TOOLS 54 -> 56, and the 104.0.0 baseline 52 -> 53 tools, 492,203 bytes.

**Docs.** One paragraph in `hermes/skills/battlegrid-manager/SKILL.md`, and three runbook bullets in "Phase 3", after
the ceiling bullet. The pool bullet now says MARGIN.

## Tests

- New: `tests/risk/test_pool_margin.py` (17), `tests/risk/test_officers.py` (16), `tests/actions/test_officer_guard.py`
  (11). Also 4 impact tests in `test_sync_on_draft.py` and 2 margin and resting tests in `test_pool_halts.py`.
- Adjusted: the test worlds that resized a position now also set `marginedUsd` (they are 1x, so the numbers are
  unchanged). The DRAFT fake's `impact` can now be configured.
- **Full suite** (one run, no `-x`): 4756 passed, 21 failed, 5 skipped. All 21 failures come from the environment,
  not from this branch. The shared `battlegrid-manager/.omega` resolves to the v0.8.3 tree that E1/E2 installed, while
  this branch pins v0.8.2. The failures are:
  - `tests/commands/test_strategy.py` (18);
  - `tests/authoring/test_pin.py` (2);
  - `tests/strategist/test_direction.py::test_a_fade_thesis_shows_the_inverted_readings`, where `pctB20_now` is v123's
    new header.

  Every package this branch touches passes in full: actions, risk, scheduler, platform, hermes, and commands except
  test_strategy.

## Concerns

1. **The review row shape is NOT MEASURED.** The stored surface has no output schema for `list_officer_reviews`, and
   no review has ever existed. The parse guesses the names (`reviews[]`, `id`, `agentId`/`agent`, `status`, `proposal`,
   an apply time from `appliedAt`/`resolvedAt`/`closedAt`/`statusChangedAt`/`updatedAt`). Any mismatch is read as
   UNREAD, which falls back to today's behaviour. So today a real officer edit would most likely still become a user
   ceiling, as before, unless the draft-source path catches it. Capture the first live answer and pin it.
2. **A merge seam with E3.** E3 stores `entryOrders` without `requestedQuantity` or margin. After both merge, every
   resting entry of another agent makes the pool UNDETERMINED: no syncs and no pool halts while it rests (TTL 15 min).
   This is dormant with one deployed agent. E3's `normalize_entry_orders` should keep `requestedQuantity`, and its read
   set should declare it. Both branches also add `list_agent_open_orders` to MANAGER_TOOLS and bump the count pins, so
   the conflict is textual.
3. **The infeasible refusal leaves the staged draft.** That blocks later syncs until the user discards it. Discarding
   would be a new platform write, which is out of scope. If the platform would have accepted a LOWERING commit, this
   keeps a higher cap. The schema text says the commit refuses an infeasible config anyway, but that is not measured.
   An unread impact refuses too; every stored sync since 10-15 served it.
4. **Today's behaviour is kept when attribution cannot be read, as briefed.** That includes the old hazard: an
   unattributed raise past a user ceiling replaces that ceiling.
5. **A downward-only binding of mine.** An officer's cap stays a downward-only bind until `ceiling clear`. This is my
   design choice, not a user ruling; it needs the user's word on officer ownership of `tradingConfig` (gap-officers
   decision 3).
6. **Notional is still used in two conservative places.** `fits` still compares a margin cap with the notional
   exchange minimum ($10). The account-level gross guard (`AccountState.gross_exposure_usd`) still sums notional. Both
   err on the safe side and were left alone.
7. **After the deploy.** D7c may refuse the next platform move as "never recorded" for the two new MANAGER_TOOLS. One
   `manager contract ack` after the first watch run copies them in, as with `list_entry_decisions`.
8. **Visibility.** The new alerts are plain Alert rows, like `CAP_SET_OUTSIDE_MANAGER`. The Hermes halt watch does not
   post them, and `manager_agent_status` does not list them.
9. **The 21 failures are environmental, not caused by this branch.** The shared `battlegrid-manager/.omega` tree is at
   v0.8.3, not the pinned v0.8.2; it was installed by E1/E2 work in another worktree. Re-run on a matching tree, or
   after E2 merges, to confirm green.

## Rebase round (12:38Z, 2026-10-20)

The coordinator's follow-up. Same worktree and branch, same rules: no BattleGrid call, no merge, push or deploy, and
Docker, `.env` and Hermes profiles untouched.

### 1. Rebased onto main 413140c (E2, E3, E5)

- **Conflicts.** Only the tool-count pins conflicted, in `manager/platform/watch.py`, `tests/platform/test_watch.py`
  and `tests/platform/test_watch_schemas.py`.
- **How they were resolved.** E3 already added `list_agent_open_orders` to MANAGER_TOOLS. This branch now adds only
  `list_officer_reviews`: 56 tools, and 53 in the 104.0.0 baseline at 492,203 bytes.
- **The OMEGA failures are gone.** The 21 failures from the first round no longer occur: main pins v0.8.3.

### 2. The E3 clash is fixed (old concern 2)

**The shape.** Read from the 104.1.0 output schema of `list_agent_open_orders`
(`tests/fixtures/2026-10-08-surface-104.1.0/output_schemas.json`). All three fields are required:
`requestedQuantity` (string), `limitPrice` (string or null) and `triggerPrice` (string or null). No snapshot in
stored state holds this read yet; it was not deployed.

**What is stored now.**
- `normalize_entry_orders` keeps `requestedQuantity`, `limitPrice` and `triggerPrice`.
- The snapshot read now also stores `entryOrderCount`, the number of ENTRY orders served before the cut at 20.
- The three fields joined the read set. They are checked served and required at 104.1.0.

**How the pool sizes a resting entry.**
- The size is `requestedQuantity x limitPrice`. A trigger entry with no limit price uses its `triggerPrice`. This is
  the notional, which is the upper bound of the margin.
- An order whose size cannot be read makes only the OTHER agents' shares UNDETERMINED. Its own agent's share is never
  affected.
- Pinned in a test: an agent with no other agent deployed is never made UNDETERMINED by its own unsized resting order
  (`test_an_agent_alone_is_never_undetermined_by_its_own_unsized_resting_order`).
- A list cut at 20 while more were served is UNDETERMINED, because whose orders were dropped is unknown.
- A failed resting-order read is still UNDETERMINED, as in the first round: a failed read is not an empty book.
- The E3 snapshot test now checks that the stored rows give the pool 0.5 x 41.25 per order.

**Daily report.** The "Exposure pool" text now says it counts margin, and it prints the note when resting entries
were not read. `test_daily` now serves the resting-order read; without it the read fails and the pool is correctly
UNDETERMINED.

### 3. Hermes posts

- **The route.** `GET /api/pool-alerts` is new (`manager/risk/officers.py:pool_alerts_view`). It serves the
  `OFFICER_EDIT_SEEN`, `OFFICER_PROPOSAL_PUSHED` and `SYNC_LIMITS_INFEASIBLE` alerts, open first. The halt watch reads
  it as one more source in `SOURCES` and posts each new open alert ONCE, using the same `posted` state, so it is
  never re-posted. An acknowledged alert is recorded and never posted.
- **What each post says.**
  - `SYNC_LIMITS_INFEASIBLE`: "The staged draft is LEFT in the agent's draft ... The user must open the agent in the
    editor and DISCARD that draft".
  - `OFFICER_EDIT_SEEN`: the user's ruling, stated as lower-only until `manager pool ceiling clear`.
  - `OFFICER_PROPOSAL_PUSHED`: the agent's SYNC_LIMITS refuse while the proposal holds its draft.
- **An unknown kind** on the route is skipped and recorded, never posted.
- **The kind string.** `SYNC_LIMITS_INFEASIBLE` is one string on both sides of the import boundary, and a test pins
  that.

### 4. The user's ruling on old concern 5

"An officer's cap only ever lowers the pool target, as min(share, user ceiling, officer cap), until `manager pool
ceiling clear`." The behaviour is unchanged. It is now cited as the ruling in four places:
- `cap_ceiling.py` (the module docstring and the alert's `rule`);
- `officers.py`;
- the runbook;
- the Commander SKILL.md.

### 5. A flake fixed

The first full run had one failure:
`tests/inventory/test_entry_failures.py::test_a_halt_older_than_the_base_is_not_read_and_moves_nothing_but_a_recent_one_does`.
It comes from E3's code, not from this branch, and it passes alone. The cause: the test called `_at(3)` twice, and the
two calls fell either side of a second boundary. The fix reads the instant once; it is test-only.

### Commits on 413140c

| sha | what |
|---|---|
| c84058f | E4: the pool counts margin and resting entries (rebased) |
| 209470a | E4: an infeasible or unread impact is never committed, `SYNC_LIMITS_INFEASIBLE` (rebased) |
| 9ced6ad | E6: the officer guard (rebased; pin conflicts resolved) |
| 2d0a30f | Docs (rebased) |
| 5e7628d | E3's stored resting orders carry quantity and prices; `entryOrderCount`; pool sizing; read set |
| 301a2f8 | `GET /api/pool-alerts` and the halt-watch posts; the ruling documented |
| 89af190 | Test flake: the 3 h halt instant read once |

### Suite

One full run in the background, no `-x`, no PYTHONPATH override: **4843 passed, 5 skipped, 0 failed** (9:55). The
affected files were run before it: hermes, api, risk, inventory, platform, and the pool, ceiling and officer actions
tests.

### Concerns now

1. **Still open: the review row shape is NOT MEASURED** (concern 1 above). Until the first live answer is captured,
   attribution through reviews most likely reads UNREAD, which keeps today's behaviour. The draft-source path works
   from the measured enum.
2. **A failed resting-order read makes the whole pool UNDETERMINED.** This includes a lone deployed agent: no syncs and
   no pool halts or resumes until the next good read. That is fail-closed and transient. E3 treats the read as a watch
   read, so its failure does not turn the heartbeat red, but the daily report and the pool record show
   UNDETERMINED.
3. **Unchanged from the first round:**
   - concern 3: an infeasible sync leaves its draft for the user to discard;
   - concern 4: the unattributed-raise hazard when attribution is unread;
   - concern 6: notional is still used in `fits` and in the account-level gross guard.
4. **After the deploy.** One `manager contract ack` may be needed after the first watch run, for
   `list_officer_reviews`. This repeats concern 7, now covering only that tool.
5. **Still not in `manager_agent_status`.** The new alerts now reach the Commander's chat through the halt watch, but
   they are not listed in agent status.
6. **The halt-watch script must be redeployed.** Its new source needs the profile copy of the script updated through
   `install_commander.py --halt-watch`, which touches the Hermes profile, so I did not run it. An older manager without
   `/api/pool-alerts` answers 404: that is logged, and the other sources still post.

## Review round (written 13:27Z, 2026-10-20)

The risk-path review came back FIX FIRST. All three items are fixed, with tests, in commit `9e6e0ec`, on top of
`89af190`. Same worktree and rules as before.

### F1 (blocking): a sync that only lowers is never blocked by its impact

- **The base.** Describe records the config the sync is built over as `notes.baseTradingConfig`, stored with the
  row's describe notes.
- **The check.** At the read-back, an infeasible or unread `impact` refuses the commit only when `only_lowers(staged,
  base)` is false (`manager/actions/agent_config.py`). It walks `config_diff`. Every changed field must be one of
  `LOWER_IS_SAFER` and must be lower, and at least one must change:
  - `LOWER_IS_SAFER`: cap, both loss lines, leverage, daily trades, slippage, min allocation, the three presets.
  - A change to `balanceThresholdUsd`, a raise, no change at all, or an unread base is no lowering: the commit is
    refused as before.
- **A lowering sync** still files `SYNC_LIMITS_INFEASIBLE` (`committed: true`, `lowering`, `draftLeft: null`) and is
  committed as main does. The platform may still refuse it. The halt-watch post for that case says it was committed
  and asks for no discard.
- **Tests** (`tests/actions/test_pool_ceilings.py`):
  - the pool lowers $20 to $12.00 with an infeasible impact: the stage AND the commit are sent, and the alert is filed;
  - a raising sync with an infeasible impact is still refused, with no commit and the left draft named;
  - `only_lowers` field directions.

### F2: a failed resting-order read no longer freezes the pool

- **Upper bounds.** A failed read, a list cut at 20, or a resting order with no readable size no longer makes the
  pool UNDETERMINED.
  - The shares are computed WITHOUT that margin, which is an upper bound on the true share.
  - Each such share carries `bound_reason` (`upperBound` on the record), and the pool carries `bound_reason` for a
    whole-read failure.
  - An unsized order only bounds the OTHER agents' shares, never its own agent's.
  - An unread POSITION margin is still UNDETERMINED.
- **Allowed on a bound:**
  - a pool HALT, when even the bound does not fit;
  - a SYNC_LIMITS that lowers the cap: `pool_resync_targets` keeps only lowerings, and describe refuses any sync whose
    target is at or above the live cap.
- **Refused on a bound:**
  - every pool RESUME, in `pool_requests` and again at describe (`_pool_recheck`);
  - every raise.
- **`POOL_ORDERS_UNREAD`.** `check_orders_unread`, executor step 1c, files the alert when the newest 3 snapshots in a
  row left resting margin unread.
  - One per run, keyed by the run's first snapshot; a good read ends the run.
  - Ledgered `pool.orders_unread`.
  - Served by `/api/pool-alerts` and posted once by the halt watch.
- **Daily report.** The "Exposure pool" section names the bounded agents.
- **Tests:**
  - `test_pool_margin.py`: bound shares;
  - `test_pool_halts.py`: HALT still proposed, RESUME refused, only lowering resync targets, and the alert after 3 and
    once per run;
  - `test_pool_ceilings.py`: describe refuses a raise, lets a lowering go, and refuses a pool RESUME;
  - `test_halt_watch.py`: the post, once.

### F3: zero is not a margin

- **`marginedUsd`.** It must be > 0. A 0 with a positive notional falls back to notional / leverage; only a zero
  notional is a zero margin.
- **Resting orders.** `marginUsd` must be > 0, else quantity x price with both > 0. Otherwise the order is unread and
  bounds the other shares, per F2.
- **Tests** in `test_pool_margin.py`.

### Suite

The affected packages were run first (hermes, actions, risk, inventory, platform, api, scheduler): 3464 passed. Then
one full run in the background, no `-x`, no override: **4857 passed, 5 skipped, 0 failed** (13:34).

### Concerns after this round

1. **A RESUME made outside the pool is unaffected.** On an upper-bound share, F2 refuses the pool's own RESUMEs. A
   user- or model-proposed RESUME (approved by the user) is not refused by it. Say if "every RESUME" was meant to
   include those.
2. **Rows proposed before this deploy carry no `baseTradingConfig`.** A row still queued at deploy time would treat an
   infeasible impact as "not only lowering" and refuse, as the first round did. This lasts at most one queue age.
3. **What counts as "lower is safer" is my reading.** For `minAllocationUsd` (clamped under the cap) and
   `maxSlippageBps`, I counted a lower value as safer. A change to `balanceThresholdUsd` counts as no lowering.
4. **Still open from earlier:**
   - the review row shape is NOT MEASURED;
   - `fits` and the gross guard still use notional;
   - one `manager contract ack` may be needed after deploy for `list_officer_reviews`;
   - the profile copy of the halt watch must be reinstalled (`install_commander.py --halt-watch`, a Hermes-profile
     step I did not run).

## Re-review note (13:55Z, 2026-10-20)

Commit `f7a39c4`, on top of `9e6e0ec`.

**The fix.** `SYNC_LIMITS_INFEASIBLE` was filed with `committed: true` before the outcome was known. It is now filed
only once the outcome is known:
- At the read-back, the send records a pending `syncInfeasible` on the row's metrics.
- **Refused at the read-back,** whether for not only lowering or for another failed check: the alert is filed at once
  with `committed: false` and `draftLeft`.
- **Commit refused by the platform:** the same, `committed: false` and `draftLeft`.
- **Commit accepted, or UNKNOWN:** the alert is left to `_settle_row`. That runs when the verify pass or a hand
  settle closes the row: DONE files `committed: true`, FAILED files `committed: false` with `draftLeft`.
- A row files at most once (`filed` is recorded on the pending entry).
- The halt watch already says to discard the draft whenever `committed` is not true.

**Tests** (`test_pool_ceilings.py`), all on the pool lowering $20 to $12.00 with an infeasible impact:
- committed, then verified DONE: no alert before verify, `committed: true` after it, filed once;
- the platform refuses the commit: `committed: false`, draft left;
- another read-back check fails: `committed: false`, draft left, no commit sent;
- committed, then verify settles FAILED: `committed: false`.

The halt watch also gets a "lowering sync that did not land" post test.

**Runbook.** It now says `POOL_ORDERS_UNREAD` re-files about every 50 snapshots during a long outage, and describes
when the infeasible alert is filed.

**Suite.** Affected packages (actions, hermes, risk): 2597 passed. One full background run, no `-x`, no override:
**4861 passed, 5 skipped, 0 failed**.
