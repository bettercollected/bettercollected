// The forms toolbar and the form menu in Dutch and English: every label comes
// from the locale files (no hard-coded English), with the right capitalisation
// and a plural form count.
import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import WorkspaceDashboardForms from '@app/components/workspace-dashboard/workspace-dashboard-forms';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import NewFormButton from '@app/views/atoms/new-form-button';

import FormOptionsDropdownMenu from './form-options-dropdown';

import commonNl from '../../../public/locales/nl/common.json';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }), usePathname: () => '/acme/dashboard/forms' }));
vi.mock('@app/components/workspace-dashboard/workspace-dashboard-form-cards', () => ({ default: () => <p>form cards</p> }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => true, ready: true, isLoading: false }) }));
vi.mock('@app/lib/hooks/use-open-formulieren-export-mode', () => ({ useOpenFormulierenExportOn: () => ({ on: true }) }));
vi.mock('@app/lib/hooks/use-breakpoint', () => ({ useIsMobile: () => false }));
vi.mock('@app/lib/hooks/use-google-forms-import-mode', () => ({ useGoogleFormsImportMode: () => ({ mode: 'on' }) }));

const forms: { total: number } = { total: 3 };
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspaceFormsQuery: () => ({ isLoading: false, data: { items: Array.from({ length: forms.total }, (_, i) => ({ formId: `f${i}` })), total: forms.total, pages: 1 } }),
        useLazySearchWorkspaceFormsQuery: () => [vi.fn()],
        useGetAllRespondersGroupQuery: () => ({ data: [] })
    };
});

const workspace = { id: 'ws1', workspaceName: 'acme', title: 'Acme' } as any;
const form = { formId: 'f1', title: 'Klantfeedback', isPublished: true, builderVersion: 'v2', settings: { provider: 'self' } } as any;

const inLanguage = async (language: 'en' | 'nl') => {
    await i18n.changeLanguage(language);
};

beforeAll(() => {
    i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    (window as any).PUBLIC_CONFIG = { FORM_DOMAIN: 'forms.example.com', HTTP_SCHEME: 'https://', DASHBOARD_DOMAIN: 'app.example.com' };
});

afterEach(async () => {
    await inLanguage('en');
});

describe('the forms toolbar', () => {
    const renderToolbar = () =>
        render(
            <ReduxProvider store={store}>
                <WorkspaceDashboardForms workspace={workspace} hasCustomDomain={false} showPagination showButtons />
            </ReduxProvider>
        );

    it('is Dutch in Dutch, with a plural count', async () => {
        store.dispatch(setWorkspace(workspace));
        await inLanguage('nl');
        forms.total = 3;
        const { unmount } = renderToolbar();
        expect(screen.getByPlaceholderText('Formulieren zoeken')).toBeInTheDocument();
        expect(screen.getByText('3 formulieren')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Nieuw formulier' })).toBeInTheDocument();
        unmount();

        forms.total = 1;
        renderToolbar();
        expect(screen.getByText('1 formulier')).toBeInTheDocument();
    });

    it('is English in English, with a plural count', async () => {
        store.dispatch(setWorkspace(workspace));
        forms.total = 3;
        const { unmount } = renderToolbar();
        expect(screen.getByPlaceholderText('Search forms')).toBeInTheDocument();
        expect(screen.getByText('3 forms')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'New Form' })).toBeInTheDocument();
        unmount();

        forms.total = 1;
        renderToolbar();
        expect(screen.getByText('1 form')).toBeInTheDocument();
    });
});

describe('the form menu', () => {
    const openMenu = () => {
        store.dispatch(setWorkspace(workspace));
        const { container } = render(
            <ReduxProvider store={store}>
                <FormOptionsDropdownMenu workspace={workspace} form={form} hasCustomDomain={false} />
            </ReduxProvider>
        );
        fireEvent.click(container.querySelector('.cursor-pointer') as HTMLElement);
    };

    it('is Dutch in Dutch, Open starting with a capital', async () => {
        await inLanguage('nl');
        openMenu();
        for (const label of ['Formulier vastzetten', 'Openen', 'Bewerken', 'Link kopiëren', 'Link aanpassen', 'QR-code maken', 'Formulier dupliceren', 'Downloaden voor Open Formulieren', 'Formulier verwijderen']) {
            expect(await screen.findByText(label)).toBeInTheDocument();
        }
        for (const old of ['Vastzetten formulier', 'Maak QR-code', 'Dupliceer formulier', 'Verwijder formulier', 'Open in de editor']) {
            expect(screen.queryByText(old)).toBeNull();
        }
        for (const english of ['Duplicate form', 'Generate QR', 'openen']) {
            expect(screen.queryByText(english)).toBeNull();
        }
    });

    it('is English in English', async () => {
        openMenu();
        for (const label of ['Open', 'Copy link', 'Generate QR', 'Duplicate form', 'Delete form']) {
            expect(await screen.findByText(label)).toBeInTheDocument();
        }
    });
});
