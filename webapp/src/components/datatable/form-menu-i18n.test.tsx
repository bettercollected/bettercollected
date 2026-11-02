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
const workspacePermissions = vi.hoisted(() => ({ formRevisionsUiEnabled: false }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => true, ready: true, isLoading: false, formRevisionsUiEnabled: workspacePermissions.formRevisionsUiEnabled }) }));
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
        render(
            <ReduxProvider store={store}>
                <FormOptionsDropdownMenu workspace={workspace} form={form} hasCustomDomain={false} />
            </ReduxProvider>
        );
        // Radix opens the menu on pointer down or the keyboard, like a user does
        const trigger = screen.getByRole('button');
        fireEvent.pointerDown(trigger, { button: 0, ctrlKey: false });
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

describe('the form menu in the form page header', () => {
    const headerForm = { ...form, title: 'Klantfeedback', settings: { provider: 'self', pinned: false } } as any;

    const renderMenu = (overrides: object = {}) => {
        store.dispatch(setWorkspace(workspace));
        return render(
            <ReduxProvider store={store}>
                <FormOptionsDropdownMenu workspace={workspace} form={{ ...headerForm, ...overrides }} hasCustomDomain={false} inHeader />
            </ReduxProvider>
        );
    };

    it('opens from the keyboard on a real, named button, and Pin form is the first item', async () => {
        renderMenu();
        const trigger = screen.getByRole('button', { name: 'More actions for Klantfeedback' });
        expect(trigger.tagName).toBe('BUTTON');
        trigger.focus();
        fireEvent.keyDown(trigger, { key: 'Enter' });
        const items = await screen.findAllByRole('menuitem');
        expect(items[0]).toHaveTextContent('Pin form');
        // already on the form: no "Open" or "Edit" here (the header has its own Edit button)
        expect(screen.queryByRole('menuitem', { name: 'Open' })).toBeNull();
        expect(screen.queryByRole('menuitem', { name: 'Edit' })).toBeNull();
    });

    it('says why Pin form is off for a form that is not public', async () => {
        renderMenu({ settings: { provider: 'self', private: true } });
        fireEvent.keyDown(screen.getByRole('button', { name: /More actions/ }), { key: 'Enter' });
        const pin = await screen.findByRole('menuitem', { name: /Pin form/ });
        expect(pin).toHaveAttribute('aria-disabled', 'true');
        expect(pin).toHaveTextContent('Visibility of the form should be public to pin it into the workspace.');
    });

    it('offers Unpin form for a pinned form', async () => {
        renderMenu({ settings: { provider: 'self', pinned: true } });
        fireEvent.keyDown(screen.getByRole('button', { name: /More actions/ }), { key: 'Enter' });
        expect(await screen.findByRole('menuitem', { name: 'Unpin form' })).toBeInTheDocument();
    });

    it('ends with the form\'s version and, for an imported form, where it came from; Open form opens the respondent page in a new tab', async () => {
        renderMenu({ version: 3, settings: { provider: 'google' } });
        fireEvent.keyDown(screen.getByRole('button', { name: /More actions/ }), { key: 'Enter' });
        const open = await screen.findByRole('menuitem', { name: /Open form/ });
        expect(open).toHaveAttribute('target', '_blank');
        expect(open).toHaveAttribute('rel', expect.stringContaining('noopener'));
        expect(screen.getByText('Version 3')).toBeInTheDocument();
        expect(screen.getByText('Imported from Google Forms')).toBeInTheDocument();
    });

    it('links the version to Versions when the server offers them, and says nothing of origin for a native form', async () => {
        workspacePermissions.formRevisionsUiEnabled = true;
        try {
            renderMenu({ version: 2 });
            fireEvent.keyDown(screen.getByRole('button', { name: /More actions/ }), { key: 'Enter' });
            expect(await screen.findByRole('menuitem', { name: 'Version 2' })).toHaveAttribute('href', '/acme/dashboard/forms/f1/versions');
            expect(screen.queryByText(/Imported from/)).toBeNull();
            expect(screen.queryByText('bettercollected form')).toBeNull();
        } finally {
            workspacePermissions.formRevisionsUiEnabled = false;
        }
    });

    it('has Preview first when the bar gives it (a phone), and is Dutch in Dutch', async () => {
        await inLanguage('nl');
        const onPreview = vi.fn();
        store.dispatch(setWorkspace(workspace));
        render(
            <ReduxProvider store={store}>
                <FormOptionsDropdownMenu workspace={workspace} form={{ ...headerForm, version: 3, settings: { provider: 'typeform' } }} hasCustomDomain={false} inHeader onPreview={onPreview} />
            </ReduxProvider>
        );
        fireEvent.keyDown(screen.getByRole('button', { name: /Meer acties/ }), { key: 'Enter' });
        const items = await screen.findAllByRole('menuitem');
        expect(items[0]).toHaveTextContent('Voorbeeld');
        expect(screen.getByText('Versie 3')).toBeInTheDocument();
        expect(screen.getByText('Geïmporteerd uit Typeform')).toBeInTheDocument();
        expect(screen.getByText('Formulier openen')).toBeInTheDocument();
        fireEvent.click(items[0]);
        expect(onPreview).toHaveBeenCalled();
    });

    it('still has Open and Edit on a form card', async () => {
        store.dispatch(setWorkspace(workspace));
        render(
            <ReduxProvider store={store}>
                <FormOptionsDropdownMenu workspace={workspace} form={headerForm} hasCustomDomain={false} />
            </ReduxProvider>
        );
        fireEvent.keyDown(screen.getByRole('button', { name: /More actions/ }), { key: 'Enter' });
        expect(await screen.findByRole('menuitem', { name: 'Open' })).toHaveAttribute('href', '/acme/dashboard/forms/f1');
        expect(screen.getByRole('menuitem', { name: 'Edit' })).toBeInTheDocument();
    });
});
