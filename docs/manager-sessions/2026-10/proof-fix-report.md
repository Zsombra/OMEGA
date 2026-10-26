# Proof-fix report (2026-10-17, written 03:36Z)

Brief: `proof-fix-brief.md` beside this file. No BattleGrid call was made. The only network calls were two downloads of
GitHub's tag tarball for OMEGA v0.8.2.

## Part A: OMEGA

Worktree `C:/tmp-omega-fix`, branch `fix/condition-keys-and-mfi`, cut from `origin/main` 3157f72.

| commit | what |
|---|---|
| `899fb9e` | Condition-key prefix always matches the platform's key pattern |
| `bfd42fa` | MFI gates on MFI14_now at the measured 50 midline, not on MFI14_zone |
| `10bdb67` | `--no-ff` merge to `main`, pushed |
| tag `v0.8.2` | annotated tag object `2c56448584ccf9b0a531f0281875aa7531ebb60e` on commit `10bdb6712f99185886d44a166e9c39c7cff28f5a`, pushed |

The OMEGA suite was 1541 passed on the branch and again on merged `main`. Before the change it was 1470 passed. The
new tests add 71: 29 for the prefix and 42 for the clause sweep.

### 1. Key prefix rule (`omega.generate.condition_prefix`)

The rule applies these steps in order:
1. **Legacy prefix.** Take the first character of each of the name's first two words and uppercase them. Keep this
   prefix whenever it matches `^[A-Z][A-Z0-9_]{0,3}$`.
2. **Letter rule.** If the legacy prefix fails, take the first ASCII letter of each of the first two whitespace
   words that have one, and uppercase them.
3. **Fallback.** If no word has an ASCII letter, use `"SETUP"`.

Step 1 goes slightly beyond the brief. Its rule ("keep today's prefix when the first two words start with letters")
would have moved real keys. For example, "PVM 15m" has always given `P1`, which the platform accepts. The letter
rule would turn it into `PM`, and every stored `P1_*` key would change. Keeping any legal legacy prefix means no
stored key can move.

Pinned examples:

| name | prefix |
|---|---|
| "4h Low-Vol Fade" | `HL` (the brief suggested LV or LVF; the "first ASCII letter of each word" rule gives HL) |
| "1h Breakout Retest" | `HB` |
| "-- Fade --" | `F` |
| "*** !!! ???", "", "2024 365" | `SETUP` |
| "Élan Vital" | `LV` |
| "日本 Momentum" | `M` |
| "PVM 15m" | `P1` (legacy prefix kept) |

The prefix is at most 5 characters, so the longest key, `CLOSE_ON_<P>_CORE_DOWN`, is at most 24.

Tests are in `tests/test_condition_prefix.py`:
- the rule table;
- every emitted key matches the pattern, for digit-led, empty, punctuation and non-ASCII names;
- legacy prefixes are unchanged for the presets and for live fleet names;
- the presets' keys are pinned;
- `axes_update(current)` keeps the held keys for every preset with all seven exits;
- a sweep over the 5 PRESETS plus 20 synthetic names (a seeded random set and fixed edge cases).

### 2. MFI

Before the fix, all four MFI readings failed OMEGA's own check (`MFI14_zone` is DISJOINT). MFI now reads:
- up: `MFI14_now gte 50`
- down: `MFI14_now lt 50`
- fade_up: `MFI14_now lt 50`
- fade_down: `MFI14_now gte 50`

The fade readings mirror the midline, the same way BOLLINGER and STOCHASTIC mirror theirs.

Evidence:
- **The zone column cannot gate.** In `data/contract/columns/_observed_vocabulary.json:47-62`, `MFI14_zone`
  declares overbought/oversold/neutral but was observed to emit only bearish/bullish (0 of 12 samples matched).
  Line 61 gives `numericReplacement: "MFI14 lt 50 (bearish) / MFI14 gte 50 (bullish)"`. Lines 114-145 show the
  replacement was verified live on 2026-08-24 on BTC, SOL and XRP (`reproducesZoneExactly: true`). Lines 155-158
  record 15 samples supporting the cut-offs.
- **`MFI14_now` accepts numeric conditions.** `data/audit/compile_dry_run_2026-08-29-deep-tail-fade.json:3323-3340`
  (outputType numeric 0-100) and `:4859-4870` show `MFI14_now` served with conditionOperators
  `lt, lte, gte, gt, between`. OMEGA's `report_headers` derives the same operators.
- **Supporting row.** The live render in the same file (`:4183`) shows BTC `MFI14_now` 76.3 with zone "bullish",
  which fits the 50 split. It also shows the platform does not label ~76 as "overbought".

I judged this evidence unambiguous enough to use a numeric reading rather than context-only. The column is served
as numeric-conditionable, and 50 is the measured replacement. I did NOT use the brief's 80/20 thresholds because
those were never measured, which is why the fade readings mirror the midline. The 50 cut-off is labelled "inferred
from observations" in the file, but that only affects how well it reproduces the zone. It does not affect whether
the clause is legal.

The menu's MFI description now says it reads the 50 midline and that its zone column is display-only. The MFI
recipe columns are unchanged.

### 3. Sweep for other stale recipes

`tests/test_module_clauses_conditionable.py` runs every `MODULE_CLAUSES` reading (40 in total, across 17 modules)
through the checks a plan runs:
- `report_headers`: the header exists, the operator is admitted, and any label is in the vocabulary;
- not measured DISJOINT;
- `validate_conditions` returns no errors.

**MFI was the only stale recipe; every other reading passes.**

### Pin hash

How the manager computes the pin's sha256 (`manager/omega_pin.py`, `scripts/install_omega.py`): it is the sha256 of
the bytes of GitHub's tag tarball, `https://github.com/Zsombra/OMEGA/archive/refs/tags/<tag>.tar.gz`.
`install_omega.verify` hashes the downloaded (or `--from`) archive and refuses a mismatch. The installer writes
`MANAGER_PIN.json` `{tag, sha256}` into the extracted tree, and `require_pin` checks it.

For v0.8.2:
- size: 4,363,005 bytes;
- sha256: `c4581b8ef8428abcece950dc10f1296dc7483e1625c85317102e4880954d2a08`;
- identical on two downloads.

## Part B: battlegrid-manager

Worktree `C:/tmp-bgm-pin082`, branch `fix/omega-082-and-brief`, cut from `origin/main` 49150c5. The branch is NOT
merged, pushed or deployed.

| commit | what |
|---|---|
| `bfe2cea` | Pin OMEGA v0.8.2 |
| `097b321` | Strategist brief changes plus `tests/strategist/test_brief.py` |

### Pin change

The re-pin follows the v0.8.1 re-pin (7e5b60d):
- **Pin constants.** `manager/omega_pin.py` sets TAG to `v0.8.2`, COMMIT to `10bdb67…`, and SHA256 to `c4581b8e…`,
  and adds a history note.
- **Build and docs.** The `Dockerfile` comment, `vendor/README.md` and `docs/phase-0/runbook.md` now name v0.8.2.
- **Tests.** Updated `tests/allocation/test_omega_pin.py`, `tests/authoring/test_install_omega.py` (renamed to
  `..._v0_8_2_...`), `test_pipeline.py`, `test_pin.py` (a comment only; the manifest is unchanged from v0.8.1),
  `tests/authoring/support.py` (a comment) and `tests/commands/test_strategy.py` ("omega pin: v0.8.2").
- **Local install.** The archive is at `battlegrid-manager/vendor/omega-v0.8.2.tar.gz` (gitignored). It was
  installed with the branch's `scripts/install_omega.py` into `battlegrid-manager/.omega/v0.8.2`, and `pip -e` into
  the shared `.venv`.
- **Tests run.** The pin, authoring and strategy command tests gave 130 passed. The strategist tests gave 36 passed
  (now 43, with the 7 new brief tests).

### Brief diff summary (`manager/strategist/brief.md`)

- **exits:** the brief lists the seven roles verbatim (`RISK_ON, CTX_UP, CTX_DOWN, CORE_UP, CORE_DOWN, UP, DOWN`)
  and says `exits` holds only those or an empty list, never a clause, with "MACDhist_trend is falling" given as the
  refused example. If the exit the user wants is not a role, the model says so in `reply`.
- **Tiers:** 1, 2 or 3. Tier 0 is not used; such modules go to `context`. The old "(0-3)" line is removed.
- **Directional modules:** `weights` needs at least two. The reason is given (one directional module builds no
  entry gate, so the strategy never trades), and the filter modules TREND_STRENGTH and VOLATILITY are named as not
  counting.
- **D8 (rule 3):** when parts are unmappable and a nearest thesis is offered, `reply` must say plainly it is a
  DIFFERENT strategy from the one asked for ("This is a different strategy from what you asked for:"). The model
  must never present it as the user's idea.
- **Name:** must start with a letter, with the timeframe after it ("Low-Vol Fade 4h").
- **Tool call shapes:** none.

`tests/strategist/test_brief.py` checks that:
- every `EXIT_ROLES` entry is in the brief, in order, and nothing else is on that line;
- the brief forbids clauses in `exits`;
- the tier wording is there and "(0-3)" is gone;
- the two-directional requirement is stated, and the filter set matches `vocabulary()`;
- the D8 wording and the name rule are there;
- there are no tool call shapes.

### Full suite

One run on the branch, in the background, without `-x`: **4207 passed, 5 skipped**, 3 warnings, in 6m05s. The
warnings are pre-existing (an anyio deprecation and two invalid escapes in `tests/review/test_take.py`).

## Concerns

- **The shared dev venv now runs OMEGA v0.8.2.** `battlegrid-manager/.venv` has v0.8.2 installed editable. Until
  this branch merges, the pin tests in the main manager checkout (which still pins v0.8.1) will fail `require_pin`.
  Re-running `install_omega.py .omega/v0.8.1` restores it. The deployed image is untouched and still on v0.8.1.
- **The MFI change also changes revisions.** For any existing strategy that weights MFI, its CORE checklist now
  reads `MFI14_now` instead of `MFI14_zone`. Before, those MFI clauses were refused or always FALSE, so this is a
  fix, but a revision will show it as a clause diff.
- **The 50 midline is still a sample.** It rests on 15 samples from one time point in 2026-08-24. Re-measure it on
  the next live preview.
- **"4h …" names give `HL`, not `LV`.** This follows the brief's per-word rule rather than its example. The brief
  now steers the model to put the timeframe last anyway.
