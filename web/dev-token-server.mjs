// Minimal local stand-in for api/token.ts, used only for `npm run dev:token`
// during local testing. Production uses the real Vercel serverless function
// at api/token.ts — this script duplicates its logic in plain Node so local
// testing doesn't require the Vercel CLI at all.
import { createServer } from 'node:http';
import { config } from 'dotenv';
import { AccessToken, AgentDispatchClient } from 'livekit-server-sdk';

config();

const PORT = process.env.DEV_TOKEN_PORT ?? 8787;
const { LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET } = process.env;

// Must match api/token.ts and agent/src/agent.py's agent_name.
const AGENT_NAME = 'passport-verification-agent';

if (!LIVEKIT_URL || !LIVEKIT_API_KEY || !LIVEKIT_API_SECRET) {
  console.error('Missing LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET in web/.env');
  process.exit(1);
}

const server = createServer(async (req, res) => {
  if (req.method !== 'POST' || req.url !== '/api/token') {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
    return;
  }

  let body = '';
  for await (const chunk of req) body += chunk;

  let parsed;
  try {
    parsed = JSON.parse(body || '{}');
  } catch {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Invalid JSON body' }));
    return;
  }

  const { identity, name, email, room } = parsed;
  if (!identity || !name || !email || !room) {
    res.writeHead(400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'identity, name, email and room are required' }));
    return;
  }

  try {
    const httpUrl = LIVEKIT_URL.replace(/^wss:\/\//, 'https://').replace(/^ws:\/\//, 'http://');
    const dispatchClient = new AgentDispatchClient(httpUrl, LIVEKIT_API_KEY, LIVEKIT_API_SECRET);
    await dispatchClient.createDispatch(room, AGENT_NAME, {
      metadata: JSON.stringify({ customer_name: name, email }),
    });

    const at = new AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET, { identity, name, ttl: '15m' });
    at.addGrant({ room, roomJoin: true, canPublish: true, canSubscribe: true, canPublishData: true });
    const token = await at.toJwt();

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ token, url: LIVEKIT_URL, room }));
  } catch (err) {
    console.error('Failed to mint token', err);
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Failed to mint token' }));
  }
});

server.listen(PORT, () => {
  console.log(`Dev token server listening on http://localhost:${PORT}`);
});
