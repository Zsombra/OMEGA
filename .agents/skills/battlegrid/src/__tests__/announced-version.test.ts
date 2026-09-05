/**
 * The announced contract version — relayed from upstream, never declared here.
 *
 * This is the whole of #20 expressed as behaviour: what a local MCP client reads in the stdio
 * handshake must be what the connected server announced, not a constant compiled into this package.
 * The failure these tests exist to prevent is silent and slow — the package sat at `11.0.0` against
 * a deployed contract of `19.3.0` and nothing failed, because a hardcoded number is always
 * internally consistent. So the assertions are deliberately written against a *divergent* upstream:
 * a test whose fake upstream announced PACKAGE_VERSION would pass just as happily with the bug
 * restored.
 *
 * Driven over a real in-memory transport pair (client ⇄ proxy Server) so the assertion is on the
 * protocol handshake a client actually observes, not on an internal field.
 */

import { describe, it, expect } from 'vitest';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import type { Implementation } from '@modelcontextprotocol/sdk/types.js';
import {
  createProxyServer,
  announcedIdentityOf,
  PACKAGE_VERSION,
  type AccountIdentity,
} from '../index.js';

/** A minimal upstream that announces `serverInfo` and nothing else of interest. */
function upstreamAnnouncing(serverInfo: Implementation | undefined): Client {
  const upstream = {
    getServerVersion: () => serverInfo,
    async listTools() {
      return { tools: [] };
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

const IDENTITIES: AccountIdentity[] = [
  { apiKey: 'bg_live_alice', userId: 'user-0', username: 'alice', keyLabel: null },
];

/** Stands up the proxy over a fake upstream and returns the handshake a local client observes. */
async function announcedToLocalClient(serverInfo: Implementation): Promise<Implementation | undefined> {
  const proxy = await createProxyServer({
    primaryKey: IDENTITIES[0].apiKey,
    isMultiAccount: IDENTITIES.length > 1,
    connect: async () => upstreamAnnouncing(serverInfo),
    resolveIdentities: async () => IDENTITIES,
  });

  const client = new Client({ name: 'announced-version-test', version: '1.0.0' });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([
    proxy.server.connect(serverTransport),
    client.connect(clientTransport),
  ]);

  return client.getServerVersion();
}

describe('announced identity — read from the upstream handshake', () => {
  it('announces the upstream contract version, not this package\'s version', async () => {
    // The real divergence at the time of writing: package 12.0.0, deployed contract 19.3.0.
    const announced = await announcedToLocalClient({ name: 'battlegrid', version: '19.3.0' });

    expect(announced?.version).toBe('19.3.0');
    expect(announced?.version).not.toBe(PACKAGE_VERSION);
  });

  it('announces the upstream server name rather than a local constant', async () => {
    const announced = await announcedToLocalClient({ name: 'battlegrid-staging', version: '19.3.0' });

    expect(announced?.name).toBe('battlegrid-staging');
  });

  it('tracks a moved contract with no change to this package', async () => {
    // The property the whole ticket turns on: the server moves, the announcement follows, and
    // nothing here was edited or republished between these two connections.
    const before = await announcedToLocalClient({ name: 'battlegrid', version: '19.3.0' });
    const after = await announcedToLocalClient({ name: 'battlegrid', version: '20.0.0' });

    expect(before?.version).toBe('19.3.0');
    expect(after?.version).toBe('20.0.0');
  });

  it('relays optional display metadata verbatim instead of reconstructing two fields', async () => {
    // A field the server adds later should reach local clients without an edit here.
    const announced = await announcedToLocalClient({
      name: 'battlegrid',
      version: '19.3.0',
      title: 'BattleGrid',
      websiteUrl: 'https://battlegrid.trade',
    });

    expect(announced?.title).toBe('BattleGrid');
    expect(announced?.websiteUrl).toBe('https://battlegrid.trade');
  });
});

describe('announcedIdentityOf — fails closed', () => {
  it('throws when a connected upstream announced no serverInfo', () => {
    // `serverInfo` is required in a successful `initialize` result, so this is a protocol
    // violation. The tempting repair — fall back to PACKAGE_VERSION — is the bug being removed.
    expect(() => announcedIdentityOf(undefined)).toThrow(/serverInfo/);
  });

  it('does not substitute the package version when the upstream is silent', () => {
    expect(() => announcedIdentityOf(undefined)).toThrow(/not something this proxy will substitute/);
  });

  it('refuses to build a proxy over an upstream that announced nothing', async () => {
    // Fail-closed has to hold at the composition site too, not just in the helper: a proxy that
    // started anyway would announce something, and there is no honest value to announce.
    await expect(
      createProxyServer({
        primaryKey: IDENTITIES[0].apiKey,
        isMultiAccount: IDENTITIES.length > 1,
        connect: async () => upstreamAnnouncing(undefined),
        resolveIdentities: async () => IDENTITIES,
      }),
    ).rejects.toThrow(/serverInfo/);
  });

  it('passes the upstream identity through unchanged', () => {
    const serverInfo: Implementation = { name: 'battlegrid', version: '19.3.0' };

    expect(announcedIdentityOf(serverInfo)).toBe(serverInfo);
  });
});
