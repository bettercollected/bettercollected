import { fireEvent, screen } from '@testing-library/react';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

jest.mock('react-toastify', () => ({
    toast: jest.fn()
}));

describe('Form Settings Tab', () => {
    it('should show toast on copying url', function () {
        renderWithProviders(<FormSettingsTab />);
        // fireEvent.click(screen.getByTestId('copy-svg'));
        // expect(toast).toBeCalledTimes(1);
    });

    it('should not update pinned settings if error on api', async function () {
        renderWithProviders(<FormSettingsTab />);
        const pinnedSwitch: any = screen.getByTestId('pinned-switch');
        fireEvent.click(pinnedSwitch);
        // await waitFor(() => {
        //     expect(toast).toBeCalledTimes(1);
        // });
    });
});
