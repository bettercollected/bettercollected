import { describe, expect, it } from 'vitest';

import { sharedWorkspacesOf } from './delete-account-modal';

describe('sharedWorkspacesOf', () => {
    it('reads the workspaces that block an account deletion', () => {
        const workspaces = [{ id: 'w1', title: 'Team', billingOwnerCanChange: false }];
        expect(sharedWorkspacesOf({ status: 409, data: { code: 'billing_owner_of_shared_workspaces', workspaces } })).toEqual(workspaces);
    });

    it('ignores every other failure', () => {
        expect(sharedWorkspacesOf({ status: 500, data: {} })).toBeNull();
        expect(sharedWorkspacesOf({ status: 409, data: { code: 'something_else' } })).toBeNull();
        expect(sharedWorkspacesOf(undefined)).toBeNull();
    });
});
