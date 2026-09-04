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
