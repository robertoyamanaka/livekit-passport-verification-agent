# web — landing page + call screen

The Angular 22 half of the demo: a landing page that collects the customer's
name/email and starts a call, and the call screen itself (video, live
transcript, passport-verification status, and the in-call contract
e-signature panel). See the root [`README.md`](../README.md) for the
project as a whole and how this talks to `agent/`.

## Local setup

Requires Node matching `@angular/cli`'s minimum (v22.22.3, v24.15.0, or
v26.0.0+ — check with `node -v`).

```bash
npm install
cp .env.example .env   # LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
```

This app has no backend of its own beyond one serverless function
([`api/token.ts`](api/token.ts)) that dispatches the agent into a room and
mints a short-lived LiveKit join token — the LiveKit API secret never reaches
the browser. Locally, that function needs a stand-in server since there's no
`vercel dev` in this workflow:

**Terminal 1:**

```bash
npm run dev:token   # plain Node re-implementation of api/token.ts, for local dev only
```

**Terminal 2:**

```bash
npm start            # ng serve; proxy.conf.json forwards /api/* to the dev token server
```

Open `http://localhost:4200`. You'll also need the `agent/` worker running
(`uv run python src/agent.py dev`) for a call to actually connect to
anything — see the root README's quick start.

## Testing, linting, formatting

```bash
npm test            # Vitest, via Angular's native unit-test builder — no browser required
npm run test:coverage
npm run lint         # ESLint (angular-eslint)
npm run format:check # Prettier
```

## Building

```bash
npm run build
```

Production build output goes to `dist/web`. Set up for Vercel deployment —
[`vercel.json`](vercel.json) has the SPA rewrite rule `api/token.ts` needs.
