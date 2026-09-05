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
read-back becomes the next baseline. Until the first live run (plan task 8) has proven the ~21 KB capture path end to end, this precondition is policy ahead of evidence; the run that proves it is recorded in the spec's status line.

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
  name. Conflict handling and omitted-field semantics are deliberately unmeasured —
  treat them as unknown.

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
