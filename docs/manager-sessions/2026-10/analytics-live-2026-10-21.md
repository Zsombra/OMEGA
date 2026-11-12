# Live analytics answers, measured 2026-10-21 ~12:15Z (contract 123.2.x), agent VWAP Sentinel 4h (959739dd-2865-4bc4-8a36-3a58aed28e0f)

These are verbatim, except where marked "(abbreviated)". Every answer is WRAPPED in one top-level key.

## get_account_review_analytics {} -> top key "analytics"
{"analytics":{"windowDays":90,"agents":[{"agentId":"959739dd-2865-4bc4-8a36-3a58aed28e0f","displayName":"VWAP Sentinel 4h","avatarUrl":"https://imagedelivery.net/x/public","realizedNetUsd":0.33,"feesUsd":0.12,"platformLlmSpendUsd":0,"netAfterLlmUsd":0.33,"closedTrades":13,"winRate":{"readiness":"INSUFFICIENT_DATA","sampleSize":13},"halt":{"haltReason":null,"haltedAt":null},"openReviewIds":[],"openReviewCount":0}],"totals":{"realizedNetUsd":0.33,"feesUsd":0.12,"platformLlmSpendUsd":0,"netAfterLlmUsd":0.33,"closedTrades":13,"decisions":99,"openReviewCount":0}}}

## get_agent_cost_economics {agentId} -> top key "economics"
{"economics":{"windowDays":90,"rows":[{"outcome":"NO_STOP_FILL","positionCount":10,"grossPnl":0.77964,"fees":0.090715,"netPnl":0.688925,"feesPercentOfGross":11.6},{"outcome":"TRAILING","positionCount":2,"grossPnl":0.07933,"fees":0.017868,"netPnl":0.061462,"feesPercentOfGross":22.5},{"outcome":"TIME_DECAY","positionCount":1,"grossPnl":-0.41056,"fees":0.009971,"netPnl":-0.420531,"feesPercentOfGross":null}],"totals":{"positionCount":13,"grossPnl":0.44841,"fees":0.118554,"netPnl":0.329856,"feesPercentOfGross":26.4},"costErodedCount":0,"unreconciledCount":0}}

## get_agent_entry_discipline {agentId, windowStartAt:"2026-10-14T00:00:00Z", windowEndAt:"2026-10-21T00:00:00Z"} -> top key "stats"
{"stats":{"agentId":"959739dd-2865-4bc4-8a36-3a58aed28e0f","windowStartAt":"2026-10-14T00:00:00.000Z","windowEndAt":"2026-10-21T00:00:00.000Z","provisionalRequiredReads":{"count":0,"population":0,"rate":null},"heldRequiredGateVersions":0,"revisionUnresolvedOutcomes":0,"confirmationTax":{"meanUsd":-0.007114285714285971,"totalUsd":-0.0498000000000018,"measuredEntries":7,"confirmedEntries":7},"fastStopOutRate":{"count":2,"population":72,"rate":2.7777777777777777},"fastStopOutUnmeasuredPositions":0,"fastStopOutBars":3,"maeBeforeMfe":{"measure":{"count":3,"population":7,"rate":42.857142857142854},"sameBarCount":0,"maeOnEntryBarCount":0},"excursionCoverage":{"excursionCoveredPositions":7,"closedPositionsInWindow":72},"adoption":{"heldConditions":0,"heldRequiredConditions":0,"totalConditions":2,"strategiesByTrigger":[{"trigger":"AT_SIGNAL","strategies":0},{"trigger":"ON_CANDLE_CLOSE","strategies":1},{"trigger":"STOP_THROUGH_LEVEL","strategies":0},{"trigger":"ON_RETEST","strategies":0}]},"baseline":{"windowStartAt":"2026-08-21T00:00:00.000Z","windowEndAt":"2026-08-28T00:00:00.000Z","provisionalFires":23,"provisionalFirePopulation":23,"maeFirst":9,"maeFirstPopulation":15,"fastStopOuts":3,"fastStopOutPopulation":19,"realisedNetUsd":-8.9,"scopeCaveat":"Hand-run review; ..."}}}

## get_agent_decision_quality {agentId} -> top key "quality"
{"quality":{"windowDays":90,"minSampleSize":20,"flatBandPct":0.5,"totalDecisions":90,"filterValue":[{"horizon":"H1","enter":{"readiness":"READY","sampleSize":97,"meanSignedReturnPct":0.22},"skip":{"readiness":"INSUFFICIENT_DATA","sampleSize":0}},{"horizon":"H4","enter":{"readiness":"READY","sampleSize":97,"meanSignedReturnPct":0.46},"skip":{"readiness":"INSUFFICIENT_DATA","sampleSize":0}},{"horizon":"H24","enter":{"readiness":"READY","sampleSize":90,"meanSignedReturnPct":0.19},"skip":{"readiness":"INSUFFICIENT_DATA","sampleSize":0}}],"exitQuality":{"prematureStop":{"readiness":"INSUFFICIENT_DATA","sampleSize":2},"postExit":{"readiness":"INSUFFICIENT_DATA","sampleSize":9}},"verdictDistribution":[{"verdict":"UNFILLED_MISSED","count":36},{"verdict":"UNFILLED_SAVED","count":35},{"verdict":"UNFILLED_FLAT","count":7},{"verdict":"THESIS_PLAYED_OUT","count":4},{"verdict":"WRONG_DIRECTION","count":2},{"verdict":"SCALPED_WIN","count":2},{"verdict":"STOPPED_EARLY","count":1}],"convictionByHorizon":[{"band":"MODERATE","cells":[{"horizon":"H1","figures":{"readiness":"READY","sampleSize":91,"meanSignedReturnPct":0.24}}]}],"exitOutcomeDistribution":[{"outcome":"DEFENDED","count":5},{"outcome":"SHOOK_OUT","count":4}],"exitEfficiency":{"measuredCount":12,"reached1RCount":5,"reached1_5RCount":5,"medianEfficiencyPercent":{"readiness":"INSUFFICIENT_DATA","sampleSize":10},"medianMaeR":{"readiness":"INSUFFICIENT_DATA","sampleSize":12}}}}
(convictionByHorizon abbreviated: LOW/MODERATE/HIGH bands, each with H1/H4/H24 cells)

## get_agent_review_analytics {agentId} -> top key "analytics" (abbreviated: ~30 KB; regime/hourOfDay/weekday/coin arrays have the same "figures" object as overall)
{"analytics":{"agentId":"959739dd-...","windowDays":90,"windowStartAt":"2026-07-23T12:15:16.076Z","windowEndAt":"2026-10-21T12:15:16.076Z","minSampleSize":20,
 "overall":{"decisions":99,"entries":99,"closedTrades":13,"winningTrades":7,"winRate":{"readiness":"INSUFFICIENT_DATA","sampleSize":13},"realizedNetUsd":0.33,"verdictDistribution":[{"verdict":"UNFILLED_MISSED","count":36},{"verdict":"UNFILLED_SAVED","count":35}, ...],"forcedExitCount":2,"prematureStopCount":1,"prematureStop":{"readiness":"INSUFFICIENT_DATA","sampleSize":2},"filterValue":[ ...same shape as decision quality... ]},
 "regime":[{"regime":"bear_ranging","figures":{ ...same as overall... }}, ...],
 "hourOfDay":[{"hourUtc":0,"figures":{...}}, ... 24 rows],
 "weekday":[{"weekday":"MONDAY","figures":{...}}, ... 7 rows],
 "coin":[{"coinTicker":"CRWV","figures":{...},"feesUsd":0.01}, ...],
 "condition":[{"conditionKey":"VWAP_REJECT_LONG","conditionName":"...","citations":96,"cells":[{"verdict":"CONFIRM","counts":{"WON":2,"LOST":2,"SKIPPED":0,"UNFILLED":33,"PENDING":1}}, ...]}],
 "llm":{"platformSpendUsd":0,"byokSpendUsd":0.27,"calls":106,"realizedNetUsd":0.33,"feesUsd":0.12,"decisions":99,"netAfterLlmUsd":0.33},
 "railRefusals":[],
 "halt":{"haltReason":null,"haltedAt":null}}}

Notes:
- The fill/unfilled picture is in verdictDistribution: UNFILLED_MISSED / UNFILLED_SAVED / UNFILLED_FLAT vs filled verdicts. There is no key containing "fill" in a numeric count field except those verdict names and the condition cells' "UNFILLED".
- llm.byokSpendUsd is the user's OWN OpenRouter key spend; platformSpendUsd is BattleGrid credit.
