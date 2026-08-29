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
