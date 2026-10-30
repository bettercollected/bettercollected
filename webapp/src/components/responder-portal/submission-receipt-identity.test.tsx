// The receipt opened by its number (no sign-in) carries no identity fields, so
// the page cannot tell "anonymous" from "no email" by `dataOwnerIdentifier`:
// it reads the `anonymize` flag the server sends instead.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SubmissionProvider } from '@app/components/responder-portal/submission-context';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import SubmissionLayoutClient from './submission-layout-client';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => '/x', useSearchParams: () => new URLSearchParams(window.location.search) }));

const receipt = (response: Record<string, unknown>, isUUID = true) => {
    store.dispatch(setWorkspace({ id: 'ws1', ownerId: 'o1', workspaceName: 'vereniging', title: 'Vereniging Voorbeeld' } as any));
    const data = { form: { title: 'Event registration' }, response: { submissionUuid: '0b1c2d3e-aaaa-bbbb-cccc-000000000001', createdAt: '2026-10-01T09:00:00Z', ...response } };
    return render(
        <ReduxProvider store={store}>
            <SubmissionProvider value={{ data, isLoading: false, isError: false, handleRequestForDeletion: () => {}, hasCustomDomain: false, workspaceName: 'vereniging', submissionId: 's1', isUUID }}>
                <SubmissionLayoutClient>
                    <p>content</p>
                </SubmissionLayoutClient>
            </SubmissionProvider>
        </ReduxProvider>
    );
};

afterEach(() => window.history.replaceState(null, '', '/'));

describe('the receipt page identity', () => {
    it('shows the Anonymous mark when the server says the response was anonymous', () => {
        receipt({ anonymize: true });
        expect(screen.getByText('Anonymous')).toBeInTheDocument();
    });

    it('shows no Anonymous mark for a known respondent whose email the receipt leaves out', () => {
        receipt({ anonymize: false });
        expect(screen.queryByText('Anonymous')).not.toBeInTheDocument();
    });

    it('shows no mark on the signed-in view of the own submission (the email is there)', () => {
        receipt({ dataOwnerIdentifier: 'ada@example.test' }, false);
        expect(screen.queryByText('Anonymous')).not.toBeInTheDocument();
    });

    it('treats a signed-in response without an email or flag as anonymous, as before', () => {
        receipt({}, false);
        expect(screen.getByText('Anonymous')).toBeInTheDocument();
    });
});
