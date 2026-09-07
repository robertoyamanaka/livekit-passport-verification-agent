# agent — the closing-call voice+vision worker

A [LiveKit Agents](https://docs.livekit.io/agents/) worker: "Miguel," a
car-financing closing-call persona. One OpenAI Realtime session handles both
the sales conversation and watching the customer's camera to read a passport
— there's no separate vision-inference call. See the top of
[`src/agent.py`](src/agent.py) for the fuller story, including two real
reliability bugs hit during development and how they were fixed.

## Setup

```bash
uv sync
cp .env.example .env.local
```

Fill in `.env.local`:

| Variable | Where to get it |
|---|---|
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Your [LiveKit Cloud](https://cloud.livekit.io/) project settings |
| `OPENAI_API_KEY` | An OpenAI key with Realtime API access |
| `RESEND_API_KEY` | [Resend](https://resend.com/) — only needed for the contract-email step |

The agent fails fast at startup with a clear message if any of these are
missing, rather than surfacing a cryptic error mid-call.

## Running

```bash
uv run python src/agent.py console   # talk to it directly in the terminal, no LiveKit room/web app needed
uv run python src/agent.py dev       # connects to your LiveKit project, joins rooms dispatched to it — pair with the web app
```

`console` mode is the fastest way to iterate on the conversation/prompt
itself. It won't exercise the video-capture or e-signature flow — for that
you need `dev` mode plus the `web/` app running locally (see the root
[`README.md`](../README.md)).

### Deploying to LiveKit Cloud

Once you have a [LiveKit Cloud](https://cloud.livekit.io/) hosted-agent
project set up (`lk agent create`), push secrets instead of relying on a
local `.env.local`:

```bash
lk agent update-secrets --secrets-file .env.local
```

## Project layout

```
src/agent.py           The agent itself: system prompt, function tools
                        (show_passport_guide, capture_and_verify_passport),
                        the signature-received handler, entrypoint/session
                        wiring.
src/contract_pdf.py     Contract copy + signed-PDF rendering (reportlab).
                        Single source of truth for vehicle/company name and
                        contract text — the same text is shown on screen and
                        baked into the final PDF, so they can't drift apart.
src/contract_email.py   Emails the signed PDF via Resend.
src/topics.py           LiveKit Text Stream topic name constants, shared
                        with web/src/app/models/events.ts on the other side
                        of the connection.
tests/                  pytest — see the root README's Testing section.
```

## Testing

```bash
uv run pytest
uv run ruff check .
```

Covers the pure/mockable logic (contract rendering, fuzzy identity matching,
dispatch-metadata parsing, contract email with `resend` mocked out — no
network calls). The live realtime session itself isn't practically
unit-testable and is verified by hand.
