---
name: battlegrid-trade-proposal
description: Find and stage a trade for one of the player's agents, for the player to approve. Activate whenever the player asks which coins fit an agent right now, wants a trade found or proposed for an agent, asks the agent to evaluate a coin, or wants to approve or decline a proposal it made. The scan is the agent's own gates over every active coin; the proposal is the agent's own conversational turn; approval is always the player's word.
---

# Trade Proposal

You are finding and staging a trade for an agent the player configured — never placing one. Every
step below reads what the server decided and puts it to the player in their terms; nothing here
re-sorts a list, re-derives a verdict, or approves on the player's behalf.

## 0. What is already held — before anything else

- `list_pending_approvals` and `list_user_active_positions` first, every time.
- A proposal holds the player's live-position slot for that coin across **all** their agents until
  it is accepted, cancelled or expires. **Never propose on a coin the player already holds a pending
  or live position on** — say why, and name the decision or position that holds it.

## 1. Which coins fit the agent right now

- `scan_agent_coins` for the agent. The rows arrive server-ranked: qualifying coins first by score,
  then the rest with their first failing gate, then coins that could not be scored with the reason.
- Read the rows **as written**: the rank, the verdict, the first failing gate, the unscorable
  label. Never re-sort them and never re-derive a verdict from its numbers — the server's ranking
  is the answer.
- A refused scan (`RATE_LIMITED`) is a refusal: say the scan was refused and when it can be retried
  (`retryAfterSeconds`). Never say "nothing fits".

## 2. Propose

- `propose_entry_decision` **only** on the coins the player named, or on the top qualifying row
  when they asked for the best fit. One coin per call.
- `userMessage` is the player's own words for the turn. Mint a **fresh UUID** `idempotencyKey` per
  proposal; a retry with the same key replays the recorded result and never runs a second turn.
- The call is synchronous and may take the turn's full LLM latency. Do not retry while it is in
  flight; a same-key call during that time is refused with `CONFLICT`.

## 3. Report the outcome in the player's terms

- `type: "recommendation"` — the PROPOSED decision, awaiting approval. State the direction, the
  entry, stop and take-profit levels, the position size, the **`convictionPercent`**, and the
  expiry (`expiresAt`). No conviction floor was applied on this surface: the conviction is the
  agent's own reading, and the player judges it.
- `type: "no_trade"` — the reason (`reasonCode`) and the next coins worth asking about.
- `type: "error"` — the engine's block or a post-billing failure, with its remedy:
  `OPEN_POSITION_CONFLICT` means a position already holds the slot (see step 0);
  `LLM_CREDITS_EXHAUSTED` means top up when `topupAvailable` is true; a `SURFACE` / `LLM_FAILURE`
  means the model was billed and produced nothing usable — retry **with a new key**, since the
  same key replays this failure.
- A refused proposal (`RATE_LIMITED`) is a refusal with its retry-after. Never "nothing to do".

## 4. Approve or decline — only on the player's word

- Present the decision and **ask**. `accept_entry_decision` only after the player explicitly
  approves; `cancel_entry_decision` only after they explicitly decline.
- Never accept because the conviction reads high, because the scan ranked the coin first, or
  because the player asked you to "find a trade" — finding is not approving. `get_entry_decision`
  re-reads the row if the conversation moved on before they answered.
