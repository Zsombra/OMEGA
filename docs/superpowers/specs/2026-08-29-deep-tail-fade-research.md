# 2026-08-29 · Deep-Tail Fade: the research record

How a VWAP intent became the Deep-Tail Fade thesis, with every measurement that
moved the design. Data and scripts: [`data/research/2026-08-29-deep-tail-fade/`](../../../data/research/2026-08-29-deep-tail-fade/).
All candle pulls were read-only `get_coin_candles` calls (closed bars only, 100-bar
cap — the windows are irreplaceable); funding history came from the Hyperliquid
public API, the same external referent doc 19 uses.

## The journey, in verdicts

1. **VWAP is not authorable as signal logic.** One VWAP exists (session, daily
   00:00-UTC family per trap 21); it is not one of the 17 modules, and the only
   platform section containing it feeds no signals (doc 07). A rolling "4h VWAP"
   is not computable in the column algebra (no products, no cross-unit division,
   no calendar windows — doc 18).
2. **A rolling VWAP proxy (Σc·v/Σv over 4 closed bars) was tested anyway** as an
   agent-computable market read, per anchor, BTC/ETH/SOL × 5m/15m/1h/4h:

   | anchor | trend hit% | trend bps | revert hit% | revert bps |
   |---|---|---|---|---|
   | 5m | 51.1 ±5.8 | +0.7 | 53.5 ±11.6 | −1.0 |
   | 15m | 48.8 ±5.8 | −0.4 | 47.2 ±11.5 | −2.1 |
   | 1h | 44.8 ±5.7 | −0.9 | **66.7 ±10.9** | **+7.4** |
   | 4h | 49.3 ±5.8 | **+18.1** | 45.8 ±11.5 | −29.3 |

   (revert = fade top-quartile |dev|; next-bar close-to-close; no costs.)
3. **Ablation (VWAP4 vs SMA4):** 94.5% sign agreement; on the wide 13-coin 1h set
   SMA4 matched hit rate (57.8% vs 57.1%) and beat edge (+10.5 vs +0.3 bps).
   **Volume weighting is not load-bearing** — the 3-coin appearance that it was
   (+7.4 vs +1.1) did not survive the wider cross-section.
4. **Cross-section (13 coins, 1h):** pooled 57.1% ±5.5; the original majors held
   66.7%, the 10 volume-ranked alts alone 54.2% ±6.3 (≈noise). Edge collapsed to
   +0.3 bps at quartile stretch.
5. **Threshold sweep is monotone** — the honest signature of a real effect
   concentrated in the tail: >50th 52.8%/−0.6 → >75th 57.1%/+0.3 → **>90th
   61.5% ±8.8 / +13.2 bps** (n=117). **Window sweep: W=4 is not special**
   (W=8: 62.2%/+17.4). Both sweeps are multiple comparisons — trust direction,
   not magnitude.
6. **Gate agreement:** at 1h stretch events the FADE modules were jointly "on"
   only 38% of the time, with no selection value (62% vs 58% conditional); MFI
   co-fired 14% (demoted), RSI 43%, %B 55%. At 4h the ALIGN gate DID select
   (+9.3 vs −3.0 bps) and the 4h trend headline was mostly the Aug 19–21 rally.
7. **Preset legs tested (CVD/FUNDING under FADE fall back to ALIGN clauses,
   [generate.py:525](../../../omega/generate.py)):** the flow-confirmation leg
   (OBV 4-bar analog of `CVD_trend rising` — true CVD history is unreachable)
   fired on 6/72 deep-tail events and lost when it fired (33%/−28 bps; 0/4 at
   90th pct) — structurally late at deep tails. The funding leg (real Hyperliquid
   history) looked right (+12.8 vs +2.3 bps; +28.8 vs +2.1 at 90th) but funding
   was positive 94–100% of hours, so "aligned" ≈ "fade-short": **confounded with
   side, unproven**. Both → context, not weights.

## The thesis (validated, briefed, zero findings)

`Deep-Tail Fade` — FADE, 1h, gate 0.65, weights `BOLLINGER: 3, RSI: 2`,
context `MFI, REGIME, CVD, FUNDING`, explicit BTC/ETH/SOL, execution on measured
platform defaults, no required signals. Thesis JSON + brief beside the data.

## Standing caveats (attached permanently)

One August window; no out-of-sample (the 100-bar cap means only future re-pulls
provide it); majors and alts differ; the deep-tail cell is a selected maximum;
+13 bps pre-cost is modest; per P1 nothing here is a performance claim.

## Where it stopped

The compile dry-run (user-authorized, ONE call) was refused by fresh platform
drift — the condition-clock feature. Findings and the migration path:
[`data/audit/compile_dry_run_2026-08-29-deep-tail-fade.json`](../../../data/audit/compile_dry_run_2026-08-29-deep-tail-fade.json)
and [the migration plan](../plans/2026-08-29-condition-clock-migration.md).

## Out-of-sample addendum · re-pull 1, 2026-08-30

First run of [the re-pull protocol](../plans/2026-08-29-out-of-sample-repull-protocol.md)
(one day early — the ≤4-day window says pull when you can). Data:
[`repulls/2026-08-30/`](../../../data/research/2026-08-29-deep-tail-fade/repulls/2026-08-30/),
battery: [`repulls/analyze_repull.py`](../../../data/research/2026-08-29-deep-tail-fade/repulls/analyze_repull.py).

- **Pull integrity:** 13-coin 1h set + BTC/ETH/SOL 4h, 100 bars each, verified
  against the base corpus — 0 gaps, 0 dupes, **0 OHLCV mismatches** on 78–94
  overlapping bars per series. New out-of-sample: **20–22 1h bars per coin**
  (~1 day), 6 4h bars per major.
- **THE cell (new-only, >90th-pct stretch, VWAP4; thresholds calibrated on the
  base window, events strictly after it): n=9, hit 66.7% ±30.8pp, edge
  +36.7 bps/bar.** Direction consistent with the thesis; the pre-registered
  failure reading (hit ≤55% or edge ≤0, *sustained*) is not triggered. But
  n=9 with a ±31pp interval is nearly uninformative — this is "no
  contradiction," not "survival." One window decides nothing.
- **The majors produced zero events.** Every one of the 9 deep-tail events (and
  all 18 >75th events) is on alts; BTC/ETH/SOL were too quiet to stretch in
  this window. The compiled strategy's explicit universe (BTC/ETH after the
  BG-14 width reduction) therefore has **no out-of-sample evidence yet** — the
  pooled cell above is evidence for the effect, not for that universe.
- **Combined corpus** (base + repull, thresholds over the full window):
  >90th cell 59.4% ±8.0pp, +8.1 bps (n=143) — vs the in-sample 61.5% ±8.8,
  +13.2 (n=117). Same direction, slightly diluted; sweep shapes unchanged
  (monotone in threshold; W=4 still not special — W=8: 61.2%/+15.8 at >75th).
- **Funding confound: unresolved.** New hours' sign mix — BTC 0/20 negative,
  ETH 0/20, SOL 1/20. Still an essentially all-positive-funding regime; the
  FUNDING leg stays context, its apparent alignment still confounded with side.
  (Note: the `fetch_funding.py` the protocol references was never preserved;
  the fetch was reconstructed from the recorded shape + the public API, and
  the repull saves the raw rows verbatim in `funding_raw.json`.)
- **Next pull due ≤ 2026-09-03** (100-bar window scrolls off ~4d4h after this
  one). The verdict on the deep-tail premise accrues across pulls; nothing is
  claimed from this one alone.

## Out-of-sample addendum · re-pull 2, 2026-09-02

Second run of [the re-pull protocol](../plans/2026-08-29-out-of-sample-repull-protocol.md),
one day inside the ≤ 2026-09-03 deadline. Data:
[`repulls/2026-09-02/`](../../../data/research/2026-08-29-deep-tail-fade/repulls/2026-09-02/).
Battery: the canonical
[`repulls/analyze_repull.py`](../../../data/research/2026-08-29-deep-tail-fade/repulls/analyze_repull.py)
**refused to run on this corpus** (see the finding below); every number here comes from
[`repulls/analyze_repull_sensitivity.py`](../../../data/research/2026-08-29-deep-tail-fade/repulls/analyze_repull_sensitivity.py),
a copy with identical math plus an explicit collision policy — and THE cell is the same
under both policies.

- **Pull integrity:** 13-coin 1h set + BTC/ETH/SOL 4h, 16/16 series, 100 bars each,
  0 gaps, 0 dupes; 27–28 (1h) / 82 (4h) bars overlap the prior record. New
  out-of-sample: **72–73 1h bars per coin** (~3 days), 18 4h bars per major.
- **FINDING — the platform restated previously served bars.** Every series differs
  from what the same endpoint served on 08-29/08-30: 253 bars, 270 fields —
  **volume on 235** (every one revised *upward*, none down), open 21, close 8,
  high 4, low 2, all price changes one to a few ticks (max 0.23%). The 4h series
  show a clean start ≈ **2026-08-22T08:00Z**: 36–37 bars before it match exactly,
  42–46 of the 45–46 after it differ. Base (08-29) and re-pull 1 (08-30) had agreed
  on those same bars, so the served history changed between 08-30 and 09-02.
  Transcription is ruled out three ways (direct re-calls, exact 1h→4h aggregation on
  72 bars, OHLC matching on ~98.5% of fields). Full verbatim old/new record:
  [`data/audit/candle_restatement_2026-09-02.json`](../../../data/audit/candle_restatement_2026-09-02.json).
  The cause is **unknown**; "late trades folded in" fits the shape but is inferred,
  not measured. `analyze_repull.py` stopped with
  `COLLISION DISAGREES: AIXBT_1h 2026-08-28T23:00:00.000Z (0.020327, 107406.0) vs (0.020327, 108026.0)`
  exactly as designed and was **not modified**; choosing its collision policy is a
  protocol change left to the user.
- **THE cell (cumulative new-only, >90th-pct stretch, VWAP4, thresholds calibrated on
  the base window, events strictly after it — i.e. *all* out-of-sample bars from both
  runs): n=58, hit 58.6% ±12.7pp, edge +1.8 bps/bar.** Identical whether collisions
  resolve first-seen or latest. The pre-registered failure reading (hit ≤55% or
  edge ≤0, *sustained*) is **not triggered** — but the edge is within noise of zero
  and the hit interval spans 46–71%.
- **This window alone** (events after re-pull 1's last bar, same base-calibrated
  thresholds; a supplementary cut, not THE number): n=49, hit 57.1% ±13.9pp,
  **edge −4.6 bps/bar**. On the edge criterion this window reads as a failure;
  one window is not "sustained". Run 1's +36.7 bps on n=9 is what keeps the
  cumulative edge above zero. Direction of travel across the two runs: down.
- **Per-coin split at the cell.** CAKE alone is 20 of the 58 events (10/20, 50%);
  MET 6/7, MOODENG 3/3, TRUMP 3/4, PEPE 3/6, AIXBT 2/5, MELANIA 2/4, LDO 1/2;
  HYPE and POPCAT 0 events. **Majors: n=7** (BTC 2/3, ETH 1/2, SOL 1/2),
  57.1% ±36.7pp, +4.5 bps — uninformative; **BTC+ETH, the created strategy's
  universe: n=5**, 60.0% ±42.9pp. The pooled cell is still alt evidence.
- **The majors at the moderate stretch (>75th) went the wrong way:** n=40, hit
  **35.0% ±14.8pp, edge −13.0 bps/bar** (BTC 3/11, ETH 6/17, SOL 5/12). Not THE
  cell, and the interval is wide, but it is the first out-of-sample number on the
  strategy's own universe with any weight, and it is adverse.
- **Combined corpus** (base + both repulls): >90th 57.4% ±6.3pp, +4.0 bps (n=237),
  vs in-sample 61.5% ±8.8, +13.2 (n=117) and run-1 combined 59.4% ±8.0, +8.1
  (n=143) — monotone dilution across pulls. Sweep shapes unchanged; W=4 still not
  special (W=8: 56.1% / +5.5 at >75th).
- **Funding sign mix (73 new hours per coin):** BTC 0/73 negative and ETH 0/73 — both
  pinned at exactly 0.0000125 every hour; **SOL 14/73 negative** (min −0.0000187),
  the first negative-funding hours in the record. The FUNDING-leg confound is still
  unresolved for BTC/ETH; SOL now offers a mixed window, not analysed here
  (`funding_cvd_test.py` was not re-run — outside this task).
- **Analysis thresholds ≠ the strategy's gates.** Percentile-calibrated stretch here;
  fixed `%B < 0.05` / `RSI14 < 35` plus Bollinger signals in the compiled strategy.
  The fixed-gate firing rate remains unmeasured; "n events here" says nothing about
  whether the strategy would have fired.
- **Still not established:** whether the deep-tail premise survives (cumulative
  reading not triggered, single-window edge negative, n=58 too small to separate
  +1.8 from 0); anything about BTC/ETH at the cell (n=5); the cause and recurrence of
  the platform restatement; whether older bars get revised again; the collision
  policy the canonical battery should adopt; `notes: null`, `closes > 1` and
  non-default `entry` semantics (untouched, as before).
- **Next pull due ≤ 2026-09-05** (hard limit ≈ 2026-09-06T04:00Z — the 100-bar window
  must still reach back to 2026-09-02T00:00Z to overlap). Expect the integrity check
  to flag volume mismatches again; whether that stays a stop-and-record finding or
  becomes a tolerance is the user's protocol decision.
