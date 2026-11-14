import { Solver } from './solver-core';

/**
 * The Web Worker that solves a challenge off the main thread, so the page and
 * assistive technology stay responsive. It receives `{ challenge, bits,
 * subpuzzles }` and answers `{ counters }` (or `{ error }`); it reads and
 * stores nothing and makes no request.
 */
interface WorkerScope {
    onmessage: ((event: { data: { challenge: string; bits: number; subpuzzles?: number } }) => void) | null;
    postMessage: (message: unknown) => void;
}
const scope = self as unknown as WorkerScope;

scope.onmessage = (event) => {
    try {
        const { challenge, bits, subpuzzles } = event.data;
        const solver = new Solver(challenge, bits, subpuzzles);
        solver.step(Infinity);
        scope.postMessage({ counters: solver.counters });
    } catch {
        scope.postMessage({ error: true });
    }
};
