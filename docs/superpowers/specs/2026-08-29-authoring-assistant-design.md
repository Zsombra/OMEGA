# The Authoring Assistant — Design

Approved 2026-08-29, brainstormed interactively. This is roadmap step 3 — the
destination: the intent → Thesis assistant, scoped by the four 2026-08-28 decisions
(builder advisor-ready / create-verify-auto-archive / full measured menu /
prepare-never-execute) plus the four below. Kept deliberately small: the generator is
already thesis-generic (verified 2026-08-29 — sections from `MODULE_RECIPES`,
allocations from weights, conditions from the stance-aware DAG; the presets are just
example Theses), so this build is the authoring surface around it, nothing more.

## The four decisions (user's choices, 2026-08-29)

1. **Runtime: "Claude driving omega."** The assistant is a Claude session in this
   repo following a documented procedure. No Python NL parsing, no CLI wizard.
2. **Scope: "Full Thesis surface."** Everything the generator supports and the
   campaigns measured: 17 modules × weights 0–3, ALIGN/FADE, the 4 anchors, gate,
   required, context, universes (explicit ≤50 / ranked ≤4), execution overrides.
3. **Unmappable intent: "Refuse + nearest expressible."** Say plainly what the
   platform cannot measure and why; offer the nearest expressible thesis, clearly
   labeled as different — never silently substituted.
4. **Endpoint: "Offline deliverable."** A conversation ends with the validated
   Thesis + full critique + wire body, zero live calls. Compile / create / revise
   each happen only on the user's ask, per-instance authorized, using the proven
   loop patterns (create 2026-08-28, revise 2026-08-29).

## Components

**A. `omega/authoring.py`** — the one substantial new module, deterministic:

- `vocabulary() -> dict`: the assistant's complete menu — the 17 modules (each with a
  plain-language "what it measures" line and its ALIGN/FADE readings), the 4 measured
  anchors with cadence/regimeTimeframe, universe rules with the BG-14 boundary, the
  16 execution params with defaults/bounds/enforcement. Derived from
  `MODULE_RECIPES`/`MODULE_CLAUSES`/`CADENCE_FOR_ANCHOR`/`REGIME_TF_FOR_ANCHOR`/
  `RANKED_LIMIT_MEASURED_MAX`/`omega.execution` — never a hand-written duplicate of
  something a map already knows. The only hand-written part: the per-module
  plain-language descriptions (they exist nowhere machine-readable).
- `validate_thesis(thesis) -> list[Finding]`: the guardrails `plan()` lacks, each a
  measured footgun or a hard bound —
  `THESIS_UNKNOWN_MODULE` (plan() silently drops unknown weight keys — verified),
  `THESIS_TOO_FEW_DIRECTIONAL` (fewer than 2 directional modules → plan() silently
  emits NO conditions and NO verdicts — verified),
  `THESIS_BAD_WEIGHT` (outside 0–3), `THESIS_BAD_STANCE` (not ALIGN/FADE),
  `THESIS_UNMEASURED_ANCHOR` (outside the 4), universe bounds (explicit >50 /
  ranked > `RANKED_LIMIT_MEASURED_MAX`), `THESIS_UNFEEDABLE_REQUIRED` (a required
  signalId no weighted module feeds), and execution findings via the existing
  `validate_execution`.
- `brief(plan) -> str`: the offline deliverable — name/stance/anchor/universe, the
  weighted modules, `validate_thesis` + `critique()` findings, the effective
  execution profile, and the wire body's vital stats. One honest page.

**B. The creation registry — `data/created/<strategy-id>.json`**, committed:
`{id, createdDate, thesis (asdict), revisions: [{date, revision, change}],
disposition, auditRecords: [paths]}`. Written by the procedure at create/revise time.
This is the advisor-ready hook: performance can attach later without rework.

**C. The prepare-never-execute checklist — `checklist(entry) -> str`** (markdown, per
strategy, saved beside the registry entry): the exact manual steps the USER would
take to let it trade — restore if archived, the bind call
(`rebind_intelligence_agent`) and radar deployment (`upsert_radar_deployment`) named
with prepared parameters, the capital-risk warnings, and the standing rule that the
assistant never executes these. App-UI specifics we have not measured are labeled
unverified, not invented.

**D. `docs/20-the-authoring-procedure.md`** — the conversation protocol any session
follows: intake (what the user believes → modules/stance/anchor/universe), the
refuse-and-offer-nearest policy, the iteration loop, the exact per-instance
authorization sentences for each live step (compile dry-run; create+verify+
auto-archive; revise via `wire_update`), registry upkeep, and the pointer map to the
records that back every claim.

**E. Tests** (all offline): `vocabulary()` completeness pinned against the module
maps and measured constants; every `validate_thesis` code exercised, the two footguns
included; `brief()`/`checklist()` content pins; registry round-trip.

## Deliberately absent (lean by instruction)

- Python natural-language parsing, CLI wizards, any second conversational layer.
- Performance/outcome claims of any kind — the builder contract stands.
- Executing binds or deployments — prepare-never-execute, permanently.
- New platform measurement — this build consumes only measured facts.
- Preset changes, generator changes beyond none, new condition machinery.

## Success criteria

A fresh session, given only this repo, can: take a plain-language intent; refuse the
unmappable parts honestly; produce a validated Thesis and its one-page brief with
zero live calls; and, on explicit per-instance authorization, run the proven
create/revise loops and keep the registry current. Suite stays green; no live calls
in any test.
