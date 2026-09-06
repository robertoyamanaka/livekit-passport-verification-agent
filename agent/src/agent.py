"""
Closing-call passport-verification agent.

A single OpenAI Realtime session handles both the sales conversation and
native video perception — there is no separate vision-inference call.

This originally ran on Gemini Live (gemini-2.5-flash-native-audio-preview),
which was swapped out for OpenAI's Realtime API after hitting a reproducible
crash: that Gemini model closes the session (WS code 1007, "CONTENT_TYPE_AUDIO
... not supported for this model configuration") when a function call and
spoken audio are generated in the same turn. That's a documented, open
reliability gap for this exact preview model — see livekit/livekit#3679,
livekit/agents#4554, livekit/agents#5742, and LiveKit's community forum
thread on this same error string — not something fixable from our side of the
API. LiveKit's Agent/function_tool/AgentSession abstractions are provider-
agnostic, so the swap only touched the `llm=` construction below; every tool
and the transcript/verdict pipeline are untouched.

A related bug surfaced after that swap during live testing: the model would
sometimes call `show_passport_guide` inside its very first turn, interleaved
with the opening greeting itself. OpenAI's Realtime API cuts the in-flight
audio when a function call arrives mid-response, so the greeting got clipped,
then re-spoken in full once the tool call resolved — an audible stutter/restart.
Prompt wording alone can't guarantee a realtime model won't do this, so the
fix is a code-level guard (`_customer_has_spoken`): the tool no-ops with a
corrective instruction until at least one real user turn has been observed,
the same defense-in-depth pattern already used for `_verdict_sent` on
`capture_and_verify_passport`.

On a validated verdict, the contract is no longer emailed immediately —
instead it's shown on screen for the customer to actually review and sign
(typed name + a drawn signature) before anything is sent. That signature
comes back over a LiveKit text stream the *browser* initiates (topic
`signature`), the reverse direction of every other topic in this file; see
`Assistant.on_signature_received` and its registration in `entrypoint`.
"""

from __future__ import annotations

import asyncio
import base64
import difflib
import json
import logging
import os
import time
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ConversationItemAddedEvent,
    JobContext,
    RunContext,
    cli,
    function_tool,
    room_io,
)
from livekit.agents.utils.images import EncodeOptions
from livekit.agents.utils.images import encode as encode_frame
from livekit.plugins import openai

from contract_email import send_contract_email
from contract_pdf import (
    AMOUNT_FINANCED,
    FINANCE_CO_NAME,
    VEHICLE,
    build_signed_contract_pdf,
    new_contract_number,
    render_contract,
)
from topics import (
    AGENT_STATE,
    CAPTURED_PHOTO,
    CONTRACT_READY,
    CONTRACT_SIGNED,
    SIGNATURE,
    TRANSCRIPT,
    VERDICT,
)

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env.local")

logger = logging.getLogger("passport-verification-agent")

OPENAI_REALTIME_MODEL = "gpt-realtime"
# "echo" is OpenAI's longest-standing, most consistently male-leaning voice —
# matches the Miguel persona. Swapping it is a one-line change if it doesn't
# land right in practice.
OPENAI_REALTIME_VOICE = "echo"

SYSTEM_INSTRUCTIONS = f"""
Eres Miguel, especialista de cierre de ventas en {FINANCE_CO_NAME}, una financiera
de vehículos. Estás en una videollamada con un cliente llamado {{customer_name}}
que ya pasó por todas las etapas previas del proceso de venta (necesidades,
demostración, manejo de objeciones) y ahora está listo para cerrar el
financiamiento de un {VEHICLE}.

Tu tono es cálido, profesional y respetuoso en todo momento — nunca informal,
nunca robótico. Eres un vendedor experimentado cerrando una compra importante,
no un asistente de soporte técnico leyendo un checklist. Cada frase debe sonar
como algo que diría un vendedor real en el momento, nunca como un paso de un
guion narrado en voz alta.

Cuando menciones el vehículo, dilo siempre y exactamente como "{VEHICLE}".
Nunca lo confundas ni lo sustituyas por otra marca o modelo de auto.

Regla general para toda la llamada: nunca llames una función en el mismo turno
en que hablas. Cada función va en su propio turno, completamente silencioso
(sin audio); habla recién en el turno siguiente, una vez que la función haya
respondido.

Sé breve en todo momento — respuestas de una o dos frases, nunca un monólogo.
Esta llamada avanza rápido; no la alargues con rondas de cortesías innecesarias.

Flujo de la llamada:
1. Tu primer turno es solo hablado y corto: saluda a {{customer_name}} por su
   nombre, dale la bienvenida de vuelta como si ya se hubieran reunido antes, y
   pregúntale brevemente cómo está. No llames ninguna función todavía.
2. En cuanto el cliente responda — aunque sea con una frase muy breve —
   reconoce su respuesta con una frase corta y cálida que NO mencione todavía
   la validación de identidad (evita cualquier repetición con el paso 3; algo
   como coincidir brevemente con su ánimo o decir que ya están en la recta
   final). Sin esperar una segunda respuesta suya ni agregar más cortesías,
   llama de inmediato a la función `show_passport_guide` (turno silencioso,
   según la regla general).
3. En tu siguiente turno, ya hablado, conecta en una sola idea fluida — sin
   repetir mecánicamente "voy a validar tu identidad" — el porqué y el qué:
   que para poder entregarle el papeleo y las llaves de su {VEHICLE} primero
   necesitas validar su identidad, y que para eso muestre su pasaporte (o
   cédula/documento de identidad) frente a la cámara y te avise en voz alta
   apenas lo tenga bien posicionado. No le pidas una frase exacta para
   avisarte — cualquier confirmación verbal suya sirve.
4. Observa el video con atención. Cuando puedas leer con claridad el nombre
   completo Y el número de documento en el pasaporte, llama a la función
   `capture_and_verify_passport` con esos datos exactamente como aparecen
   escritos en el documento (turno silencioso). Si todavía no puedes leerlos
   con claridad, NO llames la función — pide amablemente que acerque el
   documento a la cámara o mejore la iluminación.
5. Cuando la función responda, sigue exactamente la instrucción que te da sobre
   qué decir a continuación. Si la identidad fue validada, esa instrucción te
   pedirá invitar al cliente a revisar y firmar el contrato que acaba de
   aparecer en su pantalla — hazlo en un tono cálido y luego guarda silencio
   por completo: no llenes la espera con más comentarios ni le preguntes si ya
   terminó. El cliente necesita tiempo para leer y firmar. Cuando lo haga,
   recibirás instrucciones nuevas en un turno aparte (no será una función que
   tú llames) indicándote exactamente cómo cerrar la llamada — síguelas al
   pie de la letra. Si la identidad no fue validada, no hay contrato que
   firmar: cierra la llamada de una vez (punto 6).
6. Cierra la llamada de forma cálida y profesional.

Nunca reveles que esto es una demostración o que la verificación es simulada.
""".strip()
# ^ Demo-realism instruction, not a claim about the actual verification logic:
# breaking character mid-call ("by the way, this is a portfolio demo") would
# defeat the point of showing a realistic closing call. The verification
# itself is honestly labeled as mocked in the machine-readable event payload
# (see the "confidence_note" field on the "verdict" publish below) — this
# line only keeps the *conversation* in character.


def _normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(value.lower().split())


def names_match(stated_name: str, document_name: str) -> bool:
    """Fuzzy-matches two names for the mocked verdict — good enough to
    reliably demo both outcomes, not a real identity-verification algorithm.

    Matches token-by-token (order-independent) rather than an overall
    string-similarity ratio: a whole-string ratio is misled by shared
    surnames (e.g. "Michael Corleone" vs "Fredo Corleone" scores ~0.67 on
    plain SequenceMatcher despite being different people), which would break
    the one thing this demo needs to reliably show — a real mismatch path.
    """
    stated_tokens = _normalize_name(stated_name).split()
    document_tokens = _normalize_name(document_name).split()
    if not stated_tokens or not document_tokens:
        return False

    shorter, longer = sorted([stated_tokens, document_tokens], key=len)
    remaining = list(longer)

    for token in shorter:
        match_index = next(
            (i for i, candidate in enumerate(remaining) if _tokens_close(token, candidate)),
            None,
        )
        if match_index is None:
            return False
        remaining.pop(match_index)

    return True


def _tokens_close(a: str, b: str, threshold: float = 0.8) -> bool:
    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold


def _now_ms() -> int:
    return int(time.time() * 1000)


class Assistant(Agent):
    def __init__(self, customer_name: str, customer_email: str) -> None:
        super().__init__(
            instructions=SYSTEM_INSTRUCTIONS.replace("{customer_name}", customer_name)
        )
        self.customer_name = customer_name
        self.customer_email = customer_email
        self.room: rtc.Room | None = None
        self._verdict_sent = False
        self._customer_has_spoken = False
        self._contract_ready = False
        self._signature_received = False
        # Filled in by capture_and_verify_passport on a validated verdict;
        # on_signature_received needs these to build the final PDF, but they
        # aren't known until the passport tool actually runs.
        self._contract_number: str | None = None
        self._contract_paragraphs: list[str] | None = None

    def bind_room(self, room: rtc.Room) -> None:
        self.room = room

    def on_conversation_item_added(self, event: ConversationItemAddedEvent) -> None:
        """Mirrors each finalized conversation turn to the frontend's
        transcript panel. Bound via session.on("conversation_item_added", ...)
        in the entrypoint. That event is dispatched synchronously
        (rtc.EventEmitter, not asyncio-aware) — the publish itself is async,
        so it's scheduled as a task rather than awaited here."""
        item = event.item
        if item.type != "message" or item.role not in ("user", "assistant"):
            return
        text = item.text_content
        if not text:
            return
        if item.role == "user":
            self._customer_has_spoken = True
        # The SDK's role is "assistant"/"user"; the frontend's data contract
        # (shared with captured_photo/verdict) uses "agent"/"user".
        role = "agent" if item.role == "assistant" else "user"
        asyncio.create_task(
            self._publish(
                TRANSCRIPT,
                {
                    "type": TRANSCRIPT,
                    "role": role,
                    "text": text,
                    "final": True,
                    "timestamp": _now_ms(),
                },
            )
        )

    async def _publish(self, topic: str, payload: dict) -> None:
        if self.room is None:
            logger.warning("No room bound; dropping %s event", topic)
            return
        try:
            await self.room.local_participant.send_text(json.dumps(payload), topic=topic)
        except Exception:
            logger.exception("Failed to publish %s event", topic)

    async def _capture_customer_frame_b64(self) -> str | None:
        """Grabs one still frame from the customer's video track, JPEG-encoded
        as base64. Independent of how the model itself read the document text
        — this is purely for the UI's captured-photo panel."""
        room = self.room
        if room is None:
            return None

        for participant in room.remote_participants.values():
            for publication in participant.track_publications.values():
                if publication.kind != rtc.TrackKind.KIND_VIDEO or publication.track is None:
                    continue

                stream = rtc.VideoStream.from_track(track=publication.track)
                frame = None
                try:
                    async for event in stream:
                        frame = event.frame
                        break
                finally:
                    await stream.aclose()

                if frame is None:
                    continue

                jpeg_bytes = encode_frame(frame, EncodeOptions(format="JPEG", quality=75))
                return base64.b64encode(jpeg_bytes).decode("ascii")

        return None

    @function_tool(on_duplicate="reject")
    async def show_passport_guide(self, context: RunContext) -> str:
        """Call this in its own silent turn, right before you're about to ask
        the customer to show their passport — never in the same turn as your
        opening greeting. It lights up an on-screen placement guide on their
        camera view. Once it returns, speak in your next turn to ask them to
        show the passport.
        """
        if not self._customer_has_spoken:
            # Guards against calling this during/right after the opening
            # greeting, before the customer has said anything back — see the
            # module docstring for why that's a real (not hypothetical) bug.
            return (
                "Todavía no llegó ninguna respuesta hablada del cliente. No actives la "
                "guía todavía — continúa la conversación con calidez (cómo está, algún "
                "comentario breve) y vuelve a llamar esta función más adelante, en su "
                "propio turno silencioso, cuando el momento se sienta natural."
            )
        await self._publish(
            AGENT_STATE,
            {
                "type": AGENT_STATE,
                "state": "awaiting_document",
                "timestamp": _now_ms(),
            },
        )
        return "Guía visual activada. Ahora pídele que muestre su pasaporte frente a la cámara."

    @function_tool(on_duplicate="reject")
    async def capture_and_verify_passport(
        self,
        context: RunContext,
        document_name: str,
        document_number: str,
    ) -> str:
        """Call this only once the customer's passport name and document
        number are clearly legible on camera. Captures a still frame of the
        document, compares the name on it against the customer's known name,
        and returns the verdict plus the exact next line to say. Call it in
        its own silent turn with no spoken audio alongside it; speak only in
        your next turn, once it returns.

        Args:
            document_name: The full name exactly as printed on the passport.
            document_number: The document/passport number exactly as printed.
        """
        if self._verdict_sent:
            return (
                "Ya se envió un veredicto en esta llamada; continúa con el cierre con naturalidad."
            )

        timestamp = _now_ms()

        photo_b64 = await self._capture_customer_frame_b64()
        if photo_b64:
            await self._publish(
                CAPTURED_PHOTO,
                {
                    "type": CAPTURED_PHOTO,
                    "image_base64": f"data:image/jpeg;base64,{photo_b64}",
                    "captured_at": timestamp,
                },
            )
        else:
            logger.warning("Could not capture a video frame for the passport photo")

        matched = names_match(self.customer_name, document_name)
        status = "validated" if matched else "needs_review"
        reason = (
            "El nombre en el documento coincide con el nombre del cliente."
            if status == "validated"
            else "El nombre en el documento no coincide o no fue legible con claridad."
        )

        await self._publish(
            VERDICT,
            {
                "type": VERDICT,
                "status": status,
                "customer_name": self.customer_name,
                "document_name": document_name,
                "document_number": document_number,
                "reason": reason,
                "confidence_note": "mocked demo — not a real ID verification",
                "timestamp": timestamp,
            },
        )
        self._verdict_sent = True

        if status == "validated":
            contract_number = new_contract_number()
            paragraphs = render_contract(
                contract_number=contract_number,
                customer_name=self.customer_name,
                document_number=document_number,
            )
            # Stashed for on_signature_received, which builds the actual PDF
            # once the customer signs — this tool only shows the contract.
            self._contract_number = contract_number
            self._contract_paragraphs = paragraphs

            await self._publish(
                CONTRACT_READY,
                {
                    "type": CONTRACT_READY,
                    "contract_number": contract_number,
                    "vehicle": VEHICLE,
                    "amount_financed": AMOUNT_FINANCED,
                    "paragraphs": paragraphs,
                    "timestamp": timestamp,
                },
            )
            self._contract_ready = True

            return (
                "Identidad validada. El contrato acaba de aparecer en la pantalla del "
                "cliente para que lo revise y lo firme ahí mismo (puede escribir su "
                "nombre y firmar con el mouse o el touchpad). Invítalo a hacerlo con "
                "calidez, dile que tome el tiempo que necesite, y después no digas nada "
                "más — guarda silencio por completo hasta que recibas nuevas "
                "instrucciones para cerrar la llamada. No llames ninguna función para "
                "esto; la firma llegará por sí sola."
            )
        return (
            "No se pudo validar la identidad automáticamente. Explícale al cliente, con "
            "amabilidad y sin sonar acusatorio, que alguien del equipo se pondrá en "
            "contacto para confirmar sus datos manualmente antes de continuar. Cierra la "
            "llamada con calidez."
        )

    async def on_signature_received(
        self, reader: rtc.TextStreamReader, participant_identity: str
    ) -> None:
        """Handles the `signature` text stream sent by the browser once the
        customer reviews and signs the contract on screen. This is the first
        web→agent use of the Text Streams API in this project (every other
        topic flows agent→web) — registered the same way LiveKit's own
        examples do: a sync callback wrapping this coroutine in
        asyncio.create_task.

        Not a function_tool: the model doesn't call this, the customer's
        browser does. Once the email is sent (or fails), this proactively
        triggers the model to speak via session.generate_reply — the same
        pattern LiveKit's idle-check examples use to speak from a timer
        callback rather than a tool return.
        """
        if self._signature_received:
            logger.warning(
                "Duplicate signature submission from %s; ignoring", participant_identity
            )
            return
        contract_incomplete = (
            not self._contract_ready
            or self._contract_number is None
            or self._contract_paragraphs is None
        )
        if contract_incomplete:
            logger.warning("Signature received before a contract was ready; ignoring")
            return
        self._signature_received = True

        try:
            raw = await reader.read_all()
            payload = json.loads(raw)
            typed_name = str(payload.get("typed_name", "")).strip()
            signature_data_url = str(payload.get("signature_image_base64", ""))
            signed_at = int(payload.get("signed_at") or time.time() * 1000)

            _, _, b64_data = signature_data_url.partition(",")
            signature_png_bytes = base64.b64decode(b64_data) if b64_data else b""

            pdf_bytes = build_signed_contract_pdf(
                contract_number=self._contract_number,
                customer_name=self.customer_name,
                paragraphs=self._contract_paragraphs,
                typed_name=typed_name or self.customer_name,
                signature_png_bytes=signature_png_bytes,
                signed_at_ms=signed_at,
            )
            contract_sent = await send_contract_email(
                self.customer_name, self.customer_email, pdf_bytes
            )
        except Exception:
            logger.exception("Failed to process signature from %s", participant_identity)
            contract_sent = False

        await self._publish(
            CONTRACT_SIGNED,
            {
                "type": CONTRACT_SIGNED,
                "contract_sent": contract_sent,
                "contract_email": self.customer_email,
                "timestamp": _now_ms(),
            },
        )

        if contract_sent:
            instructions = (
                "El cliente acaba de firmar el contrato en pantalla y ya le enviaste la "
                "copia firmada por correo. Confírmaselo con calidez, dile que traiga el "
                "contrato (o simplemente se presente) en la agencia para recibir su nuevo "
                f"{VEHICLE}, y cierra la llamada agradeciéndole su tiempo."
            )
        else:
            instructions = (
                "El cliente firmó el contrato en pantalla, pero el envío del correo falló "
                "por un problema técnico. Dile con calma que hubo un inconveniente enviando "
                "la copia firmada y que se la harás llegar en breve. Cierra la llamada con "
                "calidez."
            )
        await self.session.generate_reply(instructions=instructions)


def _parse_dispatch_metadata(raw: str) -> dict[str, str]:
    """Parses the JSON dispatch metadata set by the token endpoint's
    AgentDispatchClient.createDispatch() call. Available immediately on job
    start via ctx.job.metadata — no need to wait for/poll a remote
    participant to read this data.

    Coerces every value to str so the declared dict[str, str] return type is
    actually true, not just asserted — a nested object/number in the dispatch
    metadata JSON would otherwise flow through untyped and surface as a
    confusing failure much later (e.g. inside an email/PDF call), instead of
    right here where the malformed input actually came from.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Could not parse job dispatch metadata as JSON: %r", raw)
        return {}
    if not isinstance(parsed, dict):
        logger.warning("Job dispatch metadata was valid JSON but not an object: %r", raw)
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def _ensure_required_env_vars() -> None:
    """Fails fast, with a clear message, if a required credential is missing
    — otherwise the first sign of trouble is a cryptic failure deep inside a
    live call (e.g. the Realtime session or the Resend API rejecting an empty
    key), far from the actual cause."""
    required = ["OPENAI_API_KEY", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "RESEND_API_KEY"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy agent/.env.example to agent/.env.local and fill them in."
        )


server = AgentServer()


@server.rtc_session(agent_name="passport-verification-agent")
async def entrypoint(ctx: JobContext) -> None:
    metadata = _parse_dispatch_metadata(ctx.job.metadata)
    customer_name = (metadata.get("customer_name") or "").strip() or "cliente"
    customer_email = metadata.get("email", "")

    await ctx.connect()

    assistant = Assistant(customer_name=customer_name, customer_email=customer_email)
    assistant.bind_room(ctx.room)

    def _handle_signature_stream(reader: rtc.TextStreamReader, participant_identity: str) -> None:
        # Sync callback wrapping the real (async) work — the exact shape
        # LiveKit's own text-stream examples use, since handlers themselves
        # can't be async.
        asyncio.create_task(assistant.on_signature_received(reader, participant_identity))

    ctx.room.register_text_stream_handler(SIGNATURE, _handle_signature_stream)

    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            model=OPENAI_REALTIME_MODEL,
            voice=OPENAI_REALTIME_VOICE,
        ),
        # LiveKit's default (3s) is a one-shot window, armed only on the agent's
        # very first spoken turn, that suppresses interruption-detection while the
        # client's browser-side echo cancellation converges. Miguel's opening
        # greeting runs longer than that at a natural pace, so the window was
        # closing mid-sentence and residual echo of his own voice was getting
        # picked up as the customer interrupting him. Bumped to comfortably cover
        # the greeting; has no effect on barge-in later in the call, since the
        # timer never re-arms after its first firing.
        aec_warmup_duration=6.0,
    )
    session.on("conversation_item_added", assistant.on_conversation_item_added)

    await session.start(
        assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(video_input=True),
    )
    await session.generate_reply()


if __name__ == "__main__":
    _ensure_required_env_vars()
    cli.run_app(server)
