# Verification record: rule versions (lever D, design step 6) — 2026-11-01

Plan: `docs/superpowers/plans/2026-10-31-rule-versions.md` (executed subagent-driven, the user's choice).
Spec: `docs/superpowers/specs/2026-10-27-decision-learning-loop-design.md`, sections 4.6, 4.7, 4.8, 5, 10 (step 6).
Code: battlegrid-manager branch `feat/rule-versions-6` (ea26ac5..8220141, 7 tasks + two fix waves, 16 commits);
the manager's own record is `docs/status/2026-11-01-rule-versions.md`. Times are stored UTC instants.

## Execution

| task | commits | review |
|---|---|---|
| 1 `rule_versions` table + module (bounds, init, propose, apply, supersede) | c6ec740 | clean |
| 2 the tick and the grid read the version in force (`/r<id>` key, `timestop_v2` on the baseline, Baseline line) | e03b9ef, 906877f, ba29e20 | one pre-review fix (timestop_v2 derived from CURRENT_FIXED), one fix round (Baseline line named the version in force, not the one the rows were judged against) |
| 3 `manager experiments take`, `manager rules init\|show\|list\|apply\|propose` | 681b096 | clean |
| 4 `verify_forward`, hourly job `rules`, compose service, runbook row | f36f60b, 7039a38 | one pre-review fix (STALE guard: a version applied mid-replay gets no verdict); clean |
| 5 report section, `/api/rules/current`, `pending_view.rules`, poll line | 637024f | clean |
| 6 evidence-only `scorecard` in AMBER dossiers; `decision_outcomes.agent_id/bars_in_trade`; `learn relabel-meta` | 5248354 | clean |
| 7 the sentinel skill reads the thresholds from the dossier; scorecard-as-evidence section | 197beec | clean |
| final whole-branch review (opus) | ba9267d, a40cd4d, 1a6579a, b425f9a, c918686 | 4 Important (affected-set definition; a failing evidence read lost the AMBER dossier; stale NEEDS_USER rows survived a newer apply; a revert proposal reached no one), 6 minors; one fix wave |
| re-review of the wave (opus) | 8220141 | the I4 fix had excluded the revert alert from the poll's RED list; one targeted fix, re-review clean |

Suite: full run on c918686 — 5810 passed, 6 skipped, 4 warnings, 25:41; the one-commit delta 8220141 covered by
`tests/triage tests/learn tests/eval tests/commands tests/api` (1091 passed). `main` fast-forwarded to 7eec4c8, pushed.

## Live verification (stored instants; details in the manager's record)

- Gated deploy of `main-8220141` (image `62d9e696b56a`): armed 2026-11-01T04:56:12Z, check exit 0 at 04:56:38Z with
  0 open positions, DEPLOY START 04:56:39Z, DEPLOY DONE 04:57:29Z; 21 manager services on the new image, `rules-1`
  created, restart count 0 everywhere; `init_db` created `rule_versions` and the two `decision_outcomes` columns.
- `manager rules init --by "user (plan 2026-10-31-rule-versions)"` → `rule version 1: APPLIED`, applied 05:01:57Z,
  thresholds 0.5 / 2.0 / 3 / 25.0 / 0.5 inside their bounds; `manager learn relabel-meta` → 114 rows filled, 0 unmatched.
- `rules` beat 04:57:39Z `no rule version` (before init), hand run 05:06:08Z `version 1 NONE n=0`; `experiments` beat
  04:57:35Z `not due`; `triage` tick 05:02:00Z 0 positions.
- `GET /api/rules/current` version 1 APPLIED verify NONE; `GET /api/triage/pending` `rules.needsUser` 0;
  `GET /api/learn/latest` `ruleVersion` 1; the poll's rules line renders `Rules in force: version 1 — loss_r 0.5R,
  profit_r 2R, time stop 3 bars, tp line 25 %, stop 0.5 ATR` (the poll itself suppressed: nothing pending).
- Unverified until a position opens: a triage row's `metrics.rule_version == 1` and an AMBER dossier's `scorecard`.

## Rulings made during execution (the SDD ledger; reported to the user)

1. `manager experiments take` does NOT call `init_db` (only `manager rules` does, as `policy` does) — lever D's ruling 5
   keeps the experiments CLI free of schema writes; the service start creates `rule_versions` — cost if wrong: a take
   before the first service start fails with "no such table".
2. Bounds text is `str()`-formatted (`loss_r 1.5 outside 0.25–1.0`), not `:g` — the plan's own example fixes it.
3. The nine `timestop_v2` grid candidates derive from the baseline in force, not `CURRENT_FIXED` — every candidate is a
   one-change variant of the baseline — cost if wrong: one extra parameter.
4. The report's Baseline line derives from the listed window's `/r<id>` segment; the version in force only with no rows.
5. `render_show` lives in `manager/learn/views.py` (the report reuses it).
6. A version applied during `verify_forward`'s replay must not receive the stale verdict: the row is re-checked after
   the read-only export, `STALE` is returned and nothing written. With no superseded row the forward baseline is
   `THRESHOLDS`; a missing CI bound is open-ended. The brief's example observed values were illustrative.
7. The forward check's affected set is `Delta.affected` (the two rule sets acted differently), the experiments'
   definition — the observed mean must be comparable to the predicted one.
8. The experiments acceptance sentence says an OPEN row applies only on the user's `manager experiments take`.
9. The evidence query runs in `_write`'s AMBER branch when no reusable dossier exists (the verdict is known only after
   the reads block); GREEN/RED/reused ticks pay no query. A None/0-bars position gets band None. A failing evidence
   read runs in a savepoint and costs nothing but the section.
10. Applying a version supersedes every other NEEDS_USER row (`rules.superseded`), `rule_versions` carries
    `base_version_id` (the version in force at proposal), the forward check replays against it, and `apply_version`
    refuses thresholds equal to the version in force — a stale revert must never undo a newer version.
11. A revert proposal reaches the user by push: `rules.revert_proposed` writes an `Alert(kind=RULE_REVERT_PROPOSED)`,
    which stays a RED mention on the triage poll (nothing else posts it), and `pending_view.rules.needsUser` counts
    the rows waiting; the poll's rules line says "N proposal(s) waiting for you". The same lesson as the unrecorded
    36-hour pause.
12. `_reusable_dossier` also requires the same `rule_version`, so an apply refreshes an AMBER dossier at the next tick.
13. HOLDS is final once the gate (20 affected, 7 days) has passed, exactly as OUTSIDE is; spec 4.8 reads as a one-time
    judgement on the next N decisions — cost if wrong: a later drift under a HOLDS version goes unflagged until the
    next experiment build re-tests the window.
14. The full suite ran once on c918686; the one-commit delta 8220141 (triage/views.py, rule_versions.py, their tests)
    was covered by `tests/triage tests/learn tests/eval tests/commands tests/api` (1091 passed).
15. Parked: an out-of-bounds take held NEEDS_USER and then superseded leaves its experiment TAKEN with no live version;
    a hand re-propose loses the experiment link (no prediction, no forward check).
16. Parked: applying a revert row itself leaves its own RULE_REVERT_PROPOSED alert standing (an hourly mention up to
    24 h until `manager alerts ack`); a one-line follow-up acks it in `apply_version`.

Deferred minors (the SDD ledger, 23 lines, triaged by the final reviewer; none blocks): `inside_bounds` on an
unvalidated dict, an explicit `baseline=` with no `/r` segment, the knob taken from the first word of a `RuleError`,
the millisecond race between the STALE check and the job's commit, test-coverage gaps named per task, the floor
counting rows while the mean counts deltas (cannot differ today), the skill's band description omitting null.

## Spec deviation, stated

"Sentinel skill text rendered from `rule_versions`" is implemented as the skill reading the thresholds the dossier
and the poll carry (`triage.metrics.thresholds.*`, `rule_version`), with a test that no threshold literal remains in
the reason definitions: the image has no `hermes/`, Hermes reads the file from the host checkout, and a rendered copy
would be stale the moment a version applies.
