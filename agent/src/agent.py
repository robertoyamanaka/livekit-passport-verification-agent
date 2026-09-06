"""
Closing-call passport-verification agent.

A single Gemini Live realtime session handles both the sales conversation and
native video perception — there is no separate vision-inference call. See
PROJECT_BRIEF.md and the implementation plan for the full concept.
"""

from __future__ import annotations

import asyncio
import base64
import difflib
import json
import logging
import time
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    cli,
    function_tool,
    room_io,
)
from livekit.agents.utils.images import EncodeOptions, encode as encode_frame
from livekit.plugins import google

from contract_email import send_contract_email

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env.local")

logger = logging.getLogger("passport-verification-agent")

FINANCE_CO_NAME = "Meridiano Auto Finance"
GEMINI_LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
PARTICIPANT_WAIT_TIMEOUT_S = 15.0

SYSTEM_INSTRUCTIONS = f"""
Eres Sofía, especialista de cierre de ventas en {FINANCE_CO_NAME}, una financiera
de vehículos. Estás en una videollamada con un cliente llamado {{customer_name}}
que ya pasó por todas las etapas previas del proceso de venta (necesidades,
demostración, manejo de objeciones) y ahora está listo para cerrar el
financiamiento de un Ford Mustang.

Tu tono es cálido, profesional y respetuoso en todo momento — nunca informal,
nunca robótico. Eres una vendedora experimentada cerrando una compra importante,
no una asistente de soporte técnico.

Flujo de la llamada:
1. Saluda a {{customer_name}} por su nombre, dale la bienvenida de vuelta como si
   ya se hubieran reunido antes, y menciona brevemente que hoy es el día de
   cerrar todo.
2. Después de un breve intercambio cordial, explica de forma natural que antes
   de finalizar necesitas validar su identidad: pídele amablemente que muestre
   su pasaporte frente a la cámara.
3. Observa el video con atención. Cuando puedas leer con claridad el nombre
   completo Y el número de documento en el pasaporte, llama a la función
   `capture_and_verify_passport` con esos datos exactamente como aparecen
   escritos en el documento. Si todavía no puedes leerlos con claridad, NO
   llames la función — pide amablemente que acerque el documento a la cámara o
   mejore la iluminación.
4. Cuando la función responda, sigue exactamente la instrucción que te da sobre
   qué decir a continuación.
5. Cierra la llamada de forma cálida y profesional.

Nunca reveles que esto es una demostración o que la verificación es simulada.
""".strip()


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


class Assistant(Agent):
    def __init__(self, customer_name: str, customer_email: str) -> None:
        super().__init__(
            instructions=SYSTEM_INSTRUCTIONS.replace("{customer_name}", customer_name)
        )
        self.customer_name = customer_name
        self.customer_email = customer_email
        self.room: rtc.Room | None = None
        self._verdict_sent = False

    def bind_room(self, room: rtc.Room) -> None:
        self.room = room

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
    async def capture_and_verify_passport(
        self,
        context: RunContext,
        document_name: str,
        document_number: str,
    ) -> str:
        """Call this only once the customer's passport name and document
        number are clearly legible on camera. Captures a still frame of the
        document, compares the name on it against the customer's known name,
        and returns the verdict plus the exact next line to say.

        Args:
            document_name: The full name exactly as printed on the passport.
            document_number: The document/passport number exactly as printed.
        """
        if self._verdict_sent:
            return "Ya se envió un veredicto en esta llamada; continúa con el cierre con naturalidad."

        timestamp = int(time.time() * 1000)

        photo_b64 = await self._capture_customer_frame_b64()
        if photo_b64:
            await self._publish(
                "captured_photo",
                {
                    "type": "captured_photo",
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

        contract_sent = False
        if status == "validated":
            contract_sent = await send_contract_email(self.customer_name, self.customer_email)
            if not contract_sent:
                reason += " (hubo un problema técnico enviando el contrato)"

        await self._publish(
            "verdict",
            {
                "type": "verdict",
                "status": status,
                "customer_name": self.customer_name,
                "document_name": document_name,
                "document_number": document_number,
                "reason": reason,
                "confidence_note": "mocked demo — not a real ID verification",
                "contract_sent": contract_sent,
                "contract_email": self.customer_email,
                "timestamp": timestamp,
            },
        )
        self._verdict_sent = True

        if status == "validated" and contract_sent:
            return (
                "Identidad validada y el contrato ya fue enviado por correo. Dile al "
                "cliente, con calidez y profesionalismo, que le enviaste el contrato a su "
                "correo, que lo revise con calma, y que una vez firmado lo traiga a la "
                "agencia para recibir su nuevo Mustang. Luego cierra la llamada "
                "agradeciéndole su tiempo."
            )
        if status == "validated" and not contract_sent:
            return (
                "La identidad fue validada, pero el envío del contrato falló por un "
                "problema técnico. Dile al cliente, con calma y profesionalismo, que hubo "
                "un inconveniente técnico enviando el contrato y que se lo harás llegar en "
                "breve por correo. Cierra la llamada con calidez."
            )
        return (
            "No se pudo validar la identidad automáticamente. Explícale al cliente, con "
            "amabilidad y sin sonar acusatorio, que alguien del equipo se pondrá en "
            "contacto para confirmar sus datos manualmente antes de continuar. Cierra la "
            "llamada con calidez."
        )


async def _wait_for_customer(room: rtc.Room, timeout: float) -> rtc.RemoteParticipant | None:
    """Returns the first remote participant, waiting briefly if none has
    joined yet (agent dispatch usually happens right after the customer
    joins, so this is normally instant)."""
    if room.remote_participants:
        return next(iter(room.remote_participants.values()))

    found: asyncio.Future[rtc.RemoteParticipant] = asyncio.get_running_loop().create_future()

    def _on_connected(participant: rtc.RemoteParticipant) -> None:
        if not found.done():
            found.set_result(participant)

    room.on("participant_connected", _on_connected)
    try:
        return await asyncio.wait_for(found, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("No customer joined within %.0fs; using a generic greeting", timeout)
        return None
    finally:
        room.off("participant_connected", _on_connected)


server = AgentServer()


@server.rtc_session(agent_name="passport-verification-agent")
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    customer = await _wait_for_customer(ctx.room, PARTICIPANT_WAIT_TIMEOUT_S)
    customer_name = (customer.name if customer and customer.name else "").strip() or "cliente"
    customer_email = customer.attributes.get("email", "") if customer else ""

    assistant = Assistant(customer_name=customer_name, customer_email=customer_email)
    assistant.bind_room(ctx.room)

    session = AgentSession(
        llm=google.beta.realtime.RealtimeModel(
            model=GEMINI_LIVE_MODEL,
            proactivity=True,
            enable_affective_dialog=True,
        ),
    )

    await session.start(
        assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(video_input=True),
    )
    await session.generate_reply()


if __name__ == "__main__":
    cli.run_app(server)
