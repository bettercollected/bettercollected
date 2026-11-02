// Settings, Access: "Who on your team can open this form". The mode, the list of grants and the add form, the
// server's refusals as sentences, read-only for whoever may not manage the circle, and nothing at all (no request)
// while the server has form-level access off.
import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import { axeViolations } from '@app/test/axe';

import FormAccessCard from './form-access-card';

import commonNl from '../../../../public/locales/nl/common.json';

const EDITOR = ['form.read', 'form.edit', 'form.share', 'form.delete', 'response.read', 'response.annotate', 'response.export', 'response.delete', 'response.edit', 'analytics.read'];

const served = vi.hoisted(() => ({
    enabled: true,
    admin: true,
    access: { data: undefined as any, isLoading: false, isError: false, refetch: () => {} },
    queries: [] as Array<{ args: unknown; options: any }>,
    memberCalls: [] as any[],
    teamCalls: [] as any[],
    members: [] as any[],
    teams: [] as any[],
    candidateCalls: [] as any[],
    candidates: { data: undefined as any, isError: false },
    impactCalls: [] as any[],
    impact: { data: undefined as any, isError: false },
    setMode: (() => {}) as any,
    putGrant: (() => {}) as any,
    deleteGrant: (() => {}) as any
}));

vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ formAccessEnabled: served.enabled, can: (permission: string) => served.admin && permission === 'members.manage', ready: true })
}));
vi.mock('@app/store/workspaces/form-access-api', async (original) => ({
    ...((await original()) as object),
    useGetFormAccessQuery: (args: unknown, options: any) => {
        served.queries.push({ args, options });
        return served.access;
    },
    useGetTeamsQuery: (_workspaceId: string, options: any) => {
        served.teamCalls.push(options);
        return { data: options?.skip ? undefined : served.teams };
    },
    useGetFormAccessCandidatesQuery: (args: unknown, options: any) => {
        served.candidateCalls.push({ args, options });
        return options?.skip ? { data: undefined, isError: false } : served.candidates;
    },
    useGetFormAccessImpactQuery: (args: unknown, options: any) => {
        served.impactCalls.push({ args, options });
        return served.impact;
    },
    useSetFormAccessModeMutation: () => [(...args: unknown[]) => served.setMode(...args), { isLoading: false }],
    usePutFormGrantMutation: () => [(...args: unknown[]) => served.putGrant(...args), { isLoading: false }],
    useDeleteFormGrantMutation: () => [(...args: unknown[]) => served.deleteGrant(...args), { isLoading: false }]
}));
vi.mock('@app/store/workspaces/members-n-invitations-api', async (original) => ({
    ...((await original()) as object),
    useGetWorkspaceMembersQuery: (_args: unknown, options: any) => {
        served.memberCalls.push(options);
        return { data: options?.skip ? undefined : served.members };
    }
}));

const person = (id: string, firstName: string, lastName: string, extra: Record<string, unknown> = {}) => ({ id, firstName, lastName, email: `${firstName.toLowerCase()}@voorbeeld.example`, roles: ['EDITOR'], role: 'EDITOR', joined: '2026-01-01T00:00:00', ...extra });

const grant = (id: string, extra: Record<string, unknown> = {}) => ({ id, subjectType: 'user', subjectId: `u-${id}`, role: 'REVIEWER', export: false, name: 'Sanne de Vries', disabled: false, createdAt: '2026-11-01T09:00:00', ...extra });

const access = (extra: Record<string, unknown> = {}) => ({
    enabled: true,
    accessMode: 'restricted',
    restricted: true,
    myPermissions: EDITOR,
    source: 'role',
    canManage: true,
    grants: [grant('g1'), grant('g2', { subjectType: 'group', subjectId: 't-1', name: 'Vrijwilligersteam', role: 'VIEWER', export: true })],
    ...extra
});

const renderCard = (hidden = false) => {
    store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'voorbeeld' } as any));
    store.dispatch(setForm({ formId: 'f1', title: 'Survey', fields: [], settings: { provider: 'self', hidden } } as any));
    return render(
        <ReduxProvider store={store}>
            <FormAccessCard />
        </ReduxProvider>
    );
};

describe('Settings, Access: who on your team can open this form', () => {
    beforeAll(() => {
        i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    });

    afterEach(async () => {
        await i18n.changeLanguage('en');
    });

    beforeEach(() => {
        served.enabled = true;
        served.admin = true;
        served.access = { data: access(), isLoading: false, isError: false, refetch: () => {} };
        served.queries = [];
        served.memberCalls = [];
        served.teamCalls = [];
        served.candidateCalls = [];
        served.candidates = { data: { members: [{ id: 'u-c', name: 'Cor Jansen' }], teams: [{ id: 't-9', name: 'Redactie', memberCount: 1 }] }, isError: false };
        served.impactCalls = [];
        served.impact = { data: { mode: 'restricted', membersLosingAccess: 3 }, isError: false };
        served.members = [person('u-a', 'Anna', 'Bakker'), person('u-b', 'Jeroen', 'Visser')];
        served.teams = [{ id: 't-2', name: 'Bestuur', memberCount: 3 }];
        served.setMode = vi.fn().mockResolvedValue({ data: {} });
        served.putGrant = vi.fn().mockResolvedValue({ data: {} });
        served.deleteGrant = vi.fn().mockResolvedValue({ data: {} });
    });

    it('renders nothing and asks for nothing while the server has form-level access off', () => {
        served.enabled = false;
        const { container } = renderCard();
        expect(container).toBeEmptyDOMElement();
        expect(served.queries).toEqual([]);
        expect(served.memberCalls).toEqual([]);
        expect(served.teamCalls).toEqual([]);
        expect(served.candidateCalls).toEqual([]);
        expect(served.impactCalls).toEqual([]);
    });

    it('renders nothing when the server answers that it is off', () => {
        served.access = { ...served.access, data: { enabled: false } };
        const { container } = renderCard();
        expect(container).toBeEmptyDOMElement();
    });

    it('is its own group with a clear heading: the team, not the respondents', () => {
        renderCard();
        const card = screen.getByTestId('form-access-card');
        expect(within(card).getByRole('heading', { level: 3, name: 'Who on your team can open this form' })).toBeInTheDocument();
        expect(within(card).getByText(/does not change who can fill the form in/)).toBeInTheDocument();
        expect(within(card).getByText('Owners, admins and the creator always have access.')).toBeInTheDocument();
    });

    it('shows the mode the server reports, with Restricted checked for a restricted form', () => {
        renderCard();
        expect(screen.getByRole('radio', { name: 'Only selected people and teams' })).toBeChecked();
        expect(screen.getByRole('radio', { name: 'Everyone in the workspace, by their role' })).not.toBeChecked();
    });

    it('lists each grant with its role, export and a Team label for a team', () => {
        renderCard();
        const list = screen.getByRole('list', { name: /People and teams with access/ });
        const rows = within(list).getAllByRole('listitem');
        expect(rows).toHaveLength(2);
        expect(within(rows[0]).getByLabelText('Role of Sanne de Vries on this form')).toHaveValue('REVIEWER');
        expect(within(rows[1]).getByText('Team')).toBeInTheDocument();
        expect(within(rows[1]).getByLabelText('Vrijwilligersteam may export responses')).toBeChecked();
    });

    it('asks before restricting, says respondents are not affected, and sends the mode only after the confirmation', async () => {
        served.access = { ...served.access, data: access({ accessMode: 'workspace', restricted: false }) };
        renderCard();
        fireEvent.click(screen.getByRole('radio', { name: 'Only selected people and teams' }));
        const dialog = await screen.findByRole('alertdialog');
        expect(within(dialog).getByText('Restrict access to this form?')).toBeInTheDocument();
        expect(within(dialog).getByText(/Respondents are not affected/)).toBeInTheDocument();
        expect(served.setMode).not.toHaveBeenCalled();
        fireEvent.click(within(dialog).getByRole('button', { name: 'Restrict' }));
        await waitFor(() => expect(served.setMode).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'f1', mode: 'restricted' }));
    });

    it('asks before opening a restricted form to the workspace, and Cancel changes nothing', async () => {
        renderCard();
        fireEvent.click(screen.getByRole('radio', { name: 'Everyone in the workspace, by their role' }));
        const dialog = await screen.findByRole('alertdialog');
        expect(within(dialog).getByText('Open this form to the workspace?')).toBeInTheDocument();
        fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
        await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull());
        expect(served.setMode).not.toHaveBeenCalled();
    });

    it('shows the server\'s refusal of a mode change as a sentence', async () => {
        served.access = { ...served.access, data: access({ accessMode: 'workspace', restricted: false }) };
        served.setMode = vi.fn().mockResolvedValue({ error: { status: 403, data: { code: 'access_manage_forbidden', message: 'x' } } });
        renderCard();
        fireEvent.click(screen.getByRole('radio', { name: 'Only selected people and teams' }));
        fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Restrict' }));
        expect((await screen.findByRole('alert')).textContent).toBe('Only an owner, an admin or the person who created the form can change who may open it.');
    });

    it('adds a person: the choice offers only people who can be given access, and sends the id, role and no export unasked', async () => {
        served.members = [
            person('u-a', 'Anna', 'Bakker'),
            person('u-owner', 'Olaf', 'Eigenaar', { role: 'OWNER', roles: ['OWNER'] }),
            person('u-admin', 'Ada', 'Beheer', { role: 'ADMIN', roles: ['ADMIN'] }),
            person('u-po', 'Pia', 'Privacy', { role: 'PRIVACY_OFFICER', roles: ['PRIVACY_OFFICER'] }),
            person('u-off', 'Dirk', 'Uit', { disabled: true }),
            person('u-gone', 'Gone', 'Account', { accountDeleted: true }),
            // already has a grant
            person('u-g1', 'Sanne', 'de Vries')
        ];
        renderCard();
        const choice = screen.getByLabelText('Person or team') as HTMLSelectElement;
        const labels = Array.from(choice.options).map((option) => option.textContent);
        expect(labels).toEqual(['Choose a person or a team', 'Anna Bakker', 'Bestuur (3 people)']);
        fireEvent.change(choice, { target: { value: 'user:u-a' } });
        fireEvent.change(screen.getByLabelText('Role on this form'), { target: { value: 'VIEWER' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add' }));
        await waitFor(() => expect(served.putGrant).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'f1', grant: { subjectType: 'user', subjectId: 'u-a', role: 'VIEWER', export: false } }));
        await waitFor(() => expect(screen.getByRole('status').textContent).toBe('Access updated.'));
    });

    it('adds a team with the export flag only because an owner or admin ticked it', async () => {
        renderCard();
        fireEvent.change(screen.getByLabelText('Person or team'), { target: { value: 'group:t-2' } });
        fireEvent.change(screen.getByLabelText('Role on this form'), { target: { value: 'REVIEWER' } });
        fireEvent.click(screen.getAllByLabelText('May export responses').at(-1) as HTMLElement);
        fireEvent.click(screen.getByRole('button', { name: 'Add' }));
        await waitFor(() => expect(served.putGrant).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'f1', grant: { subjectType: 'group', subjectId: 't-2', role: 'REVIEWER', export: true } }));
    });

    it('says who may allow export only for the roles it applies to: an Editor grant exports on its own', () => {
        served.access = { ...served.access, data: access({ grants: [grant('g1', { role: 'EDITOR' }), grant('g2', { name: 'Lotte Smit', subjectId: 'u-g2', role: 'REVIEWER', export: true })] }) };
        renderCard();
        const note = /Only owners and admins can allow a Reviewer or Viewer to export responses/;
        const form = within(screen.getByRole('form', { name: 'Add a person or a team' }));
        // Editor chosen in the add form: no tick-box and no note
        fireEvent.change(screen.getByLabelText('Role on this form'), { target: { value: 'EDITOR' } });
        expect(form.queryByRole('checkbox')).toBeNull();
        expect(screen.queryByText(note)).toBeNull();
        // Reviewer or Viewer chosen: the tick-box and the note
        fireEvent.change(screen.getByLabelText('Role on this form'), { target: { value: 'VIEWER' } });
        expect(form.getByRole('checkbox', { name: 'May export responses' })).toBeInTheDocument();
        expect(screen.getByText(note)).toBeInTheDocument();
        // the list: an Editor row says it exports by its role, with no tick-box; a Reviewer row has the tick-box
        const rows = within(screen.getByRole('list', { name: /People and teams with access/ })).getAllByRole('listitem');
        expect(within(rows[0]).queryByRole('checkbox')).toBeNull();
        expect(within(rows[0]).getByText('Can export responses')).toBeInTheDocument();
        expect(within(rows[1]).getByRole('checkbox')).toBeChecked();
    });

    it('offers only the roles the giver holds on the form (a hint: the server decides)', () => {
        served.access = { ...served.access, data: access({ myPermissions: EDITOR.filter((permission) => permission !== 'response.export') }) };
        renderCard();
        const roles = Array.from((screen.getByLabelText('Role on this form') as HTMLSelectElement).options).map((option) => option.value);
        expect(roles).toEqual(['REVIEWER', 'VIEWER']);
    });

    it.each([
        ['grant_above_own_role', "You can't give a role with more access than your own on this form."],
        ['export_grant_reserved', 'Only an owner or an admin can allow or change exporting of responses.'],
        ['cannot_grant_self', "You can't change your own access to a form."],
        ['privacy_officer_cannot_be_granted', 'A privacy officer never reads answers, so access given to one would do nothing.'],
        ['audit_unavailable', 'The change could not be recorded, so it was not made. Try again in a moment.']
    ])('says what the server meant when it refuses a grant with %s', async (code, sentence) => {
        served.putGrant = vi.fn().mockResolvedValue({ error: { status: code === 'audit_unavailable' ? 503 : 403, data: { code, message: 'server text' } } });
        renderCard();
        fireEvent.change(screen.getByLabelText('Person or team'), { target: { value: 'user:u-a' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add' }));
        expect((await screen.findByRole('alert')).textContent).toBe(sentence);
        // nothing was added to the list by the refusal
        expect(within(screen.getByRole('list', { name: /People and teams with access/ })).getAllByRole('listitem')).toHaveLength(2);
    });

    it('changes a role in place, keeping the export flag only where it means something', async () => {
        renderCard();
        const row = within(screen.getAllByRole('listitem')[1]);
        fireEvent.change(row.getByLabelText('Role of Vrijwilligersteam on this form'), { target: { value: 'EDITOR' } });
        await waitFor(() => expect(served.putGrant).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'f1', grant: { subjectType: 'group', subjectId: 't-1', role: 'EDITOR', export: false } }));
    });

    it('removes a grant only after a confirmation', async () => {
        renderCard();
        fireEvent.click(screen.getByRole('button', { name: 'Remove the access of Sanne de Vries' }));
        const dialog = await screen.findByRole('alertdialog');
        expect(within(dialog).getByText('Remove the access of Sanne de Vries?')).toBeInTheDocument();
        expect(served.deleteGrant).not.toHaveBeenCalled();
        fireEvent.click(within(dialog).getByRole('button', { name: 'Remove' }));
        await waitFor(() => expect(served.deleteGrant).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'f1', grantId: 'g1' }));
    });

    it('marks a deactivated person with words, not colour alone', () => {
        served.access = { ...served.access, data: access({ grants: [grant('g1', { disabled: true })] }) };
        renderCard();
        expect(screen.getByText('This person is deactivated.')).toBeInTheDocument();
    });

    it('is read-only for someone who may not manage the circle: no radios to change, no remove, no add form, and it says why', () => {
        served.access = { ...served.access, data: access({ canManage: false }) };
        renderCard();
        expect(screen.getByRole('radio', { name: 'Only selected people and teams' })).toBeDisabled();
        expect(screen.getByText('Only owners, admins and the creator manage access.')).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Remove the access/ })).toBeNull();
        expect(screen.queryByLabelText('Person or team')).toBeNull();
        expect(screen.getByLabelText('Role of Sanne de Vries on this form')).toBeDisabled();
    });

    it('shows no list to someone the server gives none (no grants in the answer)', () => {
        served.access = { ...served.access, data: access({ grants: null, canManage: false }) };
        renderCard();
        expect(screen.queryByRole('list', { name: /People and teams with access/ })).toBeNull();
    });

    it("someone who may share the form but not list members picks from the server's candidates, and asks for no member or team list", async () => {
        served.admin = false;
        renderCard();
        expect(served.memberCalls.every((options) => options?.skip === true)).toBe(true);
        expect(served.teamCalls.every((options) => options?.skip === true)).toBe(true);
        expect(served.candidateCalls.at(-1)).toEqual({ args: { workspaceId: 'ws-1', formId: 'f1' }, options: { skip: false } });
        const choice = screen.getByLabelText('Person or team') as HTMLSelectElement;
        expect(Array.from(choice.options).map((option) => option.textContent)).toEqual(['Choose a person or a team', 'Cor Jansen', 'Redactie (1 person)']);
        fireEvent.change(choice, { target: { value: 'group:t-9' } });
        fireEvent.change(screen.getByLabelText('Role on this form'), { target: { value: 'VIEWER' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add' }));
        await waitFor(() => expect(served.putGrant).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'f1', grant: { subjectType: 'group', subjectId: 't-9', role: 'VIEWER', export: false } }));
    });

    it('the candidates leave out whoever already has a grant, and a person is added by id', async () => {
        served.admin = false;
        served.candidates = { data: { members: [{ id: 'u-g1', name: 'Sanne de Vries' }, { id: 'u-c', name: 'Cor Jansen' }], teams: [{ id: 't-1', name: 'Vrijwilligersteam', memberCount: 4 }] }, isError: false };
        renderCard();
        const choice = screen.getByLabelText('Person or team') as HTMLSelectElement;
        expect(Array.from(choice.options).map((option) => option.textContent)).toEqual(['Choose a person or a team', 'Cor Jansen']);
        fireEvent.change(choice, { target: { value: 'user:u-c' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add' }));
        await waitFor(() => expect(served.putGrant).toHaveBeenCalledWith({ workspaceId: 'ws-1', formId: 'f1', grant: { subjectType: 'user', subjectId: 'u-c', role: 'REVIEWER', export: false } }));
    });

    it('says so when the candidates cannot be loaded, and can still remove access', () => {
        served.admin = false;
        served.candidates = { data: undefined, isError: true };
        renderCard();
        expect(screen.getByRole('alert').textContent).toMatch(/The people and teams you can add could not be loaded/);
        expect(screen.queryByLabelText('Person or team')).toBeNull();
        expect(screen.getByRole('button', { name: 'Remove the access of Sanne de Vries' })).toBeEnabled();
        // a grant that allows exporting is not theirs to change
        expect(screen.getByRole('button', { name: 'Remove the access of Vrijwilligersteam' })).toBeDisabled();
        expect(screen.getByLabelText('Vrijwilligersteam may export responses')).toBeDisabled();
    });

    it('an owner or admin keeps the member and team lists and never asks for the candidates', () => {
        renderCard();
        expect(served.candidateCalls.every((call) => call.options?.skip === true)).toBe(true);
        expect(served.memberCalls.some((options) => options?.skip === false)).toBe(true);
    });

    it('asks for no candidates when the reader may not manage the circle', () => {
        served.admin = false;
        served.access = { ...served.access, data: access({ canManage: false }) };
        renderCard();
        expect(served.candidateCalls.every((call) => call.options?.skip === true)).toBe(true);
        expect(screen.queryByLabelText('Person or team')).toBeNull();
    });

    it('shows the size of a team grant, and says in words when the team has no members', () => {
        served.access = {
            ...served.access,
            data: access({
                grants: [
                    grant('g1', { subjectType: 'group', subjectId: 't-1', name: 'Vrijwilligersteam', memberCount: 1 }),
                    grant('g2', { subjectType: 'group', subjectId: 't-2', name: 'Bestuur', memberCount: 0 }),
                    grant('g3', { subjectType: 'group', subjectId: 't-3', name: 'Redactie', memberCount: 12 }),
                    grant('g4', { memberCount: null })
                ]
            })
        };
        renderCard();
        const rows = within(screen.getByRole('list', { name: /People and teams with access/ })).getAllByRole('listitem');
        expect(within(rows[0]).getByText('1 person')).toBeInTheDocument();
        expect(within(rows[0]).queryByText('Team has no members')).toBeNull();
        expect(within(rows[1]).getByText('0 people')).toBeInTheDocument();
        expect(within(rows[1]).getByText('Team has no members')).toBeInTheDocument();
        expect(within(rows[2]).getByText('12 people')).toBeInTheDocument();
        // a person has no size
        expect(within(rows[3]).queryByText(/people|person$/)).toBeNull();
        expect(within(rows[3]).queryByText('Team has no members')).toBeNull();
    });

    it('shows nothing about a team size when the server sends no count', () => {
        renderCard();
        const rows = within(screen.getByRole('list', { name: /People and teams with access/ })).getAllByRole('listitem');
        expect(within(rows[1]).queryByText(/people|person$/)).toBeNull();
        expect(within(rows[1]).queryByText('Team has no members')).toBeNull();
    });

    it('says who added a grant and when, or only when if the name is not known', () => {
        served.access = {
            ...served.access,
            data: access({ grants: [grant('g1', { grantedBy: 'Joris Smit' }), grant('g2', { grantedBy: null }), grant('g3', { grantedBy: 'Joris Smit', createdAt: null }), grant('g4', { grantedBy: undefined, createdAt: null })] })
        };
        renderCard();
        const rows = within(screen.getByRole('list', { name: /People and teams with access/ })).getAllByRole('listitem');
        expect(within(rows[0]).getByText('Added by Joris Smit on Nov 1, 2026')).toBeInTheDocument();
        expect(within(rows[1]).getByText('Added Nov 1, 2026')).toBeInTheDocument();
        expect(within(rows[2]).getByText('Added by Joris Smit')).toBeInTheDocument();
        expect(within(rows[3]).queryByText(/Added/)).toBeNull();
    });

    it('asks the server how many people lose access when the restrict confirmation opens, and says the number in the dialog', async () => {
        served.access = { ...served.access, data: access({ accessMode: 'workspace', restricted: false }) };
        renderCard();
        expect(served.impactCalls).toEqual([]);
        fireEvent.click(screen.getByRole('radio', { name: 'Only selected people and teams' }));
        const dialog = await screen.findByRole('alertdialog');
        expect(served.impactCalls.at(-1)).toEqual({ args: { workspaceId: 'ws-1', formId: 'f1', mode: 'restricted' }, options: { refetchOnMountOrArgChange: true } });
        // a polite status region inside the dialog announces the count; the body text is unchanged
        const impact = within(dialog).getByTestId('restrict-impact');
        expect(impact).toHaveAttribute('role', 'status');
        expect(impact.textContent).toBe('3 people will lose access.');
        expect(within(dialog).getByText(/Respondents are not affected/)).toBeInTheDocument();
    });

    it.each([
        [0, 'No one will lose access.'],
        [1, '1 person will lose access.'],
        [7, '7 people will lose access.']
    ])('words the dry run count %s', async (count, sentence) => {
        served.access = { ...served.access, data: access({ accessMode: 'workspace', restricted: false }) };
        served.impact = { data: { mode: 'restricted', membersLosingAccess: count }, isError: false };
        renderCard();
        fireEvent.click(screen.getByRole('radio', { name: 'Only selected people and teams' }));
        expect((await screen.findByTestId('restrict-impact')).textContent).toBe(sentence);
    });

    it('says nothing, and still lets the change go ahead, when the dry run failed', async () => {
        served.access = { ...served.access, data: access({ accessMode: 'workspace', restricted: false }) };
        served.impact = { data: undefined, isError: true };
        renderCard();
        fireEvent.click(screen.getByRole('radio', { name: 'Only selected people and teams' }));
        const dialog = await screen.findByRole('alertdialog');
        expect(within(dialog).getByTestId('restrict-impact').textContent).toBe('');
        fireEvent.click(within(dialog).getByRole('button', { name: 'Restrict' }));
        await waitFor(() => expect(served.setMode).toHaveBeenCalled());
    });

    it('does not ask for the dry run when opening a form to the workspace', async () => {
        renderCard();
        fireEvent.click(screen.getByRole('radio', { name: 'Everyone in the workspace, by their role' }));
        const dialog = await screen.findByRole('alertdialog');
        expect(within(dialog).queryByTestId('restrict-impact')).toBeNull();
        expect(served.impactCalls).toEqual([]);
    });

    it('says what an empty list means for each mode', () => {
        served.access = { ...served.access, data: access({ grants: [] }) };
        const view = renderCard();
        expect(screen.getByText(/No one has been added yet. Only you, owners and admins can open this form./)).toBeInTheDocument();
        view.unmount();
        served.access = { ...served.access, data: access({ grants: [], restricted: false, accessMode: 'workspace' }) };
        renderCard();
        expect(screen.getByText(/Everyone in the workspace can open this form by their role/)).toBeInTheDocument();
    });

    it('says so when it cannot load, and while it loads', () => {
        served.access = { data: undefined, isLoading: true, isError: false, refetch: () => {} };
        const view = renderCard();
        expect(screen.getByRole('status').textContent).toBe('Loading who can open this form');
        view.unmount();
        served.access = { data: undefined, isLoading: false, isError: true, refetch: () => {} };
        renderCard();
        expect(screen.getByRole('alert').textContent).toMatch(/could not be loaded/);
    });

    it('asks again when the respondent visibility changes (a Private form counts as restricted until a mode is chosen)', () => {
        const refetch = vi.fn();
        served.access = { ...served.access, refetch };
        store.dispatch(setWorkspace({ id: 'ws-1', workspaceName: 'voorbeeld' } as any));
        store.dispatch(setForm({ formId: 'f1', title: 'Survey', fields: [], settings: { provider: 'self', hidden: false } } as any));
        render(
            <ReduxProvider store={store}>
                <FormAccessCard />
            </ReduxProvider>
        );
        expect(refetch).not.toHaveBeenCalled();
        act(() => {
            store.dispatch(setForm({ formId: 'f1', title: 'Survey', fields: [], settings: { provider: 'self', hidden: true } } as any));
        });
        expect(refetch).toHaveBeenCalled();
    });

    it('is Dutch in Dutch, formal', async () => {
        await i18n.changeLanguage('nl');
        served.access = { ...served.access, data: access({ grants: [grant('g1', { grantedBy: 'Joris Smit' }), grant('g2', { subjectType: 'group', subjectId: 't-1', name: 'Vrijwilligersteam', role: 'VIEWER', export: true, memberCount: 0 })] }) };
        renderCard();
        expect(screen.getByRole('heading', { level: 3, name: 'Wie in uw team dit formulier kan openen' })).toBeInTheDocument();
        expect(screen.getByRole('radio', { name: 'Alleen geselecteerde personen en teams' })).toBeChecked();
        expect(screen.getByText('Eigenaren, beheerders en de maker hebben altijd toegang.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Toegang van Sanne de Vries intrekken' })).toBeInTheDocument();
        expect(screen.getByText('Toegevoegd door Joris Smit op 1 nov 2026')).toBeInTheDocument();
        expect(screen.getByText('Team heeft geen leden')).toBeInTheDocument();
        expect(screen.getByText('0 mensen')).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText('Rol bij dit formulier'), { target: { value: 'VIEWER' } });
        expect(screen.getByText('Alleen eigenaren en beheerders kunnen een Beoordelaar of Kijker toestaan reacties te exporteren. Een Bewerker kan altijd exporteren.')).toBeInTheDocument();
    });

    it('says the dry run in Dutch, formal', async () => {
        await i18n.changeLanguage('nl');
        served.access = { ...served.access, data: access({ accessMode: 'workspace', restricted: false }) };
        renderCard();
        fireEvent.click(screen.getByRole('radio', { name: 'Alleen geselecteerde personen en teams' }));
        expect((await screen.findByTestId('restrict-impact')).textContent).toBe('3 mensen verliezen toegang.');
    });

    it('has no accessibility violations (list, add form, the picker for a non-manager, and the confirmation with its count)', async () => {
        served.access = { ...served.access, data: access({ grants: [grant('g1', { grantedBy: 'Joris Smit' }), grant('g2', { subjectType: 'group', subjectId: 't-1', name: 'Vrijwilligersteam', memberCount: 0 })] }) };
        const { container, unmount } = renderCard();
        expect(await axeViolations(container)).toEqual([]);
        fireEvent.click(screen.getByRole('radio', { name: 'Everyone in the workspace, by their role' }));
        const dialog = await screen.findByRole('alertdialog');
        expect(await axeViolations(dialog)).toEqual([]);
        unmount();
        served.admin = false;
        served.access = { ...served.access, data: access({ accessMode: 'workspace', restricted: false }) };
        const other = renderCard();
        expect(await axeViolations(other.container)).toEqual([]);
        fireEvent.click(screen.getByRole('radio', { name: 'Only selected people and teams' }));
        expect(await axeViolations(await screen.findByRole('alertdialog'))).toEqual([]);
    });
});
