// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const cookieJar = new Map<string, string>();
vi.mock('next/headers', () => ({
    cookies: async () => ({ get: (name: string) => (cookieJar.has(name) ? { name, value: cookieJar.get(name) } : undefined) })
}));

const { signedInUserId } = await import('./unsplash');
const { createRateLimiter } = await import('./rate-limit');

describe('signedInUserId', () => {
    const fetchMock = vi.fn();

    beforeEach(() => {
        cookieJar.clear();
        fetchMock.mockReset();
        vi.stubGlobal('fetch', fetchMock);
    });
    afterEach(() => vi.unstubAllGlobals());

    it("asks the backend's /auth/status with the session cookies only", async () => {
        cookieJar.set('Authorization', 'access');
        cookieJar.set('RefreshToken', 'refresh');
        fetchMock.mockResolvedValue(new Response(JSON.stringify({ id: 'user-1' }), { status: 200 }));

        expect(await signedInUserId()).toBe('user-1');
        const [url, init] = fetchMock.mock.calls[0];
        expect(String(url)).toMatch(/\/auth\/status$/);
        expect(init.headers).toEqual({ cookie: 'Authorization=access;RefreshToken=refresh' });
        expect(init.cache).toBe('no-store');
    });

    it('is null when the backend refuses the session', async () => {
        fetchMock.mockResolvedValue(new Response('{"message":"No user logged in."}', { status: 401 }));

        expect(await signedInUserId()).toBeNull();
    });

    it('is null when the backend cannot be reached', async () => {
        const quiet = vi.spyOn(console, 'error').mockImplementation(() => {});
        fetchMock.mockRejectedValue(new TypeError('fetch failed'));

        expect(await signedInUserId()).toBeNull();
        quiet.mockRestore();
    });
});

describe('createRateLimiter', () => {
    it('allows the limit in each window, then answers when to retry', () => {
        let now = 0;
        const limiter = createRateLimiter({ limit: 2, windowMs: 10_000, now: () => now });

        expect(limiter.hit('a').allowed).toBe(true);
        expect(limiter.hit('a').allowed).toBe(true);
        now = 2_500;
        expect(limiter.hit('a')).toEqual({ allowed: false, retryAfterSeconds: 8 });
        expect(limiter.hit('b').allowed).toBe(true);

        now = 10_000;
        expect(limiter.hit('a').allowed).toBe(true);
    });

    it('remembers a bounded number of keys', () => {
        let now = 0;
        const limiter = createRateLimiter({ limit: 1, windowMs: 10_000, maxKeys: 2, now: () => now });

        limiter.hit('a');
        limiter.hit('b');
        now = 1;
        limiter.hit('c'); // forgets 'a', the oldest

        expect(limiter.hit('a').allowed).toBe(true);
        expect(limiter.hit('c').allowed).toBe(false);
    });
});
