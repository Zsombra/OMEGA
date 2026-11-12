# E3 report: expired entries are now visible (battlegrid-manager)

Written 2026-10-20 around 11:30Z. Worktree `C:/tmp-bgm-e3`, branch `feat/parity-expiry`, based on main `f1f2746`.
Nothing is merged, pushed or deployed. I made no BattleGrid call and did not touch Docker, `.env` or the Hermes
profiles. The only live access was read-only psql of `system_state` (`manager_schemas`, `surface_tools`).

## Status

All five parts are done: the reads, the alert, the status line, the resting orders, and the docs.

**Suite:** 4739 passed, 5 failed, 5 skipped (full run, no `-x`).
- The 5 failures are the max_leverage 1-2 -> 1-3 test pins: four in `tests/api/test_app.py` and `tests/commands/test_policy.py::test_cli_policy_output_is_pinned_byte_for_byte`.
- They are not mine. They also fail on `f1f2746`, and main has since fixed them in `20d4fff` / `b6719d2` (fix/leverage-test-pins). A rebase onto main clears them.

## Commits (on f1f2746)

| sha | what |
|---|---|
| 78a5e0a | The reads. An EXPIRED decision's `expiryReason` uses the agent's single `get_signal_log` per snapshot, after any unread FAILED. The rows' `entryPrice`/`expiresAt`/`executedOrderId` are stored, with 4 additive `entry_decisions` columns. One `list_agent_open_orders` read per snapshot. Read sets and MANAGER_TOOLS updated. |
| fd9cec0 | The `AGENT_ENTRIES_EXPIRING` rule (`manager/inventory/entry_expiries.py`), the job wiring, `GET /api/entry-expiries`, per-alert ack scope, and exclusion from the sentinel poll. |
| 4fb0776 | The agent status gets a last-24 h line and resting entries. EXPIRED becomes an entry outcome. The daily report gets a "## Expiring entries" section. |
| 480e3c6 | The halt-watch script posts `AGENT_ENTRIES_EXPIRING` once. |
| 95e0a6c | Docs: a runbook section, plus one line each in the Commander's SOUL.md and SKILL.md. |
| a321206 | Re-measured D7c baseline size test: 53 tools, 492,203 bytes. |

## What was built

### 1. Reading the expiry reason

**How the one detail read is shared.** It stays at one `get_signal_log` per agent per snapshot:
- it reads the newest FAILED decision whose reason is unread;
- only when there is none, it reads the newest such EXPIRED one (`REASON_STATUSES` in `snapshot.py`).

So failures keep the latency they have today, and expiry reasons fill in after them.

**Storage.** `normalize_execution` now returns `expiry_reason`. It goes into the new column `entry_decisions.expiry_reason`, with the same `reason_read_status`.

**Failed reads.** UNREADABLE works as it does for failures:
- no `signalLogId` gives UNREADABLE at once;
- NOT_FOUND or `log: null` also gives UNREADABLE at once;
- 3 failed reads give UNREADABLE.

**Read set.** `get_signal_log` now declares `/log/pipeline/execution/expiryReason`. It is served and required at 119 and at the live 123.0.0.

### 2. The AGENT_ENTRIES_EXPIRING alert

It is the entry-fail rule, parameterised. `entry_failures.py` gained `EntryWatch`, plus `streak(counted=...)` and `resolve_open(watch=...)`. The FAILING defaults are unchanged.

It uses the same rules as the fail alert:
- the join boundary;
- 3 in a row, the newest under 24 h old;
- reasons settled;
- one alert per streak, keyed by instant;
- ack silences only that streak;
- it auto-resolves on EXECUTED, on undeploy, or after 24 h with no expiry;
- a halted agent, or one whose halt state is unread, files nothing.

**My choice for a FAILED in the middle: it is passed over.** It neither counts nor ends the streak.
- This mirrors how the fail watch already passes over an EXPIRED. Neither one filled, so the agent is still not getting entries.
- The refusal itself is reported by the fail watch.
- CANCELLED, PENDING and SKIPPED are passed over too. EXECUTED ends the streak.

**What the alert detail carries:**
- `expiryReason` and `reasonCounts`;
- `ttlMinutes`, taken from the message's `maxAgeMs`, or from `expiresAt - createdAt` if that is missing;
- `entries[]`, with each entry's coin, direction, `entryPrice`, createdAt, expiresAt and reason;
- a plain `note`.

**The Hermes post** says the order "rested as a limit at the bar's close price and expired unfilled after 15 min: price moved away and did not come back to it". It gives the reasons and each entry price. When a reason other than TIME is present, it says the platform withdrew the order instead.

### 3. The status line

Example: "last 24 h: 1 filled, 3 expired (TIME), 1 failed (BELOW_EXCHANGE_MINIMUM)". With mixed reasons it reads "(TIME 3, PRICE_DEVIATION 1)".

Other additions:
- "last entry EXPIRED TIME";
- "entry-expiry alert N open".

### 4. Resting orders

**Schema checked.** In the stored surface (123.0.0 `surface_tools`), `list_agent_open_orders` takes **no input** (`{}`) and serves every agent's live orders. Its output schema exists only in the 104.1.0 fixture, which has `orders[]` with `agentId`, `purpose`, `limitPrice`, `submittedAt`, and so on.

**So it is ONE read per snapshot,** not one per agent. It runs only when some agent is deployed.

**How it behaves:**
- Its key is in `WATCH_READ_PREFIXES`, so a failure never turns the heartbeat red.
- It keeps ENTRY orders only, at most 20, stored as `reads.list_agent_open_orders.entryOrders`.
- A shape error is UNDETERMINED.
- The status shows "resting entry HIMS at 41.25 for 6 min", or "resting orders UNDETERMINED".

**Read set:** `/orders[]/agentId`, `/orders[]/purpose`, `/orders[]/submittedAt`. The test checks these against the 104.1.0 schema.

### 5. Docs

- **Daily report:** a new "## Expiring entries" section, and the `entry_expiry.*` events are in NOTABLE.
- **Inventory report:** the reads line now says "resting orders: OK (N entry)".
- **Runbook:** a new section, "Expiring entries: the expiry watch".
- **Commander:** one line in SOUL.md and one in SKILL.md.

**Tests:** 15 new in `tests/inventory/test_entry_expiries.py` and 2 new in `tests/hermes/test_halt_watch.py`. Existing pins were updated for the new read: read counts 34 -> 35, MANAGER_TOOLS 54 -> 55, and the status-line pin.

## Concerns

1. **A contract ack may be needed after the deploy.** `list_agent_open_orders` is now in MANAGER_TOOLS, but the acknowledged baseline does not hold it. It is the same situation `list_entry_decisions` had. Only if D7c later refuses a move as "never recorded" should `manager contract ack` be run, and only after the first watch run records the tool.
2. **The open-orders output schema is old.** The live manager row stores input schemas only, so the newest output schema I could check is 104.1.0. The read fails closed: a renamed field reads UNDETERMINED, and READ_PATH_MISSING is filed.
3. **Expiry reasons can wait behind failures.** An agent that keeps producing unread FAILED reasons delays its expiry reasons, and with them the expiring alert. Each one waits at most until the failures on the 10-row page settle. This is deliberate, to keep the fail watch's latency.
4. **One status alert per agent after the deploy.** EXPIRED is now an entry outcome, so an agent whose newest outcome is EXPIRED gets one debounced informational change, "entry outcome FAILED -> EXPIRED". This is expected.
5. **A deploy step for Hermes.** The halt-watch script must be recopied with `python hermes/install_commander.py --halt-watch`. That is a Hermes profile action, which I did not do.
6. **Rebase first.** Rebase on main (`b6719d2`) before review, to pick up the leverage test-pin fix.
7. **Not verified live: what "entry price" is.** I treat the row's `entryPrice` as the bar close where the limit rests, per the brief. That matches the brief's live facts, but I did not cross-check it against a live `list_agent_open_orders` `limitPrice`, which would mean calling BattleGrid. The status now shows both, so the first live resting entry will confirm or refute it.

## Review round (2026-10-20, about 12:00Z)

The coordinator's verdict was SHIP, with two fixes. Both are in commit 8d2cae6.

1. **The expiry post says "withdrew" only when a served expiry code other than TIME is in the streak.**
   - The codes UNREADABLE, UNREAD and NOT_SERVED are now treated as unread, never guessed.
   - If every reason is unread, the post says "Why it expired was not read... the reason is unknown".
   - If TIME is mixed with unread reasons, it keeps the TIME wording and adds "Some expiry reasons in the streak were
     not read."
   - Test: `test_an_expiry_post_says_withdrew_only_for_a_served_code_other_than_time_and_unread_reasons_are_said_unread`.
2. **The status-change alert compares FAILED and EXPIRED as one `NOT_FILLED` value** (`entry_value` in
   `agent_status.py`).
   - An old stored baseline "FAILED" is normalised the same way, so the deploy files no one-off change.
   - The change text reads "entry outcome EXECUTED -> NOT_FILLED (FAILED)".
   - The summary line ("last entry EXPIRED TIME") and the 24 h counts still keep FAILED and EXPIRED apart.
   - Test: `test_an_entry_outcome_toggling_between_failed_and_expired_posts_no_change`. The old pin for EXECUTED <-> FAILED
     was updated.

**Rebase.** The branch is rebased onto main b6719d2, which brings the leverage-pin fix. New commits: 3e1c302, a2d7643,
1cd0cc7, 12f1ab3, 8f1d572, 59ce10c, 8d2cae6.

**Suite.**
- Affected files: 61 passed.
- The full run (no -x) has 4746 passed, 5 skipped, 0 failed. It ran with the branch's pinned OMEGA tree first on the
  path: `PYTHONPATH=.omega/v0.8.2`.
- Without that, 21 tests fail: `tests/authoring/test_pin.py`, `tests/commands/test_strategy.py` and
  `tests/strategist/test_direction.py`.
  - The cause: the shared venv now resolves OMEGA **v0.8.3**, installed into `battlegrid-manager/.omega/v0.8.3` at
    about 18:20 local time by another session.
  - The branch pins v0.8.2. `test_direction` fails on main b7ab259 for the same reason.
- This is environment drift, not E3. I did not change the shared venv. Whoever lands the v0.8.3 pin, or the E1/E2
  merge, should re-run without the override.
