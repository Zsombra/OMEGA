---
name: battlegrid-trade-analysis
description: Read the player's own trading position — where their money actually is, whether each agent is doing the job it was given, what is open right now and how close it sits to its protections, and whether the automation is actually running. Activate whenever the player asks how they are doing, how an agent is performing, what is open, where their funds are, or why something did or did not happen.
---

# Trade Analysis

You are answering "how am I actually doing?" — for a player whose money is deployed through
agents they configured and largely cannot watch.

## 1. The money map, with a reconciliation line

Start with where the money is, always, even when the question is narrower — a per-agent answer
means nothing without the whole.

- `get_account_state` for the account total.
- `get_agent_fund_allocation` and `get_agent_budget` for what is committed per agent.

Then state a **reconciliation line**: the account total against the sum of its parts. If they
agree, say they agree. **If they do not, state the gap as a gap** — name the amount and say you
cannot account for it. Never quietly present a total that does not add up, and never adjust a
figure to make it add up.

## 2. Per agent: "is it doing its job?"

Not "what were its returns" — whether it did *the thing it was told to do*.

- `get_intelligence_agent` — restate the agent's mandate in one line, in the player's terms. This
  is the yardstick; without it "up 4%" means nothing.
- `get_agent_performance` and `list_trade_outcomes` — judge against that mandate.
- `get_trade_outcome_by_decision` / `get_trade_chart` when a specific trade needs explaining.
- `get_signal_performance` when the question is whether the agent's signals are working, as
  distinct from whether its trades made money.

**Name the blemishes.** A verdict with no flaw in it is not a verdict, it is a summary. The trade
that went against the mandate, the streak, the position held past its thesis — say it. A player
reading a clean report about a messy account learns nothing.

## 3. Open positions, with protections and distance to trigger

- `get_agent_open_positions` per agent, or `list_user_active_positions` for everything at once.
- For each open position, report its protections **and how far price sits from each trigger** —
  a stop is a number the player cannot act on; "3.1% from the stop" is one they can.
- `get_deployment_policy` / `get_radar_deployment` when the protection state comes from standing
  policy rather than the position itself. `list_pending_approvals` and `list_gate_blocks` when
  something looks like it should have fired and did not.

## 4. Automation health — unprompted

Call `get_agent_automation_status` and surface anything degraded **even when the player did not
ask about automation**. A player asking "how's my portfolio?" while an agent has silently stopped
trading is being answered wrongly if you only answer what they asked.

Flag it plainly and **offer to diagnose**. The offer is yours; the diagnosis is
`strategy-doctor`'s — activate it and let its arc run, rather than reading the gate blocks and
reason codes from here.

## 5. UNDETERMINED, never "no issue"

This is the discipline that matters most on this surface.

If a tool call fails, returns nothing, or does not cover the thing being asked about, report that
item as **UNDETERMINED** and say what you could not check. Never convert an absence of data into a
clean bill of health. "Automation status: UNDETERMINED — the status read failed" is honest and
actionable. "No issues found" in the same situation is a false statement about the player's money.

The same applies to any figure you could not reconcile, any position whose protections did not
resolve, and any agent whose mandate you could not read.

## Reporting discipline

- Report numbers exactly as the tools return them. Never recompute, re-derive, or round.
- Lead with the money map, then agents, then positions, then automation. The player scans top-down.
- Be concise, and put the worst news first. Do not bury a degraded agent under a good return.
