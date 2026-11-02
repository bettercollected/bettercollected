import React from 'react';

import { fireEvent, render, screen, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setWorkspace } from '@app/store/workspaces/slice';
import { store } from '@app/store/store';

import WorkspaceMenuDropdown, { canOpenWorkspace, workspaceRoleOf } from './workspace-menu-dropdown';

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

    it('opens the workspace selection screen from "Choose workspace"', () => {
        mine.data = [space('current', { isOwner: true }), space('other')];
        openMenu();
        const entry = screen.getByText(/WORKSPACE_SELECT\.CHOOSE|Choose workspace/).closest('a');
        expect(entry?.getAttribute('href')).toBe('/workspace/select');
    });

    it('remembers the workspace switched to (its id only)', () => {
        window.localStorage.clear();
        mine.data = [space('current', { isOwner: true }), space('other')];
        openMenu();
        fireEvent.click(screen.getByText('Space other'));
        expect(window.localStorage.getItem('bc.lastWorkspaceId')).toBe('other');
    });

    it('does not switch a member into a disabled workspace', () => {
        mine.data = [space('current', { isOwner: true }), space('downgraded', { disabled: true, isOwner: false })];
        openMenu();
        fireEvent.click(screen.getByText('Space downgraded'));
        expect(push).not.toHaveBeenCalled();
    });
});

const ROLE_LABELS: Record<string, { en: string; nl: string }> = {
    OWNER: { en: 'Owner', nl: 'Eigenaar' },
    ADMIN: { en: 'Admin', nl: 'Beheerder' },
    EDITOR: { en: 'Editor', nl: 'Bewerker' },
    REVIEWER: { en: 'Reviewer', nl: 'Beoordelaar' },
    VIEWER: { en: 'Viewer', nl: 'Kijker' },
    PRIVACY_OFFICER: { en: 'Privacy officer', nl: 'Privacyfunctionaris' }
};

describe('workspaceRoleOf', () => {
    it('is Owner for every owner, whatever the role says', () => {
        expect(workspaceRoleOf(space('a', { isOwner: true, role: 'OWNER' }))).toBe('OWNER');
        expect(workspaceRoleOf(space('a', { isOwner: true }))).toBe('OWNER');
    });

    it('reads the listed role, COLLABORATOR as Editor', () => {
        expect(workspaceRoleOf(space('a', { isOwner: false, role: 'VIEWER' }))).toBe('VIEWER');
        expect(workspaceRoleOf(space('a', { isOwner: false, role: 'collaborator' }))).toBe('EDITOR');
    });

    it('falls back to the billing owner only when the list says nothing about owners', () => {
        expect(workspaceRoleOf(space('a', { ownerId: 'me' }), 'me')).toBe('OWNER');
        expect(workspaceRoleOf(space('a', { ownerId: 'me', isOwner: false }), 'me')).toBeUndefined();
    });

    it('is unknown for a missing or unrecognised role', () => {
        expect(workspaceRoleOf(space('a', { isOwner: false }))).toBeUndefined();
        expect(workspaceRoleOf(space('a', { isOwner: false, role: 'SUPERUSER' }))).toBeUndefined();
        expect(workspaceRoleOf(undefined)).toBeUndefined();
    });
});

describe('WorkspaceMenuDropdown role labels', () => {
    beforeEach(() => {
        store.dispatch(setWorkspace(space('current')));
    });
    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    const open = () => {
        render(
            <ReduxProvider store={store}>
                <WorkspaceMenuDropdown />
            </ReduxProvider>
        );
        fireEvent.click(screen.getAllByText('Space current')[0]);
    };
    const rowOf = (id: string) => screen.getAllByText(`Space ${id}`).map((node) => node.closest('div.flex.items-center.justify-between') as HTMLElement).find(Boolean) as HTMLElement;

    for (const lang of ['en', 'nl'] as const) {
        it(`shows each member's real role (${lang})`, async () => {
            await i18n.changeLanguage(lang);
            mine.data = [space('current', { isOwner: true, role: 'OWNER' }), ...Object.keys(ROLE_LABELS).filter((r) => r !== 'OWNER').map((role) => space(role.toLowerCase(), { isOwner: false, role }))];
            open();
            for (const [role, label] of Object.entries(ROLE_LABELS)) {
                if (role === 'OWNER') continue;
                expect(within(rowOf(role.toLowerCase())).getByText(label[lang])).toBeTruthy();
            }
            // never the old catch-all
            expect(screen.queryByText(/Collaborator|Medewerker/)).toBeNull();
        });

        it(`labels a workspace of several owners Owner (${lang})`, async () => {
            await i18n.changeLanguage(lang);
            mine.data = [space('current', { isOwner: true, role: 'OWNER' }), space('co', { isOwner: true, role: 'OWNER', ownerId: 'someone-else' })];
            open();
            expect(within(rowOf('co')).getByText(ROLE_LABELS.OWNER[lang])).toBeTruthy();
        });
    }

    it('shows the current workspace role in the switcher button from the list', () => {
        store.dispatch(setWorkspace(space('current', { ownerId: 'someone' })));
        mine.data = [space('current', { isOwner: false, role: 'REVIEWER' })];
        render(
            <ReduxProvider store={store}>
                <WorkspaceMenuDropdown />
            </ReduxProvider>
        );
        expect(screen.getByText('Reviewer')).toBeTruthy();
    });

    it('shows no label when the role is unknown', () => {
        mine.data = [space('current', { isOwner: false }), space('odd', { isOwner: false, role: 'SUPERUSER' })];
        open();
        expect(screen.queryByText(/Collaborator|Editor|Owner|Admin|Reviewer|Viewer|Privacy officer/)).toBeNull();
        expect(within(rowOf('odd')).queryByText(/./, { selector: 'p.text-black-700' })).toBeNull();
    });

    it('keeps "Read-only" without a stray separator when the role is unknown', () => {
        mine.data = [space('current', { isOwner: true }), space('old', { isOwner: false, disabled: true })];
        open();
        const note = within(rowOf('old')).getByText(/Read-only/);
        expect(note.textContent?.trim()).toBe('Read-only');
    });
});
