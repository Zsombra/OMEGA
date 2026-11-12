# E5 report: Commander and skills (parity epic)

Written 2026-10-20T11:26Z. Worktree `C:/tmp-bgm-e5`, branch `feat/parity-skills`, from main `f1f2746`.
Nothing merged, pushed or deployed. No BattleGrid call. Docker was touched only for read-only psql on
`system_state`.

## Status

**DONE.** Every E5 item is implemented and tested.

## Commits (oldest first)

| Commit | What it does |
|---|---|
| `263046c` | Refreshes the vendored skill pack to 32.0.18 (battlegrid-mcp `ef1acf9ed8d4787d2d948d392d8e8b18ca2604fe`, skills exported at contract 122.0.0). |
| `514956c` | Corrects the Commander's stale Radar rules: daily trades, one position, score, close outcomes. |
| `07bf82a` | Radar views: removes the score column, explains every close outcome, and stops gate blocks printing "None total". |
| `3a1b17c` | Proxy allowlist: drops the four tools v99 removed, adds nine reads (89 -> 94), and adds the 123.0.0 fixture. |
| `ddbb212` | Cap: matches the documented `RESULT_TOO_LARGE` code. |
| `f83bdf8` | Rewraps a string in `decisions.py` so the watch test does not read it as a tool name. |
| `d78e2c9` | Commander: adds the officers paragraph and the v123 note. |
| `a26c9be` | Rewraps a comment in `policy.py`. |
| `fa3c475` | Updates the numbers test: report and decisions no longer format a number. |

## What was done

### Skill pack
- **Source and hash check.** Every tracked file of the vendor repo was taken from its git blobs (LF) with
  `git -c core.autocrlf=false archive HEAD`.
  - All 19 skill files matched their sha256 in `skills/EXPORT.json` before they were copied.
  - The working-tree copies are CRLF and match only after line-ending normalisation, so they were not used.
- **Same shape as the 31.2.108 refresh** (`df855aa`): the whole repo goes into `.agents/skills/battlegrid/`.
  - Added: `battlegrid-officers` (SKILL.md and its reference file) and `src/__tests__/connect-retry.test.ts`.
  - Nothing was removed.
- **`skills-lock.json`** now carries `computedHash` `4d6e99cc…8236`.
  - Method: sha256 over a CRLF view of the tree, paths sorted with a localeCompare-like order, path then bytes.
  - Check: the same method run on the old tree reproduces the old lock hash `2e5c05a5…` exactly.
- **`hermes/install_commander.py:92`** points at `.agents/skills/battlegrid/skills` with no version pin, so it needed
  no change.
- **v123 note:** added to `hermes/skills/battlegrid-manager/SKILL.md`. The 122.0.0 skills predate v123's header
  renames, so the live read wins.

### Fixes
1. **Daily trades.** The rule now says "filled + waiting entries (since 77.1.0); refused and expired entries do not
   count", in `SKILL.md` and the `manager_radar_decisions` description in `native.py`.
2. **Score and "one position".**
   - Score / min is removed from `plugin.js`, `SKILL.md` and `native.py`, and from the views in `decisions.py`,
     `report.py` and `fleet.py`.
   - The stored DB columns and `normalize` are kept as recorded history.
   - "One position per agent" is replaced: margin headroom decides, and a second entry was attempted on 10-19.
3. **Gate blocks.**
   - The snapshot now also stores `pageEntries` and `morePages` (from `nextCursor`). `/nextCursor` is added to
     `READ_SETS`.
   - The view prints the platform total when one is served. Otherwise it prints "first page: N entries, more pages /
     no further page; total not provided since contract 113.0.0".
   - An older snapshot prints "total not provided by the platform since contract 113.0.0".
4. **Close outcomes.**
   - `decisions.py` explains FIRED, CLAIMED and MISSED. FIRED points to `fireDisposition` in
     `get_radar_close_decisions`.
   - The snapshot's `closeDecision.last` does not carry `fireDisposition`: its schema has only `barStart`,
     `barCloseAt`, `decidedAt`, `outcome` and `gate`. So it is not stored. The Commander is told where to read it.
   - The texts in `SKILL.md`, `native.py`, `report.py` and `plugin.js` name all four outcomes.
5. **Allowlist.**
   - The stored live surface (`surface_tools`, contract 123.0.0, observed 11:00Z, 158 tools) was checked first. The
     four v99 tools were absent, and they were the only absent allowlisted names.
   - The four were removed, and the `before` comment now says `cursor` / `nextCursor`.
   - The nine reads were added. Each is readOnlyHint true and destructiveHint false in that surface.
   - No write was added. A test pins that every officer write stays off, and so do `get_officer_draft` and
     `list_officer_drafts`.
   - New fixture: `tests/fixtures/2026-10-20-surface-123.0.0/tool_annotations_123.0.0.json` (names and annotations
     only).
6. **Cap.**
   - `is_over_cap` now matches code `RESULT_TOO_LARGE` or `details.limit: "result_chars"`.
   - The size and cap figures fall back to `details.actual` / `details.maximum`.
   - A write answered this way stays UNKNOWN.
7. **Officers paragraph** in the Commander `SKILL.md`. The Commander may read and explain officers, and never
   applies, pushes or dismisses a proposal, nor stages, runs or archives an officer.

## Tests

- **Full run:** 4733 passed, 6 failed, 5 skipped.
- **After that run:** one of the 6 (`tests/test_numbers.py`, caused by this branch) was fixed in `fa3c475`. That file
  passes now; the suite was not re-run in full after the fix.
- **The other 5 also fail on base `f1f2746`** (run in a temporary worktree of the base, since removed). They are not
  caused by this branch:
  - 4 in `tests/api/test_app.py`, the policy endpoints: the `max_leverage` bound `hi` is "3", the tests expect "2";
  - `tests/commands/test_policy.py::test_cli_policy_output_is_pinned_byte_for_byte`: the CLI prints "1..3", the pin
    says "1..2".
  - These look like policy v7 (3x) against stale pins.

## Concerns

- **v123 is live.** `system_state` shows `contract_live` 123.0.0 (build `ad62587`, 11:01Z) while `acknowledged` is
  122.1.0, so writes are presumably blocked until a reviewed ack. E5 does not depend on it.
- **The pack is already one contract behind live.** It was exported at 122.0.0, and the note covers the header
  renames.
- **Lock hash not checked by the real CLI.** The `skills-lock.json` hash comes from my reimplementation of the skills
  CLI's hash. It reproduced the old hash exactly, but the CLI itself was not run.
- **Officers paragraph wording.**
  - It says the account held no officer "when checked on 2026-10-20", as you stated. I did not re-check it: no
    platform call.
  - It also says a proposal touching a deployed agent's `tradingConfig` is the user's decision, because the pool sync
    governs those fields (gap-officers 2.2). The E6 guard is not built yet.
- **Not covered: `fireDisposition` on the dashboards.** It is still not on the snapshot or in the desktop table. Only
  the text says where to read it. Adding it would mean calling `get_radar_close_decisions` from the inventory, which
  is outside E5.
- **Pre-existing failures.** The 5 failing api/CLI tests on main are worth a separate small fix.
