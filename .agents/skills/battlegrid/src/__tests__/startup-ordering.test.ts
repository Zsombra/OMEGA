/**
 * Startup ordering, lazy catalog, and the two account-safety invariants.
 *
 * The regressions these pin are SILENT. A re-introduced eager `await` before the transport binds
 * still passes every other test in this suite; an account guard derived from resolved identities
 * still answers every happy-path call correctly. Both only surface as a client that never finishes
 * connecting, or as a money-moving call executing as an account nobody named.
 *
 * Driven over a real in-memory transport pair so the assertions are on the protocol a client
 * actually observes, not on internal fields.
 */

import { describe, it, expect } from 'vitest';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { ToolListChangedNotificationSchema, type Implementation } from '@modelcontextprotocol/sdk/types.js';
import { createProxyServer, type AccountIdentity, type ProxyServer } from '../index.js';

const UPSTREAM: Implementation = { name: 'battlegrid', version: '49.0.0' };

function identitiesFor(usernames: string[]): AccountIdentity[] {
  return usernames.map((username, i) => ({
    apiKey: `bg_live_${username}`,
    userId: `user-${i}`,
    username,
    keyLabel: null,
  }));
}

interface FakeUpstreamOptions {
  /** Resolve `listTools` only when this settles. A never-settling promise models a hung catalog. */
  listToolsGate?: Promise<void>;
  /** Fail `listTools` this many times before succeeding. */
  failListToolsTimes?: number;
  onListTools?: () => void;
}

function fakeUpstream(options: FakeUpstreamOptions = {}): Client {
  let failuresLeft = options.failListToolsTimes ?? 0;
  const upstream = {
    getServerVersion: () => UPSTREAM,
    async listTools() {
      options.onListTools?.();
      if (options.listToolsGate) await options.listToolsGate;
      if (failuresLeft > 0) {
        failuresLeft -= 1;
        throw new Error('upstream catalog unavailable');
      }
      return { tools: [{ name: 'get_account_state', inputSchema: { type: 'object' } }] };
    },
    async listPrompts() {
      return { prompts: [] };
    },
    async listResources() {
      return { resources: [] };
    },
  };
  return upstream as unknown as Client;
}

interface Stood {
  client: Client;
  proxy: ProxyServer;
}

async function standUp(proxy: ProxyServer): Promise<Stood> {
  const client = new Client({ name: 'startup-ordering-test', version: '1.0.0' });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([
    proxy.server.connect(serverTransport),
    client.connect(clientTransport),
  ]);
  return { client, proxy };
}

describe('bind precedes catalog resolution', () => {
  it('answers initialize while the tool catalog is still hanging', async () => {
    // The gate never settles, so any implementation that resolves the catalog before binding
    // cannot reach `initialize` at all — this test hangs against the pre-change ordering.
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream({ listToolsGate: new Promise<void>(() => {}) }),
      resolveIdentities: async () => identitiesFor(['alice']),
    });

    const { client } = await standUp(proxy);

    expect(client.getServerVersion()).toEqual(UPSTREAM);
  });

  it('advertises listChanged before the catalog has resolved', async () => {
    // The capability cannot be registered after the transport binds, so it has to be declared up
    // front or a client whose first listing failed can never learn the catalog recovered.
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream({ listToolsGate: new Promise<void>(() => {}) }),
      resolveIdentities: async () => identitiesFor(['alice']),
    });

    const { client } = await standUp(proxy);
    const capabilities = client.getServerCapabilities();

    expect(capabilities?.tools?.listChanged).toBe(true);
    expect(capabilities?.prompts?.listChanged).toBe(true);
    expect(capabilities?.resources?.listChanged).toBe(true);
  });
});

describe('catalog resolution is shared and does not cache failure', () => {
  it('resolves once for two concurrent listings', async () => {
    let listToolsCalls = 0;
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream({ onListTools: () => { listToolsCalls += 1; } }),
      resolveIdentities: async () => identitiesFor(['alice']),
    });
    const { client } = await standUp(proxy);

    await Promise.all([client.listTools(), client.listTools()]);

    expect(listToolsCalls).toBe(1);
  });

  it('joins an in-flight warm-up rather than starting a second resolution', async () => {
    let listToolsCalls = 0;
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream({ onListTools: () => { listToolsCalls += 1; } }),
      resolveIdentities: async () => identitiesFor(['alice']),
    });
    const { client } = await standUp(proxy);

    const warming = proxy.warm();
    const listed = await client.listTools();
    await warming;

    expect(listToolsCalls).toBe(1);
    expect(listed.tools).toHaveLength(1);
  });

  it('retries on the next request after a transient failure, rather than replaying it', async () => {
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream({ failListToolsTimes: 1 }),
      resolveIdentities: async () => identitiesFor(['alice']),
    });
    const { client } = await standUp(proxy);

    await expect(client.listTools()).rejects.toThrow();

    const recovered = await client.listTools();
    expect(recovered.tools).toHaveLength(1);
  });

  it('does not remember a failure raised before the resolution awaits anything', async () => {
    // The naive memo shape poisons permanently here: an async body throwing before its first
    // `await` runs the inner catch during the synchronous prefix, and the outer assignment then
    // re-installs the rejected promise.
    let firstCall = true;
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream(),
      resolveIdentities: () => {
        if (firstCall) {
          firstCall = false;
          throw new Error('synchronous identity failure');
        }
        return Promise.resolve(identitiesFor(['alice']));
      },
    });
    const { client } = await standUp(proxy);

    await expect(client.listTools()).rejects.toThrow();

    const recovered = await client.listTools();
    expect(recovered.tools).toHaveLength(1);
  });

  it('surfaces a failed listing as a protocol error, not a result carrying isError', async () => {
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream({ failListToolsTimes: 1 }),
      resolveIdentities: async () => identitiesFor(['alice']),
    });
    const { client } = await standUp(proxy);

    // A `{ content, isError }` body would arrive as a SUCCESSFUL result whose shape fails the
    // client's own ListToolsResult parse — never as a rejection.
    await expect(client.listTools()).rejects.toThrow();
  });
});

describe('warm-up cannot terminate the proxy', () => {
  it('absorbs a failed warm-up and still serves the next request', async () => {
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream({ failListToolsTimes: 1 }),
      resolveIdentities: async () => identitiesFor(['alice']),
    });
    const { client } = await standUp(proxy);

    await expect(proxy.warm()).rejects.toThrow();

    const recovered = await client.listTools();
    expect(recovered.tools).toHaveLength(1);
  });

  it('reports resolved counts and the account roster on success', async () => {
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream(),
      resolveIdentities: async () => identitiesFor(['alice']),
    });
    await standUp(proxy);

    await expect(proxy.warm()).resolves.toEqual({
      accountNames: ['alice'],
      toolCount: 1,
      promptCount: 0,
      resourceCount: 0,
    });
  });
});

describe('a client is told when a failed catalog recovers', () => {
  it('notifies the client after a resolution that succeeds following an error', async () => {
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: false,
      connect: async () => fakeUpstream({ failListToolsTimes: 1 }),
      resolveIdentities: async () => identitiesFor(['alice']),
    });
    const { client } = await standUp(proxy);

    let notified = 0;
    client.setNotificationHandler(ToolListChangedNotificationSchema, async () => {
      notified += 1;
    });

    // First listing fails and is served as an error; without the notification a real client would
    // hold that empty catalog for the life of the process.
    await expect(client.listTools()).rejects.toThrow();
    await client.listTools();

    // Let the notification cross the in-memory transport.
    await new Promise((resolve) => setTimeout(resolve, 20));

    expect(notified).toBeGreaterThanOrEqual(1);
  });
});

describe('the account guard is armed by configuration', () => {
  it('refuses an unqualified call when two keys are configured but one identity resolved', async () => {
    // Money-adjacent. Deriving isMultiAccount from the resolved count would stand the guard down
    // here and route an unqualified close_agent_position to the primary.
    let upstreamCalls = 0;
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: true, // two keys CONFIGURED
      connect: async () => {
        const upstream = fakeUpstream();
        return {
          ...upstream,
          async callTool() {
            upstreamCalls += 1;
            return { content: [] };
          },
        } as unknown as Client;
      },
      resolveIdentities: async () => identitiesFor(['alice']), // only one RESOLVED
    });
    const { client } = await standUp(proxy);

    const result = await client.callTool({ name: 'get_account_state', arguments: {} });

    expect(result.isError).toBe(true);
    expect(upstreamCalls).toBe(0);
  });

  it('offers only the accounts that resolved', async () => {
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: true,
      connect: async () => fakeUpstream(),
      resolveIdentities: async () => identitiesFor(['alice']),
    });
    const { client } = await standUp(proxy);

    const listed = await client.listTools();
    const account = (listed.tools[0].inputSchema as { properties: { account: { enum: string[] } } })
      .properties.account;

    expect(account.enum).toEqual(['alice']);
  });
});

describe('the primary account must resolve', () => {
  it('refuses the resolution when the primary key is absent from the roster', async () => {
    // Money-adjacent. The primary still serves prompts and resources, so a roster that excludes it
    // means those execute as an account no selector names and no log line prints.
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: true,
      connect: async () => fakeUpstream(),
      resolveIdentities: async () => identitiesFor(['bob']), // alice's identity lookup failed
    });
    const { client } = await standUp(proxy);

    await expect(client.listTools()).rejects.toThrow(/bg_live_alic/);
  });

  it('refuses the resolution when two accounts share a display name', async () => {
    const proxy = await createProxyServer({
      primaryKey: 'bg_live_alice',
      isMultiAccount: true,
      connect: async () => fakeUpstream(),
      resolveIdentities: async () => [
        { apiKey: 'bg_live_alice', userId: 'user-0', username: 'twin', keyLabel: null },
        { apiKey: 'bg_live_bob', userId: 'user-1', username: 'twin', keyLabel: null },
      ],
    });
    const { client } = await standUp(proxy);

    await expect(client.listTools()).rejects.toThrow(/twin/);
  });
});
