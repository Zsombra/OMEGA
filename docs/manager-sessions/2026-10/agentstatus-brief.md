# Brief: the manager knows every agent's status and reports every change (2026-10-19)

## The user's request (verbatim)

"this is the thing that we need to be aware of: the status of the agent. That way, he's aware of all the status of
the agent: what it's doing, if it failed, and what the reason is that it failed."

## What prompted it (10-19)

1. **"VWAP Sentinel" (agent `2e725543-b8c7-4a88-94fe-66bd36b02f4c`, the older one).** It sat on Radar with all 6
   coins PAUSED (`radar_policies.enabled=false`, reason POLICY_DISABLED): APT, HYPE, MET, MOODENG, PUMP, PURR. No
   alert or report told the user. The user had to notice it. (Those 6 policies were deleted at the user's request
   10-19 10:00Z, actions 114-119.)
2. **Trend Continuation (`f72d2162-...`).** It vanished from `list_intelligence_agents` after snapshot 9577
   (06:10Z), very likely archived by the user, and its BTC/ETH/SOL Radar policies are gone. Nothing alerted or
   recorded the transition.
3. **`manager agents list --archived` fails:** "[TOOL_ERROR] The result is 197456 characters, over the 150000-character
   cap; ask for less". It needs paging or narrowing.
4. **What already exists:**
   - the halt watch: AGENT_HALTED_IDLE, `get_agent_budget` per DEPLOYED agent;
   - the entry-fail watch: AGENT_ENTRIES_FAILING, `list_entry_decisions`;
   - `radar_policies` per snapshot, with section/reason/blocked_reason.

   Each covers one slice. There is no single per-agent status, and no record of transitions.

## Working rules

- **Repo and worktree:** repo `battlegrid-manager`, worktree `C:/tmp-bgm-agentstatus`, branch `feat/agent-status`
  from main (d76e53e or later).
- **Tests:** `C:/Users/rafae/Documents/GitHub/battlegrid-manager/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.
- **Commits:** small, each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Not allowed:** merging, pushing, deploying, calling BattleGrid, touching Docker/.env/Hermes profiles, or
  dispatching subagents. Read-only psql is allowed:
  `docker compose -f C:/Users/rafae/Documents/GitHub/battlegrid-manager/docker-compose.yml exec -T postgres psql -U manager -d manager`.
  Use it for real shapes, e.g. `agents`, `radar_policies`, `entry_decisions` and `snapshots.reads`.
- **Patterns to copy:** the halt watch (`manager/inventory/halts.py`), the entry-fail watch
  (`manager/inventory/entry_failures.py`), and their Hermes script `hermes/scripts/battlegrid_halt_watch.py`.
  Copy their read-set, fail-closed and alert patterns.

## What to build

### 1. One status per agent per snapshot

Derive it from what the snapshot already reads. Add reads only where needed, and stay within the rate budget.
Cover every agent the account lists, deployed or not:

- **lifecycle:** ACTIVE, ARCHIVED or NOT_LISTED (gone from the list since the last snapshot), from
  `list_intelligence_agents`.
- **binding:** the bound strategy name and id, and the model.
- **run:** `run_status` / `halt_reason` / `halted_at` / `blocked_reason` from `get_agent_budget`. Today this is read
  only for deployed agents. Extend the read to every ACTIVE agent ONLY if the count stays small (cap it, e.g. 10),
  and say what you chose.
- **deployment:** its Radar coins, each with enabled/paused, section, reason and blocked_reason (from
  `radar_policies`), and any Arena deployment.
- **activity:**
  - its newest ENTER decision's status, and its reason if read (from `entry_decisions`);
  - open positions;
  - whether an AGENT_HALTED_IDLE or AGENT_ENTRIES_FAILING alert is open.
- **one summary line,** e.g.:
  - "VWAP Sentinel 4h: ACTIVE, running, on 11 coins (11 scanning); last entry FAILED BELOW_EXCHANGE_MINIMUM 10-18 16:01Z"
  - "VWAP Sentinel: ACTIVE, running, on 6 coins, ALL PAUSED (policy disabled) - doing nothing"
  - "Trend Continuation: no longer listed (archived?) since 10-19 06:10Z"

A failed read makes that part UNDETERMINED, never "fine".

### 2. Transitions

Compare each agent's status with the previous snapshot's. Ledger `agent.status_changed {agent, from, to, at}`, and
raise ONE informational alert kind `AGENT_STATUS_CHANGED` per change batch per agent. Changes to catch:

- lifecycle changes;
- run changes (active → paused/blocked and back);
- coins added or removed;
- a coin paused or resumed;
- every coin becoming paused, or none left: "the agent is doing nothing";
- the entry outcome moving between EXECUTED and FAILED.

**Noise control:**
- ignore section flips between SCANNING and IDLE warm-up;
- debounce a change seen on only one snapshot. Your choice: require it on 2 consecutive snapshots for
  non-lifecycle changes, or report immediately with a "recovered" follow-up.
- the alert is informational: it needs no ack and auto-resolves. Follow the halt watch's pattern.

**Standing condition:** an agent whose coins are ALL paused for over 1 h, with no open position, is a standing
condition. Show it in the daily report every day while it lasts, like the halt.

### 3. Visibility

- **CLI:** `manager agents status`, one line per agent plus details with `--agent ID`.
- **API:** `GET /api/agents/status`. The plugin Fleet tab may show it, but the plugin is optional: say if you skip
  it.
- **Hermes:** the Commander's "BattleGrid halt watch" job runs `battlegrid_halt_watch.py` every 5 min. Extend it to
  post each AGENT_STATUS_CHANGED batch once (no re-posts; state handled as for the other two kinds).
- **Daily report:** a per-agent status table with the summary line, plus the day's transitions in NOTABLE.
- **Commander docs:** SOUL.md and SKILL.md get one paragraph each: the Commander can read agent status and explain
  what each agent is doing and why it failed. It cannot change deployments or settings; those are the user's.

### 4. Fix the archived listing

Fix `manager agents list --archived` so it pages or narrows the request and never overflows the 150k cap.

## Report

Tests for:
- the transitions (lifecycle, run, coin add/remove/pause, all-paused, entry outcome);
- debounce;
- fail-closed reads;
- the CLI line format;
- the Hermes once-only posting.

Run the full suite once (background, no -x). Write the report to
`C:/Users/rafae/Documents/GitHub/OMEGA/.claude/worktrees/app-development-continuation-8b80ba/agentstatus-report.md`
and return only: status, commits, suite count, concerns.
