import { Service } from '@angular/core';
import { TokenResponse } from '../models/events';

export interface TokenRequest {
  identity: string;
  name: string;
  email: string;
  room: string;
}

/** Talks to the /api/token Vercel serverless function to mint a LiveKit join token. */
@Service()
export class Token {
  async fetch(request: TokenRequest): Promise<TokenResponse> {
    const response = await fetch('/api/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body?.error ?? `Token request failed (${response.status})`);
    }

    return response.json() as Promise<TokenResponse>;
  }
}
