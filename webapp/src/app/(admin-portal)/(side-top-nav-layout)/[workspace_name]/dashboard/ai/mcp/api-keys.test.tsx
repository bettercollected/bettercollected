// The API key dialog: the "Submit responses" scope is offered only while the server has the feature on,
// can be limited to chosen forms, and a key's list says which forms it submits to.
import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import '@app/shared/hocs/i18n-provider';

import APIKeysPage from './page';

const permissions: { enabled: boolean } = { enabled: true };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (p: string) => p === WorkspacePermission.SECURITY_MANAGE, submissionsApiEnabled: permissions.enabled })
}));
vi.mock('@app/store/hooks', () => ({ useAppSelector: () => ({ id: 'workspace-1', workspaceName: 'acme' }) }));
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toasted }) }));

const created = vi.fn();
const toasted = vi.fn();
const KEYS: any[] = [];
const formsAsked = vi.fn();
// the published forms, a page each (the API's pages: `pages` is how many there are)
const ONE_PAGE = [
    {
        page: 1,
        pages: 1,
        items: [
            { formId: 'f1', title: 'Registration' },
            { formId: 'f2', title: '' }
        ]
    }
];
let formPages: any[] = ONE_PAGE;
vi.mock('@app/store/workspaces/api', () => ({
    useGetAPIKeysQuery: () => ({ data: KEYS, isLoading: false }),
    useCreateAPIKeyMutation: () => [(arg: any) => Promise.resolve(created(arg) ?? { data: { name: 'k', token: 'bc_x' } }), { isLoading: false }],
    useRevokeAPIKeyMutation: () => [vi.fn()],
    useGetWorkspaceFormsQuery: (arg: any) => {
        formsAsked(arg);
        return { data: formPages[arg.page - 1] ?? formPages[0] };
    }
}));

const scopeBox = (name: string) => screen.getByRole('checkbox', { name: new RegExp(name) });

beforeEach(() => {
    permissions.enabled = true;
    created.mockReset();
    toasted.mockReset();
    formsAsked.mockReset();
    formPages = ONE_PAGE;
    KEYS.length = 0;
});

describe('the API key dialog and submissions', () => {
    it('offers the scope only while the server has the feature on', () => {
        permissions.enabled = false;
        const { unmount } = render(<APIKeysPage />);
        expect(screen.queryByRole('checkbox', { name: /Submit responses/ })).toBeNull();
        unmount();
        permissions.enabled = true;
        render(<APIKeysPage />);
        expect(scopeBox('Submit responses')).not.toBeChecked();
    });

    it('creates a key for every form unless it is limited, and then for the forms picked', () => {
        render(<APIKeysPage />);
        fireEvent.change(screen.getByPlaceholderText(/./), { target: { value: 'CRM sync' } });
        fireEvent.click(scopeBox('Submit responses'));
        fireEvent.click(screen.getByRole('button', { name: 'Create key' }));
        expect(created.mock.calls[0][0].body).toEqual({ name: 'CRM sync', scopes: ['forms:read', 'submissions:write'], acknowledgeUnredactedResponses: false });

        created.mockClear();
        fireEvent.click(scopeBox('Only for these forms'));
        // limited to nothing is not a key: the button waits for a form
        expect(screen.getByRole('button', { name: 'Create key' })).toBeDisabled();
        fireEvent.click(screen.getByRole('checkbox', { name: 'Registration' }));
        fireEvent.click(screen.getByRole('button', { name: 'Create key' }));
        expect(created.mock.calls[0][0].body.submissionFormIds).toEqual(['f1']);
    });

    it('pages through every published form, keeping the ones picked on earlier pages', () => {
        formPages = [
            { page: 1, pages: 2, items: [{ formId: 'f1', title: 'Registration' }] },
            { page: 2, pages: 2, items: [{ formId: 'f101', title: 'Feedback' }] }
        ];
        render(<APIKeysPage />);
        fireEvent.change(screen.getByPlaceholderText(/./), { target: { value: 'CRM sync' } });
        fireEvent.click(scopeBox('Submit responses'));
        fireEvent.click(scopeBox('Only for these forms'));
        expect(formsAsked.mock.calls.at(-1)[0]).toMatchObject({ published: true, page: 1, size: 100 });
        fireEvent.click(screen.getByRole('checkbox', { name: 'Registration' }));
        expect(screen.queryByRole('checkbox', { name: 'Feedback' })).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: 'Show more forms' }));
        expect(formsAsked.mock.calls.at(-1)[0]).toMatchObject({ page: 2 });
        // the second page is added below the first; the last page has no button
        fireEvent.click(screen.getByRole('checkbox', { name: 'Feedback' }));
        expect(screen.getByRole('checkbox', { name: 'Registration' })).toBeChecked();
        expect(screen.queryByRole('button', { name: 'Show more forms' })).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: 'Create key' }));
        expect(created.mock.calls[0][0].body.submissionFormIds).toEqual(['f1', 'f101']);
    });

    it('says which forms a key submits to', () => {
        KEYS.push(
            { id: 'a', name: 'All', prefix: 'bc_aaaa', scopes: ['submissions:write'], revoked: false },
            { id: 'b', name: 'Some', prefix: 'bc_bbbb', scopes: ['submissions:write'], submissionFormIds: ['f1', 'f2'], revoked: false },
            { id: 'c', name: 'Reader', prefix: 'bc_cccc', scopes: ['forms:read'], revoked: false }
        );
        render(<APIKeysPage />);
        expect(screen.getByText(/submits to every form/)).toBeInTheDocument();
        expect(screen.getByText(/submits to 2 forms/)).toBeInTheDocument();
        expect(screen.getAllByText(/submits to/)).toHaveLength(2);
    });

    it('shows the server’s message when it refuses the key, also when the answer is an object', async () => {
        render(<APIKeysPage />);
        fireEvent.change(screen.getByPlaceholderText(/./), { target: { value: 'CRM sync' } });
        created.mockReturnValueOnce({ error: { data: { code: 'submissions_api_off', message: 'Creating responses through the API is turned off on this instance.' } } });
        fireEvent.click(screen.getByRole('button', { name: 'Create key' }));
        await waitFor(() => expect(toasted).toHaveBeenCalled());
        expect(toasted.mock.calls[0][0].description).toBe('Creating responses through the API is turned off on this instance.');
        // a string stays a string; anything else is the generic text
        created.mockReturnValueOnce({ error: { data: 'Unknown scopes: x.' } });
        fireEvent.click(screen.getByRole('button', { name: 'Create key' }));
        await waitFor(() => expect(toasted).toHaveBeenCalledTimes(2));
        expect(toasted.mock.calls[1][0].description).toBe('Unknown scopes: x.');
        created.mockReturnValueOnce({ error: { data: { unexpected: true } } });
        fireEvent.click(screen.getByRole('button', { name: 'Create key' }));
        await waitFor(() => expect(toasted).toHaveBeenCalledTimes(3));
        expect(toasted.mock.calls[2][0].description).toBe('Could not create the API key. Please try again.');
    });

    it('drops the scope when the feature is turned off while the dialog is open', () => {
        const { rerender } = render(<APIKeysPage />);
        fireEvent.click(scopeBox('Submit responses'));
        expect(scopeBox('Submit responses')).toBeChecked();
        permissions.enabled = false;
        rerender(<APIKeysPage />);
        expect(screen.queryByRole('checkbox', { name: /Submit responses/ })).toBeNull();
        fireEvent.change(screen.getByPlaceholderText(/./), { target: { value: 'k' } });
        fireEvent.click(screen.getByRole('button', { name: 'Create key' }));
        expect(created.mock.calls[0][0].body.scopes).toEqual(['forms:read']);
    });
});
