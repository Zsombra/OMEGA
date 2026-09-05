# 2026-09-04 · Schema-drift preflight — design

**Status:** implemented 2026-09-05 (tasks 1–7 of docs/superpowers/plans/2026-09-04-schema-drift-preflight.md); first live run pending the user's ask (task 8).

## Problem (measured, not speculative)

The BattleGrid platform changes what its compile endpoint expects without warning.
Five instances are on record, each costing a refused live call and a round of
rediscovery until the fifth, which was caught offline:

| # | date | what changed | visible in the published schema? | visible in a record read-back? |
|---|------|--------------|----------------------------------|-------------------------------|
| 1 | 2026-08-15 | `regimeAutoDerive`/`regimeTimeframe` declared required then rejected (Grid-Commander era; primary record not in this repo) | partly | not tested |
| 2 | 2026-08-2x | key mismatch on the write surface (`write_surface_gap.json`) | yes | n/a |
| 3 | 2026-08-29/30 | `conditions[].clock`, `closes`, `sections[].notes` required by the validator before the schema declared them | **no** at the time; caught up 08-30 | **yes** (6a8bca67 read back migrated) |
| 4 | 2026-08-30 | `entry.levelSource`, `levelOffsetAtrMultiple`, `validForBars` required by the validator, undeclared | **no** (schema still declared 4 of 7 hours later) | **yes** (6a8bca67 re-migrated, no revision bump) |
| 5 | 2026-09-04 | `conditions[].exit` required; `decisionInvalidationExitEnabled` optional; two new `entry.trigger` enum values | **yes** | **yes** (both records migrated, no revision bump) |

Two facts follow and the design rests on them. A schema fetch alone is not enough:
instances #3 and #4 were invisible in the published schema while the runtime validator
already enforced them. A record read-back alone is not enough either: it shows migration
defaults but not enums, bounds or required lists. Both, taken fresh, would have caught
every instance from #3 on before a call was spent. Instance #5 was caught exactly that way.

Everything below is a design for automating the two read-only steps that worked on
2026-09-04, and for making the compile authorization depend on them.

## Non-goals

- No compile, apply, restore, bind or deploy inside the preflight. It never mints a token.
- omega never calls the connector (`omega/probe.py:3` rule). No HTTP client is added.
- No inference of semantics. A FAIL names a field; a human reads a record back and mirrors.
- No new dependency (`jsonschema`, `regex`) without a separate user decision. The walker
  covers only the subset of JSON Schema the compile definition actually uses.
- Nothing stored in the repo is ever the truth for a verdict. Committed captures are test
  fixtures and a changelog, never the reference for a PASS.

## Architecture

Three components with one-way dependencies: session procedure → captures on disk →
Python diff → receipt on disk → plan gate.

**1. Session procedure (read-only, run by the assistant in the session).**
Produces two verbatim captures under `data/contract/`, following the `probe.py` shape
`{capturedAt, how, request, response}`:

- `data/contract/compile_strategy_plan/schema_<capturedAtZ>.json` — the tool definition
  as returned by `ToolSearch select:mcp__…__compile_strategy_plan`. A definition load,
  not a call.
- `data/contract/get_strategy/<strategyId>_<capturedAtZ>.json` — the full response of
  `get_strategy(strategyId, includeInactive: true)` for the reference record.

Both are agent transcriptions. Fidelity is checked by the Python step (below), not
assumed. The Write tool's ability to persist ~21 KB in one call is unverified; the
procedure writes in ≤ 6 KB chunks and concatenates if a single write fails, and records
the method in the capture's `how` field.

**2. `omega/preflight.py` (pure Python, no I/O beyond reading the files it is given).**

- `load_schema_capture(path)` → the CREATE/UPDATE/RESTORE arms, resolving the local
  `$ref`s the definition uses. Unresolvable constructs (a non-local `$ref`, an `anyOf`
  with no `operation` discriminator) become an explicit `UNSUPPORTED` finding, never a
  silent stop of the walk.
- `fingerprint_schema(arm)` → the fidelity checks against data the repo already holds
  independently of any schema capture (verified 2026-09-04): `rules[].signalId` enum equals
  the 84-id union of `moduleSignals` in `data/derived/signal_module_map.json`; the platform
  `sectionKey` enum equals the 25 `templates` entries in
  `data/contract/templates/platform/_all.json`; the `timeframe` enum equals the 13
  `absoluteTimeframes` in `data/contract/vocabulary/_shared.json`; every `required` list is
  present. A failed fingerprint is `TRANSCRIPTION_SUSPECT` and the verdict is FAIL
  regardless of the diff.
- `fingerprint_readback(capture, strategy_id)` → `strategy.id` equals the requested id,
  `signalRules` has 84 entries, `conditions` is a non-empty list. Same consequence.
- `diff(body, arm, record)` → a list of findings, each `{cls, path, detail, verdict}`,
  with a fixed class vocabulary:
  - `UNDECLARED` — body key the arm does not declare. FAIL. The finding text says that
    `additionalProperties: false` is schema-derived and not measured (`write_surface_gap.json`).
  - `MISSING_REQUIRED` — arm-required key the body omits. FAIL.
  - `MISSING_VS_RECORD` — a key the read-back record carries that the body omits,
    inside a request-shaped nested object (`entry`, each `conditions[]` element, each
    custom `sections[]` element, each `rules[]`/`signalRules[]` element, each column).
    FAIL, whether or not the arm declares the key — instances #3 and #4 were exactly
    undeclared-but-present-in-the-record. For arrays the exemplar is the *intersection*
    of keys across the record's elements (so an optional `window` on some columns is not
    flagged). At the top level the rule is weaker on purpose: a record key the body
    omits is `INFO` if the arm declares it as optional (the 16 platform-defaulted
    execution parameters measured 2026-08-27; `decisionInvalidationExitEnabled`) or does
    not declare it at all (`id`, `revision`, `cadence`, …), and `WARN` if it is an object
    the body lacks entirely. Required top-level keys are already `MISSING_REQUIRED`.
    Two structural deltas are named, each with its measured reason, and nothing else is
    allowlisted: the record calls `rules` `signalRules` (2026-08-29 read-back), and the
    platform mints `sectionKey` on custom sections (`custom:<uuid>`, never sent). A record
    key whose value is null on every element is `INFO` (the platform's not-set default,
    e.g. the optional section-level `timeframe`); a null carries nothing to mirror, and no
    drift instance to date was null-valued.
  - `ENUM` — body value not in the arm's enum. FAIL.
  - `BOUNDS` — body number outside the arm's minimum/maximum/exclusiveMinimum. FAIL.
  - `MIRROR` — a value omega hardcodes as a platform mirror (`entry.*`,
    `conditions[].clock/closes/exit`) differs from the record's value. WARN, never FAIL:
    the user decides whether to re-mirror. `sections[].notes` is excluded (omega sends a
    provenance string on purpose; null acceptance is unmeasured).
  - `CHANGELOG` — enum growth, new optional keys or bound changes versus the most recent
    committed schema capture. INFO only. Today it would have logged `STOP_THROUGH_LEVEL`
    and `ON_RETEST`.
- `verdict(findings)` → PASS if no FAIL-class finding, else FAIL; always accompanied by
  the fixed disclaimer: *"covers the published schema and the reference record only;
  the runtime validator is not observed by this check."*

**3. `scripts/preflight.py` (CLI, the interface between package and session).**

- `recipe <body.json> [--reference <id>]` — prints the numbered session procedure for
  this body: the two fetches, the file names to write, the fidelity fields to eyeball.
  Mirrors `omega.probe.FETCH_RECIPE`.
- `run <body.json> --schema <capture> --readback <capture> [--expires-minutes 60]` —
  runs the diff, writes the receipt, prints the gate line.
- `gate <receipt>` — exit 0 only if the receipt is PASS, the body file's sha256 matches,
  `expiresAt` is in the future, and `voided` is absent. Otherwise exit 1 with the reason.

## Receipt (the artifact the authorization depends on)

`data/audit/compile_preflight_<YYYY-MM-DD>[-<slug>].json`, audit-record conventions:

```
{ "_what", "when", "body": {"path", "sha256", "operation"},
  "captures": {"schema": {"path", "capturedAt", "fingerprint"},
               "readback": {"path", "capturedAt", "strategyId", "revision", "fingerprint"}},
  "findings": [...], "verdict": "PASS"|"FAIL", "expiresAt",
  "disclaimer", "unmeasured": [...], "voided": null | {"at", "reason", "refusalRecord"} }
```

Gate line printed on PASS and quoted verbatim by the plan checkbox:
`PREFLIGHT PASS · <receipt> · body <sha8> · schema <capturedAt> · ref <id> rev <n> · expires <expiresAt>`

## Session procedure (per compile)

1. The user asks for the preflight by name, naming the read: *"run the preflight for
   `<body>` against `<strategyId>`"*. Read-only calls need no write-path authorization,
   but the ask is explicit, not inferred from a broader request.
2. `python scripts/preflight.py recipe <body>` — prints steps 3–5 for this body.
3. ToolSearch fetch of the compile definition; save verbatim to the named capture.
4. `get_strategy(<id>, includeInactive: true)`; save verbatim to the named capture.
5. `python scripts/preflight.py run …` — receipt written, gate line printed.
6. On FAIL: stop. For each `MISSING_REQUIRED` / `MISSING_VS_RECORD` finding, the value to
   emit is the record's value if the record has one; if no record carries the field, the
   user chooses and the receipt records the value as `user-chosen, not extracted`. Amend
   omega in its own commit with tests, re-run from step 5 (captures may be reused within
   the expiry window).
7. On PASS: the plan's authorization checkbox quotes the gate line; the doc 20 §5
   verbatim per-instance authorization sentence is then requested from the user exactly
   as before. The preflight changes nothing about who authorizes the compile.
8. If the compile is refused anyway: append `voided` to the receipt with the refusal
   verbatim and a `gate_missed` class from a fixed list (`required-but-unpublished-and-
   unmigrated`, `published-but-unrecognized`, `below-schema-bound`, `compiler-semantic`,
   `preview-cap`, `deployment-between-capture-and-call`, `transcription-error`), and the
   post-refusal read-back becomes the next baseline. The miss ledger is how
   `would_have_caught` grows from measurements rather than claims.

## Reference record

Chosen by role, not by fixed id, and named in the ask:

- CREATE: the newest omega-created record (today `b9438519`, revision 2) as primary —
  it is omega's last accepted output. The oldest owned record (today `6a8bca67`) as a
  second read when the primary's `MIRROR` findings are ambiguous; two records separate
  server-derived values from migration defaults.
- UPDATE: the revise loop's existing pre-state read of the target strategy *is* the
  read-back capture. No extra call.

## Staleness defence

- Both captures are fetched fresh for every run; `expiresAt` defaults to 60 minutes from
  the older capture. Drift #4 landed between two calls on one day, so a calendar-day
  rule is provably too coarse; the window is a parameter, and the default is a judgment
  recorded here, not a measurement.
- The receipt is bound to the body's sha256; any edit to the body invalidates it.
- Committed captures are read only by `CHANGELOG` (as history) and by tests (as
  fixtures). `gate` never reads a committed capture.
- The pinned sets in `tests/test_write_surface.py` (`API_ACCEPTS`/`API_REQUIRES`) stay
  as they are: dated pins, re-verified live before any compile, updated in their own
  commit. A test asserts the pins agree with the *named* fixture capture of 2026-09-04,
  never with "the latest" capture, so a capture refresh does not silently change the
  suite's meaning.

## Testing (no platform access from pytest)

- Walker unit tests against a small hand-built schema fixture, labelled as a walker
  fixture only, never as a regression oracle for `wire()`.
- Replay tests from real records: the drift #5 record (`exit` missing → `MISSING_REQUIRED`
  and `MISSING_VS_RECORD`), the 08-30 create record (three `entry` fields → 
  `MISSING_VS_RECORD` against a read-back that has them while a 4-field schema does not),
  the step-0 record (`clock`/`closes`).
- `fingerprint_schema` tests: a capture with the `signalId` enum truncated by one is
  `TRANSCRIPTION_SUSPECT`.
- `gate` tests: expired, sha mismatch, voided, and PASS.
- The first live run must prove the capture path (the ~21 KB write) before the fidelity
  invariants mean anything; that run's captures become the named fixtures.

## Cost per run

One ToolSearch definition load, one read-only `get_strategy` (quota-free per docs/10),
roughly 35 KB of agent transcription, one Python command. Well under a minute of session
time; no platform quota.

## Would it have caught the measured instances?

- #5: yes (`MISSING_REQUIRED` from the schema; `MISSING_VS_RECORD` from the record).
- #4: yes via `MISSING_VS_RECORD` — *in principle*: every read-back in the repo was taken
  after the refusal, so whether a read immediately before would already have shown the
  migrated shape is not established. Stated, not claimed.
- #3: same as #4.
- #2: yes (`UNDECLARED`/`MISSING_REQUIRED`).
- #1: not from this repo's records; not claimed.
- Anything the runtime validator enforces without publishing and without migrating
  existing records: **no**. That is the residual risk and the disclaimer says so on
  every PASS.

## Failure modes

- Transcription error in a capture → caught by fingerprints or, failing that, fails
  toward alarm (a dropped key shows as `UNDECLARED`/`MISSING_REQUIRED`).
- Platform migrates records at read time rather than in storage → a read-back still shows
  the fields; the design holds but cannot tell the two apart and does not claim to.
- Deployment between capture and call → not detectable; the miss ledger records it.
- Allowlist rot → designed out: no hand-kept key list; record-vs-schema membership is the rule.

## Open questions settled by defaults (change them in the plan if you disagree)

- Expiry default: 60 minutes.
- Capture location: `data/contract/<tool>/`, probe.py shape.
- Walker: pure Python over `properties/required/enum/minimum/maximum/exclusiveMinimum/
  const/anyOf-by-operation/$ref(local)`; no dependency added.
- `MIRROR` findings are WARN, never FAIL.
