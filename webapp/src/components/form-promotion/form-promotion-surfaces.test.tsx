// Where copying a form to another workspace shows up, and that it shows up nowhere while the server has it off: the form
// menu's item, the Advanced settings' "Form file" card and the "Copied from" line (editors only). No request is made while
// the switch is off.
import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import FormOptionsDropdownMenu from '@app/components/datatable/form-options-dropdown';
import FormSettingsPage from '@app/components/form/settings';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import commonNl from '../../../public/locales/nl/common.json';

const served = vi.hoisted(() => ({
    enabled: true,
    permissions: ['form.read', 'form.edit', 'form.create', 'form.delete'] as string[],
    requests: [] as any[],
    download: (() => Promise.resolve({ blob: new Blob(['{}']), fileName: 'form-f1.json' })) as () => Promise<any>,
    saved: [] as any[],
    mine: [{ id: 'ws-other', title: 'Voorbeeld Acceptatie' }] as any[]
}));

vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => served.permissions.includes(permission), formPromotionEnabled: served.enabled, saveDraftsEnabled: true, isLoading: false, ready: true })
}));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }), usePathname: () => '/acme/dashboard/forms' }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal: vi.fn() }) }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({}) }));
vi.mock('@Components/modals/contexts/bottom-sheet-modal-context', () => ({ useBottomSheetModal: () => ({ openBottomSheetModal: vi.fn() }) }));
vi.mock('@app/components/form/automations/automations-section', () => ({ default: () => <section /> }));
vi.mock('@app/lib/hooks/use-open-formulieren-export-mode', () => ({ useOpenFormulierenExportOn: () => ({ on: false }) }));
vi.mock('@app/lib/hooks/use-breakpoint', () => ({ useIsMobile: () => false }));
// the dialog has its own tests: here it only has to be asked for
vi.mock('./form-promotion-dialog', () => ({ default: ({ open }: { open: boolean }) => (open ? <div role="dialog" aria-label="Copy to another workspace" /> : null) }));
vi.mock('@app/store/workspaces/api', async (original) => ({
    ...((await original()) as object),
    usePatchFormSettingsMutation: () => [vi.fn()],
    useDuplicateFormMutation: () => [vi.fn()],
    useExportFormForOpenFormulierenMutation: () => [vi.fn()],
    useGetAllMineWorkspacesQuery: () => {
        served.requests.push('mine');
        return { data: served.mine, isLoading: false };
    }
}));
vi.mock('@app/store/workspaces/form-promotion-api', async (original) => ({
    ...((await original()) as object),
    useDownloadFormFileMutation: () => [
        (arg: any) => {
            served.requests.push(['download', arg]);
            return { unwrap: () => served.download() };
        },
        { isLoading: false }
    ],
    saveFormFile: (file: any) => served.saved.push(file)
}));

const workspace = { id: 'ws-1', workspaceName: 'acme', title: 'Acme', isPro: true } as any;
const baseForm = { formId: 'f1', title: 'Aanmelding', builderVersion: 'v2', fields: [], isPublished: false, responses: 0, settings: { provider: 'self' } } as any;

const renderMenu = (form: any = baseForm) => {
    render(
        <ReduxProvider store={store}>
            <FormOptionsDropdownMenu workspace={workspace} form={form} hasCustomDomain={false} inHeader />
        </ReduxProvider>
    );
    fireEvent.keyDown(screen.getByTestId('form-menu-trigger'), { key: 'Enter' });
};

const renderAdvanced = (settings: Record<string, unknown> = {}) => {
    store.dispatch(setWorkspace(workspace));
    store.dispatch(setForm({ ...baseForm, settings: { provider: 'self', ...settings } }));
    render(
        <ReduxProvider store={store}>
            <FormSettingsPage page="advanced" />
        </ReduxProvider>
    );
};

beforeAll(() => {
    i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    (window as any).PUBLIC_CONFIG = { FORM_DOMAIN: 'forms.example.com', HTTP_SCHEME: 'https://', DASHBOARD_DOMAIN: 'app.example.com' };
});

beforeEach(() => {
    served.enabled = true;
    served.permissions = ['form.read', 'form.edit', 'form.create', 'form.delete'];
    served.requests = [];
    served.saved = [];
});

afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('the form menu', () => {
    it('offers "Copy to another workspace…" and opens the dialog', async () => {
        renderMenu();
        fireEvent.click(await screen.findByRole('menuitem', { name: 'Copy to another workspace…' }));
        expect(await screen.findByRole('dialog', { name: 'Copy to another workspace' })).toBeInTheDocument();
    });

    it('says it in Dutch', async () => {
        await i18n.changeLanguage('nl');
        renderMenu();
        expect(await screen.findByRole('menuitem', { name: 'Kopiëren naar een andere werkruimte…' })).toBeInTheDocument();
    });

    it('is not there while the server has copying off', async () => {
        served.enabled = false;
        renderMenu();
        await screen.findByRole('menuitem', { name: /Duplicate/i });
        expect(screen.queryByRole('menuitem', { name: /another workspace/ })).toBeNull();
        expect(screen.queryByRole('dialog')).toBeNull();
    });

    it('is not there for a form that is not built from pages here, or for someone who may not read it', async () => {
        renderMenu({ ...baseForm, settings: { provider: 'google' } });
        await screen.findByRole('menuitem', { name: /Delete/i });
        expect(screen.queryByRole('menuitem', { name: /another workspace/ })).toBeNull();
    });
});

describe('Settings, Advanced', () => {
    it('has the Form file card with Download, which downloads the file', async () => {
        renderAdvanced();
        expect(screen.getByText('A file with the questions, logic and look of this form. It holds no answers.')).toBeInTheDocument();
        fireEvent.click(screen.getByTestId('form-file-download'));
        await waitFor(() => expect(served.saved).toHaveLength(1));
        expect(served.requests).toContainEqual(['download', { workspaceId: 'ws-1', formId: 'f1' }]);
    });

    it('says why a restricted form’s file was refused', async () => {
        served.download = () => Promise.reject({ status: 403, data: { code: 'promotion_from_restricted_form' } });
        renderAdvanced();
        fireEvent.click(screen.getByTestId('form-file-download'));
        expect(await screen.findByTestId('form-file-error')).toHaveTextContent('Only an owner, an admin or the creator can download the file of a restricted form.');
        served.download = () => Promise.resolve({ blob: new Blob(['{}']), fileName: 'form-f1.json' });
    });

    it('names the workspace a form was copied from when the viewer is a member of it, else not', async () => {
        renderAdvanced({ promotedFrom: { workspaceId: 'ws-other', formId: 'f0', at: '2026-11-03T10:00:00' } });
        expect(screen.getByTestId('promoted-from-line')).toHaveTextContent('Copied from Voorbeeld Acceptatie on');
        expect(screen.getByTestId('promoted-from-line')).toHaveTextContent('2026');
    });

    it('does not name a workspace the viewer is not in', async () => {
        renderAdvanced({ promotedFrom: { workspaceId: 'ws-elsewhere', formId: 'f0', at: '2026-11-03T10:00:00' } });
        expect(screen.getByTestId('promoted-from-line')).toHaveTextContent('Copied from another workspace on');
    });

    it('has no origin line when the form was not copied (the server sends none to those who may not edit it)', async () => {
        renderAdvanced();
        expect(screen.queryByTestId('promoted-from-line')).toBeNull();
    });

    it('shows nothing of it, and asks nothing, while the server has copying off', async () => {
        served.enabled = false;
        renderAdvanced({ promotedFrom: { workspaceId: 'ws-other', formId: 'f0', at: '2026-11-03T10:00:00' } });
        expect(screen.queryByTestId('form-file-download')).toBeNull();
        expect(screen.queryByTestId('promoted-from-line')).toBeNull();
        expect(served.requests).toEqual([]);
    });
});
