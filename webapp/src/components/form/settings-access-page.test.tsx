// Settings, Access, with form-level access on and off: two groups with headings that tell the team question from the
// respondent one, and with it off the page exactly as it was (no card, no extra request).
import React from 'react';

import { render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import FormSettingsPage from './settings';

import commonNl from '../../../public/locales/nl/common.json';

const served = vi.hoisted(() => ({ enabled: true, queries: 0 }));

vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => ['form.edit', 'form.share'].includes(permission), saveDraftsEnabled: true, isLoading: false, formAccessEnabled: served.enabled })
}));
vi.mock('@app/store/workspaces/api', async (original) => ({ ...((await original()) as object), usePatchFormSettingsMutation: () => [vi.fn()] }));
vi.mock('@app/store/workspaces/form-access-api', async (original) => ({
    ...((await original()) as object),
    useGetFormAccessQuery: () => {
        served.queries += 1;
        return { data: { enabled: true, restricted: false, canManage: true, myPermissions: [], grants: [] }, isLoading: false, isError: false, refetch: vi.fn() };
    },
    useGetTeamsQuery: () => ({ data: [] }),
    useSetFormAccessModeMutation: () => [vi.fn(), { isLoading: false }],
    usePutFormGrantMutation: () => [vi.fn(), { isLoading: false }],
    useDeleteFormGrantMutation: () => [vi.fn(), { isLoading: false }]
}));
vi.mock('@app/store/workspaces/members-n-invitations-api', async (original) => ({ ...((await original()) as object), useGetWorkspaceMembersQuery: () => ({ data: [] }) }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal: vi.fn() }) }));
vi.mock('@app/components/modal-views/full-screen-modal-context', () => ({ useFullScreenModal: () => ({}) }));
vi.mock('@Components/modals/contexts/bottom-sheet-modal-context', () => ({ useBottomSheetModal: () => ({ openBottomSheetModal: vi.fn() }) }));

const open = (settings: Record<string, unknown> = {}) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'acme', isPro: true } as any));
    store.dispatch(setForm({ formId: 'f1', builderVersion: 'v2', title: 'Survey', fields: [], isPublished: true, settings: { provider: 'self', ...settings } } as any));
    return render(
        <ReduxProvider store={store}>
            <FormSettingsPage page="access" />
        </ReduxProvider>
    );
};

describe('Settings, Access', () => {
    beforeAll(() => {
        i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    });

    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    beforeEach(() => {
        served.enabled = true;
        served.queries = 0;
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
    });

    it('with the switch on has two groups, the team first, each named for who it is about', () => {
        open();
        const access = within(screen.getByRole('region', { name: 'Access' }));
        expect(access.getAllByRole('heading', { level: 3 }).slice(0, 2).map((heading) => heading.textContent)).toEqual(['Who on your team can open this form', 'Who can see this form as a respondent']);
        expect(access.getByText(/Respondents are the people who fill the form in/)).toBeInTheDocument();
        expect(access.getByRole('radio', { name: /Public/ })).toBeInTheDocument();
    });

    it('with the switch on, Private says who can see it in the team\'s terms', () => {
        open({ hidden: true });
        expect(screen.getByText('Only you, owners, admins and the people you add can see this form.')).toBeInTheDocument();
        expect(screen.queryByText('Only you can see this form.')).toBeNull();
    });

    it('with the switch off is the page it was: no card, no request, the old heading and text', () => {
        served.enabled = false;
        open({ hidden: true });
        expect(screen.queryByTestId('form-access-card')).toBeNull();
        expect(served.queries).toBe(0);
        expect(screen.getByRole('heading', { level: 3, name: 'Who can see this form' })).toBeInTheDocument();
        expect(screen.queryByText('Who on your team can open this form')).toBeNull();
        expect(screen.getByText('Only you can see this form.')).toBeInTheDocument();
    });

    it('is Dutch in Dutch, formal', async () => {
        await i18n.changeLanguage('nl');
        open();
        const access = within(screen.getByRole('region', { name: 'Toegang' }));
        expect(access.getAllByRole('heading', { level: 3 }).slice(0, 2).map((heading) => heading.textContent)).toEqual(['Wie in uw team dit formulier kan openen', 'Wie dit formulier als respondent kan zien']);
    });

    it('has no accessibility violations with the card on', async () => {
        const { container } = open();
        expect(await axeViolations(container)).toEqual([]);
    });
});
