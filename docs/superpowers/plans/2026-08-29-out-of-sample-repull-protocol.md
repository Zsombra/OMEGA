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
- [ ] Save under `data/research/2026-08-29-deep-tail-fade/repulls/<YYYY-MM-DD>/`
      in the same `candles.json` format (dedupe by timestamp; the base corpus
      script shows the shape). Commit the data — it is irreplaceable.

## The analysis (per run, offline)

- [ ] Rebuild the combined per-coin 1h series (base corpus + all repulls,
      deduped by timestamp; gaps are recorded, not interpolated).
- [ ] Rerun the `test_c_wide.py` battery on the combined corpus AND on the
      new-window-only slice:
      reversion hit/edge at >50/75/90th pct stretch, VWAP4-vs-SMA4 ablation,
      W∈{3,4,6,8} sweep.
- [ ] Record a dated addendum in
      `docs/superpowers/specs/2026-08-29-deep-tail-fade-research.md`:
      the >90th-pct 1h cell (hit%, edge, n) out-of-sample is THE number that
      decides whether Deep-Tail Fade keeps its weights. Pre-registered reading,
      to keep us honest: sustained out-of-sample hit ≤ 55% or edge ≤ 0 at the
      deep tail = the thesis's premise failed and the registry entry should say
      so; do not move the goalposts to a different cell that happens to work.

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
  and was not modified — numbers from `analyze_repull_sensitivity.py` (identical
  math + explicit collision policy; THE cell identical under both). THE cell,
  cumulative new-only: n=58, 58.6% ±12.7, +1.8 bps — not triggered; this window
  alone: n=49, 57.1% ±13.9, **−4.6 bps** — edge failed for the window, not yet
  "sustained". Majors n=7 at the cell (uninformative); majors at >75th 35% / −13
  bps (n=40). Funding: SOL 14/73 hours negative (first ever), BTC/ETH 0/73.
  **Open protocol decisions (user):** collision policy for the canonical script;
  whether the integrity check should tolerate volume revisions. Next pull due
  ≤ **2026-09-05** (hard limit ≈ 2026-09-06T04:00Z).
