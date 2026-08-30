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
