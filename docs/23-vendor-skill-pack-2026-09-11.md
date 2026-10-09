# 23 · The vendor skill pack, and where it disagrees with the live server

**Measured 2026-09-11.** This document exists because the repo already carried the vendor's
official skill pack — `.agents/skills/battlegrid`, installed at `@battlegrid/mcp-server` 31.2.13
on 2026-09-05 ([21](21-platform-drift-2026-09-05.md)) — and it was never *loaded*: the
`.claude/skills/battlegrid` symlink is gitignored, so it did not exist in this worktree, and
Claude Code never saw the skill. Re-running `npx skills add playbattlegrid/battlegrid-mcp`
recreated the symlink and upgraded the pack to **31.2.18**. Reading it afterwards showed that
several things this project "discovered" by measurement on 2026-09-10/11 are documented in
`battlegrid-strategy-examples/SKILL.md`, and that on two points the pack describes a contract
the server has not deployed.

**Rule that follows:** load `battlegrid-strategy-authoring` and `battlegrid-strategy-examples`
before composing anything. They are the same instructions BattleGrid's in-app Commander runs on
(pack `CLAUDE.md`: "exported from `battlegrid-app/server/src/skills/`"). Then measure — because
they are not always current, as below.

## What the pack documents that this project re-derived

| Fact | Pack | This repo |
|---|---|---|
| Verdict order | "first TRUE carrier **in declaration order** decides … order carriers most-specific first" | measured 2026-09-10/11 as first-true-wins; 5 of 11 conditions found dead ([09](09-conditions.md)) |
| `coinSelection` | "non-authoritative, never persisted, and **not recoverable from `get_strategy`**" | measured 2026-09-11: reads back `null` |
| UPDATE semantics | "carries only the axes that change. The server preserves every axis you omit" | measured 2026-09-11: UPDATE merges |
| CREATE `sectionKey` | "A CREATE omits `sectionKey`" | measured 2026-08-28 and 2026-09-10 |
| `entry` | "all six required on every CREATE, no defaults … `closes` ≠ 1 refused under any trigger but `ON_CANDLE_CLOSE`; `levelOffsetAtrMultiple` ≠ 0 and `validForBars` ≠ 4 refused under a non-level trigger" | mirrored from records; the legality matrix was not known |
| Plan cap | "capped at 256,000 UTF-8 bytes, which compile enforces and reports" | measured; the per-coin cost model is ours ([09](09-conditions.md)) |
| Apply shape | `{ request: { planToken, confirm: true } }`, "no `plan` member" | measured 2026-09-11; the "omit `plan`" workaround in [16](16-the-write-path.md) is historical |

## Where the pack and the live server disagree

The pack's vendored digest (`src/__fixtures__/authoring-contract-digest.json`) moved from
contract **54.0.0 → 55.0.0** in this upgrade. `GET https://mcp.battlegrid.trade/mcp/version` at
2026-09-11T12:4xZ returned `{"contractVersion":"54.1.0","buildSha":"37cb29b6…"}`. **The skills
are ahead of the server.** Two consequences were checked:

### A null reads FALSE, not UNRESOLVED — re-measured on 54.1.0

The pack (`strategy-examples`): *"Evaluation is three-valued: UNRESOLVED never collapses to
FALSE"* and *"Event columns … are null on every other [bar], which reads as UNRESOLVED."*

Measured, `preview_strategy_report`, 1h, eight coins, an `EMA_CROSS` value column (header
`EMA5_13`, vocabulary `Bullish | Bearish`, `closeClockReadable: true`), no crossing on any bar:

```
| coin | EMA5_13 |      every row: —
NULL_IS   EMA5_13 is "Bullish"              → FALSE  (operand "—")   on 8/8, provisional: true
NULL_IN   EMA5_13 in ["Bullish","Bearish"]  → FALSE  (operand "—")   on 8/8
conditionVerdictTally: {"UP":0,"DOWN":0,"NEITHER":8,"UNRESOLVED":0}
verdict: NEITHER, decidedBy: null
```

This is the third time the repo has measured it ([09 § A null value reads FALSE](09-conditions.md),
[22](22-platform-drift-2026-09-09.md) trap 21). It matters here because the first-UTC-hour
fallback tier on the TPO strategies was designed on exactly this reading: an absent `tpo*` value
makes its clause FALSE, the ladder falls through, and only `pTpo*`-based conditions can decide.
On 55.0.0 that may change; re-measure when `/mcp/version` moves.

### Previous-session levels: `{abs:'1d'}` accepted or refused?

31.2.13 said bind `PDH`/`PDL` `{abs: '1d'}`, "the only reference the save path accepts on them".
31.2.18 says they are **timeless**, take `{rel:'anchor'}`, and *"An absolute reference is REFUSED
at save, including `1d`"*. That is a save-path (compile) behaviour, unmeasured here — a compile is
user-gated. Recorded as a 55.0.0 claim; the TPO levels are already bound `{rel:'anchor'}` and
render, so nothing in this repo depends on the answer today.

## `required: true` is a gate — the boilerplate undersells it

The rendered report boilerplate says conditions *"do not gate, score, or qualify anything."* The
pack says *"`required: true` = FALSE blocks compose-trade before billing."* Measured,
`get_agent_coin_qualification` on PVM Alpha (XRP, BTC):

```json
"gates": {
  "aggregateScore":     {"verdict": "CLEARED",      "scorePercent": 67, "minScorePercent": 65},
  "requiredCount":      {"verdict": "NOT_ENFORCED", "count": 0, "min": 0},
  "atrVolatility":      {"verdict": "CLEARED",      "atrPct": 1.52, "minAtrPct": 0.5},
  "requiredConditions": {"verdict": "NOT_ENFORCED", "failedKeys": [], "requiredCount": 0,
                         "evaluatedCount": 0, "trueCount": 0, "reachReason": null}
}
```

A `requiredConditions` gate sits in the qualification ladder beside the aggregate gate. It reads
`NOT_ENFORCED` only because **no condition on any strategy in this account carries
`required: true`** (0 of 10 on both TPO strategies). So the "advisory" boilerplate is true of
`required: false` conditions and false of `required: true` ones. For this project that is the
missing piece: a TPO condition can *block* a trade, not merely inform the agent.

**Measured 2026-09-12, `3d720de3` rev 3.** One required, verdict-null condition
`TPO_HAS_DIRECTION` = `ANY(VALUE_ABOVE, VALUE_BELOW, VALUE_RISING_IN_BALANCE,
VALUE_FALLING_IN_BALANCE)`. Qualification afterwards on eight coins: `requiredConditions` reads
`CLEARED` (true 1/1) on XRP, DOGE, ZEC, SOL, LINK and `FAILING` with `failedKeys:
["TPO_HAS_DIRECTION"]` on MOODENG, BTC, ETH; MOODENG and ETH carry `firstFailReason:
REQUIRED_CONDITION_FALSE`. **It blocks.** It blocks `long` and `short` identically — the gate is
direction-neutral, so it enforces that TPO has an opinion, not that the trade side agrees with it.
Side-matching remains the agent's decision, informed by the verdict ladder.

## The pack's position on pre-checking, versus the preflight

`strategy-authoring` §6: *"Do not pre-check expiry, digests, ownership, viability or quota before
calling. The server is the only authority on all of them; your job is to react to what it
returns."* And §4: *"a failed compile has cost the player nothing."*

That is the opposite of [20 §5](20-the-authoring-procedure.md)'s precondition. Both are stated
here so the choice is visible:

- **For the vendor:** the compile *is* the check, it is typed, it names the offending path, and a
  refused compile parks nothing. The preflight cannot see the runtime validator either — its own
  disclaimer says so — and drift instances #3/#4/#5 were runtime-vs-published disagreements the
  preflight could not have caught.
- **What the preflight still does that a compile does not:** it runs offline against a captured
  schema and a read-back **record**, so it catches a body that is not a wire body at all (today's
  S7 design record) and mirror drift against a reference (`MIRROR`, `MISSING_VS_RECORD`) without
  spending a call. `AGENTS.md` lists a rate limit of "50 ops/day"; if that is real, offline checks
  are not free of value. It is a doc claim — `get_account_state` exposes no rate-limit field, and
  the measured burst behaviour is 3 req/s with a 120 bank ([22](22-platform-drift-2026-09-09.md)).

The honest summary: the preflight is this repo's discipline, not the platform's. Keep it for what
it uniquely catches; do not present a PASS as evidence the server will accept the body.

## Housekeeping

- The pack is tracked in git. This upgrade changes `package.json`, `package-lock.json`,
  `skills/EXPORT.json`, `strategy-examples/SKILL.md`, `references/tradingview-ports.md`,
  `src/__fixtures__/authoring-contract-digest.json`, `src/index.ts`, and `skills-lock.json`.
- `src/index.ts` is a stdio proxy: reads `BATTLEGRID_API_KEY(S)` from the environment, fetches
  `/identity`, forwards `{ request }` byte-for-byte. One dependency (`@modelcontextprotocol/sdk`).
  No exec, spawn or file writes. The installer's scanners flagged it (Socket 4 alerts, Snyk
  medium); nothing in the source explains the flags beyond network and env access.
- `AGENTS.md` also states "Wager spend $500 USD/day". Unmeasured.
- **The `mcporter` CLI can vanish from the npx cache** (measured 2026-09-12, minutes after the
  skills-pack install): `npx --no-install mcporter` refused with `missing packages
  ["mcporter@0.13.12"]` while `~/.mcporter/credentials.json` was intact. npx keys its cache by the
  literal spec string, so `mcporter@0.13.12` and bare `mcporter` are separate entries and every
  repo script uses the bare one. Restore with `npx --yes mcporter --version` — **bare spec** —
  then `--no-install` resolves again and `mcporter list battlegrid-anbu` authenticates (status ok,
  115 tools). A `--yes mcporter@0.13.12` run prints the version but does **not** repopulate the
  bare entry. The MCP connector was live throughout, despite a session banner saying otherwise.
