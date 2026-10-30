import { beforeEach, describe, expect, it, vi } from 'vitest';

const server: { workspace: any; form: any; asked: string[] } = { workspace: { id: 'workspace-1' }, form: null, asked: [] };
vi.mock('@app/lib/server/api', () => ({ getWorkspaceByName: async () => server.workspace }));
vi.mock('@app/utils/fetch-utils', () => ({
    default: async (url: string) => {
        server.asked.push(url);
        if (server.form instanceof Error) throw server.form;
        return server.form;
    }
}));

import { generateMetadata } from './page';

const title = async (formId = 'form-1') => {
    const metadata = await generateMetadata({ params: Promise.resolve({ workspace_name: 'acme', form_id: formId }) });
    return (metadata.title as { absolute: string }).absolute;
};

describe("the response page's tab title (from the route's metadata, its only writer)", () => {
    beforeEach(() => {
        server.workspace = { id: 'workspace-1' };
        server.form = { formId: 'form-1', title: '  Summer meeting registration ' };
        server.asked = [];
    });

    it('is "Response · <form title>", read from the form, never from the response', async () => {
        expect(await title()).toBe('Response · Summer meeting registration');
        expect(server.asked).toHaveLength(1);
        expect(server.asked[0]).toMatch(/\/workspaces\/workspace-1\/forms\/form-1$/);
        expect(server.asked[0]).not.toContain('submission');
    });

    it('keeps the page out of search engines', async () => {
        const metadata = await generateMetadata({ params: Promise.resolve({ workspace_name: 'acme', form_id: 'form-1' }) });
        expect(metadata.robots).toEqual({ index: false, follow: false });
    });

    it('says "Untitled form" for a form without a title', async () => {
        server.form = { formId: 'form-1', title: ' ' };
        expect(await title()).toBe('Response · Untitled form');
    });

    it.each([
        ['an error body (no access)', { detail: 'Forbidden' }],
        ['another form', { formId: 'form-2', title: 'Other' }],
        ['nothing', null],
        ['a failed request', new Error('down')]
    ])('is plain "Response" for %s', async (_name, form) => {
        server.form = form;
        expect(await title()).toBe('Response');
    });

    it('is plain "Response" without the workspace, and asks nothing', async () => {
        server.workspace = null;
        expect(await title()).toBe('Response');
        expect(server.asked).toHaveLength(0);
    });

    it('encodes the form id from the URL into the API path', async () => {
        await title('../../x');
        expect(server.asked[0]).toMatch(/\/forms\/..%2F..%2Fx$/);
    });
});
