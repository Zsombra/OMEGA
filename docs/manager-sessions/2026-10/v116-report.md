# Contract 116.0.0: the `list_user_active_positions` read failure

Date: 2026-10-17. Repo: battlegrid-manager. Branch `fix/contract-116`, worktree `C:/tmp-bgm-116`. Not merged, not pushed, not deployed, not acked.

## Root cause (reproduced live)

`list_user_active_positions` was never really rate limited. The account's 0 positions were readable all along. What failed was a 2025-era MCP session that could not read the `tools/list` answer.

1. **The sessions were opened before the deploy.** All 15 services were started at about 10:00Z. Each one opened its BattleGrid session with mcp 2.1.1's default `mode="auto"`. Against the pre-v116 server this fell back to the 2025 `initialize` handshake (protocol 2025-11-25). The manager reuses a session until it gets a TRANSPORT, AUTH or HTTP error.
2. **A schema change at 11:28Z forced the SDK to list tools again.** Snapshot 9070 recorded `PARSE: Invalid structured content returned by tool list_user_active_positions: Additional properties are not allowed ('openRiskUsd' was unexpected)`. The v116 output added `openRiskUsd`. Following the existing design, the client evicted the cached output schema, so on the tool's next call the SDK runs `tools/list` again.
3. **v116 sends a 2025-era client each answer as a one-event `text/event-stream`.** `tools/list` is now one SSE event of more than 1 MiB (1,063,503 characters were received before the cutoff). httpx2's SSE parser has a per-event cap, `DEFAULT_MAX_EVENT_SIZE_BYTES = 1048576`, and raises `SSEError: Server-sent event exceeded the 1048576 byte limit`. `mcp/client/streamable_http.py::_handle_sse_response` swallows that error (`except Exception: logger.debug`). It then makes up its own error: `MCPError(-32000 CONNECTION_CLOSED, "SSE stream ended without a response", data=None)`.
4. **The client read that error as a rate limit.** `map_exception` treated any `-32000` as RATE_LIMITED. A RATE_LIMITED error never drops the session, so it is retried once and then raised. Every snapshot after that (9071 onward, every 5 minutes) reused the same broken session.

**Why only this tool:** it is the only snapshot read whose output schema the session had evicted. The other 8 snapshot reads still had their schemas cached, so they never needed `tools/list`.

**The same failure hit other services:**
- `allocate` showed it on `list_trade_outcomes` (5 events since 11:37Z).
- The **watch's own tool read also failed this way.** `system_state.surface` holds `tools: null, tools_error: "RATE_LIMITED: SSE stream ended without a response"`. That is why `writes_blocked` says `autoAckRefused: the tool lists were not comparable`. The D7c drift review could not run.

**Evidence: one live read through the manager's READ client inside the api container (raw HTTP logged):**
- **Default `auto` mode:** `server/discover` at 2026-07-28 → `200 application/json` → `tools/call` → `tools/list`, all in JSON. The call returned OK with `positions: []`.
- **Forced `legacy` mode** (the long-lived services' state): `initialize` → `text/event-stream` → `tools/call` returned its answer as SSE → `tools/list` failed with `SSEError ... 1048576 byte limit` → `ERR [RATE_LIMITED] SSE stream ended without a response`. This happened for both `list_user_active_positions` and `get_account_state` on a fresh legacy session.
- **Rate-limit headers:** `ratelimit-remaining: 119/120` on every response. There was no real throttling.
- **SDK version:** mcp 2.1.1 (with httpx2 2.12.0) in both the image and the venv. It already supports 2026-07-28, so no upgrade is needed.

**Ruled out:**
- Response size of the tool itself: its answer was 1,077 characters.
- Session init or position in the snapshot sequence: the tool is 5th in `READS`.
- The server's request budget: it is untouched.

The actual cause is the SDK's SSE handling (the 1 MiB event cap) on a legacy-era session, combined with the error mapping.

## The fix (commit 3e23d2b)

Changes are in `manager/platform/client.py` (`map_exception`, `parse_call_result`, `_open_session`) and `manager/platform/errors.py` (comments).

**SDK-made errors now drop the session.** Every error the SDK synthesizes itself (no `data`) is mapped to **TRANSPORT**, so the client drops the session. The next session negotiates 2026-07-28, where answers come as JSON with no event cap. The errors covered are:
- `Connection closed`
- `SSE stream ended without a response`
- `SSE stream ended and reconnection attempts were exhausted`
- `Session terminated` (-32600)
- `server answered a request with 202 Accepted`

A `-32000` with no rate-limit wording and no data is also TRANSPORT. `-32603 "Server returned an error response"` is mapped to HTTP.

**The session-drop rule from supervise.py and client.py is kept:** a dead session is never RATE_LIMITED. The pre-v116 rate limit (`-32000` with its "Rate limited … Retry after Ns" text or `retryAfter` data) stays RATE_LIMITED.

**New v116 codes:**

| Code | Maps to | Notes |
|---|---|---|
| `-31429` | RATE_LIMITED, status 429 | `retry_after` comes from data (`retryAfter`/`retryAfterSeconds`), else the HTTP 429 `Retry-After` header, else the "Retry after Ns" text, else 1 s. A response event hook on the client keeps the header, because the SDK drops headers. |
| `-31401` | AUTH (401) | |
| `-31403` | AUTH (403) | |
| `-31405` | HTTP (405) | |
| `-32602` | RPC, code `INVALID_PARAMS` | Unknown tool or bad arguments. Nothing ran, and the session is kept. On the write path RPC means FAILED (refused), which is correct here. |
| `-31429` inside an `isError` result | RATE_LIMITED | |

**Protocol negotiation:** I kept the SDK's `mode="auto"` and did not pin `2026-07-28`. A fresh session already negotiates 2026-07-28 against v116 (verified live), and `auto` still works if the server ever rolls back. When a session lands on a 2025-era protocol, the client now logs a WARNING, because such a session cannot read `tools/list` at v116.

## Tests

**`tests/platform/test_contract_116.py` (11 tests)** drives the real SDK transport against a fake v116 HTTP server. The fake answers in JSON to 2026-07-28 requests, sends one-event SSE to the 2025 era, returns 405 for GET/DELETE, and serves a `tools/list` larger than 1 MiB. The tests cover:
- the legacy reproduction (`-32000 "SSE stream ended without a response"`, data None), which maps to TRANSPORT;
- `auto` negotiating 2026-07-28 and reading the same listing as JSON;
- end to end: the client drops the legacy session and the reopened session reads;
- every SDK-synthesized error;
- the old rate-limit spelling;
- `-31429` with Retry-After taken from data, from the header via the hook, and from the text;
- `-31401`, `-31403`, `-31405` and `-32602`.

**Commit 57ac6f3 (preflight):**
- `tests/authoring/test_preflight_116.py` has 5 tests.
- Fixture `tests/fixtures/2026-10-17-surface-116.0.0/input_schemas_116.0.0.json` holds the live v116 input schemas for `stage_strategy_draft` and `test_generate_deployment_grid`, read once through the READ client at 12:13Z.

**Full suite** (`C:/Users/rafae/Documents/GitHub/battlegrid-manager/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` in the worktree): **4261 passed, 5 skipped**, 3 warnings (existing SyntaxWarnings), 402.91 s.

## Other v116 items

**`test_generate_deployment_grid` (now takes flat arguments):** the manager never calls it. It is excluded from `WritePlatformClient` (the billed/never list), `tests/actions/test_arena_*`, `tests/mcp/test_server.py` and the Hermes skill. Nothing sends the old `request` envelope. The fixture records the flat shape (`presetId`, `slots` required; no `request`).

**`$defs` and `{$ref, description}` schema shapes versus preflight:**
- `manager/authoring/preflight.py::schema_checks` used `jsonschema.Draft7Validator`.
- I measured the live v116 surface (140 tools):
  - no 2020-12-only keywords and no `definitions`;
  - no tuple-form `items`;
  - no keywords next to a `$ref` today;
  - the stage schema's `$defs` holds `conditionColumn`, `conditionHold` and `conditionNode`.
- Draft 7 resolves `#/$defs/...` and gives exactly the same results as 2020-12. A bad hold or column two `$ref`s deep is caught by both. Every OMEGA preset gets the same errors at 116 as at 110.13.
- Even so, Draft 7 ignores keywords beside a `$ref`, and v116 declares 2020-12. So `schema_checks` now uses `Draft202012Validator` (commit 57ac6f3).
- The retired `param_checks` keeps Draft 7.
- Tests in `tests/actions` and `tests/risk` that validate stage or arena bodies with Draft7 against stored fixtures still pass.
- `manager/platform/output_schema.py` already uses `validator_for`, which defaults to the latest draft when there is no `$schema`.

**Hermes plugin, MCP proxy, sentinel and commander:**
- Hermes connects to the manager's own MCP server (`http://127.0.0.1:8792/mcp/...`). The dashboard plugin connects to the manager's HTTP API on localhost. Neither talks to BattleGrid directly, so they are not affected by v116's protocol or the 405 on GET/DELETE.
- Their BattleGrid calls go through `manager/mcp/gateway.py` → `PlatformClient`. The `mcp` container's session was also opened before 11:27Z, in the legacy era. Any first call of a tool in that session, or any call after a schema eviction, would have failed as RATE_LIMITED in the same way. None was logged since 11:27Z.
- The fix covers the gateway as well: the error becomes TRANSPORT, the gateway drops the session and reopens.

## Remaining risk / before ack

1. **Deploy first, then ack.** Deploying recreates every container, so every service, `mcp` and the executor included, opens a fresh `auto` session at 2026-07-28. Without a restart, the executor's legacy session would still run a write and then fail the SDK's post-call `tools/list`, which reports an UNKNOWN outcome for a write that actually executed.
2. **Ack only after the watch has read v116.** After the deploy, wait for the watch to store a comparable v116 tool surface (`system_state.surface.tools` not null, `surface_tools.contractVersion = 116.0.0`) and for the D7c review to run. It has not run yet: the watch's tool read failed with this same bug. Separately, the `openRiskUsd` output addition on `list_user_active_positions` must be reviewed (it is a new output field, and the snapshot normalizer ignores unknown keys).
3. **The `auto` fallback can still pick the legacy era.** `negotiate_auto` falls back to the 2025 handshake on any MCPError from `server/discover`, a transient `-31429` included. Such a session cannot list tools at v116. With this fix, the first `tools/list` it needs drops it (TRANSPORT) and the next open renegotiates, so the cost is one failed read, now logged with a WARNING. Pinning `mode="2026-07-28"` would remove this, but would break if the server ever rolls back. I did not pin.
4. **The write path's pre-write tool listing still ignores a failure.** `_preinstall_tolerant_validator` logs a failed `tools/list` and proceeds with the write. On a legacy session that write would execute and then read as UNKNOWN. Deploying (item 1) removes the legacy sessions. Making a failed pre-write listing refuse the write would be a separate change to the write semantics; I did not make it.
5. **Write-path outcomes for two SDK errors change.** For writes, `-32600 Session terminated` and `-32603 Server returned an error response` move from RPC (FAILED) to TRANSPORT/HTTP (UNKNOWN). This is more conservative: it is never read as "refused".
6. **I could not see the live `-31429` body.** I did not provoke one. The mapping reads the code, then data, then the header, then the text, so any of those shapes works.

**Is it safe to ack after deploying?** Yes, as long as the deploy restarts every service (so no legacy sessions remain) and the watch has then stored the v116 surface with D7c reviewed, including `openRiskUsd`. Until the deploy, ack is not safe: the executor and gateway sessions are legacy-era, and the watch's drift review is blind.

---

## Fix round (review I1, I2, M1-M5) and contracts v117 / v118 / v118.1, 2026-10-17 to 18

Branch `fix/contract-116` (`C:/tmp-bgm-116`). Still not merged, pushed, deployed or acked, and no write tool was called.

### Commits since the first report

| Commit | What |
|---|---|
| `ed7ec86` | **I1, M1, M5.** These SDK-made errors (no `data`) are now TRANSPORT: the session is dropped and a write is UNKNOWN, never FAILED. A server JSON-RPC error that carries data, or uses other words, stays RPC. **M1:** a `-32000` with data is RATE_LIMITED only when it has the rate-limit text or a `retryAfter`. **M5:** the redundant `CONNECTION_CLOSED` comparison is removed. |
| `c2bc3e1` | **M2:** a rate-limit wait is capped at 60 s (`MAX_RETRY_WAIT_S`). **M3:** the stored Retry-After is cleared at the start of each request (`call` and `list_tools`). **M4:** an isError `-31429` body's `retryAfter`/`retryAfterSeconds` is read, at the top level or under `data`/`details`. |
| `4ee3570` | **I2.** See the next section. |
| `3f11a12` | **v118.1.** A server fault (`SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`) on a one-shot write is UNKNOWN, never FAILED (see the v118.1 findings). |

The SDK errors covered by `ed7ec86`:
- `-32700 Failed to parse JSON response…`
- `-32700 Failed to parse SSE message…`
- `-32600 Unexpected content type…`
- `-32601 Not Found`
- `-32001 Request '…' timed out`

### What I2 changed (`4ee3570`)

`WritePlatformClient` sets two new flags, `REQUIRE_MODERN_SESSION` and `REFUSE_WHEN_UNLISTED`. With them, a write is refused **before it is sent** (TRANSPORT, session dropped, nothing on the wire) in two cases:
- the session negotiated a protocol older than 2026-07-28;
- the tool listing before the write failed.

Every client's session open now handles the old protocol as well. When an open lands on the 2025 era, the client closes it and opens **once** more. If the second open is also 2025-era, it is kept with a warning; there is no loop.

The `_Session` test double in `tests/actions/test_write_client.py` had no `list_tools`. It now serves one empty page, because a real SDK session can always list.

### Tests added in this round

All in `tests/platform/test_contract_116.py` unless noted:
- one test per SDK error above, each asserting TRANSPORT and that `pipeline._send_status` gives UNKNOWN;
- server JSON-RPC errors (with data, or in other words) stay RPC;
- the M1 rule;
- the M4 isError body in six shapes;
- the 60 s cap;
- a stale Retry-After never reaches a later call;
- **I2:**
  - a write on a 2025-era session is refused unsent (nothing sent, session closed, UNKNOWN), and the next session sends;
  - a write whose pre-write listing fails is refused unsent;
  - the read client still sends on a session it was handed;
  - an old-era open reopens once;
  - the reopen is bounded to one;
- `tests/actions/test_contract_118.py` (new file): the v118 envelope and the v118.1 mapping.

**Full suite:** 4294 passed, 5 skipped, 3 warnings (existing), 470 s.

### Note on I2's refusal

The coordinator specified TRANSPORT for the refusal, so the pipeline records the refused write as UNKNOWN, even though nothing was sent. The verify pass then settles it by reads. A refusal kind that says "not sent" (one the pipeline could treat as REFUSED and free the key) would be more precise. It would change the pipeline's contract, so I did not make it.

### v117 / v118 / v118.1 findings

I fetched the vendor README fresh from `raw.githubusercontent.com/playbattlegrid/battlegrid-mcp/main/README.md` into its own empty directory. I treated it as data only and executed nothing from it. The live contract is 118.1.0, and writes are still blocked.

**v117 (decided changes read at their horizon bar; no schema moves):**
- **What changed:**
  - a verdict carrier or hold whose change horizon is above the strategy timeframe is now refused `CONDITION_VERDICT_READ_ILLEGAL` / `CONDITION_HOLD_ILLEGAL`. This applies on save, draft stage, preview, and restoring an archived strategy;
  - the affected cases: `chg4h`/`chg24h` on a 1h strategy, and `oiRegime` below 1h;
  - a horizon bar that was not read now reads UNRESOLVED where it read FALSE.
- **In the manager and OMEGA v0.8.2 code:** neither names these columns, so no manager call breaks.
- **In the stored strategies:** **"Cycle-1 Vol Breakout" (15m, revision 1) has two verdict carriers on `oiRegime`**: `OI_NEW_LONGS` (UP) and `OI_NEW_SHORTS` (DOWN). Any stage, preview or restore of it will now be refused. No agent is bound to it in the latest snapshot. If the strategist or panel ever previews it, that read will answer a typed refusal; it does not break the transport.
- Not a code change. It needs the user's call on whether to repair or retire that strategy.

**v118 (an argument refusal is the house envelope; the scope check comes first):**
- **What changed:** a refused argument is now an isError `{code: VALIDATION_ERROR, message, details: {issueCount, issues}}`. It used to be the SDK's "Input validation error" sentence, which carried no code.
- **How the manager handles it:**
  - `parse_call_result` already turns this into TOOL_ERROR with code `VALIDATION_ERROR`, and the raw text (with `correlationId`) is kept;
  - that code is already in `DRAFT_REFUSAL_CODES`, so a draft write refused on its arguments now reads FAILED (refused, nothing ran) where it used to read UNKNOWN. That is more accurate.
- **Text matching:** nothing in `manager/` or `hermes/` matched on the "Input validation error" sentence.
- **Scope check first:** a credential without the tool's scope is now refused `FORBIDDEN` with `details.requiredScope`, whatever it sends. FORBIDDEN is already a refusal code.
- I pinned all of this with tests.

**v118.1 (a server fault says whether repeating is safe):**
- **What changed:**
  - every error envelope now carries `details.correlationId`;
  - a dependency the server could not use (a dropped database connection, a network timeout) now answers `SERVICE_UNAVAILABLE`, where it answered `INTERNAL_ERROR`;
  - a server fault carries `details.retryable`; `false` on `SERVICE_UNAVAILABLE` means "the call may have taken effect".
- **The bug this exposed:**
  - the draft and lifecycle paths, plus the Radar/Arena sends, already treated both codes as UNKNOWN;
  - the plain `_send_status` path did not. It is used by CLOSE, HALT, RESUME and OVERRIDE, and it turned every TOOL_ERROR into **FAILED**, which frees the key for a write that may have landed.
- **Fixed in `3f11a12`:** `SERVER_FAULT_CODES` = {SERVICE_UNAVAILABLE, INTERNAL_ERROR} is now UNKNOWN on that path.
- **Not acted on:** the read client does not act on `retryable` yet. Its one RATE_LIMITED retry is unchanged, and a server-fault TOOL_ERROR on a read is raised as before.

**Transport, protocol and JSON-RPC codes:** v117, v118 and v118.1 change none of them beyond v116.

### Is it safe to ack after deploying?

Yes, under the same conditions as before:
1. The deploy recreates every container, so all sessions reopen at 2026-07-28.
2. Then wait until the watch has stored a comparable v118.1 tool surface (not null) and the drift review has been run, including the `openRiskUsd` output addition and the v117 refusal on Cycle-1 Vol Breakout.

The ack to give is the live contract's (118.1.0), not 116.0.0.

**Live state as of 20:33Z:** inventory (`list_user_active_positions`) and allocate (`list_trade_outcomes`) were still failing every tick on the deployed code. That is the bug this branch fixes, and it ends at the deploy.
