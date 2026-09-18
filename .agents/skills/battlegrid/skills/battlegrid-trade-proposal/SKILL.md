---
name: battlegrid-trade-proposal
description: Find and stage a trade for one of the player's agents, for the player to approve. Activate whenever the player asks which coins fit an agent right now, wants a trade found or proposed for an agent, asks the agent to evaluate a coin, or wants to approve or decline a proposal it made. The scan is the agent's own gates over every active coin; a proposal is QUEUED for the agent's next strategy-bar close and answered into the conversation when that bar is decided; approval is always the player's word.
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
- The scan is the **ranking** answer, not the full gate detail. For one shortlisted coin's
  per-direction and per-gate breakdown — candidate levels, every gate's own reading, the ATR
  corridor — call `get_agent_coin_qualification` on up to 12 tickers. Never re-scan for it.
- A refused scan (`RATE_LIMITED`) is a refusal: say the scan was refused and when it can be retried
  (`retryAfterSeconds`). Never say "nothing fits".

## 2. Queue the request

**In a conversation the Agent Toolbox hosts, this section does not apply: name the coin and stop.**
The player presses **Request a trade** in the trade lane beside you and the same queued request is
registered from there, free and without a model turn; your job is to say which coin is worth
requesting and what the gates read, and to leave the press to them. `propose_entry_decision` and
`cancel_entry_request` are refused from such a conversation as tool errors, so calling one spends an
op of your budget and queues nothing. The refusal is **host-wide** — every tool that writes is
refused there, which is why no other skill carries a paragraph of its own — and every read in this
flow stays available.

- `propose_entry_decision` **only** on the coins the player named, or on the top qualifying row
  when they asked for the best fit. One coin per call.
- **The call does not decide.** It registers a request against the agent's next strategy-bar close
  and returns immediately; no model runs and nothing is spent. The agent reads that bar on its
  settled close, through the same path its radar deployments use.
- `userMessage` is the player's own words for the turn. Mint a **fresh UUID** `idempotencyKey` per
  request; a retry with the same key replays the recorded result and never registers a second one.
- **One pending request per coin.** A second is refused with `CONFLICT` / `REQUEST_PENDING` — read
  the one that exists with `get_entry_request` rather than asking again.

## 3. Tell the player what they are waiting for

- `type: "queued"` is the normal answer. Read `request` back to them: the bar being decided
  (`barStart`), when the answer is due (`decidesBy`), and the deadline past which that bar can no
  longer be decided (`windowEndsAt`). `decidesBy` and `windowEndsAt` are different instants — a bar
  that has already settled is decided at the next sweep, seconds away.
- Say where the answer will appear: in the agent's conversation, and — if it proposes a trade — in
  `list_pending_approvals`. Nothing further is needed from the player until then.
- `get_entry_request` re-reads a request still pending; `cancel_entry_request` withdraws it. Both
  are `NOT_FOUND` once it has been answered, cancelled or expired, and that is the honest record:
  the answer is in the conversation.
- `type: "error"` — the block, with its remedy: `OPEN_POSITION_CONFLICT` means a position already
  holds the slot (see step 0) and nothing was queued; `LLM_CREDITS_EXHAUSTED` means top up when
  `topupAvailable` is true. A refused request (`RATE_LIMITED`) is a refusal with its retry-after.
  Never "nothing to do".
- `type: "recommendation"` and `type: "no_trade"` arrive only as the **replay** of a request made
  before the queued contract shipped. Report them as step 4 describes and do not expect them from a
  fresh call.

## 4. When the answer arrives — approve or decline only on the player's word

**In a conversation the Agent Toolbox hosts, the approval is not yours to send.** The decided close
lands on the trade card in the lane beside you, carrying the player's own Accept and Decline;
`accept_entry_decision` and `cancel_entry_decision` are refused there as tool errors, so calling one
spends an op and moves nothing. Read the card back to them — the direction, the levels, the
conviction, the expiry — and say what you would do, which is the whole of your part. What you have
to work from is whatever the player attaches from a card: its rendered readings, nothing more.

- A decided close produces one of: a PROPOSED decision awaiting approval; a no-trade with the
  reason and the next coins worth asking about; a close that did not qualify; a window that passed
  with no sweep; or a bar the agent's own radar deployment decided first and traded in full.
- On a proposal, state the direction, the entry, stop and take-profit levels, the position size,
  the **`convictionPercent`**, and the expiry (`expiresAt`). No conviction floor is applied on this
  surface: the conviction is the agent's own reading, and the player judges it.
- Present it and **ask**. `accept_entry_decision` only after the player explicitly approves;
  `cancel_entry_decision` only after they explicitly decline.
- Never accept because the conviction reads high, because the scan ranked the coin first, or
  because the player asked you to "find a trade" — finding is not approving. `get_entry_decision`
  re-reads the row if the conversation moved on before they answered.
