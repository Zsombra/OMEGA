import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { discoverIdentities } from '../index.js';

describe('discoverIdentities', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('maps keys to account identities', async () => {
    globalThis.fetch = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const auth = (init.headers as Record<string, string>).Authorization;
      if (auth === 'Bearer bg_live_aaa') {
        return Promise.resolve(new Response(JSON.stringify({
          userId: 'u1', username: 'alice', keyLabel: 'main',
        }), { status: 200 }));
      }
      if (auth === 'Bearer bg_live_bbb') {
        return Promise.resolve(new Response(JSON.stringify({
          userId: 'u2', username: 'bob', keyLabel: null,
        }), { status: 200 }));
      }
      return Promise.resolve(new Response('not found', { status: 404 }));
    });

    const ids = await discoverIdentities(
      ['bg_live_aaa', 'bg_live_bbb'],
      'https://mcp.battlegrid.trade',
    );
    expect(ids).toHaveLength(2);
    expect(ids[0]).toEqual({
      apiKey: 'bg_live_aaa', userId: 'u1', username: 'alice', keyLabel: 'main',
    });
    expect(ids[1]).toEqual({
      apiKey: 'bg_live_bbb', userId: 'u2', username: 'bob', keyLabel: null,
    });
  });

  it('uses userId prefix when username is null', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        userId: 'abcdef12-3456-7890', username: null, keyLabel: null,
      }), { status: 200 }),
    );

    const ids = await discoverIdentities(['bg_live_x'], 'https://mcp.battlegrid.trade');
    expect(ids[0].username).toBe('abcdef12');
  });

  it('skips failed keys but returns successful ones', async () => {
    globalThis.fetch = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const auth = (init.headers as Record<string, string>).Authorization;
      if (auth === 'Bearer bg_live_good') {
        return Promise.resolve(new Response(JSON.stringify({
          userId: 'u1', username: 'alice', keyLabel: null,
        }), { status: 200 }));
      }
      return Promise.resolve(new Response('Unauthorized', { status: 401 }));
    });

    const ids = await discoverIdentities(
      ['bg_live_bad', 'bg_live_good'],
      'https://mcp.battlegrid.trade',
    );
    expect(ids).toHaveLength(1);
    expect(ids[0].username).toBe('alice');
  });

  it('throws when all keys fail', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response('Unauthorized', { status: 401 }),
    );

    await expect(
      discoverIdentities(['bg_live_x'], 'https://mcp.battlegrid.trade'),
    ).rejects.toThrow('No valid API keys');
  });

  it('strips /mcp suffix from URL for identity endpoint', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        userId: 'u1', username: 'alice', keyLabel: null,
      }), { status: 200 }),
    );
    globalThis.fetch = fetchSpy;

    await discoverIdentities(['bg_live_x'], 'https://mcp.battlegrid.trade/mcp');
    expect(fetchSpy).toHaveBeenCalledWith(
      'https://mcp.battlegrid.trade/mcp/identity',
      expect.any(Object),
    );
  });
});
