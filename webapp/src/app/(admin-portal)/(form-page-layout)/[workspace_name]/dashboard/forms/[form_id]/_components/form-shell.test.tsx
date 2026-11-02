// The form's focused shell: one bar (back, title, status, actions), the sections
// of the form down the side (a sheet on a phone), a skip link and the page; no workspace navbar.
import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
import { buildFormNav, currentItem } from './form-nav';
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

const rail = () => within(screen.getByRole('navigation', { name: 'Form sections' }));
const labels = (links: HTMLElement[]) => links.map((link) => link.textContent);

beforeAll(() => {
    i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    (window as any).PUBLIC_CONFIG = { FORM_DOMAIN: 'forms.example.com', HTTP_SCHEME: 'https://', DASHBOARD_DOMAIN: 'app.example.com' };
});

beforeEach(() => {
    window.localStorage.clear();
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

describe('the side menu', () => {
    it('is a nav of links with Deletion requests under Responses, the current page marked', () => {
        show();
        expect(labels(rail().getAllByRole('link'))).toEqual(['Pages', 'Responses12', 'Deletion requests0', 'Analytics', 'Share', 'Settings']);
        const current = rail()
            .getAllByRole('link')
            .filter((link) => link.getAttribute('aria-current') === 'page');
        expect(current).toHaveLength(1);
        expect(current[0]).toHaveAttribute('href', `${BASE}/responses`);
    });

    it('marks only the deepest page current: Deletion requests, not Responses', () => {
        show({ deletionRequests: 2 }, { pathname: `${BASE}/deletion-requests` });
        expect(rail().getByRole('link', { name: /Deletion requests/ })).toHaveAttribute('aria-current', 'page');
        expect(rail().getByRole('link', { name: /^Responses/ })).not.toHaveAttribute('aria-current');
    });

    it('shows Versions when the server offers them', () => {
        show({}, { revisions: true, pathname: `${BASE}/versions/2` });
        expect(rail().getByRole('link', { name: 'Versions' })).toHaveAttribute('aria-current', 'page');
    });

    it('leaves Deletion requests out for who may read responses but not handle privacy', () => {
        show({}, { granted: [WorkspacePermission.RESPONSE_READ, WorkspacePermission.FORM_EDIT] });
        expect(labels(rail().getAllByRole('link'))).toEqual(['Pages', 'Responses12', 'Analytics', 'Share', 'Settings']);
    });

    it('has no old tab row and no segment control', () => {
        show();
        expect(screen.getAllByRole('navigation')).toHaveLength(1);
        expect(screen.queryByText('All responses')).toBeNull();
    });

    it('is Dutch in Dutch', async () => {
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        show();
        expect(screen.getByRole('link', { name: 'Terug naar formulieren' })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Direct naar de inhoud' })).toBeInTheDocument();
        expect(labels(within(screen.getByRole('navigation', { name: 'Onderdelen van het formulier' })).getAllByRole('link'))).toEqual(['Pagina’s', 'Reacties12', 'Verwijderverzoeken0', 'Analyse', 'Delen', 'Instellingen']);
        expect(screen.getByRole('button', { name: 'Onderdelen uitklappen' })).toBeInTheDocument();
    });
});

describe('the Settings pages in the side menu', () => {
    const SETTINGS = ['Access', 'Availability', 'Respondent experience', 'Automations', 'Advanced'];

    it('opens in place while Settings is the section: five pages, the current one marked, Settings itself not', () => {
        show({}, { pathname: `${BASE}/settings/availability` });
        const links = rail().getAllByRole('link');
        expect(labels(links).slice(-6)).toEqual(['Settings', ...SETTINGS]);
        expect(rail().getByRole('link', { name: 'Availability' })).toHaveAttribute('aria-current', 'page');
        expect(rail().getByRole('link', { name: 'Availability' })).toHaveAttribute('href', `${BASE}/settings/availability`);
        expect(rail().getByRole('link', { name: 'Settings' })).not.toHaveAttribute('aria-current');
    });

    it('stays closed on the other sections, and Settings leads to Access', () => {
        show();
        expect(rail().queryByRole('link', { name: 'Availability' })).toBeNull();
        expect(rail().getByRole('link', { name: 'Settings' })).toHaveAttribute('href', `${BASE}/settings/access`);
    });

    it('lists only the pages an imported form has', () => {
        show({ settings: { provider: 'google' }, builderVersion: undefined }, { pathname: `${BASE}/settings/access`, granted: [WorkspacePermission.FORM_EDIT, WorkspacePermission.RESPONSE_READ] });
        expect(labels(rail().getAllByRole('link')).slice(-3)).toEqual(['Settings', 'Access', 'Respondent experience']);
    });

    it('is Dutch in Dutch', async () => {
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        show({}, { pathname: `${BASE}/settings/experience` });
        expect(labels(within(screen.getByRole('navigation', { name: 'Onderdelen van het formulier' })).getAllByRole('link')).slice(-6)).toEqual(['Instellingen', 'Toegang', 'Beschikbaarheid', 'Ervaring van respondenten', 'Automatiseringen', 'Geavanceerd']);
    });

    it('is in the phone sheet whichever section is open, named with its section', async () => {
        show({}, { pathname: `${BASE}/settings/automations` });
        expect(screen.getByRole('button', { name: 'Section: Settings · Automations. Choose another section' })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /^Section: / }));
        const sheet = await screen.findByRole('dialog', { name: 'Go to section' });
        expect(labels(within(sheet).getAllByRole('link')).slice(-6)).toEqual(['Settings', ...SETTINGS]);
        expect(within(sheet).getByRole('link', { name: 'Automations' })).toHaveAttribute('aria-current', 'page');
    });

    it('has no accessibility violations on a Settings page, with the sheet open', async () => {
        show({}, { pathname: `${BASE}/settings/access` });
        expect(await axeViolations(document.body, { page: true })).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: /^Section: / }));
        await screen.findByRole('dialog');
        expect(await axeViolations(document.body)).toEqual([]);
    });
});

describe('collapsing the side menu', () => {
    const toggle = () => screen.getByRole('button', { name: /sections$/ });

    it('is collapsed by default on a narrow screen, with a collapse button that says what it controls', () => {
        show();
        // jsdom has no wide screen: the default is collapsed
        expect(toggle()).toHaveAttribute('aria-expanded', 'false');
        expect(toggle()).toHaveAttribute('aria-controls', 'form-rail');
        expect(document.getElementById('form-rail')).not.toBeNull();
        // the icons still have names
        expect(rail().getByRole('link', { name: 'Responses12' })).toBeInTheDocument();
    });

    it('expands on a wide screen unless the viewer chose otherwise', () => {
        const match = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() });
        vi.stubGlobal('matchMedia', match);
        try {
            show();
            expect(toggle()).toHaveAttribute('aria-expanded', 'true');
            expect(toggle()).toHaveAccessibleName('Collapse sections');
        } finally {
            vi.unstubAllGlobals();
        }
    });

    it("remembers the viewer's choice", () => {
        const first = show();
        fireEvent.click(toggle());
        expect(toggle()).toHaveAttribute('aria-expanded', 'true');
        expect(toggle()).toHaveAccessibleName('Collapse sections');
        expect(window.localStorage.getItem('form-rail-collapsed')).toBe('0');
        first.unmount();

        show();
        expect(toggle()).toHaveAttribute('aria-expanded', 'true');
        fireEvent.click(toggle());
        expect(window.localStorage.getItem('form-rail-collapsed')).toBe('1');
        expect(toggle()).toHaveAccessibleName('Expand sections');
    });

    it('works with storage blocked', () => {
        const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
            throw new Error('blocked');
        });
        try {
            show();
            fireEvent.click(toggle());
            expect(toggle()).toHaveAttribute('aria-expanded', 'true');
        } finally {
            spy.mockRestore();
            set.mockRestore();
        }
    });
});

describe('the section switcher on a phone', () => {
    const trigger = () => screen.getByRole('button', { name: /^Section: / });

    it('names the current section and opens a sheet of all of them', async () => {
        show();
        expect(trigger()).toHaveAccessibleName('Section: Responses. Choose another section');
        fireEvent.click(trigger());
        const sheet = await screen.findByRole('dialog', { name: 'Go to section' });
        const links = within(sheet).getAllByRole('link');
        expect(labels(links)).toEqual(['Pages', 'Responses12', 'Deletion requests0', 'Analytics', 'Share', 'Settings', 'Access', 'Availability', 'Respondent experience', 'Automations', 'Advanced']);
        expect(within(sheet).getByRole('link', { name: /^Responses/ })).toHaveAttribute('aria-current', 'page');
    });

    it('names a sub-page with its section', () => {
        show({}, { pathname: `${BASE}/deletion-requests` });
        expect(trigger()).toHaveAccessibleName('Section: Responses · Deletion requests. Choose another section');
    });

    it('closes on Escape and gives focus back to the switcher', async () => {
        show();
        trigger().focus();
        fireEvent.click(trigger());
        const sheet = await screen.findByRole('dialog', { name: 'Go to section' });
        expect(sheet.contains(document.activeElement)).toBe(true);
        fireEvent.keyDown(sheet, { key: 'Escape' });
        await act(async () => {});
        expect(screen.queryByRole('dialog')).toBeNull();
        await waitFor(() => expect(document.activeElement).toBe(trigger()));
    });

    it('closes when a section is chosen', async () => {
        show();
        fireEvent.click(trigger());
        const sheet = await screen.findByRole('dialog', { name: 'Go to section' });
        fireEvent.click(within(sheet).getByRole('link', { name: 'Analytics' }));
        await act(async () => {});
        expect(screen.queryByRole('dialog')).toBeNull();
    });

    it('is Dutch in Dutch', async () => {
        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        show({}, { pathname: `${BASE}/analytics` });
        expect(screen.getByRole('button', { name: 'Onderdeel: Analyse. Kies een ander onderdeel' })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: /^Onderdeel: / }));
        expect(await screen.findByRole('dialog', { name: 'Ga naar onderdeel' })).toBeInTheDocument();
    });
});

describe('accessibility', () => {
    it('has no violations, with the form menu or the sheet open, in either language', async () => {
        const { unmount } = show();
        expect(await axeViolations(document.body, { page: true })).toEqual([]);
        fireEvent.keyDown(screen.getByRole('button', { name: /More actions/ }), { key: 'Enter' });
        await screen.findByRole('menuitem', { name: /Open form/ });
        expect(await axeViolations(document.body)).toEqual([]);
        unmount();

        await act(async () => {
            await i18n.changeLanguage('nl');
        });
        const second = show({ settings: { provider: 'google' } });
        expect(await axeViolations(document.body, { page: true })).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: /^Onderdeel: / }));
        await screen.findByRole('dialog');
        expect(await axeViolations(document.body)).toEqual([]);
        second.unmount();
    });
});

describe('buildFormNav, who sees which section', () => {
    const t = (key: string) => key;
    const nav = (form: Record<string, unknown>, granted: string[], pathname = `${BASE}/preview`, revisions = false) =>
        buildFormNav({ form: { ...baseForm, ...form }, base: BASE, pathname, can: (p) => granted.includes(p), formRevisionsUiEnabled: revisions, t });
    const items = (...args: Parameters<typeof nav>) => nav(...args).map((item) => item.key);

    it('gives a draft Pages, and Settings to who may edit', () => {
        expect(items({ isPublished: false }, [WorkspacePermission.FORM_EDIT])).toEqual(['preview', 'settings']);
        expect(items({ isPublished: false }, [])).toEqual(['preview']);
    });

    it('gives a published form Responses, Analytics and Share, then Versions, then Settings', () => {
        expect(items({}, ALL, `${BASE}/preview`, true)).toEqual(['preview', 'responses', 'analytics', 'links', 'versions', 'settings']);
    });

    it('puts Deletion requests under Responses for privacy.manage, and not for who only reads', () => {
        const withPrivacy = nav({}, ALL).find((item) => item.key === 'responses');
        expect(withPrivacy?.children?.map((c) => c.key)).toEqual(['deletion-requests']);
        const readOnly = nav({}, [WorkspacePermission.RESPONSE_READ]).find((item) => item.key === 'responses');
        expect(readOnly?.children).toBeUndefined();
    });

    it('gives privacy.manage without response.read only Deletion requests, as a section of its own', () => {
        expect(items({}, [WorkspacePermission.PRIVACY_MANAGE])).toEqual(['preview', 'deletion-requests', 'analytics', 'links']);
    });

    it('drops Analytics and Share once the form is closed', () => {
        expect(items({ settings: { provider: 'self', formCloseDate: '2000-01-01T00:00:00Z' } }, ALL)).toEqual(['preview', 'responses', 'settings']);
    });

    it('needs the server flag and form.read for Versions', () => {
        expect(items({}, [WorkspacePermission.RESPONSE_READ], `${BASE}/preview`, true)).toEqual(['preview', 'responses', 'analytics', 'links']);
        expect(items({}, [WorkspacePermission.FORM_READ], `${BASE}/preview`, true)).toEqual(['preview', 'analytics', 'links', 'versions']);
    });

    describe('Activity, after Versions', () => {
        const withActivity = (granted: string[], form: Record<string, unknown> = {}, pathname = `${BASE}/preview`, on = true) =>
            buildFormNav({ form: { ...baseForm, ...form }, base: BASE, pathname, can: (p) => granted.includes(p), formRevisionsUiEnabled: true, auditLogUiEnabled: on, t }).map((item) => item.key);

        it('sits between Versions and Settings for audit.read, while the server has it on', () => {
            expect(withActivity([...ALL, WorkspacePermission.AUDIT_READ])).toEqual(['preview', 'responses', 'analytics', 'links', 'versions', 'activity', 'settings']);
        });

        it('is the page of its own address', () => {
            const item = buildFormNav({ form: baseForm, base: BASE, pathname: `${BASE}/activity`, can: () => true, formRevisionsUiEnabled: true, auditLogUiEnabled: true, t }).find((i) => i.key === 'activity');
            expect(item).toMatchObject({ href: `${BASE}/activity`, label: 'AUDIT_LOG.NAV', active: true });
        });

        it('is there for a Privacy officer, who has no form.edit and no response.read', () => {
            expect(withActivity([WorkspacePermission.AUDIT_READ, WorkspacePermission.FORM_READ, WorkspacePermission.PRIVACY_MANAGE])).toEqual(['preview', 'deletion-requests', 'analytics', 'links', 'versions', 'activity']);
        });

        it('is there for a draft too: access changes are made before a form is published', () => {
            expect(withActivity([WorkspacePermission.AUDIT_READ], { isPublished: false })).toEqual(['preview', 'activity']);
        });

        it('is not there without audit.read (a grantee Editor holds form rights, not this one) or while the server has it off', () => {
            expect(withActivity(ALL)).not.toContain('activity');
            expect(withActivity([...ALL, WorkspacePermission.AUDIT_READ], {}, `${BASE}/preview`, false)).not.toContain('activity');
        });
    });

    it('treats the old Visibility and Integrations addresses as Settings', () => {
        const visibility = buildFormNav({ form: baseForm, base: BASE, pathname: `${BASE}/visibility`, can: () => true, formRevisionsUiEnabled: false, t });
        expect(visibility.find((item) => item.active)?.key).toBe('settings');
    });

    it('has the page itself as the current item: the sub-page when one is open', () => {
        expect(currentItem(nav({}, ALL, `${BASE}/deletion-requests`))?.key).toBe('deletion-requests');
        expect(currentItem(nav({}, ALL, `${BASE}/responses`))?.key).toBe('responses');
        expect(currentItem(nav({}, ALL, `${BASE}/elsewhere`))).toBeUndefined();
    });
});
