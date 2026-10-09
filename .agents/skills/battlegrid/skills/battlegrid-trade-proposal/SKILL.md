---
name: battlegrid-trade-proposal
description: Find and stage a trade for one of the player's agents, for the player to approve. Activate whenever the player asks which coins fit an agent right now, which of their agents fits a coin, wants a trade found or proposed for an agent or on a coin, asks the agent to evaluate a coin, or wants to approve or decline a proposal it made. The scans are the agents' own gates — one agent over every active coin, or one coin over every one of the player's agents; a proposal is QUEUED for the agent's next strategy-bar close and answered into the conversation when that bar is decided; approval is always the player's word.
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

## 1. When the player names a coin and not an agent — choose the agent

- `scan_coin_agents` for the coin. The rows arrive server-ranked across the player's own agents:
  `qualified` by score, then `rejected` with the first failing gate, then `unscorable` with the
  reason, then `ineligible` with the refusal `propose_entry_decision` would give (`AGENT_NOT_ACTIVE`,
  `MODEL_INACTIVE`, `AGENT_HALTED`). Read them **as written** — never re-sort or re-derive a verdict.
- **Ask the top-ranked qualifying agent**, and name the other agents that qualified so the player can
  choose one of them instead. One request per coin: the platform holds one pending request per coin
  across all of the player's agents, so ask one agent, not each of them.
- **When none qualifies, say so plainly.** Name each agent's blocking gate or ineligibility, and offer
  the strategy doctor for the one closest to qualifying. Never propose through an agent the scan
  reports rejected, unscorable or ineligible.
- **When the player has no agent at all**, the scan is empty: say so, and the next step is building one
  (a strategy first, when they have none).
- A refused scan (`RATE_LIMITED`) is a refusal with its retry-after, never "nothing fits".

## 2. Which coins fit the agent right now

- `scan_agent_coins` for the agent. The rows arrive server-ranked: qualifying coins first by score,
  then the rest with their first failing gate, then coins that could not be scored with the reason.
- Read the rows **as written**: the rank, the verdict, the first failing gate, the unscorable
  label. Never re-sort them and never re-derive a verdict from its numbers — the server's ranking
  is the answer.
- The scan is the **ranking** answer, not the full gate detail. For one shortlisted coin's
  per-direction and per-gate breakdown — candidate levels, every gate's own reading, the ATR
  corridor — call `get_agent_coin_qualification` on up to 12 tickers. Never re-scan for it.
- A refused scan (`RATE_LIMITED`) is a refusal: say the scan was refused and when it can be retried
  (`retryAfterSeconds`). Never say "nothing fits".

## 3. Queue the request

- `propose_entry_decision` **only** on the coins the player named, or on the top qualifying row
  when they asked for the best fit. One coin per call.
- **The call does not decide.** It registers a request against the agent's next strategy-bar close
  and returns immediately; no model runs and nothing is spent. The agent reads that bar on its
  settled close, through the same path its radar deployments use.
- `userMessage` is the player's own words for the turn. Mint a **fresh UUID** `idempotencyKey` per
  request; a retry with the same key replays the recorded result and never registers a second one.
- **One pending request per coin.** A second is refused with `CONFLICT` / `REQUEST_PENDING` — read
  the one that exists with `get_entry_request` rather than asking again.

## 4. Tell the player what they are waiting for

- `type: "queued"` is the normal answer. Read `request` back to them: the bar being decided
  (`barStart`), when the answer is due (`decidesBy`), and the deadline past which that bar can no
  longer be decided (`windowEndsAt`). `decidesBy` and `windowEndsAt` are different instants — a bar
  that has already settled is decided at the next sweep, seconds away.
- Say where the answer will appear: on the delegation card in this conversation, and — if it
  proposes a trade — in `list_pending_approvals`. Nothing further is needed from the player until
  then; the card carries the answer to them when the bar closes.
- When the player asks what the agent decided, read the request's conversation with
  `get_trade_conversation({ conversationId })`, using the id the `queued` result carried. It serves
  the whole transcript in stored order — the queued card, the agent's reasoning, its thesis and
  setups, the recommendation, a no-trade with its reason and next coins, or a close answer.
- `get_entry_request` re-reads a request until it is answered — including while its close has fired
  and the decision is being composed. `cancel_entry_request` withdraws it only while it still awaits
  its close; once the close has fired it is `NOT_FOUND`, and the answer arrives in the conversation.
  Both are `NOT_FOUND` once it has been answered, cancelled or expired, and that is the honest record:
  the answer is in the conversation.
- `type: "error"` — the block, with its remedy: `OPEN_POSITION_CONFLICT` means a position already
  holds the slot (see step 0) and nothing was queued; `LLM_CREDITS_EXHAUSTED` means top up when
  `topupAvailable` is true; `ENTRIES_PAUSED` means the platform has paused new entries while market
  data is missing across many coins, and nothing was queued. The pause is platform-wide, not the
  agent's or the coin's, so never retry it through another agent or on another coin. It lifts by
  itself once the data is back: ask again then, under a fresh `idempotencyKey` — the same key only
  replays this refusal. A refused request (`RATE_LIMITED`) is a refusal with its retry-after.
  Never "nothing to do".
- `type: "recommendation"` and `type: "no_trade"` arrive only as the **replay** of a request made
  before the queued contract shipped. Report them as step 5 describes and do not expect them from a
  fresh call.

## 5. When the answer arrives — approve or decline only on the player's word

**On a web Commander surface the approval is the card's own.** The decided close lands on the
delegation card in this conversation, carrying the player's Accept and Decline. `accept_entry_decision`
and `cancel_entry_decision` remain yours for the external and Telegram doors, and on the web only on
the player's explicit typed word — never inferred from interest, agreement, or a question about the
trade.

- A decided close produces one of: a PROPOSED decision awaiting approval; a no-trade with the
  reason and the next coins worth asking about; a refusal, `close_refused`, which names the gate that
  failed when the close did not qualify and none when it qualified and the radar's own gates stopped
  its fire; a window that passed with no sweep; a bar the agent's own radar deployment decided first;
  or an error carrying the engine's block, with nothing proposed, when admission refused the
  qualifying close's fire — `ENTRIES_PAUSED` while new entries are paused, an account block, a
  position already held.
- A bar the agent's own radar deployment decided first is reported from that deployment's decision,
  never decided again. It arrives as `close_fired_by_radar` — a trade taken in full — only when the
  deployment's fire enqueued a trade decision. Otherwise it arrives as what stopped that fire, and
  none of these is a trade: a fire admission refused arrives as the engine's block, exactly as when
  the refused fire was the request's own; a fire the radar's own gates stopped — its coin cooldown,
  its hourly cap, post-close suppression, a decision already running on the coin — arrives as
  `close_refused` with no gate, because the close qualified and nothing was entered; and a close
  whose coin another agent's fire took arrives as `close_claimed_by_radar`.
- On a proposal, state the direction, the entry, stop and take-profit levels, the position size,
  the **`convictionPercent`**, and the expiry (`expiresAt`). No conviction floor is applied on this
  surface: the conviction is the agent's own reading, and the player judges it.
- Present it and **ask**. `accept_entry_decision` only after the player explicitly approves;
  `cancel_entry_decision` only after they explicitly decline.
- Never accept because the conviction reads high, because the scan ranked the coin first, or
  because the player asked you to "find a trade" — finding is not approving. `get_entry_decision`
  re-reads the row if the conversation moved on before they answered.
