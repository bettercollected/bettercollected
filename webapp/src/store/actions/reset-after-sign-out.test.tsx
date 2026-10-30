import React from 'react';

import { render } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it } from 'vitest';

import AuthDispatcher from '@app/app/_dispatcher/auth-dispatcher';
import { setAuth } from '@app/store/auth/slice';
import { formsApi } from '@app/store/redux/form-api';
import { store } from '@app/store/store';
import { workspacesApi } from '@app/store/workspaces/api';
import { rememberResponseListPage, rememberResponseListView, rememberedListView } from '@app/utils/response-list-memory';

import { resetAfterSignOut, resetIfUserChanged } from './reset-after-sign-out';

const key = { workspaceId: 'workspace-1', formId: 'form-1', searchText: 'anna@example.com' };

// what a signed-in staff member leaves behind: a list memory with their search, and cached responses and forms
async function leaveSomethingBehind() {
    rememberResponseListView(key, 2);
    rememberResponseListPage(key, { page: 2, size: 15, total: 16, ids: ['r16'] });
    await store.dispatch(workspacesApi.util.upsertQueryData('getWorkspaceSubmission', { workspace_id: 'workspace-1', submission_id: 'r16' }, { response: { responseId: 'r16', answers: { q1: { text: 'secret' } } } }) as any);
    await store.dispatch(formsApi.util.upsertQueryData('getFormResponse' as any, { workspaceId: 'workspace-1', responseId: 'r16' }, { responseId: 'r16' }) as any);
    expect(Object.keys(store.getState().workspacesApi.queries)).not.toHaveLength(0);
    expect(Object.keys(store.getState().formsApi.queries)).not.toHaveLength(0);
}

const forgotten = () => {
    expect(rememberedListView('workspace-1', 'form-1')).toBeNull();
    expect(store.getState().workspacesApi.queries).toEqual({});
    expect(store.getState().formsApi.queries).toEqual({});
};
const kept = () => {
    expect(rememberedListView('workspace-1', 'form-1')).toEqual({ page: 2, searchText: 'anna@example.com' });
    expect(Object.keys(store.getState().workspacesApi.queries)).not.toHaveLength(0);
    expect(Object.keys(store.getState().formsApi.queries)).not.toHaveLength(0);
};

describe('the one reset after a sign-out', () => {
    beforeEach(() => {
        store.dispatch(setAuth({ id: 'me', email: 'staff@example.com', roles: [] } as any));
    });

    it('forgets the responses list memory and empties the workspaces and forms caches', async () => {
        await leaveSomethingBehind();
        resetAfterSignOut(store.dispatch);
        forgotten();
    });

    it('when the server says nobody is signed in any more', async () => {
        await leaveSomethingBehind();
        store.dispatch(resetIfUserChanged(undefined) as any);
        forgotten();
    });

    it('when someone else is signed in now', async () => {
        await leaveSomethingBehind();
        store.dispatch(resetIfUserChanged('someone-else') as any);
        forgotten();
    });

    it('not for the same user, and not when nobody was signed in here', async () => {
        await leaveSomethingBehind();
        store.dispatch(resetIfUserChanged('me') as any);
        kept();
        store.dispatch(setAuth({ id: '' } as any));
        store.dispatch(resetIfUserChanged(undefined) as any);
        kept();
    });
});

describe('AuthDispatcher (the server reports who is signed in)', () => {
    const renderWith = (auth: any) =>
        render(
            <ReduxProvider store={store}>
                <AuthDispatcher auth={auth}>
                    <span />
                </AuthDispatcher>
            </ReduxProvider>
        );

    beforeEach(() => {
        store.dispatch(setAuth({ id: 'me', email: 'staff@example.com', roles: [] } as any));
    });

    it('forgets what the last user saw when the session is gone', async () => {
        await leaveSomethingBehind();
        renderWith(null);
        forgotten();
        expect(store.getState().auth.id).toBe('');
    });

    it('keeps it for the same user', async () => {
        await leaveSomethingBehind();
        renderWith({ id: 'me', email: 'staff@example.com', roles: [] });
        kept();
        expect(store.getState().auth.id).toBe('me');
    });
});
