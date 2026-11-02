import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SaveOutcome, SaveQueue, SaveQueueState, laterVersion, versionTime } from './autosave-queue';

/** A send() whose calls the test answers one by one. */
function controlledSend() {
    const calls: Array<{ body: string; version: string | null; answer: (outcome: SaveOutcome) => Promise<void> }> = [];
    const send = vi.fn(
        (body: string, version: string | null) =>
            new Promise<SaveOutcome>((resolve) => {
                calls.push({
                    body,
                    version,
                    answer: async (outcome) => {
                        resolve(outcome);
                        // let the queue react
                        await Promise.resolve();
                        await Promise.resolve();
                    }
                });
            })
    );
    return { send, calls };
}

function makeQueue(initialVersion: string | null = 'v0', backoffMs?: number[]) {
    const { send, calls } = controlledSend();
    const states: SaveQueueState[] = [];
    const queue = new SaveQueue({ send, backoffMs, onState: (state) => states.push(state) }, initialVersion);
    queue.setBaseline('loaded');
    return { queue, send, calls, states };
}

describe('SaveQueue', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it('sends one save at a time and coalesces edits made meanwhile into the latest', async () => {
        const { queue, send, calls } = makeQueue();
        queue.enqueue('a');
        queue.enqueue('b');
        queue.enqueue('c');
        expect(send).toHaveBeenCalledTimes(1);
        expect(calls[0].body).toBe('a');

        await calls[0].answer({ kind: 'saved', version: 'v1' });
        // b was overtaken by c: only the latest state is sent next
        expect(send).toHaveBeenCalledTimes(2);
        expect(calls[1]).toMatchObject({ body: 'c', version: 'v1' });

        await calls[1].answer({ kind: 'saved', version: 'v2' });
        expect(send).toHaveBeenCalledTimes(2);
        expect(queue.state).toBe('saved');
        expect(queue.hasUnsaved()).toBe(false);
        expect(queue.version).toBe('v2');
    });

    it('does not send what the server already has', () => {
        const { queue, send } = makeQueue();
        queue.enqueue('loaded');
        expect(send).not.toHaveBeenCalled();
    });

    it('retries a network failure with backoff, then sends what was edited meanwhile', async () => {
        const { queue, send, calls, states } = makeQueue('v0', [1000, 4000]);
        queue.enqueue('a');
        await calls[0].answer({ kind: 'retryable' });
        expect(queue.state).toBe('retrying');
        expect(queue.hasUnsaved()).toBe(true);

        queue.enqueue('b');
        expect(send).toHaveBeenCalledTimes(1);
        await vi.advanceTimersByTimeAsync(999);
        expect(send).toHaveBeenCalledTimes(1);
        await vi.advanceTimersByTimeAsync(1);
        // the save whose answer never came goes first, on the version it was sent with
        expect(send).toHaveBeenCalledTimes(2);
        expect(calls[1]).toMatchObject({ body: 'a', version: 'v0' });

        await calls[1].answer({ kind: 'retryable' });
        await vi.advanceTimersByTimeAsync(3999);
        expect(send).toHaveBeenCalledTimes(2);
        await vi.advanceTimersByTimeAsync(1);
        expect(send).toHaveBeenCalledTimes(3);
        expect(calls[2]).toMatchObject({ body: 'a', version: 'v0' });
        await calls[2].answer({ kind: 'saved', version: 'v1' });
        // then the edit made since, on the version that answer gave
        expect(send).toHaveBeenCalledTimes(4);
        expect(calls[3]).toMatchObject({ body: 'b', version: 'v1' });
        await calls[3].answer({ kind: 'saved', version: 'v2' });
        expect(queue.state).toBe('saved');
        expect(states).toEqual(['saving', 'retrying', 'saving', 'retrying', 'saving', 'saving', 'saved']);
    });

    it('treats a thrown send as a network failure', async () => {
        const send = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ kind: 'saved', version: 'v1' });
        const queue = new SaveQueue({ send, backoffMs: [10] });
        queue.enqueue('a');
        await vi.advanceTimersByTimeAsync(0);
        expect(queue.state).toBe('retrying');
        await vi.advanceTimersByTimeAsync(10);
        expect(queue.state).toBe('saved');
        expect(send).toHaveBeenCalledTimes(2);
    });

    it('retries at once when asked (the browser came back online)', async () => {
        const { queue, send, calls } = makeQueue('v0', [30000]);
        queue.enqueue('a');
        await calls[0].answer({ kind: 'retryable' });
        queue.retryNow();
        expect(send).toHaveBeenCalledTimes(2);
    });

    it('stops on a conflict and never overwrites', async () => {
        const { queue, send, calls } = makeQueue();
        queue.enqueue('a');
        const flushed = queue.flush();
        await calls[0].answer({ kind: 'conflict' });
        expect(queue.state).toBe('conflict');
        await expect(flushed).resolves.toBe('conflict');

        queue.enqueue('b');
        await vi.advanceTimersByTimeAsync(60000);
        expect(send).toHaveBeenCalledTimes(1);
        expect(queue.hasUnsaved()).toBe(true);
    });

    it('a refused save waits for the next edit, which is sent', async () => {
        const { queue, send, calls } = makeQueue();
        queue.enqueue('a');
        await calls[0].answer({ kind: 'failed' });
        expect(queue.state).toBe('error');
        expect(queue.hasUnsaved()).toBe(true);
        await vi.advanceTimersByTimeAsync(60000);
        expect(send).toHaveBeenCalledTimes(1);

        queue.enqueue('a2');
        expect(send).toHaveBeenCalledTimes(2);
        await calls[1].answer({ kind: 'saved', version: 'v1' });
        expect(queue.state).toBe('saved');
    });

    it('flush resolves once everything queued is stored', async () => {
        const { queue, calls } = makeQueue();
        await expect(queue.flush()).resolves.toBe('saved');
        queue.enqueue('a');
        let result: string | undefined;
        queue.flush().then((r) => (result = r));
        queue.enqueue('b');
        await calls[0].answer({ kind: 'saved', version: 'v1' });
        expect(result).toBeUndefined();
        await calls[1].answer({ kind: 'saved', version: 'v2' });
        expect(result).toBe('saved');
    });

    it('flush reports a save the server refused', async () => {
        const { queue, calls } = makeQueue();
        queue.enqueue('a');
        const flushed = queue.flush();
        await calls[0].answer({ kind: 'failed' });
        await expect(flushed).resolves.toBe('error');
    });

    it('builds on a newer version the editor stored itself, never an older one', async () => {
        const { queue, calls } = makeQueue('2026-10-17T09:00:00.000Z');
        queue.adoptVersion('2026-10-17T09:00:05.000+00:00');
        queue.adoptVersion('2026-10-17T08:00:00');
        queue.enqueue('a');
        expect(calls[0].version).toBe('2026-10-17T09:00:05.000+00:00');
    });
});

/**
 * A stand-in for the server's whole-form save: it stores a save made on the
 * version it holds; a save made on an older version is refused (409), except
 * the very save it stored last, sent again (its answer was lost), which is
 * answered with the stored version (accept_replay).
 */
function fakeServer(initial = 'v0') {
    let version = initial;
    let counter = 0;
    let stored: string | null = null;
    let previous: string | null = null;
    return {
        stored: () => stored,
        version: () => version,
        /** Another tab saves. */
        otherTabSaves(body: string) {
            previous = version;
            version = `v${++counter}`;
            stored = body;
        },
        /** `lose`: the save is stored but its answer never arrives. */
        async handle(body: string, sent: string | null, lose = false): Promise<SaveOutcome> {
            if (sent === version) {
                previous = version;
                version = `v${++counter}`;
                stored = body;
                return lose ? { kind: 'retryable' } : { kind: 'saved', version };
            }
            if (body === stored && sent === previous) return { kind: 'saved', version };
            return { kind: 'conflict' };
        }
    };
}

describe('a save whose answer was lost', () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    function setup() {
        const server = fakeServer();
        const flags = { lose: true };
        const states: SaveQueueState[] = [];
        const queue = new SaveQueue({ send: (body, version) => server.handle(body, version, flags.lose), backoffMs: [1000], onState: (state) => states.push(state) }, server.version());
        queue.setBaseline('loaded');
        return { server, flags, states, queue };
    }

    it('is not a change made elsewhere: the next save builds on what it stored', async () => {
        const { server, flags, states, queue } = setup();

        queue.enqueue('add a field');
        await vi.advanceTimersByTimeAsync(0);
        expect(queue.state).toBe('retrying');
        expect(server.stored()).toBe('add a field');

        // the person keeps working while it retries
        flags.lose = false;
        queue.enqueue('add a field, then a title');
        await vi.advanceTimersByTimeAsync(1000);
        await vi.advanceTimersByTimeAsync(0);

        expect(states).not.toContain('conflict');
        expect(queue.state).toBe('saved');
        expect(server.stored()).toBe('add a field, then a title');
        expect(queue.version).toBe(server.version());
        expect(queue.hasUnsaved()).toBe(false);
    });

    it('is not a change made elsewhere when nothing else is edited either', async () => {
        const { server, flags, states, queue } = setup();
        queue.enqueue('add a field');
        await vi.advanceTimersByTimeAsync(0);
        flags.lose = false;
        await vi.advanceTimersByTimeAsync(1000);
        expect(queue.state).toBe('saved');
        expect(queue.version).toBe(server.version());
        // and an edit after that goes through on the version the replay answered with
        queue.enqueue('add a field, then a title');
        await vi.advanceTimersByTimeAsync(0);
        expect(queue.state).toBe('saved');
        expect(states).not.toContain('conflict');
    });

    it('still reports a change another tab made meanwhile, and overwrites nothing', async () => {
        const { server, flags, queue } = setup();
        queue.enqueue('add a field');
        await vi.advanceTimersByTimeAsync(0);
        expect(queue.state).toBe('retrying');

        // another tab saves on top of it before the retry
        server.otherTabSaves('from another tab');
        flags.lose = false;
        queue.enqueue('add a field, then a title');
        await vi.advanceTimersByTimeAsync(1000);
        await vi.advanceTimersByTimeAsync(0);

        expect(queue.state).toBe('conflict');
        expect(server.stored()).toBe('from another tab');
    });
});

describe('versions', () => {
    it('reads a time without a zone as UTC, and microseconds', () => {
        expect(versionTime('2026-10-17T09:00:00.123456')).toBe(Date.UTC(2026, 9, 17, 9, 0, 0, 123));
        expect(versionTime('2026-10-17T11:00:00+02:00')).toBe(Date.UTC(2026, 9, 17, 9));
        expect(Number.isNaN(versionTime(null))).toBe(true);
    });

    it('keeps the later one', () => {
        expect(laterVersion(null, 'a')).toBe('a');
        expect(laterVersion('2026-10-17T09:00:00Z', '2026-10-17T09:00:01Z')).toBe('2026-10-17T09:00:01Z');
        expect(laterVersion('2026-10-17T09:00:01Z', '2026-10-17T09:00:00Z')).toBe('2026-10-17T09:00:01Z');
        expect(laterVersion('2026-10-17T09:00:01Z', 'garbage')).toBe('2026-10-17T09:00:01Z');
        expect(laterVersion('2026-10-17T09:00:01Z', undefined)).toBe('2026-10-17T09:00:01Z');
    });
});

describe('a saved outcome that rewrites what waits', () => {
    it('applies savedBody and rewrites the queued body, which is then not re-sent when equal', async () => {
        const sent: string[] = [];
        let answer: (outcome: any) => void = () => undefined;
        const queue = new SaveQueue({
            send: async (body) => {
                sent.push(body);
                if (sent.length === 1) return new Promise((resolve) => (answer = resolve));
                return { kind: 'saved' };
            }
        });
        queue.enqueue('A+rule');
        queue.enqueue('B+rule');
        answer({ kind: 'saved', savedBody: 'A', rewritePending: (body: string) => body.replace('+rule', '') });
        await queue.flush();
        expect(sent).toEqual(['A+rule', 'B']);
        expect(queue.knownBody()).toBe('B');
    });
});
