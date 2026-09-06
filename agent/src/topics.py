"""LiveKit Text Stream topic names.

Every event in this project is a `room.local_participant.send_text(...,
topic=TOPIC)` call whose JSON payload also carries a matching `"type"` field
(the frontend's discriminated-union pattern — see web/src/app/models/events.ts).
Both sides of that pair, plus the browser's `registerTextStreamHandler` calls
in web/src/app/services/livekit.ts, must use the exact same string. Centralizing
them here means a typo becomes an import error instead of a silently-dropped
event.

`signature` is the one topic that flows web -> agent; everything else is
agent -> web.
"""

from __future__ import annotations

TRANSCRIPT = "transcript"
AGENT_STATE = "agent_state"
CAPTURED_PHOTO = "captured_photo"
VERDICT = "verdict"
CONTRACT_READY = "contract_ready"
CONTRACT_SIGNED = "contract_signed"
SIGNATURE = "signature"
