import { Service } from '@angular/core';

/**
 * Holds the LiveKit connection details minted by the intro screen (see Intro)
 * for the call screen to pick up (see Call). A plain in-memory handoff is
 * enough here — this is a single-flow demo, not a multi-tab app — and it
 * naturally forces a fresh /intro visit (and a fresh token) on page reload
 * instead of trying to resume a stale room.
 */
export interface PendingConnection {
  token: string;
  url: string;
  room: string;
  customerName: string;
}

@Service()
export class Connection {
  private pending: PendingConnection | null = null;

  set(value: PendingConnection): void {
    this.pending = value;
  }

  /** Reads and clears the pending connection so it can't be reused across reloads. */
  consume(): PendingConnection | null {
    const value = this.pending;
    this.pending = null;
    return value;
  }
}
