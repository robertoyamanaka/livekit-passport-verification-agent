import { describe, expect, it } from 'vitest';
import { Connection, PendingConnection } from './connection';

describe('Connection', () => {
  const sample: PendingConnection = {
    token: 'jwt',
    url: 'wss://x.livekit.cloud',
    room: 'cierre-1',
    customerName: 'Roberto',
  };

  it('returns null when nothing has been set', () => {
    expect(new Connection().consume()).toBeNull();
  });

  it('returns what was set, exactly once', () => {
    const connection = new Connection();
    connection.set(sample);

    expect(connection.consume()).toEqual(sample);
    expect(connection.consume()).toBeNull();
  });

  it('a second set() replaces the first, unconsumed value', () => {
    const connection = new Connection();
    connection.set(sample);
    connection.set({ ...sample, customerName: 'Someone Else' });

    expect(connection.consume()?.customerName).toBe('Someone Else');
  });
});
