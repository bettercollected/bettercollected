import React from 'react';

import { renderHook } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import { useWorkspacePermissions } from './use-workspace-permissions';

const query: { data: any; calls: Array<{ id: string; options: any }> } = { data: undefined, calls: [] };
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspacePermissionsQuery: (id: string, options: any) => {
            query.calls.push({ id, options });
            return { data: options?.skip ? undefined : query.data, isLoading: false };
        }
    };
});

const wrapper = ({ children }: { children: React.ReactNode }) => <ReduxProvider store={store}>{children}</ReduxProvider>;

describe('useWorkspacePermissions', () => {
    beforeEach(() => {
        query.data = undefined;
        query.calls = [];
        store.dispatch(setWorkspace({ id: 'workspace-1', ownerId: 'owner-1' } as any));
        store.dispatch(setAuth({ id: 'admin-1' }));
    });

    it('answers from the backend permissions, not from who owns the workspace', () => {
        query.data = { permissions: [WorkspacePermission.MEMBERS_MANAGE, WorkspacePermission.FORM_READ] };
        const { result } = renderHook(() => useWorkspacePermissions(), { wrapper });

        expect(result.current.can(WorkspacePermission.MEMBERS_MANAGE)).toBe(true);
        expect(result.current.can(WorkspacePermission.WORKSPACE_BILLING)).toBe(false);
        expect(query.calls.at(-1)?.id).toBe('workspace-1');
    });

    it('grants nothing until the permissions have loaded', () => {
        const { result } = renderHook(() => useWorkspacePermissions(), { wrapper });
        expect(result.current.can(WorkspacePermission.FORM_READ)).toBe(false);
    });

    it('does not ask while signed out', () => {
        store.dispatch(setAuth({ id: '' }));
        query.data = { permissions: [WorkspacePermission.FORM_READ] };
        const { result } = renderHook(() => useWorkspacePermissions(), { wrapper });

        expect(query.calls.at(-1)?.options.skip).toBe(true);
        expect(result.current.can(WorkspacePermission.FORM_READ)).toBe(false);
    });
});
