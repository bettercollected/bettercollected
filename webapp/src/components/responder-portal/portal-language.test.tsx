// The respondent portal's tabs and its form search are in the respondent's
// language (?lang=, else the browser's) and marked with it; on the team's
// dashboard the form search keeps the app's language.
// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import '@app/shared/hocs/i18n-provider';
import { setAuth } from '@app/store/auth/slice';
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

// Signed out, once the session check has answered.
const signedOut = () => store.dispatch(setAuth({ id: '', email: '', isLoading: false }));

describe('the portal around the tabs in Dutch', () => {
    beforeEach(signedOut);
    afterEach(() => at('/'));

    it('sets the page language, and has its sign-in card, credits and footer in Dutch', async () => {
        at('/acme/forms?lang=nl');
        renderPortal();
        await screen.findByRole('link', { name: 'Formulieren' });
        expect(document.documentElement).toHaveAttribute('lang', 'nl');
        expect(screen.getByRole('heading', { level: 2, name: 'Je inzendingen bekijken' }).closest('[lang]')).toHaveAttribute('lang', 'nl');
        expect(screen.getByRole('button', { name: 'E-mailadres bevestigen' })).toBeInTheDocument();
        expect(screen.getByText('Anoniem ingezonden? Gebruik dan je inzendnummer.')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Mogelijk gemaakt door bettercollected' })).toHaveAttribute('lang', 'nl');
        // the phone badge too
        const credits = screen.getAllByText('Mogelijk gemaakt door');
        expect(credits).toHaveLength(2);
        for (const credit of credits) expect(credit.closest('[lang]')).toHaveAttribute('lang', 'nl');
        const footers = screen.getAllByText('Sireto® is een geregistreerd handelsmerk van Sireto B.V.');
        expect(footers.length).toBeGreaterThan(0);
        for (const footer of footers) expect(footer.closest('footer')).toHaveAttribute('lang', 'nl');
        expect(screen.getAllByRole('link', { name: 'Een product van Sireto B.V.' })[0]).toHaveAttribute('href', 'https://sireto.com');
    });

    it('puts the page language back when the portal is left', async () => {
        at('/acme/forms?lang=nl');
        document.documentElement.setAttribute('lang', 'en');
        const { unmount } = renderPortal();
        await screen.findByRole('link', { name: 'Formulieren' });
        expect(document.documentElement).toHaveAttribute('lang', 'nl');
        unmount();
        expect(document.documentElement).toHaveAttribute('lang', 'en');
    });
});

describe('the signed-in portal', () => {
    afterEach(() => {
        signedOut();
        at('/');
    });

    it('signs out with a real button, reachable by keyboard', async () => {
        store.dispatch(setAuth({ id: 'u1', email: 'someone@example.com', isLoading: false }));
        at('/acme/forms?lang=en');
        renderPortal();
        fireEvent.click(await screen.findByRole('button', { name: /someone@example\.com/ }));
        const logout = await screen.findByRole('button', { name: 'Logout' });
        expect(logout.tagName).toBe('BUTTON');
        expect(logout).toHaveAttribute('type', 'button');
    });
});

describe('the respondent portal in English', () => {
    afterEach(() => at('/'));

    it('has its sign-in card and footer in English', async () => {
        signedOut();
        at('/acme/forms?lang=en');
        renderPortal();
        await screen.findByRole('link', { name: 'Forms' });
        expect(screen.getByRole('heading', { level: 2, name: 'See your submissions' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Verify email' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Powered by bettercollected' })).toBeInTheDocument();
        expect(screen.getAllByText('Sireto® is a registered trademark of Sireto B.V.').length).toBeGreaterThan(0);
    });

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

describe('the portal tab bar wraps instead of hiding tabs', () => {
    afterEach(() => at('/'));

    it('wraps onto a second line, with every tab keeping its own bottom rule', async () => {
        at('/acme/forms?lang=nl');
        renderPortal();
        const bar = await tabBar();
        expect(bar.className).toContain('flex-wrap');
        const tabs = Array.from(bar.querySelectorAll('a'));
        expect(tabs.length).toBeGreaterThan(1);
        for (const tab of tabs) {
            expect(tab.className).toMatch(/\bborder-b\b|\bborder-b-2\b/);
            expect(tab.className).toContain('whitespace-nowrap');
        }
    });

    it('keeps the active tab underline distinct from the inactive rule', async () => {
        renderPortal();
        const active = (await screen.findByRole('link', { name: /^Forms$/ })).className;
        const inactive = screen.getByRole('link', { name: /^My submissions$/ }).className;
        expect(active).toContain('border-b-2');
        expect(inactive).not.toContain('border-b-2');
        expect(inactive).toMatch(/\bborder-b\b/);
    });
});
