import React from 'react';

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WorkspaceDomainStatus from './workspace-domain-status';

const status = vi.hoisted(() => ({ value: 'unregistered' as string }));

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => '/acme/dashboard/custom-domain' }));
vi.mock('@app/store/hooks', () => ({
    useAppSelector: () => ({ id: 'ws-1', workspaceName: 'acme', customDomain: 'forms.acme.example', isPro: true })
}));
vi.mock('@app/store/workspaces/api', () => ({
    useVerifyWorkspaceDomainQuery: () => ({
        data: { provider: 'custom-domain', id: null, hostname: 'forms.acme.example', status: status.value, verified: false, dns_records: [], checks: [] },
        isLoading: false,
        isFetching: false,
        refetch: vi.fn()
    }),
    useRecheckWorkspaceDomainMutation: () => [vi.fn(), { isLoading: false }]
}));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn() }) }));

describe('a custom domain the new service does not hold yet', () => {
    beforeEach(() => {
        status.value = 'unregistered';
    });

    it('can be deleted while it is being migrated, to add it again now', () => {
        render(<WorkspaceDomainStatus />);
        expect(screen.getByText('Being migrated')).toBeTruthy();
        expect(screen.getByRole('button', { name: 'Domain actions' })).toBeTruthy();
        expect(screen.getByText(/delete it from the menu above and add it again/i)).toBeTruthy();
    });

    it('can still be deleted once it was removed from the service', () => {
        status.value = 'removed';
        render(<WorkspaceDomainStatus />);
        expect(screen.getByText('Removed')).toBeTruthy();
        expect(screen.getByRole('button', { name: 'Domain actions' })).toBeTruthy();
        expect(screen.getByText(/remove it from the menu above and add it again/i)).toBeTruthy();
    });
});
