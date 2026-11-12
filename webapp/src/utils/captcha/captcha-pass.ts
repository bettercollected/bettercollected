import { CaptchaUnavailable, SolveOptions, solveChallenge } from './solve';
import { CaptchaChallenge } from './solver-core';

/** A proof expires 15 minutes after it was issued; one this old is solved again in the background. */
export const REFRESH_AFTER_MS = 12 * 60 * 1000;
/** The wait is silent for this long; after it the page says "Almost ready to send...". */
export const SLOW_AFTER_MS = 1500;

export type ChallengeFetcher = () => Promise<CaptchaChallenge>;

interface Ready {
    proof: string;
    at: number;
}

interface Deps {
    solve?: (challenge: CaptchaChallenge) => Promise<string>;
    now?: () => number;
    setTimer?: (run: () => void, ms: number) => unknown;
    clearTimer?: (id: unknown) => void;
}

/**
 * The proofs of one form, kept in memory only: nothing is written to the device.
 * `warm` starts a solve (after the respondent's first interaction); `take` hands
 * out one finished proof (a proof is single use) or waits for the one being
 * solved, and starts the next in the background straight after, so a retry is
 * normally ready at once. A proof 12 minutes old is replaced by a fresh one.
 */
export class CaptchaPass {
    private ready: Ready | null = null;
    private pending: Promise<Ready> | null = null;
    private generation = 0;
    private queue: Promise<void> = Promise.resolve();
    private fetcher: ChallengeFetcher | null = null;
    private refresh: unknown = null;
    private readonly solve: (challenge: CaptchaChallenge) => Promise<string>;
    private readonly now: () => number;
    private readonly setTimer: (run: () => void, ms: number) => unknown;
    private readonly clearTimer: (id: unknown) => void;

    constructor(deps: Deps = {}, solveOptions?: SolveOptions) {
        this.solve = deps.solve ?? ((challenge) => solveChallenge(challenge, solveOptions));
        this.now = deps.now ?? (() => Date.now());
        this.setTimer = deps.setTimer ?? ((run, ms) => setTimeout(run, ms));
        this.clearTimer = deps.clearTimer ?? ((id) => clearTimeout(id as ReturnType<typeof setTimeout>));
    }

    /** Is a proof finished or being solved? */
    get busy(): boolean {
        return this.ready !== null || this.pending !== null;
    }

    /** Start solving in the background unless a fresh proof is there or on its way. Never throws. */
    warm(fetcher: ChallengeFetcher): void {
        this.fetcher = fetcher;
        if (this.ready && this.now() - this.ready.at < REFRESH_AFTER_MS) return;
        if (this.pending) return;
        this.start(fetcher).catch(() => {});
    }

    private start(fetcher: ChallengeFetcher): Promise<Ready> {
        const generation = this.generation;
        const run = (async () => {
            const challenge = await fetcher();
            const proof = await this.solve(challenge);
            return { proof, at: this.now() };
        })();
        this.pending = run;
        run.then(
            (ready) => {
                if (generation !== this.generation) return;
                if (this.pending === run) this.pending = null;
                this.ready = ready;
                this.scheduleRefresh();
            },
            () => {
                if (this.pending === run) this.pending = null;
            }
        );
        return run;
    }

    private scheduleRefresh() {
        if (this.refresh !== null) this.clearTimer(this.refresh);
        this.refresh = this.setTimer(() => {
            this.refresh = null;
            this.ready = null;
            if (this.fetcher) this.warm(this.fetcher);
        }, REFRESH_AFTER_MS);
    }

    /**
     * One proof for one request. `fresh` drops what is held and solves a new
     * challenge (a refused proof, or a network that changed). `onSlow` is called
     * when the wait passes `SLOW_AFTER_MS`, `onDone` when it ends either way.
     * Rejects with `CaptchaUnavailable` when the browser cannot solve in time.
     */
    async take(fetcher: ChallengeFetcher, options: { fresh?: boolean; onSlow?: () => void; onDone?: () => void } = {}): Promise<string> {
        const timer = options.onSlow ? this.setTimer(options.onSlow, SLOW_AFTER_MS) : null;
        // one at a time: two callers never get the same (single-use) proof
        const run = this.queue.then(() => this.takeNow(fetcher, !!options.fresh));
        this.queue = run.then(
            () => undefined,
            () => undefined
        );
        try {
            return await run;
        } finally {
            if (timer !== null) this.clearTimer(timer);
            options.onDone?.();
        }
    }

    private async takeNow(fetcher: ChallengeFetcher, fresh: boolean): Promise<string> {
        this.fetcher = fetcher;
        if (fresh) this.discard();
        let ready = this.ready && this.now() - this.ready.at < REFRESH_AFTER_MS ? this.ready : null;
        if (!ready) {
            this.ready = null;
            try {
                ready = await (this.pending ?? this.start(fetcher));
            } catch (error) {
                throw error instanceof CaptchaUnavailable ? error : new CaptchaUnavailable();
            }
        }
        if (this.ready === ready) this.ready = null;
        // this one is spent; the next, in the background, right after it is handed out
        if (this.refresh !== null) this.clearTimer(this.refresh);
        this.refresh = null;
        this.warm(fetcher);
        return ready.proof;
    }

    /** Forget what is held, finished or on its way. */
    discard(): void {
        this.generation++;
        this.ready = null;
        this.pending = null;
        if (this.refresh !== null) this.clearTimer(this.refresh);
        this.refresh = null;
    }
}

const passes = new Map<string, CaptchaPass>();

/** The proofs of this form in this browser (one per workspace and form). */
export function captchaPassFor(workspaceId: string, formId: string): CaptchaPass {
    const key = `${workspaceId}:${formId}`;
    let pass = passes.get(key);
    if (!pass) {
        pass = new CaptchaPass();
        passes.set(key, pass);
    }
    return pass;
}

/** For tests. */
export function resetCaptchaPasses(): void {
    passes.forEach((pass) => pass.discard());
    passes.clear();
}
