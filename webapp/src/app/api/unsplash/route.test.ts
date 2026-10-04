// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getMock = vi.fn();
vi.mock('unsplash-js', () => ({ createApi: () => ({ GET: getMock }) }));

process.env.UNSPLASH_ACCESS_KEY = 'test-key';

const { GET: search } = await import('./route');
const { POST: trackDownload } = await import('./download/route');

describe('unsplash routes', () => {
    beforeEach(() => getMock.mockReset());

    it('searches landscape photos and returns the feed unchanged', async () => {
        const feed = { total: 2, total_pages: 1, results: [{ id: 'a' }, { id: 'b' }] };
        getMock.mockResolvedValue({ data: feed });

        const response = await search(new Request('http://localhost/api/unsplash?query=dogs&page=2'));

        expect(response.status).toBe(200);
        expect(await response.json()).toEqual(feed);
        expect(getMock).toHaveBeenCalledWith('/search/photos', {
            params: { query: { page: 2, per_page: 30, query: 'dogs', orientation: 'landscape' } }
        });
    });

    it('requires a query', async () => {
        const response = await search(new Request('http://localhost/api/unsplash'));
        expect(response.status).toBe(400);
        expect(getMock).not.toHaveBeenCalled();
    });

    it('tracks a download by photo id', async () => {
        getMock.mockResolvedValue({ data: { url: 'https://example.test/x' } });

        const response = await trackDownload(new Request('http://localhost/api/unsplash/download', { method: 'POST', body: JSON.stringify({ id: 'mtNweauBsMQ' }) }));

        expect(response.status).toBe(200);
        expect(getMock).toHaveBeenCalledWith('/photos/{id}/download', { params: { path: { id: 'mtNweauBsMQ' } } });
    });

    it.each([{}, { id: 42 }, { id: '../../me' }, { id: 'a/b' }])('refuses an invalid photo %j', async (photo) => {
        const response = await trackDownload(new Request('http://localhost/api/unsplash/download', { method: 'POST', body: JSON.stringify(photo) }));

        expect(response.status).toBe(400);
        expect(getMock).not.toHaveBeenCalled();
    });
});
