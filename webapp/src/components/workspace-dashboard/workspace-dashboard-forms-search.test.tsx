import React from 'react';

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import I18nProvider from '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';

import WorkspaceDashboardForms from './workspace-dashboard-forms';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
// the cards stand in: what matters here is the list's own "clear the search" handler
vi.mock('@app/components/workspace-dashboard/workspace-dashboard-form-cards', () => ({
    default: ({ showEmpty, onClearSearch }: { showEmpty?: boolean; onClearSearch?: () => void }) =>
        showEmpty ? (
            <button type="button" onClick={onClearSearch}>
                Clear search
            </button>
        ) : (
            <p>form cards</p>
        )
}));
vi.mock('@app/views/atoms/new-form-button', () => ({ default: () => <button>New form</button> }));
vi.mock('@app/lib/hooks/use-google-forms-import-mode', () => ({ useGoogleFormsImportMode: () => ({ mode: 'on' }) }));

vi.mock('@app/store/workspaces/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return {
        ...actual,
        useGetWorkspaceFormsQuery: () => ({ isLoading: false, data: { items: [{ formId: 'f1', title: 'Survey' }], total: 1, pages: 1 } }),
        useLazySearchWorkspaceFormsQuery: () => [vi.fn().mockResolvedValue({ data: [] })]
    };
});

beforeEach(() => {
    store.dispatch(setWorkspace({ id: 'ws1', workspaceName: 'acme', title: 'Acme' } as any));
});
afterEach(() => {
    cleanup();
});

describe('clearing a search that found nothing', () => {
    it('empties the search box and puts focus back in it, not on the page', async () => {
        render(
            <ReduxProvider store={store}>
                <I18nProvider>
                    <WorkspaceDashboardForms workspace={{ id: 'ws1' } as any} hasCustomDomain={false} showPagination />
                </I18nProvider>
            </ReduxProvider>
        );
        const box = () => screen.getByRole('textbox') as HTMLInputElement;
        fireEvent.change(box(), { target: { value: 'zzzz' } });
        // the search box waits 500 ms before it asks; it found nothing, so the empty state's action appears
        const clear = await screen.findByRole('button', { name: 'Clear search' }, { timeout: 3000 });
        fireEvent.click(clear);
        await waitFor(() => expect(screen.getByText('form cards')).toBeInTheDocument());
        expect(box().value).toBe('');
        expect(document.activeElement).toBe(box());
    });
});
