# F2 report: finishing the plan-time header probe

Written 2026-10-21, around 11:51Z. Worktree `C:/tmp-bgm-f2`, branch `feat/finish-header-probe`, based on main `d680be7`.

- Nothing was merged, pushed or deployed.
- I made no BattleGrid calls and did not touch Docker, `.env` or the Hermes profiles.
- Postgres was read only, with `psql` (`system_state` `surface_tools` and `manager_schemas`, both at 123.2.0).

## Status

Done, except item (c). That item's premise is wrong, so I added a comment instead of deleting the entries (see below).

Full suite: **4867 passed, 5 skipped, 0 failed** (9 min 28 s; no `-x`).

## Commits

| sha | what |
|---|---|
| `d3b3d09` | Probe: benchmark sections send `benchmarkTicker`; platform sections are read through `get_strategy_section_template`, then their columns |
| `a308d72` | (d) A probe that could not run keeps its reason in HEADER_UNVERIFIED |
| `8fb5491` | (c) A comment in the direction glossary saying why `MACDhist_trend` and `PPOhist_trend` stay |

## 1. benchmarkTicker

- **Where OMEGA carries it:** on the custom section. In v0.8.3 that is `CustomSection.benchmarkTicker`, and `wire()` always writes it, null by default. `omega.generate` always sets it to None, so no OMEGA-built plan has a benchmark today. A hand-made or future plan can.
- **The live input:** the stored 123.2.0 `get_strategy_column_contract` schema has `column` (required), `anchorTimeframe`, and `benchmarkTicker`, which is a coin-symbol string or null. `additionalProperties` is false.
- **The change:** `headers.probe_requests` adds `"benchmarkTicker": <ticker>` to every column request of a section whose ticker is a non-null string.
  - A null or absent ticker is not sent. Request keys stay byte-identical, so the existing cache still hits.
  - An empty or non-string ticker raises `ValueError`, so the report counts as unread.
  - A benchmark column is a separate probe and a separate cache entry. The entry records `benchmarkTicker`.
- **OMEGA's prediction is unchanged:** `outputs_for` takes the column alone.
- **Tests:**
  - `test_a_benchmark_section_is_probed_with_its_ticker`: only that section's columns carry the ticker; null is not sent; the keys are disjoint.
  - `test_a_benchmark_column_passes_with_the_ticker_and_is_cached_with_it`: the fake compiler refuses a benchmark column sent without its ticker, which is the old behaviour. The plan now passes.

## 2. Platform sections

- **Stored state cannot verify them:** `surface_tools` and `manager_schemas` hold input schemas only. Neither has an output schema for `get_strategy_section_template`, and `manager_schemas` does not list the tool at all. No header code is stored anywhere (E2 found the same). The 123.0.0 fixture under `tests/fixtures` has no output schemas either.
- **So the probe reads them live, read-only:**
  - `get_strategy_section_template({"request": {"kind": "platform", "sectionKey": K}})` returns the template's columns. The tool keeps its `request` envelope, per the stored schema and README v111.
  - Each column is cut to OMEGA's `Column` fields. These are the same 11 keys as the column-contract `column` schema.
  - Each column then goes through the column-contract probe at the plan's anchor.
  - The served headers, in template order, are compared with OMEGA's prediction from its own capture (`omega.contract.load().platform_templates`, `data/contract/templates/platform/_all.json`). This catches a moved column as well as a moved code.
  - A difference is `HEADER_CODE_MOVED` at `axes.REPORT.platform.<key>`, naming the section.
- **Same rules as the column probe:**
  - The template read counts against `MAX_PROBES` like a column read.
  - Templates are cached per build under their own key (`{template: …}`, independent of the anchor). Columns share the column cache.
  - Fails closed. A failed call, an answer without a `columns` list, an answer for a different `sectionKey`, or a column past the bound leaves the whole section HEADER_UNVERIFIED.
  - Served platform headers join `served_all`, so a condition on a platform header is no longer judged only by OMEGA's rename table.
- **Cap: `MAX_PROBES` stays at 24.** A platform section costs 1 call plus one per column (includePriceAction is 13), but OMEGA v0.8.3 generates custom sections only, so no plan pays this today. A plan past the bound fails closed, and the next plan reuses the cached reads. The rate bucket is untouched: calls still go through the CLI's client or the api gateway.
- **`PLAN_TIME_READS` is now `{get_strategy_column_contract, get_strategy_section_template}`.** I updated the watch exemption test. The proxy policy already allowed both tools.
- **Tests:**
  - `test_a_platform_section_is_read_through_its_template_then_its_columns`: one template call, then the column calls; the second plan is all cache hits.
  - `test_a_platform_section_whose_served_headers_moved_is_refused`
  - `test_a_platform_section_unread_fails_closed`: covers a 429, no columns, the wrong sectionKey, the bound, and a section without a key.

## (d) The probe's reason

- `pipeline._observed` now returns `(answer, reason)`. `header_drift(..., unread_reason=)` puts the reason in its message, either "the report could not be read: …" or "the probe failed: RuntimeError: …".
- Test: `test_an_unread_report_or_a_failing_probe_keeps_its_reason`.

## (c) The PPO/MACD glossary: not removed

- `MACDhist_trend` and `PPOhist_trend` are **live** codes. Contract 110 retired the metrics `MACD` and `PPO` (codes `MACD`, `PPO`). Their replacements `MACD_HIST` and `PPO_HIST` have the codes `MACDhist` and `PPOhist` (OMEGA `_moves_110.json` "since"). v123 did not rename them (gap-strategy.md §2.7: "Untouched stems").
- OMEGA v0.8.3 predicts `MACDhist_t3..MACDhist_trend` and `PPOhist_…_trend` for the trajectory column, and `header_since_123` leaves both unchanged.
- `tests/strategist/test_direction.py` expects both glosses in the MACD and relative-strength plans.
- Removing them would only drop the glosses on live plans, so I added a comment to that effect.

## Concerns

1. **The live answer shape of `get_strategy_section_template` is unmeasured.** There is no stored output schema and no capture of the tool's own answer. OMEGA's capture is the `templates` block of `list_strategy_vocabulary`. The parser accepts `columns` at the top level or under `template`, `section` or `definition`; anything else fails closed. The skill pack says the template "renders" headers, so the answer may carry headers directly, which would make the column calls unnecessary. The first plan with a platform section is the first real read. There is none today.
2. **Both plan-time reads stay outside `MANAGER_TOOLS`,** for the reason E2 gave. A move can only make a plan fail closed. The reviewer's agreement still applies to the second tool.
3. **The benchmark path has not been measured live** either. The input shape comes from the stored schema; no benchmark answer has been captured. A benchmark column the compiler refuses (README 49.0.0: crowd metrics or rank transforms) is unread, so HEADER_UNVERIFIED. That is correct, but the plan does not name the platform's refusal code.
4. **The suite runs against the shared dev venv** at `.omega/v0.8.3`, as E2 left it.
