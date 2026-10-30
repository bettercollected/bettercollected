import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }), usePathname: () => '/acme/dashboard', useSearchParams: () => new URLSearchParams() }));

const closeModal = vi.fn();
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal }) }));

vi.mock('@app/store/auth/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useLogoutMutation: () => [() => Promise.resolve({ data: {} })], useLazyGetStatusQuery: () => [() => Promise.resolve({ data: {} })] };
});

import { setAuth } from '@app/store/auth/slice';
import { formsApi } from '@app/store/redux/form-api';
import { store } from '@app/store/store';
import { workspacesApi } from '@app/store/workspaces/api';
import { rememberResponseListPage, rememberResponseListView, rememberedListView, rememberedNeighbours } from '@app/utils/response-list-memory';

import LogoutView from './logout-view';

const key = { workspaceId: 'workspace-1', formId: 'form-1', searchText: 'anna@example.com' };

describe('logging out', () => {
    beforeEach(() => {
        push.mockReset();
        closeModal.mockReset();
        store.dispatch(setAuth({ id: 'me', email: 'staff@example.com', roles: [] } as any));
    });

    it('forgets what this user saw: the responses list memory (its search) and the cached responses and forms', async () => {
        rememberResponseListView(key, 2);
        rememberResponseListPage(key, { page: 2, size: 15, total: 16, ids: ['r16'] });
        await store.dispatch(workspacesApi.util.upsertQueryData('getWorkspaceSubmission', { workspace_id: 'workspace-1', submission_id: 'r16' }, { response: { responseId: 'r16', answers: { q1: { text: 'secret' } } } }) as any);
        await store.dispatch(formsApi.util.upsertQueryData('getFormResponse' as any, { workspaceId: 'workspace-1', responseId: 'r16' }, { responseId: 'r16' }) as any);
        expect(Object.keys(store.getState().workspacesApi.queries)).not.toHaveLength(0);
        expect(Object.keys(store.getState().formsApi.queries)).not.toHaveLength(0);

        render(
            <ReduxProvider store={store}>
                <LogoutView />
            </ReduxProvider>
        );
        await act(async () => {
            fireEvent.click(screen.getByRole('button', { name: 'Yes' }));
        });

        expect(push).toHaveBeenCalledWith('/login');
        expect(store.getState().auth.id).toBeFalsy();
        // Back to the list after logout: no search, no page, no previous/next of the last user
        expect(rememberedListView('workspace-1', 'form-1')).toBeNull();
        expect(rememberedNeighbours('workspace-1', 'form-1', 'r16')).toEqual({});
        // nothing of theirs left in the caches a page could draw from
        expect(store.getState().workspacesApi.queries).toEqual({});
        expect(store.getState().formsApi.queries).toEqual({});
        expect(closeModal).toHaveBeenCalled();
    });
});
