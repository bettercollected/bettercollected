import React from 'react';

import { render } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AuthDispatcher from '@app/app/_dispatcher/auth-dispatcher';
import { API_SLICES } from '@app/store/api-slices';
import { authApi } from '@app/store/auth/api';
import { setAuth } from '@app/store/auth/slice';
import { initFormState, setForm } from '@app/store/forms/slice';
import { formsApi } from '@app/store/redux/form-api';
import { store } from '@app/store/store';
import { workspacesApi } from '@app/store/workspaces/api';
import { membersNInvitationsApi } from '@app/store/workspaces/members-n-invitations-api';
import { rememberResponseListPage, rememberResponseListView, rememberedListView } from '@app/utils/response-list-memory';
import { readServerAuthAnswer } from '@app/utils/session-answer';

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

    it('covers every RTK Query API slice the store holds (a new slice must be added to API_SLICES)', () => {
        // an RTK Query slice's state has queries, mutations, provided and config
        const apiSlicesInTheStore = Object.entries(store.getState())
            .filter(([, value]) => !!value && typeof value === 'object' && ['queries', 'mutations', 'provided', 'config'].every((key) => key in (value as object)))
            .map(([reducerPath]) => reducerPath)
            .sort();
        expect(apiSlicesInTheStore.length).toBeGreaterThan(10);
        expect(API_SLICES.map((api) => api.reducerPath).sort()).toEqual(apiSlicesInTheStore);
    });

    it('resets every API slice but authApi (which reads who is signed in now)', () => {
        const dispatched: string[] = [];
        const original = store.dispatch;
        const spy = vi.spyOn(store, 'dispatch').mockImplementation((action: any) => {
            if (action?.type) dispatched.push(action.type);
            return original(action);
        });
        try {
            resetAfterSignOut(store.dispatch);
        } finally {
            spy.mockRestore();
        }
        const others = API_SLICES.filter((api) => api.reducerPath !== authApi.reducerPath);
        expect(others).toHaveLength(API_SLICES.length - 1);
        for (const api of others) expect(dispatched).toContain(api.util.resetApiState().type);
        expect(dispatched).not.toContain(authApi.util.resetApiState().type);
    });

    it("empties the members and invitations cache and the form last opened, and keeps the auth status", async () => {
        await store.dispatch(membersNInvitationsApi.util.upsertQueryData('getWorkspaceMembers' as any, { workspaceId: 'workspace-1' } as any, [{ email: 'member@example.com' }] as any) as any);
        await store.dispatch(authApi.util.upsertQueryData('getStatus', undefined, { id: 'me', email: 'staff@example.com', roles: [] } as any) as any);
        store.dispatch(setForm({ ...initFormState, formId: 'form-1', title: 'Intake' }));
        expect(Object.keys(store.getState()[membersNInvitationsApi.reducerPath].queries)).not.toHaveLength(0);

        resetAfterSignOut(store.dispatch);

        expect(store.getState()[membersNInvitationsApi.reducerPath].queries).toEqual({});
        expect(store.getState().form.formId).toBe('');
        expect(Object.keys(store.getState().authApi.queries)).not.toHaveLength(0);
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

    it('forgets what the last user saw when the server says nobody is signed in (401)', async () => {
        await leaveSomethingBehind();
        renderWith(readServerAuthAnswer(401, { detail: 'No user logged in.' }));
        forgotten();
        expect(store.getState().auth.id).toBe('');
    });

    it('forgets it when someone else is signed in now', async () => {
        await leaveSomethingBehind();
        renderWith(readServerAuthAnswer(200, { id: 'someone-else', email: 'other@example.com', roles: [] }));
        forgotten();
        expect(store.getState().auth.id).toBe('someone-else');
    });

    it('keeps it for the same user', async () => {
        await leaveSomethingBehind();
        renderWith(readServerAuthAnswer(200, { id: 'me', email: 'staff@example.com', roles: [] }));
        kept();
        expect(store.getState().auth.id).toBe('me');
    });

    it.each([
        ['a 502 error page', 502, '<html>Bad Gateway</html>'],
        ['a 503 without a user', 503, { detail: 'Sign-in is temporarily unavailable.' }],
        ['a 500 without a body', 500, null]
    ])('keeps the user signed in, with their caches, on %s', async (_name, code, body) => {
        await leaveSomethingBehind();
        renderWith(readServerAuthAnswer(code as number, body));
        kept();
        expect(store.getState().auth.id).toBe('me');
    });
});
