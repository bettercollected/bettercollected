// The respondent portal's tabs and its form search are in the respondent's
// language (?lang=, else the browser's) and marked with it; on the team's
// dashboard the form search keeps the app's language.
// Respondent text resolves through the app's i18n instance.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import ResponderPortalLayoutClient from './responder-portal-layout-client';

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => '/acme/forms'
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
