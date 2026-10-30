# Verification record: close-rule experiments (lever D, design step 5) — 2026-10-30

Plan: `docs/superpowers/plans/2026-10-31-close-rule-experiments.md` (executed subagent-driven, the user's choice).
Spec: `docs/superpowers/specs/2026-10-27-decision-learning-loop-design.md`, step 5.
Code: battlegrid-manager branch `feat/experiments-d` (0846700..8d93c9b, 7 tasks, 11 commits), fast-forwarded to
main and pushed 10-30 ~21:55Z; the manager's own record is `docs/status/2026-10-30-experiments-first-run.md`.
Times are stored UTC instants; written 22:01Z.

## Execution

| task | commits | review |
|---|---|---|
| 1 rule specs (`to_spec`/`from_spec`/`spec_hash`) | 7645b15, ed3ad8b | clean after one fix (TypeError -> ValueError) |
| 2 replay from the database (`positions_from_db`, `trade_from_outcome`) | cb3693d | clean |
| 3 grid, holdout, deltas, verdict | fd83694 | clean |
| 4 `experiments` table, writer, supersession | 52fa183, 6d93e32 | one fix round (supersede on a later verdict) |
| 5 job, compose service, CLI | 94fdc5e, 6d17e67 | one fix round (`init_db` out of the CLI; `--spec` is not the week's build) |
| 6 report section, API keys | 1393ff0 | clean |
| final whole-branch review (fable) | 8d93c9b | 1 Critical (one-agent fleet failed the agent check on last-bit rounding: `fsum` + 1e-9), 2 Important (a quiet week hid OPEN proposals; supersession too broad), 1 plan defect (dry run before the table existed), 6 minors; one fix wave, re-review (opus) clean, two new minors parked |

Full suite: 5725 passed at 1393ff0, 5735 passed / 6 skipped at 8d93c9b (20:14). The SDD workspace was deleted
after the clean re-review; its ledger's rulings are below.

## Live verification (Task 7)

- `docker ps`: 20 manager containers on main-436abf0; `contract status`: live 144.2.0, acked (watch self-clear
  06:58:34Z), writes open.
- Image `battlegrid-manager:main-8d93c9b` (78eed08a68c4) built from the branch head; `gated_deploy.sh main-8d93c9b 24`
  armed 21:55:08Z, first check OK (flat, writes open, minute 55), DEPLOY DONE 21:56:31Z, all 20 services on the new
  id, restarts 0.
- `experiments` table created by `init_db` on service start; the job's first tick built window
  `2026-09-19..2026-10-29/118/s0.05`: 23 run, 0 skipped, 0 accepted over 118 positions (beat 21:56:48Z). Every
  candidate INSUFFICIENT on `n_affected` (max 29, floor 30); the three `profit_r` variants affect zero positions (the
  profit threshold gates only MOMENTUM_STALL; 75 of 5647 triage rows sit at or above +1R).
- One-off container dry run 21:59:32Z: 0 run, 23 skipped (identity skip held). `/api/learn/latest` serves
  `experimentsBuiltAt` and `openProposals` (0). `manager experiments show` renders the 23 lines and the Baseline line.
- Other jobs' beats ok on the new image by 22:00Z; `snapshot` not-ok is the standing Normandy `MKT_DOWN` error.

## Rulings made during execution (reported to the user)

1. `positions_from_db` reads `trade_outcomes` with a plain SELECT after `export_read_only` returns — the kernel's
   read-only export cannot be extended without changing its contract — cost if wrong: a stale trade row at most.
2. Identity = `spec_hash(parsed.to_spec())`, never a caller dict — the grid's `loss_r_1.0` and a user's `{"loss_r": 1}`
   must be one experiment — cost if wrong: a duplicate row per spelling.
3. Stress pairs candidate@0.10R with baseline@0.10R — "holds under worse execution" judges both sides — cost if
   wrong: a candidate that closes more often judged ~0.05R per close too kindly.
4. `opened_at` always passed to `deltas`, never NULL in a stored row — cost: none.
5. Supersession and the week's build record only on a canonical run (grid, no `--since`, default slippage); only
   ACCEPTED/REJECTED supersede, never INSUFFICIENT; `slippage_r` stored and in `window_key` — an inconclusive or
   narrowed later run must not retract an accepted proposal — cost if wrong: an OPEN proposal stays open a week longer.
6. `run_experiments` discards uncommitted session state; the job runs it alone — cost: none.
7. `--spec` user runs are not the week's build and bypass the due gate — cost if wrong: a user spec run twice in a
   week re-runs nothing.
8. Task 7 reordered: deploy first, then the one-off dry run — cost: none.
9. Parked without a second fix wave: a hand run whose spec and window equal the grid's takes the slot until the window
   moves; non-canonical OPEN rows list under "Open proposals from earlier builds" (wording).

## What is not done

- Design step 6 (`rule_versions`, `manager review take` on PROPOSE_RULE_VERSION) and step 8 (the analyst) — nothing can
  apply a rule; the loop is report-first as decided.
- Follow-up from ruling 9: carry the canonical flag in the skip key.
- The next canonical build is Monday 2026-11-02 after the 01:00Z scorecards, on whatever window the openings make.
