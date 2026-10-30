import React from 'react';

import { render } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

// what the /auth/status poll answers: an RTK Query fetchBaseQuery error (or none) and the data
const status: { error: any; data: any; calls: Array<{ skip: boolean }> } = { error: undefined, data: undefined, calls: [] };
const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));
vi.mock('@app/utils/domain-utils', () => ({ isAdminDomain: () => false }));
vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetStatusQuery: (_arg: any, options: any) => {
            status.calls.push({ skip: !!options?.skip });
            return options?.skip ? { data: undefined, isLoading: false } : options.selectFromResult({ data: status.data, isLoading: false, isError: !!status.error, error: status.error });
        },
        useRefreshTokenMutation: () => [vi.fn()]
    };
});

import { setAuth } from '@app/store/auth/slice';
import { formsApi } from '@app/store/redux/form-api';
import { store } from '@app/store/store';
import { workspacesApi } from '@app/store/workspaces/api';
import { rememberResponseListView, rememberedListView } from '@app/utils/response-list-memory';

import AuthStatusDispatcher from './auth-status-dispatcher';

// one workspace object: a new one on every render would re-run the effect and hide a missing dependency
const workspace = { id: 'workspace-1' } as any;
const tree = () => (
    <ReduxProvider store={store}>
        <AuthStatusDispatcher workspace={workspace}>
            <span />
        </AuthStatusDispatcher>
    </ReduxProvider>
);
const renderDispatcher = () => render(tree());

async function leaveSomethingBehind() {
    rememberResponseListView({ workspaceId: 'workspace-1', formId: 'form-1', searchText: 'anna@example.com' }, 2);
    await store.dispatch(workspacesApi.util.upsertQueryData('getWorkspaceSubmission', { workspace_id: 'workspace-1', submission_id: 'r16' }, { response: { responseId: 'r16' } }) as any);
    await store.dispatch(formsApi.util.upsertQueryData('getFormResponse' as any, { workspaceId: 'workspace-1', responseId: 'r16' }, { responseId: 'r16' }) as any);
}

describe('the session status check', () => {
    beforeEach(() => {
        status.error = undefined;
        status.data = undefined;
        status.calls = [];
        replace.mockReset();
        store.dispatch(setAuth({ id: 'me', email: 'staff@example.com', roles: [], is401: false } as any));
    });

    it.each([
        ['a 401', { status: 401, data: { detail: 'No user logged in.' } }],
        ['a 401 with a body that is not JSON', { status: 'PARSING_ERROR', originalStatus: 401, data: 'Unauthorized', error: 'SyntaxError' }]
    ])('forgets what the user saw once the session has ended (%s), and stops asking', async (_name, error) => {
        await leaveSomethingBehind();
        status.data = { id: 'me', email: 'staff@example.com', roles: [] };
        status.error = error;
        renderDispatcher();
        expect(store.getState().auth.id).toBe('');
        expect(rememberedListView('workspace-1', 'form-1')).toBeNull();
        expect(store.getState().workspacesApi.queries).toEqual({});
        expect(store.getState().formsApi.queries).toEqual({});
        // signed out once: the poll is skipped from then on (no loop of resets and reloads)
        expect(status.calls.at(-1)?.skip).toBe(true);
        expect(replace).toHaveBeenCalledTimes(1);
    });

    it.each([
        ['a network failure', { status: 'FETCH_ERROR', error: 'TypeError: Failed to fetch' }],
        ['a timeout', { status: 'TIMEOUT_ERROR', error: 'AbortError' }],
        ['a 502 error page during a deploy', { status: 'PARSING_ERROR', originalStatus: 502, data: '<html>Bad Gateway</html>', error: 'SyntaxError' }],
        ['a 503 (sign-in temporarily unavailable)', { status: 503, data: { detail: 'Sign-in is temporarily unavailable.' } }],
        ['a 429', { status: 429, data: { detail: 'Too many requests' } }]
    ])('keeps the user signed in, with their caches, on %s, and asks again', async (_name, error) => {
        await leaveSomethingBehind();
        // RTK Query keeps the last answer while the latest request failed
        status.data = { id: 'me', email: 'staff@example.com', roles: [] };
        status.error = error;
        renderDispatcher();
        expect(store.getState().auth.id).toBe('me');
        expect(store.getState().auth.is401).not.toBe(true);
        expect(rememberedListView('workspace-1', 'form-1')).not.toBeNull();
        expect(Object.keys(store.getState().workspacesApi.queries)).not.toHaveLength(0);
        expect(Object.keys(store.getState().formsApi.queries)).not.toHaveLength(0);
        expect(replace).not.toHaveBeenCalled();
        // the poll is not skipped: its next round asks again
        expect(status.calls.every((call) => !call.skip)).toBe(true);
    });

    it('keeps the user signed in when the very first check fails without an answer', async () => {
        await leaveSomethingBehind();
        status.error = { status: 'FETCH_ERROR', error: 'TypeError: Failed to fetch' };
        renderDispatcher();
        expect(store.getState().auth.id).toBe('me');
        expect(Object.keys(store.getState().workspacesApi.queries)).not.toHaveLength(0);
        expect(replace).not.toHaveBeenCalled();
    });

    it('notices on the next poll that another tab signed in as someone else', async () => {
        await leaveSomethingBehind();
        status.data = { id: 'me', email: 'staff@example.com', roles: [] };
        const { rerender } = renderDispatcher();
        expect(store.getState().auth.id).toBe('me');
        expect(Object.keys(store.getState().workspacesApi.queries)).not.toHaveLength(0);

        // the poll answers with another user; nothing else changed
        status.data = { id: 'someone-else', email: 'other@example.com', roles: [] };
        rerender(tree());
        expect(store.getState().auth.id).toBe('someone-else');
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
