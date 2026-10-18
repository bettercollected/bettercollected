/**
 * A fixed-window request counter kept in this server process's memory.
 *
 * Each process counts on its own and forgets everything on restart, so with
 * several webapp replicas a caller gets the limit once per replica. That is
 * enough to stop one signed-in person from draining a shared upstream quota;
 * it is not a substitute for limits at the edge.
 */

export interface RateLimitVerdict {
    allowed: boolean;
    // seconds until the window ends, for a Retry-After header (0 when allowed)
    retryAfterSeconds: number;
}

export interface RateLimiter {
    hit(key: string): RateLimitVerdict;
    reset(): void;
}

interface RateLimiterOptions {
    limit: number;
    windowMs: number;
    // keys remembered at most; expired windows go first, then the oldest
    maxKeys?: number;
    now?: () => number;
}

export function createRateLimiter({ limit, windowMs, maxKeys = 10_000, now = Date.now }: RateLimiterOptions): RateLimiter {
    const windows = new Map<string, { count: number; resetAt: number }>();

    const makeRoom = (time: number) => {
        if (windows.size < maxKeys) return;
        for (const [key, window] of windows) {
            if (window.resetAt <= time) windows.delete(key);
        }
        // Map keeps insertion order: the first key is the oldest window
        while (windows.size >= maxKeys) {
            const oldest = windows.keys().next().value;
            if (oldest === undefined) break;
            windows.delete(oldest);
        }
    };

    return {
        hit(key: string): RateLimitVerdict {
            const time = now();
            let window = windows.get(key);
            if (!window || window.resetAt <= time) {
                windows.delete(key);
                makeRoom(time);
                window = { count: 0, resetAt: time + windowMs };
                windows.set(key, window);
            }
            window.count += 1;
            if (window.count > limit) {
                return { allowed: false, retryAfterSeconds: Math.max(1, Math.ceil((window.resetAt - time) / 1000)) };
            }
            return { allowed: true, retryAfterSeconds: 0 };
        },
        reset() {
            windows.clear();
        }
    };
}
