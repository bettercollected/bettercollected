import { fireEvent, screen } from '@testing-library/react';

import OtpRenderer from '@app/components/login/otp-renderer';
import { renderWithProviders } from '@app/utils/__test_utils__/render-with-provider';

jest.mock('react-toastify', () => ({
    toast: {
        error: jest.fn()
    }
}));

describe('Render and test Otp renderer flow', () => {
    it('should  render Otp renderer component', async function () {
        renderWithProviders(<OtpRenderer email="ankit.sapkota555@gmail.com" isCustomDomain={false} />);
        fireEvent.change(screen.getByTestId('otp-input'), { target: { value: '' } });
        expect(screen.getByTestId('verify-button')).toBeDisabled();
        fireEvent.change(screen.getByTestId('otp-input'), { target: { value: 'clb-05g' } });
        fireEvent.click(screen.getByTestId('verify-button'));
        // TODO: check for modal close (if possible)
    });
});
