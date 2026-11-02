// The form's bar shows "Restricted" next to Published (text, not colour alone) for a restricted form, only while the
// server has form-level access on.
import React from 'react';

import { render, screen, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import FormShell from './form-shell';

const served = vi.hoisted(() => ({ enabled: true, restricted: true, skips: [] as boolean[] }));

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }), usePathname: () => '/acme/dashboard/forms/f1/responses' }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal: vi.fn() }) }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({ openModal: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: () => true, formAccessEnabled: served.enabled, formRevisionsUiEnabled: false, ready: true, isLoading: false })
}));
vi.mock('@app/lib/hooks/use-open-formulieren-export-mode', () => ({ useOpenFormulierenExportOn: () => ({ on: false }) }));
vi.mock('@app/views/molecules/form-builder/publish-button', () => ({ default: () => <button type="button">Publish</button> }));
vi.mock('@app/store/workspaces/form-access-api', async (original) => ({
    ...((await original()) as object),
    useGetFormAccessQuery: (_args: unknown, options: any) => {
        served.skips.push(!!options?.skip);
        return options?.skip ? { data: undefined } : { data: { enabled: true, restricted: served.restricted } };
    }
}));

const BASE = '/acme/dashboard/forms/f1';
const form = { formId: 'f1', title: 'Join the volunteers', isPublished: true, builderVersion: 'v2', responses: 12, settings: { provider: 'self', pinned: true } } as any;

const show = () => {
    store.dispatch(setWorkspace({ id: 'ws1', workspaceName: 'acme', title: 'Stichting Voorbeeld' } as any));
    store.dispatch(setForm(form));
    return render(
        <ReduxProvider store={store}>
            <FormShell form={form} base={BASE}>
                <p>The page</p>
            </FormShell>
        </ReduxProvider>
    );
};

describe('the form bar chips', () => {
    beforeEach(() => {
        served.enabled = true;
        served.restricted = true;
        served.skips = [];
    });

    it('shows Restricted in words next to Published and Pinned for a restricted form', () => {
        show();
        const bar = within(screen.getByRole('banner'));
        expect(bar.getByText('Published')).toBeInTheDocument();
        expect(bar.getByTestId('restricted-chip').textContent).toBe('Restricted');
        expect(bar.getByText('Pinned')).toBeInTheDocument();
    });

    it('shows no Restricted chip for an open form', () => {
        served.restricted = false;
        show();
        expect(screen.queryByTestId('restricted-chip')).toBeNull();
    });

    it('shows none and asks for nothing while the switch is off', () => {
        served.enabled = false;
        show();
        expect(screen.queryByTestId('restricted-chip')).toBeNull();
        expect(served.skips.every(Boolean)).toBe(true);
    });
});
