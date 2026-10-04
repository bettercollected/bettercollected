import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { store } from '@app/store/store';

import InternalFieldsPanel from './internal-fields-panel';
import ResponseSegments from './response-segments';

// Reviewer, Viewer and Privacy officer see the response views without the
// controls their role can't use (the backend refuses them anyway).
const access: { permissions: string[] } = { permissions: [] };
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({
    useWorkspacePermissions: () => ({ can: (permission: string) => access.permissions.includes(permission), permissions: new Set(access.permissions), isLoading: false })
}));
vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/forms/f1/responses',
    useParams: () => ({ workspace_name: 'acme', form_id: 'f1' })
}));
vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useUpdateInternalAnswersMutation: () => [vi.fn(), { isLoading: false }] };
});

const VIEWER = ['form.read', 'response.read', 'analytics.read'];
const REVIEWER = [...VIEWER, 'response.annotate'];
const EDITOR = [...REVIEWER, 'form.edit', 'response.delete', 'response.export'];
const PRIVACY_OFFICER = ['form.read', 'privacy.manage', 'analytics.read', 'audit.read'];

const FIELD: any = { id: 'note', type: 'short_text', title: 'Note', internal: true };
const RESPONSE: any = { responseId: 'r1', internalAnswers: {}, internalAnswersMeta: {}, internalAnswersVersion: 0 };

const renderPanel = () =>
    render(
        <ReduxProvider store={store}>
            <InternalFieldsPanel fields={[FIELD]} response={RESPONSE} formId="f1" workspaceId="ws-1" />
        </ReduxProvider>
    );

describe('InternalFieldsPanel', () => {
    it('is read-only for a Viewer', () => {
        access.permissions = VIEWER;
        renderPanel();
        expect((screen.getByRole('textbox') as HTMLInputElement).closest('fieldset')?.disabled).toBe(true);
        expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
    });

    it('is editable for a Reviewer', () => {
        access.permissions = REVIEWER;
        renderPanel();
        expect((screen.getByRole('textbox') as HTMLInputElement).closest('fieldset')?.disabled).toBe(false);
        expect(screen.getByRole('button', { name: 'Save' })).toBeDefined();
    });
});

describe('ResponseSegments', () => {
    const renderSegments = () =>
        render(
            <ReduxProvider store={store}>
                <ResponseSegments />
            </ReduxProvider>
        );

    it('offers both views to an Editor', () => {
        access.permissions = [...EDITOR, 'privacy.manage'];
        renderSegments();
        expect(screen.getByText('All responses')).toBeDefined();
        expect(screen.getByText('Deletion requests')).toBeDefined();
    });

    it('never links a Privacy officer to the answers', () => {
        access.permissions = PRIVACY_OFFICER;
        renderSegments();
        expect(screen.queryByText('All responses')).toBeNull();
    });

    it('leaves out deletion requests for a Viewer', () => {
        access.permissions = VIEWER;
        renderSegments();
        expect(screen.queryByText('Deletion requests')).toBeNull();
    });
});
