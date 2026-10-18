// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();
vi.mock('unsplash-js', () => ({ createApi: () => ({ GET: getMock }) }));

const getUserMock = vi.fn();
vi.mock('@app/lib/server/api', () => ({ getUser: () => getUserMock() }));

process.env.UNSPLASH_ACCESS_KEY = 'test-key';

const { GET: search } = await import('./route');
const { POST: trackDownload } = await import('./download/route');
const { downloadLimiter, searchLimiter } = await import('@app/lib/server/unsplash');

const SIGNED_IN = { id: 'user-1', email: 'person@example.test', roles: ['FORM_CREATOR'] };
const FEED = { total: 2, total_pages: 1, results: [{ id: 'a' }, { id: 'b' }] };

const searchRequest = (query: string, headers?: Record<string, string>) => new Request(`http://localhost/api/unsplash${query}`, { headers });
const downloadRequest = (body: unknown) => new Request('http://localhost/api/unsplash/download', { method: 'POST', body: typeof body === 'string' ? body : JSON.stringify(body) });

describe('unsplash routes', () => {
    beforeEach(() => {
        getMock.mockReset();
        getUserMock.mockReset();
        getUserMock.mockResolvedValue(SIGNED_IN);
        searchLimiter.reset();
        downloadLimiter.reset();
    });

    describe('without a session', () => {
        beforeEach(() => getUserMock.mockResolvedValue(null));

        it('refuses a search with 401 and never calls Unsplash', async () => {
            const response = await search(searchRequest('?query=dogs'));

            expect(response.status).toBe(401);
            expect(await response.json()).toEqual({ message: 'Sign in to search images.' });
            expect(getMock).not.toHaveBeenCalled();
        });

        it('ignores headers that claim a user', async () => {
            const response = await search(searchRequest('?query=dogs', { 'x-user-id': 'user-1', authorization: 'Bearer forged' }));

            expect(response.status).toBe(401);
            expect(getMock).not.toHaveBeenCalled();
        });

        it('refuses download tracking with 401 and never calls Unsplash', async () => {
            const response = await trackDownload(downloadRequest({ id: 'mtNweauBsMQ' }));

            expect(response.status).toBe(401);
            expect(getMock).not.toHaveBeenCalled();
        });

        it('treats a status without an id as no session', async () => {
            getUserMock.mockResolvedValue({ email: 'person@example.test' });

            const response = await search(searchRequest('?query=dogs'));

            expect(response.status).toBe(401);
        });
    });

    it('searches landscape photos and returns the feed unchanged', async () => {
        getMock.mockResolvedValue({ data: FEED });

        const response = await search(searchRequest('?query=dogs&page=2'));

        expect(response.status).toBe(200);
        expect(await response.json()).toEqual(FEED);
        expect(getMock).toHaveBeenCalledWith('/search/photos', {
            params: { query: { page: 2, per_page: 30, query: 'dogs', orientation: 'landscape' } }
        });
    });

    it.each([
        ['31', 30],
        ['500', 30],
        ['12', 12]
    ])('caps perPage=%s at 30', async (perPage, expected) => {
        getMock.mockResolvedValue({ data: FEED });

        const response = await search(searchRequest(`?query=dogs&perPage=${perPage}`));

        expect(response.status).toBe(200);
        expect(getMock.mock.calls[0][1].params.query.per_page).toBe(expected);
    });

    it.each([
        ['no query', ''],
        ['a blank query', '?query=%20%20'],
        ['an over-long query', `?query=${'a'.repeat(101)}`],
        ['a page that is no number', '?query=dogs&page=two'],
        ['page 0', '?query=dogs&page=0'],
        ['a page past the cap', '?query=dogs&page=1001'],
        ['a negative page', '?query=dogs&page=-1'],
        ['a fractional perPage', '?query=dogs&perPage=1.5'],
        ['perPage 0', '?query=dogs&perPage=0'],
        ['an over-long perPage', '?query=dogs&perPage=0000000030']
    ])('refuses %s with 400', async (_, query) => {
        const response = await search(searchRequest(query));

        expect(response.status).toBe(400);
        expect(typeof (await response.json()).message).toBe('string');
        expect(getMock).not.toHaveBeenCalled();
    });

    it('answers 502 without the upstream error when Unsplash refuses', async () => {
        getMock.mockResolvedValue({ error: { errors: ['OAuth error: The access token is invalid'] } });

        const response = await search(searchRequest('?query=dogs'));

        expect(response.status).toBe(502);
        expect(JSON.stringify(await response.json())).not.toContain('OAuth');
    });

    it('limits each person to 60 searches per window, with Retry-After', async () => {
        getMock.mockResolvedValue({ data: FEED });
        for (let i = 0; i < 60; i++) {
            expect((await search(searchRequest('?query=dogs'))).status).toBe(200);
        }

        const limited = await search(searchRequest('?query=dogs'));
        expect(limited.status).toBe(429);
        expect(Number(limited.headers.get('Retry-After'))).toBeGreaterThan(0);
        expect(getMock).toHaveBeenCalledTimes(60);

        getUserMock.mockResolvedValue({ ...SIGNED_IN, id: 'user-2' });
        expect((await search(searchRequest('?query=dogs'))).status).toBe(200);
    });

    it('tracks a download by photo id', async () => {
        getMock.mockResolvedValue({ data: { url: 'https://example.test/x' } });

        const response = await trackDownload(downloadRequest({ id: 'mtNweauBsMQ' }));

        expect(response.status).toBe(200);
        expect(getMock).toHaveBeenCalledWith('/photos/{id}/download', { params: { path: { id: 'mtNweauBsMQ' } } });
    });

    it.each([{}, { id: 42 }, { id: '../../me' }, { id: 'a/b' }, 'not json', { id: 'abc', padding: 'x'.repeat(17 * 1024) }])('refuses an invalid photo %#', async (photo) => {
        const response = await trackDownload(downloadRequest(photo));

        expect(response.status).toBe(400);
        expect(getMock).not.toHaveBeenCalled();
    });
});
