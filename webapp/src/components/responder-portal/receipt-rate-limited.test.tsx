// The receipt routes answer 429 for a few minutes after too many lookups from
// one address. That must read as "too many attempts", in the respondent's
// language, never as "no submission with this number" (the number may be valid).
import React from 'react';

import { fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import SearchBySubmissionNumber from './search-by-submission-number';
import SharedSubmissionLayoutClient from './shared-submission-layout-client';

const api = vi.hoisted(() => ({
    lookup: vi.fn(),
    receipt: { data: undefined as any, isLoading: false, isError: false, error: undefined as any }
}));

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: vi.fn() }),
    usePathname: () => '/vereniging/submissions/uuid/n1/form',
    useSearchParams: () => new URLSearchParams(window.location.search)
}));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn(), closeModal: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: () => false, permissions: new Set(), isLoading: false, ready: true, answered: true })
}));
vi.mock('@app/store/workspaces/api', async (importOriginal) => ({
    ...(await importOriginal<typeof import('@app/store/workspaces/api')>()),
    useLazyGetWorkspaceSubmissionByUUIDQuery: () => [api.lookup, { isLoading: false }],
    useGetWorkspaceSubmissionByUUIDQuery: () => api.receipt,
    useGetWorkspaceSubmissionQuery: () => ({ data: undefined, isLoading: false, isError: false }),
    useRequestWorkspaceSubmissionDeletionByUUIDMutation: () => [vi.fn()],
    useRequestWorkspaceSubmissionDeletionMutation: () => [vi.fn()]
}));

const at = (url: string) => window.history.replaceState(null, '', url);

beforeEach(() => {
    store.dispatch(setWorkspace({ id: 'ws1', ownerId: 'o1', workspaceName: 'vereniging', title: 'Vereniging Voorbeeld' } as any));
});

afterEach(() => {
    at('/');
    api.lookup.mockReset();
    api.receipt = { data: undefined, isLoading: false, isError: false, error: undefined };
});

const search = async (status: number) => {
    api.lookup.mockResolvedValue({ error: { status, data: {} } });
    render(
        <ReduxProvider store={store}>
            <SearchBySubmissionNumber />
        </ReduxProvider>
    );
    const field = screen.getByRole('textbox');
    fireEvent.change(field, { target: { value: '0b1c2d3e-aaaa-4bbb-8ccc-000000000001' } });
    fireEvent.submit(field.closest('form')!);
    return field;
};

describe('looking a submission up by its number', () => {
    it('says "too many attempts" when the lookup is rate limited', async () => {
        const field = await search(429);
        expect(await screen.findByText('Too many attempts. Try again in a few minutes.')).toBeInTheDocument();
        expect(screen.queryByText('The submission number does not match with any form responses')).not.toBeInTheDocument();
        // the number is not marked wrong: it may well be right
        expect(field).not.toHaveAttribute('aria-invalid');
    });

    it('says so in Dutch for a Dutch respondent', async () => {
        at('/vereniging/forms?lang=nl');
        await search(429);
        expect(await screen.findByText('Te veel pogingen. Probeer het over een paar minuten opnieuw.')).toBeInTheDocument();
    });

    it('still says "not found" for an unknown number', async () => {
        const field = await search(404);
        expect(await screen.findByText('The submission number does not match with any form responses')).toBeInTheDocument();
        expect(field).toHaveAttribute('aria-invalid', 'true');
    });
});

const receiptPage = () =>
    render(
        <ReduxProvider store={store}>
            <SharedSubmissionLayoutClient submissionId="0b1c2d3e-aaaa-4bbb-8ccc-000000000001" isUUID>
                <p>content</p>
            </SharedSubmissionLayoutClient>
        </ReduxProvider>
    );

describe('the receipt page opened by its number', () => {
    it('says "too many attempts" instead of loading forever when rate limited', async () => {
        api.receipt = { data: undefined, isLoading: false, isError: true, error: { status: 429, data: {} } };
        receiptPage();
        expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts. Try again in a few minutes.');
    });

    it('in Dutch for a Dutch respondent', async () => {
        at('/vereniging/submissions/uuid/n1/form?lang=nl');
        api.receipt = { data: undefined, isLoading: false, isError: true, error: { status: 429, data: {} } };
        receiptPage();
        expect(await screen.findByRole('alert')).toHaveTextContent('Te veel pogingen. Probeer het over een paar minuten opnieuw.');
    });

    it('shows no such message for another error', () => {
        api.receipt = { data: undefined, isLoading: false, isError: true, error: { status: 404, data: {} } };
        receiptPage();
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
});
