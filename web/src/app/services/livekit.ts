import { Service, signal } from '@angular/core';
import { Room, RoomEvent, Track } from 'livekit-client';
import type { TextStreamReader } from 'livekit-client';
import {
  AgentStateEvent,
  CapturedPhotoEvent,
  ContractReadyEvent,
  ContractSignedEvent,
  SignatureSubmission,
  TOPICS,
  TranscriptEvent,
  VerdictEvent,
} from '../models/events';

export type AgentPresence =
  | 'connecting'
  | 'waiting_for_agent'
  | 'agent_connected'
  | 'disconnected'
  | 'error';

/**
 * Thin wrapper around livekit-client's Room. There's no official Angular
 * LiveKit SDK, so this service owns the one Room instance for the call
 * screen and exposes its live state as signals the template can bind to
 * directly.
 */
@Service()
export class Livekit {
  private room: Room | null = null;

  readonly presence = signal<AgentPresence>('connecting');
  readonly agentSpeaking = signal(false);
  readonly audioBlocked = signal(false);
  readonly transcript = signal<TranscriptEvent[]>([]);
  readonly awaitingDocument = signal(false);
  readonly capturedPhoto = signal<CapturedPhotoEvent | null>(null);
  readonly verdict = signal<VerdictEvent | null>(null);
  readonly contract = signal<ContractReadyEvent | null>(null);
  readonly contractSigned = signal<ContractSignedEvent | null>(null);
  readonly errorMessage = signal<string | null>(null);

  async connect(url: string, token: string, localVideoEl: HTMLVideoElement): Promise<void> {
    const room = new Room();
    this.room = room;

    room.on(RoomEvent.ParticipantConnected, () => {
      if (this.presence() !== 'error') {
        this.presence.set('agent_connected');
      }
    });
    room.on(RoomEvent.ParticipantDisconnected, () => {
      if (room.remoteParticipants.size === 0 && this.presence() === 'agent_connected') {
        this.presence.set('waiting_for_agent');
        this.agentSpeaking.set(false);
      }
    });
    room.on(RoomEvent.Disconnected, () => this.presence.set('disconnected'));
    room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
      this.agentSpeaking.set(speakers.some((p) => !p.isLocal));
    });

    // livekit-client never auto-attaches remote tracks to the DOM — without
    // this, the agent's synthesized speech is subscribed (bytes flowing) but
    // never actually played, which is silent and easy to mistake for a
    // connection problem. The agent only ever publishes audio (no camera),
    // but this also covers video defensively.
    room.on(RoomEvent.TrackSubscribed, (track) => {
      const el = track.attach();
      if (track.kind === Track.Kind.Audio) {
        el.style.display = 'none';
      }
      document.body.appendChild(el);
    });
    room.on(RoomEvent.TrackUnsubscribed, (track) => {
      track.detach().forEach((el) => el.remove());
    });

    this.registerJsonStream(room, TOPICS.transcript, (event: TranscriptEvent) => {
      this.transcript.update((list) => [...list, event]);
    });
    this.registerJsonStream(room, TOPICS.agentState, (event: AgentStateEvent) => {
      this.awaitingDocument.set(event.state === 'awaiting_document');
    });
    this.registerJsonStream(room, TOPICS.capturedPhoto, (event: CapturedPhotoEvent) => {
      this.capturedPhoto.set(event);
      this.awaitingDocument.set(false);
    });
    this.registerJsonStream(room, TOPICS.verdict, (event: VerdictEvent) => this.verdict.set(event));
    this.registerJsonStream(room, TOPICS.contractReady, (event: ContractReadyEvent) =>
      this.contract.set(event),
    );
    this.registerJsonStream(room, TOPICS.contractSigned, (event: ContractSignedEvent) =>
      this.contractSigned.set(event),
    );

    try {
      await room.connect(url, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      const cameraPublication = await room.localParticipant.setCameraEnabled(true);
      cameraPublication?.track?.attach(localVideoEl);

      // Browsers can block audio autoplay until a user gesture; startAudio()
      // resolves fine in most cases since joining the call was itself a
      // click, but check canPlaybackAudio as a fallback signal so the UI can
      // show a one-tap "enable audio" button if it's still blocked.
      await room.startAudio().catch(() => undefined);
      this.audioBlocked.set(!room.canPlaybackAudio);

      this.presence.set(room.remoteParticipants.size > 0 ? 'agent_connected' : 'waiting_for_agent');
    } catch (err) {
      this.errorMessage.set(
        err instanceof Error ? err.message : 'No se pudo conectar a la llamada.',
      );
      this.presence.set('error');
      throw err;
    }
  }

  /** Registers a JSON-over-text-stream handler for one topic: reads the full
   * stream, parses it, and hands the typed payload to `onEvent`. Every
   * agent->web topic (transcript/agent_state/captured_photo/verdict/
   * contract_ready/contract_signed) followed the same 8-line read-parse-catch
   * shape copy-pasted six times; this is the one place that logic lives now,
   * so a parse failure on any topic is handled identically instead of by
   * whichever copy happened to be edited most recently. */
  private registerJsonStream<T>(room: Room, topic: string, onEvent: (event: T) => void): void {
    room.registerTextStreamHandler(topic, (reader: TextStreamReader) => {
      reader
        .readAll()
        .then((text) => onEvent(JSON.parse(text) as T))
        .catch((err) => console.error(`Failed to read ${topic} stream`, err));
    });
  }

  /** Retries audio playback from a click handler — browsers allow this even
   * when the earlier automatic startAudio() call was blocked. */
  async retryAudio(): Promise<void> {
    if (!this.room) return;
    await this.room.startAudio().catch(() => undefined);
    this.audioBlocked.set(!this.room.canPlaybackAudio);
  }

  /** Sends the customer's signed contract data to the agent. This is the
   * one place in the app that sends a text stream *to* the agent — every
   * other topic flows the other way — so it lives here alongside the rest
   * of the Room interaction rather than in a component. */
  async submitSignature(payload: { typed_name: string; signature_image_base64: string }): Promise<void> {
    if (!this.room) return;
    const message: SignatureSubmission = {
      type: TOPICS.signature,
      typed_name: payload.typed_name,
      signature_image_base64: payload.signature_image_base64,
      signed_at: Date.now(),
    };
    await this.room.localParticipant.sendText(JSON.stringify(message), { topic: TOPICS.signature });
  }

  disconnect(): void {
    this.room?.disconnect();
    this.room = null;
  }
}
