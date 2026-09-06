import { Service, signal } from '@angular/core';
import { Room, RoomEvent, Track } from 'livekit-client';
import { AgentStateEvent, CapturedPhotoEvent, TranscriptEvent, VerdictEvent } from '../models/events';

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

    room.registerTextStreamHandler('transcript', (reader) => {
      reader
        .readAll()
        .then((text) => {
          const event = JSON.parse(text) as TranscriptEvent;
          this.transcript.update((list) => [...list, event]);
        })
        .catch((err) => console.error('Failed to read transcript stream', err));
    });

    room.registerTextStreamHandler('agent_state', (reader) => {
      reader
        .readAll()
        .then((text) => {
          const event = JSON.parse(text) as AgentStateEvent;
          this.awaitingDocument.set(event.state === 'awaiting_document');
        })
        .catch((err) => console.error('Failed to read agent_state stream', err));
    });

    room.registerTextStreamHandler('captured_photo', (reader) => {
      reader
        .readAll()
        .then((text) => {
          this.capturedPhoto.set(JSON.parse(text) as CapturedPhotoEvent);
          this.awaitingDocument.set(false);
        })
        .catch((err) => console.error('Failed to read captured_photo stream', err));
    });

    room.registerTextStreamHandler('verdict', (reader) => {
      reader
        .readAll()
        .then((text) => this.verdict.set(JSON.parse(text) as VerdictEvent))
        .catch((err) => console.error('Failed to read verdict stream', err));
    });

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

  /** Retries audio playback from a click handler — browsers allow this even
   * when the earlier automatic startAudio() call was blocked. */
  async retryAudio(): Promise<void> {
    if (!this.room) return;
    await this.room.startAudio().catch(() => undefined);
    this.audioBlocked.set(!this.room.canPlaybackAudio);
  }

  disconnect(): void {
    this.room?.disconnect();
    this.room = null;
  }
}
