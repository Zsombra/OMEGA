import json, os, sys
ROOT = r"C:\Users\rafae\Documents\GitHub\OMEGA\.claude\worktrees\authoring-assistant-plan-0eaf0a"

def cl(h, **kw):
    return {"kind": "clause", "column": {"sectionKey": None, "header": h}, **kw}

def C(k, n, d, v):
    return {"conditionKey": k, "name": n, "definition": d, "verdict": v,
            "required": False, "exit": False, "clock": "LIVE", "closes": 1}

def col(m, op):
    return {"metric": m, "transformId": "spread", "timeframe": {"rel": "anchor"},
            "inputs": [{"metric": op}]}

columns = [
    col("PRIOR_TPO_VAL", "CLOSE"),
    col("PRIOR_TPO_VAH", "CLOSE"),
    col("PRIOR_TPO_POC", "CLOSE"),
    col("PRIOR_TPO_VAL", "DONCHIAN_LOWER"),
    col("PRIOR_TPO_VAH", "DONCHIAN_UPPER"),
    {"metric": "TPO_SHAPE", "transformId": "value", "timeframe": {"rel": "anchor"}},
]

conditions = [
    C("ABOVE_VALUE", "Trading above prior value entirely",
      cl("pTpoVAH_close_spread", op="lte", value=-0.05), "UP"),
    C("VAL_REJECT_DN", "Decisively rejected below prior value low",
      cl("pTpoVAL_close_spread", op="gte", value=6.42), "DOWN"),
    C("VAH_CONFLUENCE_DN", "Prior value high stacked on Donchian resistance",
      cl("pTpoVAH_donchianHi_spread", op="between", low=0, high=2.14), "DOWN"),
    C("VAL_CONFLUENCE_UP", "Prior value low stacked on Donchian support",
      cl("pTpoVAL_donchianLo_spread", op="between", low=0, high=4.25), "UP"),
    C("SHAPE_B", "Developing profile skewed to the bottom of value",
      cl("tpoShape", op="is", label="b-shape"), "DOWN"),
    C("SHAPE_P", "Developing profile skewed to the top of value",
      cl("tpoShape", op="is", label="p-shape"), "UP"),
    C("BELOW_VALUE", "Close below prior value area",
      cl("pTpoVAL_close_spread", op="gte", value=0.05), "DOWN"),
    C("POC_ABOVE", "Prior point of control still above the close",
      cl("pTpoPOC_close_spread", op="gte", value=0.05), "UP"),
    C("INSIDE_VALUE", "Close below prior value high",
      cl("pTpoVAH_close_spread", op="gte", value=0.05), "NEITHER"),
    C("SHAPE_BALANCED", "Developing profile balanced",
      cl("tpoShape", op="is", label="balanced"), "NEITHER"),
    C("NO_DECISIVE_LOCATION", "No decisive location versus prior value low",
      cl("pTpoVAL_close_spread", op="lt", value=0.05), "NEITHER"),
]

rules = [{"signalId": s, "allocation": a, "required": False} for s, a in [
    ("mfi_sustained_bearish", 3), ("oi_divergence_bear", 3),
    ("htf_ma_aligned_bear", 2), ("ma_ema_aligned_bear", 2),
    ("comparison_sector_momentum", 2),
    ("funding_rate_flipping", 1), ("cvd_bearish", 1),
    ("mfi_sustained_bullish", 1), ("oi_divergence_bull", 1),
    ("htf_ma_aligned_bull", 1), ("ma_ema_aligned_bull", 1), ("cvd_bullish", 1)]]

assumptions = [
    "GATE 0.65 IS DERIVED, NOT PICKED. simulate_aggregate_score on this exact card at 1h returned: ETH 0.5648 REJECT, ballast-only floor 0.6083 REJECT, BTC 0.7699 ADMIT, SOL 0.7831 ADMIT, HYPE 0.8560 ADMIT. The gap between highest reject and lowest admit is 16.2 points and empty; 0.65 sits inside it.",
    "THE AGGREGATE IS A WEIGHTED MEAN OVER TRIGGERED SIGNALS ONLY, re-verified 3 of 3 against raw previews: HYPE 7.99265/12 = 0.66605 to 67; BTC 6.23496/13 = 0.47961 to 48; ETH 4.263432/11 = 0.387585 to 39. A signal at allocation 0 leaves the denominator entirely.",
    "THAT FORMULA IS THE LOAD-BEARING ASSUMPTION. It is measured on simulate_aggregate_score, not on the live router. If the router instead averages over all 84 materialised signals then 0.65 is unreachable and this joins the coins already reading AGGREGATE_BELOW_MIN. get_agent_coin_qualification tests it without spending anything.",
    "CURATION IS THE ENTIRE EDGE. Excluding frequently-triggering low scorers lifted BTC from 48 unweighted to 77 and SOL from 54 to 78 at the same instant. Deliberate zeros: flow_perp_spot_bear_divergence 0.109/0.144/0.100, mfi_oversold 0.205/0.020/0.071, rel_roc_negative 0.003, trend_adx_trending, ma_sma200_below.",
    "structure_fvg_approach IS AT ZERO ON PURPOSE, reversing an earlier design that weighted it at 3. It measured 0.392 and 0.451 today against 0.707 and 0.935 twenty-four hours earlier. Too unstable to weight on a one-day reading.",
    "THE FIVE BULL MIRRORS AT ALLOCATION 1 HAVE UNMEASURED SCORES. None triggered on any coin sampled. They are regime insurance, free while untriggered, and become drag the moment the tape turns.",
    "TPO FEEDS ZERO OF THE 84 SIGNAL MODULES (663-cell probe, 0 failures). All eleven conditions are advisory and gate nothing. This strategy routes on momentum signals; the TPO ladder shapes the agent read only.",
    "CONDITION ORDER IS LOAD-BEARING. Verdict resolution is first-TRUE-wins in array order - measured, identical conditions reordered returned 0 DOWN / 10 NEITHER versus 4 DOWN / 0 NEITHER. Rarest first, NEITHER tags last.",
    "THRESHOLDS ARE MEASURED QUARTILES over 12 observations at one instant: VAL_REJECT_DN 6.42 is the p75 of pTpoVAL_close_spread; VAH_CONFLUENCE_DN 2.14 the p25 of pTpoVAH_donchianHi_spread; VAL_CONFLUENCE_UP 4.25 the p25 of pTpoVAL_donchianLo_spread. Twelve observations is not a distribution.",
    "A 0.5 PERCENT SAME-LEVEL TOLERANCE WAS MEASURED WRONG AND ABANDONED. Prior value low versus Donchian support ran 2.31 to 12.19 percent apart across 12 coins, never inside 0.5. The confluence bands use measured p25 instead.",
    "tpoShape IS A CURRENT-SESSION METRIC, NULL for the first 60 minutes of each UTC day. SHAPE_B, SHAPE_P and SHAPE_BALANCED all read FALSE in that window, and a null reads FALSE both ways.",
    "A DEV_POC_ABOVE condition on tpoPOC_close_spread WAS DROPPED: that header was inferred by symmetry and has never been emitted by the server. Its column went with it.",
    "THE tpoShape CLAUSES USE THE KEY label, NOT value. The compile schema label clause requires kind, column, op and label with additionalProperties false. An earlier draft used value and would have been refused.",
    "ENTRY BLOCK COPIED VERBATIM from this account strategy 56c08ef6, the only entry block here known to compile. It has never produced a fill, so compiling is the only property demonstrated.",
    "BYTE BUDGET: measured anchors 36 tickers 433118 REFUSED, 16 tickers 281848 REFUSED, 10 COMPILED, cap 262144. Fitted 7563.5 bytes per coin on 160832 fixed overhead. At 6 columns and 11 conditions the per-coin cost should fall below that anchor, so 8 coins carries headroom.",
    "NOT DEPLOYED BY THIS PAYLOAD. Radar reads coinsDeployed 20 of coinCap 20 and every live policy currently reads qualified false. Creating this strategy schedules nothing and risks nothing.",
]

body = {
    "operation": "CREATE",
    "name": "TPO Prior-Value Momentum",
    "tagline": "Curated momentum scorecard at a 0.65 floor; prior TPO value shapes the read.",
    "description": "Routes on a curated twelve-signal momentum scorecard whose per-signal scores were read live at 1h before the gate was set. Eleven advisory prior-session TPO conditions, ordered rarest-first so no row masks another, tell the model where price sits against yesterday value area. TPO feeds no signal module and cannot score; it shapes what the agent reads, not what the router computes.",
    "intentSummary": (
        "A TPO strategy that can actually route. TPO feeds zero of the 84 signal modules, so the score "
        "comes entirely from a curated twelve-signal momentum card whose per-signal values were read live "
        "at 1h before the gate was chosen; the eleven prior-session TPO conditions are advisory and shape "
        "what the agent reads. The gate 0.65 sits inside a measured 16.2-point empty gap between the "
        "highest rejecting aggregate (0.6083, ballast only) and the lowest admitting one (0.7699, BTC). "
        "Curation is the edge: dropping frequently-triggering low scorers lifted BTC from 48 to 77 and SOL "
        "from 54 to 78 at the same instant, because the aggregate is a weighted mean over TRIGGERED "
        "signals only and allocation-0 signals leave the denominator. Conditions are ordered rarest-first "
        "because verdict resolution is first-TRUE-wins in array order. Creating this deploys nothing: "
        "Radar is at 20 of 20 coins and this strategy is bound to no agent."),
    "timeframe": "1h",
    "coinSelection": {"mode": "explicit", "tickers": ["BTC", "ETH", "SOL", "HYPE", "XRP", "AVAX", "LINK", "DOGE"]},
    "sections": [{"kind": "custom", "title": "Prior Value Location", "benchmarkTicker": None,
                  "notes": "Prior-session value area versus the close and versus the Donchian levels, plus the developing profile skew.",
                  "columns": columns}],
    "conditions": conditions,
    "rules": rules,
    "minAggregateScore": 0.65,
    "entry": {"trigger": "ON_CANDLE_CLOSE", "confirmTf": "1h", "closes": 1,
              "bandAtrMultiple": 0.5, "levelOffsetAtrMultiple": 0, "validForBars": 4},
    "assumptions": assumptions,
    "minAtrPct": 0.5,
    "minRiskRewardRatio": 1.5,
}

out = os.path.join(ROOT, "out", "tpo_suite", "bodies")
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, "PVM_create.json"), "w", encoding="utf-8") as f:
    json.dump({"request": body}, f, indent=1)

raw = json.dumps(body, separators=(",", ":"))
print("name       :", body["name"], "(%d chars, cap 50)" % len(body["name"]))
print("tagline    :", len(body["tagline"]), "chars (cap 80)")
print("description:", len(body["description"]), "chars (cap 500)")
print("columns    :", len(columns), "| conditions:", len(conditions), "| clauses:", len(conditions))
print("rules      :", len(rules), "non-zero, total allocation", sum(r["allocation"] for r in rules))
print("gate       :", body["minAggregateScore"])
print("coins      :", len(body["coinSelection"]["tickers"]))
print("assumptions: %d entries, longest %d (cap 500)" % (len(assumptions), max(len(a) for a in assumptions)))
print("body bytes :", len(raw))
print("written    : out/tpo_suite/bodies/PVM_create.json")
