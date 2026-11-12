# E2 report: re-pin OMEGA v0.8.3 and a header-code drift check

Written 2026-10-20, around 11:50Z. Worktree `C:/tmp-bgm-e2`, branch `feat/parity-omega-pin`, based on `f1f2746`. Nothing was merged, pushed or deployed. I did not touch Docker, `.env` or the Hermes profiles. The only network call was to GitHub, for the OMEGA tag. Postgres was read once, read-only, with `psql`.

## Status

Done. The full suite: **4745 passed, 5 skipped, 5 failed**. All 5 failures are max_leverage 1-2 -> 1-3 test pins (4 in `tests/api/test_app.py` and `tests/commands/test_policy.py::test_cli_policy_output_is_pinned_byte_for_byte`). They also fail on the base `f1f2746` (I checked test_app in a detached worktree). Main fixed them after this branch was cut (`20d4fff`, merged as `b6719d2`), and none of those files overlap this branch.

## Commits

| sha | what |
|---|---|
| `95a0913` | Pin OMEGA v0.8.3 (tag, commit, sha256, archive path); updates vendor/README, the Dockerfile comment and every test that pinned v0.8.2 |
| `3eb1b40` | Direction glossary keyed by the v123 codes |
| `33023dd` | Header-code drift check: probe, cache, `header_drift`, CLI and tab wiring |
| `996b935` | Stale never-sent plans: `stale_reason` column, `manager strategy stale [--mark]`, refusal at propose and describe |
| `c4ad269` | Runbook: the pin is v0.8.3 |

## 1. Pin

- **Values:**
  - `OMEGA_TAG = "v0.8.3"`
  - `OMEGA_COMMIT = "a5634c2498acb0db48009a1d19114891a634b58c"` (`git ls-remote`: `refs/tags/v0.8.3` is tag object `e94c1c8d…`, `^{}` is `a5634c2…`)
  - `OMEGA_SHA256 = "b284197c8a981237235f1bd0aa24624326cf5763df1833c2ab142752a6871f56"`
- **The archive:** GitHub's tag tarball, 4,373,296 bytes. Two downloads gave the same hash. It is at `C:/tmp-bgm-e2/vendor/omega-v0.8.3.tar.gz` (gitignored).
- **Dev venv:** installed with `scripts/install_omega.py <main checkout>/.omega/v0.8.3 --from vendor/omega-v0.8.3.tar.gz`. The shared `.venv` now imports omega from `.omega/v0.8.3`.
- **Tests against it:** the authoring, strategist, allocation and strategy-command tests all passed against the new tree. The one exception was the glossary test, fixed in `3eb1b40`.
- The tree's `_manifest.json` still says `servedContractVersion 110.8.0` and write surface 110.13.0, as E1 noted. The manifest test is unchanged.

## 2. Header-code drift (`manager/authoring/headers.py`, `preflight.header_drift`)

- **What is stored:** read-only psql of `system_state` `surface` (15 KB), `surface_tools` (294 KB, 123.0.0 at 11:20:28Z) and `manager_schemas` (716 KB). None of them holds a header code: `ADX14`, `pctB20`, `ATR14`, `bbUpper20`, `ADX_now` and `pctB_now` each appear 0 times. `RSI14` matches only as a metric KEY in the metric enums, and the stored `get_strategy_column_contract` input schema holds only key enums. So I added a probe.
- **The probe:**
  - It calls `get_strategy_column_contract({column, anchorTimeframe})` once per distinct custom column on the plan's REPORT axis, at plan time only. It reads `contract.outputs[].header`, the shape of OMEGA's captures.
  - At most 24 calls per plan.
  - Answers are cached in `system_state["header_contract"]` for the live (contractVersion, buildSha). A cache from another build is dropped. A failed or malformed answer is never cached.
- **The check:**
  - Compares `omega.fanout.outputs_for` for each column with the served headers.
  - Any difference is the error `HEADER_CODE_MOVED`, naming the header, e.g. "header ADX_now: OMEGA v0.8.3 emits it …; the platform serves ADX14_now".
  - A condition clause on a code OMEGA's v123 table retires is also `HEADER_CODE_MOVED`.
- **Fails closed:**
  - No probe, a probe that raises, an unread column, or a column past the bound is the error `HEADER_UNVERIFIED`. The plan is a FAIL, and `propose_user_stage` and describe already refuse a non-PASS plan.
  - The probe runs only once the build and surface checks pass. A stale or unread build already fails the plan.
- **Wiring:**
  - `pipeline.build(..., header_probe=)`.
  - The CLI `strategy plan` builds its READ client lazily, only when a column is not cached.
  - The Strategy tab's answer route reads through the api gateway: `turn.header_reads` plus `anyio.from_thread.run(platform.call, …)`.
- **Live measurements:** OMEGA v0.8.3 predicts all five 4h measurements exactly. They are pinned in `tests/authoring/test_headers.py`.
- **New tests:** `test_headers.py` (15), a CLI unverified case, CLI caching (the second plan builds no client), and the relay route's gateway read.

## 3. Glossary

`direction.py` now uses `pctB20_now`, `ADX14_now` ("ADX 14") and `ATR14_trend` ("ATR 14 trend"). A test checks that every glossary key is already its own v123 form under `header_since_123`.

## 4. Stale plans

- **Live state** (read-only, evaluated offline with the new rule): 66 plans. Plans 2, 3, 5, 6 and 8 were sent (STAGE_STRATEGY DONE).
- **29 were never sent and name a retired code:** ids 1, 4, 7, 9, 10, 12, 13, 15, 19, 21–23, 30–32, 35, 40, 41, 44, 47–49, 52, 55–58, 63, 65.
  - Retired codes they name: `pctB_now` 18, `ADX_now` 13, `ATR_trend` 5.
  - 25 are PASS and 4 are FAIL.
  - All of them are already unsendable: they were planned with the old OMEGA sha and an old build.
- **"Sent"** means a STAGE_STRATEGY action for the plan in PERFORMING, VERIFYING, UNKNOWN, DONE or FAILED. Plan 7 has only a REFUSED action, so it counts as never sent.
- **The CLI:** `manager strategy stale` lists them. `--mark` writes `strategy_plans.stale_reason` plus a `strategy.plan_stale` ledger event per plan. Nothing is deleted, and verdicts and checks are not rewritten. `list` and `show` print the mark.
- **Not run against live:** I did not run the CLI there, because its `init_db` would ALTER the live table.

## Concerns

1. **`get_strategy_column_contract` is NOT in `MANAGER_TOOLS`.** It is a new `preflight.PLAN_TIME_READS` exemption, and the test that every tool named in code is watched allows it.
   - Why: the probe guards itself. Any input or output move can only make a plan fail as UNVERIFIED.
   - Putting it under D7c would block every write, including SYNC_LIMITS, on a change that can only fail a plan closed. It would also break 12 historical-replay tests.
   - This needs the reviewer's agreement. The alternative is MANAGER_TOOLS plus a READ_SETS entry `/contract/outputs[]/header`, with a backfill or ack after deploy.
2. **Platform sections and ambient headers are not probed.** The column contract serves only custom columns. A clause header from a platform section passes this check unless OMEGA's v123 table recognises it as retired.
3. **First plan per build:** about 6–9 reads at the 3 req/s bucket (a few seconds) in the tab's answer request and in the CLI. After that they come from the cache.
4. **Deploy notes:**
   - `init_db` adds `strategy_plans.stale_reason` (one ALTER, only if the column is missing).
   - After deploy, run `manager strategy stale --mark` to mark the 29 plans. That is a write to the database, so it is the operator's call.
   - The image build should download the tag (the sha256 is verified), or use `--build-arg OMEGA_FROM=vendor/omega-v0.8.3.tar.gz` with the archive placed in the main checkout's `vendor/`. It is only in the worktree's `vendor/` now.
5. **The shared dev venv points at v0.8.3.** The main checkout (pin v0.8.2) will fail `require_pin` and its pin tests until this merges. To revert: `.venv/Scripts/python.exe -m pip install --no-deps -e .omega/v0.8.2`.
6. **Main has moved** to `b6719d2` (test-only leverage pins). There are no overlapping files, so this branch should merge cleanly.
7. **The probe has never been called against BattleGrid.** Its request shape (`{column, anchorTimeframe}`) and answer shape come from OMEGA's captures and the stored 123.0.0 input schema. The first live plan is its first real use; if the shape is wrong, the plan fails closed as HEADER_UNVERIFIED.
