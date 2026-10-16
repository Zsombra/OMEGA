/**
 * Protocol harness for the proxy's account contract over the authoring tools.
 *
 * These tests drive `tools/list` and `tools/call` over a real in-memory MCP
 * transport pair (client ⇄ proxy Server), with a faithful fake upstream in
 * place of the remote BattleGrid server. The fixture mirrors the two input
 * conventions the server publishes — and the server, never this package, owns
 * which tool takes which (`battlegrid-app`, `mcp-client-parity` "One
 * publication-envelope authority"):
 *
 *   - FLAT: the strategy draft tools publish their arguments at the top level;
 *   - ENVELOPED: `get_strategy_section_template`, whose payload is a union,
 *     publishes `{ request }`.
 *
 * They prove — at the protocol level, not via helper-function unit tests — that
 * the proxy:
 *
 *   - adds `account` beside a tool's own top-level properties in multi-account
 *     mode, preserving every server-owned property (unions, discriminators,
 *     required fields, bounds, additionalProperties);
 *   - publishes every schema unchanged in single-account mode;
 *   - strips ONLY `account` on a call and forwards every other argument
 *     unchanged with the routed Bearer token;
 *   - forwards a retired shape verbatim — an enveloped payload to a flat tool,
 *     or a flat payload to an enveloped one — and lets the server refuse it;
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

/** The strategy draft tools: their arguments are the top-level properties of one strict root. */
const FLAT_DRAFT_SCHEMAS: Record<string, JsonSchema> = {
  stage_strategy_draft: STAGE_REQUEST_SCHEMA,
  get_strategy_draft: GET_DRAFT_REQUEST_SCHEMA,
  commit_strategy_draft: COMMIT_REQUEST_SCHEMA,
  discard_strategy_draft: DISCARD_REQUEST_SCHEMA,
};
const FLAT_DRAFT_TOOL_NAMES = Object.keys(FLAT_DRAFT_SCHEMAS);

/** The enveloped tool: a union payload the server publishes under `request`. */
const ENVELOPED_TOOL = 'get_strategy_section_template';

interface ToolShape {
  name: string;
  description: string;
  inputSchema: JsonSchema;
}

const SERVER_TOOLS: ToolShape[] = [
  { name: 'list_strategies', description: 'List strategies.', inputSchema: LIST_STRATEGIES_SCHEMA },
  { name: 'get_account_state', description: 'Get account state.', inputSchema: GET_ACCOUNT_STATE_SCHEMA },
  { name: ENVELOPED_TOOL, description: 'Get one section template.', inputSchema: requestEnvelope(TEMPLATE_REQUEST_SCHEMA) },
  { name: 'stage_strategy_draft', description: 'Stage axes into a strategy draft.', inputSchema: STAGE_REQUEST_SCHEMA },
  { name: 'get_strategy_draft', description: 'Read a strategy draft with its diff.', inputSchema: GET_DRAFT_REQUEST_SCHEMA },
  { name: 'commit_strategy_draft', description: 'Commit the draft version read.', inputSchema: COMMIT_REQUEST_SCHEMA },
  { name: 'discard_strategy_draft', description: 'Discard the draft version read.', inputSchema: DISCARD_REQUEST_SCHEMA },
];

const SERVER_PROMPTS = [
  { name: 'author-strategy', description: 'Discover, stage, review, and commit a BattleGrid strategy through its draft' },
  { name: 'play-market-grid', description: 'Play a Market Grid game.' },
];

const SERVER_RESOURCES = [
  { uri: 'battlegrid://guide/quick-start', name: 'Quick Start', mimeType: 'text/markdown' },
];

const KNOWN_TOOL_NAMES = new Set(SERVER_TOOLS.map(t => t.name));

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

      // Every root is closed: a key the tool does not publish is refused by name, as the server's
      // strict schema refuses it. The server never reconstructs a payload, so neither can the proxy.
      const published = SERVER_TOOLS.find(t => t.name === params.name)!.inputSchema;
      const declared = Object.keys(published.properties as Record<string, unknown>);
      const unknownKeys = Object.keys(params.arguments ?? {}).filter(key => !declared.includes(key));
      if (unknownKeys.length > 0) {
        return {
          content: [{ type: 'text', text: JSON.stringify({ code: 'VALIDATION_ERROR', message: `Unrecognized key(s) in object: ${unknownKeys.map(k => `'${k}'`).join(', ')}` }) }],
          isError: true,
        };
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

describe('multi-account discovery — account beside each tool\'s own properties', () => {
  it('adds account beside a flat draft tool\'s own top-level properties, preserving each of them', async () => {
    const { client } = await setup(['alice', 'bob']);
    const tools = await toolMap(client);

    for (const name of FLAT_DRAFT_TOOL_NAMES) {
      const tool = tools.get(name);
      expect(tool, `missing authoring tool ${name}`).toBeDefined();
      const schema = tool!.inputSchema;
      const properties = schema.properties as Record<string, JsonSchema>;
      const server = FLAT_DRAFT_SCHEMAS[name];
      const serverProperties = server.properties as Record<string, JsonSchema>;

      // Root shape: account, then the tool's own properties; both required sets kept; closed world.
      expect(schema.type).toBe('object');
      expect(Object.keys(properties)).toEqual(['account', ...Object.keys(serverProperties)]);
      expect(schema.required).toEqual(['account', ...((server.required as string[] | undefined) ?? [])]);
      expect(schema.additionalProperties).toBe(false);
      expect(properties).not.toHaveProperty('request');

      // account is the only addition — a plain string enum of usernames.
      const account = properties.account as Record<string, unknown>;
      expect(account.type).toBe('string');
      expect(account.enum).toEqual(['alice', 'bob']);
      expect(typeof account.description).toBe('string');

      // Every server-owned property is byte-for-byte what the server published.
      for (const [key, value] of Object.entries(serverProperties)) {
        expect(properties[key]).toEqual(value);
      }
    }
  });

  it('adds account beside an enveloped tool\'s request, preserving the nested union', async () => {
    const { client } = await setup(['alice', 'bob']);
    const schema = (await toolMap(client)).get(ENVELOPED_TOOL)!.inputSchema;
    const properties = schema.properties as Record<string, JsonSchema>;

    expect(Object.keys(properties)).toEqual(['account', 'request']);
    expect(schema.required).toEqual(['account', 'request']);
    expect(schema.additionalProperties).toBe(false);
    expect(properties.request).toEqual(TEMPLATE_REQUEST_SCHEMA);
  });

  it('preserves the ENTRY trigger union unchanged inside the staged axes', async () => {
    const { client } = await setup(['alice', 'bob']);
    const tools = await toolMap(client);
    const axes = (tools.get('stage_strategy_draft')!.inputSchema.properties as Record<string, JsonSchema>).axes;
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

  it('injects account as the sole addition on the other flat tools too', async () => {
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

describe('single-account discovery — every schema as the server published it', () => {
  it('publishes the flat and the enveloped tools unchanged, with no account field', async () => {
    const { client } = await setup(['solo']);
    const tools = await toolMap(client);

    for (const name of FLAT_DRAFT_TOOL_NAMES) {
      expect(tools.get(name)!.inputSchema).toEqual(FLAT_DRAFT_SCHEMAS[name]);
    }
    expect(tools.get(ENVELOPED_TOOL)!.inputSchema).toEqual(requestEnvelope(TEMPLATE_REQUEST_SCHEMA));
    expect(tools.get('list_strategies')!.inputSchema).toEqual(LIST_STRATEGIES_SCHEMA);
  });
});

describe('exact forwarding — strip only account, forward every other argument unchanged', () => {
  const cases: { label: string; tool: string; args: Record<string, unknown> }[] = [
    { label: 'stage_strategy_draft (edit)', tool: 'stage_strategy_draft', args: { ...STAGE_EDIT_REQUEST } },
    { label: 'stage_strategy_draft (create)', tool: 'stage_strategy_draft', args: { ...STAGE_CREATE_REQUEST } },
    { label: 'get_strategy_draft', tool: 'get_strategy_draft', args: { ...GET_DRAFT_REQUEST } },
    { label: 'commit_strategy_draft (edit)', tool: 'commit_strategy_draft', args: { ...COMMIT_REQUEST } },
    { label: 'commit_strategy_draft (create)', tool: 'commit_strategy_draft', args: { ...COMMIT_CREATE_REQUEST } },
    { label: 'discard_strategy_draft', tool: 'discard_strategy_draft', args: { ...DISCARD_REQUEST } },
    { label: ENVELOPED_TOOL, tool: ENVELOPED_TOOL, args: { request: { ...TEMPLATE_REQUEST } } },
  ];

  for (const { label, tool, args } of cases) {
    it(`routes ${label} to the selected account and forwards its arguments verbatim`, async () => {
      const { client, calls } = await setup(['alice', 'bob']);

      const result = await client.callTool({ name: tool, arguments: { account: 'bob', ...args } });

      // Exactly one upstream call, routed to bob's key.
      expect(calls).toHaveLength(1);
      expect(calls[0]).toMatchObject({ apiKey: 'bg_live_bob', kind: 'tool', name: tool });
      // Account consumed; every other argument forwarded unchanged (no wrap, no unwrap, no reshape).
      expect(calls[0].arguments).toEqual(args);
      expect(calls[0].arguments).not.toHaveProperty('account');

      // Structured + text results are preserved consistently.
      expect(result.isError).toBeFalsy();
      expect(result.content).toEqual([{ type: 'text', text: `RESULT_TEXT:${tool}` }]);
      expect(result.structuredContent).toEqual({ tool, marker: 'structured-ok', echoed: args });
    });
  }

  it('routes to the primary account when it is selected', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    await client.callTool({ name: 'stage_strategy_draft', arguments: { account: 'alice', ...STAGE_CREATE_REQUEST } });
    expect(calls).toHaveLength(1);
    expect(calls[0].apiKey).toBe('bg_live_alice');
    expect(calls[0].arguments).toEqual({ ...STAGE_CREATE_REQUEST });
  });

  it('rejects a missing account without contacting the upstream server', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    const result = await client.callTool({ name: 'stage_strategy_draft', arguments: { ...STAGE_CREATE_REQUEST } });
    expect(result.isError).toBe(true);
    expect(calls).toHaveLength(0);
  });

  it('rejects an unknown account without contacting the upstream server', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    const result = await client.callTool({ name: 'stage_strategy_draft', arguments: { account: 'carol', ...STAGE_CREATE_REQUEST } });
    expect(result.isError).toBe(true);
    expect(calls).toHaveLength(0);
  });
});

describe('single-account forwarding', () => {
  it('forwards the published arguments with no account field', async () => {
    const { client, calls } = await setup(['solo']);
    const result = await client.callTool({ name: 'stage_strategy_draft', arguments: { ...STAGE_CREATE_REQUEST } });

    expect(calls).toHaveLength(1);
    expect(calls[0].apiKey).toBe('bg_live_solo');
    expect(calls[0].arguments).toEqual({ ...STAGE_CREATE_REQUEST });
    expect(result.structuredContent).toMatchObject({ tool: 'stage_strategy_draft', marker: 'structured-ok' });
  });
});

describe('no reconstruction of a retired shape', () => {
  it('forwards an enveloped legacy payload to a flat draft tool verbatim and lets the server refuse it', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    // A client still sending the pre-111 envelope to a tool that now publishes its arguments flat.
    const result = await client.callTool({
      name: 'stage_strategy_draft',
      arguments: { account: 'alice', request: { ...STAGE_CREATE_REQUEST } },
    });

    // Proxy stripped only account; it did NOT unwrap request.
    expect(calls).toHaveLength(1);
    expect(calls[0].arguments).toEqual({ request: { ...STAGE_CREATE_REQUEST } });
    // The server's closed root refuses the envelope by name.
    expect(result.isError).toBe(true);
    expect(JSON.stringify(result.content)).toContain("Unrecognized key(s) in object: 'request'");
  });

  it('forwards a flat payload to the enveloped tool verbatim and lets the server refuse it', async () => {
    const { client, calls } = await setup(['alice', 'bob']);
    const result = await client.callTool({ name: ENVELOPED_TOOL, arguments: { account: 'alice', ...TEMPLATE_REQUEST } });

    // Proxy stripped only account; it did NOT wrap the rest into { request }.
    expect(calls).toHaveLength(1);
    expect(calls[0].arguments).toEqual({ ...TEMPLATE_REQUEST });
    expect(result.isError).toBe(true);
    expect(JSON.stringify(result.content)).toContain("Unrecognized key(s) in object: 'kind', 'sectionKey'");
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
