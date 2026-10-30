// The server-side status request: the status code decides, and a failure to
// reach the backend is "unknown", never "signed out".
import { beforeEach, describe, expect, it, vi } from 'vitest';

const backend: { answer: () => Promise<Response> } = { answer: async () => new Response(null, { status: 500 }) };
vi.mock('@app/utils/fetch-utils', () => ({ fetchWithCookiesResponse: () => backend.answer() }));

import { fetchAuthState } from './auth-provider';

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('fetchAuthState', () => {
    beforeEach(() => {
        backend.answer = async () => new Response(null, { status: 500 });
    });

    it('reads the signed-in user', async () => {
        backend.answer = async () => json(200, { id: 'u1', email: 'ada@example.test', roles: [] });
        expect(await fetchAuthState()).toEqual({ kind: 'signed-in', user: { id: 'u1', email: 'ada@example.test', roles: [] } });
    });

    it('reads a 401 as signed out', async () => {
        backend.answer = async () => json(401, { detail: 'No user logged in.' });
        expect(await fetchAuthState()).toEqual({ kind: 'signed-out' });
    });

    it('reads a 502 error page as unknown', async () => {
        backend.answer = async () => new Response('<html>Bad Gateway</html>', { status: 502, headers: { 'content-type': 'text/html' } });
        expect(await fetchAuthState()).toEqual({ kind: 'unknown' });
    });

    it('reads a 503 without a user as unknown', async () => {
        backend.answer = async () => json(503, { detail: 'Sign-in is temporarily unavailable.' });
        expect(await fetchAuthState()).toEqual({ kind: 'unknown' });
    });

    it('reads a broken JSON body as unknown', async () => {
        backend.answer = async () => new Response('{', { status: 200, headers: { 'content-type': 'application/json' } });
        expect(await fetchAuthState()).toEqual({ kind: 'unknown' });
    });

    it('reads the backend out of reach as unknown', async () => {
        backend.answer = async () => {
            throw new TypeError('fetch failed');
        };
        expect(await fetchAuthState()).toEqual({ kind: 'unknown' });
    });
});
