// API key roles on the key page: a role and a list of forms when a key is made, the edit dialog (with its warning
// when a change widens the key), the chips in the list, every refusal in words, and nothing of it while the
// server has the switch off.
import React from 'react';

import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { KEY_ERROR_CODES, listAllowsScope, lowestRoleFor, roleAllowsScope, scopeProblems, submissionFormsOutsideList, widensKey, widensRole } from '@app/components/api-keys/key-rules';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import APIKeysPage from './page';

const served: { roles: boolean } = { roles: true };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (p: string) => p === WorkspacePermission.SECURITY_MANAGE, submissionsApiEnabled: true, apiKeyRolesEnabled: served.roles })
}));
vi.mock('@app/store/hooks', () => ({ useAppSelector: () => ({ id: 'workspace-1', workspaceName: 'acme' }) }));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toasted }) }));

const created = vi.fn();
const updated = vi.fn();
const toasted = vi.fn();
const formsAsked = vi.fn();
const refetch = vi.fn();
const KEYS: any[] = [];
const FORMS = [
    { formId: 'f1', title: 'Registration', isPublished: true },
    { formId: 'f2', title: 'Staff survey', isPublished: false },
    { formId: 'f3', title: 'Workshop feedback', isPublished: true, access: { restricted: true } }
];
let formPages: any[] = [{ page: 1, pages: 1, items: FORMS }];
vi.mock('@app/store/workspaces/api', async (original) => ({
    ...((await original()) as object),
    useGetAPIKeysQuery: () => ({ data: KEYS, isLoading: false, refetch }),
    useCreateAPIKeyMutation: () => [(arg: any) => Promise.resolve(created(arg) ?? { data: { name: 'k', token: 'bc_x' } }), { isLoading: false }],
    useUpdateAPIKeyMutation: () => [(arg: any) => Promise.resolve(updated(arg) ?? { data: {} }), { isLoading: false }],
    useRevokeAPIKeyMutation: () => [vi.fn()],
    useGetWorkspaceFormsQuery: (arg: any) => {
        formsAsked(arg);
        return { data: formPages[arg.page - 1] ?? formPages[0] };
    }
}));

const box = (name: string | RegExp) => screen.getByRole('checkbox', { name: typeof name === 'string' ? new RegExp(name) : name });
const roleSelect = () => screen.getByLabelText('Role') as HTMLSelectElement;
const createButton = () => screen.getByRole('button', { name: 'Create key' });
const name = (value = 'Nightly export') => fireEvent.change(screen.getByPlaceholderText(/./), { target: { value } });
const body = () => created.mock.calls.at(-1)?.[0].body;

const READER = { id: 'k1', name: 'Reporting', prefix: 'bc_aaaa', scopes: ['forms:read', 'responses:read'], revoked: false, role: 'VIEWER', formScope: 'listed', forms: [{ id: 'f1', title: 'Registration' }] };
const FOLLOWER = { id: 'k2', name: 'Old sync', prefix: 'bc_bbbb', scopes: ['forms:read'], revoked: false, role: null, formScope: 'all', forms: [] };

beforeEach(() => {
    served.roles = true;
    for (const mock of [created, updated, toasted, formsAsked, refetch]) mock.mockReset();
    refetch.mockImplementation(async () => ({ data: KEYS }));
    formPages = [{ page: 1, pages: 1, items: FORMS }];
    KEYS.length = 0;
});
afterEach(async () => {
    await act(() => i18n.changeLanguage('en'));
});

describe('the rules a key must keep, as the browser checks them', () => {
    it('knows which role carries which scope', () => {
        const matrix: Record<string, string[]> = {
            EDITOR: ['forms:read', 'forms:write', 'forms:delete', 'responses:read', 'submissions:write'],
            REVIEWER: ['forms:read', 'responses:read'],
            VIEWER: ['forms:read', 'responses:read'],
            PRIVACY_OFFICER: ['forms:read', 'deletion_requests:read', 'deletion_requests:write']
        };
        const every = ['forms:read', 'forms:write', 'forms:delete', 'responses:read', 'deletion_requests:read', 'deletion_requests:write', 'submissions:write'];
        for (const [role, allowed] of Object.entries(matrix)) {
            for (const scope of every) expect([role, scope, roleAllowsScope(role as any, scope)]).toEqual([role, scope, allowed.includes(scope)]);
        }
        // no role: as its creator, which can carry anything
        for (const scope of every) expect(roleAllowsScope(null, scope)).toBe(true);
    });

    it('refuses what a key limited to forms cannot carry', () => {
        expect(['forms:delete', 'deletion_requests:read', 'deletion_requests:write'].filter((scope) => !listAllowsScope(scope))).toHaveLength(3);
        expect(listAllowsScope('responses:read')).toBe(true);
        expect(scopeProblems(null, 'listed', ['forms:read', 'forms:delete'])).toEqual([{ scope: 'forms:delete', reason: 'list' }]);
        expect(scopeProblems('VIEWER', 'all', ['forms:write'])).toEqual([{ scope: 'forms:write', reason: 'role' }]);
        expect(scopeProblems('EDITOR', 'all', ['forms:read', 'forms:write'])).toEqual([]);
    });

    it('names the lowest role that allows the scopes, or none', () => {
        expect(lowestRoleFor(['forms:read'])).toBe('VIEWER');
        expect(lowestRoleFor(['forms:read', 'responses:read'])).toBe('VIEWER');
        expect(lowestRoleFor(['forms:read', 'deletion_requests:write'])).toBe('PRIVACY_OFFICER');
        expect(lowestRoleFor(['forms:write'])).toBe('EDITOR');
        expect(lowestRoleFor(['forms:write', 'deletion_requests:write'])).toBeNull();
    });

    it('tells a widening from a narrowing', () => {
        const scopes = ['forms:read', 'responses:read'];
        expect(widensRole('VIEWER', 'REVIEWER', scopes)).toBe(true);
        expect(widensRole('EDITOR', 'VIEWER', scopes)).toBe(false);
        expect(widensRole('VIEWER', null, scopes)).toBe(true);
        expect(widensRole(null, 'VIEWER', scopes)).toBe(false);
        expect(widensRole('VIEWER', 'VIEWER', scopes)).toBe(false);
        const listed = { role: 'VIEWER' as const, formScope: 'listed' as const, formIds: ['a', 'b'] };
        expect(widensKey(listed, { ...listed, formScope: 'all', formIds: [] }, scopes)).toBe(true);
        expect(widensKey(listed, { ...listed, formIds: ['a', 'b', 'c'] }, scopes)).toBe(true);
        expect(widensKey(listed, { ...listed, formIds: ['a'] }, scopes)).toBe(false);
        expect(widensKey({ ...listed, formScope: 'all', formIds: [] }, listed, scopes)).toBe(false);
    });

    it('finds a submission form that is not on the list', () => {
        expect(submissionFormsOutsideList(['a', 'z'], 'listed', ['a', 'b'])).toEqual(['z']);
        expect(submissionFormsOutsideList(['a'], 'listed', ['a'])).toEqual([]);
        expect(submissionFormsOutsideList(['z'], 'all', [])).toEqual([]);
        expect(submissionFormsOutsideList(null, 'listed', ['a'])).toEqual([]);
    });
});

describe('with the switch off', () => {
    beforeEach(() => {
        served.roles = false;
    });

    it('is the page it was: no role, no forms choice, no new request, no new field in the key', () => {
        KEYS.push({ ...FOLLOWER, role: null }, { id: 'k3', name: 'Plain', prefix: 'bc_cccc', scopes: ['forms:read'], revoked: false });
        render(<APIKeysPage />);
        expect(screen.queryByLabelText('Role')).toBeNull();
        expect(screen.queryByText('Every form this role can reach')).toBeNull();
        expect(screen.queryByRole('button', { name: /^Edit/ })).toBeNull();
        expect(screen.queryByText('All forms')).toBeNull();
        expect(screen.queryByText(/follow their creator/)).toBeNull();
        // the one request the page always made: the published forms of the submissions scope, and it is skipped
        expect(formsAsked.mock.calls.every(([arg]) => arg.published === true)).toBe(true);
        name('CRM sync');
        fireEvent.click(createButton());
        expect(body()).toEqual({ name: 'CRM sync', scopes: ['forms:read'], acknowledgeUnredactedResponses: false });
    });

    it('keeps the scope boxes as they were, whatever is ticked', () => {
        render(<APIKeysPage />);
        name('CRM sync');
        fireEvent.click(box('Delete forms'));
        fireEvent.click(box('Act on deletion requests'));
        expect(box('Delete forms')).toBeEnabled();
        expect(screen.queryByRole('alert')).toBeNull();
        expect(createButton()).toBeEnabled();
    });

    it('shows what a key already stores, read only, without an Edit', () => {
        KEYS.push(READER);
        render(<APIKeysPage />);
        expect(screen.getByText('Role: Viewer')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: '1 form' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /^Edit/ })).toBeNull();
    });
});

describe('making a key with a role and a list of forms', () => {
    it('labels the role and follows the scopes until somebody chooses', () => {
        render(<APIKeysPage />);
        expect(roleSelect()).toHaveValue('VIEWER');
        expect(screen.getByText(/The lowest role that allows these scopes/)).toBeInTheDocument();
        fireEvent.click(box('Create & edit forms'));
        expect(roleSelect()).toHaveValue('EDITOR');
        fireEvent.click(box('Act on deletion requests'));
        // nothing carries both: the key follows its creator, and the screen says so
        expect(roleSelect()).toHaveValue('');
        expect(screen.getByText(/No single role allows these scopes/)).toBeInTheDocument();
        // a role chosen by hand no longer follows
        fireEvent.change(roleSelect(), { target: { value: 'EDITOR' } });
        expect(screen.queryByText(/lowest role/)).toBeNull();
        expect(screen.getByRole('alert')).toHaveTextContent('This role cannot carry the scope “Act on deletion requests”.');
        expect(createButton()).toBeDisabled();
    });

    it('sends the role it follows, or the one chosen, and "as its creator" as no role at all', () => {
        render(<APIKeysPage />);
        name();
        fireEvent.click(createButton());
        expect(body()).toEqual({ name: 'Nightly export', scopes: ['forms:read'], acknowledgeUnredactedResponses: false, role: 'VIEWER' });
        created.mockClear();
        fireEvent.change(roleSelect(), { target: { value: 'REVIEWER' } });
        fireEvent.click(createButton());
        expect(body().role).toBe('REVIEWER');
        created.mockClear();
        fireEvent.change(roleSelect(), { target: { value: '' } });
        fireEvent.click(createButton());
        expect(body()).toEqual({ name: 'Nightly export', scopes: ['forms:read'], acknowledgeUnredactedResponses: false });
    });

    it('greys out the scope a chosen role cannot carry, and says why', () => {
        render(<APIKeysPage />);
        fireEvent.change(roleSelect(), { target: { value: 'REVIEWER' } });
        expect(box('Create & edit forms')).toBeDisabled();
        expect(box('Delete forms')).toBeDisabled();
        expect(screen.getAllByText('The chosen role cannot carry this scope.').length).toBeGreaterThan(0);
        expect(box('Read responses')).toBeEnabled();
        fireEvent.change(roleSelect(), { target: { value: 'PRIVACY_OFFICER' } });
        expect(box('Act on deletion requests')).toBeEnabled();
        expect(box('Read responses')).toBeDisabled();
    });

    it('keeps a ticked scope that the new role cannot carry enabled, so it can be unticked, and refuses to send it', () => {
        render(<APIKeysPage />);
        fireEvent.click(box('Read responses'));
        fireEvent.change(roleSelect(), { target: { value: 'PRIVACY_OFFICER' } });
        expect(box('Read responses')).toBeEnabled();
        expect(screen.getByRole('alert')).toHaveTextContent('This role cannot carry the scope “Read responses”.');
        name();
        expect(createButton()).toBeDisabled();
        fireEvent.click(box('Read responses'));
        expect(screen.queryByRole('alert')).toBeNull();
        // nothing is ticked any more: no key without a scope
        expect(createButton()).toBeDisabled();
    });

    it('limits a key to forms: asks for the forms only then, waits for one, and sends the list', () => {
        render(<APIKeysPage />);
        expect(formsAsked.mock.calls.some(([arg]) => arg.published !== true)).toBe(false);
        fireEvent.click(screen.getByRole('radio', { name: 'Only the forms I pick' }));
        expect(formsAsked.mock.calls.some(([arg]) => arg.published !== true)).toBe(true);
        expect(screen.getByText(/cannot create forms, delete forms or handle deletion requests/)).toBeInTheDocument();
        name();
        expect(createButton()).toBeDisabled();
        fireEvent.click(screen.getByRole('checkbox', { name: /Registration/ }));
        fireEvent.click(screen.getByRole('checkbox', { name: /Workshop feedback/ }));
        expect(screen.getByRole('status')).toHaveTextContent('2 of 200 forms picked');
        expect(screen.getByText('This key reaches 2 forms. It never does more than you can, now or later.')).toBeInTheDocument();
        fireEvent.click(createButton());
        expect(body()).toMatchObject({ role: 'VIEWER', formScope: 'listed', formIds: ['f1', 'f3'] });
        expect(body().submissionFormIds).toBeUndefined();
    });

    it('lists drafts and restricted forms with their chips, searches, and picks all that are shown', () => {
        render(<APIKeysPage />);
        fireEvent.click(screen.getByRole('radio', { name: 'Only the forms I pick' }));
        expect(screen.getByRole('checkbox', { name: /Staff survey.*Draft/ })).toBeInTheDocument();
        fireEvent.change(screen.getByLabelText('Search forms'), { target: { value: 'sur' } });
        expect(screen.queryByRole('checkbox', { name: /Registration/ })).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: 'Pick all shown' }));
        fireEvent.change(screen.getByLabelText('Search forms'), { target: { value: '' } });
        expect(screen.getByRole('checkbox', { name: /Staff survey/ })).toBeChecked();
        expect(screen.getByRole('checkbox', { name: /Registration/ })).not.toBeChecked();
        fireEvent.change(screen.getByLabelText('Search forms'), { target: { value: 'nothing like it' } });
        expect(screen.getByText('No form matches your search.')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Clear the picks' }));
        expect(screen.getByRole('status')).toHaveTextContent('0 of 200');
    });

    it('stops at 200 forms', () => {
        formPages = [{ page: 1, pages: 1, items: Array.from({ length: 205 }, (_, index) => ({ formId: `g${index}`, title: `Form ${index}`, isPublished: true })) }];
        render(<APIKeysPage />);
        fireEvent.click(screen.getByRole('radio', { name: 'Only the forms I pick' }));
        fireEvent.click(screen.getByRole('button', { name: 'Pick all shown' }));
        expect(screen.getByRole('status')).toHaveTextContent('200 of 200');
        expect(screen.getByText('A key can be limited to at most 200 forms.')).toBeInTheDocument();
        expect(screen.getByRole('checkbox', { name: /Form 204/ })).toBeDisabled();
        expect(screen.getByRole('checkbox', { name: /Form 0$/ })).toBeEnabled();
    });

    it('turns away, before sending, a list with the scopes a listed key cannot have', () => {
        render(<APIKeysPage />);
        fireEvent.click(box('Delete forms'));
        fireEvent.click(screen.getByRole('radio', { name: 'Only the forms I pick' }));
        fireEvent.click(screen.getByRole('checkbox', { name: /Registration/ }));
        name();
        expect(screen.getByRole('alert')).toHaveTextContent('A key limited to forms cannot carry the scope “Delete forms”.');
        expect(createButton()).toBeDisabled();
        // the scope boxes it cannot carry are greyed out, with the reason, while they are unticked
        fireEvent.click(box('Delete forms'));
        expect(box('Delete forms')).toBeDisabled();
        expect(box('Act on deletion requests')).toBeDisabled();
        expect(screen.getAllByText('A key limited to forms cannot carry this scope.').length).toBe(3);
        expect(createButton()).toBeEnabled();
    });

    it('folds the submission forms into the list', () => {
        render(<APIKeysPage />);
        fireEvent.click(box('Submit responses'));
        expect(screen.getByRole('checkbox', { name: 'Only for these forms' })).toBeInTheDocument();
        fireEvent.click(screen.getByRole('radio', { name: 'Only the forms I pick' }));
        expect(screen.queryByRole('checkbox', { name: 'Only for these forms' })).toBeNull();
        expect(screen.getByText('A key limited to forms submits only to those forms.')).toBeInTheDocument();
    });

    it('starts again after a key is made', async () => {
        render(<APIKeysPage />);
        fireEvent.click(screen.getByRole('radio', { name: 'Only the forms I pick' }));
        fireEvent.click(screen.getByRole('checkbox', { name: /Registration/ }));
        name();
        fireEvent.click(createButton());
        await waitFor(() => expect(screen.getByRole('radio', { name: 'Every form this role can reach' })).toBeChecked());
        expect(roleSelect()).toHaveValue('VIEWER');
    });
});

describe('what the server refuses is said in words', () => {
    const cases: Array<[string, string]> = [
        ['api_key_roles_off', 'Key roles are turned off on this instance.'],
        ['key_exceeds_editor', 'You cannot make this key follow a person who may do more than you may. Ask an Owner to change it.'],
        ['key_role_exceeds_creator', 'A key cannot have a role that allows more than the person who created it may do.'],
        ['key_form_scope', 'This key is limited to certain forms, so it cannot create a form.'],
        ['key_role_lacks_permission', 'The role of this key does not allow that.'],
        ['key_changed', 'Someone changed this key while you were editing it. Reload it to see how it is now, then make your change again.'],
        ['key_revoked', 'This key has been revoked and can no longer be changed.'],
        ['unknown_key_scope', 'This key carries a scope this server no longer knows. Revoke it and create a new key.'],
        ['scope_not_allowed_by_role', 'This role cannot carry the scope “Delete forms”.'],
        ['scope_not_allowed_for_listed_key', 'A key limited to forms cannot carry the scope “Delete forms”.'],
        ['invalid_key_role', 'That is not a role a key can have.'],
        ['invalid_form_scope', 'That is not a valid choice of forms.'],
        ['form_ids_required', 'Pick the forms this key may use.'],
        ['form_ids_need_listed_scope', 'A list of forms only goes with “Only the forms I pick”.'],
        ['form_not_in_workspace', 'One of the forms is not in this workspace, or you cannot open it. Reload the page and pick again.'],
        ['submission_form_outside_list', 'This key submits to a form that is not on the list. Add that form to the list, or create a new key.']
    ];

    it('has a message for every code the key routes answer with', () => {
        expect(Object.keys(KEY_ERROR_CODES).sort()).toEqual(cases.map(([code]) => code).sort());
    });

    it.each(cases)('says %s when a key is made', async (code, text) => {
        render(<APIKeysPage />);
        name();
        created.mockReturnValueOnce({ error: { status: 400, data: { code, message: `The server's own words for '${code === 'key_form_scope' ? 'x' : 'forms:delete'}'.` } } });
        fireEvent.click(createButton());
        await waitFor(() => expect(toasted).toHaveBeenCalled());
        expect(toasted.mock.calls[0][0].description).toBe(text);
    });

    it('falls back to the server’s message for a code it does not know', async () => {
        render(<APIKeysPage />);
        name();
        created.mockReturnValueOnce({ error: { data: { code: 'something_new', message: 'Something new happened.' } } });
        fireEvent.click(createButton());
        await waitFor(() => expect(toasted).toHaveBeenCalled());
        expect(toasted.mock.calls[0][0].description).toBe('Something new happened.');
    });
});

describe('the list of keys', () => {
    it('shows each key’s role and forms, and the titles on demand', () => {
        KEYS.push(READER, FOLLOWER);
        render(<APIKeysPage />);
        expect(screen.getByText('Role: Viewer')).toBeInTheDocument();
        // the option of the role select and the chip of the key that has none
        expect(screen.getAllByText('Same as its creator')).toHaveLength(2);
        expect(screen.getByText('All forms')).toBeInTheDocument();
        const chip = screen.getByRole('button', { name: '1 form' });
        expect(chip).toHaveAttribute('aria-expanded', 'false');
        expect(screen.queryByText('Registration')).toBeNull();
        fireEvent.click(chip);
        expect(chip).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByText('Registration')).toBeInTheDocument();
        fireEvent.click(chip);
        expect(screen.queryByText('Registration')).toBeNull();
    });

    it('says "a form you cannot open" for a form without a title', () => {
        KEYS.push({ ...READER, forms: [{ id: 'zz', title: null }] });
        render(<APIKeysPage />);
        fireEvent.click(screen.getByRole('button', { name: '1 form' }));
        expect(screen.getByText('A form you cannot open')).toBeInTheDocument();
    });

    it('nudges owners to limit the keys that follow their creator, and filters to them', () => {
        KEYS.push(READER, FOLLOWER, { ...FOLLOWER, id: 'k4', name: 'Gone', revoked: true });
        render(<APIKeysPage />);
        expect(screen.getByText('1 key follows its creator’s role. Limit it to what it needs.')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Show these keys' }));
        expect(screen.queryByText('Reporting')).toBeNull();
        expect(screen.getByText('Old sync')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Show all keys' }));
        expect(screen.getByText('Reporting')).toBeInTheDocument();
    });

    it('has no nudge when every key has a role', () => {
        KEYS.push(READER);
        render(<APIKeysPage />);
        expect(screen.queryByText(/follows? (its|their) creator/)).toBeNull();
    });

    it('does not offer Edit on a revoked key', () => {
        KEYS.push({ ...READER, revoked: true });
        render(<APIKeysPage />);
        expect(screen.queryByRole('button', { name: /^Edit/ })).toBeNull();
    });
});

describe('editing a key', () => {
    const open = (key: any = READER) => {
        KEYS.push(key);
        render(<APIKeysPage />);
        fireEvent.click(screen.getByRole('button', { name: `Edit “${key.name}”` }));
        return screen.getByRole('dialog', { name: `Edit “${key.name}”` });
    };
    const save = () => screen.getByRole('button', { name: /^(Save|Widen and save)$/ });

    it('opens on the key as it is, with its scopes read only and the way to change them', () => {
        const dialog = open();
        expect(within(dialog).getByLabelText('Name')).toHaveValue('Reporting');
        expect(within(dialog).getByLabelText('Role')).toHaveValue('VIEWER');
        expect(within(dialog).getByRole('radio', { name: 'Only the forms I pick' })).toBeChecked();
        expect(within(dialog).getByRole('checkbox', { name: /Registration/ })).toBeChecked();
        expect(within(dialog).getByText('Read forms')).toBeInTheDocument();
        expect(within(dialog).getByText('To change what the key does, create a new key.')).toBeInTheDocument();
        expect(within(dialog).queryByRole('checkbox', { name: /Read responses/ })).toBeNull();
        expect(save()).toBeDisabled();
    });

    it('moves focus into the dialog and closes on Escape', async () => {
        const dialog = open();
        await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
        fireEvent.keyDown(dialog, { key: 'Escape' });
        await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    });

    it('sends only what changed, and warns of nothing when the change narrows', async () => {
        const dialog = open({ ...READER, role: 'EDITOR', scopes: ['forms:read', 'responses:read'] });
        fireEvent.change(within(dialog).getByLabelText('Role'), { target: { value: 'VIEWER' } });
        fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Reporting (read only)' } });
        expect(screen.queryByText(/more access/)).toBeNull();
        expect(save()).toHaveTextContent('Save');
        fireEvent.click(save());
        await waitFor(() => expect(updated).toHaveBeenCalled());
        expect(updated.mock.calls[0][0]).toEqual({ workspace_id: 'workspace-1', key_id: 'k1', body: { name: 'Reporting (read only)', role: 'VIEWER' } });
        await waitFor(() => expect(toasted).toHaveBeenCalledWith({ description: 'Saved “Reporting (read only)”' }));
        await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    });

    it('warns before a higher role is saved, and the button says what it does', async () => {
        const dialog = open();
        fireEvent.change(within(dialog).getByLabelText('Role'), { target: { value: 'REVIEWER' } });
        expect(within(dialog).getByRole('alert')).toHaveTextContent('You are giving this key more access. Whatever holds its secret gets it too.');
        expect(save()).toHaveTextContent('Widen and save');
        fireEvent.click(save());
        await waitFor(() => expect(updated).toHaveBeenCalled());
        expect(updated.mock.calls[0][0].body).toEqual({ role: 'REVIEWER' });
    });

    it('warns when the list is lifted, and sends only the scope', async () => {
        const dialog = open();
        fireEvent.click(within(dialog).getByRole('radio', { name: 'Every form this role can reach' }));
        expect(within(dialog).getByText(/You are giving this key more access/)).toBeInTheDocument();
        fireEvent.click(save());
        await waitFor(() => expect(updated).toHaveBeenCalled());
        expect(updated.mock.calls[0][0].body).toEqual({ formScope: 'all' });
    });

    it('warns when forms are added, and not when one is taken off', async () => {
        const dialog = open({ ...READER, forms: [{ id: 'f1', title: 'Registration' }, { id: 'f2', title: 'Staff survey' }] });
        fireEvent.click(within(dialog).getByRole('checkbox', { name: /Staff survey/ }));
        expect(within(dialog).queryByText(/more access/)).toBeNull();
        fireEvent.click(within(dialog).getByRole('checkbox', { name: /Workshop feedback/ }));
        expect(within(dialog).getByText(/more access/)).toBeInTheDocument();
        fireEvent.click(save());
        await waitFor(() => expect(updated).toHaveBeenCalled());
        expect(updated.mock.calls[0][0].body).toEqual({ formScope: 'listed', formIds: ['f1', 'f3'] });
    });

    it('warns when the role is cleared to "as its creator"', async () => {
        const dialog = open();
        fireEvent.change(within(dialog).getByLabelText('Role'), { target: { value: '' } });
        expect(within(dialog).getByText(/more access/)).toBeInTheDocument();
        fireEvent.click(save());
        await waitFor(() => expect(updated).toHaveBeenCalled());
        expect(updated.mock.calls[0][0].body).toEqual({ role: null });
    });

    it('limits a key that had no list, and that is a narrowing', async () => {
        const dialog = open(FOLLOWER);
        fireEvent.click(within(dialog).getByRole('radio', { name: 'Only the forms I pick' }));
        // a list with nothing on it waits for a form
        expect(save()).toBeDisabled();
        expect(within(dialog).getByText('Pick at least one form, or choose every form.')).toBeInTheDocument();
        fireEvent.click(within(dialog).getByRole('checkbox', { name: /Registration/ }));
        expect(within(dialog).queryByText(/more access/)).toBeNull();
        fireEvent.click(save());
        await waitFor(() => expect(updated).toHaveBeenCalled());
        expect(updated.mock.calls[0][0].body).toEqual({ formScope: 'listed', formIds: ['f1'] });
    });

    it('refuses, before sending, a list for a key whose scopes a list cannot carry', () => {
        const dialog = open({ ...FOLLOWER, scopes: ['forms:read', 'forms:delete'] });
        fireEvent.click(within(dialog).getByRole('radio', { name: 'Only the forms I pick' }));
        fireEvent.click(within(dialog).getByRole('checkbox', { name: /Registration/ }));
        expect(within(dialog).getByRole('alert')).toHaveTextContent('A key limited to forms cannot carry the scope “Delete forms”.');
        expect(save()).toBeDisabled();
    });

    it('refuses, before sending, a role that cannot carry the key’s scopes', () => {
        const dialog = open({ ...FOLLOWER, role: 'EDITOR', scopes: ['forms:write'] });
        fireEvent.change(within(dialog).getByLabelText('Role'), { target: { value: 'VIEWER' } });
        expect(within(dialog).getByRole('alert')).toHaveTextContent('This role cannot carry the scope “Create & edit forms”.');
        expect(save()).toBeDisabled();
    });

    it('refuses a list that leaves out a form the key submits to', () => {
        const dialog = open({ ...READER, role: 'EDITOR', scopes: ['forms:read', 'submissions:write'], submissionFormIds: ['f1', 'f2'] });
        expect(within(dialog).getByText(/submits to a form that is not on the list/)).toBeInTheDocument();
        expect(save()).toBeDisabled();
    });

    it('offers to reload when somebody else changed the key, and starts again from the key as it is', async () => {
        const dialog = open();
        fireEvent.change(within(dialog).getByLabelText('Role'), { target: { value: 'REVIEWER' } });
        updated.mockReturnValueOnce({ error: { status: 409, data: { code: 'key_changed', message: 'The key changed.' } } });
        fireEvent.click(save());
        await waitFor(() => expect(dialog).toHaveTextContent('Someone changed this key while you were editing it.'));
        // someone made it a Reviewer meanwhile
        KEYS.splice(0, 1, { ...READER, role: 'REVIEWER', name: 'Reporting (changed)' });
        fireEvent.click(within(dialog).getByRole('button', { name: 'Reload and try again' }));
        await waitFor(() => expect(refetch).toHaveBeenCalled());
        await waitFor(() => expect(within(dialog).getByLabelText('Name')).toHaveValue('Reporting (changed)'));
        expect(within(dialog).getByLabelText('Role')).toHaveValue('REVIEWER');
        expect(within(dialog).queryByRole('alert')).toBeNull();
        expect(save()).toBeDisabled();
    });

    it('closes when the reloaded key is gone', async () => {
        const dialog = open();
        fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'New name' } });
        updated.mockReturnValueOnce({ error: { status: 409, data: { code: 'key_changed', message: 'x' } } });
        fireEvent.click(save());
        await waitFor(() => within(dialog).getByRole('button', { name: 'Reload and try again' }));
        KEYS.length = 0;
        fireEvent.click(within(dialog).getByRole('button', { name: 'Reload and try again' }));
        await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    });

    it.each(cases())('says %s and keeps the dialog open', async (code, text) => {
        const dialog = open();
        fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Renamed' } });
        updated.mockReturnValueOnce({ error: { status: 403, data: { code, message: "forms:delete 'forms:delete'" } } });
        fireEvent.click(save());
        await waitFor(() => expect(dialog).toHaveTextContent(text));
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        // only a reload is offered for key_changed
        expect(!!within(dialog).queryByRole('button', { name: 'Reload and try again' })).toBe(code === 'key_changed');
        expect(toasted).not.toHaveBeenCalled();
    });

    it('says the generic text when the answer has no code or message', async () => {
        const dialog = open();
        fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Renamed' } });
        updated.mockReturnValueOnce({ error: { status: 500, data: undefined } });
        fireEvent.click(save());
        await waitFor(() => expect(dialog).toHaveTextContent('Could not save the key. Please try again.'));
    });
});

function cases(): Array<[string, string]> {
    return [
        ['api_key_roles_off', 'Key roles are turned off on this instance.'],
        ['key_exceeds_editor', 'You cannot make this key follow a person who may do more than you may.'],
        ['key_changed', 'Someone changed this key while you were editing it.'],
        ['key_revoked', 'This key has been revoked and can no longer be changed.'],
        ['unknown_key_scope', 'This key carries a scope this server no longer knows.'],
        ['key_role_exceeds_creator', 'A key cannot have a role that allows more than the person who created it may do.'],
        ['scope_not_allowed_by_role', 'This role cannot carry the scope “Delete forms”.']
    ];
}

describe('in Dutch, and for assistive technology', () => {
    it('is written in Dutch', async () => {
        await act(() => i18n.changeLanguage('nl'));
        KEYS.push(READER, FOLLOWER);
        render(<APIKeysPage />);
        expect(screen.getByLabelText('Rol')).toBeInTheDocument();
        expect(screen.getByRole('group', { name: 'Formulieren' })).toBeInTheDocument();
        expect(screen.getByRole('radio', { name: 'Alleen de formulieren die ik kies' })).toBeInTheDocument();
        expect(screen.getByText('Rol: Kijker')).toBeInTheDocument();
        expect(screen.getByText('1 sleutel volgt de rol van zijn maker. Beperk hem tot wat hij nodig heeft.')).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Wijzigen “Reporting”' }));
        expect(screen.getByRole('dialog', { name: '“Reporting” wijzigen' })).toBeInTheDocument();
        fireEvent.change(screen.getAllByLabelText('Rol').at(-1)!, { target: { value: 'REVIEWER' } });
        expect(screen.getByText('U geeft deze sleutel meer toegang. Alles wat het geheim van de sleutel heeft, krijgt die toegang ook.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Verruimen en opslaan' })).toBeInTheDocument();
    });

    it('has labelled controls, grouped radios and no axe violations in English and Dutch, with the dialog open', async () => {
        for (const language of ['en', 'nl']) {
            await act(() => i18n.changeLanguage(language));
            KEYS.length = 0;
            KEYS.push(READER, FOLLOWER);
            const { unmount } = render(<APIKeysPage />);
            fireEvent.click(screen.getByRole('checkbox', { name: language === 'en' ? /Delete forms/ : /Formulieren verwijderen/ }));
            fireEvent.click(screen.getAllByRole('radio').at(-1)!);
            fireEvent.change(screen.getByLabelText(language === 'en' ? 'Role' : 'Rol'), { target: { value: 'EDITOR' } });
            expect(screen.getByRole('alert')).toBeInTheDocument();
            expect(await axeViolations(document.body)).toEqual([]);
            fireEvent.click(screen.getAllByRole('button', { name: /Edit|Wijzigen/ })[0]);
            expect(await axeViolations(document.body)).toEqual([]);
            unmount();
        }
    });

    it('announces a problem as an alert and a count as a status', () => {
        render(<APIKeysPage />);
        fireEvent.click(screen.getByRole('radio', { name: 'Only the forms I pick' }));
        expect(screen.getByRole('status')).toBeInTheDocument();
        fireEvent.click(box('Delete forms'));
        expect(screen.getByRole('alert')).toBeInTheDocument();
    });
});
