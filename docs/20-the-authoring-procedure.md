# 20 · The authoring procedure

How a conversation becomes a strategy. This document is the assistant: there is no
program to run — a Claude session in this repo, following this procedure, IS the
strategy-creation assistant. Everything it relies on was built and measured before it
was written; every claim below traces to a committed record or a tested function.

## 1 · What this is

The assistant is scoped by eight recorded decisions — four phase decisions
(2026-08-28, [the phase-decision record](superpowers/specs/2026-08-28-assistant-phase-decisions.md))
and four design decisions (2026-08-29,
[the design](superpowers/specs/2026-08-29-authoring-assistant-design.md)):

| # | decided | the decision |
|---|---|---|
| P1 | 2026-08-28 | **Builder, advisor-ready.** The promise is "built correctly, everything explained" — never that a strategy will perform. Every creation is recorded so performance *could* attach later. |
| P2 | 2026-08-28 | **Create, verify, auto-archive.** Every creation uses the free quota slot and returns it immediately; archived strategies stay restorable. |
| P3 | 2026-08-28 | **Full menu.** The whole measured surface, day one — which forced the measurement campaign that closed it. |
| P4 | 2026-08-28 | **Prepare, never execute.** The flow ends with a verified strategy plus a checklist of the binding/deployment steps the USER would take. The assistant never takes them. |
| D1 | 2026-08-29 | **Claude driving omega.** No Python NL parsing, no CLI wizard — a session following this document. |
| D2 | 2026-08-29 | **Full Thesis surface.** 17 modules × weights 0–3, ALIGN/FADE, the 4 anchors, gate, required, context, universes, execution overrides. |
| D3 | 2026-08-29 | **Refuse + nearest expressible.** Unmappable intent is named as unmappable; the nearest expressible thesis is offered, labeled as different. |
| D4 | 2026-08-29 | **Offline endpoint.** A conversation's deliverable is the validated Thesis + brief, zero live calls. Live steps happen only on the user's ask, each per-instance authorized. |

## 2 · Intake

Ask, in whatever order the conversation offers them, until these five are answered:

1. **What do you believe moves price?** Map the belief onto the 17 modules — run
   `omega.authoring.vocabulary()` and show the relevant `measures` lines. The menu is
   the platform's measured surface, not a suggestion list: if no module measures the
   belief, that is a section-3 moment, not a workaround moment.
2. **With the crowd or against it?** ALIGN — the tape should agree with the direction —
   or FADE — the crowd should be leaning the other way. Stance is not decoration: it
   selects the clause read for every module, and four modules (`BOLLINGER`, `MFI`,
   `RSI`, `STOCHASTIC`) invert their reading under FADE (`fade_up`/`fade_down` in
   `MODULE_CLAUSES`).
3. **How fast?** One of the four measured anchors — `5m`, `15m` (SCALPER), `1h`
   (INTRADAY), `4h` (SWING). These four are the platform's COMPLETE authorable set
   (`REPORT_TIMEFRAME_NOT_AUTHORABLE` named all four, 2026-08-28); the schema's
   13-value enum overstates. Cadence and regime timeframe are server-derived from the
   anchor — the vocabulary shows the measured pair for each.
4. **Which coins?** Explicit list (≤50 per the schema) or ranked category — where the
   measured ceiling is **limit 4** (BG-14 byte-cap bracket, 2026-08-28; wider reports
   refuse earlier). Realistic breadth needs explicit lists.
5. **Any trade-shape overrides?** The 16 execution parameters run on measured platform
   defaults unless overridden. Show `vocabulary()["execution"]` — defaults, schema
   bounds, catalog bounds, and the asymmetric enforcement (R:R refused at both catalog
   edges; minAtrPct persisted un-clamped outside the catalog).

Weights (0–3) fall out of "which of these beliefs is load-bearing?" — tier 3 the
thesis itself, tier 1 supporting evidence, tier 0/`context` visible but unweighted.

## 3 · The honesty gate

The refuse-and-offer-nearest policy (D3), verbatim:

> When the user's intent includes something the platform cannot measure, say plainly
> **what** cannot be measured and **why** — cite the vocabulary: the module list is
> complete, the anchor set is complete, the bounds are measured. Then offer the
> **nearest expressible thesis**, clearly labeled as different from what was asked.
> Never silently substitute.

Examples of the shape (not an exhaustive list): news, tweets, on-chain flows and
order-book depth appear in no module — name the miss, offer the closest measured
proxy (e.g. `VOLUME`/`CVD` for participation) and say in what way it is not the thing
asked for. A 1d anchor is not authorable — offer `4h` (SWING, regime read at 1d) and
label the difference. A 30-coin ranked universe cannot compile — offer ranked limit 4
or an explicit list, and say which coins fell away.

## 4 · Build and iterate

Zero live calls anywhere in this loop (D4).

1. Construct the `Thesis` (`omega.generate.Thesis`) from intake.
2. Run `omega.authoring.validate_thesis(thesis)`. **Errors block** — do not proceed to
   a brief carrying errors without saying so. Each code, explained:
   - `THESIS_UNKNOWN_MODULE` — the module is not one of the 17; `plan()` would
     silently drop it (verified 2026-08-29). The silent drop is the footgun; this
     code is the guardrail.
   - `THESIS_TOO_FEW_DIRECTIONAL` — fewer than 2 directional modules weighted;
     `plan()` silently emits NO conditions and NO verdicts (verified 2026-08-29).
     `TREND_STRENGTH` and `VOLATILITY` are filters and do not count.
   - `THESIS_BAD_WEIGHT` — an allocation tier outside 0–3.
   - `THESIS_BAD_STANCE` — not ALIGN or FADE.
   - `THESIS_UNMEASURED_ANCHOR` — outside the measured `{5m, 15m, 1h, 4h}`.
   - `THESIS_UNIVERSE_TOO_WIDE` — explicit >50 tickers (schema cap) or ranked limit
     >4 (measured BG-14 boundary).
   - `THESIS_UNFEEDABLE_REQUIRED` — a required signalId no weighted module feeds; it
     could never fire.
   - plus everything `validate_execution` returns (`EXECUTION_UNKNOWN_PARAM`,
     `EXECUTION_OUT_OF_BOUNDS`, `EXECUTION_OUTSIDE_CATALOG_BOUND` — severity per the
     measured enforcement).
3. `plan(thesis)` then `omega.authoring.brief(plan)` — **the brief is the
   deliverable**: identity, stance/anchor/gate/universe, weighted modules, thesis
   findings (codes verbatim), the full `critique()`, and the wire body's vital stats.
4. Read the brief back to the user; iterate on their reactions by editing the Thesis
   and regenerating. The Thesis is the single source of truth — never hand-edit the
   wire body.

## 5 · Live steps, each per-authorized

Nothing below happens by default, on inference, or under a general "go ahead". Each
step needs its own explicit user authorization naming the operation and the instance,
in the session where it runs. The proven procedures are referenced, not restated —
read them before running one.

**Precondition for every compile (2026-09-04):** a same-session schema-drift preflight
receipt, PASS, bound to the exact body's sha256 and not expired — produced by the
read-only procedure `python scripts/preflight.py recipe <body> --reference <id>`
(design: `docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md`). The
authorization checkbox quotes the printed `PREFLIGHT PASS · …` line verbatim. The
receipt is a precondition of asking for authorization, not the authorization itself;
its disclaimer stands: it covers the published schema and the reference record only;
the runtime validator is not observed. A refusal after a PASS voids the receipt
(`voided` with the refusal verbatim and a `gate_missed` class) and the post-refusal
read-back becomes the next baseline. ~~Until the first live run (plan task 8) has proven the ~21 KB capture path end to end, this precondition is policy ahead of evidence.~~ **Capture path, `run` and `gate` proven live 2026-09-11 — but no compile has yet been gated by a receipt, so "end to end" is still one step short.** Both captures were taken by script over the `mcporter` CLI (the MCP transport was unauthenticated in that session, so the recipe's `ToolSearch` route was unavailable — the CLI reaches the same server and account). Over that route the catalogue names the schema `inputSchema`; it must be saved under `parameters` (with `name`, `description`) or `resolve_arms` crashes on `KeyError: 'parameters'`. The definition is ~20 KB compact, ~40 KB in the committed `indent=1` shape — the recipe's "~21 KB" is the pre-54.1.0 size. The read-back came from `get_strategy`, with `request.strategyId` written into the capture — **this is mandatory, not preferred**: without it the fingerprint's record-id check compares the record with itself and a read-back of the wrong strategy passes. Every fidelity fingerprint passed (84 signalIds, 25 platform section keys, 13 timeframes; record id, 84 signalRules) and the changelog against the 2026-09-09 capture was empty. The run then did exactly what it exists to do: the suite builder's "submit-ready" payloads **FAILED** — five required fields missing, ten undeclared keys — while omega's offline validation had passed them with zero errors. The corrected wire body passed: `PREFLIGHT PASS · data/audit/compile_preflight_2026-09-11-tpo-S7-create-wire.json · body 6cc4de48 · schema 2026-09-11T06:39:14Z · ref 56c08ef6-480b-4293-8136-81beed2161cf rev 4 · expires 2026-09-11T07:39:14Z`. Both receipts are committed; the FAIL one is the evidence.

- **Compile dry-run** — authorization template: *"I authorize N compile_strategy_plan
  call(s) for <strategy/thesis name> in this session — compile only, nothing
  applied."* Procedure: [doc 16](16-the-write-path.md) compile discipline. Record the
  response verbatim into `data/audit/` before interpreting it; never commit a
  planToken (length + sha256 only). Tokens expire in five minutes — recompile rather
  than retry a stale one.
- **Create + verify + auto-archive** (P2) — authorization template: *"I authorize ONE
  apply_strategy_plan of the compiled <name> CREATE — this covers that single apply
  and nothing else,"* plus the archive disposition. Procedure: the 2026-08-28 loop,
  recorded in
  [`first_generated_apply_2026-08-28.json`](../data/audit/first_generated_apply_2026-08-28.json)
  — fresh compile, one apply (`{confirm, planToken}`, no `plan` key — doc 16 rule),
  read-back verified by script, archive immediately, quota slot returned.
- **Revise** — authorization template: *"I authorize the four-write revise loop on
  <strategyId>: restore, ≤2 compiles, ONE apply, archive."* Procedure: the 2026-08-29
  loop, recorded in
  [`first_generated_update_2026-08-29.json`](../data/audit/first_generated_update_2026-08-29.json)
  — `wire_update` (full body from the Thesis at `expectedRevision`), **pre-apply diff
  inspection** between compile and apply, and the measured caveat: a full-body UPDATE
  re-mints custom `sectionKey`s in lockstep even when the report is byte-identical —
  semantically safe, but anything caching a sectionKey across revisions holds a stale
  name. Conflict handling is deliberately unmeasured — treat it as unknown.
  **Omitted-field semantics were measured 2026-09-11: UPDATE merges.** On `56c08ef6`
  rev 3 → 4, omitting `entry`, `minAggregateScore` and `signalRules` preserved all three
  exactly, and the same held on `3d720de3` rev 1 → 2, where sending only `sections` and
  `conditions` left its 12 weighted signals, 0.65 gate, entry block and open position
  untouched. `coinSelection` is required on an UPDATE but is **not persisted** — it reads
  back `null`; it is a compile-time input for the internal validation preview. See
  [09 § the write path's remaining shapes](09-conditions.md).

## 6 · After every create or revise

Update the registry (`omega.registry`): `new_entry` at create, `add_revision` at every
lifecycle step, `save` — then regenerate the strategy's checklist beside it
(`checklist(load(id))` → `data/created/<id>.checklist.md`). Both files are committed.
The registry is P1's advisor-ready hook: id, date, the full Thesis, every revision
with its change, disposition, and the audit records that prove each step.

## 7 · What the assistant never does

- **Never binds** a strategy to an agent (`rebind_intelligence_agent`).
- **Never deploys** (`upsert_radar_deployment`, arena/market-grid entries).
- **Never predicts performance.** No outcome data supports such a claim, and the
  builder contract (P1) forbids making it anyway.

Binding and deployment move real capital. The checklist beside each registry entry
names those steps precisely so the USER can take them; no general "go ahead" ever
authorizes the assistant to take them instead (P4, and the standing rule beneath it).

## 2026-10-10: the TPO suite builder on the v91 draft lifecycle

`scripts/tpo_suite_build.py` (S1–S7, designed 2026-09-10/11 on contract 54.1.0) emitted the
flat `compile_strategy_plan` CREATE body with the pre-v84 condition grammar; contract 85.0.0
retired the tool and `tests/test_tpo_suite_wire.py` was skipped on 2026-10-09. The port keeps
every thesis — the market reads and the condition logic are unchanged — and changes only the
shape, each move from the README contract history or the saved 91.0.0 schema
([`schema_20261005T194629Z.json`](../data/contract/stage_strategy_draft/schema_20261005T194629Z.json)):

| 2026-09-11 body | now |
|---|---|
| one `<id>.wire.json` compile body | `<id>.stage.json` = `{draftVersion: 0, axes}`, the `request` of a CREATE `stage_strategy_draft` (no `strategyId`), its ten axes built by `omega.generate.StrategyPlan.axes()` from a `Thesis` carrying the member's identity, anchor, gate and universe and a `Report` of the TPO spine plus the member's extras; and `<id>.preview.json` = `StrategyPlan.preview_request()`, the FIELDS preview body |
| `closes: 1` on every condition | `hold: {atLeast: 1, of: 1}` on every clause and group (v84); a `conditionRef` carries none |
| `clock: "CLOSE", closes: 2` on `RSI_HELD_UP_2C` / `RSI_HELD_DOWN_2C` (S5) | `hold: {atLeast: 2, of: 2}` on the RSI14 clause — "2 closes in a row" (v84); the clock went at 61.0.0. `REENTRY_CONFIRMED_*` keep `{1,1}` on their ALL over refs: a group hold over members that hold their own bars is refused, so the two-bar hold lives on the referenced leg |
| `exit: false` everywhere | `exitSide: null` (v88). No member carried `exit: true`, so no `CLOSE_ON_<key>` rule arises |
| six-key `entry` mirrored from 56c08ef6 rev 4 | `ENTRY {entry: {trigger: "ON_CANDLE_CLOSE"}}` alone (`omega.generate.ENTRY_MIRROR`; 60.0.0 / v85) |
| `operation`, `intentSummary`, `assumptions` | gone (v85); their text lives on the design record `<id>.json` only |
| `coinSelection` on the body | on the preview body only (v85) |
| nothing for gates, dials, rules, market read | `SETUP_GATES` carries the 0.99 / 0 gate mirror plus `minAtrPct`; `TRADE_LEVEL_POLICY`, `POSITION_MANAGEMENT` and the 84-row `SIGNAL_RULES` (allocation 0) carry omega's measured 08-28 defaults, because a v91 axis is written whole; `MARKET_READ` is `market_read_text` over every condition |

Every design record lists the mappings it received under `v91Mappings`, and the design
record is a separate object — no design key reaches an axis (the test checks). The test walks
every axis and the preview body against the saved capture with `omega.preflight` (zero FAIL,
zero UNSUPPORTED) and `validate_conditions` reports no error and no warning on any member.

Two things the port records and does not decide:

- **Verdict resolution moved under the suite.** `ordered()` (directional-first) was
  load-bearing on 54.1.0, where resolution was first-true-wins. Since 56.1.0 a coin resolves over
  the DISTINCT verdicts of the carriers that read TRUE and disagreeing carriers resolve
  `NEITHER`; every LOC tag is a `NEITHER` carrier and a re-entry is TRUE together with
  `INSIDE_PRIOR_VALUE`, so S2–S5's directional legs resolve `NEITHER` when they fire. That is a
  semantics change, not a grammar mapping; it is on every design record
  (`verdictResolutionNote`) for the author, and no condition was changed.
- **Hold ceilings are unmeasured for this report.** The 2026-10-06 M2 read covers the five
  presets' headers (`RSI14_now` admits 192 bars at 1h); the `RSI14` value header and every
  TPO header have no `conditionHold` row on disk. The builder judges `{2,2}`; omega warns only
  where the header is not candle-moved, and RSI14 is.

`scripts/tpo_suite_preview.py` (read-only, `preview_strategy_report` only) now sends
`<id>.preview.json` verbatim and reads the v84 evidence shape. `scripts/build_pvm_strategy.py`
and `scripts/write_drift.py` served the compile path only and are marked retired in place.
Nothing was staged, previewed or committed by the port.

## 2026-10-13: S8 "POC Reject" - the platform's own reading of S6

`levelInteraction` was measured on `PRIOR_TPO_POC` in the re-extraction at 108.4.0, which unblocks the reading the
README gives for S6. It is added as **S8**, not swapped into S6: the platform takes a reject's side from where the
**prior close** stood against the prior bar's level, S6 from where the bar **opened**, so the two differ on a bar that
gaps across the POC - and changing S6 would change what it believes. S8 is one column (`pTpoPOC_lvl`) and two carriers
(`reject_from_above` → UP, `reject_from_below` → DOWN) over the suite's location tags. It validates with no error and no
warning, and one read-only preview (`data/audit/tpo_s8_preview_2026-10-13.json`) shows the platform accepts it and
resolves both carriers on all eight coins. Nothing was staged.
