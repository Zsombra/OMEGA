# 2026-08-29 · Out-of-sample re-pull protocol

The Deep-Tail Fade thesis rests on one seventeen-day August window. The candle
endpoint serves only the **last 100 closed bars**, so out-of-sample evidence
exists only if someone pulls it before the window scrolls away — at 1h that is
**every ≤4 days** (100 bars = 4d4h). A missed pull is evidence permanently lost.
This protocol makes each pull a one-line ask a cold session can execute.

**Authorization:** all calls here are read-only (`get_coin_candles`,
`get_top_ranked_coins`, Hyperliquid public funding). The user asking to "run the
re-pull" is sufficient; no write-path authorization is involved.

## The pull (per run)

- [ ] `get_coin_candles(ticker, "1h", limit=100)` for the 13-coin set:
      **BTC, ETH, SOL, PEPE, POPCAT, MET, MELANIA, TRUMP, HYPE, MOODENG, AIXBT,
      CAKE, LDO** (keep the set FIXED across runs — changing it reintroduces
      selection bias; if a ticker delists, record that, don't substitute).
- [ ] Optional extension (cheap, keeps the trend side observable):
      BTC/ETH/SOL at `4h`.
- [ ] Hyperliquid funding history for BTC/ETH/SOL (see
      `data/research/2026-08-29-deep-tail-fade/fetch_funding.py` shape) —
      also note the **sign mix**: the FUNDING-leg confound resolves only in a
      window containing negative-funding hours.
- [ ] Write `raw/_pulled_at.json` as `{"start": "<date -u before the first call>", "end": "<date -u after the last call>"}` (from run 4 on; exact bar age for the SETTLED view).
- [ ] Save each response's `candles` array VERBATIM to
      `data/research/2026-08-29-deep-tail-fade/repulls/<YYYY-MM-DD>/raw/<TICKER>_<tf>.json`
      (16 files; a subagent keeps the payloads out of the main context — retry a
      failed call once, record the error verbatim, never fabricate rows).
- [ ] `python …/repulls/verify_repull.py <YYYY-MM-DD>` — checks against EVERY prior
      source; fails on gaps, dupes, zero overlap, or a price restated by >1%;
      RECORDS (does not fail) volume/tick revisions to
      `data/audit/candle_restatement_<date>.json`. See the 2026-09-02 amendment.
- [ ] `python …/repulls/assemble_repull.py <YYYY-MM-DD>` — writes `candles.json`
      and `funding_raw.json` (continues from the latest funding row anywhere in
      the record). Commit the data — it is irreplaceable.

## The analysis (per run, offline)

- [ ] Rebuild the combined per-coin 1h series (base corpus + all repulls,
      deduped by timestamp; gaps are recorded, not interpolated).
- [ ] `python …/repulls/analyze_repull.py` (identical math to `test_c_wide.py`;
      `POLICY=latest` by default, see the amendment) on the combined corpus AND
      on the new-only slice (cumulative across repulls; `WINDOW=last` gives the
      single-window cut as a supplementary number, never as THE number):
      reversion hit/edge at >50/75/90th pct stretch, VWAP4-vs-SMA4 ablation,
      W∈{3,4,6,8} sweep.
- [ ] Record a dated addendum in
      `docs/superpowers/specs/2026-08-29-deep-tail-fade-research.md`:
      the >90th-pct 1h cell (hit%, edge, n) out-of-sample is THE number that
      decides whether Deep-Tail Fade keeps its weights. Pre-registered reading,
      to keep us honest: sustained out-of-sample hit ≤ 55% or edge ≤ 0 at the
      deep tail = the thesis's premise failed and the registry entry should say
      so; do not move the goalposts to a different cell that happens to work.

## Amendment 2026-09-02 · the platform restates served bars

Re-pull 2 found that `get_coin_candles` returns different values for bars it had
already served: on 2026-09-02 every series differed from the 08-29/08-30 record
(253 bars, 270 fields — volume revised upward on 235, never down; prices by one to
a few ticks on 35, max 0.23%; the 4h series show a clean start ≈ 2026-08-22T08:00Z).
Transcription was ruled out three ways; verbatim record in
`data/audit/candle_restatement_2026-09-02.json`. The cause is unknown and is not
inferred here.

Two rules written above therefore had to change, and this is a **post-hoc
amendment** — made after seeing the data, and recorded as such:

1. **Integrity.** "0 OHLCV mismatches" is no longer attainable. `verify_repull.py`
   fails on gaps, duplicates, zero overlap, or any price field restated by more
   than **1%** (chosen 2026-09-02 as well above the observed 0.23% tick noise);
   every other difference is recorded verbatim to `data/audit/` and reported, not
   failed. A recorded revision is still a finding to mention in the addendum.
2. **Collisions in the battery.** `analyze_repull.py` no longer refuses to merge
   disagreeing sources; it resolves them explicitly with `POLICY=latest` (the
   platform's current view) by default, `POLICY=first` reproducing every earlier
   run's pool, and `POLICY=strict` restoring the original refusal. It aborts under
   every policy if a close differs by more than 1%.

**Why this is not moving the goalposts:** the amendment changes how sources are
merged, not the cell, the thresholds, the window, the coin set, or the
pre-registered reading. It was adopted only after THE cell had been computed under
both policies and found identical (n=58, 58.6% ±12.7pp, +1.8 bps). If a future
restatement ever makes the two policies disagree at the cell, report both and say
so; do not pick the one that reads better.

## Amendment 2026-09-05 · young bars are held back in a SUPPLEMENTARY view (pre-registered before run 4)

Run 3 measured that bars ≤6h old at pull time are served incomplete (18/40 later
revised, 0/1040 older; `data/audit/partial_pulls_repull3/`). The cell's reference is a
volume-weighted 4-bar mean, so a short volume in a young bar moves the deviation that
decides cell membership. `analyze_repull.py` now takes `SETTLED=<hours>` (default 0):
with `SETTLED=6` every bar that was younger than 6h when its winning source served it is
dropped. Pull times are not stored per source; the age proxy is the source's latest bar
close, which understates age by up to ~1h (run 3 pulled 33–40 min after its last close),
so the rule is slightly lenient, not strict.

**What this does NOT do:** the pre-registered reading stays `SETTLED=0`, cumulative
NEW-ONLY >90th, hit ≤55% or edge ≤0 sustained. The settled view is reported alongside
from run 4 on and cannot trigger or un-trigger the failure rule by itself. If the two
views ever disagree on the verdict, that is a data-quality fact to record, not a licence
to pick the friendlier number.

**Measured on runs 1–3 (2026-09-05, before any run-4 data exists):** exactly the 6
youngest bars per 1h coin are held back (run 3's tail; every earlier tail was re-served
by a later pull). Cumulative cell `SETTLED=0`: n=105, 55.2% ±9.5, +3.0 bps.
`SETTLED=6`: n=99, 56.6% ±9.8, +3.6 bps — the six dropped events went 2 hits / 4 misses.
Window-only (`WINDOW=last`): 51.1% +4.5 (n=47) vs 53.7% +6.2 (n=41). The hold-back
moves the cumulative cell by 1.4pp on six events, inside the interval; neither view
changes the verdict. So the young-bar effect is real but, so far, small at the cell.

## Run 4 decision boundary and the meaning of "sustained" (pre-registered 2026-09-05, before any run-4 data)

**Exact cumulative state after run 3** (from the battery, not the rounded log): n=105,
hits=58 (55.24%), summed edge +314.2 bps. Run 4 on 2026-09-07 should add roughly 45–60
cell events (run 2: 49 on 73 new bars; run 3: 47 on 55).

**Arithmetic, fixed now.** With k new cell events in run 4, the cumulative hit falls to
≤55% iff the window hits ≤ ⌊0.55·(105+k) − 58⌋, and the cumulative edge falls to ≤0 iff the
window's mean edge ≤ −314.2/k bps/bar:

| k | window hits that cross ≤55% | window mean edge that crosses ≤0 |
|---|---|---|
| 40 | ≤21 (52.5%) | ≤ −7.9 |
| 45 | ≤24 (53.3%) | ≤ −7.0 |
| 50 | ≤27 (54.0%) | ≤ −6.3 |
| 55 | ≤30 (54.5%) | ≤ −5.7 |
| 60 | ≤32 (53.3%) | ≤ −5.2 |

**The gap in the rule, stated honestly.** The pre-registered reading is "hit ≤55% or
edge ≤0, *sustained*", and "sustained" was never given a number. The run logs so far
carry an implicit reading: run 2's window failed on edge and was called "one window is
not sustained"; run 3's window failed on hit and was called "not sustained under the
rule as written; one more such window would be". Four readings are consistent with the
words, and they do not agree on where things stand:

- **(A) cumulative cell fails at two consecutive runs.** Never failed yet; run 4 alone
  cannot trigger; earliest trigger is run 5. Most lenient to the thesis.
- **(B) cumulative cell fails once** (the cumulative already spans several windows).
  Run 4 triggers iff the table above is crossed.
- **(C) two consecutive windows fail on either criterion.** Runs 2 and 3 already
  qualify (edge, then hit) — under this reading the rule is ALREADY triggered, and the
  run-3 log's "not sustained" was wrong.
- **(D) two consecutive windows fail on the same criterion.** Run 3's window failed on
  hit (51.1%); run 4 triggers iff its window hit is ≤55%, whatever the cumulative says.
  This is the reading the run-3 log's sentence most plausibly meant.

**Choice: the user's, to be written here before pull 4 is made.** Not choosing before the
data arrives would let the data choose the definition, which is the goalpost-moving the
protocol forbids. The assistant's recommendation is (D), because it is the reading the
prior log already committed to in writing and it does not let a single noisy window
decide; (C) is the stricter reading and would mean recording the thesis as failed today.
Whichever is chosen, the `SETTLED=6` view stays supplementary and the choice is recorded
below verbatim, with the date, before run 4's raw files exist.

**Chosen reading (recorded 2026-09-05T03:31Z, no run-4 raw files exist; user: "let's go ahead and run your recommendation"): (D).** "Sustained" means two consecutive out-of-sample windows (`WINDOW=last`, `SETTLED=0`, base-calibrated thresholds, the >90th cell) fail on the SAME criterion — hit ≤55% in both, or edge ≤0 in both. Run 3's window failed on hit (51.1%, n=47). Therefore run 4 triggers the failure reading iff its window hit is ≤55%; a run-4 window that fails on edge alone starts a new edge chain and does not trigger. The cumulative cell remains THE number reported, and crossing the table above is recorded as such, but under (D) the cumulative crossing alone is not the trigger. If run 4 triggers: the registry entry for b9438519 and the research spec record the premise as failed out of sample, and the strategy stays archived; no re-cut of the cell is permitted. If it does not: the chain resets to the criterion run 4 failed on, if any, and run 5 is due ≤3 days later. This paragraph is not to be edited after run 4's raw files exist.

## Cadence

Every 3–4 days. First run due **2026-09-01/02**. Scheduling this as an
autonomous job is NOT reliable — the BattleGrid connector needs interactive
authentication and a headless run may wake without it; run it inside a normal
session on the user's ask.

## Run log

- **Run 1, 2026-08-30** (a day early; the window scrolls, early is safe):
  `repulls/2026-08-30/` + addendum in the research spec. THE cell: n=9,
  66.7% ±30.8, +36.7 bps — no contradiction, n tiny, majors had zero events.
  Battery script for future runs: `repulls/analyze_repull.py` (run it, then
  write the dated addendum). Next pull due ≤ **2026-09-03**.
- **Run 2, 2026-09-02** (deadline −1): `repulls/2026-09-02/` + addendum in the
  research spec. Integrity: 0 gaps, 0 dupes — but **the platform restated
  previously served bars** (volume up on 235 fields, small price changes on 35,
  all 16 series; the 4h series show a clean start ≈ 2026-08-22T08:00Z). Recorded
  verbatim in `data/audit/candle_restatement_2026-09-02.json`; transcription ruled
  out. The canonical `analyze_repull.py` stopped on `COLLISION DISAGREES` by design
  and was not modified — numbers from a same-day sensitivity copy (identical
  math + explicit collision policy; THE cell identical under both) since folded
  into the canonical script and removed. THE cell,
  cumulative new-only: n=58, 58.6% ±12.7, +1.8 bps — not triggered; this window
  alone: n=49, 57.1% ±13.9, **−4.6 bps** — edge failed for the window, not yet
  "sustained". Majors n=7 at the cell (uninformative); majors at >75th 35% / −13
  bps (n=40). Funding: SOL 14/73 hours negative (first ever), BTC/ETH 0/73.
  Both open decisions were resolved later the same day, on the user's instruction to
  follow the best recommendation — see the amendment above (`POLICY=latest` default;
  `verify_repull.py` records revisions, fails only on >1% price restatement; the
  copy-pasted steps became `verify_repull.py` / `assemble_repull.py`). Next pull due
  ≤ **2026-09-05** (hard limit ≈ 2026-09-06T04:00Z).
- **Run 3, 2026-09-04** (deadline −1; main session pulled all 16 in one pass at
  08:33–08:40Z after two subagents died on usage limits — their partial snapshots are
  in `data/audit/partial_pulls_repull3/`): `repulls/2026-09-04/` + addendum. Integrity:
  0 gaps/dupes, 45/86 bars overlap, no price >1%; 34 bars restated, all within ~5h of
  run 2's pull time (`data/audit/candle_restatement_2026-09-04.json`). **New finding:**
  bars ≤6h old at pull time are served incomplete (the 09-04T05:00Z bar had 11–56% of
  median volume on every coin; 18/40 young bars revised across three snapshots, 0/1040
  older ones). THE cell, cumulative: n=105, 55.2% ±9.5, +3.0 bps — **not triggered,
  0.2pp above the line**; this window alone n=47, 51.1%, +4.5 bps (hit criterion
  failed for the window). Trajectory 66.7 → 58.6 → 55.2. Majors n=14 at the cell;
  BTC+ETH n=10, −1.5 bps; majors at >75th 44.4% / −11.5 bps (n=72). Funding: BTC 1/55
  negative (first ever), ETH 0/55, SOL 8/55. Open protocol question (user): whether to
  hold back bars younger than ~6h from the battery. Next pull due ≤ **2026-09-07**
  (hard limit ≈ 2026-09-08T11:00Z).
