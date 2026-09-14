# Reuse vs fresh — decision record (2026-09-14)

**Asked:** "decide what would be the best course of action: from scratch, take some of the
features, or implement them. Don't take my bias. Look at the pros and cons." Constraint restated
the same day: the entire backend runs in Docker, and every backend job must be switchable on and
off from Docker. The Hermes agent and the desktop app are not backend.

**Decision:** a **fresh Python repository `battlegrid-manager`**. OMEGA is reused as a library.
grid-commander is reused as design patterns and reference documents, not code. MAEZTRO is reused
as facts, not code. This confirms D8/D9 of the design spec, now on measured evidence instead of a
lean.

## What was measured (all 2026-09-14)

| Candidate | Measurement | How |
|---|---|---|
| OMEGA, this branch (`main` + planning docs) | **1009 tests pass in 4.8 s**; `omega/` is 5,348 lines; no first-true-wins assumption in `omega/*.py` or `docs/` on this branch | `pytest -q`; `grep` |
| OMEGA, TPO branch `5c6a064` | 28 commits ahead of `main`, unmerged; panel logger and TPO scripts live only there. **The first-true-wins assumption lives here**: `docs/09-conditions.md:343`, `docs/23`, and `scripts/build_pvm_strategy.py`, which wrote "ordered rarest-first so no row masks another" into the live PVM strategy's description | `git rev-list`; `git grep` |
| grid-commander | 30,445 lines of TS/TSX in `src/`; 199 test files (its handoff reports 2,121 vitest tests on 2026-08-11; not re-run). Surface record probed 2026-08-11 at MCP `serverInfo.version` **17.2.0**, 114 tools. Versus the live list: added `get_radar_activity_summary`, `propose_entry_decision`, `scan_agent_coins`; removed `get_coin_market_context`, `get_macd_heatmap`. Schemas not compared. Its own backlog holds `the-surface-map-is-two-majors-stale` | local checkout; `mcporter list` |
| MAEZTRO | 139 Python files, **0 automated tests**: the 17 `test_*.py` files are one-off probes spawning `npx mcporter`; many are `_v2`…`_v9` retries of one script | listing; reading one |
| Hermes `battlegrid` skill | 1,326 lines of references: Radar upsert schema, submit-grid schema, qualification gates, error envelopes | `wc -l` |
| Platform | `/mcp/version` `contractVersion` 54.1.0 → **56.1.0** within the day; 115 tools before and after; semantics changed | `curl`; pack diff |

Not comparable, and not compared: grid-commander's `serverInfo.version` (17.2.0) and the
`/mcp/version` `contractVersion` (56.1.0) are different fields. Nothing here claims how many
contract versions grid-commander is behind; the measured staleness is the tool-name diff above.

## Options

### A. Fresh Python repository, OMEGA as a library — chosen

Pros
- One language end to end. OMEGA's validator, generator, preflight, execution defaults and panel
  logic are imported or copied, never re-implemented or bridged across a service boundary.
- The design's four rules are built in from the first commit: decide in the model and enforce in
  code; one write path; unreadable is not empty; every backend job a Docker service.
- Contract drift is handled by design (the platform watch), not inherited as debt.
- The Phase 0 plan already exists task by task.

Cons
- Patterns grid-commander already proved get re-implemented in Python: confirm-before-perform
  writes, digest-bound tokens, a surface record, an audit trail. Mitigation: adopted as design
  rules, with its documents kept as references.
- OMEGA needs a tag and a pin before Phase 4, which means merging the TPO branch into `main`.
  That merge happens only on the user's explicit ask.
- Estimate, not measurement: the manager needs roughly 2–3k lines through Phase 3.

### B. Revive grid-commander as the backend

Pros
- Already Dockerised with Postgres, migrations, an audit table, describe → confirm → perform
  writes with digest-bound tokens, a read-only MCP server, and the strongest freshness discipline
  of the three repositories.
- Mature pages for agents, pipeline, qualification and trades that Phase 5 would otherwise rebuild.

Cons — why not
- TypeScript, Next.js and Drizzle, while the measured authoring toolkit is Python. The choice is a
  sidecar service or a rewrite of OMEGA's 5,348 lines.
- Its founding principle is the reverse of this goal: no model may write through it. Reversing
  that reaches the write path, the token design and a long history of decisions built on it.
- Its surface record is from 2026-08-11, tool names have moved since, and schemas are unverified.
- It has no decision loop, no triage, no risk policy and no Hermes integration: the parts the
  manager exists for.
- It is a multi-tenant product with per-user credential encryption. A single-account manager
  carries that weight for nothing.

### C. Grow MAEZTRO into the backend

Pros
- It has exercised every write path once: strategies, agents, Radar, Market Grid.

Cons — why not
- No tests, no structure, nine versions of the same script, and a 5–8 s subprocess per call.
  Its value is the facts it learned, and those are already folded into the spec.

### D. Extend OMEGA in place with a `manager/` package

Pros
- No dependency plumbing; fastest first commit.

Cons — why not
- Breaks OMEGA's stated promise that nothing in the repository writes to BattleGrid.
- Its 10 MB data tree and research docs would ride into every Docker build context.
- `main` and the TPO branch differ by 28 commits; a manager package would have to choose one.

### E. Fresh repository, plus grid-commander as an optional UI container

Pros
- Its pages for free, as a Compose service under a profile.

Cons — why not, for now
- Its pages read tools whose schemas are unverified since 2026-08-11. A UI that renders a stale
  shape silently is worse than no UI. Reconsider after a surface re-probe, if ever; Phase 5's
  Hermes plugin covers the need.

## What is reused, precisely

| From | Reused as | Not reused |
|---|---|---|
| OMEGA | the `omega` package: validate, generate, preflight, execution defaults, membership, the performance gate. `scripts/tpo_panel_pull.py` copied verbatim into `manager/panel/columns.py`. Docs 16, 20, 21, 22 as the write-path record | the repository as a home; the data tree |
| grid-commander | design rules: describe → confirm → perform, digest-bound tokens, a surface record keyed by per-tool hashes, "unreadable is not empty", fail on a stale surface. `docs/REPORT_TABLE_GRAMMAR.md`, `docs/MCP_SERVER.md`, `docs/BATTLEGRID_SURFACE_MAP.md` as references | any TypeScript; its schema; its UI |
| MAEZTRO | facts: one agent-grid submission per Market Grid session; the `submit_market_grid` schema; Radar cap 20; call-timeout and stderr rules | any script |
| Hermes `battlegrid` skill | `references/*.md` folded into the manager's Hermes skill | its mcporter recipes |
| Vendor pack 31.2.22 | the nine skills, loaded by `commander`; `EXPORT.json` contract version read by the platform watch | — |

## Consequences

- **Docker:** one image, one Compose service per backend job (spec §2.4). Phase 0 ships
  `postgres`, `api`, `watch`, `inventory`, and `panel` under a profile. Later phases add `mcp`,
  `triage` (profile `shadow`), `executor` (profile `live`), `review` (profile `live`) and `eval`
  (profile `eval`). All BattleGrid writes run only inside `executor`, so stopping that one service
  makes a write impossible regardless of any flag.
- **Found on the way, not fixed here:** the live PVM strategy's description asserts behaviour
  (rarest-first ordering prevents masking) that contract 56.1.0 no longer has. It is TPO-branch
  work and needs the user's standing authorization for a revision; recorded, not acted on.
