#!/usr/bin/env node

/**
 * @battlegrid/mcp-server — stdio proxy to BattleGrid's remote MCP server
 *
 * Reads BATTLEGRID_API_KEYS (comma-separated) or BATTLEGRID_API_KEY from
 * environment, discovers account identities via GET /mcp/identity, connects
 * to the remote BattleGrid MCP server via Streamable HTTP, and re-exposes
 * all tools, prompts, and resources over stdio transport for local MCP clients.
 *
 * Multi-account support: when multiple keys are configured, an `account`
 * enum parameter is injected into every tool so the AI agent can choose
 * which account to act as. Tool calls are routed with the matching Bearer token.
 *
 * Strategy authoring (v3): the strategy-authoring tools publish one strict
 * server-owned outer object, `{ request: canonicalPayload }`. In multi-account
 * mode the proxy adds `account` only as a sibling of `request`, producing
 * exactly `{ account, request }`; on a call it strips only `account` and
 * forwards the unchanged `{ request }`. It never descends into or reconstructs
 * the nested request — the server owns every required field, bound, union
 * discriminator, and `additionalProperties:false` constraint.
 *
 * Versions (two of them, describing two different things):
 *   - PACKAGE_VERSION — this proxy's own code. Sent UPSTREAM as the client identity.
 *   - the announced contract — read from the upstream handshake at connect time and relayed
 *     DOWNSTREAM verbatim. Never a constant compiled into this package. See `announcedIdentityOf`.
 *
 * Architecture: Matches Stripe's @stripe/mcp pattern — thin authenticated proxy.
 *
 * Usage:
 *   BATTLEGRID_API_KEY=bg_live_... npx @battlegrid/mcp-server
 *   BATTLEGRID_API_KEYS=bg_live_aaa,bg_live_bbb npx @battlegrid/mcp-server
 *
 * Environment Variables:
 *   BATTLEGRID_API_KEYS (optional) — Comma-separated list of API keys
 *   BATTLEGRID_API_KEY  (optional) — Single API key (fallback if BATTLEGRID_API_KEYS not set)
 *   BATTLEGRID_API_URL  (optional) — Override server URL (default: https://mcp.battlegrid.trade/mcp)
 */

import { createHash } from 'crypto';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
  ListPromptsRequestSchema,
  GetPromptRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
  type Implementation,
  type Prompt,
  type Resource,
} from '@modelcontextprotocol/sdk/types.js';

/**
 * This package's own version — the proxy's code, and nothing else.
 *
 * It deliberately does NOT describe the server's wire contract. That number is read from the
 * upstream handshake on every connection and relayed downstream (`announcedIdentityOf`), so the two
 * cannot drift: there is no second place to update and no release needed when the contract moves.
 *
 * Sent upstream as the CLIENT identity, where "which proxy build is calling" is exactly the question
 * being asked. Move it for a change to THIS package — a proxy fix, a dependency bump, a docs
 * correction. Never move it to track the server.
 */
export const PACKAGE_VERSION = '31.2.13';
export const DEFAULT_URL = 'https://mcp.battlegrid.trade/mcp';
const MAX_RETRIES = 3;
const RETRY_DELAYS_MS = [2000, 4000, 8000];

// One rule, two expressions. Asserted here so the delay table genuinely bounds the attempt count,
// which is what lets connectWithRetry index it without a fallback.
if (RETRY_DELAYS_MS.length !== MAX_RETRIES) {
  throw new Error(
    `Retry budget disagrees with itself: MAX_RETRIES=${MAX_RETRIES} but RETRY_DELAYS_MS carries ` +
    `${RETRY_DELAYS_MS.length} delays. Reconcile them at their declaration.`
  );
}

// --- Types ---

export interface EnvConfig {
  apiKeys: string[];
  apiUrl: string;
}

export interface AccountIdentity {
  apiKey: string;
  userId: string;
  username: string;
  keyLabel: string | null;
}

// --- Environment validation (exported for testing) ---

export function validateEnv(env: Record<string, string | undefined>): EnvConfig {
  const apiUrl = env.BATTLEGRID_API_URL || DEFAULT_URL;

  // BATTLEGRID_API_KEYS (comma-separated) takes precedence
  const keysRaw = env.BATTLEGRID_API_KEYS;
  let apiKeys: string[];

  if (keysRaw) {
    apiKeys = keysRaw.split(',').map(k => k.trim()).filter(Boolean);
  } else {
    const singleKey = env.BATTLEGRID_API_KEY;
    apiKeys = singleKey ? [singleKey] : [];
  }

  if (apiKeys.length === 0) {
    throw new Error(
      'BATTLEGRID_API_KEY or BATTLEGRID_API_KEYS environment variable is required.\n' +
      'Get your API key at: https://battlegrid.trade → Profile → MCP tab'
    );
  }

  for (const key of apiKeys) {
    if (!key.startsWith('bg_live_')) {
      throw new Error(
        `API key must start with "bg_live_" (got "${key.slice(0, 12)}...")\n` +
        'Create a new key at: https://battlegrid.trade → Profile → MCP tab'
      );
    }
  }

  return { apiKeys, apiUrl };
}

// --- Identity discovery (exported for testing) ---

export async function discoverIdentities(
  apiKeys: string[],
  apiUrl: string,
): Promise<AccountIdentity[]> {
  // Strip trailing slash for clean URL construction
  const baseUrl = apiUrl.replace(/\/+$/, '');

  const results = await Promise.allSettled(
    apiKeys.map(async (apiKey) => {
      const response = await fetch(`${baseUrl}/identity`, {
        headers: { Authorization: `Bearer ${apiKey}` },
      });
      if (!response.ok) {
        const text = await response.text().catch(() => '');
        throw new Error(`HTTP ${response.status}: ${text}`);
      }
      const data = await response.json() as { userId: string; username: string | null; keyLabel: string | null };
      return {
        apiKey,
        userId: data.userId,
        username: data.username ?? data.userId.slice(0, 8),
        keyLabel: data.keyLabel,
      } satisfies AccountIdentity;
    }),
  );

  const identities: AccountIdentity[] = [];
  for (let i = 0; i < results.length; i++) {
    const result = results[i];
    if (result.status === 'fulfilled') {
      identities.push(result.value);
    } else {
      const reason = result.reason instanceof Error ? result.reason.message : String(result.reason);
      const keyPrefix = apiKeys[i].substring(0, 12);
      process.stderr.write(
        `Warning: identity discovery failed for key #${i + 1} (${keyPrefix}): ${reason}\n`
      );
    }
  }

  if (identities.length === 0) {
    throw new Error(
      'No valid API keys — all identity lookups failed.\n' +
      'Check your keys at: https://battlegrid.trade → Profile → MCP tab'
    );
  }

  return identities;
}

// --- Connection with retry ---

function isAuthError(error: unknown): boolean {
  // Check error.code for StreamableHTTPError (MCP SDK stores HTTP status as .code)
  if (error && typeof error === 'object' && 'code' in error) {
    const code = (error as { code: unknown }).code;
    if (code === 401 || code === 403) return true;
  }
  const message = error instanceof Error ? error.message : String(error);
  return message.includes('401') || message.includes('Unauthorized') || message.includes('403');
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function connectWithRetry(client: Client, transport: StreamableHTTPClientTransport, apiUrl: string, apiKey: string): Promise<void> {
  const keyPrefix = apiKey.substring(0, 12);
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      await client.connect(transport);
      return;
    } catch (error) {
      // Log full error detail for diagnostics
      const errorCode = error && typeof error === 'object' && 'code' in error
        ? (error as { code: unknown }).code
        : undefined;
      const errorMessage = error instanceof Error ? error.message : String(error);

      if (isAuthError(error)) {
        throw new Error(
          `Authentication failed for key ${keyPrefix} (HTTP ${errorCode ?? 'unknown'}): ${errorMessage}\n` +
          'This means the server rejected your API key. Possible causes:\n' +
          '  1. Key was revoked (a new key invalidates all previous keys)\n' +
          '  2. Key was corrupted during copy-paste\n' +
          '  3. Environment variable contains extra whitespace or newline\n' +
          'Create a new key at: https://battlegrid.trade → Profile → MCP tab'
        );
      }

      if (attempt === MAX_RETRIES) {
        throw new Error(
          `Cannot connect to BattleGrid server at ${apiUrl} with key ${keyPrefix} after ` +
          `${MAX_RETRIES + 1} attempts.\n` +
          `Last error: ${errorMessage}\n` +
          `Check your internet connection or verify the server is running.\n` +
          `Health check: ${apiUrl.replace('/mcp', '')}/health`
        );
      }

      const delay = RETRY_DELAYS_MS[attempt];
      process.stderr.write(
        `Connection attempt ${attempt + 1} failed (${errorMessage}), retrying in ${delay / 1000}s...\n`
      );
      await sleep(delay);
    }
  }
}

// --- Multi-account tool augmentation ---

export interface ToolDefinition {
  name: string;
  description?: string;
  inputSchema: {
    type: string;
    properties?: Record<string, unknown>;
    required?: string[];
    [key: string]: unknown;
  };
}

/**
 * Add a required `account` enum to every discovered tool, as a sibling of the
 * existing top-level properties. For the strict authoring tools whose schema is
 * `{ request: canonicalPayload }`, this produces exactly `{ account, request }`
 * with `required: ["account", "request"]`; the server-owned root
 * `additionalProperties:false` and the entire nested `request` (unions,
 * required fields, bounds) are preserved by reference, never rewritten.
 */
export function injectAccountParam(tools: ToolDefinition[], accountNames: string[]): ToolDefinition[] {
  return tools.map(tool => ({
    ...tool,
    inputSchema: {
      ...tool.inputSchema,
      properties: {
        account: {
          type: 'string',
          enum: accountNames,
          description: `Which BattleGrid account to use for this action. Available: ${accountNames.join(', ')}`,
        },
        ...tool.inputSchema.properties,
      },
      required: ['account', ...(tool.inputSchema.required ?? [])],
    },
  }));
}

// --- Announced identity (exported for testing) ---

/**
 * The identity the local stdio server announces downstream: the upstream server's own, relayed
 * verbatim from the handshake that just completed.
 *
 * WHY RELAY RATHER THAN DECLARE. A local client reads this handshake as a statement about the
 * contract it is about to call. Announcing a constant compiled into this package makes that
 * statement on the server's behalf and then depends on a human keeping the two in step — which is
 * how the package sat at `11.0.0` against a deployed contract of `19.3.0` for ten days, how `5.1.0`
 * came to be declared in this repository and absent from the registry, and why four of the last five
 * releases were version bumps carrying no code change at all. Reading the number off the connection
 * that will actually serve the calls makes the pairing true by construction, on every connection,
 * with no release involved.
 *
 * VERBATIM, NOT RECONSTRUCTED. `Implementation` also carries optional display metadata (`title`,
 * `websiteUrl`, `icons`, …). Passing the object through means a field the server adds later reaches
 * local clients without an edit here — the same reason the tool catalog is never enumerated.
 *
 * FAILS CLOSED. `serverInfo` is required in a successful MCP `initialize` result, so a connected
 * client holding none is a protocol violation rather than a case to design around. Falling back to
 * PACKAGE_VERSION here would reintroduce the exact fiction this function exists to remove, and would
 * do it silently, at the one moment the truth was unavailable.
 */
export function announcedIdentityOf(serverInfo: Implementation | undefined): Implementation {
  if (serverInfo === undefined) {
    throw new Error(
      'Upstream MCP server completed initialize without announcing serverInfo, so there is no ' +
      'contract version to relay to local clients. This is a protocol violation by the server — ' +
      'not a configuration problem, and not something this proxy will substitute a guess for.'
    );
  }
  return serverInfo;
}

// --- Proxy server factory (exported for protocol testing) ---

export interface CreateProxyServerOptions {
  /**
   * The operator's FIRST configured key — used for the announcing handshake, the prompt and
   * resource surfaces, and single-account routing. Deliberately not derived from whichever
   * identity lookups happened to succeed: that made a mistyped first key silently promote the
   * second, relocating every unqualified call to a different account.
   */
  primaryKey: string;
  /**
   * Whether a tool call must name an account. Derived from the CONFIGURED key count, so the guard
   * is armed before any network call. Deriving it from resolved identities would let a transient
   * identity failure convert a multi-account proxy into a single-account one and route an
   * unqualified money-moving call to the primary.
   */
  isMultiAccount: boolean;
  /** Connect (or reuse) a remote MCP client for a given API key. */
  connect: (apiKey: string) => Promise<Client>;
  /** Resolve account identities. Awaited lazily, on the first request that needs the catalog. */
  resolveIdentities: () => Promise<AccountIdentity[]>;
}

/**
 * Everything the catalog resolution produces, resolved together as one shared value.
 *
 * The account selector published on every tool schema and the membership check applied to an
 * incoming call are one rule at two altitudes, so `accountNames` and `keyByAccount` are members
 * here rather than re-derived at each handler.
 */
export interface ProxyCatalog {
  identities: AccountIdentity[];
  accountNames: string[];
  keyByAccount: Map<string, string>;
  tools: ToolDefinition[];
  prompts: Prompt[];
  resources: Resource[];
}

/**
 * What a completed warm-up reports back to `main()`, which owns every startup diagnostic.
 *
 * Carries `accountNames` as well as the counts because the account-roster line is the only surface
 * naming which accounts actually resolved — the signal a dangling primary or a silent single-account
 * collapse would otherwise hide.
 */
export interface WarmSummary {
  accountNames: string[];
  toolCount: number;
  promptCount: number;
  resourceCount: number;
}

export interface ProxyServer {
  server: Server;
  /** The upstream identity relayed downstream — the contract a local client will actually reach. */
  announced: Implementation;
  /**
   * Resolve the catalog, returning its counts. Returns the SAME memoized resolution a request
   * triggers — it starts nothing of its own, so warm-up and a first request never resolve twice.
   */
  warm: () => Promise<WarmSummary>;
}

/**
 * Build the local stdio-facing MCP server that proxies to the remote BattleGrid server.
 *
 * ORDERING IS THE POINT. Exactly one upstream operation happens here: the handshake that yields the
 * identity this proxy relays. `serverInfo` is captured by the SDK at `Server` construction and read
 * when `initialize` is answered, with no setter, so relaying the upstream's identity verbatim makes
 * one round trip inherent. Everything else — identity discovery and the three catalog calls —
 * resolves lazily, after the caller has bound the transport, because none of it is needed to answer
 * `initialize` and every unit of work placed ahead of the bind is paid by every client on every
 * start.
 */
export async function createProxyServer(options: CreateProxyServerOptions): Promise<ProxyServer> {
  const { primaryKey, isMultiAccount, connect, resolveIdentities } = options;

  // The one retained pre-bind round trip.
  const primaryClient = await connect(primaryKey);

  // What this proxy announces downstream is what the upstream just announced to it — read here,
  // from the completed handshake, so it can never be a stale constant.
  const announced = announcedIdentityOf(primaryClient.getServerVersion());

  // `listChanged` is declared HERE and can never be added later: registerCapabilities throws once a
  // transport is connected, and a client only registers list-changed handlers for capabilities the
  // server advertised. Without it, a client whose first tools/list failed holds an empty catalog for
  // the life of the process — the symptom this lazy catalog exists to remove, made silent.
  const localServer = new Server(
    announced,
    {
      capabilities: {
        tools: { listChanged: true },
        prompts: { listChanged: true },
        resources: { listChanged: true },
      },
    }
  );

  // Pool of PROMISES, not clients: concurrent callers for one key share one in-flight connect
  // rather than each building a transport that is never closed. A rejection is removed so the next
  // caller retries.
  const clientPool = new Map<string, Promise<Client>>();
  clientPool.set(primaryKey, Promise.resolve(primaryClient));

  function getClientForKey(apiKey: string): Promise<Client> {
    const existing = clientPool.get(apiKey);
    if (existing) return existing;

    const pending = connect(apiKey);
    clientPool.set(apiKey, pending);
    pending.catch(() => {
      if (clientPool.get(apiKey) === pending) clientPool.delete(apiKey);
    });
    return pending;
  }

  let catalogMemo: Promise<ProxyCatalog> | null = null;
  let servedCatalogError = false;

  async function announceListsChanged(): Promise<void> {
    try {
      await Promise.all([
        localServer.sendToolListChanged(),
        localServer.sendPromptListChanged(),
        localServer.sendResourceListChanged(),
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      process.stderr.write(`Warning: could not notify client that the catalog recovered: ${message}\n`);
    }
  }

  async function buildCatalog(): Promise<ProxyCatalog> {
    const identities = await resolveIdentities();

    // The declared primary must be in the resolved roster. Identity discovery is a single unretried
    // request while the handshake retries three times, so a primary can complete the handshake and
    // still be missing here — which would serve prompts and resources as an account that appears in
    // no selector and no log line.
    if (!identities.some((identity) => identity.apiKey === primaryKey)) {
      throw new Error(
        `Primary key (${primaryKey.substring(0, 12)}) is absent from the resolved account roster, ` +
        'so every call routed to it would execute as an account this proxy never resolved.'
      );
    }

    const accountNames = identities.map((identity) => identity.username);
    const keyByAccount = new Map<string, string>();
    for (const identity of identities) {
      if (keyByAccount.has(identity.username)) {
        throw new Error(
          `Two configured accounts resolved to the display name "${identity.username}", so an ` +
          'account selection cannot name one of them unambiguously.'
        );
      }
      keyByAccount.set(identity.username, identity.apiKey);
    }

    const [toolsResult, promptsResult, resourcesResult] = await Promise.all([
      primaryClient.listTools(),
      primaryClient.listPrompts(),
      primaryClient.listResources(),
    ]);

    const discovered = toolsResult.tools as ToolDefinition[];

    return {
      identities,
      accountNames,
      keyByAccount,
      tools: isMultiAccount ? injectAccountParam(discovered, accountNames) : discovered,
      prompts: promptsResult.prompts,
      resources: resourcesResult.resources,
    };
  }

  /**
   * The catalog, resolved at most once and shared by every caller.
   *
   * The clear-on-failure is identity-guarded deliberately. The obvious shape — an async IIFE whose
   * inner catch nulls the memo — poisons it permanently when the body throws before its first
   * `await`: that catch runs during the synchronous prefix and the outer assignment then
   * re-installs the rejected promise. Guarding on identity is correct for both timings and also
   * cannot discard a newer resolution another request installed.
   */
  function resolveCatalog(): Promise<ProxyCatalog> {
    const existing = catalogMemo;
    if (existing) return existing;

    const pending = buildCatalog();
    catalogMemo = pending;

    pending.catch(() => {
      if (catalogMemo === pending) catalogMemo = null;
    });

    void pending.then(
      () => {
        if (!servedCatalogError) return;
        servedCatalogError = false;
        void announceListsChanged();
      },
      () => undefined,
    );

    return pending;
  }

  /** Resolve the catalog, remembering that a failure was served so a later recovery can be announced. */
  async function catalogOrThrow(): Promise<ProxyCatalog> {
    try {
      return await resolveCatalog();
    } catch (error) {
      servedCatalogError = true;
      throw error;
    }
  }

  // --- Proxy: tools ---

  // Throws on rejection: ListToolsResult carries only `tools`, so the tools/call in-band
  // `{content, isError}` shape would ship as a SUCCESSFUL result that fails the client's own parse.
  // The SDK maps a thrown handler error to a proper JSON-RPC error.
  localServer.setRequestHandler(ListToolsRequestSchema, async () => {
    const catalog = await catalogOrThrow();
    return { tools: catalog.tools };
  });

  localServer.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
      let targetKey = primaryKey;
      const args = { ...request.params.arguments } as Record<string, unknown>;

      // Read from the constructor option, never from the catalog: the guard must be armed even
      // while the account set is still unknown.
      if (isMultiAccount) {
        const { keyByAccount, accountNames } = await catalogOrThrow();
        const selectedAccount = args.account as string | undefined;
        if (!selectedAccount || !keyByAccount.has(selectedAccount)) {
          return {
            content: [{
              type: 'text' as const,
              text: `Error: "account" parameter is required. Choose one of: ${accountNames.join(', ')}`,
            }],
            isError: true,
          };
        }
        targetKey = keyByAccount.get(selectedAccount)!;
        delete args.account; // Strip ONLY account before forwarding; request is forwarded unchanged
      }

      const client = await getClientForKey(targetKey);
      return await client.callTool({
        name: request.params.name,
        arguments: args,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: 'text' as const, text: `Error: ${message}` }],
        isError: true,
      };
    }
  });

  // --- Proxy: prompts ---

  localServer.setRequestHandler(ListPromptsRequestSchema, async () => {
    const catalog = await catalogOrThrow();
    return { prompts: catalog.prompts };
  });

  localServer.setRequestHandler(GetPromptRequestSchema, async (request) => {
    return await primaryClient.getPrompt({
      name: request.params.name,
      arguments: request.params.arguments,
    });
  });

  // --- Proxy: resources ---

  localServer.setRequestHandler(ListResourcesRequestSchema, async () => {
    const catalog = await catalogOrThrow();
    return { resources: catalog.resources };
  });

  localServer.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    return await primaryClient.readResource({
      uri: request.params.uri,
    });
  });

  return {
    server: localServer,
    announced,
    warm: async (): Promise<WarmSummary> => {
      const catalog = await resolveCatalog();
      return {
        accountNames: catalog.accountNames,
        toolCount: catalog.tools.length,
        promptCount: catalog.prompts.length,
        resourceCount: catalog.resources.length,
      };
    },
  };
}

// --- Main ---

async function main(): Promise<void> {
  let config: EnvConfig;
  try {
    config = validateEnv(process.env);
  } catch (error) {
    process.stderr.write(`Error: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  }

  // Log key diagnostics for cross-referencing with server logs
  for (let i = 0; i < config.apiKeys.length; i++) {
    const key = config.apiKeys[i];
    const hashPrefix = createHash('sha256').update(key).digest('hex').substring(0, 16);
    process.stderr.write(
      `BattleGrid MCP: Key #${i + 1} prefix=${key.substring(0, 12)} hashPrefix=${hashPrefix} len=${key.length}\n`
    );
  }

  // Connect a remote MCP client for a given API key, with retry + auth diagnostics.
  const connect = async (apiKey: string): Promise<Client> => {
    const transport = new StreamableHTTPClientTransport(
      new URL(config.apiUrl),
      { requestInit: { headers: { Authorization: `Bearer ${apiKey}` } } }
    );
    // Upstream is told which proxy build is calling — the one question PACKAGE_VERSION answers.
    const client = new Client(
      { name: 'battlegrid-proxy', version: PACKAGE_VERSION },
      { capabilities: {} }
    );
    await connectWithRetry(client, transport, config.apiUrl, apiKey);
    return client;
  };

  let proxy: ProxyServer;
  try {
    proxy = await createProxyServer({
      // The operator's declared first key, chosen before discovery so an unreachable one fails
      // loudly here instead of silently promoting the second.
      primaryKey: config.apiKeys[0],
      // Armed by configuration, so a later identity failure cannot stand the account guard down.
      isMultiAccount: config.apiKeys.length > 1,
      connect,
      resolveIdentities: () => discoverIdentities(config.apiKeys, config.apiUrl),
    });
  } catch (error) {
    process.stderr.write(`Error: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  }

  // Both numbers, labelled. They describe different things and are EXPECTED to differ — printing
  // only one leaves an operator to guess which, and printing neither is how the last drift went
  // unnoticed for ten days.
  process.stderr.write(
    `BattleGrid MCP: announcing ${proxy.announced.name}@${proxy.announced.version} ` +
    `(server contract, read from the upstream handshake) — proxy ${PACKAGE_VERSION}\n`
  );

  // --- Start stdio transport, BEFORE any catalog work ---
  //
  // Everything above is the single upstream handshake the relayed serverInfo requires. From here the
  // process answers `initialize`; identity discovery and the three catalog calls happen behind it.

  const stdioTransport = new StdioServerTransport();
  await proxy.server.connect(stdioTransport);

  process.stderr.write('BattleGrid MCP server running on stdio\n');

  // Warm the catalog so the first tools/list joins an in-flight resolution rather than starting one.
  // Deliberately NOT awaited, and the rejection handler is the whole of the guarantee that a
  // background failure cannot kill a process that has already answered `initialize`. The failure is
  // reported and absorbed; the next request that needs the catalog retries it.
  void proxy.warm().then(
    (summary) => {
      process.stderr.write(
        `BattleGrid MCP: ${summary.accountNames.length} account(s) discovered — ${summary.accountNames.join(', ')}\n`
      );
      process.stderr.write(
        `BattleGrid MCP: ${summary.toolCount} tools, ${summary.promptCount} prompts, ${summary.resourceCount} resources\n`
      );
    },
    (error: unknown) => {
      const message = error instanceof Error ? error.message : String(error);
      process.stderr.write(
        `Warning: catalog warm-up failed (${message}). The proxy is connected; the next request ` +
        'that needs the catalog will retry it.\n'
      );
    },
  );
}


// Only run when executed directly (not when imported for testing)
const isDirectExecution = process.argv[1] &&
  (process.argv[1].endsWith('/index.js') || process.argv[1].endsWith('/battlegrid-mcp'));

if (isDirectExecution) {
  main().catch((error) => {
    process.stderr.write(`Fatal error: ${error}\n`);
    process.exit(1);
  });
}
