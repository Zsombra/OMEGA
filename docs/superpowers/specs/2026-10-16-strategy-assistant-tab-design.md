# Strategy assistant tab — design (2026-10-16)

**Status:** Section 1 (components) was approved in conversation on 2026-10-16 ("YES DO IT"). This written spec
needs the user's review before the implementation plan is written. The code lives in battlegrid-manager. The spec
sits here because OMEGA holds the assistant's earlier design records (doc 20, 2026-08-28/29).

## 1. Purpose

**What the user decided:**
- The strategy-creation assistant (OMEGA's end goal) lives in **the Hermes BattleGrid plugin**.
- Input is **chat + live preview**. The user describes an idea in words, a free model turns it into a strategy, and
  the tab shows that strategy.
- The workflow ends with **stage, then approve commit**:
  - "Stage" puts an unsaved draft in the BattleGrid strategy editor.
  - "Commit" saves it after the user approves it in the tab.
  - Binding and deployment stay the user's job, outside the tab.
- Version 1 covers **new strategies and revisions of existing ones**.
- The engine is **approach A**: a manager Docker service that calls a free model, **reusing the user's Nous key**.
  The user copies that key into the manager's `.env` themselves.

**What this spec assumes (correct these in review):**
- One user and one active conversation at a time is enough.
- "Plain English" means OMEGA's existing `brief` / `StrategyPlan.render()` text, not new prose.
- A turn of up to ~60 s is acceptable: a free model, polled, but not the Hermes CLI's minutes.

**Success means** the user can do all of this from the tab, with no CLI:
- describe an idea;
- read back exactly what will be built, and why anything was approximated or refused;
- see the platform's own rendered report;
- stage the strategy and commit it with one approval;
- revise an existing strategy the same way.

None of this changes what the guards allow.

## 2. Decisions

| # | Decision | Source |
|---|---|---|
| D1 | The tab is a seventh tab, **Strategy**, in `hermes/plugin/battlegrid-manager` | the user |
| D2 | Chat on the left, live strategy card on the right. Updates are polled; no WebSocket in v1 | the user (chat + preview); the SDK calls `ctx.socket` "an accelerator over your polling" |
| D3 | The flow is stage → approve → commit. The tab never binds, deploys, funds or creates an agent | the user; the Phase 4A rule "the authoring assistant never binds and never deploys" |
| D4 | New strategies and revisions (UPDATE plans) | the user |
| D5 | A new compose service, `strategist`, calls the Nous OpenAI-compatible API with a FREE model only | the user (approach A, reuse the key); memory "free models only" |
| D6 | **v1 works at the thesis level.** The model writes an OMEGA `Thesis`: modules, stance, anchor, context, exits, execution and coin selection. OMEGA generates the conditions from its measured recipes. A hand-written clause such as "RSI < 30 AND close crosses VWAP" is approximated by modules, and the reply says so. Exact clause authoring is **v2** | design finding: `omega.generate.Thesis` has no field for explicit conditions, and `manager.authoring.pipeline` validates theses only |
| D7 | The model never calls BattleGrid and gets no tool definitions. It emits JSON only, and every BattleGrid call is the manager's existing code | design: free models are weak at tool calls, and this keeps the write path where it is |
| D8 | Refuse, then offer the nearest expressible thesis (OMEGA doc 20, D3). An idea no module measures is named as unmappable, and the nearest expressible thesis is offered and labelled as different | OMEGA decision record, 2026-08-29 |

## 3. Components

```
Hermes plugin ── Strategy tab (desktop/plugin.js)
   │  ctx.rest calls, polled; no secrets in the JS
   ▼
dashboard/plugin_api.py ── one proxy route per manager route (20 s timeout; every route answers fast)
   ▼
manager api  /api/strategy/*  ── bearer-protected, /api/policy conventions (400 not 422, `by`, required note)
   ▼
strategist service (compose service, profile "live")
   ├─ chat store      Postgres: strategy_chats, strategy_chat_turns
   ├─ model client    manager/strategist/model.py — Nous chat/completions, model on an allowlist of :free ids
   ├─ thesis turn     manager/strategist/turn.py — prompt, JSON parse, one repair round
   └─ reuses          manager.authoring.pipeline.build/store (OMEGA plan + every existing check)
                      READ client preview_strategy_report (the platform's own render; read-only)
                      manager.actions.strategy_propose (STAGE_STRATEGY / COMMIT_STRATEGY rows)
```

What each unit does and what it depends on:

- **`manager/strategist/model.py`**
  - One function, `complete(messages, *, model) -> str`.
  - It refuses any model id that is not on `STRATEGIST_FREE_MODELS`, where every id ends `:free`.
  - It reads `NOUS_API_KEY` from the environment. A missing key is a named error that the tab shows.
  - Timeout 90 s. The only retry is one, on HTTP 429, after its Retry-After.
  - It depends on nothing else in the manager.
- **`manager/strategist/turn.py`**
  - `run_turn(chat, user_text) -> TurnResult`.
  - The prompt is built from:
    - the system brief (section 5);
    - `omega.authoring.vocabulary()`, the module menu;
    - the chat's current thesis JSON;
    - for a revision, a summary of the strategy's current axes.
  - It parses the model's JSON and calls `pipeline.build`. On FAIL it feeds the findings back for ONE repair round,
    then stops and reports.
  - Apart from the model call it is pure, and it never calls BattleGrid.
- **`manager/strategist/store.py`**: the two tables and their reads; no business rules.
- **`manager/strategist/service.py`**: the compose service loop. It claims the oldest QUEUED turn, runs it and writes
  the result. It runs one turn at a time, because of the rate budget and the free models' limits.
- **The `manager/api` routes**: thin. They validate the body, call the store, pipeline or propose functions, and
  return the fresh chat body.
- **The Strategy tab**: renders only and never recomputes a verdict. This is the 5.2 rule: the JS shows the manager's
  lines verbatim.

## 4. Data flow

**New strategy**
1. The tab sends `POST /api/strategy/chats {kind:"new", by}` and gets a chat id back.
2. The tab sends `POST /api/strategy/chats/{id}/messages {text}`. The answer is 202 and the turn is QUEUED.
3. The strategist runs the turn:
   - the model returns thesis JSON;
   - `pipeline.build` checks it, with one repair round;
   - `pipeline.store` writes a `strategy_plans` row (PASS/FAIL, `body_sha256`, the live build);
   - the reply text and the plan id are saved on the turn.
4. While a turn is QUEUED or RUNNING, the tab polls `GET /api/strategy/chats/{id}` every 3 s. It shows the reply, and
   the card shows the plan's `brief`, verdict and findings.
5. **Preview** runs from a button, or automatically on PASS. `POST /api/strategy/plans/{id}/preview` makes the manager
   send the plan's stored `preview` body to `preview_strategy_report` (READ client) and return the render. It is
   read-only.
6. **Stage**: `POST /api/strategy/plans/{id}/stage {note}` calls `propose_user_stage`, which files a QUEUED
   STAGE_STRATEGY row.
   - The executor sends it as it does today; STAGE_STRATEGY needs no approval in unsupervised LIVE.
   - The card shows the row's status and, once it is DONE, the stored diff review.
7. **Commit**: `POST /api/strategy/stages/{action_id}/commit {note}` calls `propose_user_commit`, which files a
   COMMIT_STRATEGY row. That row **always** waits for approval (`STRATEGY_APPROVAL_REQUIRED`).
   - The tab's Commit dialog shows the row's describe lines verbatim: the diff sha and the exposure
     (UNBOUND/BOUND/LIVE).
   - Its **Approve** button sends `POST /api/actions/{id}/approve {note}`, which calls `pipeline.approve`.
   - A strategy bound to a LIVE agent is refused without `allow_live`. The tab offers that only as an explicit
     checkbox that names the bound agent.

**Revision**
1. The tab sends `POST /api/strategy/chats {kind:"revise", strategy_id}`.
   - The manager reads the strategy with the reader behind `manager strategy current`: the draft first, otherwise
     `get_strategy` + `axes_of_strategy`. It stores the axes on the chat.
   - If the player holds a draft the manager did not write, the chat is refused ("the player holds a draft of this
     strategy").
2. Turns run as above, but `pipeline.build` runs the UPDATE plan with `current` set to the stored axes. The settings
   the thesis does not name therefore come from the strategy itself; without them the plan fails with
   `THESIS_UNPLANNABLE`, which is already enforced.
3. Stage and commit work as above. Propose already refuses a second unsettled stage on the same strategy.

## 5. The model contract

- **Output:** exactly one JSON object, `{"reply": str, "thesis": {...} | null, "unmappable": [str]}`.
  - The `thesis` keys are `Thesis`'s: `name, tagline, description, anchor, weights, stance, context, coin_selection,
    execution, exits`.
  - `thesis_from_dict` already refuses unknown keys and the retired ones (`gate`, `required`, `show_scoring_data`).
- **System brief**, versioned in the repo as `manager/strategist/brief.md`:
  - OMEGA doc 20's intake questions and honesty gate, rewritten for contract 108+: conditions-only, no score gate,
    and the module tier is display-only;
  - the four anchors, and ALIGN/FADE;
  - D6 and D8, verbatim.

  It names no tool call shapes, because the vendor's exported skills still show the retired `request` envelope.
- **Repair:** one round, given the findings' codes and messages. A second FAIL is shown to the user as it is.
- **Model choice:** a free model, proven on the eval harness first (memory "free models only": prove a free
  replacement before using it). The candidate is `poolside/laguna-s-2.1:free`, the Commander's model.
  - The proof is a fixed set of 10 intake prompts, in `tests/fixtures/strategist/`.
  - Each prompt is scored on three things:
    - the output is valid JSON;
    - it reaches PASS after at most one repair;
    - a human reads it and checks the meaning.

    The semantic check exists because validation cannot catch a backwards thesis: the generator once built a
    mean-reversion strategy that bought strength.

## 6. Data model

- `strategy_chats`: id, kind (new|revise), strategy_id (null for new), current_axes (json, revise only),
  thesis (json, the latest valid one), plan_id (latest), stage_action_id, commit_action_id, created_at, by, closed_at.
- `strategy_chat_turns`: id, chat_id, role (user|assistant), text, status (QUEUED|RUNNING|DONE|FAILED), model,
  thesis (json|null), plan_id (null), findings (json), error, created_at, finished_at.
- Two new ORM models in `manager/db/models.py`, created by `init_db`'s `Base.metadata.create_all` (the manager has
  no Alembic; new tables need no column back-fill). No existing table changes shape.

## 7. Safety and guards (unchanged paths)

- **There is no new write path.** Stage and commit use the existing action rows, guards, ledger and executor.
  - The tab is a second *proposer* that goes through the same builder. `strategy_propose.py` says it is the only
    builder of a strategy row, and it still is, because the routes call it.
  - Its docstring and the test asserting "only the CLI proposes" are amended, not bypassed.
- In v1 the approve route accepts **only** COMMIT_STRATEGY rows; any other kind gets a 400. Every other approval
  stays on the CLI.
- The model's text is data.
  - It is never executed.
  - It never becomes a tool argument except through `thesis_from_dict`.
  - The tab shows it as escaped text.
- **Import boundary:** `manager/strategist/*` may import `manager.authoring` and `manager.actions.strategy_propose`.
  It may not import the write client (`manager.actions.write_client`); an import-boundary test enforces this.
- **Free models only**, enforced three ways:
  - the `STRATEGIST_FREE_MODELS` allowlist;
  - a test that every id on it ends `:free`;
  - a refusal at call time.

## 8. Errors

| Failure | What the user sees |
|---|---|
| No `NOUS_API_KEY` | the turn FAILS with "the strategist has no model key"; the tab shows it with the .env line to add |
| Model 429, timeout, or non-JSON twice | the turn FAILED with the provider's status; "send again" re-queues it |
| The thesis still fails after the repair | the reply and the findings list; the card stays on the last thesis that passed |
| An idea that can't be expressed | listed under "not expressible", with the nearest thesis labelled as different (D8) |
| Pin drift or a stale build | the existing preflight FAIL; the card says to re-plan |
| Stage or commit refused by propose | the refusal text verbatim (e.g. name taken, unsettled stage, held draft) |
| The strategist service is down | messages stay QUEUED, and the tab shows "the strategist service is not running" from `/health` |

## 9. Testing

- **Unit:**
  - `model.py`: the allowlist, a missing key and the 429 retry, against a fake HTTP server;
  - `turn.py`: a scripted fake model covering valid, invalid-then-repaired, twice-invalid and unmappable;
  - store round-trips.
- **API:** every route, in the style of `tests/api/test_app.py` (auth, 400 bodies, the fresh body returned). The
  approve route refuses any row that is not COMMIT_STRATEGY.
- **Plugin:**
  - `tests/hermes/test_plugin_api.py`: the proxy routes;
  - `tests/hermes/test_plugin_js.py`: the tab renders the manager's lines verbatim, and has no fetch and no token.
- **Boundary:** an import-boundary test for `manager/strategist`.
- **Model proof** (manual, recorded): the 10-prompt eval on the chosen free model, before the service is enabled.
- **Live check after deploy:**
  - read-only first: one new-strategy chat through to PASS and a preview;
  - stage and commit only on the user's word in the tab.

## 10. Out of scope (v1)

- Exact clause authoring (v2, D6).
- Trade-history evidence in suggestions (the user chose "new + revise" over "+ evidence").
- Binding, deploying, funding and agent creation.
- WebSocket streaming.
- Working several chats at once. The store allows many chats; the service runs one turn at a time.

## 11. Waiting on the user

- Copy the Nous API key into `battlegrid-manager/.env` as `NOUS_API_KEY=`. Claude never copies secrets.
- After the plugin changes ship, press Capabilities → Plugins → Rescan in Hermes, then reopen the profile.
