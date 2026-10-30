// The receipt opened by its number (no sign-in) carries no identity fields, so
// the page cannot tell "anonymous" from "no email" by `dataOwnerIdentifier`:
// it reads the `anonymize` flag the server sends instead.
import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SubmissionProvider } from '@app/components/responder-portal/submission-context';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { initialAuthState, setAuth } from '@app/store/auth/slice';
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import SubmissionLayoutClient from './submission-layout-client';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => '/x', useSearchParams: () => new URLSearchParams(window.location.search) }));

// what the viewer may do in the workspace (staff read every response; a respondent only their own);
// `failed`: the permissions request failed (settled, but no answer, so nothing is granted)
const viewer: { permissions: string[]; ready: boolean; failed: boolean } = { permissions: [], ready: true, failed: false };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => {
        const permissions = viewer.failed ? [] : viewer.permissions;
        return { can: (permission: string) => permissions.includes(permission), permissions: new Set(permissions), isLoading: !viewer.ready, ready: viewer.ready, answered: viewer.ready && !viewer.failed };
    }
}));

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

afterEach(() => {
    window.history.replaceState(null, '', '/');
    viewer.permissions = [];
    viewer.ready = true;
    viewer.failed = false;
    store.dispatch(setAuth(initialAuthState));
});

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

describe('the receipt number on the submission page', () => {
    const NUMBER = '0b1c2d3e-aaaa-bbbb-cccc-000000000001';
    // every attribute value and the text of the whole page
    const everythingInTheDom = (container: HTMLElement) =>
        [container.textContent ?? '', ...Array.from(container.querySelectorAll('*')).flatMap((element) => Array.from(element.attributes).map((attribute) => attribute.value))].join('\n');

    it('is shown in full when the page was opened by the number itself', () => {
        receipt({ anonymize: true }, true);
        expect(screen.getByText(`#${NUMBER}`)).toBeInTheDocument();
    });

    it('is shown in full to the respondent on their own submission', () => {
        store.dispatch(setAuth({ id: 'u1', email: 'ada@example.test', roles: [] } as any));
        receipt({ dataOwnerIdentifier: 'ada@example.test' }, false);
        expect(screen.getByText(`#${NUMBER}`)).toBeInTheDocument();
    });

    it('is shown in full to a respondent who cannot read other responses (an anonymous submission of their own)', () => {
        store.dispatch(setAuth({ id: 'u1', email: 'ada@example.test', roles: [] } as any));
        receipt({ anonymize: true }, false);
        expect(screen.getByText(`#${NUMBER}`)).toBeInTheDocument();
    });

    it("is shortened for staff who open someone else's response by its id: never in full in the DOM", () => {
        store.dispatch(setAuth({ id: 'staff', email: 'staff@example.test', roles: [] } as any));
        viewer.permissions = [WorkspacePermission.RESPONSE_READ];
        const { container } = receipt({ dataOwnerIdentifier: 'ada@example.test' }, false);
        expect(screen.getByText('#0b1c2d3e…')).toBeInTheDocument();
        expect(everythingInTheDom(container)).not.toContain(NUMBER);
        expect(everythingInTheDom(container)).not.toContain('aaaa-bbbb');
    });

    it('is shortened for staff on an anonymous response too, and while the permissions are still loading', () => {
        store.dispatch(setAuth({ id: 'staff', email: 'staff@example.test', roles: [] } as any));
        viewer.permissions = [WorkspacePermission.RESPONSE_READ];
        const { unmount } = receipt({ anonymize: true }, false);
        expect(screen.getByText('#0b1c2d3e…')).toBeInTheDocument();
        unmount();
        viewer.permissions = [];
        viewer.ready = false;
        receipt({ anonymize: true }, false);
        expect(screen.getByText('#0b1c2d3e…')).toBeInTheDocument();
    });

    it('is shortened for staff whose permissions request failed (no answer is not "cannot read others")', () => {
        store.dispatch(setAuth({ id: 'staff', email: 'staff@example.test', roles: [] } as any));
        viewer.permissions = [WorkspacePermission.RESPONSE_READ];
        viewer.failed = true;
        const { container } = receipt({ dataOwnerIdentifier: 'ada@example.test' }, false);
        expect(screen.getByText('#0b1c2d3e…')).toBeInTheDocument();
        expect(everythingInTheDom(container)).not.toContain(NUMBER);
    });
});
