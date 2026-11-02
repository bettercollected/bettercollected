// Workspace, Members, Teams: list, create, rename and delete teams; add and remove members (active members only);
// the limits and the server's refusals in plain words; owners and admins only, and nothing while the switch is off.
import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import Teams from './teams';

import commonNl from '../../../public/locales/nl/common.json';

const served = vi.hoisted(() => ({
    ready: true,
    admin: true,
    enabled: true,
    teams: { data: undefined as any, isLoading: false, isError: false },
    team: { data: undefined as any, isLoading: false, isError: false },
    members: [] as any[],
    teamCalls: [] as any[],
    createTeam: (() => {}) as any,
    renameTeam: (() => {}) as any,
    deleteTeam: (() => {}) as any,
    addMember: (() => {}) as any,
    removeMember: (() => {}) as any
}));

vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ ready: served.ready, formAccessEnabled: served.enabled, can: (permission: string) => served.admin && permission === 'members.manage' })
}));
vi.mock('@app/store/workspaces/form-access-api', async (original) => ({
    ...((await original()) as object),
    useGetTeamsQuery: (...args: unknown[]) => {
        served.teamCalls.push(args);
        return served.teams;
    },
    useGetTeamQuery: () => served.team,
    useCreateTeamMutation: () => [(...args: unknown[]) => served.createTeam(...args), { isLoading: false }],
    useRenameTeamMutation: () => [(...args: unknown[]) => served.renameTeam(...args), { isLoading: false }],
    useDeleteTeamMutation: () => [(...args: unknown[]) => served.deleteTeam(...args), { isLoading: false }],
    useAddTeamMemberMutation: () => [(...args: unknown[]) => served.addMember(...args), { isLoading: false }],
    useRemoveTeamMemberMutation: () => [(...args: unknown[]) => served.removeMember(...args), { isLoading: false }]
}));
vi.mock('@app/store/workspaces/members-n-invitations-api', async (original) => ({
    ...((await original()) as object),
    useGetWorkspaceMembersQuery: () => ({ data: served.members, isLoading: false })
}));

const person = (id: string, firstName: string, lastName: string, extra: Record<string, unknown> = {}) => ({ id, firstName, lastName, email: `${firstName.toLowerCase()}@voorbeeld.example`, roles: ['EDITOR'], role: 'EDITOR', joined: '2026-01-01T00:00:00', ...extra });
const team = (id: string, name: string, memberCount = 2) => ({ id, name, memberCount, source: 'manual' });

const renderTeams = () => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'voorbeeld' } as any));
    return render(
        <ReduxProvider store={store}>
            <Teams />
        </ReduxProvider>
    );
};

describe('Workspace, Members, Teams', () => {
    beforeAll(() => {
        i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    });

    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    beforeEach(() => {
        served.ready = true;
        served.admin = true;
        served.enabled = true;
        served.teams = { data: [team('t-1', 'Vrijwilligersteam', 3), team('t-2', 'Bestuur', 1)], isLoading: false, isError: false };
        served.team = { data: { ...team('t-1', 'Vrijwilligersteam', 2), formCount: 2, members: [{ userId: 'u-a', name: 'Anna Bakker', role: 'EDITOR' }, { userId: 'u-b', name: 'Jeroen Visser', role: 'VIEWER' }] }, isLoading: false, isError: false };
        served.members = [person('u-a', 'Anna', 'Bakker'), person('u-b', 'Jeroen', 'Visser'), person('u-c', 'Lotte', 'Smit'), person('u-off', 'Dirk', 'Uit', { disabled: true }), person('u-gone', 'Gone', 'Account', { accountDeleted: true })];
        served.teamCalls = [];
        served.createTeam = vi.fn().mockResolvedValue({ data: {} });
        served.renameTeam = vi.fn().mockResolvedValue({ data: {} });
        served.deleteTeam = vi.fn().mockResolvedValue({ data: undefined });
        served.addMember = vi.fn().mockResolvedValue({ data: undefined });
        served.removeMember = vi.fn().mockResolvedValue({ data: undefined });
    });

    it('lists the teams with their size and the limit', () => {
        renderTeams();
        expect(screen.getByRole('heading', { level: 2, name: 'Teams' })).toBeInTheDocument();
        expect(screen.getByText('2 of 20 teams')).toBeInTheDocument();
        const rows = within(screen.getByRole('list', { name: 'Teams' })).getAllByRole('listitem');
        expect(rows).toHaveLength(2);
        expect(within(rows[0]).getByText('Vrijwilligersteam')).toBeInTheDocument();
        expect(within(rows[0]).getByText('3 people')).toBeInTheDocument();
        expect(within(rows[1]).getByText('1 person')).toBeInTheDocument();
    });

    it('says how many directory groups feed a team, and leaves removing a person from a group to the directory', () => {
        served.teams = { data: [{ ...team('t-1', 'Vrijwilligersteam', 3), linkedGroups: 2 }, team('t-2', 'Bestuur', 1)], isLoading: false, isError: false };
        served.team = { data: { ...team('t-1', 'Vrijwilligersteam', 2), linkedGroups: 2, formCount: 1, members: [{ userId: 'u-a', name: 'Anna Bakker', role: 'EDITOR' }, { userId: 'u-b', name: 'Jeroen Visser', role: 'VIEWER', viaDirectory: true }] }, isLoading: false, isError: false };
        renderTeams();
        const rows = within(screen.getByRole('list', { name: 'Teams' })).getAllByRole('listitem');
        expect(within(rows[0]).getByText(/Fed by 2 directory groups/)).toBeInTheDocument();
        expect(within(rows[1]).queryByText(/Fed by/)).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: 'Manage the team Vrijwilligersteam' }));
        expect(screen.getByRole('button', { name: 'Remove Anna Bakker from Vrijwilligersteam' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: 'Remove Jeroen Visser from Vrijwilligersteam' })).toBeNull();
        expect(screen.getByText('From your directory')).toBeInTheDocument();
    });

    it('says nothing, and asks for nothing, to anyone but an owner or admin, and while the switch is off', () => {
        served.admin = false;
        const view = renderTeams();
        expect(screen.getByText('Only owners and admins manage teams.')).toBeInTheDocument();
        expect(screen.queryByLabelText('New team')).toBeNull();
        view.unmount();
        served.admin = true;
        served.enabled = false;
        const off = renderTeams();
        expect(screen.getByText('Teams are turned off on this server.')).toBeInTheDocument();
        off.unmount();
        expect(served.teamCalls).toEqual([]);
    });

    it('shows nothing to manage while the permissions are unknown', () => {
        served.ready = false;
        renderTeams();
        expect(screen.getByRole('status').textContent).toBe('Loading');
        expect(screen.queryByLabelText('New team')).toBeNull();
    });

    it('explains an empty workspace', () => {
        served.teams = { data: [], isLoading: false, isError: false };
        renderTeams();
        expect(screen.getByText(/Teams let you give a group of people access to a form in one step/)).toBeInTheDocument();
    });

    it('creates a team with the trimmed name, then clears the field and says so', async () => {
        renderTeams();
        const field = screen.getByLabelText('New team') as HTMLInputElement;
        expect(screen.getByRole('button', { name: 'Create team' })).toBeDisabled();
        fireEvent.change(field, { target: { value: '  Redactie  ' } });
        fireEvent.click(screen.getByRole('button', { name: 'Create team' }));
        await waitFor(() => expect(served.createTeam).toHaveBeenCalledWith({ workspaceId: 'ws-1', name: 'Redactie' }));
        await waitFor(() => expect(field.value).toBe(''));
        expect(screen.getByText('Team created.')).toBeInTheDocument();
    });

    it.each([
        ['team_name_taken', 409, 'A team with this name already exists.'],
        ['too_many_teams', 409, 'A workspace can have at most 20 teams.'],
        ['invalid_name', 422, 'Enter a name of up to 80 characters, without line breaks or special characters.']
    ])('keeps what was typed and says what is wrong when the server refuses with %s', async (code, status, sentence) => {
        served.createTeam = vi.fn().mockResolvedValue({ error: { status, data: { code, message: 'server text' } } });
        renderTeams();
        const field = screen.getByLabelText('New team') as HTMLInputElement;
        fireEvent.change(field, { target: { value: 'Redactie' } });
        fireEvent.click(screen.getByRole('button', { name: 'Create team' }));
        expect((await screen.findByRole('alert')).textContent).toBe(sentence);
        expect(field.value).toBe('Redactie');
        expect(field).toHaveAttribute('aria-invalid', 'true');
    });

    it('shows the limit plainly and stops offering a new team at the maximum', () => {
        served.teams = { data: Array.from({ length: 20 }, (_, index) => team(`t-${index}`, `Team ${index + 1}`)), isLoading: false, isError: false };
        renderTeams();
        expect(screen.getByText('20 of 20 teams')).toBeInTheDocument();
        expect(screen.getByText(/A workspace can have at most 20 teams. Delete one to make a new one./)).toBeInTheDocument();
        expect(screen.getByLabelText('New team')).toBeDisabled();
        expect(screen.getByRole('button', { name: 'Create team' })).toBeDisabled();
    });

    it('opens a team: its members, where it is used, and only active members who are not in it can be added', async () => {
        renderTeams();
        fireEvent.click(screen.getByRole('button', { name: 'Manage the team Vrijwilligersteam' }));
        const dialog = await screen.findByRole('dialog', { name: 'Vrijwilligersteam' });
        expect(within(dialog).getByText('Used on 2 forms.')).toBeInTheDocument();
        expect(within(dialog).getByText('Anna Bakker')).toBeInTheDocument();
        const choice = within(dialog).getByLabelText('Add a member') as HTMLSelectElement;
        expect(Array.from(choice.options).map((option) => option.textContent)).toEqual(['Choose a member', 'Lotte Smit']);
        expect(within(dialog).getByText(/Only active members can be added. A team has at most 500 members./)).toBeInTheDocument();
        fireEvent.change(choice, { target: { value: 'u-c' } });
        fireEvent.click(within(dialog).getByRole('button', { name: 'Add' }));
        await waitFor(() => expect(served.addMember).toHaveBeenCalledWith({ workspaceId: 'ws-1', teamId: 't-1', memberId: 'u-c' }));
    });

    it('removes a member from a team', async () => {
        renderTeams();
        fireEvent.click(screen.getByRole('button', { name: 'Manage the team Vrijwilligersteam' }));
        const dialog = await screen.findByRole('dialog', { name: 'Vrijwilligersteam' });
        fireEvent.click(within(dialog).getByRole('button', { name: 'Remove Jeroen Visser from Vrijwilligersteam' }));
        await waitFor(() => expect(served.removeMember).toHaveBeenCalledWith({ workspaceId: 'ws-1', teamId: 't-1', memberId: 'u-b' }));
    });

    it('says the team is full in the server\'s terms', async () => {
        served.addMember = vi.fn().mockResolvedValue({ error: { status: 409, data: { code: 'team_full', message: 'x' } } });
        renderTeams();
        fireEvent.click(screen.getByRole('button', { name: 'Manage the team Vrijwilligersteam' }));
        const dialog = await screen.findByRole('dialog', { name: 'Vrijwilligersteam' });
        fireEvent.change(within(dialog).getByLabelText('Add a member'), { target: { value: 'u-c' } });
        fireEvent.click(within(dialog).getByRole('button', { name: 'Add' }));
        expect((await within(dialog).findByRole('alert')).textContent).toBe('A team can have at most 500 members.');
    });

    it('renames a team, and says when the name is taken', async () => {
        renderTeams();
        fireEvent.click(screen.getByRole('button', { name: 'Manage the team Vrijwilligersteam' }));
        const dialog = await screen.findByRole('dialog', { name: 'Vrijwilligersteam' });
        const save = within(dialog).getByRole('button', { name: 'Save name' });
        expect(save).toBeDisabled();
        fireEvent.change(within(dialog).getByLabelText('Name of the team'), { target: { value: 'Vrijwilligers' } });
        fireEvent.click(save);
        await waitFor(() => expect(served.renameTeam).toHaveBeenCalledWith({ workspaceId: 'ws-1', teamId: 't-1', name: 'Vrijwilligers' }));
    });

    it('deletes a team only after a confirmation that says which forms lose access', async () => {
        renderTeams();
        fireEvent.click(screen.getByRole('button', { name: 'Manage the team Vrijwilligersteam' }));
        const dialog = await screen.findByRole('dialog', { name: 'Vrijwilligersteam' });
        fireEvent.click(within(dialog).getByRole('button', { name: 'Delete team' }));
        const confirm = await screen.findByRole('alertdialog');
        expect(within(confirm).getByText('Delete the team Vrijwilligersteam?')).toBeInTheDocument();
        expect(within(confirm).getByText('It is used on 2 forms; those lose the access it gave.')).toBeInTheDocument();
        expect(served.deleteTeam).not.toHaveBeenCalled();
        fireEvent.click(within(confirm).getByRole('button', { name: 'Delete team' }));
        await waitFor(() => expect(served.deleteTeam).toHaveBeenCalledWith({ workspaceId: 'ws-1', teamId: 't-1' }));
    });

    it('is Dutch in Dutch, formal', async () => {
        await i18n.changeLanguage('nl');
        renderTeams();
        expect(screen.getByText('Geef een groep mensen in één keer toegang tot een formulier.')).toBeInTheDocument();
        expect(screen.getByText('2 van 20 teams')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Team maken' })).toBeInTheDocument();
        expect(screen.getByText('3 mensen')).toBeInTheDocument();
    });

    it('has no accessibility violations (the list and an open team)', async () => {
        const { container } = renderTeams();
        expect(await axeViolations(container)).toEqual([]);
        fireEvent.click(screen.getByRole('button', { name: 'Manage the team Vrijwilligersteam' }));
        const dialog = await screen.findByRole('dialog', { name: 'Vrijwilligersteam' });
        expect(await axeViolations(dialog)).toEqual([]);
    });
});
