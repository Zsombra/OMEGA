# No pool halt: the cap floors at the minimum (the user's ruling, 2026-10-25)

This was written at 15:32Z.

- **Branch:** `C:/tmp-bgm-nopoolhalt` on `fix/pool-no-halt-floor-at-min`, from main `8bc4cfb`.
- **Not done:** nothing is merged, pushed or deployed. There were no BattleGrid calls and no Docker, .env or Hermes
  profile changes. The only database access was read-only psql, used for the 08:05Z replay numbers (action 131's describe
  notes and the snapshot positions).

## Commits

| sha | what |
|---|---|
| 3764675 | The exposure pool never halts for lack of room: the cap floors at the minimum. |
| 0475b2a | The pool's RESUME of its own legacy halt skips the heat and gross lines. |
| b55a26b | Every text names the floor-at-min rule, not the pool halt. |
| 3c5d575 | Every queued pool HALT is refused at describe; tests follow the floor-at-min rule. |

## What changed

### 1. The cap rule (`manager/risk/pool.py`)

- `PoolShare` gains `floor_usd`, which is the exchange minimum.
- `cap_usd` is now `min(max(share, minimum), ceiling)`.
- `floored` is true when the share is below the minimum.
- `fits` is now `cap >= minimum`. That is false only under a ceiling the user set below the minimum.
- `share_usd` stays the raw share, which can be negative.
- `share_record` adds `flooredAtMin` and `capUsd`.

### 2. No HALT for lack of room

- **`pool_requests` (`manager/risk/pool_state.py`)** proposes no HALT any more.
  - A ceiling below the minimum is noted, with no cap written and no halt.
  - The RESUME path for legacy `pool_halts` is unchanged. That covers "tighten before re-arm": the stored cap must be at
    or below the floored cap before the RESUME.
- **`_propose_pool` (`jobs.py`)** drops and logs any HALT request that reaches it, as a backstop.
- **Describe (`manager/actions/describe.py`, `_pool_recheck`)** refuses every pool HALT unsent. This covers a row still
  queued from before the deploy.
- **A HALT already sent before the deploy** still settles in the verify pass and is recorded in `pool_halts`, so the
  pool's RESUME can undo it.

### 3. The sync and the guard

- **SYNC guard (`manager/risk/guards.py`).** A share below the minimum is no longer a verdict. The metrics record
  `sync_limits_pool_floored_at_min` and `sync_limits_pool_cap_usd`. Only a ceiling below the minimum still refuses, and
  its text now says "the pool never halts".
- **Describe (sync).** A share below the minimum writes `cap_usd`. The describe notes record `poolFlooredAtMin`. A
  ceiling below the minimum is refused with no halt.
- **Resync (`pool_resync_targets`, `_sync_targets`).** A floored agent is now a target: its stored cap against the floor.
- **`build_trading_config`.** Unchanged. Its below-minimum refusal is now only a backstop.
- **A cap the user set below $10 is never raised.** This holds through the ceiling (10-16 rule) and `fresh_cap_refusal`
  when the user's edit is newer than the snapshot. Both are tested.
  - A cap below the minimum that the manager itself wrote before the ruling is still raised. The existing test
    `test_a_fresh_read_at_the_manager_s_own_value_is_raised_as_before` covers this. I first added a blanket "never raise
    a live cap below the minimum" check, and it broke that case, so I removed it.
- **The non-raising exemption still applies.** A floor of 10 against a stored $20 is a lowering. This is tested.

### 4. The pool's RESUME

- New `is_pool_resume` (proposed_by "pool", never RED).
- It skips heat and gross exposure only, recorded as `pool_resume_heat_gross_exempt`. That is narrower than the syncfix
  exemption.
- It keeps leverage, the open count, the same-direction cap, the breach lines, unread budgets, the action cap and the
  platform holds.
- **Why it is needed:** under floor-at-min the account can sit over the gross line, which would otherwise refuse the
  legacy RESUME forever.

### 5. Texts

These now state the new rule:

- `docs/phase-0/runbook.md`: the pause bullet, the pool section, the ceiling bullet and the margin bullet;
- the pause blast radius in `manager/risk/control.py`, with `tests/api/test_app.py` updated to match;
- the Commander skill, `hermes/skills/battlegrid-manager/SKILL.md`;
- the halt watch's POOL_ORDERS_UNREAD, PLATFORM_CHANGE_SEEN and docstring text, in `hermes/scripts/battlegrid_halt_watch.py`;
- the docstrings in `pool.py`, `pool_state.py`, `agent_config.py`, `radar_describe.py`, `holds.py`, `guards.py`,
  `requests.py` and `jobs.py`.

## Tests

**New file:** `tests/risk/test_pool_floor_at_min.py`:

- share 13.90 gives cap 13.90;
- share -0.74 gives cap 10, floored, `fits` true;
- ceiling 8 gives no cap written;
- a ceiling of 12 still caps the floor;
- **the 10-25 08:05Z replay.** Gross 21.16. The others' margin: BRENTOIL 10.8247, COIN 7.2565, MU 3.8131. The share of
  2c05ced6 is -0.74 under its $20 ceiling. The result is cap 10, `fits` true, and no HALT.
- a floored SYNC of 10 against a stored 20 is non-raising;
- the pool RESUME skips heat and gross only, and keeps leverage, breach lines and unread budgets.

**Rewritten to the new rule:**

| file | what it now checks |
|---|---|
| `test_pool_halts.py` | no HALT; a resync target at the minimum; a legacy halt waits for its cap |
| `test_pool_executor.py` | no HALT in supervised or unsupervised LIVE; the resync syncs a below-minimum agent at the minimum; a legacy `pool_halts` record leads to the cap synced, then a pool RESUME |
| `test_pool_ceilings.py` | ceiling 8 gives no sync and no HALT; a user cap of 8 newer than the snapshot is refused at send |
| `test_pool_actions.py` | a legacy queued HALT is refused unsent; a HALT sent before the deploy still verifies and records; a pool RESUME with a below-minimum share is sent |
| `test_model_resume.py` | a model RESUME with a below-minimum share is described, floored |
| `test_platform_first_replay.py` | no HALT at 08:05Z; the old action-131 path is still replayed |
| `test_pool_sync.py` | see concern 1 |
| `test_pool_guards.py` | updated to the new SYNC guard |
| `test_pool.py`, `test_pool_margin.py` | the shares and caps under the floor |
| `test_refused_sync_throttle.py` | the tick probe now checks that the pool step runs, instead of expecting a pool HALT |

**Suite:** 5292 passed, 5 skipped, 1 error.

- The error was `tests/actions/test_strategy_describe.py::test_a_commit_of_a_create_describes_to_the_stages_version_sha_and_no_base`.
  It was Windows socket exhaustion (WinError 10055).
- That file alone: 60 passed.

## Concerns

1. **The loss-line split can block the floored sync.**
   - `build_trading_config` keeps the manager's own rule that each loss line must be at or below the cap. The ruling
     says to keep the split.
   - When the split's drawdown is above the floored cap, the sync is refused. The agent then keeps its higher stored cap
     and is not halted. A legacy-halted agent then never gets its RESUME, because its cap never reaches the floor.
   - At 10-25 numbers this does not bite (drawdown 1.24 against a cap of 10). It does in the $1000 test world (50
     against 17.5), and `test_pool_sync.py` now pins that refusal.
   - The user should decide whether to clamp the loss lines to the floored cap.
2. **The whole-pool capacity check still blocks.** `_fleet_over_capacity` still proposes no SYNC at all when the whole
   gross line is below one minimum. I left it unchanged. Under the ruling it could arguably floor everyone at 10.
3. **Stale texts and rows stay until deploy and reinstall.**
   - The Commander and halt watch copies Hermes actually runs change only after the skill and script are reinstalled.
     That is a profile step I did not take.
   - Legacy pool HALT rows from before the deploy are refused at describe. Their keys are freed as usual.
4. **The RESUME exemption is narrower than the sync one.** It covers heat and gross only. If a legacy-halted agent is
   blocked by the open-position count or leverage, it stays halted. That is intended (narrow), but worth knowing.

## The coordinator's rulings on concerns 1 and 2 (written 15:48Z)

Concerns 3 and 5 stand as done. Concern 4 (the Hermes copies) is the coordinator's, after the deploy.

| sha | ruling | what changed |
|---|---|---|
| dbd9a0a | Concern 1: clamp the loss lines | See "Concern 1" below. |
| 5ea3ca0 | Concern 2: a pool under the minimum does not block | See "Concern 2" below. |

### Concern 1: clamp the loss lines (dbd9a0a)

- **The clamp.** New `manager.risk.pool.clamped_loss_lines` takes the fleet's split loss lines and clamps them down so
  that daily is at or below drawdown, which is at or below the cap. That is the order the platform requires.
- **`build_trading_config`** clamps instead of refusing when a line is above the cap. Each clamp is recorded on the row
  (key, from, to, why). It still refuses a policy split whose daily line is above its drawdown line.
- **Same lines everywhere.** `pool_resync_targets` and the pool RESUME's "tighten before re-arm" check compare against
  the same clamped lines. So a clamp that has landed settles and does not trigger another sync.
- **Clamping down never counts as raising.** One caveat: a sync can still raise a stored line that sat lower. That is
  then judged as raising, as before. `test_pool_sync.py` pins this. In that world the floor of 17.5 raises a stored
  drawdown of 10, so the gross line refuses the sync.
- **Tests:**
  - the drawdown clamped to the cap;
  - both lines clamped;
  - the daily ≤ drawdown ≤ cap ordering, pinned across 7 caps;
  - no clamp under a large cap;
  - a legacy-halted agent with share 10 floored at 17.5 and a drawdown split of 50. Its resync target names the cap and
    the drawdown at 17.5, and the build gives 17.5 / 17.5 / 15. Once the build lands, it is no longer a target and the
    pool proposes its RESUME.

### Concern 2: a pool under the minimum does not block (5ea3ca0)

- **Removed.** `_fleet_over_capacity` is gone, together with its call in the resync loop. It proposed no sync at all and
  filed `FLEET_OVER_CAPACITY` whenever the whole gross line was below the minimum.
- **New behaviour.** Each agent's cap now floors at the minimum. It is still capped by the user's ceiling, and the loss
  lines are clamped under it.
- **Kept.** The constant stays for the review module, which still reads the acknowledged alerts filed before.
- **Runbook** updated.
- **Tests:**
  - a 600.00 pool under a 601 minimum now proposes the sync (cap 601, `poolFlooredAtMin` share 600.00) and files no alert;
  - no alert is filed across ticks or after a fleet change.

**Suite:** 5302 passed, 5 skipped, 0 failed, 0 errors (558 s).

### Remaining concerns

- **The deploy check still refuses (out of scope).** `radar_describe`'s deployment check still refuses a Radar deploy
  when the whole pool is below one minimum. The ruling covered syncs only.
- **Two review texts are stale.** The review module's capacity text (`manager/review/views.py`, "over capacity ...
  UNDECIDED") and `fleet_capacity` still describe the retired stop. No new alert can arise, so they only show for
  alerts filed before 10-25.

## The no-halt review fixes (verdict MERGE AFTER FIXES; written 16:04Z)

| sha | finding | fix |
|---|---|---|
| 74bdd9d | The pool-RESUME exemption also skipped an UNREAD heat | `heat is None` refuses every request again, the pool RESUME included. Only the heat-above-max and gross-above-max comparisons are skipped for it. Test: a pool RESUME with a position missing its mark is refused "heat is undetermined". |
| 37d9f65 | `pin_held` ran after the build, so a held loss line could break daily ≤ drawdown ≤ cap | See "The held-value order check" below. |
| 2e67ca3 | The Radar deploy check under a sub-minimum pool, and its wording | See "The Radar wording" below. |
| ba4e2f2 | The dead `kind == "HALT" and share.holds_position` branch in describe | Removed. |

### The held-value order check (37d9f65)

- **Describe.** New `holds.held_order_refusal`. After the held keys are pinned, describe checks that daily ≤ drawdown ≤
  cap still holds. If a held key breaks it, the sync is refused and the verdict names that key. Nothing is built to
  send, so there is no write and no infeasible draft. A value that is not a number counts as breaking it.
- **The resync.** `sync_hold_skip` makes the same prediction and skips the agent, so the row does not churn. Its
  predicted loss lines now use the clamped lines the build writes, not the raw split.
- **Tests:**
  - **executor:** the user holds a drawdown of 15; OTHER opens 10; AGENT's cap floors at 10. The resync logs the skip
    and proposes nothing. A direct describe is refused, names "held maxCumulativeDrawdownUsd ... 15.0 (held)", and
    carries no params;
  - **unit:** the order check, plus the resync prediction.

### The Radar wording (2e67ca3)

- **Behaviour is unchanged.** The deploy is still refused, because a deployment adds exposure and the ruling covered
  caps and halts.
- **The texts now say a new deployment waits for room**, and none says the pool halts an agent or that "no agent
  could open". Updated: the `radar_describe` verdict and docstring; `review.rules` (`fleet_capacity`, `fleet_effect`'s
  warning, `capacity_sentence`); `review.views.capacity_line`; and `pool.can_fund_one`.
- **Tests** in `test_radar_describe.py` and `review/test_rules.py` are updated to the new wording.

**Suite:** 5305 passed, 5 skipped, 0 failed, 0 errors (531 s).
