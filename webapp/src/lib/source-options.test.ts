import { afterEach, describe, expect, it, vi } from 'vitest';

import { SourceOptionsLimited, fetchSourceOptions, pageOf } from '@app/lib/source-options';

afterEach(() => vi.unstubAllGlobals());

describe('pageOf', () => {
    it('keeps ids and texts only', () => {
        const page = pageOf({ items: [{ id: 'li1', label: 'A', group: 'secret', extra: 1 }, { id: 5, label: 'bad' }, null], total: 7, truncated: true, available: true });
        expect(page).toEqual({ items: [{ id: 'li1', label: 'A' }], total: 7, truncated: true, available: true });
        expect(pageOf({ items: [], available: false }).available).toBe(false);
    });

    it('refuses a reply that is not a page', () => {
        expect(() => pageOf(null)).toThrow();
        expect(() => pageOf({ items: 'x' })).toThrow();
    });
});

describe('fetchSourceOptions', () => {
    it('asks the public route with the search, the page and the parent ids, and keeps nothing', async () => {
        const fetched = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [{ id: 'li1', label: 'Amsterdam' }], total: 1, truncated: false, available: true }) });
        vi.stubGlobal('fetch', fetched);
        const page = await fetchSourceOptions({ workspaceId: 'w 1', formId: 'f1', fieldId: 'city', q: 'am', offset: 50, limit: 50, parent: ['nl', 'de'] });
        expect(page.items).toEqual([{ id: 'li1', label: 'Amsterdam' }]);
        const [url, init] = fetched.mock.calls[0];
        expect(url).toContain('/workspaces/w%201/forms/f1/options/city?');
        expect(url).toContain('q=am');
        expect(url).toContain('offset=50');
        expect(url.match(/parent=/g)).toHaveLength(2);
        expect(init).toMatchObject({ credentials: 'include', cache: 'no-store' });
    });

    it('rejects on every failure, with no detail', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) }));
        await expect(fetchSourceOptions({ workspaceId: 'w', formId: 'f', fieldId: 'c' })).rejects.toThrow('options unavailable');
    });

    it('tells a request to slow down from a failure, and how long to wait', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 429, headers: new Headers({ 'Retry-After': '7' }), json: async () => ({}) }));
        await expect(fetchSourceOptions({ workspaceId: 'w', formId: 'f', fieldId: 'c' })).rejects.toMatchObject({ retryAfter: 7 });
        await expect(fetchSourceOptions({ workspaceId: 'w', formId: 'f', fieldId: 'c' })).rejects.toBeInstanceOf(SourceOptionsLimited);
        // a missing or silly header is a short pause, never none and never long
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 429, headers: new Headers({ 'Retry-After': '99999' }), json: async () => ({}) }));
        await expect(fetchSourceOptions({ workspaceId: 'w', formId: 'f', fieldId: 'c' })).rejects.toMatchObject({ retryAfter: 60 });
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 429, headers: new Headers(), json: async () => ({}) }));
        await expect(fetchSourceOptions({ workspaceId: 'w', formId: 'f', fieldId: 'c' })).rejects.toMatchObject({ retryAfter: 5 });
    });
});
