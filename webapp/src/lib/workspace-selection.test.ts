import { afterEach, describe, expect, it } from 'vitest';

import { WorkspaceChoice, WorkspaceSelection, matchesSearch, orderChoices, postSignInDestination, readLastWorkspaceId, rememberWorkspace, selectWorkspaceUrl, workspaceDashboardPath, workspaceHome } from './workspace-selection';

const choice = (name: string, extra: Partial<WorkspaceChoice> = {}): WorkspaceChoice => ({
    id: `id-${name}`,
    title: name[0].toUpperCase() + name.slice(1),
    workspaceName: name,
    role: 'EDITOR',
    isOwner: false,
    disabled: false,
    ssoRequired: false,
    ...extra
});

const selection = (workspaces: WorkspaceChoice[], extra: Partial<WorkspaceSelection> = {}): WorkspaceSelection => ({
    workspaces,
    isCreator: true,
    canCreateWorkspace: false,
    next: null,
    notice: null,
    ...extra
});

describe('where a sign-in goes', () => {
    it('no workspace: the selection screen (never a blank page)', () => {
        expect(postSignInDestination(selection([]))).toBe('/workspace/select');
    });

    it('exactly one workspace: straight in', () => {
        expect(postSignInDestination(selection([choice('acme')]))).toBe('/acme/dashboard/forms');
    });

    it('one owned workspace without a title: its onboarding', () => {
        expect(postSignInDestination(selection([choice('mine', { title: 'Untitled', isOwner: true })]))).toBe('/mine/onboarding');
    });

    it('several workspaces: the selection screen, even with a last-used one', () => {
        rememberWorkspace('id-acme');
        expect(postSignInDestination(selection([choice('acme'), choice('beta'), choice('gamma')]))).toBe('/workspace/select');
    });

    it('a disabled workspace an owner may open still counts as the only one', () => {
        expect(postSignInDestination(selection([choice('old', { disabled: true, isOwner: true })]))).toBe('/old/dashboard/forms');
    });

    it('the only workspace needs its single sign-on: the screen, whose row starts it', () => {
        expect(postSignInDestination(selection([choice('acme', { ssoRequired: true })]))).toBe('/workspace/select');
    });

    it('a deep link the server allowed goes there', () => {
        expect(postSignInDestination(selection([choice('acme'), choice('beta')], { next: '/acme/dashboard/forms/f1/responses' }))).toBe('/acme/dashboard/forms/f1/responses');
    });

    it('a deep link to a workspace the user is not in: the screen with the notice, even with one workspace', () => {
        expect(postSignInDestination(selection([choice('acme')], { notice: 'no_access' }))).toBe('/workspace/select?notice=no_access');
    });

    it('never builds a notice from anything but the one code', () => {
        expect(selectWorkspaceUrl('<script>')).toBe('/workspace/select');
        expect(selectWorkspaceUrl('no_access')).toBe('/workspace/select?notice=no_access');
    });
});

describe('rows', () => {
    afterEach(() => window.localStorage.clear());

    it('puts the last-used workspace first and keeps the rest in the server order', () => {
        const list = [choice('alpha'), choice('beta'), choice('gamma')];
        expect(orderChoices(list, 'id-gamma').map((w) => w.workspaceName)).toEqual(['gamma', 'alpha', 'beta']);
        expect(orderChoices(list, 'id-unknown').map((w) => w.workspaceName)).toEqual(['alpha', 'beta', 'gamma']);
        expect(orderChoices(list, null)).toBe(list);
    });

    it('remembers the workspace id only', () => {
        rememberWorkspace('id-beta');
        expect(readLastWorkspaceId()).toBe('id-beta');
        expect(Object.keys(window.localStorage)).toEqual(['bc.lastWorkspaceId']);
        rememberWorkspace('not an id <b>');
        expect(readLastWorkspaceId()).toBe('id-beta');
        window.localStorage.setItem('bc.lastWorkspaceId', 'javascript:alert(1)');
        expect(readLastWorkspaceId()).toBeNull();
    });

    it('searches the name, handle and domain', () => {
        const row = choice('acme', { title: 'Acme Corp', customDomain: 'forms.acme.test' });
        expect(matchesSearch(row, 'corp')).toBe(true);
        expect(matchesSearch(row, 'ACME')).toBe(true);
        expect(matchesSearch(row, 'forms.acme')).toBe(true);
        expect(matchesSearch(row, 'beta')).toBe(false);
        expect(matchesSearch(row, '  ')).toBe(true);
    });

    it('links a workspace by its encoded handle', () => {
        expect(workspaceHome(choice('a b'))).toBe('/a%20b/dashboard/forms');
        expect(workspaceDashboardPath('a b')).toBe('/a%20b/dashboard');
        expect(workspaceDashboardPath('a%20b')).toBe('/a%20b/dashboard');
        expect(workspaceDashboardPath('%E0%A4%A')).toBe('/%25E0%25A4%25A/dashboard');
    });
});
