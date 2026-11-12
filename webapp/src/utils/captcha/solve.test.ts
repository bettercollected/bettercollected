// The browser's half of the automatic spam check: the hash agrees with the
// server's (counters computed with Python's hashlib), the worker is used when
// there is one, and the main thread solves in short slices when there is not
// (sandboxed embeds, no Worker), within a hard budget.
import { describe, expect, it, vi } from 'vitest';

import { CaptchaUnavailable, SOLVE_BUDGET_MS, WORKER_PATH, solveChallenge } from './solve';
import { CAPTCHA_HEADER, SUBPUZZLES, Solver, hasLeadingZeroBits, proofHeaderValue } from './solver-core';

// counters for this challenge at 14 bits, found with hashlib.sha256(f"{challenge}:{i}:{c}") as the server checks them
const CHALLENGE = 'eyJ2IjoxfQ.c2lnbmF0dXJl';
const SERVER_COUNTERS = [157, 3413, 1056, 1336, 1683, 668, 8198, 99];
const challenge = (over = {}) => ({ challenge: CHALLENGE, algorithm: 'sha256-lz', bits: 14, subpuzzles: SUBPUZZLES, expiresAt: 0, ...over });

describe('the hash', () => {
    it('counts leading zero bits as the server does', () => {
        expect(hasLeadingZeroBits(Uint8Array.of(0, 0, 0xff), 16)).toBe(true);
        expect(hasLeadingZeroBits(Uint8Array.of(0, 0x1f), 11)).toBe(true);
        expect(hasLeadingZeroBits(Uint8Array.of(0, 0x20), 11)).toBe(false);
        expect(hasLeadingZeroBits(Uint8Array.of(0x80), 1)).toBe(false);
        expect(hasLeadingZeroBits(Uint8Array.of(0x7f), 1)).toBe(true);
        expect(hasLeadingZeroBits(Uint8Array.of(1), 0)).toBe(true);
    });

    it('finds the same counters as the server verifies (bits - 3 zero bits each, 8 of them)', () => {
        const solver = new Solver(CHALLENGE, 14);
        expect(solver.step(Infinity)).toBe(true);
        expect(solver.counters).toEqual(SERVER_COUNTERS);
    });

    it('works in slices and arrives at the same counters', () => {
        let tick = 0;
        const solver = new Solver(CHALLENGE, 14, SUBPUZZLES, () => (tick += 5));
        let slices = 0;
        while (!solver.step(8)) slices++;
        expect(slices).toBeGreaterThan(1);
        expect(solver.counters).toEqual(SERVER_COUNTERS);
        expect(solver.done).toBe(true);
    });

    it('writes the header as the server reads it', () => {
        expect(proofHeaderValue('a.b', [1, 22, 333])).toBe('a.b.1,22,333');
        expect(CAPTCHA_HEADER).toBe('X-BC-Captcha');
    });
});

/** A Worker that answers like captcha-worker.ts does. */
class FakeWorker {
    static created = 0;
    onmessage: ((event: { data: unknown }) => void) | null = null;
    onerror: (() => void) | null = null;
    onmessageerror: (() => void) | null = null;
    terminated = false;
    constructor() {
        FakeWorker.created++;
    }
    postMessage(message: { challenge: string; bits: number; subpuzzles: number }) {
        const solver = new Solver(message.challenge, message.bits, message.subpuzzles);
        solver.step(Infinity);
        queueMicrotask(() => this.onmessage?.({ data: { counters: solver.counters } }));
    }
    terminate() {
        this.terminated = true;
    }
}

describe('solving a challenge', () => {
    it('uses a Web Worker when there is one, and ends it', async () => {
        let worker: FakeWorker | undefined;
        const proof = await solveChallenge(challenge(), {
            createWorker: () => (worker = new FakeWorker()) as unknown as Worker
        });
        expect(proof).toBe(proofHeaderValue(CHALLENGE, SERVER_COUNTERS));
        expect(worker!.terminated).toBe(true);
    });

    it('starts the static same-origin worker file by default', async () => {
        const started: string[] = [];
        class Stub extends FakeWorker {
            constructor(url: string) {
                super();
                started.push(url);
            }
        }
        vi.stubGlobal('Worker', Stub);
        try {
            const proof = await solveChallenge(challenge());
            expect(proof).toBe(proofHeaderValue(CHALLENGE, SERVER_COUNTERS));
        } finally {
            vi.unstubAllGlobals();
        }
        expect(started).toEqual([WORKER_PATH]);
        expect(WORKER_PATH).toBe('/captcha/worker-v1.js');
    });

    it('falls back to the main thread when no Worker can be started (a sandboxed embed)', async () => {
        const yields = vi.fn(() => Promise.resolve());
        const proof = await solveChallenge(challenge({ bits: 17 }), {
            createWorker: () => {
                throw new DOMException('The operation is insecure.', 'SecurityError');
            },
            sliceMs: 0,
            yieldToMain: yields
        });
        expect(proof.startsWith(`${CHALLENGE}.`)).toBe(true);
        expect(proof.split('.').pop()!.split(',')).toHaveLength(SUBPUZZLES);
        // it yielded between slices: the page stayed responsive
        expect(yields.mock.calls.length).toBeGreaterThan(0);
    });

    it('falls back when there is no Worker at all, and when the worker fails or answers badly', async () => {
        const expected = proofHeaderValue(CHALLENGE, SERVER_COUNTERS);
        expect(await solveChallenge(challenge(), { createWorker: null })).toBe(expected);
        const failing = () => {
            const w = new FakeWorker();
            w.postMessage = () => queueMicrotask(() => w.onerror?.());
            return w as unknown as Worker;
        };
        expect(await solveChallenge(challenge(), { createWorker: failing })).toBe(expected);
        const nonsense = () => {
            const w = new FakeWorker();
            w.postMessage = () => queueMicrotask(() => w.onmessage?.({ data: { error: true } }));
            return w as unknown as Worker;
        };
        expect(await solveChallenge(challenge(), { createWorker: nonsense })).toBe(expected);
    });

    it('gives up after the hard budget and says so', async () => {
        let clock = 0;
        await expect(
            solveChallenge(challenge({ bits: 21 }), {
                createWorker: null,
                now: () => (clock += 1000),
                yieldToMain: () => Promise.resolve()
            })
        ).rejects.toBeInstanceOf(CaptchaUnavailable);
        expect(SOLVE_BUDGET_MS).toBe(25_000);
    });

    it('gives up on a worker that never answers', async () => {
        vi.useFakeTimers();
        try {
            const silent = () => {
                const w = new FakeWorker();
                w.postMessage = () => {};
                return w as unknown as Worker;
            };
            const outcome = solveChallenge(challenge(), { createWorker: silent, budgetMs: 25_000 }).catch((e) => e);
            await vi.advanceTimersByTimeAsync(25_001);
            expect(await outcome).toBeInstanceOf(CaptchaUnavailable);
        } finally {
            vi.useRealTimers();
        }
    });
});
