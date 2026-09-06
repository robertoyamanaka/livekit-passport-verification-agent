import type { VercelRequest, VercelResponse } from '@vercel/node';
import { AccessToken } from 'livekit-server-sdk';

interface TokenRequestBody {
  identity?: string;
  name?: string;
  email?: string;
  room?: string;
}

/**
 * Mints a short-lived LiveKit access token server-side so the LiveKit API
 * secret never reaches the browser. The caller's email is stashed in the
 * participant's attributes so the Python agent can read it on join and use
 * it to send the contract email after a validated verdict.
 */
export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  const { identity, name, email, room } = (req.body ?? {}) as TokenRequestBody;

  if (!identity || !name || !email || !room) {
    res.status(400).json({ error: 'identity, name, email and room are required' });
    return;
  }

  const apiKey = process.env['LIVEKIT_API_KEY'];
  const apiSecret = process.env['LIVEKIT_API_SECRET'];
  const url = process.env['LIVEKIT_URL'];

  if (!apiKey || !apiSecret || !url) {
    console.error('Missing LiveKit env vars: LIVEKIT_API_KEY / LIVEKIT_API_SECRET / LIVEKIT_URL');
    res.status(500).json({ error: 'Server is missing LiveKit credentials' });
    return;
  }

  try {
    const at = new AccessToken(apiKey, apiSecret, {
      identity,
      name,
      ttl: '15m',
      attributes: { email },
    });
    at.addGrant({
      room,
      roomJoin: true,
      canPublish: true,
      canSubscribe: true,
      canPublishData: true,
    });

    const token = await at.toJwt();
    res.status(200).json({ token, url, room });
  } catch (err) {
    console.error('Failed to mint LiveKit token', err);
    res.status(500).json({ error: 'Failed to mint token' });
  }
}
