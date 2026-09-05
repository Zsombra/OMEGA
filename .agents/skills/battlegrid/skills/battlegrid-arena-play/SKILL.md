---
name: battlegrid-arena-play
description: Enter the player into Market Grid sessions — find an open session, read its coin pool and live market context, compose a grid with real per-coin reasoning or have one of their agents generate it, submit it against the session's entry fee, then read the results and the reasoning journal after settlement. Activate whenever the player wants to play, enter, join or submit to a session, wants their agent to enter one, asks what is open to play, or asks how a session they entered turned out.
---

# Arena Play

A submission is a **wager**. On a paid session the entry fee moves as part of the submit call, and
the grid you submit is the one that gets scored. There is no draft state and no undo.

## The three failures this flow exists to prevent

1. **A blind submission.** *Cue: "just enter me", "pick something", any ask that skips reading.*
   A grid composed without the session's own market context is a guess the player pays for. →
   steps 2–3.
2. **A stale or superseded agent grid submitted.** *Cue: the agent generated a grid and then
   anything happened — a regeneration, a long pause, a change of mind.* The submit consumes
   whatever generation is cached, not the one the player looked at. → step 4.
3. **Restating a limit number.** *Cue: the urge to say "you have N entries left today" or "your cap
   is $X".* Daily wager caps are platform config with per-user overrides, and the pipeline is the
   only authority on them. → the negatives below.

## Sequence

### 1. Account state first

`get_account_state`. It carries the balance, the rank, and **`mcpWagerEnabled`** — a served
projection of the player's Server-Signed Wagers signer consent.

- **False** ⇒ say so up front, name the enablement path (Profile → Wallet tab → enable Agent
  Wagers), and continue **read-only**: sessions, market context, results and journals are all still
  useful. Do not pretend a submit will work.
- **True** ⇒ proceed. It is a routing signal for what you tell them, never an authorization: the
  wager pipeline re-checks consent at the fee itself, and its refusal is the authority in either
  direction.

### 2. Workflow A reads, in order

1. `list_market_grid_sessions` with status `PENDING` — the sessions still enterable. **The
   `sessionId` you use comes from here; never fabricate one.**
2. `get_market_grid_session` — the coin pool (note each coin's `id`), the entry fee, the pool and
   the lock time.
3. `get_market_context` for that session — the indicators, rankings and trends the picks will
   actually be reasoned from.
4. `check_market_grid_submission` — **before composing anything.** If a submission already exists,
   report it (with its id and time) and offer `update_market_grid` where the session still permits
   it. Never compose a duplicate.

### 3. Compose — the reasoning is yours to get right

A direct submission carries `grid`, `reasoning`, `confidenceScore`, `modelName` and
`pickReasoning`, and all of them are required.

- **Exactly one cell is captain** (2× multiplier).
- **`pickReasoning` carries one entry per grid cell — every cell, no coin twice.** Compose it
  correctly because it is yours to compose, not because something downstream will catch it: the
  boundary refuses an incomplete payload before the fee moves, and leaning on that check means
  submitting payloads you have not read.
- Each entry's reasoning cites **the market context you read in this conversation**, for that
  coin. Boilerplate reasoning attached to a real wager is worse than none — it looks like
  evidence.
- `confidenceScore` is your honest read, and you state it to the player on the confirm form.

**The agent path instead:** `generate_agent_grid` has one of the player's agents produce the grid.
It spends a **billed LLM inference against the player's intelligence credits** — say that before
you call it. Each call replaces any previous pick for this (session, agent) pair, and the pending
generation lives about ten minutes.

Present the generation as a card: the agent, its confidence against the threshold
(`confidenceThreshold: null` means no deployment declares a bar here, so the grid is **ungated** —
say that rather than inventing a bar), whether it meets the threshold, and the per-coin picks.

### 4. Confirm, then submit promptly

One confirmation naming **the session, its entry fee, and the confidence** — then submit on an
explicit pick.

- Direct → `submit_market_grid`.
- Agent → `submit_agent_grid`, which consumes the cached generation for that (session, agent).

**A regeneration voids any prior confirm.** The submit takes no generation token — it reads
whatever is currently cached — so a grid regenerated after the player confirmed would be submitted
under a confirmation given for different picks. Re-present the confirm for the new generation,
every time, and submit promptly after the confirmed one.

**If the submit is refused for a missing pending generation**, the ten-minute window lapsed. The
recovery is `generate_agent_grid` again and a fresh confirm. **Never** convert the stale picks into
a hand-composed `submit_market_grid` under the player's own name — that submits an agent's
reasoning as the player's, and the attribution is part of what was scored.

### 5. After settlement

- `get_market_grid_results` — available only once the session is SETTLED. Before that it returns a
  typed CONFLICT naming the current status: **report it and stop**. Do not poll it in a loop; the
  op budget is finite and a settling session is not a failure.
- `get_mcp_reasoning_journal` on request — the reasoning, confidence and picks as recorded at
  submit. Compare the outcome against what was actually reasoned, and say where the reasoning was
  wrong.

## Refusals, and what each one means

Each is typed and distinguishable. Read the code, do not paraphrase:

- **No wallet consent** — the shared wager pipeline's own refusal, carrying its enablement copy.
  Surface that path verbatim. This is the same refusal an external MCP client gets; there is no
  chat-side difference and no chat-side override.
- **A daily cap** — a typed rate-limit refusal. Say the cap is spent and that it resets on the UTC
  day. Distinguishable from the run's op budget and from consent — do not merge them into "you
  can't play right now".
- **Funds, session state, an already-submitted grid** — ordinary typed refusals. Report what the
  server said.

## Negatives

- **Never restate a limit number** — not the daily count, not the volume cap. The pipeline holds
  the real value including per-user overrides, and a number repeated from anywhere else will
  eventually be wrong on a surface where being wrong costs money.
- **Never use `random_submit_market_grid`.** It shuffles the pool and wagers on the result with no
  reasoning at all. It exists for other clients; it is not something to offer a player who asked
  you to think.
- **Your confirmation with the player is interaction, never authorization.** Do not describe it as
  a permission check, do not add a wager gate of your own, and do not treat free text typed while a
  confirmation is open as consent.
- **Never re-submit over an unknown outcome.** An interrupted submit may have committed the fee.
  Run `check_market_grid_submission` first and report what actually exists.

## Reporting discipline

- Report fees, pools, scores and payouts exactly as served. Never recompute a payout or a rank.
- Name the session and the fee every time money is about to move.
- A tool that fails is reported as failed. Never fill a gap with a plausible value on a surface
  that is about to charge someone.
