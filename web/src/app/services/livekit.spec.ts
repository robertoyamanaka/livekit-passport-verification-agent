import { describe, expect, it, vi } from 'vitest';
import { Livekit } from './livekit';

/** Minimal stand-in for livekit-client's Room, just enough to drive
 * registerJsonStream: it only needs a registerTextStreamHandler that
 * captures the callback so the test can invoke it directly with a fake
 * reader, without any real WebRTC/media setup (not viable in this
 * environment — see the module docstring's note on what's out of scope). */
function fakeRoom() {
  let handler: ((reader: { readAll: () => Promise<string> }) => void) | undefined;
  return {
    registerTextStreamHandler: vi.fn((_topic: string, cb: typeof handler) => {
      handler = cb;
    }),
    // The handler itself returns void (it fires off a .then().catch() chain
    // internally, per registerJsonStream) — a macrotask flush guarantees
    // every microtask in that chain, including the .catch() on a parse
    // failure, has settled before the caller inspects the result.
    trigger: async (text: string) => {
      handler!({ readAll: () => Promise.resolve(text) });
      await new Promise((resolve) => setTimeout(resolve, 0));
    },
  };
}

describe('Livekit.registerJsonStream (private helper)', () => {
  it('parses the stream text as JSON and hands it to onEvent', async () => {
    const livekit = new Livekit();
    const room = fakeRoom();
    const onEvent = vi.fn();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (livekit as any).registerJsonStream(room, 'verdict', onEvent);
    await room.trigger('{"type":"verdict","status":"validated"}');

    expect(onEvent).toHaveBeenCalledWith({ type: 'verdict', status: 'validated' });
  });

  it('logs and swallows a parse failure instead of throwing', async () => {
    const livekit = new Livekit();
    const room = fakeRoom();
    const onEvent = vi.fn();
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (livekit as any).registerJsonStream(room, 'verdict', onEvent);
    await room.trigger('not json');

    expect(onEvent).not.toHaveBeenCalled();
    expect(consoleError).toHaveBeenCalled();
    consoleError.mockRestore();
  });
});
