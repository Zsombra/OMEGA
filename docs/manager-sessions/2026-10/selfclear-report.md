# Self-clear report: the manager leaves SAFE mode and write blocks by itself once verified (2026-10-19)

Worktree `C:/tmp-bgm-selfclear`, branch `feat/self-clear` from main 4b4eb50. Nothing merged, pushed or deployed. No
BattleGrid call; read-only psql only.

## Commits

- `848fa13` Self-clear core + SAFE exit after two good probes (watch.py, jobs.py, settings.py, triage/review.py, tests)
- `0488fc6` Self-clear (a): a manager tool the acknowledged baseline never recorded (served by the acknowledged build) is
  named, not compared, and does not stop the clear
- `88256de` Visibility: Hermes cleared post, daily-report NOTABLE, runbook, Commander SOUL.md, manager SKILL.md

## What was built

### 1. Write block self-clear (`manager/platform/watch.py` `self_clear_verdict`, `manager/scheduler/jobs.py` `_self_clear`)

On every watch run where `writes_blocked.blocked` was already true at the start of the run, the CURRENT observation is
judged against the last ACKNOWLEDGED contract (`system_state.contract`) and baseline (`manager_schemas_acked`), ignoring
the drift that set the block.

- **(a) identical:** version AND build equal the acknowledged ones, the listing was fully read (hash version 3), and
  every `MANAGER_TOOLS` schema the baseline records is served and equal in all four parts (description, input, output,
  annotations). Only the block clears; `contract` is untouched. `verified = "identical to acknowledged"`.
- **(b) a move from the acknowledged contract:** a synthetic drift is built from the baseline to the current schemas
  (manager tools only) and judged by the existing D7b (`auto_ack_refusal`), then D7c (`field_safe_refusal`, with read
  sets and read-only description waivers). If accepted: `contract` = current version/build (`by: watch-self-clear`),
  the baseline is rewritten, the block clears. If refused: the block stays; `reason` becomes
  `contract <acked> -> <current>, build ... -> ...` (the drift push still parses the target), `autoAckRefused` =
  `self-clear against the acknowledged <acked> refused: <why>`, `blockedBy` keeps the reason the block began with,
  `selfClear` holds the refusal.
- **D7 is never used in the self-clear**: it judges every served tool and the acknowledged state of tools the manager
  never calls is not stored. A same-version build move goes to D7c instead, which ignores those tools anyway.
- **Never clears on:** an unreadable listing; a failed version probe (a failed `observe` resets the count); SAFE mode
  true; no acknowledged contract; a missing baseline or one of another contract; for (b), any manager tool the
  baseline does not record.
- **Stability:** `SELF_CLEAR_CONFIRMATIONS = 2`. The pending count lives in `system_state.self_clear_pending`
  (a fingerprint of version, build, the full tool-hash map, the manager schemas hash, plus the block's `since`). A
  different qualifying state counts again from one, and any non-qualifying run resets it (`contract.self_clear_reset`).
  The first qualifying run records `contract.self_clear_pending`.
- **On clear:** `contract.self_cleared` is ledgered with `verified`, `rule`, `observed`, `acknowledged`,
  `from_block_reason`, `confirmations`, and `fieldChanges` / `unrecordedInBaseline` where they apply. The run also
  writes `writes_blocked.selfCleared`, settles the drift's RED-only `CONTRACT_DRIFT` alerts the same way an ack does
  (`settle_drift_alerts(..., by=...)`), and raises an unacknowledged `CONTRACT_BLOCK_SELF_CLEARED` alert.
- **Kill switch:** `WATCH_SELF_CLEAR` (default true) in `manager/settings.py`. `.env` is untouched.
- **Unchanged:** the user's `manager contract ack` (tested), deploy-check and the guards. A drift stacking on a
  pending block now carries `blockedBy` in the normal path too.

### 2. SAFE exit (`job_health`)

`SAFE_EXIT_CONFIRMATIONS = 2` consecutive good probes. A failure in between resets `okProbes`. `safe.exit` now carries
`confirmations` and `since`. Entry is still immediate. The `safe` row is still written on every good probe when not
SAFE, because deploy-check and `mode` refuse a row that was never written.

### 3. Visibility

- **Hermes** `battlegrid_contract_watch.py`: the cleared post says "a SELF-clear of the block", what began it, and
  what was verified. The block post adds one sentence saying the watch clears only after verifying on two runs.
- **Daily report:** `contract.self_cleared` is in NOTABLE.
- **Docs:** the watch.py D7c docstring (the old "a block awaiting the user stays blocked"), the runbook (a new
  section, the D7c paragraph, the contract-watch and `/health` lines), `hermes/commander/SOUL.md` and
  `hermes/skills/battlegrid-manager/SKILL.md` (repo copies only; no live Hermes profile was touched).

## Tests

`tests/platform/test_watch_self_clear.py` (22 tests) covers:
- **(a) today's case:** 120.2.0 is acknowledged; 113.0.0 is served with an unreadable listing and blocks with "not
  comparable"; 113.0.0 then becomes readable and is refused, with the reason naming it; the platform returns to
  120.2.0. After one run the block stands with count 1; after the second it is cleared.
- **The same case with a baseline lacking a served manager tool** (the live shape) also clears, names the tool in
  `unrecordedInBaseline`, and does not add it to the baseline.
- **(b):**
  - A safe move after an unsafe block is acknowledged by D7c on run 2.
  - An untouched move is acknowledged by D7b.
  - An unsafe move stays blocked and names why.
- **Never clears:** an unreadable listing, a missing baseline, SAFE, or the switch off.
- **Flapping and confirmations:**
  - good / unreadable / good / probe failure / good is never two in a row.
  - A different qualifying state restarts the count.
  - One confirmation is not enough; two are.
- **Pure verdict cases:**
  - Same build with different schemas refuses.
  - A baseline tool that is no longer served refuses.
  - A baseline of a foreign contract refuses.
  - No acknowledged contract refuses.
  - A tool the baseline does not record refuses under (b).
  - Auto-ack off refuses.
  - A same-version build move goes to D7c.
- **User ack:** `manager contract ack` still clears a pending block (CLI on a file DB), and the next run stays open.

Elsewhere:
- **SAFE:** `tests/scheduler/test_jobs.py` covers one success between failures (no exit) against two in a row (exit,
  `confirmations == 2`), immediate re-entry, and the `safe` row written on a first good probe.
- **Hermes:** the self-clear post in `tests/hermes/test_contract_watch.py`.
- **Daily report:** a NOTABLE test in `tests/inventory/test_daily.py`.
- **Updated:** `test_health_enters_safe_once_and_exits` (two probes to exit), and the stacking-case docstring in
  `test_watch_d7c.py` (one run still never clears).

Full suite after the first three commits: 4611 passed, 5 skipped (10 min). The count after the refinement is at the
end of this file.

## Live check (read-only, 05:25Z)

I copied the live `system_state` rows to the scratchpad and ran the new verdict on them:
- **Now:** writes are blocked, since 05:24:24Z. The reason is `contract 113.0.0 -> 120.3.0`; the platform now serves
  **120.3.0** build e77e51f0, but the tool list was unreadable (SSE stream ended). Verdict: refused, "the tool list was
  not fully read". The block stays, as intended.
- **113.0.0 served readable:** refused under (b), because the acknowledged baseline does not record
  `list_entry_decisions`. It stays for the user.
- **120.2.0 served again** with the acknowledged schemas plus `list_entry_decisions`: (a) identical, so it would clear
  after two runs.

## Concerns

1. **(Resolved live)** The 120.2.0 baseline (02:45Z) lacked `list_entry_decisions`, so any (b) self-clear would have
   refused until a user ack. Someone has since acknowledged 120.3.0: read at 05:50Z, `contract` shows 120.3.0 at
   05:38:31Z, and the baseline is `by: user` and holds the tool. Writes are open.
2. **Judgement call in (a).** A manager tool the baseline never recorded, served by the acknowledged version AND build,
   is accepted without comparison, and is named in the ledger. It rests on the premise `_keep_schemas`' seed already
   uses: version + build identical means the acknowledged surface. Strict equality would have kept today's block
   forever. If you want it strict, change one line in `self_clear_verdict` (refuse when `unrecorded` is non-empty).
3. **Tools the manager never calls are not compared in (a).** The acknowledged full-surface tool hashes are not
   stored, so only the manager's tools are compared ("at minimum every manager-called tool's schema", as the brief
   allows). Storing an acked surface hash map would let (a) check every tool and allow D7 in (b).
4. **Timing.** The watch runs every 600 s, so a self-clear takes about 10-20 min after the platform is back. A SAFE
   run resets the count, so after an outage it takes SAFE's two probes (about 2 min) plus two watch runs.
5. **Wording.** `test_a_build_only_redeploy_never_clears_a_block_still_awaiting_the_user` (test_watch.py) still passes
   because it runs one watch. Its name is now true only for one run.
6. **Push wording.** The drift push (`notify/drift.py`) still says "Review the drift, then: manager contract ack X".
   It was left unchanged because the brief did not list it.
7. **Line endings.** One commit-time CRLF warning on jobs.py came from a scripted edit. The index is LF and the
   working copy was normalized.

## Ruling refinement: DIAGNOSE -> REMEDIATE -> RE-VERIFY -> CLEAR (commit `850c875`)

The user: "the block feature is basically to let us know that there's an issue. We need to find out what the issue is
and fix it." What was already built stays. The self-clear is now driven by a cause.

**Cause record.** `manager/platform/diagnose.py` builds the cause from evidence on every watch run while a block
stands, including the run that set it.
- **Where it lives:** `writes_blocked.cause`, with `class`, `origin`, `evidence`, `diagnosis`, `remediation[]`,
  `needs` and `needsYou`.
- **Across stacked drifts:** a drift stacking on a block keeps the block's `startedAt` and its cause record.
- **Classes:**
  - **OBSERVATION:** the listing was unreadable or not comparable, a probe failed, or the platform was in SAFE.
  - **TRANSIENT_VERSION:** the acknowledged contract came back, after a block that did not begin as an observation
    problem.
  - **SAFE_CHANGE:** the move passes D7b or D7c.
  - **UNREVIEWED_TEXT:** a reworded description, with every other change safe.
  - **BREAKING_FOR_MANAGER:** an unsafe input, output or annotation change, or a removed tool, that the manager reads.
  - **UNVERIFIABLE:** a sixth class I added, because the evidence cannot name one of the five. It covers no
    acknowledged contract or baseline, a manager tool the baseline never recorded, and a hash that moved with no field
    change. It fails closed and needs the user.

**Remediation and re-verification.**
- **OBSERVATION:**
  - `watch.observe` re-lists once on a fresh session after a TRANSPORT, HTTP or AUTH listing failure. The client has
    already dropped the session on those, so the second listing opens a new one.
  - The run then re-records `surface` and `manager_schemas` from that read and re-verifies against the acknowledged
    contract.
  - Each step is ledgered as `contract.remediation {cause, step, result}`, but only when that step's result changes,
    so a 9-hour block is not ledgered every 10 minutes.
  - A listing that heals while nothing is blocked is ledgered too.
- **TRANSIENT_VERSION / SAFE_CHANGE:** as built, with 2 confirmations. `contract.self_cleared`, the
  `CONTRACT_BLOCK_SELF_CLEARED` alert and `writes_blocked.selfCleared` now carry `cause`, `origin` and the
  remediation steps.
- **UNREVIEWED_TEXT:** the diagnosis is a sentence-level unified diff plus the added and removed sentences. The narrow
  rule clears only when all of these hold:
  - every changed sentence is an addition;
  - the tool is readOnlyHint true, its annotations did not move, and it is on no write list;
  - every backticked identifier is a property ADDED in the same move or another served tool's name.

  If the rule holds, the block clears after 2 runs with `rule: narrow-text` and the move is acknowledged. Otherwise the
  block stays, `needsYou` is set, and one `CONTRACT_BLOCK_DIAGNOSED` alert is raised per diagnosis.
- **BREAKING_FOR_MANAGER:** this never clears. The diagnosis lists tool, part, path, change, role (write / write-pipeline
  read / read set) and `readBy`: the modules under `manager/` that name the tool as a string literal, scanned at
  diagnosis time.
- **SAFE:** `safe.cause` is one of three classes:
  - **PLATFORM_OUTAGE:** HTTP 5xx, transport or timeout. It is re-probed every minute.
  - **TOKEN:** AUTH or HTTP 401/403. The manager tries one token refresh per SAFE episode through the new
    `PlatformClient.refresh_auth` (ledgered `safe.remediation`), then re-probes.
  - **PLATFORM_ERROR:** anything else.

  The exit still needs 2 consecutive good probes. `safe.exit` carries the cause and the remediation.
- **Status:**
  - `manager contract status` has a `why` list and `manager mode show` adds lines: cause and evidence, what was tried,
    and "clears when" or "NEEDS YOU".
  - The commander's contract-watch post adds "Blocked because X: ... I did: ... It clears when: ..." or "Needs you
    (X): ...", with the diff or the breaking changes. It posts once more when a standing block's diagnosis changes.
  - The cleared post names the cause and the steps.
- **Docs:** the runbook (a cause table and the narrow rule), Commander SOUL.md and the manager SKILL.md.

**Tests** are in `tests/platform/test_block_causes.py`, plus Hermes and command tests:
- **OBSERVATION, today's 05:24Z case:** 120.3.0 is served with an "SSE stream ended" listing on both tries, so it
  blocks. A dead-session client then fails the first listing and reads on the re-list. It is OBSERVATION on run 1 and
  cleared on run 2, with remediation ledgered and `surface` and `manager_schemas` fresh. When the listing never heals,
  it never clears, and the failed step is ledgered once.
- **TRANSIENT_VERSION:** an unsafe 121 comes back to 120.2.0. It clears as TRANSIENT_VERSION with origin
  BREAKING_FOR_MANAGER.
- **SAFE_CHANGE:** the cause is named while pending ("1 more watch run") and on the clear.
- **UNREVIEWED_TEXT, today's `get_agents_hub` sentence:**
  - Narrow-rule clear after 2 re-verifications; 120.3.0 is acknowledged by `watch-self-clear`.
  - An edited sentence and an unadded identifier both stay, with the diagnosis and one alert.
  - Plain prose that names nothing clears.
  - With a baseline that never recorded `list_entry_decisions`, the block stays (the text passes, the tool cannot be
    compared).
  - The real 120.3.0 wording, which names `review*` and `openOfficerReviewCount`, clears. A `review*` that matches a
    pre-existing property stays.
- **BREAKING_FOR_MANAGER:** 6 runs, never cleared; the diagnosis names `/tradeStats` and the `manager/` modules.
- **UNVERIFIABLE:** no baseline.
- **Pure functions:** the sentence diff, the narrow rule (readOnlyHint, missing added property, write tool) and the
  status lines.
- **SAFE:** a 502 outage gives cause, needs and an exit with cause. A 401 gives TOKEN, with one refresh over 3
  failures.
- **Status and Hermes:** `contract status` `why` and `mode show`; the Hermes cause post, which posts once per diagnosis.

**Live check of the real text (read-only).** I read the 05:34Z `contract.description_changed` event for 120.3.0.
- **The diff:** `get_agents_hub` adds exactly one sentence and removes none.
- **Identifiers:** `review*` and `openOfficerReviewCount`.
- **The narrow rule:** it holds if those five fields were added in the move. As first written, the rule failed on the
  `review*` pattern, so I extended it fail-closed: a pattern passes only when every property it matches on that tool
  was added in the move.
- **What I could not check:** whether the five fields were added in 120.2.0 -> 120.3.0 exactly. The 120.2.0 baseline
  was replaced by the user's 05:38Z ack.

**Full suite after the refinement:** 4630 passed, 5 skipped, 0 failed (9 min 49 s).

### Refinement concerns

1. **The pattern extension.** The narrow rule's `review*` handling goes beyond the literal wording "a property ADDED
   in this same move". It stays fail-closed: every match must be added, and at least one must match. Drop it if you
   want the literal rule; then today's real sentence would stay blocked for the user.
2. **The sixth class, UNVERIFIABLE.** It is not in the ruling's list. Its blocks always need the user.
3. **Token refresh.** `refresh_auth` forces one token grant per SAFE episode, and BattleGrid rotates the refresh
   token on every grant. The health probe is a plain GET, so in practice AUTH comes only as HTTP 401/403 there. The
   refresh path is untested live.
4. **`readBy` is a source scan.** It looks for `"tool"` string literals under `manager/`, excluding the registries. A
   module that builds a tool name dynamically would not be listed.
5. **The extra re-list.** The OBSERVATION re-list runs on every watch run whose first listing fails, blocked or not.
   That is one extra `tools/list` at most per run, and only after a TRANSPORT, HTTP or AUTH failure.

## Fix round 1 (commit `826a11d`)

The independent review said FIX FIRST. Each item below has its tests.

- **HIGH 1: the narrow text rule** (`diagnose.narrow_text_rule`). It now needs all five conditions:
  - (i) additions only;
  - (ii) readOnlyHint true, the annotations unmoved, and the tool on no write list;
  - (iii) every added sentence names, in backticks, at least one property added in the move, matched by full path.
    Added chains come from field_diff's ADDED paths plus every property under them. A bare name counts only if it
    existed nowhere in the tool before the move; a dotted path counts by its full tail;
  - (iv) every backticked identifier is such a property. The other-tool allowance is removed. A pattern counts only
    when it matches at least one property and every chain it matches was added in the move;
  - (v) no behaviour word, matched case-insensitive and whole-word ("no longer" spans whitespace).

  The tests and the live check:
  - **The five reviewer sentences:** each fails, one parametrized test per sentence. Live check: all five fail.
  - **The real 120.3.0 sentence passes.** Tested with the text from the 05:34Z ledger event and the five `summary.*`
    fields added. Checked live against the real 120.3.0 `get_agents_hub` schema, with those five fields removed to
    stand in for the baseline: it holds. The same sentence fails when one `review*` field was not added in the move.
  - **The other conditions:** tests cover full path versus bare name, the dropped other-tool allowance, (iii) per
    sentence, readOnlyHint, and a write tool.
- **HIGH 2: mixed builds.** Each counting watch run now takes 3 version samples. The first is the observation itself;
  the other 2 are fresh probes, `SELF_CLEAR_SAMPLE_GAP_S` = 3 s apart, with no DB session open across them. Every
  sample must equal the observation being verified, or the count resets.
  - **The cause record** now keeps `versionsSeen` (every non-acknowledged version@build seen during the block) and
    `classesSeen`.
  - **The strict count:** an identical clear is strict when any other build was seen, or the origin or any stacked
    cause was BREAKING_FOR_MANAGER or UNVERIFIABLE. Strict means `SELF_CLEAR_STRICT_CONFIRMATIONS` = 3 runs spanning
    `SELF_CLEAR_STRICT_WINDOW_S` = 1800 s. A plain observation block keeps 2.
  - **In practice the strict count almost always applies.** A not-comparable block can only be set by a version or
    build move, which already puts another build in `versionsSeen`. So the 2-run case is reachable only when the block
    record shows no other version, and the test seeds that state directly.
  - **Tests:**
    - Today's 05:24Z 120.3.0 case is strict: 3 quick runs are still blocked and say "spanning at least 30 min"; it
      clears once the window has passed.
    - A Mixed client that alternates builds never clears.
    - TRANSIENT_VERSION after a BREAKING block needs 3 runs.
    - The 03:34Z case needs 3, and the flapping test needs 3.
- **MEDIUM 3: unrecorded tools.**
  - **Backfill:** `_keep_schemas` backfills the unrecorded manager tools into `manager_schemas_acked`
    (`backfilled` list, ledgered `contract.schemas_backfilled`). It does so only while writes are open, nothing
    drifted, the listing is comparable, and the live version+build equal both the acknowledged contract and the
    baseline. Recorded tools are never rewritten.
  - **(a) is strict:** any unrecorded tool refuses, and the cause is UNVERIFIABLE.
  - **Tests:** the backfill itself; a block meeting an unrecorded tool never clears; and a hash-only move on an
    unrecorded tool under the same version and build never clears.
- **MEDIUM 4: no TOKEN cause.** A 401/403 on the unauthenticated probe is now PLATFORM_ERROR.
  `PlatformClient.refresh_auth` and every refresh in the SAFE path are removed, and `job_health` holds no session
  across an await. Test: three 401 probes leave the client's `refresh_auth` uncalled and write no `safe.remediation`.
- **MEDIUM 5: the Hermes key** is now `class|needsYou|origin`, plus a sha256 of the diagnosis only when `needsYou` is
  set. Test: 6 alternating good and bad OBSERVATION runs post once.
- **LOW 6:** SAFE and the kill switch now apply after the narrow-text override. Test: no `self_clear_pending` while
  SAFE.
- **LOW 7:** covered by the full-path matching in 1(iii).
- **LOW 8: lost update.** `_block_unchanged` re-reads `writes_blocked` with `FOR UPDATE` and `populate_existing`
  before any write. If the row is no longer blocked, or its `since` changed, nothing is written and
  `contract.self_clear_skipped` is ledgered. Test: an ack lands mid-run and the user's row stands.
- **LOW 9: the drift push** (`notify/drift.py`) is cause-aware: "Blocked because X: ...; I did: ...; it clears when:
  ..." or "Needs you (X): ...; then ...". Without a cause it keeps the old line. Two tests.
- **Docs:** the runbook table and the narrow rule rewritten; TOKEN removed from the SKILL.md SAFE list.

**Full suite after fix round 1:** 4646 passed, 5 skipped, 0 failed (9 min 52 s).

### Fix round 1 concerns

1. **The strict count dominates in practice.** Most real clears will take at least 30 minutes, about 4 watch runs at
   600 s, plus 2 extra version GETs per counting run.
2. **The behaviour-word list is deliberately blunt.** A future additive sentence using "not" or "only" stays blocked
   for the user, which is the fail-closed direction.
3. **`FOR UPDATE` is a no-op on SQLite.** The test exercises the re-read logic (`populate_existing`), not real row
   locking; that holds on Postgres.

## Round 2 (commit `99e5241`)

**Finding.** The tightened narrow text rule still passed three behaviour sentences:
- "rows with a pending review are omitted";
- "closes for that agent fail";
- "the list is capped at 20 rows".

**Ruling.** The controller ruled that prose cannot be verified by rules, so the auto-clear for reworded text is
removed.

**Code.**
- **Deleted from `diagnose.py`:** `narrow_text_rule`, `NARROW_TEXT_RULE` and `BEHAVIOUR_WORDS`. `diagnose()` returns
  no `narrow` verdict, and the narrow-text override in `jobs._self_clear` is deleted.
- **What remains for reworded text:** UNREVIEWED_TEXT always stays blocked, with `needsYou`, one
  `CONTRACT_BLOCK_DIAGNOSED` alert per diagnosis, and "needs you: ... then `manager contract ack <v>`". No clear path
  for prose is left; a test asserts the narrow-rule symbols are gone.
- **The diagnosis code is kept.** `text_change_diagnosis` gives, per reworded tool:
  - the before/after sentence diff (unified, added, removed);
  - the properties added in the same move, by full path (`addedProperties`);
  - which of them the new text mentions (`mentionsAdded`, by full path; a bare name counts only if it is new
    everywhere in the tool; a pattern counts only if every property it matches was added);
  - the other backticked names (`mentionsOther`);
  - added names that appear anywhere in the added sentences (`addedNamesInText`).
- **Where the diagnosis is shown:** the Hermes post now says "mentions added X; also names Y" in place of the
  rule verdict.
- **Unchanged:** the 2026-10-18 read-only description waiver for tools outside every write list and the write
  pipeline.

**Tests.**
- Nine sentences, parametrized, each run 6 times: the 5 from fix round 1, the 3 from round 2, and the plain
  "carries `reviewStatus` and `reviewedAt`". Each stays blocked with `needsYou` true, the diff, `addedProperties`,
  exactly one alert, no pending or self-cleared event, and the contract not acknowledged.
- **Today's real 120.3.0 sentence:** it is quoted from the 05:34Z ledger event, with its five `summary.*` fields added
  in the same move. The block stays; the diagnosis names `openOfficerReviewCount` and `review*`, and the evidence says
  "mentioning added openOfficerReviewCount, review*".
- An edited sentence plus a name that was not added stays.
- The baseline-never-recorded case stays.
- `text_change_diagnosis` matches by full path, rejecting a bare name that existed elsewhere.
- The SAFE test now uses a SAFE_CHANGE move.
- The Hermes test is updated to the new wording.

**Docs.** The runbook has a new table row and a new paragraph in place of the narrow rule, quoting the three round-2
sentences as the reason. Commander SOUL.md, the manager SKILL.md and the watch.py `field_safe_refusal` docstring all
state that wording changes on tools the manager uses for writes always wait for the user, and why.

**Full suite after round 2:** 4646 passed, 5 skipped, 0 failed (9 min 15 s).

### Round 2 concerns

1. **More acks for the user.** Every reworded description of a write tool or a write-pipeline read (24 reads in
   `WRITE_PIPELINE_READS`) now blocks writes until a manual ack. By the 10-16..10-18 history that may be several times
   a week. The diagnosis makes each ack one step, but the writes stay blocked until someone acts, and the phone push
   fires only while a position is open.

