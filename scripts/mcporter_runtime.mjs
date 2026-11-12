// One long-lived mcporter runtime for a script that makes hundreds of calls (2026-11-11).
//
// `npx mcporter call` starts Node, loads the config and opens a new MCP session for every call: 240 hints took 162
// minutes on 2026-11-11 (a CPU-starved host), and the contract moved under the read (168.2.0 -> 168.3.0) before it
// finished. This helper keeps ONE runtime and ONE session: a JSON line in, a JSON line out.
//
//   in   {"id": 1, "tool": "get_metric_construction_hints", "args": {"metric": "EMA20"}, "timeoutMs": 120000}
//   out  {"id": 1, "ok": true, "value": <what `mcporter call --output json` prints>}
//        {"id": 1, "ok": false, "error": "<why, at most 300 characters>"}
//   first line out: {"ready": true, "server": "battlegrid-anbu"} (or {"ready": false, "error": ...} and exit 2)
//
// The value is `createCallResult(raw).json()`, the same reduction the CLI's `--output json` applies, so a caller reads
// the same object from either transport. `disableOAuth: true`: a cached token is used, an interactive authorization is
// never started (re-authorizing is the user's step) - a call that needs one fails with the server's message.
//
//   node scripts/mcporter_runtime.mjs [server]      MCPORTER_DIST=<.../node_modules/mcporter> when the package is not
//                                                   resolvable from here (the npx cache)
import path from 'node:path';
import { createInterface } from 'node:readline';
import { pathToFileURL } from 'node:url';

const server = process.argv[2] || 'battlegrid-anbu';
const say = (obj) => process.stdout.write(JSON.stringify(obj) + '\n');
const why = (e) => String(e?.message ?? e).slice(0, 300);

let runtime;
let createCallResult;
try {
  const dist = process.env.MCPORTER_DIST;
  const mod = await import(dist ? pathToFileURL(path.join(dist, 'dist', 'index.js')).href : 'mcporter');
  createCallResult = mod.createCallResult;
  runtime = await mod.createRuntime();
} catch (e) {
  say({ ready: false, error: why(e) });
  process.exit(2);
}
say({ ready: true, server });

for await (const line of createInterface({ input: process.stdin })) {
  if (!line.trim()) continue;
  let req;
  try {
    req = JSON.parse(line);
  } catch {
    say({ id: null, ok: false, error: 'the request line is not JSON' });
    continue;
  }
  try {
    const raw = await runtime.callTool(server, req.tool, {
      args: req.args ?? {},
      timeoutMs: req.timeoutMs ?? 120000,
      disableOAuth: true,
    });
    const value = createCallResult(raw).json();
    say(value === null ? { id: req.id, ok: false, error: 'the answer is not JSON' } : { id: req.id, ok: true, value });
  } catch (e) {
    say({ id: req.id, ok: false, error: why(e) });
  }
}
await runtime.close().catch(() => {});
