/**
 * Protocol harness for the strict strategy-authoring proxy contract.
 *
 * These tests drive `tools/list` and `tools/call` over a real in-memory MCP
 * transport pair (client ⇄ proxy Server), with a faithful fake upstream in
 * place of the remote BattleGrid server. They prove — at the protocol level,
 * not via helper-function unit tests — that the proxy:
 *
 *   - publishes the enveloped authoring tools as exactly `{ account, request }` in
 *     multi-account mode, preserving the server-owned nested `request`
 *     (unions, discriminators, required fields, bounds, additionalProperties);
 *   - publishes the server-native `{ request }` unchanged in single-account mode;
 *   - strips ONLY the outer `account` on a call and forwards the unchanged
 *     `{ request }` with the routed Bearer token;
 *   - covers the strategy draft lifecycle — stage (into an existing strategy's draft
 *     and into a new create draft), get, commit, and discard — plus section-template;
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

const UUID_SCHEMA: JsonSchema = { type: 'string', format: 'uuid' };

// A strategy's ENTRY axis — a union discriminated by `trigger` (contract 85.0.0): the close trigger
// alone, or a level trigger with its two dials.
const ENTRY_AXIS_SCHEMA: JsonSchema = {
  type: 'object',
  properties: {
    entry: {
      anyOf: [
        {
          type: 'object',
          properties: { trigger: { type: 'string', const: 'ON_CANDLE_CLOSE' } },
          required: ['trigger'],
          additionalProperties: false,
        },
        {
          type: 'object',
          properties: {
            trigger: { type: 'string', enum: ['STOP_THROUGH_LEVEL', 'ON_RETEST'] },
            levelOffsetAtrMultiple: { type: 'number' },
            validForBars: { type: 'integer', minimum: 1 },
          },
          required: ['trigger', 'levelOffsetAtrMultiple', 'validForBars'],
          additionalProperties: false,
        },
      ],
    },
  },
  required: ['entry'],
  additionalProperties: false,
};

// stage_strategy_draft request — the version read, and the proposed axes, each optional.
const STAGE_REQUEST_SCHEMA: JsonSchema = {
  type: 'object',
  properties: {
    strategyId: UUID_SCHEMA,
    draftVersion: { type: 'integer', minimum: 0 },
    axes: {
      type: 'object',
      properties: {
        IDENTITY: {
          type: 'object',
          properties: {
            name: { type: 'string', minLength: 1, maxLength: 50 },
            description: { type: 'string', maxLength: 500 },
            tagline: { type: 'string', maxLength: 80 },
          },
          required: ['name', 'description', 'tagline'],
          additionalProperties: false,
        },
        TIMEFRAME_PROFILE: {
          type: 'object',
          properties: { timeframe: { type: 'string' } },
          required: ['timeframe'],
          additionalProperties: false,
        },
        REPORT: {
          type: 'object',
          properties: { sections: { type: 'array' } },
          required: ['sections'],
          additionalProperties: false,
        },
        ENTRY: ENTRY_AXIS_SCHEMA,
        SIGNAL_RULES: {
          type: 'object',
          properties: { rules: { type: 'array' } },
          required: ['rules'],
          additionalProperties: false,
        },
      },
      additionalProperties: false,
    },
  },
  required: ['draftVersion', 'axes'],
  additionalProperties: false,
};

// get_strategy_draft request — the id alone.
const GET_DRAFT_REQUEST_SCHEMA: JsonSchema = {
  type: 'object',
  properties: { strategyId: UUID_SCHEMA },
  required: ['strategyId'],
  additionalProperties: false,
};

// commit_strategy_draft request — exactly the two numbers the draft read returned.
const COMMIT_REQUEST_SCHEMA: JsonSchema = {
  type: 'object',
  properties: {
    strategyId: UUID_SCHEMA,
    draftVersion: { type: 'integer', minimum: 1 },
    expectedRevision: { anyOf: [{ type: 'integer', minimum: 1 }, { type: 'null' }] },
  },
  required: ['strategyId', 'draftVersion', 'expectedRevision'],
  additionalProperties: false,
};

// discard_strategy_draft request — the version read, nothing else.
const DISCARD_REQUEST_SCHEMA: JsonSchema = {
  type: 'object',
  properties: {
    strategyId: UUID_SCHEMA,
    draftVersion: { type: 'integer', minimum: 1 },
  },
  required: ['strategyId', 'draftVersion'],
  additionalProperties: false,
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
  'stage_strategy_draft',
  'get_strategy_draft',
  'commit_strategy_draft',
  'discard_strategy_draft',
] as const;

const ENVELOPE_SCHEMAS: Record<string, JsonSchema> = {
  get_strategy_section_template: TEMPLATE_REQUEST_SCHEMA,
  stage_strategy_draft: STAGE_REQUEST_SCHEMA,
  get_strategy_draft: GET_DRAFT_REQUEST_SCHEMA,
  commit_strategy_draft: COMMIT_REQUEST_SCHEMA,
  discard_strategy_draft: DISCARD_REQUEST_SCHEMA,
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
  { name: 'stage_strategy_draft', description: 'Stage axes into a strategy draft.', inputSchema: requestEnvelope(STAGE_REQUEST_SCHEMA) },
  { name: 'get_strategy_draft', description: 'Read a strategy draft with its diff.', inputSchema: requestEnvelope(GET_DRAFT_REQUEST_SCHEMA) },
  { name: 'commit_strategy_draft', description: 'Commit the draft version read.', inputSchema: requestEnvelope(COMMIT_REQUEST_SCHEMA) },
  { name: 'discard_strategy_draft', description: 'Discard the draft version read.', inputSchema: requestEnvelope(DISCARD_REQUEST_SCHEMA) },
];

const SERVER_PROMPTS = [
  { name: 'author-strategy', description: 'Discover, stage, review, and commit a BattleGrid strategy through its draft' },
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
  'compile_strategy_plan',
  'stage_strategy_plan',
  'apply_strategy_plan',
  'update_strategy_signal_rule',
  'create_intelligence_agent',
  'update_intelligence_agent',
  'rebind_intelligence_agent',
];

// --- Request payload fixtures (client-side call arguments) ---

const STRATEGY_ID = '11111111-2222-4333-8444-555555555555';

// A stage into an existing strategy's draft, at the version its read returned.
const STAGE_EDIT_REQUEST = {
  strategyId: STRATEGY_ID,
  draftVersion: 3,
  axes: {
    ENTRY: { entry: { trigger: 'ON_RETEST', levelOffsetAtrMultiple: 0.25, validForBars: 3 } },
    SIGNAL_RULES: { rules: [{ signalId: 'RSI_OVERSOLD', allocation: 3, required: false, params: {} }] },
  },
} as const;

// A stage that opens a new create draft: no id, no draft read.
const STAGE_CREATE_REQUEST = {
  draftVersion: 0,
  axes: {
    IDENTITY: { name: 'Protocol momentum', description: 'Staged through the live MCP dispatcher.', tagline: '' },
    TIMEFRAME_PROFILE: { timeframe: '1h' },
    REPORT: { sections: [{ kind: 'platform', sectionKey: 'includeRsi' }] },
  },
} as const;

const TEMPLATE_REQUEST = { kind: 'platform', sectionKey: 'includeRsi' } as const;

const GET_DRAFT_REQUEST = { strategyId: STRATEGY_ID } as const;

const COMMIT_REQUEST = { strategyId: STRATEGY_ID, draftVersion: 4, expectedRevision: 7 } as const;

// A create commits at expectedRevision null — the null must survive the proxy as null.
const COMMIT_CREATE_REQUEST = { strategyId: STRATEGY_ID, draftVersion: 2, expectedRevision: null } as const;

const DISCARD_REQUEST = { strategyId: STRATEGY_ID, draftVersion: 4 } as const;

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

  it('preserves the ENTRY trigger union unchanged inside the staged axes', async () => {
    const { client } = await setup(['alice', 'bob']);
    const tools = await toolMap(client);
    const request = (tools.get('stage_strategy_draft')!.inputSchema.properties as Record<string, JsonSchema>).request;
    const axes = (request.properties as Record<string, JsonSchema>).axes;
    const entryAxis = (axes.properties as Record<string, JsonSchema>).ENTRY;
    const entry = (entryAxis.properties as Record<string, JsonSchema>).entry;

    const branches = entry.anyOf as JsonSchema[];
    expect(branches).toHaveLength(2);
    const triggers = branches.map(b => (b.properties as Record<string, JsonSchema>).trigger);
    expect(triggers).toEqual([
      { type: 'string', const: 'ON_CANDLE_CLOSE' },
      { type: 'string', enum: ['STOP_THROUGH_LEVEL', 'ON_RETEST'] },
    ]);
    for (const branch of branches) {
      expect(branch.additionalProperties).toBe(false);
      expect(Array.isArray(branch.required)).toBe(true);
    }
    // A representative nested bound survives untouched.
    expect(((branches[1].properties as Record<string, JsonSchema>).validForBars as JsonSchema).minimum).toBe(1);
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
  const cases: { label: string; tool: string; request: Record<string, unknown> }[] = [
    { label: 'stage_strategy_draft (edit)', tool: 'stage_strategy_draft', request: { ...STAGE_EDIT_REQUEST } },
    { label: 'stage_strategy_draft (create)', tool: 'stage_strategy_draft', request: { ...STAGE_CREATE_REQUEST } },
    { label: 'get_strategy_draft', tool: 'get_strategy_draft', request: { ...GET_DRAFT_REQUEST } },
    { label: 'commit_strategy_draft (edit)', tool: 'commit_strategy_draft', request: { ...COMMIT_REQUEST } },
    { label: 'commit_strategy_draft (create)', tool: 'commit_strategy_draft', request: { ...COMMIT_CREATE_REQUEST } },
    { label: 'discard_strategy_draft', tool: 'discard_strategy_draft', request: { ...DISCARD_REQUEST } },
    { label: 'get_strategy_section_template', tool: 'get_strategy_section_template', request: { ...TEMPLATE_REQUEST } },
  ];

  for (const { label, tool, request } of cases) {
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
    await client.callTool({ name: 'stage_strategy_draft', arguments: { account: 'alice', request: { ...STAGE_CREATE_REQUEST } } });
    expect(calls).toHaveLength(1);
    expect(calls[0].apiKey).toBe('bg_live_alice');
    expect(calls[0].arguments).toEqual({ request: { ...STAGE_CREATE_REQUEST } });
  });

  it('rejects a missing account without contacting the upstream server', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    const result = await client.callTool({ name: 'stage_strategy_draft', arguments: { request: { ...STAGE_CREATE_REQUEST } } });
    expect(result.isError).toBe(true);
    expect(calls).toHaveLength(0);
  });

  it('rejects an unknown account without contacting the upstream server', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    const result = await client.callTool({ name: 'stage_strategy_draft', arguments: { account: 'carol', request: { ...STAGE_CREATE_REQUEST } } });
    expect(result.isError).toBe(true);
    expect(calls).toHaveLength(0);
  });
});

describe('single-account forwarding', () => {
  it('forwards the server-native { request } with no account field', async () => {
    const { client, calls } = await setup(['solo']);
    const result = await client.callTool({ name: 'stage_strategy_draft', arguments: { request: { ...STAGE_CREATE_REQUEST } } });

    expect(calls).toHaveLength(1);
    expect(calls[0].apiKey).toBe('bg_live_solo');
    expect(calls[0].arguments).toEqual({ request: { ...STAGE_CREATE_REQUEST } });
    expect(result.structuredContent).toMatchObject({ tool: 'stage_strategy_draft', marker: 'structured-ok' });
  });
});

describe('no reconstruction of flat legacy payloads', () => {
  it('forwards a flat stage payload verbatim and lets the server reject it', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    // A client that sends the request fields flat (no { request } wrapper).
    const legacyFlat = { account: 'alice', draftVersion: 0, axes: { TIMEFRAME_PROFILE: { timeframe: '1h' } } };
    const result = await client.callTool({ name: 'stage_strategy_draft', arguments: legacyFlat });

    // Proxy stripped only account; it did NOT wrap the rest into { request }.
    expect(calls).toHaveLength(1);
    expect(calls[0].arguments).toEqual({ draftVersion: 0, axes: { TIMEFRAME_PROFILE: { timeframe: '1h' } } });
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
