/**
 * Protocol harness for the strict strategy-authoring proxy contract.
 *
 * These tests drive `tools/list` and `tools/call` over a real in-memory MCP
 * transport pair (client ⇄ proxy Server), with a faithful fake upstream in
 * place of the remote BattleGrid server. They prove — at the protocol level,
 * not via helper-function unit tests — that the proxy:
 *
 *   - publishes the four authoring tools as exactly `{ account, request }` in
 *     multi-account mode, preserving the server-owned nested `request`
 *     (unions, discriminators, required fields, bounds, additionalProperties);
 *   - publishes the server-native `{ request }` unchanged in single-account mode;
 *   - strips ONLY the outer `account` on a call and forwards the unchanged
 *     `{ request }` with the routed Bearer token;
 *   - covers CREATE, UPDATE, and RESTORE compile branches plus section-template,
 *     focused-rule-update, and apply;
 *   - never reconstructs flat legacy payloads into the envelope;
 *   - does not expose or reintroduce the retired `create_strategy` operation;
 *   - preserves structured content and JSON-text results consistently.
 */

import { describe, it, expect } from 'vitest';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { createProxyServer, type AccountIdentity } from '../index.js';

// --- Canonical server-owned schemas (mirror of the live authoring contract) ---

type JsonSchema = Record<string, unknown>;

const COIN_SELECTION_SCHEMA: JsonSchema = {
  oneOf: [
    {
      type: 'object',
      properties: {
        mode: { const: 'ranked' },
        limit: { type: 'integer', minimum: 1, maximum: 20 },
      },
      required: ['mode', 'limit'],
      additionalProperties: false,
    },
    {
      type: 'object',
      properties: {
        mode: { const: 'explicit' },
        tickers: { type: 'array', items: { type: 'string' }, minItems: 1, maxItems: 30 },
      },
      required: ['mode', 'tickers'],
      additionalProperties: false,
    },
  ],
};

const AUTHORING_CONTEXT_PROPS: JsonSchema = {
  intentSummary: { type: 'string', minLength: 1, maxLength: 2000 },
  assumptions: { type: 'array', items: { type: 'string' } },
  coinSelection: COIN_SELECTION_SCHEMA,
};

// compile_strategy_plan request — strict CREATE / UPDATE / RESTORE discriminated union.
const COMPILE_REQUEST_SCHEMA: JsonSchema = {
  oneOf: [
    {
      type: 'object',
      properties: {
        operation: { const: 'CREATE' },
        ...AUTHORING_CONTEXT_PROPS,
        name: { type: 'string', minLength: 1, maxLength: 50 },
        description: { type: 'string', maxLength: 500 },
        timeframe: { type: 'string' },
        regimeAutoDerive: { type: 'boolean' },
        sections: { type: 'array' },
      },
      required: [
        'operation', 'intentSummary', 'assumptions', 'coinSelection',
        'name', 'timeframe', 'regimeAutoDerive', 'sections',
      ],
      additionalProperties: false,
    },
    {
      type: 'object',
      properties: {
        operation: { const: 'UPDATE' },
        ...AUTHORING_CONTEXT_PROPS,
        strategyId: { type: 'string', format: 'uuid' },
        expectedRevision: { type: 'integer', minimum: 1 },
        rules: { type: 'array' },
      },
      required: [
        'operation', 'intentSummary', 'assumptions', 'coinSelection',
        'strategyId', 'expectedRevision',
      ],
      additionalProperties: false,
    },
    {
      type: 'object',
      properties: {
        operation: { const: 'RESTORE' },
        ...AUTHORING_CONTEXT_PROPS,
        strategyId: { type: 'string', format: 'uuid' },
        expectedRevision: { type: 'integer', minimum: 1 },
      },
      required: [
        'operation', 'intentSummary', 'assumptions', 'coinSelection',
        'strategyId', 'expectedRevision',
      ],
      additionalProperties: false,
    },
  ],
};

// get_strategy_section_template request — platform / custom discriminated union.
const TEMPLATE_REQUEST_SCHEMA: JsonSchema = {
  oneOf: [
    {
      type: 'object',
      properties: { kind: { const: 'platform' }, sectionKey: { type: 'string' } },
      required: ['kind', 'sectionKey'],
      additionalProperties: false,
    },
    {
      type: 'object',
      properties: { kind: { const: 'custom' }, templateKey: { type: 'string', minLength: 1 } },
      required: ['kind', 'templateKey'],
      additionalProperties: false,
    },
  ],
};

// update_strategy_signal_rule request — one focused rule edit.
const RULE_UPDATE_REQUEST_SCHEMA: JsonSchema = {
  type: 'object',
  properties: {
    strategyId: { type: 'string', format: 'uuid' },
    expectedRevision: { type: 'integer', minimum: 1 },
    signalId: { type: 'string' },
    allocation: { type: 'integer', minimum: 0, maximum: 3 },
    required: { type: 'boolean' },
    params: { type: 'object' },
  },
  required: ['strategyId', 'expectedRevision', 'signalId', 'allocation', 'required'],
  additionalProperties: false,
};

// apply_strategy_plan request — the credential-bound token and the confirmation, nothing else.
// The server holds the plan its own compile approved and reads it back (contract 33.0.0), so this
// fixture carries no plan member; `additionalProperties: false` is what rejects one upstream.
const APPLY_REQUEST_SCHEMA: JsonSchema = {
  type: 'object',
  properties: {
    planToken: { type: 'string', minLength: 1, maxLength: 4096 },
    confirm: { const: true },
  },
  required: ['planToken', 'confirm'],
  additionalProperties: false,
};

/** Strict server publication envelope: `{ request: canonicalPayload }`. */
function requestEnvelope(request: JsonSchema): JsonSchema {
  return {
    type: 'object',
    properties: { request },
    required: ['request'],
    additionalProperties: false,
  };
}

// Flat (non-enveloped) tools also present in the live surface.
const LIST_STRATEGIES_SCHEMA: JsonSchema = {
  type: 'object',
  properties: { includeInactive: { type: 'boolean' } },
  additionalProperties: false,
};

const GET_ACCOUNT_STATE_SCHEMA: JsonSchema = {
  type: 'object',
  properties: {},
  additionalProperties: false,
};

const ENVELOPE_TOOL_NAMES = [
  'get_strategy_section_template',
  'update_strategy_signal_rule',
  'compile_strategy_plan',
  'apply_strategy_plan',
] as const;

const ENVELOPE_SCHEMAS: Record<string, JsonSchema> = {
  get_strategy_section_template: TEMPLATE_REQUEST_SCHEMA,
  update_strategy_signal_rule: RULE_UPDATE_REQUEST_SCHEMA,
  compile_strategy_plan: COMPILE_REQUEST_SCHEMA,
  apply_strategy_plan: APPLY_REQUEST_SCHEMA,
};

interface ToolShape {
  name: string;
  description: string;
  inputSchema: JsonSchema;
}

const SERVER_TOOLS: ToolShape[] = [
  { name: 'list_strategies', description: 'List strategies.', inputSchema: LIST_STRATEGIES_SCHEMA },
  { name: 'get_account_state', description: 'Get account state.', inputSchema: GET_ACCOUNT_STATE_SCHEMA },
  { name: 'get_strategy_section_template', description: 'Get one section template.', inputSchema: requestEnvelope(TEMPLATE_REQUEST_SCHEMA) },
  { name: 'update_strategy_signal_rule', description: 'Update one signal rule.', inputSchema: requestEnvelope(RULE_UPDATE_REQUEST_SCHEMA) },
  { name: 'compile_strategy_plan', description: 'Compile a CREATE/UPDATE/RESTORE plan.', inputSchema: requestEnvelope(COMPILE_REQUEST_SCHEMA) },
  { name: 'apply_strategy_plan', description: 'Apply an approved plan.', inputSchema: requestEnvelope(APPLY_REQUEST_SCHEMA) },
];

const SERVER_PROMPTS = [
  { name: 'author-strategy', description: 'Compile → review → apply a strategy plan.' },
  { name: 'play-market-grid', description: 'Play a Market Grid game.' },
];

const SERVER_RESOURCES = [
  { uri: 'battlegrid://guide/quick-start', name: 'Quick Start', mimeType: 'text/markdown' },
];

const KNOWN_TOOL_NAMES = new Set(SERVER_TOOLS.map(t => t.name));
const ENVELOPE_TOOL_SET = new Set<string>(ENVELOPE_TOOL_NAMES);

// Retired operations that must never appear in discovery or be reintroduced.
const RETIRED_TOOLS = [
  'create_strategy',
  'update_strategy',
  'repair_strategy',
  'get_rule_suggestions',
  'apply_rule_suggestions',
];

// --- Request payload fixtures (client-side call arguments) ---

const STRATEGY_ID = '11111111-2222-4333-8444-555555555555';

const CREATE_REQUEST = {
  operation: 'CREATE',
  intentSummary: 'Author a momentum strategy.',
  assumptions: ['Use canonical RSI context.'],
  coinSelection: { mode: 'explicit', tickers: ['BTC'] },
  name: 'Protocol momentum',
  description: 'Compiled through the live MCP dispatcher.',
  timeframe: '1h',
  regimeAutoDerive: true,
  sections: [{ kind: 'platform', sectionKey: 'includeRsi' }],
} as const;

const UPDATE_REQUEST = {
  operation: 'UPDATE',
  intentSummary: 'Raise one RSI allocation.',
  assumptions: [],
  coinSelection: { mode: 'explicit', tickers: ['BTC'] },
  strategyId: STRATEGY_ID,
  expectedRevision: 7,
  rules: [{ signalId: 'RSI_OVERSOLD', allocation: 3, required: false }],
} as const;

const RESTORE_REQUEST = {
  operation: 'RESTORE',
  intentSummary: 'Restore the viable inactive revision.',
  assumptions: [],
  coinSelection: { mode: 'explicit', tickers: ['BTC'] },
  strategyId: STRATEGY_ID,
  expectedRevision: 7,
} as const;

const TEMPLATE_REQUEST = { kind: 'platform', sectionKey: 'includeRsi' } as const;

const RULE_UPDATE_REQUEST = {
  strategyId: STRATEGY_ID,
  expectedRevision: 1,
  signalId: 'RSI_OVERSOLD',
  allocation: 2,
  required: false,
} as const;

const APPLY_REQUEST = {
  planToken: 'plan_tok_abcdef',
  confirm: true,
} as const;

// --- Fake upstream ---

interface RecordedCall {
  apiKey: string;
  kind: 'tool' | 'prompt' | 'resource';
  name?: string;
  uri?: string;
  arguments?: Record<string, unknown>;
}

interface ToolResult {
  content: { type: 'text'; text: string }[];
  structuredContent?: Record<string, unknown>;
  isError?: boolean;
}

function makeUpstream(apiKey: string, calls: RecordedCall[]): Client {
  const upstream = {
    // What the real SDK returns once `initialize` has completed. The proxy relays it downstream
    // instead of announcing a constant of its own, so a fake upstream has to answer it.
    getServerVersion() {
      return { name: 'battlegrid', version: '19.3.0' };
    },
    async listTools() {
      return { tools: structuredClone(SERVER_TOOLS) };
    },
    async listPrompts() {
      return { prompts: structuredClone(SERVER_PROMPTS) };
    },
    async listResources() {
      return { resources: structuredClone(SERVER_RESOURCES) };
    },
    async callTool(params: { name: string; arguments?: Record<string, unknown> }): Promise<ToolResult> {
      calls.push({ apiKey, kind: 'tool', name: params.name, arguments: params.arguments });

      // Unknown / retired operation → server rejects as an unavailable method.
      if (!KNOWN_TOOL_NAMES.has(params.name)) {
        throw new Error(`MCP error -32601: Method not found: ${params.name}`);
      }

      // Enveloped tools enforce a closed-world `{ request }` root. A flat legacy
      // payload (or extra root keys) fails validation — the server never
      // reconstructs it, so neither can the proxy.
      if (ENVELOPE_TOOL_SET.has(params.name)) {
        const args = params.arguments ?? {};
        const keys = Object.keys(args);
        const strictRequestOnly = keys.length === 1 && keys[0] === 'request' && args.request !== undefined;
        if (!strictRequestOnly) {
          return {
            content: [{ type: 'text', text: JSON.stringify({ code: 'VALIDATION_ERROR', message: 'closed-world root: exactly { request } required' }) }],
            isError: true,
          };
        }
      }

      return {
        content: [{ type: 'text', text: `RESULT_TEXT:${params.name}` }],
        structuredContent: { tool: params.name, marker: 'structured-ok', echoed: params.arguments ?? null },
        isError: false,
      };
    },
    async getPrompt(params: { name: string; arguments?: Record<string, string> }) {
      calls.push({ apiKey, kind: 'prompt', name: params.name, arguments: params.arguments });
      return {
        description: `prompt:${params.name}`,
        messages: [{ role: 'user', content: { type: 'text', text: `PROMPT:${params.name}` } }],
      };
    },
    async readResource(params: { uri: string }) {
      calls.push({ apiKey, kind: 'resource', uri: params.uri });
      return { contents: [{ uri: params.uri, mimeType: 'text/plain', text: `RESOURCE:${params.uri}` }] };
    },
  };
  return upstream as unknown as Client;
}

// --- Harness ---

interface Harness {
  client: Client;
  calls: RecordedCall[];
}

function identitiesFor(usernames: string[]): AccountIdentity[] {
  return usernames.map((username, i) => ({
    apiKey: `bg_live_${username}`,
    userId: `user-${i}`,
    username,
    keyLabel: null,
  }));
}

async function setup(usernames: string[]): Promise<Harness> {
  const calls: RecordedCall[] = [];
  const identities = identitiesFor(usernames);
  const connect = async (apiKey: string): Promise<Client> => makeUpstream(apiKey, calls);

  const proxy = await createProxyServer({
    primaryKey: identities[0].apiKey,
    // The CONFIGURED count — the path under test. Deriving this from resolved identities is the
    // defect the guard exists to prevent, so the harness must not reintroduce it.
    isMultiAccount: usernames.length > 1,
    connect,
    resolveIdentities: async () => identities,
  });

  const client = new Client({ name: 'proxy-protocol-test', version: '1.0.0' });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([
    proxy.server.connect(serverTransport),
    client.connect(clientTransport),
  ]);

  return { client, calls };
}

async function toolMap(client: Client): Promise<Map<string, { name: string; inputSchema: JsonSchema }>> {
  const listed = await client.listTools();
  return new Map(listed.tools.map(t => [t.name, t as unknown as { name: string; inputSchema: JsonSchema }]));
}

// --- Tests ---

describe('multi-account discovery — strict { account, request }', () => {
  it('publishes each authoring tool as exactly { account, request } with the nested request preserved', async () => {
    const { client } = await setup(['alice', 'bob']);
    const tools = await toolMap(client);

    for (const name of ENVELOPE_TOOL_NAMES) {
      const tool = tools.get(name);
      expect(tool, `missing authoring tool ${name}`).toBeDefined();
      const schema = tool!.inputSchema;
      const properties = schema.properties as Record<string, JsonSchema>;

      // Root shape: exactly { account, request }, both required, closed world.
      expect(schema.type).toBe('object');
      expect(Object.keys(properties)).toEqual(['account', 'request']);
      expect(schema.required).toEqual(['account', 'request']);
      expect(schema.additionalProperties).toBe(false);

      // account is the only addition — a plain string enum of usernames.
      const account = properties.account as Record<string, unknown>;
      expect(account.type).toBe('string');
      expect(account.enum).toEqual(['alice', 'bob']);
      expect(typeof account.description).toBe('string');

      // The nested request is byte-for-byte the server-owned payload.
      expect(properties.request).toEqual(ENVELOPE_SCHEMAS[name]);
    }
  });

  it('preserves the compile discriminator union (CREATE/UPDATE/RESTORE) unchanged inside request', async () => {
    const { client } = await setup(['alice', 'bob']);
    const tools = await toolMap(client);
    const request = (tools.get('compile_strategy_plan')!.inputSchema.properties as Record<string, JsonSchema>).request;

    const branches = request.oneOf as JsonSchema[];
    expect(branches).toHaveLength(3);
    const operations = branches.map(b => ((b.properties as Record<string, JsonSchema>).operation as JsonSchema).const);
    expect(operations).toEqual(['CREATE', 'UPDATE', 'RESTORE']);
    for (const branch of branches) {
      expect(branch.additionalProperties).toBe(false);
      expect(Array.isArray(branch.required)).toBe(true);
    }
    // A representative nested bound survives untouched.
    const updateBranch = branches[1];
    expect(((updateBranch.properties as Record<string, JsonSchema>).expectedRevision as JsonSchema).minimum).toBe(1);
  });

  it('injects account as the sole addition on flat (non-enveloped) tools too', async () => {
    const { client } = await setup(['alice', 'bob']);
    const tools = await toolMap(client);

    const listStrategies = tools.get('list_strategies')!.inputSchema;
    expect(Object.keys(listStrategies.properties as Record<string, unknown>)).toEqual(['account', 'includeInactive']);
    expect(listStrategies.required).toEqual(['account']);

    const getAccountState = tools.get('get_account_state')!.inputSchema;
    expect(Object.keys(getAccountState.properties as Record<string, unknown>)).toEqual(['account']);
    expect(getAccountState.required).toEqual(['account']);
  });

  it('omits the retired create_strategy operation and every other retired tool from discovery', async () => {
    const { client } = await setup(['alice', 'bob']);
    const tools = await toolMap(client);
    for (const retired of RETIRED_TOOLS) {
      expect(tools.has(retired), `retired tool ${retired} must be absent`).toBe(false);
    }
  });
});

describe('single-account discovery — server-native { request }', () => {
  it('publishes the authoring tools with the strict { request } schema and no account field', async () => {
    const { client } = await setup(['solo']);
    const tools = await toolMap(client);

    for (const name of ENVELOPE_TOOL_NAMES) {
      const schema = tools.get(name)!.inputSchema;
      expect(Object.keys(schema.properties as Record<string, unknown>)).toEqual(['request']);
      expect(schema.required).toEqual(['request']);
      expect(schema.additionalProperties).toBe(false);
      expect((schema.properties as Record<string, JsonSchema>).request).toEqual(ENVELOPE_SCHEMAS[name]);
    }

    // Flat tools are passed through unchanged as well.
    expect(tools.get('list_strategies')!.inputSchema).toEqual(LIST_STRATEGIES_SCHEMA);
  });
});

describe('exact forwarding — strip only account, forward unchanged { request }', () => {
  const cases: { tool: string; request: Record<string, unknown> }[] = [
    { tool: 'compile_strategy_plan', request: { ...CREATE_REQUEST } },
    { tool: 'compile_strategy_plan', request: { ...UPDATE_REQUEST } },
    { tool: 'compile_strategy_plan', request: { ...RESTORE_REQUEST } },
    { tool: 'get_strategy_section_template', request: { ...TEMPLATE_REQUEST } },
    { tool: 'update_strategy_signal_rule', request: { ...RULE_UPDATE_REQUEST } },
    { tool: 'apply_strategy_plan', request: { ...APPLY_REQUEST } },
  ];

  for (const { tool, request } of cases) {
    const label = 'operation' in request ? `${tool} (${request.operation})` : tool;
    it(`routes ${label} to the selected account and forwards { request } verbatim`, async () => {
      const { client, calls } = await setup(['alice', 'bob']);

      const result = await client.callTool({ name: tool, arguments: { account: 'bob', request } });

      // Exactly one upstream call, routed to bob's key.
      expect(calls).toHaveLength(1);
      expect(calls[0]).toMatchObject({ apiKey: 'bg_live_bob', kind: 'tool', name: tool });
      // Account consumed; request forwarded unchanged (no unwrap, no reshape).
      expect(calls[0].arguments).toEqual({ request });
      expect(calls[0].arguments).not.toHaveProperty('account');

      // Structured + text results are preserved consistently.
      expect(result.isError).toBeFalsy();
      expect(result.content).toEqual([{ type: 'text', text: `RESULT_TEXT:${tool}` }]);
      expect(result.structuredContent).toEqual({ tool, marker: 'structured-ok', echoed: { request } });
    });
  }

  it('routes to the primary account when it is selected', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    await client.callTool({ name: 'compile_strategy_plan', arguments: { account: 'alice', request: { ...CREATE_REQUEST } } });
    expect(calls).toHaveLength(1);
    expect(calls[0].apiKey).toBe('bg_live_alice');
    expect(calls[0].arguments).toEqual({ request: { ...CREATE_REQUEST } });
  });

  it('rejects a missing account without contacting the upstream server', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    const result = await client.callTool({ name: 'compile_strategy_plan', arguments: { request: { ...CREATE_REQUEST } } });
    expect(result.isError).toBe(true);
    expect(calls).toHaveLength(0);
  });

  it('rejects an unknown account without contacting the upstream server', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    const result = await client.callTool({ name: 'compile_strategy_plan', arguments: { account: 'carol', request: { ...CREATE_REQUEST } } });
    expect(result.isError).toBe(true);
    expect(calls).toHaveLength(0);
  });
});

describe('single-account forwarding', () => {
  it('forwards the server-native { request } with no account field', async () => {
    const { client, calls } = await setup(['solo']);
    const result = await client.callTool({ name: 'compile_strategy_plan', arguments: { request: { ...CREATE_REQUEST } } });

    expect(calls).toHaveLength(1);
    expect(calls[0].apiKey).toBe('bg_live_solo');
    expect(calls[0].arguments).toEqual({ request: { ...CREATE_REQUEST } });
    expect(result.structuredContent).toMatchObject({ tool: 'compile_strategy_plan', marker: 'structured-ok' });
  });
});

describe('no reconstruction of flat legacy payloads', () => {
  it('forwards a flat legacy compile payload verbatim and lets the server reject it', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    // A client that still sends the retired flat shape (no { request } wrapper).
    const legacyFlat = { account: 'alice', operation: 'CREATE', name: 'Legacy', timeframe: '1h' };
    const result = await client.callTool({ name: 'compile_strategy_plan', arguments: legacyFlat });

    // Proxy stripped only account; it did NOT wrap the rest into { request }.
    expect(calls).toHaveLength(1);
    expect(calls[0].arguments).toEqual({ operation: 'CREATE', name: 'Legacy', timeframe: '1h' });
    expect(calls[0].arguments).not.toHaveProperty('request');
    // Server enforces the closed-world root and rejects it.
    expect(result.isError).toBe(true);
  });

  it('surfaces retired create_strategy as an unavailable method — forwarded verbatim, never rebuilt', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    const result = await client.callTool({ name: 'create_strategy', arguments: { account: 'alice', name: 'Legacy', direction: 'UP' } });

    // Forwarded verbatim (account stripped only); no envelope reconstruction.
    expect(calls).toHaveLength(1);
    expect(calls[0].name).toBe('create_strategy');
    expect(calls[0].arguments).toEqual({ name: 'Legacy', direction: 'UP' });
    // Upstream rejects the unavailable method; proxy surfaces it as an error.
    expect(result.isError).toBe(true);
  });
});

describe('prompts and resources passthrough', () => {
  it('lists and reads prompts and resources through the primary account', async () => {
    const { client, calls } = await setup(['alice', 'bob']);

    const prompts = await client.listPrompts();
    expect(prompts.prompts.map(p => p.name)).toEqual(['author-strategy', 'play-market-grid']);

    const resources = await client.listResources();
    expect(resources.resources.map(r => r.uri)).toEqual(['battlegrid://guide/quick-start']);

    const prompt = await client.getPrompt({ name: 'author-strategy' });
    expect(prompt.description).toBe('prompt:author-strategy');

    const resource = await client.readResource({ uri: 'battlegrid://guide/quick-start' });
    expect(resource.contents[0].text).toBe('RESOURCE:battlegrid://guide/quick-start');

    // Prompt/resource proxying always uses the primary (first) account.
    for (const call of calls.filter(c => c.kind !== 'tool')) {
      expect(call.apiKey).toBe('bg_live_alice');
    }
  });
});
