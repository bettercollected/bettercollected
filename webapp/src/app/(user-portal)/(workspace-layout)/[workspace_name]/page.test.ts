// The portal's root URL redirects to its forms tab and keeps a respondent's
// ?lang=nl|en (and only that), so the forms page is in the same language.
import { redirect } from 'next/navigation';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import WorkspaceIndexPage from './page';

vi.mock('next/navigation', () => ({ redirect: vi.fn() }));

const visit = (search: Record<string, string | string[]>) => WorkspaceIndexPage({ params: Promise.resolve({ workspace_name: 'acme' }), searchParams: Promise.resolve(search) });

describe('the portal root redirect', () => {
    beforeEach(() => vi.mocked(redirect).mockClear());

    it.each([
        [{ lang: 'nl' }, '/acme/forms?lang=nl'],
        [{ lang: 'en', utm_source: 'mail' }, '/acme/forms?lang=en'],
        [{ lang: 'de' }, '/acme/forms'],
        [{}, '/acme/forms']
    ])('%o goes to %s', async (search, target) => {
        await visit(search);
        expect(redirect).toHaveBeenCalledWith(target);
    });

    it.each(['%2Fevil.com', '/evil.com', '//evil.com', 'javascript:alert(1)'])('stays on the site for the handle %s', async (workspace_name) => {
        await WorkspaceIndexPage({ params: Promise.resolve({ workspace_name }), searchParams: Promise.resolve({}) });
        const target = vi.mocked(redirect).mock.calls[0][0] as string;
        expect(target).toMatch(/^\/[^/\\]/);
        expect(new URL(target, 'https://forms.example').origin).toBe('https://forms.example');
    });
});
