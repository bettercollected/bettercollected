/**
 * The builder's save queue (used by AutoSaveForm).
 *
 * - One save in flight at a time; edits made meanwhile are coalesced, so
 *   only the latest state is sent next.
 * - Network failures retry on their own with backoff; a save the server
 *   refuses waits for the next edit.
 * - Every save carries the version (`updatedAt`) the editor last saw. When
 *   the server answers that the form changed elsewhere (409), the queue stops
 *   and never overwrites it.
 */

export type SaveOutcome =
    | { kind: 'saved'; version?: string | null }
    /** The stored form is newer than the version sent: nothing was written. */
    | { kind: 'conflict' }
    /** The request did not reach the server, or a gateway failed: retry. */
    | { kind: 'retryable' }
    /** The server refused the save; sending it again won't help. */
    | { kind: 'failed' };

export type SaveQueueState = 'idle' | 'saving' | 'saved' | 'retrying' | 'error' | 'conflict';

export type FlushResult = 'saved' | 'conflict' | 'error';

export interface SaveQueueOptions {
    send: (body: string, version: string | null) => Promise<SaveOutcome>;
    onState?: (state: SaveQueueState, info: { savedAt?: number; retryInMs?: number }) => void;
    /** Waits between retries of a network failure; the last one repeats. */
    backoffMs?: number[];
}

export const DEFAULT_BACKOFF_MS = [1000, 2000, 5000, 10000, 30000];

/** Milliseconds of an ISO time; one without a zone is UTC (as the API stores it). */
export function versionTime(version: string | null | undefined): number {
    if (!version) return Number.NaN;
    const hasZone = /([zZ]|[+-]\d\d:?\d\d)$/.test(version);
    return Date.parse(hasZone ? version : `${version}Z`);
}

/** The later of two versions; an unreadable one never wins. */
export function laterVersion(current: string | null, candidate: string | null | undefined): string | null {
    if (!candidate) return current;
    if (!current) return candidate;
    const a = versionTime(current);
    const b = versionTime(candidate);
    if (Number.isNaN(a)) return candidate;
    if (Number.isNaN(b)) return current;
    return b > a ? candidate : current;
}

export class SaveQueue {
    private readonly options: SaveQueueOptions;
    private send: SaveQueueOptions['send'];
    private pending: string | null = null;
    private inFlightBody: string | null = null;
    private lastSavedBody: string | null = null;
    private retryTimer: ReturnType<typeof setTimeout> | null = null;
    private attempt = 0;
    private waiters: Array<(result: FlushResult) => void> = [];
    private disposed = false;
    state: SaveQueueState = 'idle';
    version: string | null;

    constructor(options: SaveQueueOptions, initialVersion: string | null = null) {
        this.options = options;
        this.send = options.send;
        this.version = initialVersion;
    }

    /** Swap the sender (it closes over component state that changes). */
    setSender(send: SaveQueueOptions['send']) {
        this.send = send;
    }

    /** The state the server already has: opening a form is not an edit. */
    setBaseline(body: string) {
        this.lastSavedBody = body;
    }

    /** A newer version saved by this editor some other way (e.g. an AI edit). */
    adoptVersion(version: string | null | undefined) {
        this.version = laterVersion(this.version, version);
    }

    /** What the server will hold once everything queued has been sent. */
    knownBody(): string | null {
        return this.pending ?? this.inFlightBody ?? this.lastSavedBody;
    }

    /** True while something is not (yet) stored. */
    hasUnsaved(): boolean {
        return this.pending !== null || this.inFlightBody !== null || this.state === 'retrying' || this.state === 'error' || this.state === 'conflict';
    }

    enqueue(body: string) {
        if (this.disposed) return;
        if (body === this.knownBody() && this.state !== 'error') return;
        this.pending = body;
        if (this.state === 'conflict') return;
        if (this.state === 'error') this.setState('idle');
        this.pump();
    }

    /** Send a retry now (e.g. the browser came back online). */
    retryNow() {
        if (!this.retryTimer) return;
        clearTimeout(this.retryTimer);
        this.retryTimer = null;
        this.pump();
    }

    /** Resolves once everything queued is stored, or it can't be. */
    flush(): Promise<FlushResult> {
        const settled = this.settledResult();
        if (settled) return Promise.resolve(settled);
        return new Promise((resolve) => this.waiters.push(resolve));
    }

    dispose() {
        this.disposed = true;
        if (this.retryTimer) clearTimeout(this.retryTimer);
        this.retryTimer = null;
    }

    private settledResult(): FlushResult | null {
        if (this.state === 'conflict') return 'conflict';
        if (this.state === 'error' && this.pending === null && this.inFlightBody === null) return 'error';
        if (this.pending === null && this.inFlightBody === null && !this.retryTimer) return 'saved';
        return null;
    }

    private settle() {
        const result = this.settledResult();
        if (!result) return;
        const waiters = this.waiters;
        this.waiters = [];
        waiters.forEach((resolve) => resolve(result));
    }

    private setState(state: SaveQueueState, info: { savedAt?: number; retryInMs?: number } = {}) {
        this.state = state;
        this.options.onState?.(state, info);
    }

    private async pump(): Promise<void> {
        if (this.disposed || this.inFlightBody !== null || this.pending === null || this.retryTimer || this.state === 'conflict') return;
        const body = this.pending;
        this.pending = null;
        this.inFlightBody = body;
        this.setState('saving');

        let outcome: SaveOutcome;
        try {
            outcome = await this.send(body, this.version);
        } catch {
            outcome = { kind: 'retryable' };
        }
        this.inFlightBody = null;
        if (this.disposed) return;

        if (outcome.kind === 'saved') {
            this.lastSavedBody = body;
            this.attempt = 0;
            this.adoptVersion(outcome.version);
            if (this.pending !== null && this.pending !== body) {
                this.pump();
                return;
            }
            this.pending = null;
            this.setState('saved', { savedAt: Date.now() });
        } else if (outcome.kind === 'conflict') {
            // Keep the unsaved state around, but never send it.
            this.pending = this.pending ?? body;
            this.setState('conflict');
        } else if (outcome.kind === 'retryable') {
            if (this.pending === null) this.pending = body;
            const backoff = this.options.backoffMs ?? DEFAULT_BACKOFF_MS;
            const wait = backoff[Math.min(this.attempt, backoff.length - 1)];
            this.attempt += 1;
            this.retryTimer = setTimeout(() => {
                this.retryTimer = null;
                this.pump();
            }, wait);
            this.setState('retrying', { retryInMs: wait });
            return;
        } else {
            this.attempt = 0;
            if (this.pending !== null && this.pending !== body) {
                // A newer edit may well be valid: send it.
                this.pump();
                return;
            }
            this.pending = null;
            this.setState('error');
        }
        this.settle();
    }
}
