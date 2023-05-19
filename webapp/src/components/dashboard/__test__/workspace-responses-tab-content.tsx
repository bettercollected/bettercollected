import { screen } from '@testing-library/react';

import WorkspaceResponsesTabContent from '@app/components/dashboard/workspace-responses-tab-content';
import { initWorkspaceDto } from '@app/models/dtos/workspaceDto';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

jest.mock('next/router', () => ({
    useRouter() {
        return {
            route: '/',
            pathname: '',
            query: '',
            asPath: '',
            push: jest.fn(),
            events: {
                on: jest.fn(),
                off: jest.fn()
            },
            beforePopState: jest.fn(() => null),
            prefetch: jest.fn(() => null)
        };
    }
}));

describe('Render Workspaces Responses', () => {
    it('should render loading initially', async function () {
        renderWithProviders(<WorkspaceResponsesTabContent workspace={initWorkspaceDto} />);
        expect(screen.getByTestId('loader')).toBeInTheDocument();

        // await waitFor(() => {
        //     expect(screen.getByTestId('empty-forms-view')).toBeInTheDocument();
        // });
    });
});
