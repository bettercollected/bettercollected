// Workspace, Members, Teams: linked directory groups. Only the owner sees and changes them; nothing is asked of the
// directory by anyone without security.manage; a group is linked to one team, or to none.
import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { axeViolations } from '@app/test/axe';

import commonNl from '../../../public/locales/nl/common.json';
import TeamDirectoryGroups from './team-directory-groups';

const served = vi.hoisted(() => ({
    security: true,
    overview: { data: undefined as any },
    scimCalls: [] as any[],
    link: (() => {}) as any,
    unlink: (() => {}) as any
}));

vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => served.security && permission === 'security.manage' })
}));
vi.mock('@app/store/workspaces/api', async (original) => ({
    ...((await original()) as object),
    useGetWorkspaceScimQuery: (...args: unknown[]) => {
        served.scimCalls.push(args);
        return served.overview;
    }
}));
vi.mock('@app/store/workspaces/form-access-api', async (original) => ({
    ...((await original()) as object),
    useSetScimGroupTeamMutation: () => [(...args: unknown[]) => served.link(...args), { isLoading: false }],
    useClearScimGroupTeamMutation: () => [(...args: unknown[]) => served.unlink(...args), { isLoading: false }]
}));

const teams = [
    { id: 't-1', name: 'Vrijwilligersteam', memberCount: 3 },
    { id: 't-2', name: 'Bestuur', memberCount: 1 }
];
const overview = (extra: Record<string, unknown> = {}) => ({
    available: true,
    directory: { id: 'd-1' },
    canManage: true,
    groups: [
        { id: 'g-1', name: 'Vrijwilligers', members: 4, teamId: 't-1' },
        { id: 'g-2', name: 'Bestuursleden', members: 2, teamId: null },
        { id: 'g-3', name: 'Oud', members: 1, teamId: 't-gone' }
    ],
    ...extra
});

const renderGroups = () =>
    render(
        <ReduxProvider store={store}>
            <TeamDirectoryGroups workspaceId="ws-1" teams={teams} />
        </ReduxProvider>
    );

describe('Workspace, Members, Teams: linked directory groups', () => {
    beforeAll(() => {
        i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    });

    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    beforeEach(() => {
        served.security = true;
        served.overview = { data: overview() };
        served.scimCalls = [];
        served.link = vi.fn().mockResolvedValue({ data: {} });
        served.unlink = vi.fn().mockResolvedValue({ data: {} });
    });

    it('lists the directory groups with the team each feeds, and says the people are read from the directory', () => {
        renderGroups();
        expect(screen.getByRole('heading', { level: 2, name: 'Linked directory groups' })).toBeInTheDocument();
        expect(screen.getByText(/leave the team at once/)).toBeInTheDocument();
        const rows = within(screen.getByRole('list', { name: 'Linked directory groups' })).getAllByRole('listitem');
        expect(rows).toHaveLength(3);
        expect((screen.getByLabelText('Team for the group Vrijwilligers') as HTMLSelectElement).value).toBe('t-1');
        expect((screen.getByLabelText('Team for the group Bestuursleden') as HTMLSelectElement).value).toBe('');
        // a link to a team that is gone shows as not linked
        expect((screen.getByLabelText('Team for the group Oud') as HTMLSelectElement).value).toBe('');
        expect(within(rows[0]).getByText('4 people')).toBeInTheDocument();
    });

    it('links a group to a team, and unlinks it by choosing none', async () => {
        renderGroups();
        fireEvent.change(screen.getByLabelText('Team for the group Bestuursleden'), { target: { value: 't-2' } });
        await waitFor(() => expect(served.link).toHaveBeenCalledWith({ workspaceId: 'ws-1', groupId: 'g-2', teamId: 't-2' }));
        expect(await screen.findByText('Link updated.')).toBeInTheDocument();

        fireEvent.change(screen.getByLabelText('Team for the group Vrijwilligers'), { target: { value: '' } });
        await waitFor(() => expect(served.unlink).toHaveBeenCalledWith({ workspaceId: 'ws-1', groupId: 'g-1' }));
    });

    it("shows the server's words when a change is refused", async () => {
        served.link = vi.fn().mockResolvedValue({ error: { status: 422, data: { code: 'form_access_off' } } });
        renderGroups();
        fireEvent.change(screen.getByLabelText('Team for the group Bestuursleden'), { target: { value: 't-2' } });
        expect(await screen.findByRole('alert')).toBeInTheDocument();
        expect(screen.queryByText('Link updated.')).toBeNull();
    });

    it('is not shown to an admin (the owner changes it), without a directory, or while the directory is unavailable', () => {
        for (const extra of [{ canManage: false }, { directory: null }, { available: false }]) {
            served.overview = { data: overview(extra) };
            const view = renderGroups();
            expect(screen.queryByText('Linked directory groups')).toBeNull();
            view.unmount();
        }
        served.overview = { data: undefined };
        const loading = renderGroups();
        expect(screen.queryByText('Linked directory groups')).toBeNull();
        loading.unmount();
    });

    it('asks nothing of the directory for someone without security.manage', () => {
        served.security = false;
        renderGroups();
        expect(served.scimCalls).toHaveLength(1);
        expect(served.scimCalls[0][1]).toEqual({ skip: true });
    });

    it('explains an empty directory', () => {
        served.overview = { data: overview({ groups: [] }) };
        renderGroups();
        expect(screen.getByText('Your directory has no groups yet.')).toBeInTheDocument();
    });

    it('speaks Dutch', async () => {
        await i18n.changeLanguage('nl');
        renderGroups();
        expect(screen.getByRole('heading', { level: 2, name: 'Gekoppelde directorygroepen' })).toBeInTheDocument();
        expect(screen.getByLabelText('Team voor de groep Vrijwilligers')).toBeInTheDocument();
    });

    it('has no accessibility violations', async () => {
        const { container } = renderGroups();
        expect(await axeViolations(container)).toEqual([]);
    });
});
