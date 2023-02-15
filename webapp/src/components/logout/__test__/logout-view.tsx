import { useRouter } from 'next/router';

import { fireEvent, screen, waitFor } from '@testing-library/react';

import LogoutView from '@app/components/logout/logout-view';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

jest.mock('next/router', () => ({
    useRouter: jest.fn()
}));

describe('Render Logout View ', () => {
    it('should render the logout component and call logout api when clicked', async function () {
        const mockRouter = {
            push: jest.fn()
        };
        (useRouter as jest.Mock).mockReturnValue(mockRouter);

        renderWithProviders(<LogoutView />);

        fireEvent.click(screen.getByTestId('logout-button'));

        await waitFor(() => {
            expect(mockRouter.push).toBeCalledTimes(1);
        });
    });
});
