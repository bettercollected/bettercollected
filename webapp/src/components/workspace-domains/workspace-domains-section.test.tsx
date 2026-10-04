import React from 'react';

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { WorkspaceDomainDto } from '@app/models/dtos/workspace-domain-dto';
import { store } from '@app/store/store';

import WorkspaceDomainsSection, { checkErrorMessage } from './workspace-domains-section';

// Partial-mock only the hooks; the store keeps the real workspacesApi.
const refetchMock = vi.fn();
const domainsQueryMock: { data: WorkspaceDomainDto[] | undefined; isLoading: boolean; isError: boolean; refetch: typeof refetchMock } = { data: [], isLoading: false, isError: false, refetch: refetchMock };
const claimMock = vi.fn();
const verifyMock = vi.fn();
const deleteMock = vi.fn();
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetEmailDomainsQuery: () => domainsQueryMock,
        useClaimEmailDomainMutation: () => [claimMock, { isLoading: false }],
        useVerifyEmailDomainMutation: () => [verifyMock, { isLoading: false }],
        useDeleteEmailDomainMutation: () => [deleteMock, { isLoading: false }]
    };
});

const toastMock = vi.fn();
vi.mock('@app/shadcn/components/ui/use-toast', () => ({ useToast: () => ({ toast: toastMock }) }));

vi.mock('@app/store/workspaces/slice', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, selectWorkspace: () => ({ id: 'ws1', title: 'Acme' }) };
});

const domain = (overrides: Partial<WorkspaceDomainDto> = {}): WorkspaceDomainDto => ({
    id: 'd1',
    domain: 'acme.com',
    displayDomain: 'acme.com',
    status: 'pending',
    txtRecordName: '_bettercollected-verification.acme.com',
    txtRecordValue: 'bettercollected-domain-verification=0123456789abcdef0123456789abcdef',
    createdAt: '2026-10-04T10:00:00Z',
    verifiedAt: null,
    lastCheckedAt: null,
    lastCheckError: null,
    failedChecks: 0,
    verificationLostAt: null,
    ...overrides
});

const renderSection = () =>
    render(
        <ReduxProvider store={store}>
            <WorkspaceDomainsSection />
        </ReduxProvider>
    );

describe('WorkspaceDomainsSection', () => {
    beforeEach(() => {
        domainsQueryMock.data = [];
        domainsQueryMock.isLoading = false;
        domainsQueryMock.isError = false;
        refetchMock.mockReset();
        claimMock.mockReset().mockResolvedValue({ data: domain() });
        verifyMock.mockReset().mockResolvedValue({ data: domain({ status: 'verified', verifiedAt: '2026-10-04T10:05:00Z' }) });
        deleteMock.mockReset().mockResolvedValue({ data: undefined });
        toastMock.mockReset();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('shows an empty state', () => {
        renderSection();
        expect(screen.getByText(/No domains yet/)).toBeDefined();
    });

    it('shows a load error with a retry instead of the empty state', () => {
        domainsQueryMock.data = undefined;
        domainsQueryMock.isError = true;
        renderSection();
        expect(screen.queryByText(/No domains yet/)).toBeNull();
        expect(screen.getByRole('alert').textContent).toMatch(/couldn.t be loaded/);
        fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
        expect(refetchMock).toHaveBeenCalledTimes(1);
    });

    it('claims a domain', async () => {
        renderSection();
        fireEvent.change(screen.getByLabelText('Add a domain'), { target: { value: ' acme.com ' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add domain' }));
        await waitFor(() => expect(claimMock).toHaveBeenCalledWith({ workspace_id: 'ws1', domain: 'acme.com' }));
        await waitFor(() => expect((screen.getByLabelText('Add a domain') as HTMLInputElement).value).toBe(''));
    });

    it('shows why a domain was refused', async () => {
        claimMock.mockResolvedValue({ error: { status: 422, data: { code: 'free_mail_domain', message: 'Free email providers’ domains cannot be claimed by a workspace.' } } });
        renderSection();
        fireEvent.change(screen.getByLabelText('Add a domain'), { target: { value: 'gmail.com' } });
        fireEvent.click(screen.getByRole('button', { name: 'Add domain' }));
        const alert = await screen.findByRole('alert');
        expect(alert.textContent).toMatch(/Free email providers/);
        expect((screen.getByLabelText('Add a domain') as HTMLInputElement).value).toBe('gmail.com');
    });

    it('shows the TXT record to create, copyable', async () => {
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.assign(navigator, { clipboard: { writeText } });
        domainsQueryMock.data = [domain()];
        renderSection();

        const card = screen.getByTestId('domain-acme.com');
        expect(within(card).getByText('Not verified yet')).toBeDefined();
        expect(within(card).getByText('_bettercollected-verification.acme.com')).toBeDefined();
        expect(within(card).getByText('bettercollected-domain-verification=0123456789abcdef0123456789abcdef')).toBeDefined();

        fireEvent.click(within(card).getByLabelText('Copy record value for acme.com'));
        await waitFor(() => expect(writeText).toHaveBeenCalledWith('bettercollected-domain-verification=0123456789abcdef0123456789abcdef'));
        fireEvent.click(within(card).getByLabelText('Copy record name for acme.com'));
        await waitFor(() => expect(writeText).toHaveBeenCalledWith('_bettercollected-verification.acme.com'));
    });

    it('verifies now and reports success', async () => {
        domainsQueryMock.data = [domain()];
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: 'Verify now' }));
        await waitFor(() => expect(verifyMock).toHaveBeenCalledWith({ workspace_id: 'ws1', domain_id: 'd1' }));
        await waitFor(() => expect(toastMock).toHaveBeenCalledWith({ description: 'acme.com is verified.' }));
    });

    it('explains a failed check', async () => {
        verifyMock.mockResolvedValue({ data: domain({ status: 'failed', lastCheckError: 'no_record', lastCheckedAt: '2026-10-04T10:05:00Z' }) });
        domainsQueryMock.data = [domain()];
        renderSection();
        fireEvent.click(screen.getByRole('button', { name: 'Verify now' }));
        await waitFor(() => expect(toastMock).toHaveBeenCalledWith(expect.objectContaining({ variant: 'destructive', description: expect.stringMatching(/No TXT record was found/) })));
    });

    it('shows each status', () => {
        domainsQueryMock.data = [
            domain({ id: 'a', domain: 'a.com', displayDomain: 'a.com', status: 'verified', verifiedAt: '2026-10-04T10:05:00Z' }),
            domain({ id: 'b', domain: 'b.com', displayDomain: 'b.com', status: 'failed', lastCheckError: 'token_mismatch' }),
            domain({ id: 'c', domain: 'c.com', displayDomain: 'c.com', status: 'conflict', lastCheckError: 'verified_by_another_workspace' }),
            domain({ id: 'd', domain: 'xn--bcher-kva.de', displayDomain: 'bücher.de' })
        ];
        renderSection();

        const verified = screen.getByTestId('domain-a.com');
        expect(within(verified).getByText('Verified')).toBeDefined();
        expect(within(verified).getByRole('button', { name: 'Check again' })).toBeDefined();
        expect(within(verified).getByText(/Keep this TXT record in place/)).toBeDefined();

        const failed = screen.getByTestId('domain-b.com');
        expect(within(failed).getByText('Verification failed')).toBeDefined();
        expect(within(failed).getByText(/none has this verification value/)).toBeDefined();

        const conflict = screen.getByTestId('domain-c.com');
        expect(within(conflict).getByText('Verified by another workspace')).toBeDefined();
        expect(within(conflict).queryByRole('button', { name: 'Verify now' })).toBeNull();
        expect(within(conflict).queryByText('_bettercollected-verification.c.com')).toBeNull();

        const idn = screen.getByTestId('domain-xn--bcher-kva.de');
        expect(within(idn).getByText('bücher.de')).toBeDefined();
        expect(within(idn).getByText('xn--bcher-kva.de')).toBeDefined();
    });

    it('warns when a verified domain lost its record', () => {
        domainsQueryMock.data = [domain({ status: 'verified', verifiedAt: '2026-09-01T10:00:00Z', lastCheckError: 'no_record', failedChecks: 3, verificationLostAt: '2026-10-03T10:00:00Z' })];
        renderSection();
        expect(screen.getByRole('alert').textContent).toMatch(/verification record has been missing/);
    });

    it('removes a domain after confirmation', async () => {
        domainsQueryMock.data = [domain({ status: 'verified' })];
        const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true);
        renderSection();

        fireEvent.click(screen.getByRole('button', { name: 'Remove acme.com' }));
        expect(confirm.mock.calls[0][0]).toMatch(/Single sign-on/);
        expect(deleteMock).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole('button', { name: 'Remove acme.com' }));
        await waitFor(() => expect(deleteMock).toHaveBeenCalledWith({ workspace_id: 'ws1', domain_id: 'd1' }));
    });

    it('maps every check error to a message', () => {
        for (const code of ['no_record', 'token_mismatch', 'dns_timeout', 'dns_error', 'verified_by_another_workspace', 'something_new']) {
            expect(checkErrorMessage(domain({ lastCheckError: code }))).toBeTruthy();
        }
        expect(checkErrorMessage(domain())).toBeNull();
    });
});
