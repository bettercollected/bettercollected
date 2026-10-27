import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import WorkspaceFormCard from './workspace-form-card';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@app/components/modal-views/context', () => ({ useModal: () => ({ openModal: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-group-form', () => ({ useGroupForm: () => ({ deleteFormFromGroup: vi.fn() }) }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ can: () => false, ready: true, isLoading: false }) }));
vi.mock('@Components/datatable/form-options-dropdown', () => ({ default: () => null }));

const workspace = { id: 'ws1', workspaceName: 'acme' } as any;
const form = (settings: Record<string, unknown>) => ({ formId: 'f1', title: 'Imported form', isPublished: false, builderVersion: 'v2', settings: { provider: 'self', ...settings } }) as any;

function renderCard(settings: Record<string, unknown>, extra: Record<string, unknown> = {}) {
    return render(
        <ReduxProvider store={store}>
            <WorkspaceFormCard form={form(settings)} workspace={workspace} hasCustomDomain={false} {...extra} />
        </ReduxProvider>
    );
}

describe('the forms list', () => {
    it('marks an imported form that needs review', () => {
        renderCard({ needsReview: true, importSource: 'open_formulieren', importId: 'imp1' });
        expect(screen.getByText('Needs review')).toBeInTheDocument();
        expect(screen.getByText('Imported form')).toBeInTheDocument();
    });

    it('has no mark once the form is reviewed, or for a form that was not imported', () => {
        const { unmount } = renderCard({ needsReview: false, importSource: 'open_formulieren', importId: 'imp1' });
        expect(screen.queryByText('Needs review')).toBeNull();
        unmount();
        renderCard({});
        expect(screen.queryByText('Needs review')).toBeNull();
    });

    it('does not show the mark to respondents', () => {
        renderCard({ needsReview: true, importSource: 'open_formulieren', importId: 'imp1' }, { isResponderPortal: true });
        expect(screen.queryByText('Needs review')).toBeNull();
    });
});
