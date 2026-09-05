# Next-session handoff plan (written 2026-08-31)

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:executing-plans to work
> through this plan. Steps use checkbox (`- [ ]`) syntax. Task 1 is deadline-bound;
> everything else can wait. **Nothing in this plan authorises a write to the BattleGrid
> platform.** Task 1 is read-only. Task 3 is the user's own command. Task 4 is a proposal
> that needs the user's go-ahead before any code is written.

**Goal:** carry the OMEGA project forward from the merged condition-clock work without
losing the perishable out-of-sample evidence, and without assuming anything that was not
measured.

**Architecture:** no new subsystem. Task 1 re-runs an existing, proven procedure. Task 2
is bookkeeping. Task 3 is a one-line decision that belongs to the user. Task 4 is
deliberately unspecified pending brainstorming.

**Tech Stack:** Python 3 + pytest (908 tests, all passing at `80f479b`); the BattleGrid
MCP connector (`mcp__c330236a-…__*`); the Hyperliquid public REST API.

## Global Constraints

- **Binding and deployment are never the assistant's to perform** —
  `rebind_intelligence_agent`, `upsert_radar_deployment`, arena/market-grid entries. No
  general "go ahead" authorises them. (P4, and doc 20 §7.)
- **Every platform write needs its own verbatim per-instance authorization** naming the
  operation and the instance, in the session where it runs (doc 20 §5). Task 1 needs
  none: it is read-only.
- **Extract, never infer.** On a refusal naming a field the published schema does not
  declare, read an existing record back for the platform's own migration defaults and
  mirror them exactly. Never invent semantics. (Four drift instances so far; two on
  2026-08-30 alone.)
- **Never predict performance.** No outcome data supports such a claim (P1).
- Run `python -m pytest -q` from the repo root before and after any code change; the
  baseline is **908 passed**.

## Verified state at the time of writing (re-verify, do not trust this list)

Measured on 2026-08-31 from `C:/Users/rafae/Documents/GitHub/OMEGA`:

- `main` is at **`80f479b`**, working tree clean, **6 commits ahead of `origin/main` and
  not pushed**. The condition-clock branch was merged and deleted — do not look for it.
- Test suite: **908 passed**.
- An **empty** directory may linger at `.claude/worktrees/condition-clock-migration-c78839`.
  It is not a registered worktree and nothing depends on it; deleting it is safe.
- Strategy **`b9438519-8223-4ef1-a3c3-6f4592bb823d`** ("Deep-Tail Fade") exists on the
  platform at **revision 2, archived**, never bound, never deployed.
- `docs/superpowers/plans/2026-08-29-condition-clock-migration.md` is complete through
  Step 4 items 1–2. Item 3 (binding/deployment) is user-only and untouched.

**Open questions that remain UNMEASURED.** Do not answer them from reasoning; only a live
call settles them:

- whether `sections[].notes: null` is accepted (only non-empty strings have been sent);
- what `conditions[].closes > 1` does (only `1` has ever been sent);
- what non-default `entry` values mean at runtime, including why the platform assigns
  `levelSource: "SWING_HIGH"` to a strategy that trades both directions.

---

### Task 1: Out-of-sample re-pull #2 (READ-ONLY, deadline ≤ 2026-09-03)

**Why this is first:** `get_coin_candles` serves only the last 100 closed bars. At 1h that
is 4d4h of history. Run 1 pulled on 2026-08-30, so bars begin scrolling out of reach
around **2026-09-03**. A missed pull is evidence permanently lost — it cannot be
back-filled at any later date.

**Authorization:** none needed. Every call is read-only (`get_coin_candles`, Hyperliquid
public REST). The user asking to "run the re-pull" is sufficient. Do not use this task as
cover for any write call.

**Governing document:** `docs/superpowers/plans/2026-08-29-out-of-sample-repull-protocol.md`
— read it first; it is the authority and this task is its operational detail.

**Files:**
- Create: `data/research/2026-08-29-deep-tail-fade/repulls/<YYYY-MM-DD>/raw/<TICKER>_<tf>.json` (16 files)
- Create: `data/research/2026-08-29-deep-tail-fade/repulls/<YYYY-MM-DD>/candles.json`
- Create: `data/research/2026-08-29-deep-tail-fade/repulls/<YYYY-MM-DD>/funding_raw.json`
- Modify: `docs/superpowers/specs/2026-08-29-deep-tail-fade-research.md` (append a dated addendum)
- Modify: `docs/superpowers/plans/2026-08-29-out-of-sample-repull-protocol.md` (append to the Run log)
- Reuse unchanged: `data/research/2026-08-29-deep-tail-fade/repulls/analyze_repull.py`

**Interfaces:**
- Consumes: the base corpus `data/research/2026-08-29-deep-tail-fade/candles.json` and
  every existing `repulls/*/candles.json`.
- Produces: one new dated `repulls/<date>/candles.json` in the shape
  `{"_what": <str>, "series": {"<TICKER>_<tf>": [<candle objects verbatim>]}}`.
  `analyze_repull.py` globs `repulls/*/candles.json`, so a correctly named new folder is
  picked up with **no code change**.

- [ ] **Step 1: Load the candle tool schema**

Deferred tools must be loaded before they can be called. Run ToolSearch with query
`select:mcp__c330236a-7aee-4d07-ae11-e487c8cbc894__get_coin_candles`, max_results 1.

- [ ] **Step 2: Pull the 16 series, saving each response verbatim**

The ticker set is **FIXED** — changing it reintroduces selection bias. If a ticker has
delisted, record that fact; do **not** substitute another.

13 tickers at `interval: "1h", limit: 100`:
`BTC, ETH, SOL, PEPE, POPCAT, MET, MELANIA, TRUMP, HYPE, MOODENG, AIXBT, CAKE, LDO`
plus 3 at `interval: "4h", limit: 100`: `BTC, ETH, SOL`.

Save each response's `candles` array **exactly as returned** — all fields, no reordering,
no dedupe, no transformation — to
`data/research/2026-08-29-deep-tail-fade/repulls/<YYYY-MM-DD>/raw/<TICKER>_<interval>.json`.

This is 16 sequential MCP calls and is well suited to a subagent, so the raw payloads stay
out of the main context. Run 1 used exactly that and all 16 succeeded first try. Instruct
the subagent: retry a failed call **once**, then record the error text verbatim and move
on; never fabricate rows; call no other MCP tool.

- [ ] **Step 3: Verify integrity against the existing corpus BEFORE assembling**

The point of this step is to catch a platform-side data change, not to rubber-stamp the
pull. Run 1's result was 0 gaps, 0 dupes, **0 OHLCV mismatches** on 78–94 overlapping
bars per series.

Note the comparison pool: it must be **every prior source**, not just the original base
corpus. By run 2 the 100-bar window may no longer overlap the base corpus at all, which
would make a base-only check silently vacuous — it would pass by comparing nothing.

```bash
cd "C:/Users/rafae/Documents/GitHub/OMEGA" && python - << 'EOF'
import glob, json, os
from datetime import datetime, timedelta
CORPUS = "data/research/2026-08-29-deep-tail-fade"
RP     = f"{CORPUS}/repulls/<YYYY-MM-DD>"
# every prior source: base corpus + all earlier repulls (excluding this one).
# normpath is REQUIRED, not cosmetic: on Windows glob returns mixed separators
# ('repulls/' from the literal pattern, '\<date>\' from the * expansion), so a plain
# string compare silently fails to exclude this pull and the check compares the file
# against itself - overlap=100, new=0, MISMATCH=0 on every series. Verified 2026-08-31.
prev = {}
norm_rp = os.path.normpath(RP)
for src in [f"{CORPUS}/candles.json"] + sorted(glob.glob(f"{CORPUS}/repulls/*/candles.json")):
    if os.path.normpath(os.path.dirname(src)) == norm_rp:
        continue
    for key, rows in json.load(open(src, encoding="utf-8"))["series"].items():
        prev.setdefault(key, {}).update({r["timestamp"]: r for r in rows})
print("comparison pool:", {k: len(v) for k, v in sorted(prev.items())})
problems = []
for fn in sorted(os.listdir(f"{RP}/raw")):
    sym, tf = fn[:-5].rsplit("_", 1)
    rows = json.load(open(f"{RP}/raw/{fn}", encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != 100:
        problems.append(f"{fn}: expected a 100-row list"); continue
    ts   = [datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")) for r in rows]
    step = timedelta(hours=1 if tf == "1h" else 4)
    gaps = sum(1 for a, b in zip(ts, ts[1:]) if b - a != step)
    dupes = len(ts) - len(set(ts))
    bmap = prev.get(f"{sym}_{tf}", {})
    overlap = sum(1 for r in rows if r["timestamp"] in bmap)
    mism = sum(1 for r in rows if r["timestamp"] in bmap
               and any(bmap[r["timestamp"]][k] != r[k]
                       for k in ("open", "high", "low", "close", "volume")))
    new  = sum(1 for r in rows if r["timestamp"] not in bmap)
    print(f"{sym}_{tf:>2}  gaps={gaps} dupes={dupes} overlap={overlap} MISMATCH={mism} new={new}")
    if gaps or dupes or mism:
        problems.append(f"{fn}: gaps={gaps} dupes={dupes} mismatch={mism}")
    if overlap == 0:
        problems.append(f"{fn}: ZERO overlap with prior data - a gap in the record")
print("problems:", problems or "none")
EOF
```

Expected: `problems: none`, with a non-zero `overlap` on every series.

Two distinct failure signals here, and neither should be waved through:

- **Any non-zero MISMATCH** means the platform restated history for a bar it had already
  served. That is a finding: stop, record it verbatim in `data/audit/`, and report it.
- **`overlap == 0` on a series** means more than 100 bars elapsed since the last pull and
  there is now a permanent hole in that coin's record. The pull is still worth keeping —
  save it — but the gap must be stated in the addendum and **never interpolated across**.
  `analyze_repull.py` computes reference windows from adjacent rows, so a silent hole
  would corrupt the stretch calculation at the seam.

- [ ] **Step 4: Assemble `candles.json` and pull funding**

`startTime` continues from the last funding row already on disk. Record the **sign mix**:
the FUNDING-leg confound resolves only in a window containing negative-funding hours (run
1: BTC 0/20, ETH 0/20, SOL 1/20 negative — still unresolved).

```bash
cd "C:/Users/rafae/Documents/GitHub/OMEGA" && python - << 'EOF'
import glob, json, os, urllib.request
RP = "data/research/2026-08-29-deep-tail-fade/repulls/<YYYY-MM-DD>"
series = {fn[:-5]: json.load(open(f"{RP}/raw/{fn}", encoding="utf-8"))
          for fn in sorted(os.listdir(f"{RP}/raw"))}
json.dump({"_what": "Out-of-sample re-pull <YYYY-MM-DD> per the re-pull protocol. "
                    "Read-only get_coin_candles, closed bars, 100-bar cap; 13-coin fixed "
                    "1h set + BTC/ETH/SOL 4h. Verified against the prior corpus. "
                    "IRREPLACEABLE once the window scrolls.",
           "series": series},
          open(f"{RP}/candles.json", "w", encoding="utf-8"),
          separators=(",", ":"), ensure_ascii=False)
print("candles.json:", os.path.getsize(f"{RP}/candles.json"), "bytes,", len(series), "series")

# continue from the latest funding row across ALL prior files, not just the base one -
# the base record ends 2026-08-29, so using it alone would re-pull hours already saved
# and misreport the "new hours" count. The two files use different shapes.
CORP = "data/research/2026-08-29-deep-tail-fade"
last = {c: 0 for c in ("BTC", "ETH", "SOL")}
base_f = json.load(open(f"{CORP}/funding_history.json", encoding="utf-8"))
for c in last:
    last[c] = max(last[c], max(r["time"] for r in base_f[c]))
for p in sorted(glob.glob(f"{CORP}/repulls/*/funding_raw.json")):
    coins = json.load(open(p, encoding="utf-8"))["coins"]
    for c in last:
        if coins.get(c):
            last[c] = max(last[c], max(r["time"] for r in coins[c]))
print("continuing funding from:", last)
out = {}
for coin in ("BTC", "ETH", "SOL"):
    start, rows, seen = last[coin] + 1, [], set()
    for _ in range(40):
        req = urllib.request.Request("https://api.hyperliquid.xyz/info",
            data=json.dumps({"type": "fundingHistory", "coin": coin,
                             "startTime": start}).encode(),
            headers={"Content-Type": "application/json"})
        page = json.loads(urllib.request.urlopen(req, timeout=30).read())
        new = [r for r in page if r["time"] not in seen]
        if not new: break
        rows += new; seen |= {r["time"] for r in new}
        start = max(r["time"] for r in new) + 1
        if len(page) < 20: break
    rows.sort(key=lambda r: r["time"])
    out[coin] = rows
    rates = [float(r["fundingRate"]) for r in rows]
    neg = sum(1 for x in rates if x < 0)
    print(f"{coin}: {len(rows)} new hours, negative {neg}/{len(rates)}")
json.dump({"_what": "Hyperliquid public fundingHistory rows, VERBATIM, continuing the "
                    "prior funding record.", "coins": out},
          open(f"{RP}/funding_raw.json", "w", encoding="utf-8"),
          indent=1, ensure_ascii=False)
EOF
```

- [ ] **Step 5: Run the analysis battery unchanged**

```bash
cd "C:/Users/rafae/Documents/GitHub/OMEGA" && python data/research/2026-08-29-deep-tail-fade/repulls/analyze_repull.py
```

Expected: a `COMBINED corpus` block and a `NEW-ONLY slice` block, the latter marking
`<-- THE CELL` on the `>90th` row. If the script raises `COLLISION DISAGREES`, two sources
give different OHLCV for the same timestamp — that is a platform restatement and a
finding; stop and record it.

- [ ] **Step 6: Read the result honestly — the pre-registered rule**

THE number is the `>90th` cell of the **NEW-ONLY** block: hit%, edge, n.

Fixed in advance by the protocol, and not to be renegotiated after seeing the data:
**sustained out-of-sample hit ≤ 55% or edge ≤ 0 at the deep tail means the premise
failed**, and the registry entry should say so. Do not move the goalposts to a different
threshold, window or coin subset that happens to work.

Three honesty traps this specific analysis sets — all three were live in run 1:

1. **"NEW-ONLY" is cumulative, not per-run.** `analyze_repull.py` computes each coin's
   cutoff from the **original base corpus only**, so on run 2 the "new-only" slice covers
   *all* bars since 2026-08-29 — run 1's bars included. That is a defensible quantity
   (total out-of-sample evidence), but it must be labelled as such. Reporting it as "this
   window's result" would be false.
2. **Analysis thresholds ≠ the strategy's gates.** The battery uses percentile-calibrated
   stretch thresholds. The deployed strategy uses fixed constants (`%B < 0.05`,
   `RSI14 < 35`, plus the Bollinger signals). "Zero events in the analysis" does **not**
   mean "the strategy would not have fired." They are different triggers and the fixed-gate
   firing rate has never been measured.
3. **Check the per-coin split before summarising.** In run 1 every deep-tail event was on
   an alt; BTC and ETH produced **zero** events, so the universe the created strategy
   actually trades still has no out-of-sample evidence at all. If that repeats, say it
   plainly rather than quoting the pooled number.

- [ ] **Step 7: Write the dated addendum**

Append a `## Out-of-sample addendum · re-pull N, <YYYY-MM-DD>` section to
`docs/superpowers/specs/2026-08-29-deep-tail-fade-research.md`, following the run-1
addendum already in that file as the format. It must state: pull integrity numbers, THE
cell with its confidence interval and n, the majors-vs-alts split, the funding sign mix,
and — explicitly — what is still not established.

Then append one entry to the `## Run log` in
`docs/superpowers/plans/2026-08-29-out-of-sample-repull-protocol.md`, including the next
due date (this pull's date + 3 to 4 days).

- [ ] **Step 8: Commit the data — it is irreplaceable**

```bash
cd "C:/Users/rafae/Documents/GitHub/OMEGA" && python -m pytest -q 2>&1 | tail -1 && git add -A && git status --short
```

Expected: `908 passed` (this task touches no code). Then commit with a message stating the
measured cell and its limitations, e.g.
`Out-of-sample re-pull 2 (<date>): <THE cell verbatim>; <one honest sentence on what it does and does not show>`.

---

### Task 2: Clear the leftover empty worktree directory (optional, 10 seconds)

**Files:** none tracked by git.

- [x] **Step 1: Remove it if it is still there and still empty** (2026-09-05: the directory no longer exists; nothing to do)

It was left behind because it was a live shell's working directory during the merge. A
**new** session will not hold that lock.

```bash
cd "C:/Users/rafae/Documents/GitHub/OMEGA" && ls -a ".claude/worktrees/condition-clock-migration-c78839" 2>/dev/null && rmdir ".claude/worktrees/condition-clock-migration-c78839" && echo removed
```

Only proceed if the listing shows nothing but `.` and `..`. If it has contents, stop and
report — that would mean something was written there after the merge, which is not
expected.

---

### Task 3: Decide whether to push `main` (THE USER'S CALL — do not run unasked)

**Context the user needs to decide:** `main` is 6 commits ahead of `origin/main`. Those
commits contain ~1.5 MB of candle data that the 100-bar endpoint cannot serve again. Until
it is pushed, that data exists on **one machine only**. Task 1 adds more of the same.

This is not the assistant's decision. The user declined a push once already, on
2026-08-30, choosing a purely local merge; that choice stands until they say otherwise.

- [ ] **Step 1: Ask, then run only if the user says to**

```bash
git push origin main
```

Do not force-push. If the push is rejected, the remote has moved — investigate; do not
reach for `--force`.

---

### Task 4: PROPOSED, NOT APPROVED — a schema-drift preflight

**Status: this task has no approved design and no user go-ahead. Do not write code for
it.** It is recorded here so the idea is not lost, and so the next session knows it is a
proposal rather than a decision.

**The problem it would address (measured, not speculative):** the platform has drifted
four times, twice on 2026-08-30 alone. Each instance cost a refused live call and a round
of rediscovery. Both of that day's refusals were, in principle, detectable offline: a
read-only diff of the live compile schema and a reference strategy read-back against what
`omega.generate.StrategyPlan.wire()` emits would have shown the missing `entry` fields
before any call was spent.

**Why it is not specified here:** designing it is creative work. Per
`superpowers:brainstorming`, the design conversation comes before any plan, and per the
project's own rules the user chooses what gets built. Open questions a brainstorm would
need to settle: whether it lives as a test, a script, or a `preflight()` API; which
reference strategy it reads back and whether that read is cheap enough to run often;
whether it should fail loudly in CI or only warn; and how it avoids becoming another
cached capability list that goes stale — the exact failure mode it is meant to prevent.

- [ ] **Step 1: If the user wants this, brainstorm the design with them first**

Use `superpowers:brainstorming`, then `superpowers:writing-plans` to produce a real
implementation plan with TDD tasks. Do not skip to code.

---

## What is deliberately NOT in this plan

- **Binding `b9438519-…` to an agent, or deploying it.** User-only, always. The steps are
  written out for the user in `data/created/b9438519-8223-4ef1-a3c3-6f4592bb823d.checklist.md`.
  No general instruction to "continue" ever authorises them.
- **Any further compile or apply.** The authoring loop is proven end-to-end; there is no
  pending strategy work. A future compile needs its own verbatim authorization.
- **Settling the unmeasured questions** (`notes: null`, `closes > 1`, non-default `entry`).
  Each would cost a live compile, and none of them blocks anything right now. Left open,
  and honestly labelled as open, until there is a reason to spend a call.
