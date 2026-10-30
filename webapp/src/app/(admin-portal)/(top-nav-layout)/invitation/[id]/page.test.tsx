import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const reload = vi.fn();
vi.mock('@app/utils/reload-page', () => ({ reloadPage: () => reload() }));
vi.mock('next/navigation', () => ({ useParams: () => ({ id: 'invite-token' }), useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('@app/app/(auth)/_components/login-view', () => ({ default: () => <div>login</div> }));
vi.mock('@app/components/auth/auth-navbar', () => ({ default: () => null }));
vi.mock('@app/components/invitation/expired', () => ({ default: () => null }));
vi.mock('@Components/invitation/main-valid-user', () => ({ default: () => null }));
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useLogoutMutation: () => [() => Promise.resolve({ data: {} })], useLazyGetStatusQuery: () => [() => Promise.resolve({ data: {} })] };
});
// no invitation for this account: the page offers to switch account
vi.mock('@app/store/workspaces/members-n-invitations-api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useGetWorkspaceInvitationQuery: () => ({ data: undefined, isLoading: false }) };
});

import { invitationConstant } from '@app/constants/locales/invitations';
import { setAuth } from '@app/store/auth/slice';
import { formsApi } from '@app/store/redux/form-api';
import { store } from '@app/store/store';
import { workspacesApi } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';
import { rememberResponseListView, rememberedListView } from '@app/utils/response-list-memory';

import InvitationPage from './page';

describe('"switch account" on the invitation page', () => {
    beforeEach(() => {
        reload.mockReset();
        store.dispatch(setAuth({ id: 'me', email: 'staff@example.com', roles: [] } as any));
        store.dispatch(setWorkspace({ id: 'workspace-1', workspaceName: 'acme' } as any));
    });

    it('signs out with the same reset as the logout dialog: list memory and caches forgotten', async () => {
        rememberResponseListView({ workspaceId: 'workspace-1', formId: 'form-1', searchText: 'anna@example.com' }, 2);
        await store.dispatch(workspacesApi.util.upsertQueryData('getWorkspaceSubmission', { workspace_id: 'workspace-1', submission_id: 'r16' }, { response: { responseId: 'r16' } }) as any);
        await store.dispatch(formsApi.util.upsertQueryData('getFormResponse' as any, { workspaceId: 'workspace-1', responseId: 'r16' }, { responseId: 'r16' }) as any);

        render(
            <ReduxProvider store={store}>
                <InvitationPage />
            </ReduxProvider>
        );
        await act(async () => {
            fireEvent.click(screen.getByText(invitationConstant.switchAccount));
        });

        expect(store.getState().auth.id).toBe('');
        expect(rememberedListView('workspace-1', 'form-1')).toBeNull();
        expect(store.getState().workspacesApi.queries).toEqual({});
        expect(store.getState().formsApi.queries).toEqual({});
        expect(reload).toHaveBeenCalled();
    });
});
