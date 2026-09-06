import { Service, signal } from '@angular/core';
import { Room, RoomEvent } from 'livekit-client';
import { CapturedPhotoEvent, TranscriptEvent, VerdictEvent } from '../models/events';

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
  readonly transcript = signal<TranscriptEvent[]>([]);
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
      }
    });
    room.on(RoomEvent.Disconnected, () => this.presence.set('disconnected'));

    room.registerTextStreamHandler('transcript', (reader) => {
      reader
        .readAll()
        .then((text) => {
          const event = JSON.parse(text) as TranscriptEvent;
          this.transcript.update((list) => [...list, event]);
        })
        .catch((err) => console.error('Failed to read transcript stream', err));
    });

    room.registerTextStreamHandler('captured_photo', (reader) => {
      reader
        .readAll()
        .then((text) => this.capturedPhoto.set(JSON.parse(text) as CapturedPhotoEvent))
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

      this.presence.set(room.remoteParticipants.size > 0 ? 'agent_connected' : 'waiting_for_agent');
    } catch (err) {
      this.errorMessage.set(
        err instanceof Error ? err.message : 'No se pudo conectar a la llamada.',
      );
      this.presence.set('error');
      throw err;
    }
  }

  disconnect(): void {
    this.room?.disconnect();
    this.room = null;
  }
}
