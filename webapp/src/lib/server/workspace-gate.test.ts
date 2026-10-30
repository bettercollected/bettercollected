// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('next/headers', () => ({
    cookies: async () => ({ get: (name: string) => (name === 'Authorization' ? { name, value: 'token' } : undefined) })
}));
vi.mock('@app/configs/environments', () => ({ default: { INTERNAL_DOCKER_API_ENDPOINT_HOST: 'http://api.internal/api/v1' } }));

const { requireWorkspaceAccess } = await import('./workspace-gate');
const { nextOutcome } = await import('@app/test/next-outcome');

/** Where the gate sent the browser, or null when it let the page through. */
async function outcome(handle: string): Promise<string | null> {
    return (await nextOutcome(() => requireWorkspaceAccess(handle))).redirect ?? null;
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe('requireWorkspaceAccess (every workspace dashboard page and the onboarding)', () => {
    const fetchMock = vi.fn();
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal('fetch', fetchMock);
    });
    afterEach(() => vi.unstubAllGlobals());

    it("asks the server about this workspace's dashboard only, with the session cookie", async () => {
        fetchMock.mockImplementation(async () => json({ next: '/acme/dashboard', notice: null }));
        expect(await outcome('acme')).toBeNull();
        const [url, init] = fetchMock.mock.calls[0];
        expect(String(url)).toBe('http://api.internal/api/v1/workspaces/mine/selection/target?next=%2Facme%2Fdashboard');
        expect(init.headers).toEqual({ cookie: 'Authorization=token' });
        expect(init.cache).toBe('no-store');
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('a workspace the user is not in and one that does not exist: the same notice', async () => {
        fetchMock.mockImplementation(async () => json({ next: null, notice: 'no_access' }));
        const notMember = await outcome('secret');
        const missing = await outcome('no-such-workspace');
        expect(notMember).toBe('/workspace/select?notice=no_access');
        expect(missing).toBe(notMember);
    });

    it('a workspace that needs its single sign-on first: the screen, whose row starts it', async () => {
        fetchMock.mockImplementation(async () => json({ next: null, notice: null }));
        expect(await outcome('acme')).toBe('/workspace/select');
    });

    it('nobody signed in: the sign-in page, then back to this workspace', async () => {
        fetchMock.mockImplementation(async () => json({ detail: 'not signed in' }, 401));
        expect(await outcome('acme')).toBe('/login?redirect_to=%2Facme%2Fdashboard');
    });

    it.each([
        ['a server error', () => json({}, 500)],
        ['an over-long handle (422)', () => json({}, 422)],
        ['a gateway timeout', () => json({}, 504)]
    ])('fails closed on %s: the selection screen, whatever the workspace', async (_label, reply) => {
        fetchMock.mockImplementation(async () => reply());
        expect(await outcome('acme')).toBe('/workspace/select');
        expect(await outcome('no-such-workspace')).toBe('/workspace/select');
    });

    it('fails closed when the API cannot be reached', async () => {
        fetchMock.mockRejectedValue(new TypeError('fetch failed'));
        expect(await outcome('acme')).toBe('/workspace/select');
    });

    it('encodes the handle', async () => {
        fetchMock.mockImplementation(async () => json({ next: null, notice: 'no_access' }));
        await outcome('a b');
        expect(String(fetchMock.mock.calls[0][0])).toContain('next=%2Fa%2520b%2Fdashboard');
    });
});
