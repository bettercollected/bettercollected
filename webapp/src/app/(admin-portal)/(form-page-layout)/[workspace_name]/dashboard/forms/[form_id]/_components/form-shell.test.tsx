// The form's focused shell: one bar (back, title, status, actions), the sections
// of the form as a row of links, a skip link and the page; no workspace navbar.
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import commonNl from '../../../../../../../../../public/locales/nl/common.json';
import { buildFormNav } from './form-nav';
import FormShell from './form-shell';

const route = vi.hoisted(() => ({ pathname: '/acme/dashboard/forms/f1/responses', push: vi.fn() }));
const perms = vi.hoisted(() => ({ granted: [] as string[], revisions: false }));
const openModal = vi.hoisted(() => vi.fn());
const openFullScreenModal = vi.hoisted(() => vi.fn());

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: route.push, refresh: vi.fn() }), usePathname: () => route.pathname }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal, closeModal: vi.fn() }) }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({ openModal: openFullScreenModal }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => perms.granted.includes(permission), formRevisionsUiEnabled: perms.revisions, ready: true, isLoading: false })
}));
vi.mock('@app/lib/hooks/use-open-formulieren-export-mode', () => ({ useOpenFormulierenExportOn: () => ({ on: false }) }));
vi.mock('@app/views/molecules/form-builder/publish-button', () => ({ default: () => <button type="button">Publish</button> }));

const ALL = [WorkspacePermission.RESPONSE_READ, WorkspacePermission.FORM_EDIT, WorkspacePermission.FORM_READ, WorkspacePermission.FORM_CREATE, WorkspacePermission.FORM_DELETE, WorkspacePermission.PRIVACY_MANAGE];
const BASE = '/acme/dashboard/forms/f1';

const baseForm = {
    formId: 'f1',
    title: 'Join the volunteers',
    isPublished: true,
    builderVersion: 'v2',
    responses: 12,
    version: 4,
    settings: { provider: 'self' }
} as any;

const workspace = { id: 'ws1', workspaceName: 'acme', title: 'Stichting Voorbeeld' } as any;

const show = (over: Record<string, unknown> = {}, { pathname = `${BASE}/responses`, granted = ALL, revisions = false }: { pathname?: string; granted?: string[]; revisions?: boolean } = {}) => {
    route.pathname = pathname;
    perms.granted = granted;
    perms.revisions = revisions;
    store.dispatch(setWorkspace(workspace));
    const form = { ...baseForm, ...over };
    store.dispatch(setForm(form));
    return render(
        <ReduxProvider store={store}>
            <FormShell form={form} base={BASE}>
                <p>The page</p>
            </FormShell>
        </ReduxProvider>
    );
};

const tabs = () => within(screen.getByRole('navigation', { name: 'Form sections' }));

beforeAll(() => {
    i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    (window as any).PUBLIC_CONFIG = { FORM_DOMAIN: 'forms.example.com', HTTP_SCHEME: 'https://', DASHBOARD_DOMAIN: 'app.example.com' };
});

beforeEach(() => {
    openModal.mockClear();
    openFullScreenModal.mockClear();
    route.push.mockClear();
});

afterEach(async () => {
    await act(async () => {
        await i18n.changeLanguage('en');
    });
});

describe('the bar', () => {
    it('has Back to forms as a real link that carries the workspace, and the title as the one h1', () => {
        show();
        const back = screen.getByRole('link', { name: 'Back to forms' });
        expect(back).toHaveAttribute('href', '/acme/dashboard/forms');
        const h1 = screen.getAllByRole('heading', { level: 1 });
        expect(h1).toHaveLength(1);
        expect(h1[0]).toHaveTextContent('Join the volunteers');
        // the whole title stays in the DOM for a screen reader; only the eye sees it cut
        expect(h1[0]).toHaveAttribute('title', 'Join the volunteers');
    });

    it('keeps the visible word of the Back link inside its accessible name (the avatar letter is not text)', () => {
        show();
        const back = screen.getByRole('link', { name: 'Back to forms' });
        expect(back).toHaveTextContent('Forms');
        expect(back.textContent).not.toMatch(/S/);
    });

    it('names an untitled form', () => {
        show({ title: '   ' });
        expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Untitled form');
    });

    it('says Published or Draft, and Pinned', () => {
        show({ settings: { provider: 'self', pinned: true } });
        expect(screen.getByText('Published')).toBeInTheDocument();
        expect(screen.getByText('Pinned')).toBeInTheDocument();
    });

    it('has no workspace navbar, breadcrumb, meta line or footer line', () => {
        show();
        expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).toBeNull();
        expect(screen.queryByText('12 responses')).toBeNull();
        expect(screen.queryByText('bettercollected form')).toBeNull();
        expect(screen.queryByText('Version 4')).toBeNull();
        expect(screen.queryByRole('link', { name: /Open form/ })).toBeNull();
        expect(screen.getAllByRole('banner')).toHaveLength(1);
    });

    it('has Preview, Edit and Share for a published form, and Share opens the share dialog', () => {
        show();
        fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
        expect(openFullScreenModal).toHaveBeenCalledWith('PREVIEW_MODAL');
        fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
        expect(route.push).toHaveBeenCalledWith(expect.stringContaining('/edit'));
        fireEvent.click(screen.getByRole('button', { name: 'Share' }));
        expect(openModal).toHaveBeenCalledWith('SHARE_VIEW', expect.objectContaining({ formTitle: 'Join the volunteers' }));
    });

    it('has Publish, not Share, for a draft', () => {
        show({ isPublished: false });
        expect(screen.getByText('Draft')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Publish' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Share' })).toBeNull();
    });

    it('leaves Edit and Publish to those who may edit, and Edit to forms built here', () => {
        show({}, { granted: [WorkspacePermission.RESPONSE_READ] });
        expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
        expect(screen.getByRole('button', { name: 'Preview' })).toBeInTheDocument();
    });

    it('has no Edit or Preview for a form imported from elsewhere', () => {
        show({ builderVersion: undefined, settings: { provider: 'google' } });
        expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
        expect(screen.queryByRole('button', { name: 'Preview' })).toBeNull();
    });

    it('has Share off, with no dialog, for a hidden form', () => {
        show({ settings: { provider: 'self', hidden: true } });
        // the private-form tooltip wraps the button in its own trigger, so look for the one that is disabled
        expect(screen.getAllByRole('button', { name: 'Share' }).some((button) => (button as HTMLButtonElement).disabled)).toBe(true);
        expect(openModal).not.toHaveBeenCalled();
    });

    it('puts the version, Open form and where an imported form came from in the menu', async () => {
        show({ settings: { provider: 'typeform' } }, { revisions: true });
        const trigger = screen.getByRole('button', { name: /More actions for Join the volunteers/ });
        fireEvent.keyDown(trigger, { key: 'Enter' });
        expect(await screen.findByRole('menuitem', { name: /Open form/ })).toHaveAttribute('target', '_blank');
        expect(screen.getByRole('menuitem', { name: 'Version 4' })).toHaveAttribute('href', `${BASE}/versions`);
        expect(screen.getByText('Imported from Typeform')).toBeInTheDocument();
    });
});

describe('the skip link and the page', () => {
    it('has a skip link as the first stop, to the main landmark', () => {
        show();
        const skip = screen.getByRole('link', { name: 'Skip to content' });
        expect(skip).toHaveAttribute('href', '#form-main');
        expect(document.body.querySelector('a, button')).toBe(skip);
        const main = screen.getByRole('main');
        expect(main).toHaveAttribute('id', 'form-main');
        expect(main).toHaveAttribute('tabindex', '-1');
        expect(within(main).getByText('The page')).toBeInTheDocument();
    });
});

describe('the sections', () => {
    it('are a nav of links, the current one marked', () => {
        show();
        const links = tabs().getAllByRole('link');
        expect(links.map((link) => link.textContent)).toEqual(['Pages', 'Responses12', 'Analytics', 'Share', 'Settings']);
        const current = links.filter((link) => link.getAttribute('aria-current') === 'page');
        expect(current).toHaveLength(1);
        expect(current[0]).toHaveAttribute('href', `${BASE}/responses`);
    });

    it('keeps Responses current on Deletion requests', () => {
        show({}, { pathname: `${BASE}/deletion-requests` });
        expect(tabs().getByRole('link', { name: /Responses/ })).toHaveAttribute('aria-current', 'page');
    });

    it('shows Versions when the server offers them', () => {
        show({}, { revisions: true, pathname: `${BASE}/versions/2` });
        expect(tabs().getByRole('link', { name: 'Versions' })).toHaveAttribute('aria-current', 'page');
    });

    it('is Dutch in Dutch', async () => {
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        show();
        expect(screen.getByRole('link', { name: 'Terug naar formulieren' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Direct naar de inhoud' })).toBeInTheDocument();
        expect(
            within(screen.getByRole('navigation', { name: 'Onderdelen van het formulier' }))
                .getAllByRole('link')
                .map((link) => link.textContent)
        ).toEqual(['Pagina’s', 'Reacties12', 'Analyse', 'Delen', 'Instellingen']);
    });

    it('has no accessibility violations, with the menu closed or open, in either language', async () => {
        const { unmount } = show();
        expect(await axeViolations(document.body, { page: true })).toEqual([]);
        fireEvent.keyDown(screen.getByRole('button', { name: /More actions/ }), { key: 'Enter' });
        await screen.findByRole('menuitem', { name: /Open form/ });
        expect(await axeViolations(document.body)).toEqual([]);
        unmount();

        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        show({ settings: { provider: 'google' } });
        expect(await axeViolations(document.body, { page: true })).toEqual([]);
    });
});

describe('buildFormNav, who sees which section', () => {
    const t = (key: string) => key;
    const items = (form: Record<string, unknown>, granted: string[], pathname = `${BASE}/preview`, revisions = false) =>
        buildFormNav({ form: { ...baseForm, ...form }, base: BASE, pathname, can: (p) => granted.includes(p), formRevisionsUiEnabled: revisions, t }).map((item) => item.key);

    it('gives a draft Pages, and Settings to who may edit', () => {
        expect(items({ isPublished: false }, [WorkspacePermission.FORM_EDIT])).toEqual(['preview', 'settings']);
        expect(items({ isPublished: false }, [])).toEqual(['preview']);
    });

    it('gives a published form Responses, Analytics and Share, then Versions, then Settings', () => {
        expect(items({}, ALL, `${BASE}/preview`, true)).toEqual(['preview', 'responses', 'analytics', 'links', 'versions', 'settings']);
    });

    it('gives privacy.manage without response.read only Deletion requests', () => {
        expect(items({}, [WorkspacePermission.PRIVACY_MANAGE])).toEqual(['preview', 'deletion-requests', 'analytics', 'links']);
    });

    it('drops Analytics and Share once the form is closed', () => {
        expect(items({ settings: { provider: 'self', formCloseDate: '2000-01-01T00:00:00Z' } }, ALL)).toEqual(['preview', 'responses', 'settings']);
    });

    it('needs the server flag and form.read for Versions', () => {
        expect(items({}, [WorkspacePermission.RESPONSE_READ], `${BASE}/preview`, true)).toEqual(['preview', 'responses', 'analytics', 'links']);
        expect(items({}, [WorkspacePermission.FORM_READ], `${BASE}/preview`, true)).toEqual(['preview', 'analytics', 'links', 'versions']);
    });

    it('treats the old Visibility and Integrations addresses as Settings', () => {
        const nav = buildFormNav({ form: baseForm, base: BASE, pathname: `${BASE}/visibility`, can: () => true, formRevisionsUiEnabled: false, t });
        expect(nav.find((item) => item.active)?.key).toBe('settings');
    });
});
