import { screen, waitFor } from '@testing-library/react';
import { rest } from 'msw';

import WorkspaceFormsTabContent from '@app/components/dashboard/workspace-forms-tab-content';
import { server } from '@app/mock/api/server';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

describe('render workspace forms tab in workspace page', () => {
    it('should render component', async function () {
        const { rerender } = renderWithProviders(<WorkspaceFormsTabContent workspace={initWorkspaceDto} />);
        expect(screen.getByTestId('loader')).toBeInTheDocument();
        await waitFor(() => {
            expect(screen.getByTestId('empty-view')).toBeInTheDocument();
        });
        rerender(<WorkspaceFormsTabContent workspace={initWorkspaceDto} />);
    });
});
