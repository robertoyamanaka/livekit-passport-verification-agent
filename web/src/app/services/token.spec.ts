import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { Token } from './token';

describe('Token', () => {
  let token: Token;

  beforeEach(() => {
    token = new Token();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts the request and resolves with the parsed token response on success', async () => {
    const fakeResponse = { token: 'jwt', url: 'wss://x.livekit.cloud', room: 'cierre-1' };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(fakeResponse),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await token.fetch({
      identity: 'cliente-1',
      name: 'Roberto',
      email: 'r@example.com',
      room: 'cierre-1',
    });

    expect(result).toEqual(fakeResponse);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/token',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('throws the server-provided error message on a non-OK response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: 'Agent dispatch failed' }),
      }),
    );

    await expect(
      token.fetch({ identity: 'i', name: 'n', email: 'e', room: 'r' }),
    ).rejects.toThrow('Agent dispatch failed');
  });

  it('falls back to a generic error when the failure response has no body', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: () => Promise.reject(new Error('not json')),
      }),
    );

    await expect(
      token.fetch({ identity: 'i', name: 'n', email: 'e', room: 'r' }),
    ).rejects.toThrow('Token request failed (503)');
  });
});
