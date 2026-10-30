import React from 'react';

import { render } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const status: { error: boolean; data: any } = { error: false, data: undefined };
const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));
vi.mock('@app/utils/domain-utils', () => ({ isAdminDomain: () => false }));
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetStatusQuery: (_arg: any, options: any) => (options?.skip ? { data: undefined, isLoading: false } : options.selectFromResult({ data: status.data, isLoading: false, isError: status.error })),
        useRefreshTokenMutation: () => [vi.fn()]
    };
});

import { setAuth } from '@app/store/auth/slice';
import { formsApi } from '@app/store/redux/form-api';
import { store } from '@app/store/store';
import { workspacesApi } from '@app/store/workspaces/api';
import { rememberResponseListView, rememberedListView } from '@app/utils/response-list-memory';

import AuthStatusDispatcher from './auth-status-dispatcher';

const renderDispatcher = () =>
    render(
        <ReduxProvider store={store}>
            <AuthStatusDispatcher workspace={{ id: 'workspace-1' } as any}>
                <span />
            </AuthStatusDispatcher>
        </ReduxProvider>
    );

async function leaveSomethingBehind() {
    rememberResponseListView({ workspaceId: 'workspace-1', formId: 'form-1', searchText: 'anna@example.com' }, 2);
    await store.dispatch(workspacesApi.util.upsertQueryData('getWorkspaceSubmission', { workspace_id: 'workspace-1', submission_id: 'r16' }, { response: { responseId: 'r16' } }) as any);
    await store.dispatch(formsApi.util.upsertQueryData('getFormResponse' as any, { workspaceId: 'workspace-1', responseId: 'r16' }, { responseId: 'r16' }) as any);
}

describe('the session status check', () => {
    beforeEach(() => {
        status.error = false;
        status.data = undefined;
        replace.mockReset();
        store.dispatch(setAuth({ id: 'me', email: 'staff@example.com', roles: [] } as any));
    });

    it('forgets what the user saw once the session has ended (401)', async () => {
        await leaveSomethingBehind();
        status.error = true;
        renderDispatcher();
        expect(store.getState().auth.id).toBe('');
        expect(rememberedListView('workspace-1', 'form-1')).toBeNull();
        expect(store.getState().workspacesApi.queries).toEqual({});
        expect(store.getState().formsApi.queries).toEqual({});
    });

    it('keeps it while the same user is still signed in', async () => {
        await leaveSomethingBehind();
        status.data = { id: 'me', email: 'staff@example.com', roles: [] };
        renderDispatcher();
        expect(store.getState().auth.id).toBe('me');
        expect(rememberedListView('workspace-1', 'form-1')).not.toBeNull();
        expect(Object.keys(store.getState().workspacesApi.queries)).not.toHaveLength(0);
    });
});
