import { CaptchaChallenge, Solver, proofHeaderValue } from './solver-core';

/** The most time the browser gives a solve before it stops and says so. */
export const SOLVE_BUDGET_MS = 25_000;
/** The main-thread fallback works in slices of about this long, yielding between them. */
export const SLICE_MS = 8;

/** The browser could not finish the calculation in time (or at all). */
export class CaptchaUnavailable extends Error {
    constructor() {
        super('The automatic spam check could not be completed in this browser.');
        this.name = 'CaptchaUnavailable';
    }
}

export interface SolveOptions {
    /** Makes the worker; none (or a throwing one) means the main thread solves. */
    createWorker?: (() => Worker) | null;
    budgetMs?: number;
    sliceMs?: number;
    now?: () => number;
    yieldToMain?: () => Promise<void>;
}

/** The worker's address: a static file of this site (public/captcha/worker-v1.js, built by `yarn build:captcha-worker`), never a third party. */
export const WORKER_PATH = '/captcha/worker-v1.js';
const defaultWorker = () => new Worker(`${process.env.__NEXT_ROUTER_BASEPATH ?? ''}${WORKER_PATH}`);

const defaultYield = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

/** Solve in a Web Worker; `null` when none can be started or it fails (sandboxed embeds, no Worker). */
function solveInWorker(challenge: CaptchaChallenge, make: () => Worker, remainingMs: () => number): Promise<number[] | null> {
    return new Promise((resolve, reject) => {
        let worker: Worker;
        try {
            worker = make();
        } catch {
            resolve(null);
            return;
        }
        const finish = (done: () => void) => {
            clearTimeout(timer);
            worker.terminate();
            done();
        };
        const timer = setTimeout(() => finish(() => reject(new CaptchaUnavailable())), Math.max(0, remainingMs()));
        worker.onmessage = (event: MessageEvent) => finish(() => (Array.isArray(event.data?.counters) ? resolve(event.data.counters) : resolve(null)));
        worker.onerror = () => finish(() => resolve(null));
        worker.onmessageerror = () => finish(() => resolve(null));
        try {
            worker.postMessage({ challenge: challenge.challenge, bits: challenge.bits, subpuzzles: challenge.subpuzzles });
        } catch {
            finish(() => resolve(null));
        }
    });
}

/**
 * The `X-BC-Captcha` header value for `challenge`. Solved in a Web Worker; with
 * none available (no `Worker`, or an embed sandboxed without `allow-same-origin`,
 * where a worker script from the form's host cannot start) the same code runs on
 * the main thread in short slices that yield between them. Rejects with
 * `CaptchaUnavailable` after `budgetMs`.
 */
export async function solveChallenge(challenge: CaptchaChallenge, options: SolveOptions = {}): Promise<string> {
    const now = options.now ?? (() => performance.now());
    const started = now();
    const budget = options.budgetMs ?? SOLVE_BUDGET_MS;
    const remaining = () => budget - (now() - started);

    const make = options.createWorker === undefined ? (typeof Worker === 'undefined' ? null : defaultWorker) : options.createWorker;
    if (make) {
        const counters = await solveInWorker(challenge, make, remaining);
        if (counters) return proofHeaderValue(challenge.challenge, counters);
    }

    const solver = new Solver(challenge.challenge, challenge.bits, challenge.subpuzzles, now);
    const yieldToMain = options.yieldToMain ?? defaultYield;
    while (!solver.step(options.sliceMs ?? SLICE_MS)) {
        if (remaining() <= 0) throw new CaptchaUnavailable();
        await yieldToMain();
    }
    return proofHeaderValue(challenge.challenge, solver.counters);
}
