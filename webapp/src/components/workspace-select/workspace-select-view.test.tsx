import React from 'react';

import { fireEvent, render, screen, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkspaceChoice, WorkspaceSelection } from '@app/lib/workspace-selection';
import { setAuth } from '@app/store/auth/slice';
import { store } from '@app/store/store';

import WorkspaceSelectView from './workspace-select-view';

const navigateWithReferrer = vi.fn();
vi.mock('@app/lib/sso', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, navigateWithReferrer: (url: string) => navigateWithReferrer(url) };
});

const openModal = vi.fn();
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal, closeModal: vi.fn() }) }));

const answer: { data?: WorkspaceSelection; isLoading: boolean; isError: boolean } = { isLoading: false, isError: false };
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useGetWorkspaceSelectionQuery: () => ({ ...answer, refetch: vi.fn() }) };
});

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

const show = (workspaces: WorkspaceChoice[], extra: Partial<WorkspaceSelection> = {}, notice: string | null = null) => {
    answer.data = { workspaces, isCreator: true, canCreateWorkspace: false, next: null, notice: null, ...extra };
    return render(
        <ReduxProvider store={store}>
            <WorkspaceSelectView notice={notice} />
        </ReduxProvider>
    );
};

const rows = () => within(screen.getByRole('list')).getAllByRole('listitem');

describe('WorkspaceSelectView', () => {
    beforeEach(() => {
        navigateWithReferrer.mockReset();
        store.dispatch(setAuth({ id: 'u1', email: 'jane@example.test' } as any));
    });
    afterEach(() => window.localStorage.clear());

    it('lists three workspaces as links under a focused heading', () => {
        show([choice('alpha', { role: 'OWNER', isOwner: true }), choice('beta', { customDomain: 'forms.beta.test' }), choice('gamma', { role: 'VIEWER' })]);

        const heading = screen.getByRole('heading', { level: 1 });
        expect(document.activeElement).toBe(heading);
        expect(rows()).toHaveLength(3);
        const links = within(screen.getByRole('list')).getAllByRole('link');
        expect(links.map((a) => a.getAttribute('href'))).toEqual(['/alpha/dashboard/forms', '/beta/dashboard/forms', '/gamma/dashboard/forms']);
        expect(screen.getByText('forms.beta.test')).toBeTruthy();
        // no search for a short list
        expect(screen.queryByRole('searchbox')).toBeNull();
    });

    it('marks the last-used workspace and lists it first', () => {
        window.localStorage.setItem('bc.lastWorkspaceId', 'id-gamma');
        show([choice('alpha'), choice('beta'), choice('gamma')]);

        const first = rows()[0];
        expect(within(first).getByText('Gamma')).toBeTruthy();
        expect(within(first).getByText(/LAST_USED|Last used/)).toBeTruthy();
    });

    it('remembers the workspace opened', () => {
        show([choice('alpha'), choice('beta')]);
        fireEvent.click(within(rows()[1]).getByRole('link'));
        expect(window.localStorage.getItem('bc.lastWorkspaceId')).toBe('id-beta');
    });

    it('offers a labelled search for a long list', () => {
        show(Array.from({ length: 12 }, (_, i) => choice(`space${String(i).padStart(2, '0')}`)));

        const search = screen.getByRole('searchbox', { name: /SEARCH_LABEL|Search workspaces/ });
        fireEvent.change(search, { target: { value: 'space07' } });
        expect(rows()).toHaveLength(1);
        fireEvent.change(search, { target: { value: 'nothing-like-it' } });
        expect(screen.queryByRole('list')).toBeNull();
        expect(screen.getByRole('status')).toBeTruthy();
    });

    it('marks a disabled workspace read-only and still opens it for its owner', () => {
        show([choice('old', { disabled: true, isOwner: true, role: 'OWNER' }), choice('beta')]);
        const row = rows()[1].textContent?.includes('Old') ? rows()[1] : rows()[0];
        expect(within(row).getByText(/READ_ONLY|Read-only/)).toBeTruthy();
        expect(within(row).getByRole('link').getAttribute('href')).toBe('/old/dashboard/forms');
    });

    it('starts the single sign-on for a workspace that requires it, never a plain link', () => {
        show([choice('acme', { ssoRequired: true }), choice('beta')]);
        const row = rows()[0];
        expect(within(row).queryByRole('link')).toBeNull();
        expect(within(row).getByText(/SSO_REQUIRED|Requires single sign-on/)).toBeTruthy();
        fireEvent.click(within(row).getByRole('button'));
        expect(navigateWithReferrer).toHaveBeenCalledTimes(1);
        const url = navigateWithReferrer.mock.calls[0][0] as string;
        expect(url).toContain('/auth/sso/login?');
        expect(new URLSearchParams(url.split('?')[1]).get('email')).toBe('jane@example.test');
    });

    it('shows the no-access notice', () => {
        show([choice('alpha'), choice('beta')], {}, 'no_access');
        expect(screen.getByRole('status').textContent).toMatch(/NO_ACCESS|don't have access/);
    });

    describe('with no workspace', () => {
        it('a creator who may: "Create a workspace"', () => {
            show([], { canCreateWorkspace: true });
            expect(screen.getByRole('link', { name: /CREATE|Create a workspace/ }).getAttribute('href')).toBe('/workspace/create');
        });

        it('a creator who may not: an explanation, no button', () => {
            show([], { canCreateWorkspace: false });
            expect(screen.getByText(/EMPTY_ASK|invite you/)).toBeTruthy();
            expect(screen.queryByRole('link')).toBeNull();
        });

        it('a respondent: where their submissions are', () => {
            show([], { isCreator: false });
            expect(screen.getByText(/EMPTY_RESPONDENT|My submissions/)).toBeTruthy();
            expect(screen.queryByRole('link')).toBeNull();
        });
    });

    it('signs out from the screen', () => {
        show([choice('alpha'), choice('beta')]);
        fireEvent.click(screen.getByRole('button', { name: /SIGN_OUT|Sign out/ }));
        expect(openModal).toHaveBeenCalledWith('LOGOUT_VIEW', {});
    });
});
