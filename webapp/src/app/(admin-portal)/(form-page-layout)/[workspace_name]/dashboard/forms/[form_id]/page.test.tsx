import { beforeEach, describe, expect, it, vi } from 'vitest';

import Page from './page';

// next's redirect() throws; the test reads where it was sent
class Redirected extends Error {
    constructor(public url: string) {
        super(url);
    }
}
vi.mock('next/navigation', () => ({
    redirect: (url: string) => {
        throw new Redirected(url);
    }
}));

const go = async (query: Record<string, string | string[]>) => {
    try {
        await Page({ params: Promise.resolve({ workspace_name: 'acme', form_id: 'f1' }), searchParams: Promise.resolve(query) });
    } catch (error) {
        if (error instanceof Redirected) return error.url;
        throw error;
    }
    return undefined;
};

describe("the form page's old response link", () => {
    beforeEach(() => vi.clearAllMocks());

    it('sends ?view=Responses&sub_id=<id> to the response page', async () => {
        expect(await go({ view: 'Responses', sub_id: 'r-1' })).toBe('/acme/dashboard/forms/f1/responses/r-1');
    });

    it('encodes the id: it stays a path of this workspace, never a destination of its own', async () => {
        expect(await go({ view: 'Responses', sub_id: '/\\evil.example.com' })).toBe('/acme/dashboard/forms/f1/responses/%2F%5Cevil.example.com');
        expect(await go({ view: 'Responses', sub_id: '../../x' })).toBe('/acme/dashboard/forms/f1/responses/..%2F..%2Fx');
    });

    it('takes the first value when the parameter is repeated', async () => {
        expect(await go({ view: 'Responses', sub_id: ['a', 'b'] })).toBe('/acme/dashboard/forms/f1/responses/a');
    });

    it('leaves every other visit as it was: the preview', async () => {
        expect(await go({})).toBe('/acme/dashboard/forms/f1/preview');
        expect(await go({ view: 'Responses' })).toBe('/acme/dashboard/forms/f1/preview');
        expect(await go({ sub_id: 'r-1' })).toBe('/acme/dashboard/forms/f1/preview');
    });
});
