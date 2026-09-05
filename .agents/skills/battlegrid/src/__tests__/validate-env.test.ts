import { describe, it, expect } from 'vitest';
import { validateEnv, DEFAULT_URL } from '../index.js';

describe('validateEnv', () => {
  // --- Single key (backwards compat) ---

  it('returns config with valid single API key and default URL', () => {
    const result = validateEnv({ BATTLEGRID_API_KEY: 'bg_live_abc123' });
    expect(result).toEqual({
      apiKeys: ['bg_live_abc123'],
      apiUrl: DEFAULT_URL,
    });
  });

  it('uses custom BATTLEGRID_API_URL when provided', () => {
    const result = validateEnv({
      BATTLEGRID_API_KEY: 'bg_live_abc123',
      BATTLEGRID_API_URL: 'http://localhost:4002/mcp',
    });
    expect(result.apiUrl).toBe('http://localhost:4002/mcp');
  });

  it('throws when no API key env vars are set', () => {
    expect(() => validateEnv({})).toThrow('BATTLEGRID_API_KEY or BATTLEGRID_API_KEYS environment variable is required');
  });

  it('throws when BATTLEGRID_API_KEY is undefined', () => {
    expect(() => validateEnv({ BATTLEGRID_API_KEY: undefined })).toThrow(
      'BATTLEGRID_API_KEY or BATTLEGRID_API_KEYS environment variable is required'
    );
  });

  it('throws when BATTLEGRID_API_KEY is empty string', () => {
    expect(() => validateEnv({ BATTLEGRID_API_KEY: '' })).toThrow(
      'BATTLEGRID_API_KEY or BATTLEGRID_API_KEYS environment variable is required'
    );
  });

  it('throws when API key does not start with bg_live_', () => {
    expect(() => validateEnv({ BATTLEGRID_API_KEY: 'sk_test_abc' })).toThrow(
      'API key must start with "bg_live_"'
    );
  });

  it('throws when API key has wrong prefix casing', () => {
    expect(() => validateEnv({ BATTLEGRID_API_KEY: 'BG_LIVE_abc' })).toThrow(
      'API key must start with "bg_live_"'
    );
  });

  it('accepts minimum valid key (bg_live_ prefix only)', () => {
    const result = validateEnv({ BATTLEGRID_API_KEY: 'bg_live_x' });
    expect(result.apiKeys).toEqual(['bg_live_x']);
  });

  it('defaults to production URL when BATTLEGRID_API_URL is empty', () => {
    const result = validateEnv({
      BATTLEGRID_API_KEY: 'bg_live_abc123',
      BATTLEGRID_API_URL: '',
    });
    expect(result.apiUrl).toBe(DEFAULT_URL);
  });

  // --- Multi-key (BATTLEGRID_API_KEYS) ---

  it('parses comma-separated BATTLEGRID_API_KEYS', () => {
    const result = validateEnv({
      BATTLEGRID_API_KEYS: 'bg_live_aaa,bg_live_bbb,bg_live_ccc',
    });
    expect(result.apiKeys).toEqual(['bg_live_aaa', 'bg_live_bbb', 'bg_live_ccc']);
  });

  it('trims whitespace around comma-separated keys', () => {
    const result = validateEnv({
      BATTLEGRID_API_KEYS: ' bg_live_aaa , bg_live_bbb ',
    });
    expect(result.apiKeys).toEqual(['bg_live_aaa', 'bg_live_bbb']);
  });

  it('BATTLEGRID_API_KEYS takes precedence over BATTLEGRID_API_KEY', () => {
    const result = validateEnv({
      BATTLEGRID_API_KEYS: 'bg_live_multi1,bg_live_multi2',
      BATTLEGRID_API_KEY: 'bg_live_single',
    });
    expect(result.apiKeys).toEqual(['bg_live_multi1', 'bg_live_multi2']);
  });

  it('throws when BATTLEGRID_API_KEYS is empty', () => {
    expect(() => validateEnv({ BATTLEGRID_API_KEYS: '' })).toThrow(
      'BATTLEGRID_API_KEY or BATTLEGRID_API_KEYS environment variable is required'
    );
  });

  it('throws when any key in BATTLEGRID_API_KEYS has invalid prefix', () => {
    expect(() =>
      validateEnv({ BATTLEGRID_API_KEYS: 'bg_live_good,sk_bad_key' })
    ).toThrow('API key must start with "bg_live_"');
  });

  it('filters out empty entries from trailing commas', () => {
    const result = validateEnv({
      BATTLEGRID_API_KEYS: 'bg_live_aaa,,bg_live_bbb,',
    });
    expect(result.apiKeys).toEqual(['bg_live_aaa', 'bg_live_bbb']);
  });

  it('works with single key in BATTLEGRID_API_KEYS', () => {
    const result = validateEnv({
      BATTLEGRID_API_KEYS: 'bg_live_only',
    });
    expect(result.apiKeys).toEqual(['bg_live_only']);
  });
});
