import type { VercelRequest, VercelResponse } from '@vercel/node';
import { AccessToken, AgentDispatchClient } from 'livekit-server-sdk';

interface TokenRequestBody {
  identity?: string;
  name?: string;
  email?: string;
  room?: string;
}

// Must match the agent_name passed to @server.rtc_session(...) in agent/src/agent.py.
// The agent registers under a named (non-empty) agent_name, which opts it into
// LiveKit's *explicit* dispatch model — it will NOT auto-join every new room
// unless something explicitly requests it by name.
//
// This is done via a direct AgentDispatchClient.createDispatch() call, called
// BEFORE minting the token, per LiveKit's own guidance: dispatch requests
// embedded in an access token's roomConfig only take effect the moment a room
// is first created — for an already-existing room they're silently ignored,
// which is an easy race to lose in practice. Explicit dispatch via the API
// sidesteps that entirely. See https://docs.livekit.io/agents/server/agent-dispatch/
const AGENT_NAME = 'passport-verification-agent';

/**
 * Explicitly dispatches the agent into the room, then mints a short-lived
 * LiveKit access token server-side so the LiveKit API secret never reaches
 * the browser. The caller's name and email are passed as dispatch metadata
 * (not participant attributes) — LiveKit's recommended way to hand a job
 * context data, and it's available to the agent immediately on job start
 * rather than requiring it to wait for/poll a remote participant.
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
    const httpUrl = url.replace(/^wss:\/\//, 'https://').replace(/^ws:\/\//, 'http://');
    const dispatchClient = new AgentDispatchClient(httpUrl, apiKey, apiSecret);
    await dispatchClient.createDispatch(room, AGENT_NAME, {
      metadata: JSON.stringify({ customer_name: name, email }),
    });

    const at = new AccessToken(apiKey, apiSecret, { identity, name, ttl: '15m' });
    at.addGrant({ room, roomJoin: true, canPublish: true, canSubscribe: true, canPublishData: true });
    const token = await at.toJwt();

    res.status(200).json({ token, url, room });
  } catch (err) {
    console.error('Failed to dispatch agent / mint LiveKit token', err);
    res.status(500).json({ error: 'Failed to mint token' });
  }
}
