import { beforeEach, describe, expect, it, vi } from 'vitest';

import FormLanding from './_components/form-landing';
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
        const shown: any = await Page({ params: Promise.resolve({ workspace_name: 'acme', form_id: 'f1' }), searchParams: Promise.resolve(query) });
        // no redirect from the server: the page is the landing, which chooses in the browser
        return shown.type === FormLanding ? `lands:${shown.props.base}` : undefined;
    } catch (error) {
        if (error instanceof Redirected) return error.url;
        throw error;
    }
};

describe("the form page's old response link and its landing", () => {
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

    it('hands every other visit to the landing, which opens Responses or Pages', async () => {
        expect(await go({})).toBe('lands:/acme/dashboard/forms/f1');
        expect(await go({ view: 'Responses' })).toBe('lands:/acme/dashboard/forms/f1');
        expect(await go({ sub_id: 'r-1' })).toBe('lands:/acme/dashboard/forms/f1');
    });
});
