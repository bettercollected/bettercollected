import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { setWorkspace } from '@app/store/workspaces/slice';
import { store } from '@app/store/store';

import WorkspaceMenuDropdown, { canOpenWorkspace } from './workspace-menu-dropdown';

const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));

const mine: { data: any[] } = { data: [] };
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useGetAllMineWorkspacesQuery: () => ({ data: mine.data, isLoading: false }) };
});

const space = (id: string, extra: Record<string, unknown> = {}) => ({ id, title: `Space ${id}`, workspaceName: `space-${id}`, ownerId: 'someone', ...extra }) as any;

describe('canOpenWorkspace', () => {
    it('opens an enabled workspace for anyone', () => {
        expect(canOpenWorkspace(space('a'))).toBe(true);
        expect(canOpenWorkspace(space('a', { isOwner: false }))).toBe(true);
    });

    it('opens a disabled workspace for its owners only', () => {
        expect(canOpenWorkspace(space('a', { disabled: true, isOwner: true }))).toBe(true);
        expect(canOpenWorkspace(space('a', { disabled: true, isOwner: false }))).toBe(false);
        expect(canOpenWorkspace(space('a', { disabled: true }))).toBe(false);
        expect(canOpenWorkspace(undefined)).toBe(false);
    });
});

describe('WorkspaceMenuDropdown', () => {
    beforeEach(() => {
        push.mockReset();
        store.dispatch(setWorkspace(space('current')));
    });

    const openMenu = () => {
        render(
            <ReduxProvider store={store}>
                <WorkspaceMenuDropdown />
            </ReduxProvider>
        );
        fireEvent.click(screen.getAllByText('Space current')[0]);
    };

    it('switches an owner into their disabled workspace and marks it read-only', () => {
        mine.data = [space('current', { isOwner: true }), space('downgraded', { disabled: true, isOwner: true })];
        openMenu();
        expect(screen.getByText(/DASHBOARD_DRAWER\.READ_ONLY|Read-only/)).toBeTruthy();
        fireEvent.click(screen.getByText('Space downgraded'));
        expect(push).toHaveBeenCalledWith('/space-downgraded/dashboard/forms');
    });

    it('does not switch a member into a disabled workspace', () => {
        mine.data = [space('current', { isOwner: true }), space('downgraded', { disabled: true, isOwner: false })];
        openMenu();
        fireEvent.click(screen.getByText('Space downgraded'));
        expect(push).not.toHaveBeenCalled();
    });
});
