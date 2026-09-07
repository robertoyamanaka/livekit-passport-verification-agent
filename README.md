# Closing Call — Passport Verification Agent

A demo of a real-time voice+vision AI agent conducting a car-financing
"closing call": it talks with the customer over live video, watches their
camera to read a passport and confirm their identity, then walks them through
reviewing and e-signing a contract — all inside a single call, no separate
forms or follow-up steps.

**"Miguel," the agent, is a fictional persona for Meridiano Auto Finance, a
fictional company** — this is a portfolio/demo project, not a real financing
product. The identity check is intentionally a simplified, mocked verification
(honestly labeled as such in its own event payload) built to reliably
demonstrate both a match and a mismatch outcome, not a production KYC/identity
system.

## What it actually does

1. A customer opens a link, enters their name and email, and joins a video
   call.
2. The agent (a single OpenAI Realtime session — one model handles both the
   conversation and watching the video, no separate vision API call) greets
   them by name and asks them to show a passport to the camera.
3. Once it can read the document clearly, it compares the name on it against
   the customer's own name (fuzzy-matched, to tolerate minor typos/accents)
   and either continues to the next step or ends the call for manual review.
4. On a match, a generated contract appears on screen for the customer to
   scroll through, type their name, and draw a signature — a DocuSign-style
   acknowledgment, not just a form to click past.
5. The signed contract is rendered as a PDF server-side and emailed to the
   customer; the agent confirms this out loud and closes the call.

## Architecture

```
web/    Angular 22 app — the landing page + call screen the customer uses,
        plus a small serverless function that dispatches the agent into a
        room and mints a short-lived LiveKit join token.

agent/  Python LiveKit Agents worker — the actual "Miguel" persona, the
        passport-reading/matching logic, and contract PDF generation + email.
```

The two sides only ever talk to each other through
[LiveKit](https://livekit.io/) — the browser and the agent join the same
real-time room, and exchange structured events (transcript lines, capture
photos, the identity verdict, the contract, the signature) over LiveKit's Text
Streams API, in addition to the live audio/video itself.

## Tech stack

- **Agent**: Python, [LiveKit Agents](https://docs.livekit.io/agents/),
  OpenAI's Realtime API (voice + native video understanding in one session),
  [Resend](https://resend.com/) for email, [reportlab](https://www.reportlab.com/)
  for PDF generation. Dependency management via [uv](https://docs.astral.sh/uv/).
- **Web**: Angular 22 (signals, standalone components, the new `@if`/`@for`
  control-flow syntax), [livekit-client](https://github.com/livekit/client-sdk-js),
  [signature_pad](https://github.com/szimek/signature_pad) for the e-signature
  canvas. Vitest for unit tests, ESLint (`angular-eslint`) + Prettier for
  linting/formatting.

## Running it locally

You'll need a [LiveKit Cloud](https://cloud.livekit.io/) project (free tier is
fine), an OpenAI API key with Realtime API access, and a
[Resend](https://resend.com/) API key.

**1. The agent** (see [`agent/README.md`](agent/README.md) for details):

```bash
cd agent
uv sync
cp .env.example .env.local   # fill in LIVEKIT_URL/API_KEY/SECRET, OPENAI_API_KEY, RESEND_API_KEY
uv run python src/agent.py dev
```

**2. The web app** — two more terminals, both from `web/`:

```bash
cp .env.example .env   # fill in the same LiveKit values
npm install
npm run dev:token      # local stand-in for the Vercel token-minting function
```

```bash
npm start               # ng serve, proxies /api/token to the dev token server
```

Open `http://localhost:4200`, fill in a name and email, and join the call.

## Live demo

**[web-lime-alpha-39.vercel.app](https://web-lime-alpha-39.vercel.app)** — the
agent is deployed on [LiveKit Cloud](https://cloud.livekit.io/)'s hosted agent
runtime and the web app on [Vercel](https://vercel.com/). Give it a real name
and a passport (or any ID-shaped document) to see it through, or a mismatched
name to see the other branch.

## Testing

```bash
cd agent && uv run pytest        # backend: contract generation, email, identity matching
cd web && npm test                # frontend: services + component logic
```

Both suites cover the pure/mockable logic — contract rendering, the fuzzy
identity matcher, event-parsing, form/component gating. The live LiveKit
session itself (the actual voice conversation, video perception, and WebRTC
connection) isn't practically unit-testable and is verified by hand, the same
way the original edge cases (name mismatch, audio playback, etc.) were found.

## License

MIT — see [LICENSE](LICENSE).
