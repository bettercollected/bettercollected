// The respondent portal's tabs and its form search are in the respondent's
// language (?lang=, else the browser's) and marked with it; on the team's
// dashboard the form search keeps the app's language.
// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import ResponderPortalLayoutClient from './responder-portal-layout-client';

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => '/acme/forms',
    useSearchParams: () => new URLSearchParams(window.location.search)
}));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn() }) }));
vi.mock('@Components/responder-portal/workspace-details-card', () => ({ default: () => null }));
vi.mock('./search-by-submission-number', () => ({ default: () => null }));
vi.mock('@app/components/dashboard/form-cards', () => ({ default: () => null }));
vi.mock('@app/store/workspaces/api', async (importOriginal) => ({
    ...(await importOriginal<typeof import('@app/store/workspaces/api')>()),
    useGetWorkspaceFormsQuery: () => ({ isLoading: false, isError: false, data: { items: [{ formId: 'f1', title: 'Intake' }], total: 1 } }),
    useLazySearchWorkspaceFormsQuery: () => [vi.fn()]
}));

const workspace = { id: 'w1', workspaceName: 'acme', title: 'Acme' } as any;

const at = (url: string) => window.history.replaceState(null, '', url);

describe('the respondent portal in Dutch', () => {
    afterEach(() => at('/'));

    it('names its tabs in Dutch and marks them so', async () => {
        at('/acme/forms?lang=nl');
        render(
            <ReduxProvider store={store}>
                <ResponderPortalLayoutClient hasCustomDomain={false}>
                    <p>content</p>
                </ResponderPortalLayoutClient>
            </ReduxProvider>
        );
        const forms = await screen.findByRole('link', { name: 'Formulieren' });
        expect(screen.getByRole('link', { name: 'Mijn inzendingen' })).toBeInTheDocument();
        expect(forms.parentElement).toHaveAttribute('lang', 'nl');
    });

    it('searches forms in Dutch on the portal', async () => {
        at('/acme/forms?lang=nl');
        render(
            <ReduxProvider store={store}>
                <WorkspaceFormsTabContent workspace={workspace} />
            </ReduxProvider>
        );
        const search = await screen.findByPlaceholderText('Formulieren zoeken');
        expect(search.closest('[lang]')).toHaveAttribute('lang', 'nl');
    });

    it("keeps the app's language for the team's preview of the portal", async () => {
        at('/acme/dashboard?lang=nl');
        render(
            <ReduxProvider store={store}>
                <WorkspaceFormsTabContent workspace={workspace} audience="team" />
            </ReduxProvider>
        );
        const search = await screen.findByPlaceholderText('Search forms');
        expect(search.closest('[lang]')).toHaveAttribute('lang', 'en');
    });
});

describe('the respondent portal in English', () => {
    afterEach(() => at('/'));

    it('keeps its English tab names', async () => {
        at('/acme/forms?lang=en');
        render(
            <ReduxProvider store={store}>
                <ResponderPortalLayoutClient hasCustomDomain={false}>
                    <p>content</p>
                </ResponderPortalLayoutClient>
            </ReduxProvider>
        );
        expect(await screen.findByRole('link', { name: 'Forms' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'My submissions' })).toBeInTheDocument();
    });
});

const renderPortal = () =>
    render(
        <ReduxProvider store={store}>
            <ResponderPortalLayoutClient hasCustomDomain={false}>
                <p>content</p>
            </ResponderPortalLayoutClient>
        </ReduxProvider>
    );

// The tab bar: the parent of the first tab, "Forms" or "Formulieren".
const tabBar = async () => (await screen.findByRole('link', { name: /^(Forms|Formulieren)$/ })).parentElement!;

describe('the portal tab links', () => {
    afterEach(() => at('/'));

    it.each([
        ['/acme/forms?lang=nl&utm_source=x', '?lang=nl'],
        ['/acme/forms?lang=EN', '?lang=en'],
        ['/acme/forms?lang=de', ''],
        ['/acme/forms?next=https://example.com', '']
    ])('on %s carry %s and nothing else', async (url, query) => {
        at(url);
        renderPortal();
        const tabs = Array.from((await tabBar()).querySelectorAll('a'));
        expect(tabs.map((tab) => tab.getAttribute('href')!.replace(/^.*\/(forms|my-submissions)/, '$1'))).toEqual([`forms${query}`, `my-submissions${query}`]);
    });
});

describe('the portal tab bar on a narrow screen', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        at('/');
    });

    const narrow = (scrollWidth: number) => {
        vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(scrollWidth);
        vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(300);
    };

    it('fades the edge that has more tabs past it, and not the other', async () => {
        narrow(480);
        renderPortal();
        expect(await screen.findByTestId('more-tabs-after')).toHaveAttribute('aria-hidden', 'true');
        expect(screen.queryByTestId('more-tabs-before')).toBeNull();

        const bar = await tabBar();
        bar.scrollLeft = 180;
        fireEvent.scroll(bar);
        expect(await screen.findByTestId('more-tabs-before')).toBeInTheDocument();
        expect(screen.queryByTestId('more-tabs-after')).toBeNull();
    });

    it('shows no fade when every tab fits', async () => {
        narrow(300);
        renderPortal();
        await tabBar();
        expect(screen.queryByTestId('more-tabs-after')).toBeNull();
        expect(screen.queryByTestId('more-tabs-before')).toBeNull();
    });
});
