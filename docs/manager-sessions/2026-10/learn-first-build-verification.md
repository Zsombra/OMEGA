# Learning loop, first build: verification record (2026-10-27)

Branch `feat/learn-loop-1` in battlegrid-manager (19 commits on main `6e12804`, head `31446fa`), merged as
PR #1 on the user's word at 2026-10-28 14:10Z (main `353dc40`); not deployed. Plan:
`docs/superpowers/plans/2026-10-27-decision-learning-first-build.md`; spec:
`docs/superpowers/specs/2026-10-27-decision-learning-loop-design.md`. This is Task 13 of the plan.

Every instant below is the stored UTC instant from the command that produced it.

## Steps 1 and 2: from the database alone (done)

The manager was blind (refresh token revoked) and the branch is not deployed, so the commands ran in a
one-off container built from the branch (`battlegrid-manager:learn-31446fa`, the vendored OMEGA archive)
on the compose network against the live Postgres. The running stack was not touched; the eight new
tables were created by `init_db` as a deploy would create them.

| Command | Result |
|---|---|
| `learn backfill --trades /fixture/trades.json` | 128 new, 0 updated; the fixture's 8-character agent ids resolved to the six full ids (no prefix keys left) |
| `learn label` | graded 108; pending 110, 111, 112 (`no_outcome`: the trades were not in the 10-26 fixture); 6 positions excluded by the replay (4 "no cached trade", 2 "no decided stop", among them decision 98's PURR trade, whose \|grossR\| of 0.043 is too small to derive a stop) |
| `learn score --now` | 82 scorecard rows at 19:24:23Z; trades: 8 NO_EDGE, 35 INSUFFICIENT, 0 EDGE; decisions: 6 EDGE, 33 INSUFFICIENT |
| `learn show` | the report renders: no trade slice has an edge; `close_reason=INVALIDATION` n=23 mean -1.51R CI [-1.64, -1.39]; VWAP Sentinel 15m n=26 mean -0.73R; `outcome=CLOSE` n=85 mean delta +0.40R CI [+0.33, +0.47] EDGE; `outcome=HOLD` 2 GOOD / 14 BAD (n=19, INSUFFICIENT) |

Note for the deploy: the image carries no `tests/` directory, so `learn backfill` needs `--trades` with
the fixture mounted; the default path does not exist in a container.

### The grades against the 2026-10-26 close-decisions report

The first run graded at a 0.25R margin and put decision 100 at UNCLEAR (+0.22R) where the report said
GOOD. The report's own grading implies a margin between its UNCLEAR at +0.13R and its GOOD at +0.22R,
so the margin was set to 0.2R and the method version bumped to 2 (commit `31446fa`); every decision was
re-graded. After that:

| Decision | Report | Ours (method 2) | delta R | plan_unreliable | Match |
|---|---|---|---|---|---|
| 85 | GOOD | GOOD | +0.26 | yes | yes |
| 86 | GOOD | GOOD | +1.37 | no | yes |
| 87 | GOOD (by candles) | GOOD | +1.24 | yes | flagged, as spec 11.1 expects |
| 90 | GOOD | GOOD | +1.23 | no | yes |
| 91 | BAD (by candles; plan says GOOD) | GOOD | +0.70 | yes | flagged, as expected |
| 93 | GOOD | GOOD | +0.35 | no | yes |
| 95 | UNCLEAR (by candles) | GOOD | +0.55 | yes | flagged, as expected |
| 97 | GOOD (by candles) | GOOD | +1.25 | yes | flagged, as expected |
| 98 | GOOD (by candles) | excluded | n/a | n/a | no decided stop derivable from the fixture |
| 99 | GOOD in reality (plan says BAD) | BAD | -0.68 | yes | flagged, as expected |
| 100 | GOOD | GOOD | +0.22 | no | yes (after the margin change) |
| 102 | GOOD | GOOD | +0.63 | no | yes |
| 103 | GOOD | GOOD | +0.66 | yes | yes |
| 104 | GOOD | GOOD | +0.66 | no | yes |
| 105 | GOOD | GOOD | +0.32 | no | yes |
| 106 | UNCLEAR (+0.10R vs plan) | UNCLEAR | +0.13 | no | yes |
| 107 | UNCLEAR (-0.03R vs plan) | UNCLEAR | +0.02 | no | yes |
| 108 | BAD so far (running) | GOOD | +0.33 | no | the trade has since closed |
| 109 | BAD so far (running) | BAD | -0.22 | no | the trade has since closed |

Pass condition met: every decision the report graded from plan data matches, and the six it re-graded by
hand against candles carry `plan_unreliable = true` or are excluded.

Grade counts over all 108: GOOD 68, BAD 25, UNCLEAR 15.

## Steps 3 and 4: live reads and deploy (blocked)

Blocked on the user: the manager has been blind since 2026-10-26 09:53Z (`HTTP 400 invalid_grant`, the
fix is `manager auth login`), the live contract moved to 137.5.0 against an acknowledged 135.2.0, and
writes have been blocked since 2026-10-27 18:27Z. The 136 to 137.5 review is its own task. After the
login and that review:

1. `manager learn probe --out ...` captures the first live page of every read the loop uses; every
   served field name in `manager/learn/*` is pinned from tool descriptions or the stored 132.0.0 schema
   and has never been seen live. A wrong pin shows as an error line or a NULL column, never a wrong row.
2. `manager learn collect`, then `manager learn platform --now`.
3. Deploy through the guarded chain. On the first clean watch tick the eight new `MANAGER_TOOLS`
   names are backfilled into the acknowledged schemas; a drift overlapping the deploy needs one
   `manager contract ack`.

## Test suite

Full suite at `e85e378` (before the final-review fix wave): 5597 passed, 5 skipped, 4 pre-existing
warnings, 733 s. Full suite after the fix wave (`4093388`): 5629 passed, 5 skipped, 0 failed, the same
4 warnings, 743 s. `tests/learn` at `31446fa` (the margin change): 177 passed, no warnings.
