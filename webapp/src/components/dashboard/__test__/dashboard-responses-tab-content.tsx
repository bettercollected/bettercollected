import '@testing-library/jest-dom';
import { screen } from '@testing-library/react';
import { rest } from 'msw';
import 'whatwg-fetch';

import DashboardResponsesTabContent from '@app/components/dashboard/dashboard-responses-tab-content';
import { server } from '@app/mock/api/server';
import mockUseBreakPoint from '@app/utils/__test_utils__/mock-use-breakpoint';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

mockUseBreakPoint('xs');

jest.mock('next/router', () => ({
    useRouter: () => ({
        query: { sub_id: '123456' },
        path: '/dashboard',
        push: jest.fn()
    })
}));

describe('Test Dashboard Responses Component', () => {
    it('should render component', async function () {
        server.use(
            rest.get('http://localhost/workspaces/undefined/submissions/123456', (req, res, ctx) => {
                return res(ctx.status(500));
            })
        );
        renderWithProviders(<DashboardResponsesTabContent />);
        expect(await screen.getByTestId('full-screen-loader')).toBeInTheDocument();
        expect(screen.queryByTestId('form-renderer')).toBe(null);
    });

    it('renders form when form is provided', async () => {
        server.use(
            rest.get('http://localhost/workspaces/undefined/submissions/123456', (req, res, ctx) => {
                return res(
                    ctx.body(
                        JSON.stringify({
                            formId: 'Hello World'
                        })
                    )
                );
            })
        );
        renderWithProviders(<DashboardResponsesTabContent />);
    });
});
