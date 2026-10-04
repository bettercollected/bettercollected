import React from 'react';

import { act, renderHook } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';
import { WORKSPACE_PERMISSIONS_TAG, workspacesApi } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

import { useWorkspacePermissions } from './use-workspace-permissions';

const query: { result: any; calls: Array<{ arg: any; options: any }> } = { result: {}, calls: [] };
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspacePermissionsQuery: (arg: any, options: any) => {
            query.calls.push({ arg, options });
            return options?.skip ? { data: undefined, isLoading: false, isError: false } : { isLoading: false, isError: false, ...query.result };
        }
    };
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;

describe('useWorkspacePermissions', () => {
    beforeEach(() => {
        query.result = {};
        query.calls = [];
        store.dispatch(setWorkspace({ id: 'workspace-1', ownerId: 'owner-1' } as any));
        store.dispatch(setAuth({ id: 'admin-1' }));
    });

    it('answers from the backend permissions, not from who owns the workspace', () => {
        query.result = { data: { permissions: [WorkspacePermission.MEMBERS_MANAGE, WorkspacePermission.FORM_READ] } };
        const { result } = renderHook(() => useWorkspacePermissions(), { wrapper });

        expect(result.current.can(WorkspacePermission.MEMBERS_MANAGE)).toBe(true);
        expect(result.current.can(WorkspacePermission.WORKSPACE_BILLING)).toBe(false);
        expect(query.calls.at(-1)?.arg).toEqual({ workspaceId: 'workspace-1', userId: 'admin-1' });
    });

    it('grants nothing until the permissions have loaded', () => {
        const { result } = renderHook(() => useWorkspacePermissions(), { wrapper });
        expect(result.current.can(WorkspacePermission.FORM_READ)).toBe(false);
    });

    it('grants nothing when the request fails', () => {
        query.result = { isError: true, data: { permissions: [WorkspacePermission.MEMBERS_MANAGE] } };
        const { result } = renderHook(() => useWorkspacePermissions(), { wrapper });
        expect(result.current.can(WorkspacePermission.MEMBERS_MANAGE)).toBe(false);
    });

    it('does not ask while signed out', () => {
        store.dispatch(setAuth({ id: '' }));
        query.result = { data: { permissions: [WorkspacePermission.FORM_READ] } };
        const { result } = renderHook(() => useWorkspacePermissions(), { wrapper });

        expect(query.calls.at(-1)?.options.skip).toBe(true);
        expect(result.current.can(WorkspacePermission.FORM_READ)).toBe(false);
    });

    it('drops the cached permissions when the signed-in user changes', () => {
        const dispatched: any[] = [];
        const original = store.dispatch;
        const spy = vi.spyOn(store, 'dispatch').mockImplementation((action: any) => {
            dispatched.push(action);
            return original(action);
        });
        renderHook(() => useWorkspacePermissions(), { wrapper });

        act(() => {
            store.dispatch(setAuth({ id: 'someone-else' }));
        });

        const invalidate = workspacesApi.util.invalidateTags([WORKSPACE_PERMISSIONS_TAG]);
        expect(dispatched.some((action) => action?.type === invalidate.type && JSON.stringify(action.payload) === JSON.stringify(invalidate.payload))).toBe(true);
        expect(query.calls.at(-1)?.arg).toEqual({ workspaceId: 'workspace-1', userId: 'someone-else' });
        spy.mockRestore();
    });
});
