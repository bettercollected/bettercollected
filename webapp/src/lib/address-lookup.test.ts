import { afterEach, describe, expect, it, vi } from 'vitest';

import { lookUpAddress } from './address-lookup';

const request = { workspaceId: 'ws-1', formId: 'form 1', fieldId: 'home', postcode: '1015CS', houseNumber: '12' };
const reply = (body: unknown, init: { ok?: boolean; status?: number } = {}) => Promise.resolve({ ok: init.ok ?? true, status: init.status ?? 200, json: () => Promise.resolve(body) } as Response);

afterEach(() => vi.unstubAllGlobals());

describe('lookUpAddress', () => {
    it('posts the two values and the question to the form\'s lookup route, and keeps nothing in the address', async () => {
        const fetcher = vi.fn(() => reply({ status: 'found', street: 'Keizersgracht', city: 'Amsterdam' }));
        vi.stubGlobal('fetch', fetcher);
        await expect(lookUpAddress(request)).resolves.toEqual({ status: 'found', street: 'Keizersgracht', city: 'Amsterdam' });
        const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
        expect(url).toMatch(/\/workspaces\/ws-1\/forms\/form%201\/address-lookup$/);
        expect(url).not.toContain('1015');
        expect(init.method).toBe('POST');
        expect(JSON.parse(init.body as string)).toEqual({ fieldId: 'home', postcode: '1015CS', houseNumber: '12' });
        expect(init.cache).toBe('no-store');
    });

    it('answers not found', async () => {
        vi.stubGlobal('fetch', () => reply({ status: 'not_found' }));
        await expect(lookUpAddress(request)).resolves.toEqual({ status: 'not_found' });
    });

    it('rejects, without the reply, for a failure status or a reply that is not one of ours', async () => {
        for (const answer of [reply({ code: 'lookup_unavailable' }, { ok: false, status: 503 }), reply({ status: 'found', street: 1, city: 'x' }), reply(null), reply({ status: 'maybe' })]) {
            vi.stubGlobal('fetch', () => answer);
            await expect(lookUpAddress(request)).rejects.toThrow('address lookup unavailable');
        }
    });
});
